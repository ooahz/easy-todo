"""待办列表视图 - 核心内容区域"""
from __future__ import annotations
from datetime import date as date_type
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel

from qfluentwidgets import (
    PrimaryPushButton, ToolButton, BodyLabel, CaptionLabel, FluentIcon,
    SmoothScrollArea,
)
from views.todo_card import TodoCard
from views.subtask_card import SubtaskCard
from views.calendar_view import WeekView
from config.settings import settings


class TodoListView(QWidget):
    """待办列表视图"""

    add_clicked = Signal()
    edit_clicked = Signal(int)
    delete_clicked = Signal(int)
    toggle_done = Signal(int)
    float_clicked = Signal()
    calendar_clicked = Signal()  # 日程视图按钮点击
    reorder_requested = Signal(int, int, bool, list)  # from_id, to_id, insert_after, current_order
    add_subtask_clicked = Signal(int)  # parent_id

    def __init__(self, parent=None, view_name: str = ""):
        super().__init__(parent)
        self._todos: list[dict] = []
        self._all_todos: list[dict] = []
        self._cards: list = []
        self._view_name = view_name
        self._filter_date: date_type | None = None

        self._setup_ui()

    def _setup_ui(self):
        """构建 UI"""
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(20, 16, 20, 8)
        self.main_layout.setSpacing(12)

        # ---- 顶部工具栏 ----
        self.toolbar = QHBoxLayout()
        self.toolbar.setSpacing(8)

        self.toolbar.addStretch()

        # 日程视图按钮
        self.calendar_btn = ToolButton(FluentIcon.CALENDAR)
        self.calendar_btn.setFixedSize(36, 36)
        self.calendar_btn.setToolTip("日程视图")
        self.calendar_btn.clicked.connect(self.calendar_clicked.emit)
        self.toolbar.addWidget(self.calendar_btn)

        # 浮窗按钮
        self.float_btn = ToolButton(FluentIcon.ZOOM)
        self.float_btn.setFixedSize(36, 36)
        self.float_btn.setToolTip("浮窗")
        self.float_btn.clicked.connect(self.float_clicked.emit)
        self.toolbar.addWidget(self.float_btn)

        # 新建按钮
        self.add_btn = PrimaryPushButton(FluentIcon.ADD, "新建任务")
        self.add_btn.clicked.connect(self.add_clicked.emit)
        self.toolbar.addWidget(self.add_btn)

        self.main_layout.addLayout(self.toolbar)

        self.week_view = WeekView()
        self.week_view.filter_changed.connect(self._on_filter_changed)
        self.week_view.setVisible(settings.show_week_view)
        self.main_layout.addWidget(self.week_view)

        self.stats_label = CaptionLabel("")
        self.stats_label.setContentsMargins(0, 0, 0, 4)
        self.main_layout.addWidget(self.stats_label)

        # ---- 滚动区域 ----
        self.scroll_area = SmoothScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("""
            SmoothScrollArea {
                border: none;
                background: transparent;
            }
        """)

        self.scroll_widget = QWidget()
        self.scroll_widget.setStyleSheet("background: transparent;")
        self.list_layout = QVBoxLayout(self.scroll_widget)
        self.list_layout.setContentsMargins(0, 0, 8, 0)
        self.list_layout.setSpacing(6)
        self.list_layout.addStretch()

        self.scroll_area.setWidget(self.scroll_widget)
        self.main_layout.addWidget(self.scroll_area, 1)

        # ---- 空状态 ----
        self.empty_widget = QWidget()
        empty_layout = QVBoxLayout(self.empty_widget)
        empty_layout.setAlignment(Qt.AlignCenter)
        empty_layout.setSpacing(12)

        from qfluentwidgets import IconWidget
        self.empty_icon = IconWidget(FluentIcon.DOCUMENT)
        self.empty_icon.setFixedSize(56, 56)
        self.empty_icon.setStyleSheet("color: #D0D0D0;")
        empty_layout.addWidget(self.empty_icon, alignment=Qt.AlignCenter)

        self.empty_label = BodyLabel("暂无任务")
        self.empty_label.setStyleSheet("color: #AAA; font-size: 16px; font-weight: bold;")
        empty_layout.addWidget(self.empty_label, alignment=Qt.AlignCenter)

        self.empty_hint = CaptionLabel("点击上方「新建任务」按钮创建你的第一个待办")
        self.empty_hint.setStyleSheet("color: #BBB; font-size: 13px;")
        self.empty_hint.setAlignment(Qt.AlignCenter)
        empty_layout.addWidget(self.empty_hint, alignment=Qt.AlignCenter)

        self.empty_widget.setVisible(False)
        self.main_layout.addWidget(self.empty_widget)

    def set_todos(self, todos: list[dict]):
        """设置待办列表数据（父任务列表，已包含 children）"""
        self._all_todos = todos
        self.week_view.set_todos(todos)
        
        if self._filter_date:
            self._todos = self._filter_todos_by_date(todos, self._filter_date)
        else:
            self._todos = todos
        
        self._refresh_list()

    def _on_filter_changed(self, filter_date: date_type | None):
        """处理周视图过滤变化"""
        self._filter_date = filter_date
        
        if filter_date:
            self._todos = self._filter_todos_by_date(self._all_todos, filter_date)
        else:
            self._todos = self._all_todos
        
        self._refresh_list()

    def _filter_todos_by_date(self, todos: list[dict], target_date: date_type) -> list[dict]:
        """根据截止日期过滤任务"""
        filtered = []
        
        for todo in todos:
            filtered_children = []
            for child in todo.get("children", []):
                child_due = child.get("due_date")
                if child_due:
                    try:
                        child_date = date_type.fromisoformat(child_due)
                        if child_date == target_date:
                            filtered_children.append(child)
                    except (ValueError, TypeError):
                        pass
            
            due_date = todo.get("due_date")
            parent_match = False
            if due_date:
                try:
                    task_date = date_type.fromisoformat(due_date)
                    if task_date == target_date:
                        parent_match = True
                except (ValueError, TypeError):
                    pass
            
            if parent_match or filtered_children:
                filtered_todo = todo.copy()
                if not parent_match:
                    filtered_todo["children"] = filtered_children
                filtered.append(filtered_todo)
        
        return filtered

    def _refresh_list(self):
        """刷新列表显示 - 树形渲染：父任务 + 缩进子任务"""
        for card in self._cards:
            card.deleteLater()
        self._cards.clear()

        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        has_todos = len(self._todos) > 0
        self.scroll_area.setVisible(has_todos)
        self.empty_widget.setVisible(not has_todos)

        # 构建父任务 ID 列表（用于拖拽排序）
        parent_ids = [t["id"] for t in self._todos]

        for todo_data in self._todos:
            # 父任务卡片
            card = TodoCard(todo_data)
            card.edit_clicked.connect(self.edit_clicked.emit)
            card.delete_clicked.connect(self.delete_clicked.emit)
            card.toggle_done.connect(self.toggle_done.emit)
            card.add_subtask_clicked.connect(self.add_subtask_clicked.emit)
            card.reorder_requested.connect(
                lambda from_id, to_id, after, order=parent_ids: self.reorder_requested.emit(from_id, to_id, after, order)
            )
            self.list_layout.addWidget(card)
            self._cards.append(card)

            # 子任务卡片（整体缩进）
            children = todo_data.get("children", [])
            for child_data in children:
                # 创建容器实现整体缩进
                container = QWidget()
                container_layout = QHBoxLayout(container)
                container_layout.setContentsMargins(24, 0, 0, 0)  # 左侧缩进 24px
                container_layout.setSpacing(0)
                
                child_card = SubtaskCard(child_data)
                child_card.edit_clicked.connect(self.edit_clicked.emit)
                child_card.delete_clicked.connect(self.delete_clicked.emit)
                child_card.toggle_done.connect(self.toggle_done.emit)
                container_layout.addWidget(child_card)
                
                self.list_layout.addWidget(container)
                self._cards.append(child_card)  # 仍然记录卡片用于更新

        self.list_layout.addStretch()

        parent_count = len(self._todos)
        child_count = sum(len(t.get("children", [])) for t in self._todos)
        total_count = parent_count + child_count
        
        if self._filter_date:
            self.stats_label.setText(f"筛选: {self._filter_date.month}月{self._filter_date.day}日 · 共{total_count}个任务")
        elif self._view_name == "全部任务":
            # 全部任务页面：只统计父任务（不统计子任务）
            from datetime import date
            all_count = parent_count
            done_count = sum(1 for t in self._todos if t.get("status") == 1)
            overdue_count = 0
            today = date.today()
            for t in self._todos:
                if t.get("status") == 0:  # 只统计未完成的
                    due = t.get("due_date")
                    if due:
                        try:
                            if date.fromisoformat(due) < today:
                                overdue_count += 1
                        except:
                            pass
            self.stats_label.setText(f"全部任务{all_count} · 已完成{done_count} · 已超期{overdue_count}")
        else:
            self.stats_label.setText(f"共{total_count}个任务")

    def update_single_todo(self, todo_data: dict):
        """更新单个卡片（父任务或子任务）"""
        for card in self._cards:
            if card.todo_id == todo_data["id"]:
                card.update_data(todo_data)
                break

    def remove_todo(self, todo_id: int):
        """移除单个卡片"""
        for i, card in enumerate(self._cards):
            if card.todo_id == todo_id:
                self._cards.pop(i)
                card.deleteLater()
                self.list_layout.removeWidget(card)
                break

        parent_cards = [c for c in self._cards if not isinstance(c, SubtaskCard)]
        child_cards = [c for c in self._cards if isinstance(c, SubtaskCard)]
        total_count = len(parent_cards) + len(child_cards)
        self.stats_label.setText(f"共{total_count}个任务")

        if len(self._cards) == 0:
            self.scroll_area.setVisible(False)
            self.empty_widget.setVisible(True)

    def set_show_week_view(self, show: bool):
        """设置是否显示周日程视图"""
        self.week_view.setVisible(show)
        if not show:
            self.week_view.clear_selection()
