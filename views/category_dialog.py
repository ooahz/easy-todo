"""分类管理对话框"""
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QPainter, QColor, QPainterPath
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QWidget, QListWidgetItem, QLabel
)

from qfluentwidgets import (
    LineEdit, PushButton, PrimaryPushButton, ListWidget,
    TransparentToolButton, FluentIcon, isDarkTheme, SubtitleLabel, MessageBox,
    BodyLabel, CaptionLabel
)

from services.category_service import CategoryService, category_event_bus

SYSTEM_VIEWS = [
    ("recent", "最近待办", FluentIcon.QUICK_NOTE),
    ("today", "今日任务", FluentIcon.CALENDAR),
    ("important", "重要任务", FluentIcon.CALORIES),
    ("all", "全部任务", FluentIcon.APPLICATION),
    ("done", "已完成", FluentIcon.COMPLETED),
]

SYSTEM_VIEW_MAP = {key: (name, icon) for key, name, icon in SYSTEM_VIEWS}


class SystemViewItem(QWidget):
    """系统视图项"""

    move_up_clicked = Signal(str)
    move_down_clicked = Signal(str)

    def __init__(self, view_key: str, name: str, icon: FluentIcon, parent=None):
        super().__init__(parent)
        self._view_key = view_key
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)

        self.icon_w = QWidget()
        self.icon_w.setFixedSize(12, 12)
        self._update_icon_color()
        layout.addWidget(self.icon_w)

        name_label = BodyLabel(name)
        layout.addWidget(name_label, 1)

        sys_tag = CaptionLabel("系统")
        self._update_sys_tag_style(sys_tag)
        layout.addWidget(sys_tag)

        self.up_btn = TransparentToolButton(FluentIcon.UP)
        self.up_btn.setFixedSize(28, 28)
        self.up_btn.setIconSize(QSize(12, 12))
        self.up_btn.setToolTip("上移")
        self.up_btn.clicked.connect(lambda: self.move_up_clicked.emit(self._view_key))
        layout.addWidget(self.up_btn)

        self.down_btn = TransparentToolButton(FluentIcon.DOWN)
        self.down_btn.setFixedSize(28, 28)
        self.down_btn.setIconSize(QSize(12, 12))
        self.down_btn.setToolTip("下移")
        self.down_btn.clicked.connect(lambda: self.move_down_clicked.emit(self._view_key))
        layout.addWidget(self.down_btn)

    def _update_icon_color(self):
        color = "#0078D4" if not isDarkTheme() else "#60CDFF"
        self.icon_w.setStyleSheet(f"background-color: {color}; border-radius: 2px;")

    def _update_sys_tag_style(self, tag):
        if isDarkTheme():
            tag.setStyleSheet("color: #AAA; font-size: 11px; padding: 1px 6px; background: rgba(255,255,255,0.08); border-radius: 3px;")
        else:
            tag.setStyleSheet("color: #888; font-size: 11px; padding: 1px 6px; background: rgba(0,0,0,0.06); border-radius: 3px;")


class CategoryListItem(QWidget):
    """分类列表项部件"""

    edit_clicked = Signal(int)
    delete_clicked = Signal(int)
    move_up_clicked = Signal(int)

    def __init__(self, category_id: int, name: str, parent=None):
        super().__init__(parent)
        self.category_id = category_id
        self._name = name
        self._setup_ui()
        self._update_icon_color()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)

        self.icon_label = QWidget()
        self.icon_label.setFixedSize(12, 12)
        self.icon_label.setStyleSheet("border-radius: 2px;")
        layout.addWidget(self.icon_label)

        self.name_label = BodyLabel(self._name)
        layout.addWidget(self.name_label, 1)

        self.up_btn = TransparentToolButton(FluentIcon.UP)
        self.up_btn.setFixedSize(28, 28)
        self.up_btn.setIconSize(QSize(12, 12))
        self.up_btn.setToolTip("上移")
        self.up_btn.clicked.connect(lambda: self.move_up_clicked.emit(self.category_id))
        layout.addWidget(self.up_btn)

        self.edit_btn = TransparentToolButton(FluentIcon.EDIT)
        self.edit_btn.setFixedSize(28, 28)
        self.edit_btn.setIconSize(QSize(12, 12))
        self.edit_btn.setToolTip("编辑")
        self.edit_btn.clicked.connect(lambda: self.edit_clicked.emit(self.category_id))
        layout.addWidget(self.edit_btn)

        self.delete_btn = TransparentToolButton(FluentIcon.DELETE)
        self.delete_btn.setFixedSize(28, 28)
        self.delete_btn.setIconSize(QSize(12, 12))
        self.delete_btn.setToolTip("删除")
        self.delete_btn.clicked.connect(lambda: self.delete_clicked.emit(self.category_id))
        layout.addWidget(self.delete_btn)

    def _update_icon_color(self):
        color = "#0078D4" if not isDarkTheme() else "#60CDFF"
        self.icon_label.setStyleSheet(f"background-color: {color}; border-radius: 2px;")


