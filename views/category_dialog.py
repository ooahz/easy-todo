"""分类管理对话框"""
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QWidget, QListWidgetItem
)

from qfluentwidgets import (
    LineEdit, PushButton, PrimaryPushButton, ListWidget,
    TransparentToolButton, FluentIcon, isDarkTheme, SubtitleLabel, MessageBox
)

from services.category_service import CategoryService


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

        # 分类图标
        self.icon_label = QWidget()
        self.icon_label.setFixedSize(12, 12)
        self.icon_label.setStyleSheet("border-radius: 2px;")
        layout.addWidget(self.icon_label)

        # 分类名称
        from qfluentwidgets import BodyLabel
        self.name_label = BodyLabel(self._name)
        layout.addWidget(self.name_label, 1)

        # 上移按钮
        self.up_btn = TransparentToolButton(FluentIcon.UP)
        self.up_btn.setFixedSize(28, 28)
        self.up_btn.setIconSize(QSize(12, 12))
        self.up_btn.setToolTip("上移")
        self.up_btn.clicked.connect(lambda: self.move_up_clicked.emit(self.category_id))
        layout.addWidget(self.up_btn)

        # 编辑按钮
        self.edit_btn = TransparentToolButton(FluentIcon.EDIT)
        self.edit_btn.setFixedSize(28, 28)
        self.edit_btn.setIconSize(QSize(12, 12))
        self.edit_btn.setToolTip("编辑")
        self.edit_btn.clicked.connect(lambda: self.edit_clicked.emit(self.category_id))
        layout.addWidget(self.edit_btn)

        # 删除按钮
        self.delete_btn = TransparentToolButton(FluentIcon.DELETE)
        self.delete_btn.setFixedSize(28, 28)
        self.delete_btn.setIconSize(QSize(12, 12))
        self.delete_btn.setToolTip("删除")
        self.delete_btn.clicked.connect(lambda: self.delete_clicked.emit(self.category_id))
        layout.addWidget(self.delete_btn)

    def _update_icon_color(self):
        """根据主题更新图标颜色"""
        color = "#0078D4" if not isDarkTheme() else "#60CDFF"
        self.icon_label.setStyleSheet(f"background-color: {color}; border-radius: 2px;")


class CategoryDialog(QDialog):
    """分类管理对话框"""

    categories_changed = Signal()

    def __init__(self, parent=None):
        self.category_service = CategoryService()
        self._editing_id = None
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setFixedSize(400, 420)
        self._setup_ui()
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

    def closeEvent(self, event):
        """关闭时释放数据库连接"""
        if hasattr(self, 'category_service') and self.category_service:
            self.category_service.close()
        super().closeEvent(event)

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
                    background-color: rgb(43, 43, 43);
                }
                BodyLabel { color: #DDD; }
                LineEdit { background-color: rgb(59, 59, 59); color: #EEE; border: 1px solid rgb(80,80,80); border-radius: 6px; }
                ListWidget { background-color: rgb(59, 59, 59); color: #EEE; border: 1px solid rgb(80,80,80); border-radius: 6px; }
            """)
            # 更新列表项图标颜色
            for i in range(self.category_list.count()):
                item = self.category_list.item(i)
                widget = self.category_list.itemWidget(item)
                if widget:
                    widget._update_icon_color()
        else:
            self.setStyleSheet("""
                QDialog {
                    background-color: rgb(249, 249, 249);
                }
                BodyLabel { color: #333; }
                LineEdit { background-color: #FFF; color: #333; }
                ListWidget { background-color: #FFF; color: #333; }
            """)
            # 更新列表项图标颜色
            for i in range(self.category_list.count()):
                item = self.category_list.item(i)
                widget = self.category_list.itemWidget(item)
                if widget:
                    widget._update_icon_color()

    def _load_categories(self):
        """加载分类列表"""
        self.category_list.clear()
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
        self._load_categories()
        self.categories_changed.emit()

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
            self._load_categories()
            self.categories_changed.emit()

    def _on_move_up(self, category_id: int):
        """上移分类"""
        categories = self.category_service.get_all()
        cat_ids = [c.id for c in categories]

        idx = cat_ids.index(category_id)
        if idx > 0:
            cat_ids[idx], cat_ids[idx - 1] = cat_ids[idx - 1], cat_ids[idx]
            self.category_service.reorder(cat_ids)
            self._load_categories()
            self.categories_changed.emit()
