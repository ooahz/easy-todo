"""四象限浮窗组件 - 艾森豪威尔矩阵视图"""
from __future__ import annotations
from datetime import date

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPainter, QColor, QPen, QFont
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QSizePolicy

from qfluentwidgets import BodyLabel

from config.constants import (
    PRIORITY_IMPORTANT_URGENT,
    PRIORITY_IMPORTANT_NOT_URGENT,
    PRIORITY_NOT_IMPORTANT_URGENT,
    PRIORITY_NOT_IMPORTANT_NOT_URGENT,
    PRIORITY_MAP,
    PRIORITY_GROUP_COLORS,
)
from config.settings import settings
from config.theme_config import FontSize, theme_colors


class _ElidedLabel(QLabel):
    """自动省略超长文本的 QLabel"""

    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self._full_text = text
        self.setWordWrap(False)

    def setText(self, text: str):
        self._full_text = text
        self._update_elided()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_elided()

    def _update_elided(self):
        fm = self.fontMetrics()
        elided = fm.elidedText(self._full_text, Qt.TextElideMode.ElideRight, self.width())
        super().setText(elided)


class QuadrantCell(QFrame):
    """单个象限格子"""

    todo_toggled = Signal(int)

    def __init__(self, priority: int, parent=None):
        super().__init__(parent)
        self._priority = priority
        self._todos: list[dict] = []
        self._color = PRIORITY_GROUP_COLORS.get(priority, "#888")
        self._title = PRIORITY_MAP.get(priority, "")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(2)

        # 标题行：彩色圆点 + 名称 + 计数
        header = QHBoxLayout()
        header.setSpacing(4)
        dot = QLabel("●")
        dot.setStyleSheet(f"color: {self._color}; font-size: {FontSize.TINY}px; border: none; background: transparent;")
        header.addWidget(dot)

        title_label = QLabel(self._title)
        title_label.setStyleSheet(f"font-size: {FontSize.BODY}px; font-weight: bold; color: {self._color}; border: none; background: transparent;")
        header.addWidget(title_label)
        header.addStretch()

        self.count_label = BodyLabel("0")
        self.count_label.setStyleSheet(f"font-size: {FontSize.TINY}px; border: none; background: transparent;")
        header.addWidget(self.count_label)
        layout.addLayout(header)

        # 任务列表
        self.list_widget = QWidget(self)
        self.list_widget.setStyleSheet("background: transparent;")
        self.list_layout = QVBoxLayout(self.list_widget)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(1)
        self.list_layout.addStretch()
        layout.addWidget(self.list_widget, 1)

        self._apply_style()

    def _apply_style(self):
        c = self._theme_colors()
        bg = c["cell_bg"]
        border = c["cell_border"]
        self.setStyleSheet(f"""
            QuadrantCell {{
                background-color: {bg};
                border: 1px solid {border};
                border-radius: 6px;
                border-top: 2px solid {self._color};
            }}
        """)

    @staticmethod
    def _theme_colors():
        return theme_colors()

    def set_todos(self, todos: list[dict]):
        self._todos = todos
        total = len(todos)
        done = sum(1 for t in todos if t.get("_is_done", False))
        if done > 0:
            self.count_label.setText(f"{done}/{total}")
        else:
            self.count_label.setText(str(total))
        self._refresh()

    def _refresh(self):
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        c = theme_colors()
        for todo in self._todos:
            row = self._create_row(todo, c)
            self.list_layout.addWidget(row)
        self.list_layout.addStretch()

    def _create_row(self, todo: dict, c: dict) -> QWidget:
        is_done = todo.get("_is_done", False)
        title = todo.get("title", "")
        todo_id = todo["id"]
        due = todo.get("due_date")
        has_due = settings.floating_show_due_date and due and not is_done

        due_text = ""
        due_color = c['text']
        if has_due:
            try:
                due_date = date.fromisoformat(due)
                today = date.today()
                if due_date < today:
                    due_text = "已过期"
                    due_color = settings.warning_color
                elif due_date == today:
                    due_text = "今天"
                else:
                    due_text = due
            except (ValueError, TypeError):
                has_due = False

        row = QFrame()
        row.setFixedHeight(30)
        row.setCursor(Qt.PointingHandCursor)

        if is_done:
            text_style = f"color: {c['done_text']}; text-decoration: line-through;"
        else:
            text_style = f"color: {c.get('floating_font_color') or c['text']};"

        row.setStyleSheet(f"""
            QFrame {{
                border: none;
                border-radius: 3px;
                background: transparent;
            }}
            QFrame:hover {{
                background-color: {c['hover']};
            }}
        """)

        h = QHBoxLayout(row)
        h.setContentsMargins(4, 0, 4, 0)
        h.setSpacing(6)

        title_label = _ElidedLabel(title)
        title_label.setToolTip(title)
        title_label.setStyleSheet(
            f"font-size: {FontSize.SUBTITLE}px; {text_style} border: none; background: transparent;"
        )
        title_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        h.addWidget(title_label, 1)

        if has_due:
            due_label = QLabel(due_text)
            due_label.setToolTip(due)
            due_label.setAlignment(Qt.AlignVCenter | Qt.AlignRight)
            due_label.setStyleSheet(
                f"font-size: {FontSize.CAPTION}px; color: {due_color}; border: none; background: transparent;"
            )
            h.addWidget(due_label, 0)

        row.mousePressEvent = lambda e, tid=todo_id: self._on_clicked(e, tid)
        return row

    def _on_clicked(self, event, todo_id: int):
        if event.button() == Qt.LeftButton:
            self.todo_toggled.emit(todo_id)

    def refresh_theme(self):
        self._apply_style()
        self._refresh()


