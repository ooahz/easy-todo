"""导出 Excel 筛选对话框"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QGridLayout, QButtonGroup, QSizePolicy,
)

from qfluentwidgets import (
    MessageBoxBase, SubtitleLabel, BodyLabel, RadioButton, FastCalendarPicker,
)


# 时间字段选项
DATE_FIELD_OPTIONS = [
    ("", "不按时间筛选"),
    ("due_date", "截止时间"),
    ("created_at", "创建时间"),
]


class ExcelExportFilterDialog(MessageBoxBase):
    """导出 Excel 前的筛选对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)

        self._date_field: str = ""
        self._start_date: Optional[date] = None
        self._end_date: Optional[date] = None

        self.widget.setMinimumWidth(440)

        title = SubtitleLabel("导出 Excel 筛选")
        self.viewLayout.addWidget(title)

        # 时间字段
        self.viewLayout.addWidget(self._make_section_label("按时间筛选："))
        self._field_btn_group = QButtonGroup(self)
        self._field_radios: list[RadioButton] = []
        for field_key, label in DATE_FIELD_OPTIONS:
            radio = RadioButton(label)
            self._field_btn_group.addButton(radio)
            self._field_radios.append((field_key, radio))
            self.viewLayout.addWidget(radio)
        self._field_radios[0][1].setChecked(True)
        self._field_btn_group.buttonClicked.connect(self._on_field_changed)

        # 日期范围
        self._range_container = QVBoxLayout()
        self.viewLayout.addLayout(self._range_container)

        # 快捷范围
        self._range_container.addWidget(self._make_section_label("快捷范围："))
        quick_layout = QHBoxLayout()
        quick_layout.setSpacing(8)
        self._btn_group = QButtonGroup(self)
        for key, label in [
            (7, "近 7 天"),
            (30, "近 30 天"),
            ("prev_week", "前一周"),
            (None, "自定义"),
        ]:
            btn = RadioButton(label)
            quick_layout.addWidget(btn)
            self._btn_group.addButton(btn)
            btn.setProperty("_range_key", key)
        self._btn_group.buttonClicked.connect(self._on_quick_changed)
        self._range_container.addLayout(quick_layout)

        # 自定义日期
        date_grid = QGridLayout()
        date_grid.setHorizontalSpacing(12)
        date_grid.setVerticalSpacing(6)
        date_grid.addWidget(BodyLabel("起始日期："), 0, 0, Qt.AlignmentFlag.AlignRight)
        date_grid.addWidget(BodyLabel("结束日期："), 1, 0, Qt.AlignmentFlag.AlignRight)

        self._start_edit = FastCalendarPicker()
        self._end_edit = FastCalendarPicker()
        for picker in (self._start_edit, self._end_edit):
            picker.setDateFormat("yyyy-MM-dd")
            picker.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        today = date.today()
        default_start = QDate(today.year, today.month, today.day)
        self._start_edit.setDate(default_start)
        self._end_edit.setDate(default_start)

        date_grid.addWidget(self._start_edit, 0, 1)
        date_grid.addWidget(self._end_edit, 1, 1)

        self._range_container.addLayout(date_grid)

        # 初始状态：未启用时间筛选时禁用范围
        self._set_range_enabled(False)

        self.yesButton.setText("开始导出")
        self.cancelButton.setText("取消")

    def _make_section_label(self, text: str) -> BodyLabel:
        label = BodyLabel(text)
        label.setStyleSheet("font-weight: bold; margin-top: 4px;")
        return label

    def _on_field_changed(self, btn: RadioButton):
        for field_key, radio in self._field_radios:
            if radio is btn:
                self._date_field = field_key
                break
        self._set_range_enabled(bool(self._date_field))

    def _on_quick_changed(self, btn: RadioButton):
        key = btn.property("_range_key")
        if key is None:
            return
        end = date.today()
        if key == "prev_week":
            today_weekday = end.weekday()  # 周一=0
            this_monday = end - timedelta(days=today_weekday)
            end = this_monday - timedelta(days=1)
            start = end - timedelta(days=6)
        else:
            start = end - timedelta(days=key - 1)
        self._start_edit.setDate(QDate(start.year, start.month, start.day))
        self._end_edit.setDate(QDate(end.year, end.month, end.day))

    def _set_range_enabled(self, enabled: bool):
        for w in [self._start_edit, self._end_edit]:
            w.setEnabled(enabled)
        for btn in self._btn_group.buttons():
            btn.setEnabled(enabled)

    def accept(self):
        if self._date_field:
            q_start = self._start_edit.date
            q_end = self._end_edit.date
            self._start_date = date(q_start.year(), q_start.month(), q_start.day())
            self._end_date = date(q_end.year(), q_end.month(), q_end.day())
            if self._start_date > self._end_date:
                from qfluentwidgets import InfoBar, InfoBarPosition
                InfoBar.error(
                    title="日期范围无效",
                    content="结束时间不能小于开始时间",
                    parent=self,
                    position=InfoBarPosition.TOP,
                    duration=2000,
                )
                return
            if (self._end_date - self._start_date).days > 365:
                from qfluentwidgets import InfoBar, InfoBarPosition
                InfoBar.error(
                    title="日期范围无效",
                    content="时间范围不能超过一年",
                    parent=self,
                    position=InfoBarPosition.TOP,
                    duration=2000,
                )
                return
        else:
            self._start_date = None
            self._end_date = None
        super().accept()

    @property
    def date_field(self) -> str:
        return self._date_field

    @property
    def date_field_label(self) -> str:
        for field_key, label in DATE_FIELD_OPTIONS:
            if field_key == self._date_field:
                return label
        return ""

    @property
    def start_date(self) -> Optional[date]:
        return self._start_date

    @property
    def end_date(self) -> Optional[date]:
        return self._end_date
