"""浮窗组件 - 显示当前页面任务列表"""
from __future__ import annotations
from PySide6.QtCore import Qt, Signal, QPoint, QRect, QPropertyAnimation, QEasingCurve, QSequentialAnimationGroup, QParallelAnimationGroup, QSize, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QGraphicsOpacityEffect,
    QApplication, QGraphicsScale,
)
from PySide6.QtGui import QMouseEvent, QCursor, QIcon, QPainter, QPixmap, QVector3D

from qfluentwidgets import BodyLabel, SmoothScrollArea, isDarkTheme, LineEdit, FluentIcon, TransparentToolButton, PipsPager, PipsScrollButtonDisplayMode

from config.settings import settings


class FloatingWidget(QWidget):
    """浮窗布局"""

    todo_toggled = Signal(int)
    quick_add = Signal(str)       # 快速新建任务
    pin_changed = Signal(bool)    # 固定状态变更

    # 边缘检测区域宽度
    EDGE_SIZE = 5
    MIN_WIDTH = 240
    MIN_HEIGHT = 160
    SNAP_THRESHOLD = 20
    COLLAPSED_STRIP = 6
    COLLAPSE_DELAY = 400

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Window |
            Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
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
        self._user_visible = False
        self._closing = False
        self._page_size = 20
        self._current_page = 0
        self._snap_anim: QPropertyAnimation | None = None
        self._snapped_edges = 0       # 贴边方向位掩码: 上1 下2 左4 右8
        self._collapsed = False
        self._edge_animating = False
        self._expanded_pos = QPoint()
        self._collapse_timer = QTimer(self)
        self._collapse_timer.setSingleShot(True)
        self._collapse_timer.setInterval(self.COLLAPSE_DELAY)
        self._collapse_timer.timeout.connect(self._do_collapse)

        self._setup_ui()
        self._apply_theme()

    def _setup_ui(self):
        """构建 UI"""
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # 背景容器
        self.bg_frame = QFrame(self)
        self.bg_frame.setObjectName("floatingBg")
        self.bg_frame.setMouseTracking(True)

        bg_layout = QVBoxLayout(self.bg_frame)
        bg_layout.setContentsMargins(12, 10, 12, 10)
        bg_layout.setSpacing(6)

        # 标题栏
        self.title_bar = QWidget(self.bg_frame)
        self.title_bar.setFixedHeight(32)
        title_layout = QHBoxLayout(self.title_bar)
        title_layout.setContentsMargins(1, 0, 1, 0)

        self.title_label = BodyLabel("任务列表")
        self.title_label.setStyleSheet("font-weight: bold; font-size: 13px; border: none;")
        title_layout.addWidget(self.title_label)
        title_layout.addStretch()

        # 新建按钮
        self.add_btn = TransparentToolButton(FluentIcon.ADD)
        self.add_btn.setFixedSize(24, 24)
        self.add_btn.setIconSize(QSize(12, 12))
        self.add_btn.setToolTip("快速新建任务")
        self.add_btn.clicked.connect(self._show_quick_add)
        title_layout.addWidget(self.add_btn)

        # 固定按钮
        self.pin_btn = TransparentToolButton(FluentIcon.PIN)
        self.pin_btn.setFixedSize(24, 24)
        self.pin_btn.setIconSize(QSize(12, 12))
        self.pin_btn.setToolTip("固定浮窗")
        self.pin_btn.clicked.connect(self._toggle_pin)
        title_layout.addWidget(self.pin_btn)

        # 关闭按钮
        self.close_btn = TransparentToolButton(FluentIcon.CLOSE)
        self.close_btn.setFixedSize(24, 24)
        self.close_btn.setIconSize(QSize(12, 12))
        self.close_btn.setToolTip("关闭")
        self.close_btn.clicked.connect(self.hide)
        title_layout.addWidget(self.close_btn)

        bg_layout.addWidget(self.title_bar)

        # 分隔线
        self.sep = QLabel()
        self.sep.setFixedHeight(1)
        bg_layout.addWidget(self.sep)

        # 任务列表
        self.scroll = SmoothScrollArea(self.bg_frame)
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("SmoothScrollArea { border: none; background: transparent; }")
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.list_widget = QWidget(self.scroll)
        self.list_widget.setStyleSheet("background: transparent;")
        self.list_layout = QVBoxLayout(self.list_widget)
        self.list_layout.setContentsMargins(0, 4, 0, 4)
        self.list_layout.setSpacing(2)
        self.list_layout.addStretch()

        self.scroll.setWidget(self.list_widget)
        bg_layout.addWidget(self.scroll, 1)

        # 分页器
        self.pager = PipsPager(Qt.Horizontal)
        self.pager.setNextButtonDisplayMode(PipsScrollButtonDisplayMode.ALWAYS)
        self.pager.setPreviousButtonDisplayMode(PipsScrollButtonDisplayMode.ALWAYS)
        self.pager.setVisible(False)
        self.pager.currentIndexChanged.connect(self._on_page_changed)
        bg_layout.addWidget(self.pager, alignment=Qt.AlignCenter)

        # 固定状态遮罩层
        self._pin_mask = QWidget(self.scroll)
        self._pin_mask.setObjectName("pinMask")
        self._pin_mask.setVisible(False)
        self._pin_mask.setStyleSheet("#pinMask { background-color: transparent; }")
        # 安装事件过滤器：阻止点击，放行滚轮
        self._pin_mask.installEventFilter(self)

        # 遮罩层
        self.mask_layer = QLabel(self.bg_frame)
        self.mask_layer.setVisible(False)
        self.mask_opacity = QGraphicsOpacityEffect(self.mask_layer)
        self.mask_layer.setGraphicsEffect(self.mask_opacity)
        self.mask_opacity.setOpacity(0)

        # 快速新建弹窗
        self.quick_overlay = QFrame(self.bg_frame)
        self.quick_overlay.setObjectName("quickOverlay")
        self.quick_overlay.setVisible(False)
        self.overlay_opacity = QGraphicsOpacityEffect(self.quick_overlay)
        self.quick_overlay.setGraphicsEffect(self.overlay_opacity)
        self.overlay_opacity.setOpacity(0)
        overlay_layout = QVBoxLayout(self.quick_overlay)
        overlay_layout.setContentsMargins(12, 10, 12, 10)
        overlay_layout.setSpacing(8)
        overlay_title = BodyLabel("添加")
        overlay_title.setStyleSheet("font-weight: bold; font-size: 13px; border: none;")
        overlay_layout.addWidget(overlay_title)
        self.quick_input = LineEdit()
        self.quick_input.setPlaceholderText("输入任务标题...")
        self.quick_input.setClearButtonEnabled(True)
        self.quick_input.returnPressed.connect(self._on_quick_add)
        overlay_layout.addWidget(self.quick_input)
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
        """根据透明度更新背景色"""
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

    def eventFilter(self, obj, event):
        """固定遮罩事件过滤"""
        if obj is self._pin_mask:
            if event.type() == event.Type.MouseButtonPress:
                return True  # 阻止点击
            if event.type() in (event.Type.MouseButtonRelease, event.Type.MouseButtonDblClick):
                return True  # 阻止点击
            if event.type() == event.Type.Wheel:
                # 将滚轮事件转发给 scroll 的视口
                QApplication.sendEvent(self.scroll.viewport(), event)
                return True
        return super().eventFilter(obj, event)

    def resizeEvent(self, event):
        """窗口大小变化时更新固定遮罩尺寸"""
        super().resizeEvent(event)
        if self._pin_mask.isVisible():
            self._pin_mask.setGeometry(self.scroll.viewport().rect())

    def _update_pin_mask(self):
        """更新固定遮罩的显示状态和位置"""
        if self._pinned:
            self._pin_mask.setGeometry(self.scroll.viewport().rect())
            self._pin_mask.raise_()
            self._pin_mask.setVisible(True)
        else:
            self._pin_mask.setVisible(False)

    def set_pinned(self, pinned: bool):
        """设置固定状态"""
        self._pinned = pinned
        self.pin_btn.setIcon(FluentIcon.UNPIN if pinned else FluentIcon.PIN)
        self.pin_btn.setIconSize(QSize(12, 12))
        self.pin_btn.setToolTip("取消固定" if pinned else "固定浮窗")
        self._update_pin_mask()
        # 固定时展开并清除贴边状态
        if pinned and (self._collapsed or self._snapped_edges):
            self._collapse_timer.stop()
            if self._snap_anim is not None:
                self._snap_anim.stop()
                self._edge_animating = False
            self._snapped_edges = 0
            self._collapsed = False
            self.move(self._expanded_pos)

    def _toggle_pin(self):
        """切换固定状态"""
        self._pinned = not self._pinned
        self.set_pinned(self._pinned)
        self.pin_changed.emit(self._pinned)

    def _show_quick_add(self):
        """显示快速新建弹窗"""
        overlay_w = min(self.bg_frame.width() - 24, 240)
        overlay_h = 110
        x = (self.bg_frame.width() - overlay_w) // 2
        y = (self.bg_frame.height() - overlay_h) // 2
        self.quick_overlay.setFixedSize(overlay_w, overlay_h)
        self.quick_overlay.move(x, y)

        # 遮罩淡入
        self.mask_layer.setGeometry(self.bg_frame.rect())
        self.mask_layer.setStyleSheet("background-color: rgba(0, 0, 0, 0.3);")
        self.mask_layer.raise_()
        self.mask_layer.setVisible(True)
        self.mask_opacity.setOpacity(0)
        mask_anim = QPropertyAnimation(self.mask_opacity, b"opacity")
        mask_anim.setDuration(150)
        mask_anim.setStartValue(0)
        mask_anim.setEndValue(1)

        # 弹窗缩放+淡入
        self.quick_overlay.raise_()
        self.quick_overlay.setVisible(True)
        self.overlay_opacity.setOpacity(0)
        overlay_anim = QPropertyAnimation(self.overlay_opacity, b"opacity")
        overlay_anim.setDuration(150)
        overlay_anim.setStartValue(0)
        overlay_anim.setEndValue(1)

        group = QParallelAnimationGroup(self)
        group.addAnimation(mask_anim)
        group.addAnimation(overlay_anim)
        group.start()
        self.quick_input.setFocus()

    def _hide_quick_add(self):
        mask_anim = QPropertyAnimation(self.mask_opacity, b"opacity")
        mask_anim.setDuration(120)
        mask_anim.setStartValue(1)
        mask_anim.setEndValue(0)
        mask_anim.finished.connect(lambda: self.mask_layer.setVisible(False))

        overlay_anim = QPropertyAnimation(self.overlay_opacity, b"opacity")
        overlay_anim.setDuration(120)
        overlay_anim.setStartValue(1)
        overlay_anim.setEndValue(0)
        overlay_anim.finished.connect(lambda: self.quick_overlay.setVisible(False))

        group = QParallelAnimationGroup(self)
        group.addAnimation(mask_anim)
        group.addAnimation(overlay_anim)
        group.start()
        self.quick_input.clear()

    def _on_quick_add(self):
        """快速新建任务"""
        text = self.quick_input.text().strip()
        if text:
            self.quick_input.clear()
            self._hide_quick_add()
            self.quick_add.emit(text)

    def set_todos(self, todos: list[dict]):
        self._todos = todos
        self._current_page = 0
        self._update_pager()
        self._refresh_list()

    def refresh_theme(self):
        """主题切换时刷新浮窗样式"""
        self._apply_theme()
        self._refresh_list()

    def _refresh_list(self):
        from config.settings import settings

        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        c = self._theme_colors()
        show_subtasks = settings.floating_show_subtasks

        if not self._todos:
            empty = BodyLabel("暂无任务")
            empty.setStyleSheet(f"color: {c['empty']}; font-size: 12px; border: none;")
            empty.setAlignment(Qt.AlignCenter)
            self.list_layout.addWidget(empty)
        else:
            # 客户端分页：只渲染当前页的数据
            start = self._current_page * self._page_size
            end = start + self._page_size
            page_todos = self._todos[start:end]

            for todo in page_todos:
                # 父任务行
                row = self._create_todo_row(todo, c)
                self.list_layout.addWidget(row)
                # 子任务行
                if show_subtasks:
                    for child in todo.get("children", []):
                        child_row = self._create_todo_row(child, c, is_child=True)
                        self.list_layout.addWidget(child_row)

        self.list_layout.addStretch()

    def _create_todo_row(self, todo: dict, c: dict, is_child: bool = False) -> QWidget:
        is_done = todo.get("_is_done", False)
        due = todo.get("due_date")
        has_due = settings.floating_show_due_date and due and not is_done

        row = QFrame()
        row.setFixedHeight(42 if (has_due and not is_child) else (36 if has_due else (26 if is_child else 30)))
        row.setCursor(Qt.PointingHandCursor)

        color_tag = todo.get("color_tag")
        if is_child:
            border_left = "border-left: 2px solid transparent;"
        else:
            border_left = f"border-left: 3px solid {color_tag};" if color_tag else "border-left: 3px solid transparent;"

        is_overdue = False
        if due and not is_done:
            try:
                from datetime import date as pydate
                if pydate.fromisoformat(due) < pydate.today():
                    is_overdue = True
            except:
                pass

        if is_done:
            text_style = f"color: {c['done_text']}; text-decoration: line-through;"
        elif is_overdue:
            text_style = f"color: {settings.warning_color};"
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
        if is_child:
            h_layout.setContentsMargins(20, 2, 6, 2)
        else:
            h_layout.setContentsMargins(8, 2, 6, 2)
        h_layout.setSpacing(0)

        title = todo.get("title", "")
        font_size = "13px" if is_child else "15px"

        if has_due:
            try:
                from datetime import date as pydate
                due_date = pydate.fromisoformat(due)
                today = pydate.today()
                if due_date < today:
                    due_text = "已过期"
                    due_color = settings.warning_color
                elif due_date == today:
                    due_text = "今天"
                    due_color = c['title']
                else:
                    due_text = due
                    due_color = c['title']
                display = (
                    f'<span style="font-size:{font_size};{text_style}">{title}</span>'
                    f'<br><span style="font-size:11px;color:{due_color};float:right;margin-top:2px">{due_text}</span>'
                )
            except:
                display = f'<span style="font-size:{font_size};{text_style}">{title}</span>'
        else:
            display = f'<span style="font-size:{font_size};{text_style}">{title}</span>'

        content_label = QLabel(display)
        content_label.setToolTip(title)
        content_label.setWordWrap(True)
        content_label.setTextFormat(Qt.RichText)
        content_label.setStyleSheet("border: none; background: transparent;")
        h_layout.addWidget(content_label, 1)

        todo_id = todo["id"]
        row.mousePressEvent = lambda e, tid=todo_id: self._on_row_clicked(e, tid)
        return row

    def _on_row_clicked(self, event, todo_id: int):
        if event.button() == Qt.LeftButton:
            self.todo_toggled.emit(todo_id)

    def _update_pager(self):
        """更新分页器状态"""
        total = len(self._todos)
        total_pages = (total + self._page_size - 1) // self._page_size if total > 0 else 1

        if total_pages <= 1:
            self.pager.setVisible(False)
        else:
            self.pager.setVisible(True)
            self.pager.blockSignals(True)
            if self.pager.count() != total_pages:
                self.pager.setPageNumber(total_pages)
            if self._current_page >= total_pages:
                self._current_page = total_pages - 1
            self.pager.setCurrentIndex(self._current_page)
            self.pager.blockSignals(False)

    def _on_page_changed(self, index: int):
        """分页器页码变化，重新渲染当前页"""
        self._current_page = index
        self._refresh_list()

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
        if self._collapsed:
            self._do_expand()
            return
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
                # 拖拽开始时重置贴边状态
                self._collapse_timer.stop()
                if self._snapped_edges:
                    self._snapped_edges = 0
                    self._collapsed = False
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._collapsed or self._edge_animating:
            super().mouseMoveEvent(event)
            return

        if self._dragging and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            return

        if self._resizing and event.buttons() & Qt.LeftButton:
            delta = event.globalPosition().toPoint() - self._resize_start_pos
            geo = QRect(self._resize_start_geo)
            edge = self._resize_edge

            if edge & 1:   # 上
                geo.setTop(geo.top() + delta.y())
            if edge & 2:   # 下
                geo.setBottom(geo.bottom() + delta.y())
            if edge & 4:   # 左
                geo.setLeft(geo.left() + delta.x())
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

            # 强制最大尺寸
            max_w, max_h = 800, 1200
            if geo.width() > max_w:
                if edge & 4:
                    geo.setLeft(geo.right() - max_w)
                else:
                    geo.setRight(geo.left() + max_w)
            if geo.height() > max_h:
                if edge & 1:
                    geo.setTop(geo.bottom() - max_h)
                else:
                    geo.setBottom(geo.top() + max_h)

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
        was_dragging = self._dragging
        self._dragging = False
        self._resizing = False
        self._resize_edge = 0
        if was_dragging:
            self._snap_to_edge()
        super().mouseReleaseEvent(event)

    def enterEvent(self, event):
        if self._collapsed and self._snapped_edges and not self._edge_animating:
            self._do_expand()
        super().enterEvent(event)

    def leaveEvent(self, event):
        if (not self._collapsed and self._snapped_edges
                and not self._edge_animating
                and not self._dragging and not self._resizing
                and not self.quick_overlay.isVisible()):
            self._collapse_timer.start()
        super().leaveEvent(event)

    def _snap_to_edge(self):
        """拖拽结束"""
        if self._pinned:
            return

        screen = QApplication.screenAt(self.geometry().center())
        if not screen:
            screen = QApplication.primaryScreen()
        if not screen:
            return
        geo = screen.availableGeometry()
        threshold = self.SNAP_THRESHOLD

        pos = self.pos()
        target_x, target_y = pos.x(), pos.y()
        edges = 0

        # 左右贴边
        if pos.x() - geo.left() <= threshold:
            target_x = geo.left()
            edges |= 4  # 左
        elif geo.right() - (pos.x() + self.width()) <= threshold:
            target_x = geo.right() - self.width()
            edges |= 8  # 右

        # 上下贴边
        if pos.y() - geo.top() <= threshold:
            target_y = geo.top()
            edges |= 1  # 上
        elif geo.bottom() - (pos.y() + self.height()) <= threshold:
            target_y = geo.bottom() - self.height()
            edges |= 2  # 下

        if edges == 0:
            return  # 无需吸附

        # 记录展开位置和贴边方向
        self._expanded_pos = QPoint(target_x, target_y)
        self._snapped_edges = edges

        collapsed_pos = self._calc_collapsed_pos(geo)
        self._start_edge_anim(pos, collapsed_pos, on_done=self._on_snap_done)

    def _calc_collapsed_pos(self, screen_geo=None):
        """根据贴边方向计算收起位置"""
        if screen_geo is None:
            screen = QApplication.screenAt(self.geometry().center())
            if not screen:
                screen = QApplication.primaryScreen()
            if not screen:
                return self._expanded_pos
            screen_geo = screen.availableGeometry()

        x, y = self._expanded_pos.x(), self._expanded_pos.y()
        strip = self.COLLAPSED_STRIP

        if self._snapped_edges & 4:   # 左
            x = screen_geo.left() - (self.width() - strip)
        elif self._snapped_edges & 8: # 右
            x = screen_geo.right() - strip

        if self._snapped_edges & 1:   # 上
            y = screen_geo.top() - (self.height() - strip)
        elif self._snapped_edges & 2: # 下
            y = screen_geo.bottom() - strip

        return QPoint(x, y)

    def _start_edge_anim(self, start: QPoint, end: QPoint, on_done=None):
        if self._snap_anim is not None:
            self._snap_anim.stop()

        self._edge_animating = True
        self._snap_anim = QPropertyAnimation(self, b"pos")
        self._snap_anim.setDuration(200)
        self._snap_anim.setStartValue(start)
        self._snap_anim.setEndValue(end)
        self._snap_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        if on_done:
            self._snap_anim.finished.connect(on_done)
        self._snap_anim.start()

    def _on_snap_done(self):
        self._collapsed = True
        self._edge_animating = False

    # ---- 收起 / 展开 ----

    def _do_collapse(self):
        """收起浮窗到贴边条带"""
        if self._collapsed or self._edge_animating or self._snapped_edges == 0:
            return
        if self.quick_overlay.isVisible():
            self._collapse_timer.start()
            return

        screen = QApplication.screenAt(self.geometry().center())
        if not screen:
            screen = QApplication.primaryScreen()
        if not screen:
            return

        collapsed_pos = self._calc_collapsed_pos(screen.availableGeometry())
        self._start_edge_anim(self.pos(), collapsed_pos, on_done=self._on_collapse_done)

    def _on_collapse_done(self):
        self._collapsed = True
        self._edge_animating = False

    def _do_expand(self):
        """展开浮窗到贴边位置"""
        if not self._collapsed or self._edge_animating:
            return

        self._collapse_timer.stop()
        self._start_edge_anim(self.pos(), self._expanded_pos, on_done=self._on_expand_done)

    def _on_expand_done(self):
        self._collapsed = False
        self._edge_animating = False

    def show(self):
        self.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, False)
        self._user_visible = True
        super().show()

    def hide(self):
        self._user_visible = False
        super().hide()

    def close(self):
        self._closing = True
        self._user_visible = False
        super().close()

    def hideEvent(self, event):
        super().hideEvent(event)
        if self._user_visible and not self._closing:
            QTimer.singleShot(50, self._restore_visibility)

    def _restore_visibility(self):
        if self._user_visible and not self._closing:
            super().show()

    def showEvent(self, event):
        super().showEvent(event)
        self._apply_theme()
        if self._todos:
            self._refresh_list()
        self._update_pin_mask()