class QuadrantFloatingWidget(QWidget):
    """四象限浮窗 - 艾森豪威尔矩阵"""

    todo_toggled = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._todos: list[dict] = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # 2x2 网格
        grid = QVBoxLayout()
        grid.setSpacing(4)
        grid.setContentsMargins(0, 0, 0, 0)

        # 第一行：重要且紧急 | 重要不紧急
        row1 = QHBoxLayout()
        row1.setSpacing(4)
        self.cell_1 = QuadrantCell(PRIORITY_IMPORTANT_URGENT)
        self.cell_2 = QuadrantCell(PRIORITY_IMPORTANT_NOT_URGENT)
        row1.addWidget(self.cell_1, 1)
        row1.addWidget(self.cell_2, 1)
        grid.addLayout(row1, 1)

        # 第二行：不重要但紧急 | 不重要不紧急
        row2 = QHBoxLayout()
        row2.setSpacing(4)
        self.cell_3 = QuadrantCell(PRIORITY_NOT_IMPORTANT_URGENT)
        self.cell_4 = QuadrantCell(PRIORITY_NOT_IMPORTANT_NOT_URGENT)
        row2.addWidget(self.cell_3, 1)
        row2.addWidget(self.cell_4, 1)
        grid.addLayout(row2, 1)

        layout.addLayout(grid, 1)

        # 连接信号
        for cell in (self.cell_1, self.cell_2, self.cell_3, self.cell_4):
            cell.todo_toggled.connect(self.todo_toggled)

    def set_todos(self, todos: list[dict]):
        """按优先级分发任务到四个象限"""
        self._todos = todos
        buckets = {
            PRIORITY_IMPORTANT_URGENT: [],
            PRIORITY_IMPORTANT_NOT_URGENT: [],
            PRIORITY_NOT_IMPORTANT_URGENT: [],
            PRIORITY_NOT_IMPORTANT_NOT_URGENT: [],
        }
        for todo in todos:
            p = todo.get("priority", 0)
            if p in buckets:
                buckets[p].append(todo)
        self.cell_1.set_todos(buckets[PRIORITY_IMPORTANT_URGENT])
        self.cell_2.set_todos(buckets[PRIORITY_IMPORTANT_NOT_URGENT])
        self.cell_3.set_todos(buckets[PRIORITY_NOT_IMPORTANT_URGENT])
        self.cell_4.set_todos(buckets[PRIORITY_NOT_IMPORTANT_NOT_URGENT])

    def refresh_theme(self):
        for cell in (self.cell_1, self.cell_2, self.cell_3, self.cell_4):
            cell.refresh_theme()
