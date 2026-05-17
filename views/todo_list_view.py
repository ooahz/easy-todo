"""待办列表视图 - 核心内容区域"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel

from qfluentwidgets import (
    PrimaryPushButton, ToolButton, BodyLabel, CaptionLabel, FluentIcon,
    SmoothScrollArea,
)
from views.todo_card import TodoCard
from views.subtask_card import SubtaskCard


class TodoListView(QWidget):
    """待办列表视图"""

    add_clicked = Signal()
    edit_clicked = Signal(int)
    delete_clicked = Signal(int)
    toggle_done = Signal(int)
    float_clicked = Signal()
    reorder_requested = Signal(int, int, bool, list)  # from_id, to_id, insert_after, current_order
    add_subtask_clicked = Signal(int)  # parent_id

    def __init__(self, parent=None, view_name: str = "", total_count: int = 0):
        super().__init__(parent)
        self._todos: list[dict] = []  # 父任务列表
        self._cards: list = []  # 所有卡片（TodoCard 或 SubtaskCard）
        self._view_name = view_name
        self._total_count = total_count

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

        # ---- 列表统计 ----
        self.stats_label = CaptionLabel("")
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
        self._todos = todos
        self._refresh_list()

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
        # 统计当前页面所有任务（父任务+子任务）
        child_count = sum(len(t.get("children", [])) for t in self._todos)
        total_count = parent_count + child_count
        # 统计已完成数量（父任务+子任务）
        done_parent = sum(1 for t in self._todos if t.get("status") == 1)
        done_child = sum(
            1 for t in self._todos for c in t.get("children", []) if c.get("status") == 1
        )
        done_count = done_parent + done_child
        self.stats_label.setText(f"已完成{done_count}个任务，共{total_count}个任务")

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
        done_count = sum(1 for c in self._cards if c.todo_data.get("status") == 1)
        self.stats_label.setText(f"已完成{done_count}个任务，共{total_count}个任务")

        if len(self._cards) == 0:
            self.scroll_area.setVisible(False)
            self.empty_widget.setVisible(True)
