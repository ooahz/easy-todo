"""子任务卡片组件 - 子任务的卡片展示"""
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QSizePolicy

from qfluentwidgets import (
    CheckBox, TransparentToolButton, BodyLabel, CaptionLabel,
    FluentIcon, CardWidget,
)

from config.theme_config import (
    FontSize, palette, theme_colors, tooltip_style, accent_color,
)


class SubtaskCard(CardWidget):
    """子任务卡片组件"""

    edit_clicked = Signal(int)
    delete_clicked = Signal(int)
    toggle_done = Signal(int)
    archive_clicked = Signal(int)

    def __init__(self, todo_data: dict, readonly: bool = False, parent=None):
        super().__init__(parent)
        self.todo_data = todo_data
        self.todo_id = todo_data["id"]
        self._is_done = todo_data.get("_is_done", False)
        self._is_selected = False
        self._readonly = readonly

        self.setMinimumHeight(52)
        self.setCursor(Qt.PointingHandCursor)

        self._setup_ui()
        self._apply_styles()

    def _setup_ui(self):
        """构建子任务卡片 UI"""
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(12, 6, 8, 6)  # 正常边距，缩进由外部容器处理
        self.main_layout.setSpacing(0)

        # 主行：无色条 + 复选框 + 标题 + 按钮
        self.row = QHBoxLayout()
        self.row.setSpacing(8)

        # 复选框
        self.checkbox = CheckBox()
        self.checkbox.setFixedSize(18, 18)
        self.checkbox.setChecked(self._is_done)
        if self.todo_data.get("_is_archived", False):
            self.checkbox.setEnabled(False)
        self.checkbox.checkStateChanged.connect(lambda: self.toggle_done.emit(self.todo_id))
        self.row.addWidget(self.checkbox)

        # 标题
        self.title_label = BodyLabel(self.todo_data["title"])
        self.title_label.setWordWrap(True)
        self.title_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self._apply_title_style()
        self.row.addWidget(self.title_label, 1)

        # 操作按钮
        self.edit_btn = TransparentToolButton(FluentIcon.EDIT)
        self.edit_btn.setFixedSize(26, 26)
        self.edit_btn.setIconSize(QSize(14, 14))
        self.edit_btn.setToolTip("编辑")
        self.edit_btn.clicked.connect(lambda: self.edit_clicked.emit(self.todo_id))
        self.row.addWidget(self.edit_btn)

        self.archive_btn = TransparentToolButton(FluentIcon.FOLDER)
        self.archive_btn.setFixedSize(26, 26)
        self.archive_btn.setIconSize(QSize(14, 14))
        self.archive_btn.setToolTip("归档")
        self.archive_btn.clicked.connect(lambda: self.archive_clicked.emit(self.todo_id))
        self.row.addWidget(self.archive_btn)

        self.delete_btn = TransparentToolButton(FluentIcon.DELETE)
        self.delete_btn.setFixedSize(26, 26)
        self.delete_btn.setIconSize(QSize(14, 14))
        self.delete_btn.setToolTip("删除")
        self.delete_btn.clicked.connect(lambda: self.delete_clicked.emit(self.todo_id))
        self.row.addWidget(self.delete_btn)

        if self._readonly:
            self.edit_btn.hide()
            self.archive_btn.setVisible(self._is_done)
        else:
            self.archive_btn.hide()

        self.main_layout.addLayout(self.row)

    def _apply_title_style(self):
        c = theme_colors()
        if self._is_done:
            self.title_label.setStyleSheet(f"""
                BodyLabel {{
                    text-decoration: line-through;
                    color: {c['done']};
                    font-size: 13px;
                }}
            """)
        else:
            self.title_label.setStyleSheet(f"""
                BodyLabel {{
                    color: {c['title']};
                    font-size: 13px;
                }}
            """)

    def _apply_styles(self):
        c = theme_colors()
        tip_style = tooltip_style()
        self.setStyleSheet(f"""
            CardWidget {{
                border: none;
                border-radius: 6px;
                background-color: transparent;
            }}
            CardWidget:hover {{
                background-color: {c['hover_bg']};
            }}
            {tip_style}
        """)

    def update_data(self, todo_data: dict):
        """更新卡片数据"""
        self.todo_data = todo_data
        self.todo_id = todo_data["id"]
        self._is_done = todo_data.get("_is_done", False)
        self.checkbox.blockSignals(True)
        self.checkbox.setChecked(self._is_done)
        self.checkbox.blockSignals(False)
        self.checkbox.setEnabled(not todo_data.get("_is_archived", False))
        self.title_label.setText(todo_data["title"])
        self._apply_title_style()
        if self._readonly:
            self.archive_btn.setVisible(self._is_done)
        else:
            self.archive_btn.hide()

    def set_selected(self, selected: bool):
        self._is_selected = selected
        if selected:
            accent = accent_color()
            self.setStyleSheet(f"""
                CardWidget {{
                    border: 1px solid {accent};
                    border-radius: 6px;
                    background-color: {palette().HOVER_BG_SOFT};
                }}
            """)
        else:
            self._apply_styles()
