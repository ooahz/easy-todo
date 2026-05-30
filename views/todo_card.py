"""待办卡片组件 - 单个待办事项的卡片展示"""
from __future__ import annotations
from datetime import date

from PySide6.QtCore import Qt, Signal, QMimeData, QByteArray, QPoint
from PySide6.QtGui import QDrag, QPixmap, QPainter
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QFrame, QSizePolicy
)

from qfluentwidgets import (
    CheckBox, TransparentToolButton, BodyLabel, CaptionLabel,
    FluentIcon, CardWidget, isDarkTheme
)

from config.constants import PRIORITY_MAP
from config.settings import settings
from services.file_service import FileService


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


def _tooltip_style() -> str:
    """获取 tooltip 样式"""
    if isDarkTheme():
        return """
            QToolTip {
                background-color: #3C3C3C;
                color: #EEE;
                border: 1px solid #555;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 12px;
            }
        """
    return """
        QToolTip {
            background-color: #FFF;
            color: #333;
            border: 1px solid #DDD;
            border-radius: 6px;
            padding: 6px 10px;
            font-size: 12px;
        }
    """


class TodoCard(CardWidget):
    """待办事项卡片组件（仅用于父任务）"""

    card_clicked = Signal(int)
    edit_clicked = Signal(int)
    delete_clicked = Signal(int)
    toggle_done = Signal(int)
    reorder_requested = Signal(int, int, bool)  # from_id, to_id, insert_after
    add_subtask_clicked = Signal(int)  # parent_id
    archive_clicked = Signal(int)

    def __init__(self, todo_data: dict, readonly: bool = False, parent=None):
        super().__init__(parent)
        self.todo_data = todo_data
        self.todo_id = todo_data["id"]
        self._is_done = todo_data.get("_is_done", False)
        self._is_selected = False
        self._readonly = readonly
        self._file_service = FileService()

        # 动态计算高度
        self._base_height = 72
        self._has_files = self._file_service.get_file_count(self.todo_id) > 0
        self.setMinimumHeight(self._base_height + (20 if self._has_files else 0))
        self.setCursor(Qt.PointingHandCursor)

        self._setup_ui()
        self._apply_styles()

    def _setup_ui(self):
        """构建卡片 UI"""
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(12, 8, 8, 8)
        self.main_layout.setSpacing(0)

        # 主行：色条 + 复选框 + 内容 + 按钮
        self.top_row = QHBoxLayout()
        self.top_row.setSpacing(8)

        # 左侧色条
        self.priority_bar = QFrame()
        self.priority_bar.setFixedWidth(4)
        self.priority_bar.setMinimumHeight(40)
        self._update_bar_color()
        self.top_row.addWidget(self.priority_bar)

        # 复选框
        self.checkbox = CheckBox()
        self.checkbox.setFixedSize(20, 20)
        self.checkbox.setChecked(self._is_done)
        if self.todo_data.get("_is_archived", False):
            self.checkbox.setEnabled(False)
        self.checkbox.checkStateChanged.connect(lambda: self.toggle_done.emit(self.todo_id))
        self.top_row.addWidget(self.checkbox)

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

        category = self.todo_data.get("category")
        if category:
            info_parts.append(category.get("name", ""))

        if due:
            due_date = date.fromisoformat(due)
            today = date.today()
            if due_date < today:
                info_parts.append(f'<span style="color:{settings.warning_color}">已过期 ({due})</span>')
            elif due_date == today:
                info_parts.append("今天")
            else:
                info_parts.append(f"{due}")

        recurrence = self.todo_data.get("recurrence_type")
        if recurrence:
            from config.constants import RECURRENCE_TYPES
            interval = self.todo_data.get("recurrence_interval", 1)
            recurrence_day = self.todo_data.get("recurrence_day")
            type_name = RECURRENCE_TYPES.get(recurrence, "")
            if recurrence == "weekly" and recurrence_day:
                weekday_names = {1: "一", 2: "二", 3: "三", 4: "四", 5: "五", 6: "六", 7: "日"}
                day_name = weekday_names.get(recurrence_day, "")
                if interval > 1:
                    info_parts.append(f"每{interval}周周{day_name}")
                else:
                    info_parts.append(f"每周{day_name}")
            elif recurrence == "monthly" and recurrence_day:
                if interval > 1:
                    info_parts.append(f"每{interval}月{recurrence_day}号")
                else:
                    info_parts.append(f"每月{recurrence_day}号")
            elif interval > 1:
                unit = {"daily": "天", "weekly": "周", "monthly": "月"}.get(recurrence, "")
                info_parts.append(f"每{interval}{unit}")
            else:
                info_parts.append(type_name)

        file_count = self._file_service.get_file_count(self.todo_id)
        if file_count > 0:
            info_parts.append(f"📎 {file_count}")

        if info_parts:
            self.info_label = CaptionLabel("  |  ".join(info_parts))
            self.info_label.setObjectName("infoLabel")
            self._apply_info_style()
            self.content_layout.addWidget(self.info_label)

        self.top_row.addLayout(self.content_layout, 1)

        # 操作按钮
        self.action_layout = QHBoxLayout()
        self.action_layout.setSpacing(2)
        self.action_layout.setContentsMargins(0, 0, 4, 0)

        action_widget = QWidget()
        action_widget.setLayout(self.action_layout)
        action_widget.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred
        )

        # 新建子任务按钮
        self.add_subtask_btn = TransparentToolButton(FluentIcon.ADD_TO)
        self.add_subtask_btn.setFixedSize(30, 30)
        self.add_subtask_btn.setToolTip("添加子任务")
        self.add_subtask_btn.clicked.connect(lambda: self.add_subtask_clicked.emit(self.todo_id))
        self.action_layout.addWidget(self.add_subtask_btn)

        self.edit_btn = TransparentToolButton(FluentIcon.EDIT)
        self.edit_btn.setFixedSize(30, 30)
        self.edit_btn.setToolTip("编辑")
        self.edit_btn.clicked.connect(lambda: self.edit_clicked.emit(self.todo_id))
        self.action_layout.addWidget(self.edit_btn)

        self.archive_btn = TransparentToolButton(FluentIcon.FOLDER)
        self.archive_btn.setFixedSize(30, 30)
        self.archive_btn.setToolTip("归档")
        self.archive_btn.clicked.connect(lambda: self.archive_clicked.emit(self.todo_id))
        self.action_layout.addWidget(self.archive_btn)

        self.delete_btn = TransparentToolButton(FluentIcon.DELETE)
        self.delete_btn.setFixedSize(30, 30)
        self.delete_btn.setToolTip("删除")
        self.delete_btn.clicked.connect(lambda: self.delete_clicked.emit(self.todo_id))
        self.action_layout.addWidget(self.delete_btn)

        if self._readonly:
            self.add_subtask_btn.hide()
            self.edit_btn.hide()
            self.archive_btn.setVisible(self._is_done)
        else:
            self.archive_btn.hide()

        self.top_row.addWidget(action_widget)
        self.main_layout.addLayout(self.top_row)

        # 启用拖拽
        self.setAcceptDrops(True)
        self._drag_start_pos = None
        self._is_dragging = False

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_start_pos = event.pos()
            self._is_dragging = False
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not self._drag_start_pos:
            return

        if not self._is_dragging and (event.pos() - self._drag_start_pos).manhattanLength() > 10:
            self._is_dragging = True
            self._start_drag()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            if not self._is_dragging and self._drag_start_pos:
                self.card_clicked.emit(self.todo_id)
            self._drag_start_pos = None
            self._is_dragging = False
        super().mouseReleaseEvent(event)

    def _start_drag(self):
        """开始拖拽"""
        drag = QDrag(self)
        mime_data = QMimeData()
        mime_data.setData("application/x-todo-id", QByteArray(str(self.todo_id).encode()))
        drag.setMimeData(mime_data)

        pixmap = self.grab()
        alpha_pixmap = QPixmap(pixmap.size())
        alpha_pixmap.fill(Qt.transparent)
        painter = QPainter(alpha_pixmap)
        painter.setOpacity(0.7)
        painter.drawPixmap(0, 0, pixmap)
        painter.end()
        drag.setPixmap(alpha_pixmap)
        drag.setHotSpot(self._drag_start_pos)

        drag.exec(Qt.MoveAction)

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat("application/x-todo-id"):
            source_id = int(bytes(event.mimeData().data("application/x-todo-id")).decode())
            if source_id != self.todo_id:
                event.acceptProposedAction()
                self.setStyleSheet("""
                    CardWidget {
                        border: 2px dashed #0078D4;
                        border-radius: 8px;
                        background-color: rgba(0, 120, 212, 0.1);
                    }
                """)

    def dragLeaveEvent(self, event):
        self._apply_styles()

    def dropEvent(self, event):
        self._apply_styles()
        if event.mimeData().hasFormat("application/x-todo-id"):
            source_id = int(bytes(event.mimeData().data("application/x-todo-id")).decode())
            if source_id != self.todo_id:
                pos = event.position().y() if hasattr(event, 'position') else event.pos().y()
                height = self.height()
                insert_after = pos > height / 2
                self.reorder_requested.emit(source_id, self.todo_id, insert_after)
            event.acceptProposedAction()

    def _update_bar_color(self):
        """更新左侧色条颜色"""
        color_tag = self.todo_data.get("color_tag")
        color = color_tag if color_tag else "transparent"
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
        tooltip_style = _tooltip_style()
        self.setStyleSheet(f"""
            CardWidget {{
                border: none;
                border-radius: 8px;
                background-color: transparent;
            }}
            CardWidget:hover {{
                background-color: {c['hover_bg']};
            }}
            {tooltip_style}
        """)

    def update_data(self, todo_data: dict):
        """更新卡片数据"""
        self.todo_data = todo_data
        self._is_done = todo_data.get("_is_done", False)
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
