"""日程视图"""
from __future__ import annotations
from datetime import date, timedelta
from calendar import monthrange

from services.recurrence_utils import matches_recurrence

from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QFrame, QSizePolicy
)
from PySide6.QtGui import QColor, QPainter, QPainterPath

from qfluentwidgets import (
    BodyLabel, CaptionLabel, ToolButton, FluentIcon, StrongBodyLabel, SubtitleLabel,
    TransparentToolButton
)

from config.settings import settings
from config.theme_config import FontSize, palette, theme_colors, tooltip_style, is_dark


class WeekView(QWidget):
    """周视图组件"""

    filter_changed = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._todos: list[dict] = []
        self._pending_dates: set[date] = set()
        self._selected_date: date | None = None
        self._week_offset: int = 0
        self._setup_ui()

    def _setup_ui(self):
        c = palette()

        self.setStyleSheet(f"""
            WeekView {{
                background-color: transparent;
            }}
        """)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(4)

        # 导航行
        nav_layout = QHBoxLayout()
        nav_layout.setSpacing(4)
        nav_layout.setContentsMargins(0, 0, 0, 0)

        # 上一周按钮
        self.prev_week_btn = ToolButton(FluentIcon.LEFT_ARROW)
        self.prev_week_btn.setFixedSize(24, 56)
        self.prev_week_btn.setIconSize(QSize(12, 12))
        self.prev_week_btn.setToolTip("上一周")
        self.prev_week_btn.clicked.connect(self._prev_week)
        nav_layout.addWidget(self.prev_week_btn)

        # 日期显示区域
        self.days_layout = QHBoxLayout()
        self.days_layout.setSpacing(4)
        self.days_layout.setContentsMargins(0, 0, 0, 0)

        self._day_widgets: list[dict] = []
        for i in range(7):
            day_widget = self._create_day_widget(i)
            self.days_layout.addWidget(day_widget["frame"])
            self._day_widgets.append(day_widget)

        nav_layout.addLayout(self.days_layout)

        # 下一周按钮
        self.next_week_btn = ToolButton(FluentIcon.RIGHT_ARROW)
        self.next_week_btn.setFixedSize(24, 56)
        self.next_week_btn.setIconSize(QSize(12, 12))
        self.next_week_btn.setToolTip("下一周")
        self.next_week_btn.clicked.connect(self._next_week)
        nav_layout.addWidget(self.next_week_btn)

        self.main_layout.addLayout(nav_layout)

        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setStyleSheet(f"""
            QFrame {{
                background-color: {c.DIVIDER_FALLBACK};
                border: none;
                max-height: 1px;
            }}
        """)
        self.main_layout.addWidget(separator)

        self._update_week_display()

    def _prev_week(self):
        """显示上一周（最多往前两周）"""
        if self._week_offset <= -2:
            return
        self._week_offset -= 1
        self._update_week_display()
        self._update_pending_dates()
        self.filter_changed.emit(self._selected_date)

    def _next_week(self):
        """显示下一周（最多往后两周）"""
        if self._week_offset >= 2:
            return
        self._week_offset += 1
        self._update_week_display()
        self._update_pending_dates()
        self.filter_changed.emit(self._selected_date)

    def _create_day_widget(self, index: int) -> dict:
        c = palette()

        frame = QFrame()
        frame.setObjectName("dayFrame")
        frame.setCursor(Qt.PointingHandCursor)
        frame.setFixedHeight(56)
        frame.mousePressEvent = lambda e, idx=index: self._on_day_clicked(idx)

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(4, 6, 4, 6)
        layout.setSpacing(2)
        layout.setAlignment(Qt.AlignCenter)

        weekday_label = CaptionLabel()
        weekday_label.setAlignment(Qt.AlignCenter)
        weekday_label.setStyleSheet(f"""
            color: {c.BLOCKQUOTE};
            font-size: {FontSize.TINY}px;
        """)
        layout.addWidget(weekday_label)

        day_label = BodyLabel()
        day_label.setAlignment(Qt.AlignCenter)
        day_label.setStyleSheet(f"""
            color: {c.BODY_LIGHT};
            font-size: {FontSize.MEDIUM}px;
            font-weight: 600;
        """)
        layout.addWidget(day_label)

        weekdays = ["一", "二", "三", "四", "五", "六", "日"]
        weekday_label.setText(weekdays[index])

        return {
            "frame": frame,
            "weekday_label": weekday_label,
            "day_label": day_label,
            "date": None
        }

    def _on_day_clicked(self, index: int):
        day_widget = self._day_widgets[index]
        clicked_date = day_widget["date"]

        if self._selected_date == clicked_date:
            self._selected_date = None
        else:
            self._selected_date = clicked_date

        self._update_week_display()
        self.filter_changed.emit(self._selected_date)

    def _update_week_display(self):
        c = theme_colors()
        today = date.today()

        weekday = today.weekday()
        # 计算当前显示周的起始日期
        days_offset = self._week_offset * 7
        start_of_week = today - timedelta(days=weekday) + timedelta(days=days_offset)

        for i, day_widget in enumerate(self._day_widgets):
            current_date = start_of_week + timedelta(days=i)
            day_widget["date"] = current_date
            day_widget["day_label"].setText(f"{current_date.month}/{current_date.day}")

            is_selected = current_date == self._selected_date
            has_pending = current_date in self._pending_dates

            if is_selected:
                day_widget["frame"].setStyleSheet(f"""
                    QFrame#dayFrame {{
                        background-color: {c['drop_bg']};
                        border: 2px solid {c['accent']};
                        border-radius: 8px;
                    }}
                    QFrame#dayFrame:hover {{
                        background-color: {c['option_selected_bg']};
                    }}
                """)
                day_widget["day_label"].setStyleSheet(f"""
                    color: {c['accent']};
                    font-size: {FontSize.MEDIUM}px;
                    font-weight: bold;
                """)
            elif has_pending:
                # 待办高亮使用警告色，主题感知
                if is_dark():
                    bg_color = "rgba(255, 152, 0, 0.12)"
                    border_color = "rgba(255, 152, 0, 0.3)"
                    hover_bg = "rgba(255, 152, 0, 0.18)"
                    day_color = "#FFD54F"
                else:
                    bg_color = "rgba(255, 152, 0, 0.08)"
                    border_color = "rgba(255, 152, 0, 0.25)"
                    hover_bg = "rgba(255, 152, 0, 0.12)"
                    day_color = "#F9A825"
                day_widget["frame"].setStyleSheet(f"""
                    QFrame#dayFrame {{
                        background-color: {bg_color};
                        border: 1px solid {border_color};
                        border-radius: 8px;
                    }}
                    QFrame#dayFrame:hover {{
                        background-color: {hover_bg};
                    }}
                """)
                day_widget["day_label"].setStyleSheet(f"""
                    color: {day_color};
                    font-size: {FontSize.MEDIUM}px;
                    font-weight: 600;
                """)
            else:
                day_widget["frame"].setStyleSheet(f"""
                    QFrame#dayFrame {{
                        background-color: {c['cell_bg']};
                        border: 1px solid {c['cell_border']};
                        border-radius: 8px;
                    }}
                    QFrame#dayFrame:hover {{
                        background-color: {c['hover']};
                    }}
                """)
                day_widget["day_label"].setStyleSheet(f"""
                    color: {c['text']};
                    font-size: {FontSize.MEDIUM}px;
                    font-weight: 600;
                """)

    def set_todos(self, todos: list[dict]):
        self._todos = todos
        self._calculate_pending_dates()
        self._update_week_display()

    def _calculate_pending_dates(self):
        self._pending_dates = set()

        today = date.today()
        # 从周一开始计算
        week_start = today - timedelta(days=today.weekday()) - timedelta(weeks=2)
        week_end = week_start + timedelta(weeks=5) - timedelta(days=1)

        instance_limit = today + timedelta(days=14)

        for todo in self._todos:
            if todo.get("is_recurrence_template"):
                continue
            if not todo.get("recurrence_type") and todo.get("status") == 1:
                continue
            if todo.get("_is_archived", False):
                continue

            task_type = todo.get("task_type", "default")
            if task_type == "periodic":
                # 周期任务：[start_date, due_date] 范围内的每一天都标记
                start_str = todo.get("start_date")
                due_str = todo.get("due_date")
                if start_str and due_str:
                    try:
                        start_d = date.fromisoformat(start_str)
                        due_d = date.fromisoformat(due_str)
                        # 只标记在可见周范围内的日期
                        current = max(start_d, week_start)
                        end = min(due_d, week_end)
                        while current <= end:
                            self._pending_dates.add(current)
                            current += timedelta(days=1)
                    except (ValueError, TypeError):
                        pass
                continue

            due_date_str = todo.get("due_date")
            if due_date_str:
                try:
                    task_date = date.fromisoformat(due_date_str)
                    self._pending_dates.add(task_date)
                except (ValueError, TypeError):
                    pass

            for child in todo.get("children", []):
                if child.get("_is_done", False):
                    continue
                child_due = child.get("due_date")
                if child_due:
                    try:
                        child_date = date.fromisoformat(child_due)
                        self._pending_dates.add(child_date)
                    except (ValueError, TypeError):
                        pass

    def _update_pending_dates(self):
        """更新待办日期显示"""
        self._calculate_pending_dates()
        self._update_week_display()

    def refresh_theme(self):
        self._update_week_display()

    def clear_selection(self):
        self._selected_date = None
        self._update_week_display()
        self.filter_changed.emit(None)

    def set_selected_date(self, target_date: date):
        """从外部设置选中日期"""
        self._selected_date = target_date
        self._week_offset = 0
        self._update_week_display()


