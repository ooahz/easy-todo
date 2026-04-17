"""新建/编辑待办对话框"""
from datetime import date, datetime

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
)

from qfluentwidgets import (
    LineEdit, TextEdit, ComboBox, CalendarPicker,
    PrimaryPushButton, PushButton, SubtitleLabel, CheckBox,
    FluentIcon, isDarkTheme, setCustomStyleSheet
)

from config.constants import PRIORITY_MAP, TODO_COLORS


class TodoDialog(QDialog):
    """新建/编辑待办对话框"""

    todo_saved = Signal(dict)

    def __init__(self, todo_data: dict = None, parent=None):
        super().__init__(parent)
        self.todo_data = todo_data
        self._is_edit = todo_data is not None
        self._selected_color = None

        self.setWindowTitle("编辑任务" if self._is_edit else "新建任务")
        self.setFixedSize(480, 460)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        self._setup_ui()
        self._connect_signals()

        if self._is_edit:
            self._fill_data(todo_data)

    def _setup_ui(self):
        """构建对话框 UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 20)
        layout.setSpacing(12)

        # 标题
        title = SubtitleLabel("编辑任务" if self._is_edit else "新建任务")
        layout.addWidget(title)

        # 分隔线
        sep = QLabel()
        sep.setFixedHeight(1)
        sep.setObjectName("dialogSep")
        setCustomStyleSheet(
            sep,
            "#dialogSep { background-color: rgba(0,0,0,0.08); }",
            "#dialogSep { background-color: rgba(255,255,255,0.06); }"
        )
        layout.addWidget(sep)

        # 标题输入
        self.title_edit = LineEdit()
        self.title_edit.setPlaceholderText("输入任务标题...")
        self.title_edit.setClearButtonEnabled(True)
        layout.addWidget(self.title_edit)

        # 描述输入
        self.desc_edit = TextEdit()
        self.desc_edit.setPlaceholderText("添加详细描述（可选）...")
        self.desc_edit.setFixedHeight(60)
        layout.addWidget(self.desc_edit)

        # 优先级 + 截止日期
        row1 = QHBoxLayout()
        row1.setSpacing(20)

        self.priority_combo = ComboBox()
        self.priority_combo.setFixedWidth(210)
        self.priority_combo.addItem("选择优先级", userData=None)
        for val, name in PRIORITY_MAP.items():
            self.priority_combo.addItem(name, userData=val)
        self.priority_combo.setCurrentIndex(0)
        row1.addWidget(self.priority_combo)

        self.due_picker = CalendarPicker()
        self.due_picker.setFixedWidth(210)
        try:
            self.due_picker.setText("截止日期")
        except Exception:
            pass
        row1.addWidget(self.due_picker)

        row1.addStretch()
        layout.addLayout(row1)

        # 自动延期（独立一行）
        self.auto_postpone_cb = CheckBox("自动延期")
        self.auto_postpone_cb.setToolTip("开启后，过期未完成的任务会自动延期到当天")
        layout.addWidget(self.auto_postpone_cb)

        # 颜色标签
        color_row = QHBoxLayout()
        color_row.setSpacing(8)

        self.color_buttons = []
        dark = isDarkTheme()
        for name, color in TODO_COLORS:
            btn = QPushButton()
            btn.setFixedSize(24, 24)
            btn.setCheckable(True)
            checked_border = "border: 2px solid #AAA;" if dark else "border: 2px solid #333;"
            hover_border = "border: 2px solid #888;" if dark else "border: 2px solid #666;"
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {color};
                    border-radius: 12px;
                    border: 2px solid transparent;
                }}
                QPushButton:checked {{
                    {checked_border}
                }}
                QPushButton:hover {{
                    {hover_border}
                }}
            """)
            btn.setToolTip(name)
            btn.setProperty("color_value", color)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked, c=color, b=btn: self._on_color_clicked(c, b))
            color_row.addWidget(btn)
            self.color_buttons.append(btn)

        color_row.addStretch()
        layout.addLayout(color_row)

        layout.addStretch()

        # 按钮区
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        btn_layout.addStretch()

        self.cancel_btn = PushButton("取消")
        self.cancel_btn.setFixedWidth(100)
        self.cancel_btn.clicked.connect(self.close)

        self.save_btn = PrimaryPushButton("保存")
        self.save_btn.setFixedWidth(100)
        self.save_btn.setIcon(FluentIcon.SAVE)
        self.save_btn.clicked.connect(self._on_save)

        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addWidget(self.save_btn)
        layout.addLayout(btn_layout)

    def _connect_signals(self):
        self.title_edit.returnPressed.connect(self._on_save)

    def _on_color_clicked(self, color: str, btn: QPushButton):
        if self._selected_color == color:
            btn.setChecked(False)
            self._selected_color = None
        else:
            for b in self.color_buttons:
                b.setChecked(False)
            btn.setChecked(True)
            self._selected_color = color

    def _fill_data(self, data: dict):
        self.title_edit.setText(data.get("title", ""))
        self.desc_edit.setPlainText(data.get("description", ""))

        priority = data.get("priority", 0)
        for i in range(self.priority_combo.count()):
            if self.priority_combo.itemData(i) == priority:
                self.priority_combo.setCurrentIndex(i)
                break

        color_tag = data.get("color_tag")
        if color_tag:
            self._selected_color = color_tag
            for btn in self.color_buttons:
                if btn.property("color_value") == color_tag:
                    btn.setChecked(True)
                    break

        # 自动延期
        self.auto_postpone_cb.setChecked(data.get("auto_postpone", False))

        due_str = data.get("due_date")
        if due_str:
            try:
                from PySide6.QtCore import QDate
                if isinstance(due_str, str):
                    pyd = date.fromisoformat(due_str)
                    self.due_picker.setDate(QDate(pyd.year, pyd.month, pyd.day))
                else:
                    self.due_picker.setDate(QDate(due_str.year, due_str.month, due_str.day))
            except Exception:
                pass

    def _on_save(self):
        title = self.title_edit.text().strip()
        if not title:
            self.title_edit.setStyleSheet(
                "LineEdit { border: 2px solid #D13438; border-radius: 6px; }"
            )
            return

        due_date = None
        try:
            qdate = self.due_picker.date
            if qdate is not None and hasattr(qdate, 'isValid') and qdate.isValid():
                due_date = date(qdate.year(), qdate.month(), qdate.day())
        except Exception:
            pass

        priority_val = self.priority_combo.currentData()
        priority = priority_val if priority_val is not None else 0

        data = {
            "title": title,
            "description": self.desc_edit.toPlainText().strip(),
            "priority": priority,
            "color_tag": self._selected_color,
            "due_date": due_date,
            "auto_postpone": self.auto_postpone_cb.isChecked(),
        }

        if self._is_edit:
            data["id"] = self.todo_data["id"]

        self.todo_saved.emit(data)
        self.close()

    def showEvent(self, event):
        super().showEvent(event)
        self.title_edit.setFocus()
        self.title_edit.setStyleSheet("")
        # 对话框背景跟随主题
        if isDarkTheme():
            self.setStyleSheet(
                "QDialog { background-color: rgb(43, 43, 43); }"
                "SubtitleLabel { color: #EEE; }"
                "BodyLabel { color: #DDD; }"
                "CaptionLabel { color: #AAA; }"
                "QLabel { color: #DDD; }"
                "LineEdit { background-color: rgb(59, 59, 59); color: #EEE; border: 1px solid rgb(80,80,80); border-radius: 6px; }"
                "TextEdit { background-color: rgb(59, 59, 59); color: #EEE; border: 1px solid rgb(80,80,80); border-radius: 6px; }"
                "CheckBox { color: #DDD; }"
            )
        else:
            self.setStyleSheet(
                "QDialog { background-color: rgb(249, 249, 249); }"
                "SubtitleLabel { color: #111; }"
                "BodyLabel { color: #333; }"
                "CaptionLabel { color: #666; }"
                "QLabel { color: #333; }"
                "LineEdit { background-color: #FFF; color: #333; }"
                "TextEdit { background-color: #FFF; color: #333; }"
                "CheckBox { color: #333; }"
            )
