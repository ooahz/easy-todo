"""日程视图 - 月历形式展示任务（弹窗模式）"""
from __future__ import annotations
from datetime import date, timedelta
from calendar import monthrange

from services.recurrence_utils import matches_recurrence, generate_occurrences

from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QFrame, QGraphicsDropShadowEffect, QSizePolicy
)
from PySide6.QtGui import QColor

from qfluentwidgets import (
    BodyLabel, CaptionLabel, ToolButton, FluentIcon, isDarkTheme, StrongBodyLabel, IconWidget, SubtitleLabel,
    TransparentToolButton
)


class WeekView(QWidget):
    """周视图组件"""

    filter_changed = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._todos: list[dict] = []
        self._pending_dates: set[date] = set()
        self._selected_date: date | None = None
        self._week_offset: int = 0  # 周偏移量
        self._setup_ui()

    def _setup_ui(self):
        dark = isDarkTheme()
        
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
                background-color: {'rgba(255, 255, 255, 0.08)' if dark else 'rgba(0, 0, 0, 0.06)'};
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
        dark = isDarkTheme()
        
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
        if dark:
            color = "#AAA"
        else:
            color = "#666"
        weekday_label.setStyleSheet(f"""
            color: {color};
            font-size: 10px;
        """)
        layout.addWidget(weekday_label)
        
        day_label = BodyLabel()
        day_label.setAlignment(Qt.AlignCenter)
        day_label.setStyleSheet(f"""
            color: {'#E0E0E0' if dark else '#333'};
            font-size: 14px;
            font-weight: 600;
        """)
        layout.addWidget(day_label)

        weekdays = ["日", "一", "二", "三", "四", "五", "六"]
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
        dark = isDarkTheme()
        today = date.today()

        weekday = today.weekday()
        # 计算当前显示周的起始日期（包含周偏移）
        days_offset = self._week_offset * 7
        start_of_week = today - timedelta(days=(weekday + 1) % 7) + timedelta(days=days_offset)

        for i, day_widget in enumerate(self._day_widgets):
            current_date = start_of_week + timedelta(days=i)
            day_widget["date"] = current_date
            day_widget["day_label"].setText(f"{current_date.month}/{current_date.day}")

            is_selected = current_date == self._selected_date
            has_pending = current_date in self._pending_dates

            if is_selected:
                day_widget["frame"].setStyleSheet(f"""
                    QFrame#dayFrame {{
                        background-color: rgba(0, 120, 212, 0.25);
                        border: 2px solid #0078D4;
                        border-radius: 8px;
                    }}
                    QFrame#dayFrame:hover {{
                        background-color: rgba(0, 120, 212, 0.35);
                    }}
                """)
                day_widget["day_label"].setStyleSheet("""
                    color: #0078D4;
                    font-size: 14px;
                    font-weight: bold;
                """)
            elif has_pending:
                if dark:
                    bg_color = "rgba(255, 152, 0, 0.12)"
                    border_color = "rgba(255, 152, 0, 0.3)"
                else:
                    bg_color = "rgba(255, 152, 0, 0.08)"
                    border_color = "rgba(255, 152, 0, 0.25)"
                day_widget["frame"].setStyleSheet(f"""
                    QFrame#dayFrame {{
                        background-color: {bg_color};
                        border: 1px solid {border_color};
                        border-radius: 8px;
                    }}
                    QFrame#dayFrame:hover {{
                        background-color: {'rgba(255, 152, 0, 0.18)' if dark else 'rgba(255, 152, 0, 0.12)'};
                    }}
                """)
                day_widget["day_label"].setStyleSheet(f"""
                    color: {'#FFD54F' if dark else '#F9A825'};
                    font-size: 14px;
                    font-weight: 600;
                """)
            else:
                if dark:
                    bg_color = "rgba(255, 255, 255, 0.03)"
                    border_color = "rgba(255, 255, 255, 0.06)"
                    hover_bg = "rgba(255, 255, 255, 0.06)"
                    color = "#E0E0E0"
                else:
                    bg_color = "rgba(0, 0, 0, 0.02)"
                    border_color = "rgba(0, 0, 0, 0.04)"
                    hover_bg = "rgba(0, 0, 0, 0.04)"
                    color = "#333"
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
                    color: {color};
                    font-size: 14px;
                    font-weight: 600;
                """)

    def set_todos(self, todos: list[dict]):
        self._todos = todos
        self._calculate_pending_dates()
        self._update_week_display()

    def _calculate_pending_dates(self):
        self._pending_dates = set()

        today = date.today()
        week_start = today - timedelta(days=(today.weekday() + 1) % 7) - timedelta(weeks=2)
        week_end = week_start + timedelta(weeks=5) - timedelta(days=1)

        for todo in self._todos:
            if todo.get("status") == 1:
                continue

            due_date_str = todo.get("due_date")
            if due_date_str:
                try:
                    task_date = date.fromisoformat(due_date_str)
                    recurrence_type = todo.get("recurrence_type")
                    if recurrence_type:
                        end_str = todo.get("recurrence_end_date")
                        end_date = date.fromisoformat(end_str) if end_str else None
                        interval = todo.get("recurrence_interval", 1)
                        completed_dates = todo.get("_completed_dates", set())
                        occurrences = generate_occurrences(
                            task_date, week_start, week_end,
                            recurrence_type, interval, end_date
                        )
                        for occ in occurrences:
                            if occ not in completed_dates:
                                self._pending_dates.add(occ)
                    else:
                        self._pending_dates.add(task_date)
                except (ValueError, TypeError):
                    pass

            for child in todo.get("children", []):
                if child.get("status") == 1:
                    continue
                child_due = child.get("due_date")
                if child_due:
                    try:
                        child_date = date.fromisoformat(child_due)
                        self._pending_dates.add(child_date)
                    except (ValueError, TypeError):
                        pass

    def _update_pending_dates(self):
        """更新待办日期显示（不重新计算）"""
        # 重新计算以获取新周的待办日期
        self._calculate_pending_dates()
        self._update_week_display()

    def refresh_theme(self):
        self._update_week_display()

    def clear_selection(self):
        self._selected_date = None
        self._update_week_display()
        self.filter_changed.emit(None)


class CalendarDialog(QDialog):
    """日程视图弹窗"""

    def __init__(self, todos: list[dict], parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setMinimumSize(680, 400)
        self.setMaximumSize(1200, 900)
        self.resize(760, 520)

        self._current_date = date.today()
        self._todos = todos
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

    def showEvent(self, event):
        super().showEvent(event)
        screen = self.screen().availableGeometry()
        x = screen.x() + (screen.width() - self.width()) // 2
        y = screen.y() + (screen.height() - self.height()) // 2
        self.move(x, y)

    def _get_tooltip_style(self) -> str:
        """获取 tooltip 样式片段"""
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
        else:
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

    def _setup_ui(self):
        """构建 UI"""
        dark = isDarkTheme()
        tooltip_style = self._get_tooltip_style()
        
        bg_color = "#1E1E1E" if dark else "#FAFAFA"
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {bg_color};
            }}
            {tooltip_style}
        """)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(24, 12, 24, 20)
        self.main_layout.setSpacing(12)

        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)

        title_label = SubtitleLabel("日程视图")
        title_label.setStyleSheet(f"font-weight: bold; color: {'#EEE' if dark else '#111'};")
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
                background-color: {'rgba(255, 255, 255, 0.1)' if dark else 'rgba(0, 0, 0, 0.08)'};
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
        month_color = "#FFF" if dark else "#1A1A1A"
        self.month_label.setStyleSheet(f"""
            font-size: 16px;
            font-weight: 600;
            color: {month_color};
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
        weekdays = ["日", "一", "二", "三", "四", "五", "六"]

        for i, wd in enumerate(weekdays):
            label = CaptionLabel(wd)
            label.setAlignment(Qt.AlignCenter)
            label.setFixedHeight(28)
            is_weekend = i == 0 or i == 6
            if dark:
                color = "#FF6B6B" if is_weekend else "#AAA"
            else:
                color = "#E53935" if is_weekend else "#666"
            label.setStyleSheet(f"""
                color: {color};
                font-size: 13px;
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

        day_label = CaptionLabel()
        day_label.setAlignment(Qt.AlignRight | Qt.AlignTop)
        day_label.setStyleSheet("font-weight: 500;")
        day_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        layout.addWidget(day_label)

        tasks_widget = QWidget()
        tasks_layout = QVBoxLayout(tasks_widget)
        tasks_layout.setContentsMargins(0, 0, 0, 0)
        tasks_layout.setSpacing(1)
        layout.addWidget(tasks_widget, 1)

        cell.day_label = day_label
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
        self._update_month_label()
        self.refresh_calendar()

    def _go_to_today(self):
        """回到今天"""
        self._current_date = date.today()
        self._update_month_label()
        self.refresh_calendar()

    def refresh_calendar(self):
        """刷新日历显示"""
        year = self._current_date.year
        month = self._current_date.month

        first_day = date(year, month, 1)
        _, days_in_month = monthrange(year, month)

        start_weekday = first_day.weekday()
        start_weekday = (start_weekday + 1) % 7

        for row in range(6):
            for col in range(7):
                cell = self.calendar_grid.itemAtPosition(row, col).widget()
                cell.day_label.setText("")
                cell.setProperty("date", None)
                cell.setProperty("is_today", False)

                while cell.tasks_layout.count():
                    item = cell.tasks_layout.takeAt(0)
                    if item.widget():
                        item.widget().deleteLater()

                cell.setStyleSheet(self._get_cell_style(False, False, col))

        today = date.today()

        for day in range(1, days_in_month + 1):
            cell_index = start_weekday + day - 1
            row = cell_index // 7
            col = cell_index % 7

            if row >= 6:
                break

            cell = self.calendar_grid.itemAtPosition(row, col).widget()
            cell_date = date(year, month, day)
            cell.setProperty("date", cell_date)

            is_today = (cell_date == today)
            cell.setProperty("is_today", is_today)

            day_label_style = self._get_day_label_style(is_today, col)
            cell.day_label.setStyleSheet(day_label_style)
            cell.day_label.setText(str(day))

            day_tasks = self._get_tasks_for_date(cell_date)

            for task in day_tasks[:4]:
                title = task["title"]
                if task.get("_is_virtual"):
                    title = "🔁 " + title
                display = title[:8] + ".." if len(title) > 8 else title
                task_label = QLabel(display)
                task_label.setStyleSheet(self._get_task_style(task))
                task_label.setToolTip(task["title"])
                cell.tasks_layout.addWidget(task_label)

            if len(day_tasks) > 4:
                more_label = CaptionLabel(f"+{len(day_tasks) - 4}")
                more_label.setStyleSheet(self._get_more_style())
                cell.tasks_layout.addWidget(more_label)

            cell.setStyleSheet(self._get_cell_style(is_today, len(day_tasks) > 0, col))

    def _get_tasks_for_date(self, target_date: date) -> list[dict]:
        """获取指定日期的任务"""
        tasks = []
        for todo in self._todos:
            due_date_str = todo.get("due_date")
            if due_date_str:
                try:
                    task_date = date.fromisoformat(due_date_str)
                    recurrence_type = todo.get("recurrence_type")
                    if recurrence_type:
                        end_str = todo.get("recurrence_end_date")
                        end_date = date.fromisoformat(end_str) if end_str else None
                        interval = todo.get("recurrence_interval", 1)
                        if matches_recurrence(task_date, target_date, recurrence_type, interval, end_date):
                            virtual = dict(todo)
                            virtual["_virtual_date"] = target_date.isoformat()
                            virtual["_is_virtual"] = target_date != task_date
                            completed_dates = todo.get("_completed_dates", set())
                            virtual["_occurrence_done"] = target_date in completed_dates
                            tasks.append(virtual)
                    else:
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
        return tasks

    def _get_day_label_style(self, is_today: bool, col: int) -> str:
        dark = isDarkTheme()
        is_weekend = col == 0 or col == 6
        
        if is_today:
            return """
                QLabel {
                    color: #FFF;
                    font-size: 12px;
                    font-weight: bold;
                    background-color: #0078D4;
                    border-radius: 10px;
                    padding: 0px 4px;
                    min-height: 20px;
                }
            """
        
        if dark:
            color = "#FF8A80" if is_weekend else "#E0E0E0"
        else:
            color = "#E53935" if is_weekend else "#424242"
        
        return f"color: {color}; font-size: 12px; font-weight: {'600' if is_weekend else '500'};"

    def _get_cell_style(self, is_today: bool, has_tasks: bool, col: int) -> str:
        """获取单元格样式"""
        dark = isDarkTheme()
        is_weekend = col == 0 or col == 6
        
        if dark:
            if is_today:
                bg_color = "rgba(0, 120, 212, 0.15)"
                border_color = "#0078D4"
            elif has_tasks:
                bg_color = "rgba(255, 255, 255, 0.05)"
                border_color = "rgba(255, 255, 255, 0.08)"
            elif is_weekend:
                bg_color = "rgba(255, 107, 107, 0.05)"
                border_color = "rgba(255, 255, 255, 0.05)"
            else:
                bg_color = "rgba(255, 255, 255, 0.02)"
                border_color = "rgba(255, 255, 255, 0.05)"
        else:
            if is_today:
                bg_color = "rgba(0, 120, 212, 0.08)"
                border_color = "#0078D4"
            elif has_tasks:
                bg_color = "rgba(0, 0, 0, 0.02)"
                border_color = "rgba(0, 0, 0, 0.06)"
            elif is_weekend:
                bg_color = "rgba(229, 57, 53, 0.04)"
                border_color = "rgba(0, 0, 0, 0.04)"
            else:
                bg_color = "rgba(0, 0, 0, 0.01)"
                border_color = "rgba(0, 0, 0, 0.04)"

        return f"""
            QFrame#dayCell {{
                background-color: {bg_color};
                border: 1px solid {border_color};
                border-radius: 8px;
            }}
            QFrame#dayCell:hover {{
                background-color: {'rgba(255, 255, 255, 0.08)' if dark else 'rgba(0, 0, 0, 0.04)'};
                border-color: {'rgba(255, 255, 255, 0.15)' if dark else 'rgba(0, 0, 0, 0.12)'};
            }}
        """

    def _get_task_style(self, task: dict) -> str:
        """获取任务标签样式"""
        dark = isDarkTheme()
        is_done = task.get("status") == 1 or task.get("_occurrence_done", False)
        color_tag = task.get("color_tag")

        if is_done:
            color = "#888" if dark else "#AAA"
            decoration = "text-decoration: line-through;"
            bg = "transparent"
        elif color_tag:
            color = color_tag
            decoration = ""
            bg = "rgba(255, 255, 255, 0.08)" if dark else "rgba(0, 0, 0, 0.05)"
        else:
            priority = task.get("priority", 0)
            if dark:
                colors = {0: "#B0BEC5", 1: "#4FC3F7", 2: "#FFB74D", 3: "#EF5350"}
            else:
                colors = {0: "#607D8B", 1: "#0288D1", 2: "#F57C00", 3: "#D32F2F"}
            color = colors.get(priority, colors[0])
            decoration = ""
            bg = "rgba(255, 255, 255, 0.08)" if dark else "rgba(0, 0, 0, 0.05)"

        tooltip_bg = "#3C3C3C" if dark else "#FFF"
        tooltip_text = "#EEE" if dark else "#333"
        tooltip_border = "#555" if dark else "#DDD"

        return f"""
            QLabel {{
                color: {color};
                font-size: 10px;
                {decoration}
                padding: 2px 4px;
                border-radius: 3px;
                background-color: {bg};
            }}
            QToolTip {{
                background-color: {tooltip_bg};
                color: {tooltip_text};
                border: 1px solid {tooltip_border};
                border-radius: 6px;
                padding: 6px 10px;
            }}
        """

    def _get_more_style(self) -> str:
        """获取"更多"标签样式"""
        dark = isDarkTheme()
        color = "#888" if dark else "#999"
        return f"""
            color: {color};
            font-size: 9px;
            padding: 1px 4px;
        """