class CalendarDialog(QDialog):
    """日程视图弹窗"""

    def __init__(self, todos: list[dict], parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMinimumSize(680, 400)
        self.setMaximumSize(1200, 900)
        self.resize(760, 520)

        self._current_date = date.today()
        self._todos = todos
        self._holidays: dict[str, dict] = {}  # key: "2026-01-01", value: {"name": ..., "isOffDay": ...}
        self._load_holidays()
        self._setup_ui()
        self.refresh_calendar()
        # 根据内容调整窗口大小
        self.adjustSize()

        # 窗口拖动相关
        self._drag_pos = None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and self._drag_pos is not None:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        """鼠标释放清除位置"""
        self._drag_pos = None

    def paintEvent(self, event):
        c = palette()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        bg_color = QColor(c.BG)
        border_color = QColor(c.INPUT_BORDER) if is_dark() else QColor(210, 210, 210)
        path = QPainterPath()
        path.addRoundedRect(0.5, 0.5, self.width() - 1, self.height() - 1, 10, 10)
        painter.fillPath(path, bg_color)
        painter.setPen(border_color)
        painter.drawPath(path)
        super().paintEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
        screen = self.screen().availableGeometry()
        x = screen.x() + (screen.width() - self.width()) // 2
        y = screen.y() + (screen.height() - self.height()) // 2
        self.move(x, y)

    def _setup_ui(self):
        """构建 UI"""
        c = palette()
        tc = tooltip_style(FontSize.SMALL)

        self.setStyleSheet(f"""
            QDialog {{
                background-color: transparent;
            }}
            {tc}
        """)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(24, 12, 24, 20)
        self.main_layout.setSpacing(12)

        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)

        title_label = SubtitleLabel("日程视图")
        title_label.setStyleSheet(f"font-weight: bold; color: {c.TITLE};")
        top_bar.addWidget(title_label, 1)

        close_btn = TransparentToolButton(FluentIcon.CLOSE)
        close_btn.setFixedSize(28, 28)
        close_btn.clicked.connect(self.reject)
        top_bar.addWidget(close_btn)

        self.main_layout.addLayout(top_bar)

        # 导航栏
        nav_layout = QHBoxLayout()
        nav_layout.setSpacing(8)

        nav_layout.addStretch()
        self.main_layout.addLayout(nav_layout)

        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setStyleSheet(f"""
            QFrame {{
                background-color: {c.BORDER_STRONG};
                border: none;
                max-height: 1px;
            }}
        """)
        self.main_layout.addWidget(separator)

        self.toolbar = QHBoxLayout()
        self.toolbar.setSpacing(12)

        self.toolbar.addStretch()

        self.prev_btn = ToolButton(FluentIcon.LEFT_ARROW)
        self.prev_btn.setFixedSize(32, 32)
        self.prev_btn.clicked.connect(self._prev_month)
        self.toolbar.addWidget(self.prev_btn)

        self.month_label = StrongBodyLabel()
        self.month_label.setStyleSheet(f"""
            font-size: {FontSize.LARGE}px;
            font-weight: 600;
            color: {c.TITLE};
            min-width: 120px;
        """)
        self.month_label.setAlignment(Qt.AlignCenter)
        self.toolbar.addWidget(self.month_label)

        self.next_btn = ToolButton(FluentIcon.RIGHT_ARROW)
        self.next_btn.setFixedSize(32, 32)
        self.next_btn.clicked.connect(self._next_month)
        self.toolbar.addWidget(self.next_btn)

        self.today_btn = ToolButton(FluentIcon.CALENDAR)
        self.today_btn.setFixedSize(32, 32)
        self.today_btn.setToolTip("回到今天")
        self.today_btn.clicked.connect(self._go_to_today)
        self.toolbar.addWidget(self.today_btn)

        self.toolbar.addStretch()

        self.main_layout.addLayout(self.toolbar)

        self.week_header = QHBoxLayout()
        self.week_header.setSpacing(4)
        weekdays = ["一", "二", "三", "四", "五", "六", "日"]

        for i, wd in enumerate(weekdays):
            label = CaptionLabel(wd)
            label.setAlignment(Qt.AlignCenter)
            label.setFixedHeight(28)
            is_weekend = i == 5 or i == 6  # 周六、周日
            if is_dark():
                color = "#ffeb6b" if is_weekend else c.MUTED
            else:
                color = "#e59935" if is_weekend else c.BLOCKQUOTE
            label.setStyleSheet(f"""
                color: {color};
                font-size: {FontSize.BODY}px;
                font-weight: {'bold' if is_weekend else 'normal'};
            """)
            self.week_header.addWidget(label)
        self.main_layout.addLayout(self.week_header)

        self.calendar_grid = QGridLayout()
        self.calendar_grid.setSpacing(4)
        self.calendar_grid.setContentsMargins(0, 0, 0, 0)

        for row in range(6):
            for col in range(7):
                cell = self._create_day_cell()
                self.calendar_grid.addWidget(cell, row, col)

        self.main_layout.addLayout(self.calendar_grid, 1)

        self._update_month_label()

    def _create_day_cell(self) -> QFrame:
        """创建日期单元格"""
        cell = QFrame()
        cell.setObjectName("dayCell")
        cell.setMinimumHeight(72)
        cell.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.MinimumExpanding)
        cell.setCursor(Qt.PointingHandCursor)

        layout = QVBoxLayout(cell)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(2)

        # 日期行：日期数字 + 节假日角标
        day_row = QHBoxLayout()
        day_row.setContentsMargins(0, 0, 0, 0)
        day_row.setSpacing(2)

        day_label = CaptionLabel()
        day_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        day_label.setStyleSheet("font-weight: 500;")
        day_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        day_row.addWidget(day_label)

        # 节假日/调休角标（休/班），默认隐藏
        holiday_badge = CaptionLabel()
        holiday_badge.setAlignment(Qt.AlignCenter)
        holiday_badge.setFixedSize(16, 16)
        holiday_badge.hide()
        day_row.addWidget(holiday_badge)

        day_row.addStretch()
        layout.addLayout(day_row)

        tasks_widget = QWidget()
        tasks_layout = QVBoxLayout(tasks_widget)
        tasks_layout.setContentsMargins(0, 0, 0, 0)
        tasks_layout.setSpacing(1)
        layout.addWidget(tasks_widget, 1)

        cell.day_label = day_label
        cell.holiday_badge = holiday_badge
        cell.tasks_widget = tasks_widget
        cell.tasks_layout = tasks_layout
        cell.setProperty("date", None)
        cell.setProperty("is_today", False)

        return cell

    def _update_month_label(self):
        """更新月份标签"""
        self.month_label.setText(self._current_date.strftime("%Y年%m月"))

    def _prev_month(self):
        """上一个月"""
        year = self._current_date.year
        month = self._current_date.month
        if month == 1:
            year -= 1
            month = 12
        else:
            month -= 1
        self._current_date = date(year, month, 1)
        self._load_holidays()
        self._update_month_label()
        self.refresh_calendar()

    def _next_month(self):
        """下一个月"""
        year = self._current_date.year
        month = self._current_date.month
        if month == 12:
            year += 1
            month = 1
        else:
            month += 1
        self._current_date = date(year, month, 1)
        self._load_holidays()
        self._update_month_label()
        self.refresh_calendar()

    def _go_to_today(self):
        """回到今天"""
        self._current_date = date.today()
        self._update_month_label()
        self.refresh_calendar()

    def _load_holidays(self):
        """加载节日数据"""
        if settings.holiday_source == "none":
            return
        from services.holiday_service import holiday_service
        # 加载当前月和前后月可能涉及的年份
        year = self._current_date.year
        holiday_service.load_year(year)
        # 如果当前是1月或12月，可能需要加载相邻年份
        if self._current_date.month == 1:
            holiday_service.load_year(year - 1)
        elif self._current_date.month == 12:
            holiday_service.load_year(year + 1)
        self._holidays = holiday_service._data

    def refresh_calendar(self):
        """刷新日历显示"""
        year = self._current_date.year
        month = self._current_date.month

        first_day = date(year, month, 1)
        _, days_in_month = monthrange(year, month)

        start_weekday = first_day.weekday()

        # 构建 42 个单元格对应的日期列表，包含上月填充和下月填充
        calendar_dates = []
        # 上月填充
        for i in range(start_weekday):
            calendar_dates.append(first_day - timedelta(days=start_weekday - i))
        # 当月日期
        for day in range(1, days_in_month + 1):
            calendar_dates.append(date(year, month, day))
        # 下月填充
        while len(calendar_dates) < 42:
            calendar_dates.append(calendar_dates[-1] + timedelta(days=1))

        today = date.today()

        for row in range(6):
            for col in range(7):
                idx = row * 7 + col
                cell = self.calendar_grid.itemAtPosition(row, col).widget()

                while cell.tasks_layout.count():
                    item = cell.tasks_layout.takeAt(0)
                    if item.widget():
                        item.widget().deleteLater()

                cell_date = calendar_dates[idx]
                is_current_month = cell_date.month == month and cell_date.year == year
                cell.setProperty("date", cell_date)

                is_today = (cell_date == today)
                cell.setProperty("is_today", is_today)

                # 获取节日信息
                holiday = self._holidays.get(cell_date.isoformat()) if self._holidays else None

                if is_current_month:
                    day_label_style = self._get_day_label_style(is_today, col, holiday)
                else:
                    day_label_style = self._get_day_label_style_dim(col)
                cell.day_label.setStyleSheet(day_label_style)
                cell.day_label.setText(str(cell_date.day))

                # 节假日/调休角标
                if holiday and is_current_month:
                    is_off = holiday.get("isOffDay", True)
                    badge_text = "休" if is_off else "班"
                    cell.holiday_badge.setText(badge_text)
                    cell.holiday_badge.setStyleSheet(self._get_holiday_badge_style(is_off))
                    cell.holiday_badge.show()
                else:
                    cell.holiday_badge.hide()

                # 显示节日名称
                if holiday and is_current_month:
                    holiday_label = CaptionLabel(holiday["name"])
                    holiday_label.setStyleSheet(self._get_holiday_label_style(holiday))
                    cell.tasks_layout.addWidget(holiday_label)

                day_tasks = self._get_tasks_for_date(cell_date)
                max_tasks = 3 if holiday else 4

                for task in day_tasks[:max_tasks]:
                    title = task["title"]
                    if task.get("_is_virtual"):
                        title = "🔁 " + title
                    display = title[:8] + ".." if len(title) > 8 else title
                    task_label = QLabel(display)
                    task_label.setStyleSheet(self._get_task_style(task))
                    task_label.setToolTip(task["title"])
                    cell.tasks_layout.addWidget(task_label)

                if len(day_tasks) > max_tasks:
                    more_label = CaptionLabel(f"+{len(day_tasks) - max_tasks}")
                    more_label.setStyleSheet(self._get_more_style())
                    cell.tasks_layout.addWidget(more_label)

                if is_current_month:
                    cell.setStyleSheet(self._get_cell_style(is_today, len(day_tasks) > 0, col, holiday))
                else:
                    cell.setStyleSheet(self._get_cell_style_dim(col))

    def _get_tasks_for_date(self, target_date: date) -> list[dict]:
        """获取指定日期的任务"""
        tasks = []
        today = date.today()
        instance_limit = today + timedelta(days=14)

        for todo in self._todos:
            if todo.get("is_recurrence_template"):
                continue
            task_type = todo.get("task_type", "default")
            if task_type == "periodic":
                # 周期任务：目标日期在生效期内即匹配
                start_str = todo.get("start_date")
                due_str = todo.get("due_date")
                if start_str and due_str:
                    try:
                        start_d = date.fromisoformat(start_str)
                        due_d = date.fromisoformat(due_str)
                        if start_d <= target_date <= due_d:
                            tasks.append(todo)
                    except (ValueError, TypeError):
                        pass
                continue
            due_date_str = todo.get("due_date")
            if due_date_str:
                try:
                    task_date = date.fromisoformat(due_date_str)
                    if task_date == target_date:
                        tasks.append(todo)
                except (ValueError, TypeError):
                    pass
            for child in todo.get("children", []):
                child_due = child.get("due_date")
                if child_due:
                    try:
                        child_date = date.fromisoformat(child_due)
                        if child_date == target_date:
                            tasks.append(child)
                    except (ValueError, TypeError):
                        pass

        if target_date > instance_limit:
            for todo in self._todos:
                if not todo.get("is_recurrence_template"):
                    continue
                due_str = todo.get("due_date")
                if not due_str:
                    continue
                try:
                    tpl_date = date.fromisoformat(due_str)
                    recurrence_type = todo.get("recurrence_type")
                    if not recurrence_type:
                        continue
                    end_str = todo.get("recurrence_end_date")
                    end_date = date.fromisoformat(end_str) if end_str else None
                    interval = todo.get("recurrence_interval", 1)
                    recurrence_day = todo.get("recurrence_day")
                    if matches_recurrence(tpl_date, target_date, recurrence_type, interval, end_date, recurrence_day):
                        virtual = dict(todo)
                        virtual["_virtual_date"] = target_date.isoformat()
                        virtual["_is_virtual"] = True
                        virtual["_is_done"] = False
                        virtual["status"] = 0
                        tasks.append(virtual)
                except (ValueError, TypeError):
                    pass

        return tasks

    def _get_day_label_style(self, is_today: bool, col: int, holiday: dict = None) -> str:
        c = palette()
        is_weekend = col == 5 or col == 6  # 周六、周日

        if is_today:
            return f"""
                QLabel {{
                    color: #FFF;
                    font-size: {FontSize.SMALL}px;
                    font-weight: bold;
                    background-color: {c.ACCENT};
                    border-radius: 10px;
                    padding: 0px 4px;
                    min-height: 20px;
                }}
            """

        # 调休上班日
        if holiday and not holiday.get("isOffDay", True):
            return f"color: {c.DANGER}; font-size: {FontSize.SMALL}px; font-weight: 600;"

        # 节假日
        if holiday and holiday.get("isOffDay", False):
            return f"color: {c.DONE_GREEN}; font-size: {FontSize.SMALL}px; font-weight: 600;"

        if is_dark():
            color = "#E0E0E0"
        else:
            color = c.BODY_LIGHT

        return f"color: {color}; font-size: {FontSize.SMALL}px; font-weight: 500;"

    def _get_day_label_style_dim(self, col: int) -> str:
        """非当月日期的日期标签样式"""
        if is_dark():
            color = "#555"
        else:
            color = "#C0C0C0"
        return f"color: {color}; font-size: {FontSize.SMALL}px; font-weight: 400;"

    def _get_cell_style_dim(self, col: int) -> str:
        """非当月日期的单元格样式"""
        if is_dark():
            bg_color = "rgba(255, 255, 255, 0.01)"
            border_color = "rgba(255, 255, 255, 0.03)"
        else:
            bg_color = "rgba(0, 0, 0, 0.005)"
            border_color = "rgba(0, 0, 0, 0.03)"
        return f"""
            QFrame#dayCell {{
                background-color: {bg_color};
                border: 1px solid {border_color};
                border-radius: 8px;
            }}
        """

    def _get_cell_style(self, is_today: bool, has_tasks: bool, col: int, holiday: dict = None) -> str:
        """获取单元格样式"""
        c = theme_colors()
        is_weekend = col == 5 or col == 6  # 周六、周日
        is_holiday = holiday and holiday.get("isOffDay", False)
        is_workday = holiday and not holiday.get("isOffDay", True)

        if is_dark():
            if is_today:
                bg_color = "rgba(0, 120, 212, 0.15)"
                border_color = "#0078D4"
            elif is_holiday:
                bg_color = "rgba(255, 235, 59, 0.10)"
                border_color = "rgba(255, 235, 59, 0.25)"
            elif is_workday:
                bg_color = "rgba(255, 255, 255, 0.02)"
                border_color = "rgba(255, 255, 255, 0.05)"
            elif is_weekend:
                bg_color = "rgba(255, 235, 59, 0.10)"
                border_color = "rgba(255, 235, 59, 0.25)"
            elif has_tasks:
                bg_color = "rgba(255, 255, 255, 0.05)"
                border_color = "rgba(255, 255, 255, 0.08)"
            else:
                bg_color = "rgba(255, 255, 255, 0.02)"
                border_color = "rgba(255, 255, 255, 0.05)"
            hover_bg = "rgba(255, 255, 255, 0.08)"
            hover_border = "rgba(255, 255, 255, 0.15)"
        else:
            if is_today:
                bg_color = "rgba(0, 120, 212, 0.08)"
                border_color = "#0078D4"
            elif is_holiday:
                bg_color = "rgba(255, 235, 59, 0.12)"
                border_color = "rgba(255, 235, 59, 0.30)"
            elif is_workday:
                bg_color = "rgba(0, 0, 0, 0.01)"
                border_color = "rgba(0, 0, 0, 0.04)"
            elif is_weekend:
                bg_color = "rgba(255, 235, 59, 0.12)"
                border_color = "rgba(255, 235, 59, 0.30)"
            elif has_tasks:
                bg_color = "rgba(0, 0, 0, 0.02)"
                border_color = "rgba(0, 0, 0, 0.06)"
            else:
                bg_color = "rgba(0, 0, 0, 0.01)"
                border_color = "rgba(0, 0, 0, 0.04)"
            hover_bg = "rgba(0, 0, 0, 0.04)"
            hover_border = "rgba(0, 0, 0, 0.12)"

        return f"""
            QFrame#dayCell {{
                background-color: {bg_color};
                border: 1px solid {border_color};
                border-radius: 8px;
            }}
            QFrame#dayCell:hover {{
                background-color: {hover_bg};
                border-color: {hover_border};
            }}
        """

    def _get_task_style(self, task: dict) -> str:
        """获取任务标签样式"""
        c = palette()
        is_done = task.get("_is_done", False)
        color_tag = task.get("color_tag")

        if is_done:
            color = c.MUTED
            decoration = "text-decoration: line-through;"
            bg = "transparent"
        elif color_tag:
            color = color_tag
            decoration = ""
            bg = c.HOVER_BG_STRONG if is_dark() else "rgba(0, 0, 0, 0.05)"
        else:
            priority = task.get("priority", 0)
            if is_dark():
                colors = {0: "#B0BEC5", 1: "#4FC3F7", 2: "#FFB74D", 3: "#EF5350"}
            else:
                colors = {0: "#607D8B", 1: "#0288D1", 2: "#F57C00", 3: "#D32F2F"}
            color = colors.get(priority, colors[0])
            decoration = ""
            bg = c.HOVER_BG_STRONG if is_dark() else "rgba(0, 0, 0, 0.05)"

        return f"""
            QLabel {{
                color: {color};
                font-size: {FontSize.TINY}px;
                {decoration}
                padding: 2px 4px;
                border-radius: 3px;
                background-color: {bg};
            }}
            QToolTip {{
                background-color: {c.TOOLTIP_BG};
                color: {c.BODY_LIGHT};
                border: 1px solid {c.DIVIDER};
                border-radius: 6px;
                padding: 6px 10px;
            }}
        """

    def _get_more_style(self) -> str:
        """获取"更多"标签样式"""
        c = palette()
        return f"""
            color: {c.MUTED};
            font-size: 9px;
            padding: 1px 4px;
        """

    def _get_holiday_label_style(self, holiday: dict) -> str:
        """获取节日标签样式"""
        c = palette()
        is_off = holiday.get("isOffDay", True)
        color = c.DONE_GREEN if is_off else c.DANGER
        return f"""
            color: {color};
            font-size: 9px;
            font-weight: 600;
            padding: 1px 3px;
            border-radius: 2px;
        """

    def _get_holiday_badge_style(self, is_off: bool) -> str:
        """获取节假日/调休角标样式"""
        c = palette()
        if is_off:
            bg = c.DONE_GREEN
        else:
            bg = c.DANGER
        return f"""
            background-color: {bg};
            color: #FFF;
            font-size: 9px;
            font-weight: bold;
            border-radius: 8px;
        """