class CategoryDialog(QDialog):
    """分类管理对话框"""

    def __init__(self, parent=None):
        self.category_service = CategoryService()
        self._editing_id = None
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(400, 500)
        self._setup_ui()

        # 订阅分类事件总线，自身的数据变更也会通过总线回灌，
        # 这样就不需要调用方在 close 后再触发全量刷新，
        # 关闭的瞬间也不会出现"延迟动作"导致空窗口闪烁。
        bus = category_event_bus()
        bus.created.connect(self._on_category_event)
        bus.updated.connect(self._on_category_event)
        bus.deleted.connect(self._on_category_event)
        bus.reordered.connect(self._on_category_event)

        self._load_categories()

        # 窗口拖动相关
        self._drag_pos = None

    def mousePressEvent(self, event):
        """鼠标按下记录位置"""
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        """鼠标移动时拖动窗口"""
        if event.buttons() == Qt.MouseButton.LeftButton and self._drag_pos is not None:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        """鼠标释放清除位置"""
        self._drag_pos = None

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        dark = isDarkTheme()
        bg_color = QColor(43, 43, 43) if dark else QColor(249, 249, 249)
        border_color = QColor(60, 60, 60) if dark else QColor(210, 210, 210)
        path = QPainterPath()
        path.addRoundedRect(0.5, 0.5, self.width() - 1, self.height() - 1, 10, 10)
        painter.fillPath(path, bg_color)
        painter.setPen(border_color)
        painter.drawPath(path)
        super().paintEvent(event)

    def closeEvent(self, event):
        """关闭时释放数据库连接并断开事件总线订阅"""
        bus = category_event_bus()
        try:
            bus.created.disconnect(self._on_category_event)
            bus.updated.disconnect(self._on_category_event)
            bus.deleted.disconnect(self._on_category_event)
            bus.reordered.disconnect(self._on_category_event)
        except (TypeError, RuntimeError):
            # 重复 disconnect / 已断开时忽略
            pass
        super().closeEvent(event)

    def _on_category_event(self, *_args):
        """总线事件回调：刷新自身列表"""
        self._load_categories()
        # 退出编辑态，避免被改/被删的分类残留
        if self._editing_id is not None:
            cat = self.category_service.get_by_id(self._editing_id)
            if not cat:
                self._editing_id = None
                self.add_btn.setText(" 添加 ")

    def _setup_ui(self):
        from PySide6.QtWidgets import QFrame
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 12, 20, 16)
        layout.setSpacing(12)

        # ---- 顶部栏 ----
        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)

        title_label = SubtitleLabel("管理分类")
        title_label.setStyleSheet(f"font-weight: bold; color: {'#EEE' if isDarkTheme() else '#111'};")
        top_bar.addWidget(title_label, 1)

        close_btn = TransparentToolButton(FluentIcon.CLOSE)
        close_btn.setFixedSize(28, 28)
        close_btn.clicked.connect(self.reject)
        top_bar.addWidget(close_btn)

        layout.addLayout(top_bar)

        # 分隔线
        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet(f"background-color: {'#444' if isDarkTheme() else '#DDD'};")
        layout.addWidget(divider)

        # ---- 新建分类输入区 ----
        input_row = QHBoxLayout()
        input_row.setSpacing(10)

        self.name_input = LineEdit()
        self.name_input.setPlaceholderText("输入分类名称...")
        self.name_input.setMaxLength(20)
        self.name_input.setClearButtonEnabled(True)
        self.name_input.returnPressed.connect(self._on_add)
        input_row.addWidget(self.name_input, 1)

        self.add_btn = PrimaryPushButton(" 添加 ")
        self.add_btn.setIcon(FluentIcon.ADD)
        self.add_btn.clicked.connect(self._on_add)
        input_row.addWidget(self.add_btn)

        layout.addLayout(input_row)

        # ---- 分类列表 ----
        self.category_list = ListWidget()
        self.category_list.setMinimumHeight(280)
        layout.addWidget(self.category_list, 1)

    def showEvent(self, event):
        super().showEvent(event)
        screen = self.screen().availableGeometry()
        x = screen.x() + (screen.width() - self.width()) // 2
        y = screen.y() + (screen.height() - self.height()) // 2
        self.move(x, y)
        # 设置弹窗整体背景色
        if isDarkTheme():
            self.setStyleSheet("""
                QDialog {
                    background-color: transparent;
                }
                BodyLabel { color: #DDD; }
                LineEdit { background-color: rgb(59, 59, 59); color: #EEE; border: 1px solid rgb(80,80,80); border-radius: 6px; }
                ListWidget { background-color: rgb(59, 59, 59); color: #EEE; border: 1px solid rgb(80,80,80); border-radius: 6px; }
            """)
            # 更新列表项图标颜色
            for i in range(self.category_list.count()):
                item = self.category_list.item(i)
                widget = self.category_list.itemWidget(item)
                if widget and hasattr(widget, '_update_icon_color'):
                    widget._update_icon_color()
        else:
            self.setStyleSheet("""
                QDialog {
                    background-color: transparent;
                }
                BodyLabel { color: #333; }
                LineEdit { background-color: #FFF; color: #333; }
                ListWidget { background-color: #FFF; color: #333; }
            """)
            # 更新列表项图标颜色
            for i in range(self.category_list.count()):
                item = self.category_list.item(i)
                widget = self.category_list.itemWidget(item)
                if widget and hasattr(widget, '_update_icon_color'):
                    widget._update_icon_color()

    def _load_categories(self):
        """加载分类列表"""
        self.category_list.clear()

        from config.settings import settings
        order = settings.system_view_order
        for key in order:
            if key in SYSTEM_VIEW_MAP:
                name, icon = SYSTEM_VIEW_MAP[key]
                item = QListWidgetItem()
                widget = SystemViewItem(key, name, icon)
                widget.move_up_clicked.connect(self._on_system_view_move_up)
                widget.move_down_clicked.connect(self._on_system_view_move_down)
                self.category_list.addItem(item)
                self.category_list.setItemWidget(item, widget)
                item.setSizeHint(widget.sizeHint())

        sep_item = QListWidgetItem()
        sep_widget = QLabel()
        sep_widget.setFixedHeight(1)
        c = "#444" if isDarkTheme() else "#DDD"
        sep_widget.setStyleSheet(f"background-color: {c}; margin: 4px 8px;")
        self.category_list.addItem(sep_item)
        self.category_list.setItemWidget(sep_item, sep_widget)
        sep_item.setSizeHint(sep_widget.sizeHint())

        categories = self.category_service.get_all()
        for cat in categories:
            item = QListWidgetItem()
            item.setData(Qt.UserRole, cat.id)
            widget = CategoryListItem(cat.id, cat.name)
            widget.edit_clicked.connect(self._on_edit_clicked)
            widget.delete_clicked.connect(self._on_delete_clicked)
            widget.move_up_clicked.connect(self._on_move_up)
            self.category_list.addItem(item)
            self.category_list.setItemWidget(item, widget)
            item.setSizeHint(widget.sizeHint())

    def _on_add(self):
        """添加或保存编辑分类"""
        name = self.name_input.text().strip()
        if not name:
            return

        if self._editing_id:
            self.category_service.update(self._editing_id, name=name)
            self._editing_id = None
            self.add_btn.setText(" 添加 ")
        else:
            self.category_service.create(name)

        self.name_input.clear()
        # service 会通过事件总线触发 _on_category_event，列表自动刷新

    def _on_edit_clicked(self, category_id: int):
        """编辑按钮点击"""
        category = self.category_service.get_by_id(category_id)
        if category:
            self.name_input.setText(category.name)
            self.name_input.setFocus()
            self._editing_id = category_id
            self.add_btn.setText(" 保存 ")

    def _on_delete_clicked(self, category_id: int):
        """删除分类"""
        category = self.category_service.get_by_id(category_id)
        if not category:
            return

        msg = MessageBox("确认删除", f"确定要删除分类 \"{category.name}\" 吗？\n\n关联的任务将变为无分类。", self)
        msg.yesButton.setText("删除")
        msg.cancelButton.setText("取消")
        if msg.exec():
            self.category_service.delete(category_id)
            # service 会通过事件总线触发 _on_category_event，列表自动刷新

    def _on_move_up(self, category_id: int):
        """上移分类"""
        categories = self.category_service.get_all()
        cat_ids = [c.id for c in categories]

        idx = cat_ids.index(category_id)
        if idx > 0:
            cat_ids[idx], cat_ids[idx - 1] = cat_ids[idx - 1], cat_ids[idx]
            self.category_service.reorder(cat_ids)
            # service 会通过事件总线触发 _on_category_event，列表自动刷新

    def _on_system_view_move_up(self, view_key: str):
        """上移系统视图"""
        from config.settings import settings
        order = list(settings.system_view_order)
        idx = order.index(view_key) if view_key in order else -1
        if idx > 0:
            order[idx], order[idx - 1] = order[idx - 1], order[idx]
            settings.system_view_order = order
            # 系统视图顺序不影响分类数据，但本对话框顶部的"系统视图"段会展示出来
            self._load_categories()

    def _on_system_view_move_down(self, view_key: str):
        """下移系统视图"""
        from config.settings import settings
        order = list(settings.system_view_order)
        idx = order.index(view_key) if view_key in order else -1
        if 0 <= idx < len(order) - 1:
            order[idx], order[idx + 1] = order[idx + 1], order[idx]
            settings.system_view_order = order
            self._load_categories()
