"""待办列表视图 - 核心内容区域"""
from __future__ import annotations

from datetime import date
from datetime import date as date_type

from PySide6.QtCore import Signal, Qt, QDate, QSize, QPoint
from PySide6.QtGui import QPainter, QColor
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QWidget, QApplication
)
from qfluentwidgets import (
    ComboBox, CalendarPicker, ToolButton, SmoothScrollArea, PipsPager, PipsScrollButtonDisplayMode, isDarkTheme,
    FluentIcon, CaptionLabel, PushButton, PrimaryPushButton, BodyLabel
)

from config.constants import PRIORITY_GROUP_COLORS, PRIORITY_MAP
from config.settings import settings
from config.theme_config import FontSize, palette, theme_colors, tooltip_style
from views.calendar_view import WeekView
from views.subtask_card import SubtaskCard
from views.todo_card import TodoCard


class DateRangeButton(QPushButton):
    """日期范围选择按钮，点击后打开抽屉式面板选择开始日期和截止日期"""

    date_changed = Signal()

    def __init__(self, parent=None, placeholder: str = "截止日期"):
        super().__init__(parent)
        self._start_date = None
        self._due_date = None
        self._drawer = None
        self._placeholder = placeholder

        self.setText(placeholder)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(33)
        self.clicked.connect(self._open_drawer)

    def paintEvent(self, event):
        c = palette()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 使用与弹窗一致的背景色（#FCFCFC / #2B2B2B）
        bg = QColor(43, 43, 43) if isDarkTheme() else QColor(252, 252, 252)
        text_color = QColor(c.SUBTITLE if isDarkTheme() else c.BODY_LIGHT)

        # 绘制背景（无边框无阴影）
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(bg)
        painter.drawRoundedRect(0, 0, self.width(), self.height(), 6, 6)

        # 绘制文字
        painter.setPen(text_color)
        font = painter.font()
        font.setPixelSize(13)
        painter.setFont(font)
        text_width = self.width() - 40
        painter.drawText(12, 0, text_width, self.height(), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                         self.text())

        # 绘制右侧日历图标
        from PySide6.QtGui import QPixmap
        icon = FluentIcon.CALENDAR.icon()
        icon_color = QColor(160, 160, 160) if isDarkTheme() else QColor(136, 136, 136)
        pixmap = icon.pixmap(QSize(14, 14))
        # 给图标着色
        colored = QPixmap(pixmap.size())
        colored.fill(Qt.GlobalColor.transparent)
        p = QPainter(colored)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        p.drawPixmap(0, 0, pixmap)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        p.fillRect(colored.rect(), icon_color)
        p.end()
        painter.drawPixmap(self.width() - 26, (self.height() - 14) // 2, colored)

        painter.end()

    def _update_display(self):
        """更新按钮显示文本，并自动调整宽度"""
        if self._start_date and self._due_date:
            start_str = self._start_date.strftime("%m/%d") if isinstance(self._start_date, date) else str(
                self._start_date)
            due_str = self._due_date.strftime("%m/%d") if isinstance(self._due_date, date) else str(self._due_date)
            self.setText(f"{start_str} ~ {due_str}")
        elif self._due_date:
            due_str = self._due_date.strftime("%Y/%m/%d") if isinstance(self._due_date, date) else str(self._due_date)
            self.setText(due_str)
        elif self._start_date:
            start_str = self._start_date.strftime("%m/%d") if isinstance(self._start_date, date) else str(
                self._start_date)
            self.setText(f"{start_str} ~ ...")
        else:
            self.setText(self._placeholder)

        # 根据文本长度自动调整按钮宽度
        from PySide6.QtGui import QFontMetrics
        fm = QFontMetrics(self.font())
        text_width = fm.horizontalAdvance(self.text())
        # 文字宽度 + 左边距12 + 右侧图标区域26 + 边距余量
        new_width = max(120, text_width + 48)
        self.setMinimumWidth(new_width)

    def set_start_date(self, d):
        """设置起始日期 (date object, QDate, or None)"""
        if d is None:
            self._start_date = None
        elif isinstance(d, QDate):
            self._start_date = date(d.year(), d.month(), d.day()) if d.isValid() else None
        else:
            self._start_date = d
        self._update_display()

    def set_due_date(self, d):
        """设置截止日期 (date object, QDate, or None)"""
        if d is None:
            self._due_date = None
        elif isinstance(d, QDate):
            self._due_date = date(d.year(), d.month(), d.day()) if d.isValid() else None
        else:
            self._due_date = d
        self._update_display()

    def get_start_date(self):
        """返回起始日期的 date 对象或 None"""
        return self._start_date

    def get_due_date(self):
        """返回截止日期的 date 对象或 None"""
        return self._due_date

    def clear_dates(self):
        """清除所有日期"""
        self._start_date = None
        self._due_date = None
        self._update_display()

    def _open_drawer(self):
        """打开抽屉式日期选择面板"""
        if self._drawer is not None:
            self._drawer.close()
            self._drawer = None
            return

        dark = isDarkTheme()
        label_color = "#CCC" if dark else "#666"

        # 使用自定义绘制背景的容器
        class DrawerFrame(QFrame):
            def __init__(self, parent=None):
                super().__init__(parent)
                self._dark = isDarkTheme()

            def paintEvent(self, event):
                painter = QPainter(self)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                # 使用与 ComboBox 下拉面板一致的背景色
                bg_color = QColor(43, 43, 43) if self._dark else QColor(252, 252, 252)
                border_color = QColor(65, 65, 65) if self._dark else QColor(225, 225, 225)
                # 绘制圆角背景
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(bg_color)
                painter.drawRoundedRect(0, 0, self.width(), self.height(), 10, 10)
                # 绘制边框
                painter.setPen(border_color)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRoundedRect(0.5, 0.5, self.width() - 1, self.height() - 1, 10, 10)
                painter.end()

        drawer = DrawerFrame(self.window())
        drawer.setWindowFlags(
            Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint | Qt.WindowType.NoDropShadowWindowHint)
        drawer.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        layout = QVBoxLayout(drawer)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        # 起始日期
        start_label = CaptionLabel("起始日期")
        start_label.setStyleSheet(f"color: {label_color}; font-size: 12px; font-weight: bold;")
        layout.addWidget(start_label)

        start_picker = CalendarPicker()
        start_picker.setToolTip("选择起始日期")
        try:
            start_picker.setText("起始日期")
        except Exception:
            pass
        if self._start_date:
            sd = self._start_date
            start_picker.setDate(QDate(sd.year, sd.month, sd.day) if isinstance(sd, date) else QDate())
        else:
            start_picker.setDate(QDate.currentDate())
        layout.addWidget(start_picker)

        # 截止日期
        due_label = CaptionLabel("截止日期")
        due_label.setStyleSheet(f"color: {label_color}; font-size: 12px; font-weight: bold;")
        layout.addWidget(due_label)

        due_picker = CalendarPicker()
        due_picker.setToolTip("选择截止日期")
        try:
            due_picker.setText("截止日期")
        except Exception:
            pass
        if self._due_date:
            dd = self._due_date
            due_picker.setDate(QDate(dd.year, dd.month, dd.day) if isinstance(dd, date) else QDate())
        else:
            due_picker.setDate(QDate.currentDate())
        layout.addWidget(due_picker)

        # 按钮行
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        clear_btn = PushButton("清除")
        clear_btn.setFixedHeight(28)
        clear_btn.clicked.connect(lambda: self._on_drawer_clear(drawer, start_picker, due_picker))

        save_btn = PrimaryPushButton("保存")
        save_btn.setFixedHeight(28)
        save_btn.clicked.connect(lambda: self._on_drawer_save(drawer, start_picker, due_picker))

        btn_row.addStretch()
        btn_row.addWidget(clear_btn)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

        # 定位：在按钮下方弹出
        drawer.adjustSize()
        btn_pos = self.mapToGlobal(QPoint(0, self.height()))
        # 确保不超出屏幕
        screen = QApplication.screenAt(btn_pos)
        if screen:
            screen_geo = screen.availableGeometry()
            x = min(btn_pos.x(), screen_geo.right() - drawer.width())
            y = btn_pos.y() + 4
            if y + drawer.height() > screen_geo.bottom():
                y = self.mapToGlobal(QPoint(0, 0)).y() - drawer.height() - 4
        else:
            x, y = btn_pos.x(), btn_pos.y() + 4

        drawer.move(x, y)
        drawer.show()
        self._drawer = drawer

    def _on_drawer_clear(self, drawer, start_picker, due_picker):
        """清除日期"""
        self._start_date = None
        self._due_date = None
        start_picker.setDate(QDate())
        try:
            start_picker.setText("起始日期")
        except Exception:
            pass
        due_picker.setDate(QDate())
        try:
            due_picker.setText("截止日期")
        except Exception:
            pass
        self._update_display()
        self.date_changed.emit()
        drawer.close()
        self._drawer = None

    def _on_drawer_save(self, drawer, start_picker, due_picker):
        """保存日期选择"""
        # 获取起始日期
        new_start = None
        try:
            qdate = start_picker.getDate()
            if qdate is not None and hasattr(qdate, 'isValid') and qdate.isValid():
                new_start = date(qdate.year(), qdate.month(), qdate.day())
        except Exception:
            pass

        # 获取截止日期
        new_due = None
        try:
            qdate = due_picker.getDate()
            if qdate is not None and hasattr(qdate, 'isValid') and qdate.isValid():
                new_due = date(qdate.year(), qdate.month(), qdate.day())
        except Exception:
            pass

        # 校验起始日期不能超过截止日期
        if new_start and new_due and new_start > new_due:
            from qfluentwidgets import InfoBar, InfoBarPosition
            InfoBar.warning(
                title="日期无效",
                content="起始日期不能超过截止日期",
                parent=self.window(),
                position=InfoBarPosition.TOP,
                duration=3000,
            )
            return

        # 校验日期范围不超过一年
        if new_start and new_due:
            delta = (new_due - new_start).days
            if delta > 365:
                from qfluentwidgets import InfoBar, InfoBarPosition
                InfoBar.warning(
                    title="范围过大",
                    content="筛选日期范围不能超过一年",
                    parent=self.window(),
                    position=InfoBarPosition.TOP,
                    duration=3000,
                )
                return

        self._start_date = new_start
        self._due_date = new_due
        self._update_display()
        self.date_changed.emit()
        drawer.close()
        self._drawer = None


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
    time_filter_changed = Signal(str)
    page_changed = Signal(int, int)  # (page, page_size)

    def __init__(self, parent=None, view_name: str = "", readonly: bool = False):
        super().__init__(parent)
        self._todos: list[dict] = []
        self._all_todos: list[dict] = []
        self._cards: list = []
        self._view_name = view_name
        self._readonly = readonly
        self._filter_date: date_type | None = None
        self._time_filter: str = "all"
        self._custom_due_start: date_type | None = None
        self._custom_due_end: date_type | None = None
        self._page_size = 100
        self._current_page = 0
        self._total_count = 0
        self._stats: dict | None = None
        self._groups: list[dict] | None = None
        self._group_display_limit = 50
        self._expanded_groups: set[str] = set()

        self._setup_ui()

    def _setup_ui(self):
        """构建 UI"""
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(20, 16, 20, 8)
        self.main_layout.setSpacing(12)

        # ---- 顶部工具栏 ----
        self.toolbar = QHBoxLayout()
        self.toolbar.setSpacing(8)

        # 过滤下拉框
        self.filter_combo = ComboBox(self)
        self.filter_combo.addItems(["已完成", "已归档"])
        self.filter_combo.setCurrentIndex(0)
        self.filter_combo.setFixedWidth(100)
        self.filter_combo.currentIndexChanged.connect(
            lambda idx: self.filter_changed.emit("done" if idx == 0 else "archived")
        )
        self.filter_combo.setVisible(False)
        self.toolbar.addWidget(self.filter_combo)

        self.time_filter_combo = ComboBox(self)
        self.time_filter_combo.addItems(["全部", "本周", "本月", "上周", "上月", "本年", "自定义"])
        self.time_filter_combo.setCurrentIndex(0)
        self.time_filter_combo.setFixedWidth(90)
        self.time_filter_combo.currentIndexChanged.connect(self._on_time_filter_index_changed)
        self.time_filter_combo.setVisible(False)
        self.toolbar.addWidget(self.time_filter_combo)

        self.date_range_btn = DateRangeButton(self, placeholder="日期范围")
        self.date_range_btn.setFixedHeight(33)
        self.date_range_btn.setMinimumWidth(120)
        self.date_range_btn.date_changed.connect(self._on_custom_date_changed)
        self.date_range_btn.setVisible(False)
        self.toolbar.addWidget(self.date_range_btn)

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

        self.week_view = WeekView(self)
        self.week_view.filter_changed.connect(self._on_filter_changed)
        self.week_view.setVisible(settings.show_week_view)
        self.main_layout.addWidget(self.week_view)

        self.stats_label = CaptionLabel("")
        self.stats_label.setContentsMargins(0, 0, 0, 4)
        self.main_layout.addWidget(self.stats_label)

        # ---- 滚动区域 ----
        self.scroll_area = SmoothScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("""
            SmoothScrollArea {
                border: none;
                background: transparent;
            }
        """)

        self.scroll_widget = QWidget(self.scroll_area)
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
        self.empty_widget = QWidget(self)
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
        self.setStyleSheet(tooltip_style())

    def set_todos(self, todos: list[dict], recurring_instances: list[dict] = None,
                  total_count: int = -1, stats: dict = None):
        """设置待办列表数据"""
        self._all_todos = todos
        self._stats = stats
        self.week_view.set_todos(todos)

        if self._filter_date:
            self._todos = self._filter_todos_by_date(todos, self._filter_date)
            self._total_count = len(self._todos)
            self._groups = None
        else:
            self._todos = todos
            if self._view_name == "最近待办":
                self._groups = self._categorize_for_recent(self._todos)
            elif self._view_name == "重要任务":
                self._groups = self._categorize_for_important(self._todos)
            else:
                self._groups = None

            if self._groups is not None:
                self._total_count = sum(len(g["todos"]) for g in self._groups)
                self._expanded_groups.clear()
            else:
                self._total_count = total_count if total_count >= 0 else len(self._todos)

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
            self._todos = self._all_todos
            if self._view_name == "最近待办":
                self._groups = self._categorize_for_recent(self._todos)
            elif self._view_name == "重要任务":
                self._groups = self._categorize_for_important(self._todos)
            else:
                self._groups = None

            if self._groups is not None:
                self._total_count = sum(len(g["todos"]) for g in self._groups)
                self._expanded_groups.clear()
            else:
                self._total_count = len(self._todos)

        # 重置到第一页
        self._current_page = 0
        self._update_pager()
        self._refresh_list()

    def _update_pager(self):
        """更新分页器状态"""
        if self._groups is not None:
            self.pager.setVisible(False)
            return
        total = self._total_count
        total_pages = (total + self._page_size - 1) // self._page_size if total > 0 else 1

        if total_pages <= 1:
            self.pager.setVisible(False)
        else:
            self.pager.setVisible(True)
            self.pager.blockSignals(True)
            if self.pager.count() != total_pages:
                self.pager.setPageNumber(total_pages)
            # 调整当前页
            if self._current_page >= total_pages:
                self._current_page = total_pages - 1
            self.pager.setCurrentIndex(self._current_page)
            self.pager.blockSignals(False)

    def _on_page_changed(self, index: int):
        """分页器页码变化，通知外部重新加载数据"""
        self._current_page = index
        self.page_changed.emit(index, self._page_size)

    @staticmethod
    def _dedup_recurrence(todos: list[dict]) -> list[dict]:
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
        from services.todo_service import TodoService
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
            # 周期任务按生效状态分组
            task_type = todo.get("task_type", "default")
            if task_type == "periodic":
                periodic_status = TodoService.get_periodic_status(todo)
                if periodic_status == "not_started":
                    groups[2]["todos"].append(todo)  # 后续任务
                elif periodic_status == "expired":
                    groups[0]["todos"].append(todo)  # 超期未完成
                else:
                    groups[1]["todos"].append(todo)  # 今日任务（进行中）
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

    @staticmethod
    def _categorize_for_important(todos: list[dict]) -> list[dict]:
        """按优先级分组"""
        groups = []
        for prio_val, prio_name in PRIORITY_MAP.items():
            if prio_val == 0:
                continue
            groups.append({
                "key": f"priority_{prio_val}",
                "title": prio_name,
                "color": PRIORITY_GROUP_COLORS.get(prio_val, "#888"),
                "todos": [],
            })
        for todo in todos:
            priority = todo.get("priority", 0)
            for group in groups:
                if group["key"] == f"priority_{priority}":
                    group["todos"].append(todo)
                    break
        return groups

    def _filter_todos_by_date(self, todos: list[dict], target_date: date_type) -> list[dict]:
        """根据截止日期过滤任务，周期任务按生效期匹配"""
        from services.todo_service import TodoService
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

            task_type = todo.get("task_type", "default")
            parent_match = False
            if task_type == "periodic":
                # 周期任务
                periodic_status = TodoService.get_periodic_status(todo)
                start_str = todo.get("start_date")
                due_str = todo.get("due_date")
                if start_str and due_str:
                    try:
                        start_date = date_type.fromisoformat(start_str)
                        due_date = date_type.fromisoformat(due_str)
                        if start_date <= target_date <= due_date:
                            parent_match = True
                    except (ValueError, TypeError):
                        pass
            else:
                due_date = todo.get("due_date")
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
        """刷新列表显示"""
        if self._groups is not None:
            self._full_rebuild()
            return

        page_todos = self._todos

        # 快速路径：如果 ID 序列完全一致，就地更新卡片数据
        new_ids = self._flat_id_list(page_todos)
        old_ids = [c.todo_id for c in self._cards]
        if new_ids and new_ids == old_ids:
            data_map = {}
            for t in page_todos:
                data_map[t["id"]] = t
                for ch in t.get("children", []):
                    data_map[ch["id"]] = ch
            for card in self._cards:
                d = data_map.get(card.todo_id)
                if d:
                    card.update_data(d)
            self._update_stats()
            return

        # 慢速路径：全量重建
        self._full_rebuild()

    @staticmethod
    def _flat_id_list(todos: list[dict]) -> list[int]:
        """提取父+子任务的 ID 平铺序列"""
        ids = []
        for t in todos:
            ids.append(t["id"])
            for ch in t.get("children", []):
                ids.append(ch["id"])
        return ids

    def _full_rebuild(self):
        """全量销毁重建列表"""
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._cards.clear()

        if self._groups is not None:
            self._refresh_grouped_list()
            return

        page_todos = self._todos

        self.stats_label.setVisible(True)

        has_todos = len(page_todos) > 0
        self.scroll_area.setVisible(has_todos)
        self.empty_widget.setVisible(not has_todos)

        parent_ids = [t["id"] for t in page_todos]

        for todo_data in page_todos:
            card = TodoCard(todo_data, readonly=self._readonly)
            card.edit_clicked.connect(self.edit_clicked.emit)
            card.delete_clicked.connect(self.delete_clicked.emit)
            card.toggle_done.connect(self.toggle_done.emit)
            card.add_subtask_clicked.connect(self.add_subtask_clicked.emit)
            card.card_clicked.connect(self.card_clicked.emit)
            card.archive_clicked.connect(self.archive_clicked.emit)
            card.reorder_requested.connect(
                lambda from_id, to_id, after, order=parent_ids: self.reorder_requested.emit(from_id, to_id, after,
                                                                                            order)
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
        self._update_stats()

    def _update_stats(self):
        """更新底部统计标签"""
        parent_count = self._total_count
        child_count = sum(len(t.get("children", [])) for t in self._todos)
        total_count = parent_count + child_count

        if self._filter_date and self._view_name != "今日任务":
            self.stats_label.setText(
                f"筛选: {self._filter_date.month}月{self._filter_date.day}日 · 共{total_count}个任务")
        elif self._view_name == "今日任务":
            from datetime import date as _date
            if self._filter_date and self._filter_date != _date.today():
                self.stats_label.setText(
                    f"筛选: {self._filter_date.month}月{self._filter_date.day}日 · 共{total_count}个任务")
            else:
                all_count = parent_count
                if self._stats and "done_count" in self._stats:
                    done_count = self._stats["done_count"]
                else:
                    done_count = sum(1 for t in self._todos if t.get("_is_done", False))
                self.stats_label.setText(f"今日任务{all_count} · 已完成{done_count}")
        elif self._view_name == "全部任务":
            if self._stats and "all_count" in self._stats:
                all_count = self._stats["all_count"]
                done_count = self._stats.get("done_count", 0)
                overdue_count = self._stats.get("overdue_count", 0)
            else:
                all_count = parent_count
                from datetime import date
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
                            except (ValueError, TypeError):
                                pass
            self.stats_label.setText(f"全部任务{all_count} · 已完成{done_count} · 已超期{overdue_count}")
        else:
            self.stats_label.setText(f"共{total_count}个任务")

    def _refresh_grouped_list(self):
        """刷新分组列表显示"""
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
            title_color = palette().TITLE if isDarkTheme() else palette().BODY_LIGHT
            title.setStyleSheet(f"font-weight: bold; font-size: {FontSize.BODY}px; color: {title_color};")
            h_layout.addWidget(title)

            count = CaptionLabel(str(len(group["todos"])))
            count_color = palette().DISABLED if isDarkTheme() else palette().MUTED_LIGHT
            count.setStyleSheet(f"color: {count_color};")
            h_layout.addWidget(count)

            h_layout.addStretch()
            self.list_layout.addWidget(header)

            group_key = group["key"]
            is_expanded = group_key in self._expanded_groups
            limit = self._group_display_limit
            total_in_group = len(group["todos"])
            display_todos = group["todos"] if is_expanded or total_in_group <= limit else group["todos"][:limit]

            for todo_data in display_todos:
                card = TodoCard(todo_data, readonly=self._readonly)
                card.edit_clicked.connect(self.edit_clicked.emit)
                card.delete_clicked.connect(self.delete_clicked.emit)
                card.toggle_done.connect(self.toggle_done.emit)
                card.add_subtask_clicked.connect(self.add_subtask_clicked.emit)
                card.card_clicked.connect(self.card_clicked.emit)
                card.archive_clicked.connect(self.archive_clicked.emit)
                card.reorder_requested.connect(
                    lambda from_id, to_id, after, order=parent_ids: self.reorder_requested.emit(from_id, to_id, after,
                                                                                                order)
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

            if total_in_group > limit:
                toggle_btn = QPushButton()
                toggle_btn.setCursor(Qt.PointingHandCursor)
                toggle_btn.setFixedHeight(32)
                remaining = total_in_group - limit
                if is_expanded:
                    toggle_btn.setText(f"收起")
                    toggle_btn.clicked.connect(lambda _, k=group_key: self._toggle_group(k, False))
                else:
                    toggle_btn.setText(f"查看更多（剩余 {remaining} 条）")
                    toggle_btn.clicked.connect(lambda _, k=group_key: self._toggle_group(k, True))
                btn_color = palette().MUTED if isDarkTheme() else "#666"
                btn_hover = palette().DISABLED if isDarkTheme() else "#444"
                toggle_btn.setStyleSheet(
                    f"QPushButton {{ color: {btn_color}; background: transparent; border: none;"
                    f" font-size: {FontSize.SMALL}px; }}"
                    f"QPushButton:hover {{ color: {btn_hover}; }}"
                )
                self.list_layout.addWidget(toggle_btn, alignment=Qt.AlignCenter)

        self.list_layout.addStretch()

        self.stats_label.setVisible(False)

    def _toggle_group(self, group_key: str, expand: bool):
        if expand:
            self._expanded_groups.add(group_key)
        else:
            self._expanded_groups.discard(group_key)
        self._full_rebuild()

    def update_single_todo(self, todo_data: dict):
        """更新单个卡片"""
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
        """展示加载态"""
        for card in self._cards:
            card.deleteLater()
        self._cards.clear()
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def set_show_week_view(self, show: bool):
        self.week_view.setVisible(show)
        if not show:
            self.week_view.clear_selection()

    def _on_time_filter_index_changed(self, idx: int):
        keys = ["all", "week", "last_week", "month", "last_month", "year", "custom"]
        if 0 <= idx < len(keys):
            self._time_filter = keys[idx]
            self.date_range_btn.setVisible(self._time_filter == "custom")
            if self._time_filter == "custom":
                # 如果还没有设置自定义日期，不立即触发过滤
                return
            self.time_filter_changed.emit(self._time_filter)

    def set_time_filter_visible(self, visible: bool):
        self.time_filter_combo.setVisible(visible)
        if visible and self._time_filter == "custom":
            self.date_range_btn.setVisible(True)
        else:
            self.date_range_btn.setVisible(False)

    def current_time_filter(self) -> str:
        return self._time_filter

    def get_custom_date_range(self) -> tuple:
        """返回自定义日期范围 """
        return self._custom_due_start, self._custom_due_end

    def _on_custom_date_changed(self):
        """自定义日期范围变化时触发过滤"""
        start = self.date_range_btn.get_start_date()
        end = self.date_range_btn.get_due_date()
        self._custom_due_start = start
        self._custom_due_end = end
        self.time_filter_changed.emit(self._time_filter)

    def reset_time_filter(self):
        self._time_filter = "all"
        self._custom_due_start = None
        self._custom_due_end = None
        self.time_filter_combo.blockSignals(True)
        self.time_filter_combo.setCurrentIndex(0)
        self.time_filter_combo.blockSignals(False)
        self.date_range_btn.setVisible(False)
        self.date_range_btn.clear_dates()
