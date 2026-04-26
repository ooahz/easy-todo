"""浮窗组件 - 显示当前页面任务列表"""
from PySide6.QtCore import Qt, Signal, QPoint, QRect
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
)
from PySide6.QtGui import QMouseEvent, QCursor

from qfluentwidgets import BodyLabel, SmoothScrollArea, isDarkTheme, LineEdit


class FloatingWidget(QWidget):
    """浮窗布局"""

    todo_toggled = Signal(int)
    quick_add = Signal(str)       # 快速新建任务
    pin_changed = Signal(bool)    # 固定状态变更

    # 边缘检测区域宽度
    EDGE_SIZE = 5
    MIN_WIDTH = 240
    MIN_HEIGHT = 160

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Window |
            Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMouseTracking(True)
        self.resize(300, 400)
        self.setMinimumSize(self.MIN_WIDTH, self.MIN_HEIGHT)
        self.setMaximumSize(800, 1200)

        self._opacity = 0.95
        self._dragging = False
        self._resizing = False
        self._resize_edge = 0  # 位掩码: 上1 下2 左4 右8
        self._drag_pos = QPoint()
        self._resize_start_geo = QRect()
        self._resize_start_pos = QPoint()
        self._todos: list[dict] = []
        self._pinned = False

        self._setup_ui()
        self._apply_theme()

    def _setup_ui(self):
        """构建 UI"""
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # 背景容器
        self.bg_frame = QFrame()
        self.bg_frame.setObjectName("floatingBg")
        self.bg_frame.setMouseTracking(True)

        bg_layout = QVBoxLayout(self.bg_frame)
        bg_layout.setContentsMargins(12, 10, 12, 10)
        bg_layout.setSpacing(6)

        # 标题栏
        self.title_bar = QWidget()
        self.title_bar.setFixedHeight(32)
        title_layout = QHBoxLayout(self.title_bar)
        title_layout.setContentsMargins(1, 0, 1, 0)

        self.title_label = BodyLabel("任务列表")
        self.title_label.setStyleSheet("font-weight: bold; font-size: 13px; border: none;")
        title_layout.addWidget(self.title_label)
        title_layout.addStretch()

        # 新建按钮（固定按钮左侧）
        self.add_btn = QLabel("+")
        self.add_btn.setFixedSize(20, 20)
        self.add_btn.setAlignment(Qt.AlignCenter)
        self.add_btn.setCursor(Qt.PointingHandCursor)
        self.add_btn.setToolTip("快速新建任务")
        self.add_btn.mousePressEvent = lambda e: self._show_quick_add()
        title_layout.addWidget(self.add_btn)

        # 固定按钮
        self.pin_btn = QLabel("○")
        self.pin_btn.setFixedSize(20, 20)
        self.pin_btn.setAlignment(Qt.AlignCenter)
        self.pin_btn.setCursor(Qt.PointingHandCursor)
        self.pin_btn.setToolTip("固定浮窗")
        self.pin_btn.mousePressEvent = lambda e: self._toggle_pin()
        title_layout.addWidget(self.pin_btn)

        # 关闭按钮
        self.close_btn = QLabel("X")
        self.close_btn.setFixedSize(20, 20)
        self.close_btn.setAlignment(Qt.AlignCenter)
        self.close_btn.setCursor(Qt.PointingHandCursor)
        self.close_btn.setToolTip("关闭")
        self.close_btn.mousePressEvent = lambda e: self.hide()
        title_layout.addWidget(self.close_btn)

        bg_layout.addWidget(self.title_bar)

        # 分隔线
        self.sep = QLabel()
        self.sep.setFixedHeight(1)
        bg_layout.addWidget(self.sep)

        # 任务列表
        self.scroll = SmoothScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("SmoothScrollArea { border: none; background: transparent; }")
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.list_widget = QWidget()
        self.list_widget.setStyleSheet("background: transparent;")
        self.list_layout = QVBoxLayout(self.list_widget)
        self.list_layout.setContentsMargins(0, 4, 0, 4)
        self.list_layout.setSpacing(2)
        self.list_layout.addStretch()

        self.scroll.setWidget(self.list_widget)
        bg_layout.addWidget(self.scroll, 1)

        # 遮罩层
        self.mask_layer = QLabel(self.bg_frame)
        self.mask_layer.setVisible(False)

        # 弹窗
        self.quick_overlay = QFrame(self.bg_frame)
        self.quick_overlay.setObjectName("quickOverlay")
        self.quick_overlay.setVisible(False)
        overlay_layout = QVBoxLayout(self.quick_overlay)
        overlay_layout.setContentsMargins(12, 10, 12, 10)
        overlay_layout.setSpacing(8)
        overlay_title = BodyLabel("快速添加")
        overlay_title.setStyleSheet("font-weight: bold; font-size: 13px; border: none;")
        overlay_layout.addWidget(overlay_title)
        self.quick_input = LineEdit()
        self.quick_input.setPlaceholderText("输入任务标题...")
        self.quick_input.setClearButtonEnabled(True)
        self.quick_input.returnPressed.connect(self._on_quick_add)
        overlay_layout.addWidget(self.quick_input)
        # 按钮
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.setSpacing(12)
        self.quick_cancel = QLabel("取消")
        self.quick_cancel.setCursor(Qt.PointingHandCursor)
        self.quick_cancel.mousePressEvent = lambda e: self._hide_quick_add()
        btn_row.addWidget(self.quick_cancel)
        self.quick_confirm = QLabel("确认")
        self.quick_confirm.setCursor(Qt.PointingHandCursor)
        self.quick_confirm.mousePressEvent = lambda e: self._on_quick_add()
        btn_row.addWidget(self.quick_confirm)
        overlay_layout.addLayout(btn_row)

        self.main_layout.addWidget(self.bg_frame)
        self._apply_theme()

    def _setup_opacity(self):
        pass

    def _update_bg_opacity(self):
        """更新背景色"""
        c = self._theme_colors()
        if isDarkTheme():
            r, g, b = 45, 45, 45
        else:
            r, g, b = 255, 255, 255
        alpha = int(self._opacity * 255)
        self.bg_frame.setStyleSheet(f"""
            #floatingBg {{
                background-color: rgba({r}, {g}, {b}, {alpha});
                border: 1px solid {c['border']};
                border-radius: 12px;
            }}
        """)

    def _apply_theme(self):
        c = self._theme_colors()
        if isDarkTheme():
            r, g, b = 45, 45, 45
        else:
            r, g, b = 255, 255, 255
        alpha = int(self._opacity * 255)
        self.bg_frame.setStyleSheet(f"""
            #floatingBg {{
                background-color: rgba({r}, {g}, {b}, {alpha});
                border: 1px solid {c['border']};
                border-radius: 12px;
            }}
        """)
        title_color = f"color: {c['title']};" if c['title'] else ""
        self.title_label.setStyleSheet(
            f"font-weight: bold; font-size: 13px; {title_color} border: none;"
        )
        # 操作按钮样式
        for btn in (self.add_btn, self.pin_btn, self.close_btn):
            btn.setStyleSheet(f"""
                QLabel {{
                    color: {c['close']};
                    font-size: 12px;
                    border-radius: 10px;
                    border: none;
                }}
                QLabel:hover {{
                    color: {c['close_hover']};
                    background-color: {c['close_hover_bg']};
                }}
            """)
        self.sep.setStyleSheet(f"background-color: {c['sep']}; border: none;")
        # 快速新建弹窗样式
        if isDarkTheme():
            overlay_bg = "rgba(43, 43, 43, 240)"
            input_bg = "rgb(59, 59, 59)"
            input_border = "rgb(80, 80, 80)"
            input_color = "#EEE"
            btn_color = "#0078D4"
        else:
            overlay_bg = "rgba(255, 255, 255, 245)"
            input_bg = "#FFF"
            input_border = "rgb(200, 200, 200)"
            input_color = "#333"
            btn_color = "#0078D4"
        self.quick_overlay.setStyleSheet(f"""
            #quickOverlay {{
                background-color: {overlay_bg};
                border: 1px solid {c['border']};
                border-radius: 8px;
            }}
            LineEdit {{
                background-color: {input_bg};
                color: {input_color};
                border: 1px solid {input_border};
                border-radius: 6px;
            }}
        """)
        self.quick_cancel.setStyleSheet(f"color: #888; font-size: 13px; border: none;")
        self.quick_confirm.setStyleSheet(f"color: {btn_color}; font-size: 13px; font-weight: bold; border: none;")

    @staticmethod
    def _theme_colors():
        if isDarkTheme():
            return {
                "bg": "rgba(45, 45, 45, 245)",
                "border": "rgba(255, 255, 255, 0.08)",
                "title": "#EEE",
                "close": "#888",
                "close_hover": "#FFF",
                "close_hover_bg": "rgba(255,255,255,0.1)",
                "sep": "rgba(255,255,255,0.06)",
                "empty": "#888",
                "done_text": "#666",
                "row_hover": "rgba(255,255,255,0.06)",
            }
        return {
            "bg": "rgba(255, 255, 255, 245)",
            "border": "rgba(0, 0, 0, 0.08)",
            "title": "",
            "close": "#999",
            "close_hover": "#333",
            "close_hover_bg": "rgba(0,0,0,0.06)",
            "sep": "rgba(0,0,0,0.06)",
            "empty": "#999",
            "done_text": "#999",
            "row_hover": "rgba(0,0,0,0.04)",
        }

    def set_opacity(self, value: float):
        self._opacity = max(0.1, min(1.0, value))
        self._update_bg_opacity()

    def get_opacity(self) -> float:
        return self._opacity

    def set_always_on_top(self, enabled: bool):
        """设置浮窗是否始终置顶"""
        was_visible = self.isVisible()
        flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
        if enabled:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMouseTracking(True)
        if was_visible:
            self.show()

    def set_pinned(self, pinned: bool):
        """设置固定状态"""
        self._pinned = pinned
        self.pin_btn.setText("◉" if pinned else "○")
        self.pin_btn.setToolTip("取消固定" if pinned else "固定浮窗")

    def _toggle_pin(self):
        """切换固定状态"""
        self._pinned = not self._pinned
        self.set_pinned(self._pinned)
        self.pin_changed.emit(self._pinned)

    def _show_quick_add(self):
        """显示快速新建弹窗"""
        # 显示遮罩层
        self.mask_layer.setGeometry(self.bg_frame.rect())
        self.mask_layer.setStyleSheet("background-color: rgba(0, 0, 0, 0.3);")
        self.mask_layer.raise_()
        self.mask_layer.setVisible(True)
        # 居中显示弹窗
        overlay_w = min(self.bg_frame.width() - 24, 240)
        overlay_h = 110
        x = (self.bg_frame.width() - overlay_w) // 2
        y = (self.bg_frame.height() - overlay_h) // 2
        self.quick_overlay.setFixedSize(overlay_w, overlay_h)
        self.quick_overlay.move(x, y)
        self.quick_overlay.raise_()
        self.quick_overlay.setVisible(True)
        self.quick_input.setFocus()

    def _hide_quick_add(self):
        """隐藏快速新建弹窗"""
        self.mask_layer.setVisible(False)
        self.quick_overlay.setVisible(False)
        self.quick_input.clear()

    def _on_quick_add(self):
        """快速新建任务"""
        text = self.quick_input.text().strip()
        if text:
            self.quick_input.clear()
            self.mask_layer.setVisible(False)
            self.quick_overlay.setVisible(False)
            self.quick_add.emit(text)

    def set_todos(self, todos: list[dict]):
        self._todos = todos
        self._refresh_list()

    def refresh_theme(self):
        """主题切换时刷新浮窗样式"""
        self._apply_theme()
        self._refresh_list()

    def _refresh_list(self):
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        c = self._theme_colors()

        if not self._todos:
            empty = BodyLabel("暂无任务")
            empty.setStyleSheet(f"color: {c['empty']}; font-size: 12px; border: none;")
            empty.setAlignment(Qt.AlignCenter)
            self.list_layout.addWidget(empty)
        else:
            for todo in self._todos:
                row = self._create_todo_row(todo, c)
                self.list_layout.addWidget(row)

        self.list_layout.addStretch()

    def _create_todo_row(self, todo: dict, c: dict) -> QWidget:
        row = QFrame()
        row.setFixedHeight(30)
        row.setCursor(Qt.PointingHandCursor)

        color_tag = todo.get("color_tag")
        border_left = f"border-left: 3px solid {color_tag};" if color_tag else "border-left: 3px solid transparent;"

        status = todo.get("status", 0)
        if status == 1:
            text_style = f"color: {c['done_text']}; text-decoration: line-through;"
        else:
            text_style = f"color: {c['title']};"

        row.setStyleSheet(f"""
            QFrame {{
                {border_left}
                border-top: none;
                border-right: none;
                border-bottom: none;
                border-radius: 4px;
                background: transparent;
            }}
            QFrame:hover {{
                background-color: {c['row_hover']};
            }}
        """)

        h_layout = QHBoxLayout(row)
        h_layout.setContentsMargins(8, 0, 6, 0)
        h_layout.setSpacing(0)

        title_label = BodyLabel(todo.get("title", ""))
        title_label.setStyleSheet(f"font-size: 15px; {text_style} border: none;")
        h_layout.addWidget(title_label, 1)

        todo_id = todo["id"]
        row.mousePressEvent = lambda e, tid=todo_id: self._on_row_clicked(e, tid)
        return row

    def _on_row_clicked(self, event, todo_id: int):
        if event.button() == Qt.LeftButton:
            self.todo_toggled.emit(todo_id)

    # ---- 边缘检测 ----

    def _detect_edge(self, pos: QPoint) -> int:
        """检测鼠标位于哪个边缘，返回位掩码"""
        edge = 0
        x, y = pos.x(), pos.y()
        w, h = self.width(), self.height()
        e = self.EDGE_SIZE

        if y <= e:
            edge |= 1   # 上
        if y >= h - e:
            edge |= 2   # 下
        if x <= e:
            edge |= 4   # 左
        if x >= w - e:
            edge |= 8   # 右
        return edge

    @staticmethod
    def _edge_cursor(edge: int) -> Qt.CursorShape:
        """根据边缘返回光标样式"""
        cursors = {
            1: Qt.CursorShape.SizeVerCursor,          # 上
            2: Qt.CursorShape.SizeVerCursor,          # 下
            4: Qt.CursorShape.SizeHorCursor,          # 左
            8: Qt.CursorShape.SizeHorCursor,          # 右
            5: Qt.CursorShape.SizeFDiagCursor,        # 上+左
            10: Qt.CursorShape.SizeFDiagCursor,       # 上+右
            6: Qt.CursorShape.SizeBDiagCursor,        # 下+左
            9: Qt.CursorShape.SizeBDiagCursor,        # 下+右
        }
        return cursors.get(edge, Qt.CursorShape.ArrowCursor)

    # ---- 鼠标事件 ----

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            edge = self._detect_edge(event.pos())
            if edge and not self._pinned:
                self._resizing = True
                self._resize_edge = edge
                self._resize_start_geo = self.geometry()
                self._resize_start_pos = event.globalPosition().toPoint()
                return
            if self.title_bar.underMouse() and not self._pinned:
                self._dragging = True
                self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._dragging and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            return

        if self._resizing and event.buttons() & Qt.LeftButton:
            delta = event.globalPosition().toPoint() - self._resize_start_pos
            geo = QRect(self._resize_start_geo)
            edge = self._resize_edge

            if edge & 1:   # 上
                new_top = geo.top() + delta.y()
                if self.height() - delta.y() >= self.MIN_HEIGHT:
                    geo.setTop(new_top)
            if edge & 2:   # 下
                geo.setBottom(geo.bottom() + delta.y())
            if edge & 4:   # 左
                new_left = geo.left() + delta.x()
                if self.width() - delta.x() >= self.MIN_WIDTH:
                    geo.setLeft(new_left)
            if edge & 8:   # 右
                geo.setRight(geo.right() + delta.x())

            # 强制最小尺寸
            if geo.width() < self.MIN_WIDTH:
                if edge & 4:
                    geo.setLeft(geo.right() - self.MIN_WIDTH)
                else:
                    geo.setRight(geo.left() + self.MIN_WIDTH)
            if geo.height() < self.MIN_HEIGHT:
                if edge & 1:
                    geo.setTop(geo.bottom() - self.MIN_HEIGHT)
                else:
                    geo.setBottom(geo.top() + self.MIN_HEIGHT)

            self.setGeometry(geo)
            return

        # 非拖动时更新光标
        if not self._dragging and not self._resizing:
            if self._pinned:
                self.unsetCursor()
            else:
                edge = self._detect_edge(event.pos())
                if edge:
                    self.setCursor(self._edge_cursor(edge))
                elif self.title_bar.underMouse() and not self._pinned:
                    self.setCursor(Qt.CursorShape.SizeAllCursor)
                else:
                    self.unsetCursor()

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        self._dragging = False
        self._resizing = False
        self._resize_edge = 0
        super().mouseReleaseEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
        self._apply_theme()
        if self._todos:
            self._refresh_list()
