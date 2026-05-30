"""重复任务删除对话框"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QButtonGroup, QFrame

from qfluentwidgets import (
    MessageBoxBase, SubtitleLabel, BodyLabel, CaptionLabel,
    RadioButton, CheckBox, IconWidget, FluentIcon, isDarkTheme,
)


def _colors():
    if isDarkTheme():
        return {
            "option_bg": "#2D2D2D",
            "option_selected_bg": "rgba(96, 205, 255, 0.08)",
            "option_selected_border": "rgba(96, 205, 255, 0.3)",
            "border": "rgba(255, 255, 255, 0.06)",
            "muted": "#999",
            "body": "#BBB",
            "accent": "#60CDFF",
            "danger": "#FF6B6B",
            "warning": "#FFB347",
        }
    return {
        "option_bg": "#FFFFFF",
        "option_selected_bg": "rgba(0, 120, 212, 0.05)",
        "option_selected_border": "rgba(0, 120, 212, 0.3)",
        "border": "rgba(0, 0, 0, 0.06)",
        "muted": "#999",
        "body": "#555",
        "accent": "#0078D4",
        "danger": "#D13438",
        "warning": "#FF8C00",
    }


class _OptionCard(QFrame):
    """可选择的选项卡片"""

    clicked = None

    def __init__(self, icon: FluentIcon, title: str, desc: str,
                 color: str, parent=None):
        super().__init__(parent)
        self._selected = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(64)
        c = _colors()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)

        icon_w = IconWidget(icon)
        icon_w.setFixedSize(20, 20)
        icon_w.setStyleSheet(f"color: {color};")
        layout.addWidget(icon_w)

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(1)

        title_label = BodyLabel(title)
        title_label.setStyleSheet(f"color: {c['body']}; font-size: 13px; font-weight: 500;")
        text_layout.addWidget(title_label)

        desc_label = CaptionLabel(desc)
        desc_label.setStyleSheet(f"color: {c['muted']}; font-size: 11px;")
        desc_label.setWordWrap(True)
        text_layout.addWidget(desc_label)

        layout.addLayout(text_layout, 1)

        self._apply_style()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            parent_dlg = self.parent()
            while parent_dlg and not isinstance(parent_dlg, RecurrenceDeleteDialog):
                parent_dlg = parent_dlg.parent()
            if parent_dlg:
                for i, card in enumerate(parent_dlg._cards):
                    if card is self:
                        parent_dlg._radios[i].setChecked(True)
                        break
        super().mousePressEvent(event)

    def set_selected(self, selected: bool):
        self._selected = selected
        self._apply_style()

    def _apply_style(self):
        c = _colors()
        if self._selected:
            self.setStyleSheet(
                f"background: {c['option_selected_bg']};"
                f"border: 1px solid {c['option_selected_border']};"
                f"border-radius: 8px;"
            )
        else:
            self.setStyleSheet(
                f"background: {c['option_bg']};"
                f"border: 1px solid {c['border']};"
                f"border-radius: 8px;"
            )


class RecurrenceDeleteDialog(MessageBoxBase):
    """重复任务删除对话框：RadioButton + 选项卡片 + 文件删除选项"""

    def __init__(self, file_count: int = 0, parent=None):
        super().__init__(parent)
        self._result_mode: str | None = None

        self.yesButton.hide()
        self.cancelButton.setText("取消")

        self.widget.setMinimumWidth(420)

        title = SubtitleLabel("删除重复任务")
        self.viewLayout.addWidget(title)

        hint = BodyLabel("这是一个重复任务，请选择删除范围：")
        hint.setWordWrap(True)
        self.viewLayout.addWidget(hint)

        self._btn_group = QButtonGroup(self)
        c = _colors()

        options = [
            ("this", FluentIcon.CALENDAR, "仅删除此次",
             "只删除当前这一项，后续重复任务不受影响",
             c["accent"]),
            ("this_and_future", FluentIcon.CALENDAR, "删除此次及之后",
             "删除当前和之后的所有重复实例",
             c["warning"]),
            ("all", FluentIcon.SYNC, "删除所有重复",
             "删除重复模板及全部实例，此操作不可撤销",
             c["danger"]),
        ]

        self._radios: list[RadioButton] = []
        self._cards: list[_OptionCard] = []

        for i, (mode, icon, opt_title, desc, color) in enumerate(options):
            row = QHBoxLayout()
            row.setSpacing(8)

            radio = RadioButton()
            if i == 0:
                radio.setChecked(True)
                self._result_mode = mode
            radio.setProperty("_mode", mode)
            self._btn_group.addButton(radio)
            self._radios.append(radio)

            card = _OptionCard(icon, opt_title, desc, color)
            self._cards.append(card)

            row.addWidget(radio)
            row.addWidget(card, 1)
            self.viewLayout.addLayout(row)

        self._btn_group.buttonClicked.connect(self._on_radio_clicked)

        if file_count > 0:
            self._file_checkbox = CheckBox(f"同时删除关联的 {file_count} 个文件")
            self._file_checkbox.setChecked(True)
            self.viewLayout.addWidget(self._file_checkbox)
        else:
            self._file_checkbox = None

        self._update_card_selection()

    def _on_radio_clicked(self, btn):
        self._result_mode = btn.property("_mode")
        self._update_card_selection()

    def _update_card_selection(self):
        for i, radio in enumerate(self._radios):
            self._cards[i].set_selected(radio.isChecked())

    @property
    def result_mode(self) -> str | None:
        return self._result_mode

    @property
    def delete_files(self) -> bool:
        if self._file_checkbox is None:
            return False
        return self._file_checkbox.isChecked()
