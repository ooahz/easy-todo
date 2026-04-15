"""浮窗组件 - 显示当前页面任务列表"""
from PySide6.QtCore import Qt, Signal, QPoint, QRect
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
)
from PySide6.QtGui import QMouseEvent, QCursor

from qfluentwidgets import BodyLabel, SmoothScrollArea, isDarkTheme


class FloatingWidget(QWidget):
    """浮窗 - 置顶、无边框、可拖动、四边+四角可调整大小"""

    todo_toggled = Signal(int)

    # 边缘检测区域宽度
    EDGE_SIZE = 5
    MIN_WIDTH = 240
    MIN_HEIGHT = 160

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Tool
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
        title_layout.setContentsMargins(4, 0, 4, 0)

        self.title_label = BodyLabel("任务列表")
        self.title_label.setStyleSheet("font-weight: bold; font-size: 13px; border: none;")
        title_layout.addWidget(self.title_label)
        title_layout.addStretch()

        # 关闭按钮
        self.close_btn = QLabel("X")
        self.close_btn.setFixedSize(20, 20)
        self.close_btn.setAlignment(Qt.AlignCenter)
        self.close_btn.setCursor(Qt.PointingHandCursor)
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

        self.main_layout.addWidget(self.bg_frame)
        self._apply_theme()

    def _setup_opacity(self):
        """透明度只影响背景色，不影响内容"""
        pass

    def _update_bg_opacity(self):
        """根据透明度更新背景色"""
        c = self._theme_colors()
        # 解析原始背景色的 RGB 值
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
        self.close_btn.setStyleSheet(f"""
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
            if edge:
                self._resizing = True
                self._resize_edge = edge
                self._resize_start_geo = self.geometry()
                self._resize_start_pos = event.globalPosition().toPoint()
                return
            if self.title_bar.underMouse():
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
            edge = self._detect_edge(event.pos())
            if edge:
                self.setCursor(self._edge_cursor(edge))
            elif self.title_bar.underMouse():
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
