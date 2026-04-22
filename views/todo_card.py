"""待办卡片组件 - 单个待办事项的卡片展示"""
from datetime import date

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QFrame, QSizePolicy
)

from qfluentwidgets import (
    CheckBox, TransparentToolButton, BodyLabel, CaptionLabel,
    FluentIcon, CardWidget, isDarkTheme
)

from config.constants import PRIORITY_MAP


def _tc():
    """根据主题返回颜色字典"""
    if isDarkTheme():
        return {
            "hover_border": "rgba(255, 255, 255, 0.08)",
            "hover_bg": "rgba(255, 255, 255, 0.04)",
            "title": "#EEE",
            "muted": "#888",
            "done": "#666",
            "info": "#999",
        }
    return {
        "hover_border": "rgba(0, 0, 0, 0.06)",
        "hover_bg": "rgba(0, 0, 0, 0.02)",
        "title": "#222",
        "muted": "#999",
        "done": "gray",
        "info": "#888",
    }


class TodoCard(CardWidget):
    """待办事项卡片组件"""

    card_clicked = Signal(int)
    edit_clicked = Signal(int)
    delete_clicked = Signal(int)
    toggle_done = Signal(int)

    def __init__(self, todo_data: dict, parent=None):
        super().__init__(parent)
        self.todo_data = todo_data
        self.todo_id = todo_data["id"]
        self._is_done = todo_data["status"] == 1
        self._is_selected = False

        self.setFixedHeight(72)
        self.setCursor(Qt.PointingHandCursor)

        self._setup_ui()
        self._apply_styles()

    def _setup_ui(self):
        """构建卡片 UI"""
        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(12, 8, 8, 8)
        self.main_layout.setSpacing(8)

        # 左侧色条
        self.priority_bar = QFrame()
        self.priority_bar.setFixedWidth(4)
        self.priority_bar.setMinimumHeight(40)
        self._update_bar_color()
        self.main_layout.addWidget(self.priority_bar)

        # 复选框
        self.checkbox = CheckBox()
        self.checkbox.setFixedSize(20, 20)
        self.checkbox.setChecked(self._is_done)
        self.checkbox.checkStateChanged.connect(lambda: self.toggle_done.emit(self.todo_id))
        self.main_layout.addWidget(self.checkbox)

        # 中间内容区
        self.content_layout = QVBoxLayout()
        self.content_layout.setSpacing(2)
        self.content_layout.setContentsMargins(4, 0, 4, 0)

        # 标题
        self.title_row = QHBoxLayout()
        self.title_row.setSpacing(8)

        self.title_label = BodyLabel(self.todo_data["title"])
        self.title_label.setWordWrap(True)
        self.title_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self._apply_title_style()
        self.title_row.addWidget(self.title_label, 1)

        self.content_layout.addLayout(self.title_row)

        # 描述行
        desc = self.todo_data.get("description", "")
        due = self.todo_data.get("due_date", "")

        # 描述
        if desc:
            self.desc_label = CaptionLabel(desc)
            self.desc_label.setObjectName("descLabel")
            self.desc_label.setWordWrap(True)
            self.desc_label.setMaximumHeight(36)
            self._apply_desc_style()
            self.content_layout.addWidget(self.desc_label)

        # 信息行
        info_parts = []
        priority = self.todo_data.get("priority", 0)
        if priority in PRIORITY_MAP and priority > 0:
            info_parts.append(PRIORITY_MAP[priority])
        if due:
            due_date = date.fromisoformat(due)
            today = date.today()
            if due_date < today:
                info_parts.append(f"已过期 ({due})")
            elif due_date == today:
                info_parts.append("今天")
            else:
                info_parts.append(f"{due}")

        if info_parts:
            self.info_label = CaptionLabel("  |  ".join(info_parts))
            self.info_label.setObjectName("infoLabel")
            self._apply_info_style()
            self.content_layout.addWidget(self.info_label)

        self.main_layout.addLayout(self.content_layout, 1)

        # 操作按钮
        self.action_layout = QHBoxLayout()
        self.action_layout.setSpacing(2)
        self.action_layout.setContentsMargins(0, 0, 4, 0)

        action_widget = QWidget()
        action_widget.setLayout(self.action_layout)
        action_widget.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred
        )

        self.edit_btn = TransparentToolButton(FluentIcon.EDIT)
        self.edit_btn.setFixedSize(30, 30)
        self.edit_btn.setToolTip("编辑")
        self.edit_btn.clicked.connect(lambda: self.edit_clicked.emit(self.todo_id))
        self.action_layout.addWidget(self.edit_btn)

        self.delete_btn = TransparentToolButton(FluentIcon.DELETE)
        self.delete_btn.setFixedSize(30, 30)
        self.delete_btn.setToolTip("删除")
        self.delete_btn.clicked.connect(lambda: self.delete_clicked.emit(self.todo_id))
        self.action_layout.addWidget(self.delete_btn)

        self.main_layout.addWidget(action_widget)

        self.mousePressEvent = self._on_mouse_press

    def _on_mouse_press(self, event):
        if event.button() == Qt.LeftButton:
            self.card_clicked.emit(self.todo_id)

    def _update_bar_color(self):
        """更新左侧色条颜色"""
        color_tag = self.todo_data.get("color_tag")
        if color_tag:
            color = color_tag
        else:
            priority = self.todo_data.get("priority", 0)
            colors = {0: "transparent", 1: "#0078D4", 2: "#FF8C00", 3: "#D13438"}
            color = colors.get(priority, "transparent")
        self.priority_bar.setStyleSheet(f"""
            QFrame {{
                background-color: {color};
                border-radius: 2px;
            }}
        """)

    def _apply_title_style(self):
        c = _tc()
        if self._is_done:
            self.title_label.setStyleSheet(f"""
                BodyLabel {{
                    text-decoration: line-through;
                    color: {c['done']};
                    font-size: 14px;
                }}
            """)
        else:
            self.title_label.setStyleSheet(f"""
                BodyLabel {{
                    color: {c['title']};
                    font-size: 14px;
                }}
            """)

    def _apply_info_style(self):
        c = _tc()
        if self._is_done:
            self.info_label.setStyleSheet(f"""
                CaptionLabel#infoLabel {{
                    color: {c['done']};
                    font-size: 12px;
                }}
            """)
        else:
            self.info_label.setStyleSheet(f"""
                CaptionLabel#infoLabel {{
                    color: {c['info']};
                    font-size: 12px;
                }}
            """)

    def _apply_desc_style(self):
        c = _tc()
        if self._is_done:
            self.desc_label.setStyleSheet(f"""
                CaptionLabel#descLabel {{
                    color: {c['done']};
                    font-size: 12px;
                }}
            """)
        else:
            self.desc_label.setStyleSheet(f"""
                CaptionLabel#descLabel {{
                    color: {c['muted']};
                    font-size: 12px;
                }}
            """)

    def _apply_styles(self):
        c = _tc()
        self.setStyleSheet(f"""
            CardWidget {{
                border: none;
                border-radius: 8px;
                background-color: transparent;
            }}
            CardWidget:hover {{
                background-color: {c['hover_bg']};
            }}
        """)

    def update_data(self, todo_data: dict):
        """更新卡片数据"""
        self.todo_data = todo_data
        self._is_done = todo_data["status"] == 1
        self.checkbox.blockSignals(True)
        self.checkbox.setChecked(self._is_done)
        self.checkbox.blockSignals(False)
        self.title_label.setText(todo_data["title"])
        self._apply_title_style()
        self._update_bar_color()
        desc = todo_data.get("description", "")
        if hasattr(self, "desc_label") and desc:
            self.desc_label.setText(desc)
            self._apply_desc_style()

    def set_selected(self, selected: bool):
        self._is_selected = selected
        if selected:
            self.setStyleSheet("""
                CardWidget {
                    border: 2px solid #0078D4;
                    border-radius: 8px;
                    background-color: rgba(0, 120, 212, 0.05);
                }
            """)
        else:
            self._apply_styles()
