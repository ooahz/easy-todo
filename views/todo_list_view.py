"""待办列表视图 - 核心内容区域"""
from __future__ import annotations
from datetime import date as date_type
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel

from qfluentwidgets import (
    PrimaryPushButton, ToolButton, BodyLabel, CaptionLabel, FluentIcon,
    SmoothScrollArea, PipsPager, PipsScrollButtonDisplayMode, ComboBox, isDarkTheme
)
from views.todo_card import TodoCard
from views.subtask_card import SubtaskCard
from views.skeleton_widget import SkeletonCard, SkeletonSubtaskCard
from views.calendar_view import WeekView
from config.settings import settings


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


class TodoListView(QWidget):
    """待办列表视图"""

    add_clicked = Signal()
    edit_clicked = Signal(int)
    delete_clicked = Signal(int)
    toggle_done = Signal(int)
    float_clicked = Signal()
    calendar_clicked = Signal()
    reorder_requested = Signal(int, int, bool, list)
    add_subtask_clicked = Signal(int)
    card_clicked = Signal(int)
    archive_clicked = Signal(int)
    archive_all_clicked = Signal()
    filter_changed = Signal(str)
    page_changed = Signal(int, int)  # (page, page_size)

    def __init__(self, parent=None, view_name: str = "", readonly: bool = False):
        super().__init__(parent)
        self._todos: list[dict] = []
        self._all_todos: list[dict] = []
        self._cards: list = []
        self._skeleton_cards: list = []
        self._view_name = view_name
        self._readonly = readonly
        self._filter_date: date_type | None = None
        self._page_size = 100
        self._current_page = 0
        self._total_count = 0
        self._groups: list[dict] | None = None

        self._setup_ui()

    def _setup_ui(self):
        """构建 UI"""
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(20, 16, 20, 8)
        self.main_layout.setSpacing(12)

        # ---- 顶部工具栏 ----
        self.toolbar = QHBoxLayout()
        self.toolbar.setSpacing(8)

        # 过滤下拉框（仅已完成页面使用）
        self.filter_combo = ComboBox()
        self.filter_combo.addItems(["已完成", "已归档"])
        self.filter_combo.setCurrentIndex(0)
        self.filter_combo.setFixedWidth(100)
        self.filter_combo.currentIndexChanged.connect(
            lambda idx: self.filter_changed.emit("done" if idx == 0 else "archived")
        )
        self.filter_combo.setVisible(False)
        self.toolbar.addWidget(self.filter_combo)

        self.toolbar.addStretch()

        self.float_btn = ToolButton(FluentIcon.ZOOM)
        self.float_btn.setFixedSize(36, 36)
        self.float_btn.setToolTip("浮窗")
        self.float_btn.clicked.connect(self.float_clicked.emit)
        self.toolbar.addWidget(self.float_btn)

        self.archive_all_btn = ToolButton(FluentIcon.FOLDER)
        self.archive_all_btn.setFixedSize(36, 36)
        self.archive_all_btn.setToolTip("一键归档")
        self.archive_all_btn.clicked.connect(self.archive_all_clicked.emit)
        self.archive_all_btn.setVisible(False)
        self.toolbar.addWidget(self.archive_all_btn)

        self.calendar_btn = ToolButton(FluentIcon.CALENDAR)
        self.calendar_btn.setFixedSize(36, 36)
        self.calendar_btn.setToolTip("日程视图")
        self.calendar_btn.clicked.connect(self.calendar_clicked.emit)
        self.toolbar.addWidget(self.calendar_btn)

        # 新建按钮
        self.add_btn = PrimaryPushButton(FluentIcon.ADD, "新建任务")
        self.add_btn.clicked.connect(self.add_clicked.emit)
        self.toolbar.addWidget(self.add_btn)

        if self._readonly:
            self.add_btn.hide()

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

        # ---- 分页器 ----
        self.pager = PipsPager(Qt.Horizontal)
        self.pager.setNextButtonDisplayMode(PipsScrollButtonDisplayMode.ALWAYS)
        self.pager.setPreviousButtonDisplayMode(PipsScrollButtonDisplayMode.ALWAYS)
        self.pager.setVisible(False)
        self.pager.currentIndexChanged.connect(self._on_page_changed)
        self.main_layout.addWidget(self.pager, alignment=Qt.AlignCenter)

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
        
        # 设置 tooltip 样式
        self.setStyleSheet(_tooltip_style())

    def set_todos(self, todos: list[dict], recurring_instances: list[dict] = None,
                  total_count: int = -1):
        """设置待办列表数据（父任务列表，已包含 children）

        total_count: 数据库端总数，用于分页器。-1 表示使用客户端数据长度。
        """
        self._all_todos = todos
        self.week_view.set_todos(todos)

        if self._filter_date:
            self._todos = self._filter_todos_by_date(todos, self._filter_date)
            self._total_count = len(self._todos)
            self._groups = None
        else:
            self._todos = self._dedup_recurrence(todos)
            self._total_count = total_count if total_count >= 0 else len(self._todos)
            if self._view_name == "最近待办":
                self._groups = self._categorize_for_recent(self._todos)
            else:
                self._groups = None

        self._update_pager()
        self._refresh_list()

    def _on_filter_changed(self, filter_date: date_type | None):
        """处理周视图过滤变化"""
        self._filter_date = filter_date

        if filter_date:
            self._todos = self._filter_todos_by_date(self._all_todos, filter_date)
            self._total_count = len(self._todos)
            self._groups = None
        else:
            self._todos = self._dedup_recurrence(self._all_todos)
            self._total_count = len(self._todos)
            if self._view_name == "最近待办":
                self._groups = self._categorize_for_recent(self._todos)
            else:
                self._groups = None

        # 重置到第一页
        self._current_page = 0
        self._update_pager()
        self._refresh_list()

    def _update_pager(self):
        """更新分页器状态"""
        total = self._total_count
        total_pages = (total + self._page_size - 1) // self._page_size if total > 0 else 1
        
        if total_pages <= 1:
            self.pager.setVisible(False)
        else:
            self.pager.setVisible(True)
            # 先重置内部索引，避免 setPageNumber 检查时越界
            self.pager.setCurrentIndex(0)
            # 调整当前页
            if self._current_page >= total_pages:
                self._current_page = total_pages - 1
            self.pager.setPageNumber(total_pages)
            self.pager.setCurrentIndex(self._current_page)

    def _on_page_changed(self, index: int):
        """分页器页码变化，通知外部重新加载数据"""
        self._current_page = index
        self.page_changed.emit(index, self._page_size)

    @staticmethod
    def _dedup_recurrence(todos: list[dict]) -> list[dict]:
        """每个重复系列只保留离今天最近的未完成实例"""
        from datetime import date
        today = date.today()
        best: dict[int, dict] = {}

        for todo in todos:
            tmpl_id = todo.get("recurrence_template_id")
            if not tmpl_id or not todo.get("recurrence_type"):
                continue
            prev = best.get(tmpl_id)

            def _score(t):
                d_str = t.get("due_date")
                try:
                    d = date.fromisoformat(d_str) if d_str else date.min
                except (ValueError, TypeError):
                    d = date.min
                is_done = t.get("_is_done", False)
                if not is_done and d >= today:
                    return (0, abs((d - today).days))
                if not is_done:
                    return (1, abs((d - today).days))
                return (2, abs((d - today).days))

            if prev is None or _score(todo) < _score(prev):
                best[tmpl_id] = todo

        result = []
        seen = set()
        for todo in todos:
            tmpl_id = todo.get("recurrence_template_id")
            if not tmpl_id or not todo.get("recurrence_type"):
                result.append(todo)
                continue
            if tmpl_id in seen:
                continue
            seen.add(tmpl_id)
            result.append(best[tmpl_id])
        return result

    @staticmethod
    def _categorize_for_recent(todos: list[dict]) -> list[dict]:
        from datetime import date as _date
        today = _date.today()
        groups = [
            {"key": "overdue", "title": "超期未完成", "color": "#D13438", "todos": []},
            {"key": "today", "title": "今日任务", "color": "#0078D4", "todos": []},
            {"key": "upcoming", "title": "后续任务", "color": "#107C10", "todos": []},
            {"key": "completed", "title": "已完成", "color": "#8764B8", "todos": []},
        ]
        for todo in todos:
            is_done = todo.get("_is_done", False) or todo.get("status", 0) == 1
            if is_done:
                groups[3]["todos"].append(todo)
                continue
            due = todo.get("due_date")
            if due:
                try:
                    due_date = _date.fromisoformat(due)
                    if due_date < today:
                        groups[0]["todos"].append(todo)
                    elif due_date == today:
                        groups[1]["todos"].append(todo)
                    else:
                        groups[2]["todos"].append(todo)
                except (ValueError, TypeError):
                    groups[2]["todos"].append(todo)
            else:
                groups[2]["todos"].append(todo)
        return groups

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
        self._hide_skeleton()

        for card in self._cards:
            card.deleteLater()
        self._cards.clear()

        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if self._groups is not None:
            self._refresh_grouped_list()
            return

        # 数据已在数据库端分页，直接渲染当前页数据
        page_todos = self._todos

        self.stats_label.setVisible(True)

        has_todos = len(page_todos) > 0
        self.scroll_area.setVisible(has_todos)
        self.empty_widget.setVisible(not has_todos)

        # 构建父任务 ID 列表（用于拖拽排序）
        parent_ids = [t["id"] for t in page_todos]

        for todo_data in page_todos:
            # 父任务卡片
            card = TodoCard(todo_data, readonly=self._readonly)
            card.edit_clicked.connect(self.edit_clicked.emit)
            card.delete_clicked.connect(self.delete_clicked.emit)
            card.toggle_done.connect(self.toggle_done.emit)
            card.add_subtask_clicked.connect(self.add_subtask_clicked.emit)
            card.card_clicked.connect(self.card_clicked.emit)
            card.archive_clicked.connect(self.archive_clicked.emit)
            card.reorder_requested.connect(
                lambda from_id, to_id, after, order=parent_ids: self.reorder_requested.emit(from_id, to_id, after, order)
            )
            self.list_layout.addWidget(card)
            self._cards.append(card)

            # 子任务卡片（整体缩进）
            children = todo_data.get("children", [])
            for child_data in children:
                container = QWidget()
                container_layout = QHBoxLayout(container)
                container_layout.setContentsMargins(24, 0, 0, 0)
                container_layout.setSpacing(0)
                
                child_card = SubtaskCard(child_data, readonly=self._readonly)
                child_card.edit_clicked.connect(self.edit_clicked.emit)
                child_card.delete_clicked.connect(self.delete_clicked.emit)
                child_card.toggle_done.connect(self.toggle_done.emit)
                child_card.archive_clicked.connect(self.archive_clicked.emit)
                container_layout.addWidget(child_card)
                
                self.list_layout.addWidget(container)
                self._cards.append(child_card)

        self.list_layout.addStretch()

        parent_count = self._total_count
        child_count = sum(len(t.get("children", [])) for t in self._todos)
        total_count = parent_count + child_count
        
        if self._filter_date and self._view_name != "今日任务":
            self.stats_label.setText(f"筛选: {self._filter_date.month}月{self._filter_date.day}日 · 共{total_count}个任务")
        elif self._view_name == "今日任务":
            from datetime import date as _date
            if self._filter_date and self._filter_date != _date.today():
                self.stats_label.setText(f"筛选: {self._filter_date.month}月{self._filter_date.day}日 · 共{total_count}个任务")
            else:
                all_count = parent_count
                done_count = sum(1 for t in self._todos if t.get("_is_done", False))
                self.stats_label.setText(f"今日任务{all_count} · 已完成{done_count}")
        elif self._view_name == "全部任务":
            # 全部任务页面：只统计父任务（不统计子任务）
            from datetime import date
            all_count = parent_count
            done_count = sum(1 for t in self._todos if t.get("_is_done", False))
            overdue_count = 0
            today = date.today()
            for t in self._todos:
                if not t.get("_is_done", False) and not t.get("_is_archived", False):
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

    def _refresh_grouped_list(self):
        """刷新分组列表显示（最近待办视图）"""
        all_todos = []
        for group in self._groups:
            all_todos.extend(group["todos"])

        has_todos = len(all_todos) > 0
        self.scroll_area.setVisible(has_todos)
        self.empty_widget.setVisible(not has_todos)

        parent_ids = [t["id"] for t in all_todos]

        for group in self._groups:
            if not group["todos"]:
                continue

            header = QWidget()
            h_layout = QHBoxLayout(header)
            h_layout.setContentsMargins(0, 10, 0, 2)
            h_layout.setSpacing(6)

            dot = QLabel()
            dot.setFixedSize(8, 8)
            dot.setStyleSheet(f"background-color: {group['color']}; border-radius: 4px;")
            h_layout.addWidget(dot)

            title = BodyLabel(group["title"])
            title_color = "#EEE" if isDarkTheme() else "#333"
            title.setStyleSheet(f"font-weight: bold; font-size: 13px; color: {title_color};")
            h_layout.addWidget(title)

            count = CaptionLabel(str(len(group["todos"])))
            count_color = "#AAA" if isDarkTheme() else "#888"
            count.setStyleSheet(f"color: {count_color};")
            h_layout.addWidget(count)

            h_layout.addStretch()
            self.list_layout.addWidget(header)

            for todo_data in group["todos"]:
                card = TodoCard(todo_data, readonly=self._readonly)
                card.edit_clicked.connect(self.edit_clicked.emit)
                card.delete_clicked.connect(self.delete_clicked.emit)
                card.toggle_done.connect(self.toggle_done.emit)
                card.add_subtask_clicked.connect(self.add_subtask_clicked.emit)
                card.card_clicked.connect(self.card_clicked.emit)
                card.archive_clicked.connect(self.archive_clicked.emit)
                card.reorder_requested.connect(
                    lambda from_id, to_id, after, order=parent_ids: self.reorder_requested.emit(from_id, to_id, after, order)
                )
                self.list_layout.addWidget(card)
                self._cards.append(card)

                children = todo_data.get("children", [])
                for child_data in children:
                    container = QWidget()
                    container_layout = QHBoxLayout(container)
                    container_layout.setContentsMargins(24, 0, 0, 0)
                    container_layout.setSpacing(0)

                    child_card = SubtaskCard(child_data, readonly=self._readonly)
                    child_card.edit_clicked.connect(self.edit_clicked.emit)
                    child_card.delete_clicked.connect(self.delete_clicked.emit)
                    child_card.toggle_done.connect(self.toggle_done.emit)
                    child_card.archive_clicked.connect(self.archive_clicked.emit)
                    container_layout.addWidget(child_card)

                    self.list_layout.addWidget(container)
                    self._cards.append(child_card)

        self.list_layout.addStretch()

        self.stats_label.setVisible(False)

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

    def show_loading(self):
        """展示骨架加载态"""
        for card in self._cards:
            card.deleteLater()
        self._cards.clear()
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._show_skeleton()

    def _show_skeleton(self):
        """显示骨架占位"""
        self._hide_skeleton()
        self.empty_widget.setVisible(False)
        self.scroll_area.setVisible(True)

        for i in range(5):
            card = SkeletonCard()
            self.list_layout.addWidget(card)
            self._skeleton_cards.append(card)
            if i % 2 == 0:
                container = QWidget()
                container_layout = QHBoxLayout(container)
                container_layout.setContentsMargins(24, 0, 0, 0)
                container_layout.setSpacing(0)
                sub = SkeletonSubtaskCard()
                container_layout.addWidget(sub)
                self.list_layout.addWidget(container)
                self._skeleton_cards.append(sub)
        self.list_layout.addStretch()

    def _hide_skeleton(self):
        """移除骨架占位"""
        for card in self._skeleton_cards:
            card.stop()
            card.deleteLater()
        self._skeleton_cards.clear()

    def set_show_week_view(self, show: bool):
        """设置是否显示周日程视图"""
        self.week_view.setVisible(show)
        if not show:
            self.week_view.clear_selection()
