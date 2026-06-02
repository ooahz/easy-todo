"""主窗口"""
from __future__ import annotations
import json
import os
import sys
import winreg
from datetime import date, timedelta
from pathlib import Path

from PySide6.QtCore import QTimer, QRunnable, QThreadPool, Signal, QObject
from PySide6.QtWidgets import QApplication, QWidget, QFileDialog, QSystemTrayIcon, QMenu
from PySide6.QtGui import QAction, QIcon

from qfluentwidgets import (
    FluentWindow, NavigationItemPosition, FluentIcon, Theme,
    setTheme, InfoBar, InfoBarPosition, MessageBox, MessageBoxBase,
    SubtitleLabel, BodyLabel, isDarkTheme
)

from views.todo_list_view import TodoListView
from views.todo_dialog import TodoDialog
from views.settings_dialog import SettingsPage
from views.floating_widget import FloatingWidget
from views.todo_detail_panel import TodoDetailDialog
from views.recurrence_delete_dialog import RecurrenceDeleteDialog
from views.recurrence_edit_dialog import RecurrenceEditDialog
from views.delete_todo_dialog import DeleteTodoDialog
from services.todo_service import TodoService
from services.category_service import CategoryService
from services.file_service import FileService
from config.constants import STATUS_TODO, STATUS_DONE, STATUS_ARCHIVED, APP_NAME
from config.settings import settings


class _LoadTodosSignals(QObject):
    """后台加载待办数据的信号"""
    done = Signal(dict)


class _LoadTodosWorker(QRunnable):
    """后台线程执行数据库查询，避免阻塞 UI"""

    def __init__(self, params: dict):
        super().__init__()
        self._signals = _LoadTodosSignals()
        self.params = params
        self.setAutoDelete(True)

    @property
    def signals(self):
        return self._signals

    @staticmethod
    def _build_tree(todos, truncate_desc=False):
        """将 ORM 对象列表转为树形字典"""
        todo_dicts = [t.to_dict(truncate_desc=truncate_desc) for t in todos]
        id_map = {t["id"]: t for t in todo_dicts}
        parents = []
        for t in todo_dicts:
            if t["pid"] is None:
                parents.append(t)
            else:
                parent = id_map.get(t["pid"])
                if parent:
                    parent["children"].append(t)
        return parents

    @staticmethod
    def _mark_done(tree, done_at_bottom=False):
        """为任务树设置完成/归档标志"""
        for t in tree:
            t["_is_done"] = t.get("status", 0) == 1
            t["_is_archived"] = t.get("status", 0) == 2
            for ch in t.get("children", []):
                ch["_is_done"] = ch.get("status", 0) == 1
                ch["_is_archived"] = ch.get("status", 0) == 2
        if done_at_bottom:
            tree.sort(key=lambda t: t.get("status", 0))

    def run(self):
        from services.todo_service import TodoService
        svc = TodoService()
        try:
            p = self.params
            PAGE_SIZE = 100
            sort_rules = p['sort_rules']
            done_at_bottom = p['done_at_bottom']
            show_done = p['show_done_tasks']
            result = {}

            # ---- 全部任务 ----
            due_start, due_end = p.get('all_due_start'), p.get('all_due_end')
            if show_done:
                todos = svc.get_all_including_done(
                    sort_rules=sort_rules, done_at_bottom=done_at_bottom,
                    page=0, page_size=PAGE_SIZE,
                    due_start=due_start, due_end=due_end,
                )
                total = svc.count_filtered_including_done(
                    due_start=due_start, due_end=due_end,
                )
            else:
                todos = svc.get_all(
                    status=STATUS_TODO, sort_rules=sort_rules,
                    page=0, page_size=PAGE_SIZE,
                    due_start=due_start, due_end=due_end,
                )
                total = svc.count_filtered(
                    status=STATUS_TODO, due_start=due_start, due_end=due_end,
                )
            tree = self._build_tree(todos, truncate_desc=True)
            self._mark_done(tree, done_at_bottom=done_at_bottom)
            result['all'] = {'tree': tree, 'total': total}

            # ---- 最近待办 ----
            due_start, due_end = p.get('recent_due_start'), p.get('recent_due_end')
            recent_todos = svc.get_all_including_done(
                sort_rules=sort_rules, done_at_bottom=False,
                page=0, page_size=PAGE_SIZE,
                due_start=due_start, due_end=due_end,
            )
            recent_total = svc.count_filtered_including_done(
                due_start=due_start, due_end=due_end,
            )
            recent_tree = self._build_tree(recent_todos, truncate_desc=True)
            self._mark_done(recent_tree)
            result['recent'] = {'tree': recent_tree, 'total': recent_total}

            # ---- 今日任务 ----
            if show_done:
                today_todos = svc.get_all_including_done(
                    sort_rules=sort_rules, done_at_bottom=done_at_bottom,
                    page=0, page_size=PAGE_SIZE,
                )
                today_total = svc.count_filtered_including_done()
            else:
                today_todos = svc.get_all(
                    status=STATUS_TODO, sort_rules=sort_rules,
                    page=0, page_size=PAGE_SIZE,
                )
                today_total = svc.count_filtered(status=STATUS_TODO)
            today_tree = self._build_tree(today_todos, truncate_desc=True)
            self._mark_done(today_tree, done_at_bottom=done_at_bottom)
            result['today'] = {'tree': today_tree, 'total': today_total}

            # ---- 重要任务 ----
            due_start, due_end = p.get('imp_due_start'), p.get('imp_due_end')
            important_todos = svc.get_high_priority(
                page=0, page_size=PAGE_SIZE,
                due_start=due_start, due_end=due_end,
            )
            important_total = svc.count_high_priority(
                due_start=due_start, due_end=due_end,
            )
            important_tree = self._build_tree(important_todos, truncate_desc=True)
            self._mark_done(important_tree)
            result['important'] = {'tree': important_tree, 'total': important_total}

            # ---- 已完成/已归档 ----
            done_filter = p.get('done_filter', 'done')
            if done_filter == 'archived':
                done_todos = svc.get_all(status=STATUS_ARCHIVED, page=0, page_size=PAGE_SIZE)
                done_total = svc.count_filtered(status=STATUS_ARCHIVED)
            else:
                done_todos = svc.get_all(status=STATUS_DONE, page=0, page_size=PAGE_SIZE)
                done_total = svc.count_filtered(status=STATUS_DONE)
            done_tree = self._build_tree(done_todos, truncate_desc=True)
            self._mark_done(done_tree)
            result['done'] = {'tree': done_tree, 'total': done_total}

            # ---- 分类视图 ----
            cat_results = {}
            for cat_id, due_start, due_end in p.get('categories', []):
                cat_todos = svc.get_by_category(
                    cat_id, page=0, page_size=PAGE_SIZE,
                    due_start=due_start, due_end=due_end,
                )
                cat_total = svc.count_by_category(
                    cat_id, due_start=due_start, due_end=due_end,
                )
                cat_tree = self._build_tree(cat_todos, truncate_desc=True)
                self._mark_done(cat_tree)
                cat_results[cat_id] = {'tree': cat_tree, 'total': cat_total}
            result['categories'] = cat_results

            self._signals.done.emit(result)
        except Exception:
            self._signals.done.emit({})
        finally:
            svc.close()


class ConfirmDialog(MessageBoxBase):
    """带阴影和圆角的确认弹窗"""

    def __init__(self, title: str, content: str, confirm_text: str = "确认",
                 cancel_text: str = "取消", parent=None):
        super().__init__(parent)
        self._confirmed = False

        self.widget.setMinimumWidth(360)

        title_label = SubtitleLabel(title)
        self.viewLayout.addWidget(title_label)

        content_label = BodyLabel(content)
        content_label.setWordWrap(True)
        self.viewLayout.addWidget(content_label)

        self.yesButton.setText(confirm_text)
        self.cancelButton.setText(cancel_text)
        self.yesButton.clicked.connect(self._on_confirm)

    def _on_confirm(self):
        self._confirmed = True

    @property
    def confirmed(self):
        return self._confirmed


class MainWindow(FluentWindow):
    """Easy Todo 主窗口"""

    def __init__(self):
        super().__init__()
        self.todo_service = TodoService()
        self.category_service = CategoryService()
        self.file_service = FileService()

        # 当前视图标识
        self._current_view_key = "all"
        self._floating_view_key = "all"
        self._tray_tip_shown = False
        self._detail_dialog = None  # 任务详情对话框引用

        # 分类导航项缓存 {category_id: (interface, navigation_widget)}
        self._category_nav_items: dict[int, tuple] = {}
        self._last_system_view_order = list(settings.system_view_order)

        self._setup_ui()
        self._setup_navigation()
        self._setup_category_navigation()
        self._setup_floating()
        self._setup_tray()
        self._connect_signals()
        self._apply_initial_theme()

        # 启动时处理自动延期
        self.todo_service.process_auto_postpone()

        # 跨天检测：5分钟轮询 + changeEvent 兜底休眠恢复
        self._last_refresh_date = date.today()  # 启动时已执行 process_auto_postpone
        self._daily_check_timer = QTimer(self)
        self._daily_check_timer.setInterval(300_000)  # 5分钟
        self._daily_check_timer.timeout.connect(self._check_daily_refresh)
        self._daily_check_timer.start()

        self._load_todos()

    def _setup_ui(self):
        """初始化窗口"""
        self.setWindowTitle(APP_NAME)
        self.resize(*settings.window_size)

        pos = settings.window_pos
        if pos:
            self.move(*pos)

        self.setMinimumSize(800, 500)

        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)

    def _setup_navigation(self):
        """设置导航栏"""
        self._view_instances = {
            "all": TodoListView(view_name="全部任务"),
            "today": TodoListView(view_name="今日任务"),
            "important": TodoListView(view_name="重要任务"),
            "done": TodoListView(view_name="已完成", readonly=True),
            "recent": TodoListView(view_name="最近待办"),
        }
        self._view_instances["all"].setObjectName("todoListView")
        self._view_instances["today"].setObjectName("todayView")
        self._view_instances["important"].setObjectName("importantView")
        self._view_instances["done"].setObjectName("doneView")
        self._view_instances["recent"].setObjectName("recentView")

        self.todo_list_view = self._view_instances["all"]
        self.today_view = self._view_instances["today"]
        self.important_view = self._view_instances["important"]
        self.done_view = self._view_instances["done"]
        self.recent_view = self._view_instances["recent"]

        self._view_map = {
            "all": FluentIcon.APPLICATION,
            "today": FluentIcon.CALENDAR,
            "important": FluentIcon.CALORIES,
            "done": FluentIcon.COMPLETED,
            "recent": FluentIcon.QUICK_NOTE,
        }
        self._view_names = {
            "all": "全部任务",
            "today": "今日任务",
            "important": "重要任务",
            "done": "已完成",
            "recent": "最近待办",
        }

        order = settings.system_view_order
        for key in order:
            if key in self._view_instances:
                view = self._view_instances[key]
                icon = self._view_map[key]
                name = self._view_names[key]
                self.addSubInterface(view, icon, name)

        # 日程视图弹窗（不添加到 stackedWidget）
        # 通过工具栏按钮打开

        # 底部导航 - 设置
        self.settings_page = SettingsPage()
        self.settings_page.setObjectName("settingsPage")
        self.addSubInterface(
            self.settings_page, FluentIcon.SETTING,
            "设置",
            position=NavigationItemPosition.BOTTOM,
        )

    def _setup_floating(self):
        """初始化浮窗"""
        self.floating = FloatingWidget()
        self.floating.set_opacity(settings.floating_opacity)
        self.floating.set_always_on_top(settings.floating_top)
        self.floating.set_pinned(settings.floating_pinned)
        self.floating.pin_changed.connect(self._on_floating_pin_changed)
        self.floating.quick_add.connect(self._on_floating_quick_add)

        # 恢复浮窗位置和视图
        geo = settings.floating_geometry
        if geo:
            self.floating.setGeometry(geo.get("x", 0), geo.get("y", 0),
                                      geo.get("w", 300), geo.get("h", 400))
            self._floating_view_key = settings.floating_view
        else:
            self._position_floating()

        # 固定状态下自动显示浮窗
        self._restore_floating_pending = settings.floating_pinned

    def _position_floating(self):
        """将浮窗定位到主窗口右侧"""
        main_geo = self.geometry()
        fx = main_geo.right() + 10
        fy = main_geo.y() + 50
        screen = QApplication.primaryScreen().geometry()
        if fx + 300 > screen.right():
            fx = main_geo.left() - 310
        self.floating.move(fx, fy)

    def _setup_tray(self):
        """初始化系统托盘"""
        self.tray_icon = QSystemTrayIcon(self)

        # 设置托盘图标
        icon_path = self._get_icon_path()
        if icon_path:
            self.tray_icon.setIcon(QIcon(icon_path))
        else:
            self.tray_icon.setIcon(self.windowIcon())

        self.tray_icon.setToolTip(APP_NAME)

        # 托盘菜单
        tray_menu = QMenu()

        show_action = QAction("显示主窗口", self)
        show_action.triggered.connect(self._tray_show)
        tray_menu.addAction(show_action)

        float_action = QAction("显示浮窗", self)
        float_action.triggered.connect(self._tray_toggle_floating)
        tray_menu.addAction(float_action)

        quit_action = QAction("退出", self)
        quit_action.triggered.connect(self._tray_quit)
        tray_menu.addAction(quit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self._tray_activated)
        self.tray_icon.show()

    def _get_icon_path(self):
        """获取图标路径"""
        icon_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "assets", "icon.ico"
        )
        if os.path.exists(icon_path):
            return icon_path
        return None

    def _tray_activated(self, reason):
        """托盘图标激活"""
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._tray_show()

    def _tray_show(self):
        """从托盘恢复窗口"""
        self.showNormal()
        self.activateWindow()
        self.raise_()

    def _tray_toggle_floating(self):
        """从托盘显示浮窗"""
        if not self.floating.isVisible():
            self._position_floating()
            self._update_floating_data(self._floating_view_key)
        self.floating.show()
        self.floating.activateWindow()

    def _tray_quit(self):
        """从托盘退出应用"""
        settings.flush()
        self.tray_icon.hide()
        self.floating.close()
        self.todo_service.close()
        self.category_service.close()
        QApplication.quit()

    def _connect_signals(self):
        """连接信号"""
        view_map = {
            "all": self.todo_list_view,
            "today": self.today_view,
            "important": self.important_view,
            "done": self.done_view,
            "recent": self.recent_view,
        }

        for key, view in view_map.items():
            view.add_clicked.connect(lambda: self._open_todo_dialog())
            view.edit_clicked.connect(self._open_todo_dialog)
            view.delete_clicked.connect(self._delete_todo)
            view.toggle_done.connect(self._toggle_todo_done)
            view.reorder_requested.connect(self._on_reorder_todos)
            view.add_subtask_clicked.connect(self._open_todo_dialog_for_subtask)
            view.card_clicked.connect(self._on_card_clicked)
            view.archive_clicked.connect(self._archive_todo)
            view.float_clicked.connect(lambda k=key: self._toggle_floating(k))
            view.calendar_clicked.connect(self._show_calendar_view)
            view.page_changed.connect(lambda page, ps, k=key: self._on_page_changed(k, page, ps))

        self.done_view.filter_combo.setVisible(True)
        self.done_view.archive_all_btn.setVisible(True)
        self.done_view.filter_changed.connect(self._on_done_filter_changed)
        self.done_view.archive_all_clicked.connect(self._archive_all_done)

        self.todo_list_view.set_time_filter_visible(True)
        self.important_view.set_time_filter_visible(True)
        self.recent_view.set_time_filter_visible(True)

        for key, view in view_map.items():
            if key not in ("done", "today"):
                view.time_filter_changed.connect(
                    lambda fk, k=key: self._on_time_filter_changed(k, fk)
                )

        # 浮窗点击完成待办
        self.floating.todo_toggled.connect(self._toggle_todo_done)

        # 设置页面信号
        self.settings_page.opacity_changed.connect(self.floating.set_opacity)
        self.settings_page.theme_changed.connect(self._on_theme_changed)
        self.settings_page.show_done_changed.connect(self._on_show_done_changed)
        self.settings_page.show_week_view_changed.connect(self._on_show_week_view_changed)
        self.settings_page.auto_start_changed.connect(self._on_auto_start_changed)
        self.settings_page.sort_rule_changed.connect(self._on_sort_rule_changed)
        self.settings_page.done_at_bottom_changed.connect(self._on_done_at_bottom_changed)
        self.settings_page.floating_top_changed.connect(self._on_floating_top_changed)
        self.settings_page.manual_refresh_clicked.connect(self._manual_refresh)
        self.settings_page.export_btn.clicked.connect(self._export_data)
        self.settings_page.import_btn.clicked.connect(self._import_data)
        self.settings_page.categories_changed.connect(self._on_categories_changed)

        # 导航切换时记录当前视图
        self.stackedWidget.currentChanged.connect(self._on_view_changed)

        self.resizeEvent = self._on_resize
        self.moveEvent = self._on_move

    def _on_view_changed(self, index):
        """导航切换时记录当前视图"""
        widget = self.stackedWidget.widget(index)
        if widget == self.todo_list_view:
            self._current_view_key = "all"
        elif widget == self.today_view:
            self._current_view_key = "today"
            self._reset_today_filter()
        elif widget == self.important_view:
            self._current_view_key = "important"
        elif widget == self.done_view:
            self._current_view_key = "done"
        elif widget == self.recent_view:
            self._current_view_key = "recent"
        else:
            for cat_id, (view, name) in self._category_nav_items.items():
                if widget == view:
                    self._current_view_key = f"cat_{cat_id}"
                    break

    def _reset_today_filter(self):
        """重置今日任务页面的筛选日期为今天"""
        today = date.today()
        self.today_view._filter_date = today
        self.today_view.week_view.set_selected_date(today)
        if self.today_view._all_todos:
            self.today_view._todos = self.today_view._filter_todos_by_date(
                self.today_view._all_todos, today
            )
            self.today_view._current_page = 0
            self.today_view._update_pager()
            self.today_view._refresh_list()

    def _toggle_floating(self, view_key: str = None):
        """显示/刷新浮窗"""
        key = view_key or self._current_view_key
        if not self.floating.isVisible():
            self._position_floating()
        self._floating_view_key = key
        self._update_floating_data(key)
        self.floating.show()
        self.floating.activateWindow()

    def _update_floating_data(self, view_key: str):
        """根据视图标识更新浮窗数据"""
        # 处理分类视图
        if view_key.startswith("cat_"):
            cat_id = int(view_key.split("_")[1])
            cat_name = self._category_nav_items.get(cat_id, (None, "任务列表"))[1]
            self.floating.title_label.setText(cat_name)
            todos = self.todo_service.get_by_category(cat_id)
            tree = self._build_todo_tree(todos, truncate_desc=True)
            tree = TodoListView._dedup_recurrence(tree)
            self._inject_completed_dates(tree)
            self.floating.set_todos(tree)
            return

        title_map = {"all": "全部任务", "today": "今日任务", "important": "重要任务", "done": "已完成", "recent": "最近待办"}
        self.floating.title_label.setText(title_map.get(view_key, "任务列表"))

        if view_key == "done":
            done_todos = self.todo_service.get_all(status=STATUS_DONE)
            todos = done_todos
        elif view_key == "today":
            if settings.show_done_tasks:
                todos = self.todo_service.get_all_including_done(
                    sort_rules=settings.sort_rules,
                    done_at_bottom=settings.done_at_bottom
                )
            else:
                todos = self.todo_service.get_all(
                    status=STATUS_TODO, sort_rules=settings.sort_rules
                )
        elif view_key == "important":
            todos = self.todo_service.get_high_priority()
        elif view_key == "recent":
            todos = self.todo_service.get_all_including_done(
                sort_rules=settings.sort_rules,
                done_at_bottom=False,
            )
        else:
            if settings.show_done_tasks:
                todos = self.todo_service.get_all_including_done(
                    sort_rules=settings.sort_rules,
                    done_at_bottom=settings.done_at_bottom
                )
            else:
                todos = self.todo_service.get_all(
                    status=STATUS_TODO, sort_rules=settings.sort_rules
                )

        tree = self._build_todo_tree(todos, truncate_desc=True)
        if view_key == "today":
            self._inject_completed_dates(tree, done_at_bottom=settings.done_at_bottom)
            tree = self.today_view._filter_todos_by_date(tree, date.today())
        elif view_key == "recent":
            tree = TodoListView._dedup_recurrence(tree)
            self._inject_completed_dates(tree)
            tree = self._sort_for_recent(tree)
        else:
            tree = TodoListView._dedup_recurrence(tree)
            done_at_bottom = settings.done_at_bottom if view_key in ("all",) else False
            self._inject_completed_dates(tree, done_at_bottom=done_at_bottom)
        self.floating.set_todos(tree)

    def _apply_initial_theme(self):
        theme = settings.theme
        if theme == "dark":
            setTheme(Theme.DARK)
        elif theme == "light":
            setTheme(Theme.LIGHT)
        else:
            try:
                import darkdetect
                setTheme(Theme.DARK if darkdetect.isDark() else Theme.LIGHT)
            except Exception:
                setTheme(Theme.LIGHT)

        # 主题应用后恢复固定浮窗
        if getattr(self, '_restore_floating_pending', False):
            self._restore_floating_pending = False
            self._update_floating_data(self._floating_view_key)
            self.floating.refresh_theme()
            self.floating.show()

    def _check_daily_refresh(self):
        """检测是否跨天，跨天则执行自动延期 + 刷新列表"""
        if date.today() != self._last_refresh_date:
            self._run_daily_refresh()

    def _run_daily_refresh(self):
        """执行每日维护：自动延期 + 刷新列表（后台线程）"""
        self._last_refresh_date = date.today()
        self._start_postpone_worker()

    def _manual_refresh(self):
        """手动刷新：执行自动延期 + 刷新列表，不影响跨天检测"""
        self._start_postpone_worker()

    def _start_postpone_worker(self):
        """启动后台 worker 执行 auto-postpone 并刷新 UI"""
        class _RefreshWorker(QRunnable):
            def __init__(self, callback):
                super().__init__()
                self._signals = _LoadTodosSignals()
                self._signals.done.connect(callback)
                self.setAutoDelete(True)

            def run(self):
                from services.todo_service import TodoService
                svc = TodoService()
                try:
                    svc.process_auto_postpone()
                finally:
                    svc.close()
                self._signals.done.emit({})

        def _on_done():
            self.todo_service.reset_session()
            self._load_todos()

        worker = _RefreshWorker(_on_done)
        QThreadPool.globalInstance().start(worker)

    def changeEvent(self, event):
        """窗口激活时检测跨天，应对系统休眠"""
        super().changeEvent(event)
        if event.type() == event.Type.ActivationChange and self.isActiveWindow():
            self._check_daily_refresh()

    def _build_todo_tree(self, todos: list, truncate_desc: bool = False) -> list[dict]:
        """在内存中构建任务树形结构"""
        todo_dicts = [t.to_dict(truncate_desc=truncate_desc) for t in todos]
        id_map = {t["id"]: t for t in todo_dicts}

        # 构建树形：子任务放入父任务的 children
        parents = []
        for t in todo_dicts:
            if t["pid"] is None:
                parents.append(t)
            else:
                parent = id_map.get(t["pid"])
                if parent:
                    parent["children"].append(t)

        return parents

    def _inject_completed_dates(self, tree: list[dict], done_at_bottom: bool = False):
        """为任务树设置完成/归档标志"""
        for t in tree:
            t["_is_done"] = t.get("status", 0) == 1
            t["_is_archived"] = t.get("status", 0) == 2
            for ch in t.get("children", []):
                ch["_is_done"] = ch.get("status", 0) == 1
                ch["_is_archived"] = ch.get("status", 0) == 2

        if done_at_bottom:
            tree.sort(key=lambda t: t.get("status", 0))

    def _sort_for_recent(self, tree: list[dict]) -> list[dict]:
        """按最近待办视图的优先级排序：超期未完成 → 今日 → 后续 → 已完成"""
        from datetime import date as _date
        today = _date.today()

        def _rank(t):
            if t.get("_is_done", False):
                return 3
            due_str = t.get("due_date")
            if due_str:
                try:
                    due = _date.fromisoformat(due_str)
                    if due < today:
                        return 0
                    elif due == today:
                        return 1
                except (ValueError, TypeError):
                    pass
            return 2

        tree.sort(key=_rank)
        return tree

    def _load_todos(self):
        """加载待办数据（后台线程查询，避免阻塞 UI）"""
        if getattr(self, '_load_in_progress', False):
            self._pending_load = True
            return

        self._load_in_progress = True
        self._pending_load = False

        self.todo_list_view.show_loading()
        self.today_view.show_loading()
        self.important_view.show_loading()
        self.done_view.show_loading()
        self.recent_view.show_loading()
        for cat_id, (view, _) in self._category_nav_items.items():
            view.show_loading()

        # 在主线程中收集查询参数（访问 UI 组件）
        params = self._collect_load_params()
        worker = _LoadTodosWorker(params)
        worker.signals.done.connect(self._on_todos_loaded)
        QThreadPool.globalInstance().start(worker)

    def _collect_load_params(self):
        """收集查询参数（在主线程中调用，访问 UI 组件）"""
        all_filter = self.todo_list_view.current_time_filter()
        recent_filter = self.recent_view.current_time_filter()
        imp_filter = self.important_view.current_time_filter()

        all_due_start, all_due_end = self._get_date_range(all_filter)
        recent_due_start, recent_due_end = self._get_date_range(recent_filter)
        imp_due_start, imp_due_end = self._get_date_range(imp_filter)

        categories = []
        for cat_id, (view, _) in self._category_nav_items.items():
            cat_filter = view.current_time_filter()
            cat_due_start, cat_due_end = self._get_date_range(cat_filter)
            categories.append((cat_id, cat_due_start, cat_due_end))

        return {
            'sort_rules': settings.sort_rules,
            'done_at_bottom': settings.done_at_bottom,
            'show_done_tasks': settings.show_done_tasks,
            'done_filter': getattr(self, '_done_filter', 'done'),
            'all_due_start': all_due_start,
            'all_due_end': all_due_end,
            'recent_due_start': recent_due_start,
            'recent_due_end': recent_due_end,
            'imp_due_start': imp_due_start,
            'imp_due_end': imp_due_end,
            'categories': categories,
        }

    def _on_todos_loaded(self, result: dict):
        """后台线程查询完成，在主线程中更新 UI"""
        self._load_in_progress = False

        if not result:
            return

        if 'all' in result:
            r = result['all']
            self.todo_list_view.set_todos(r['tree'], total_count=r['total'])

        if 'recent' in result:
            r = result['recent']
            self.recent_view.set_todos(r['tree'], total_count=r['total'])

        if 'today' in result:
            r = result['today']
            self.today_view._filter_date = date.today()
            self.today_view.week_view.set_selected_date(date.today())
            self.today_view.set_todos(r['tree'], total_count=r['total'])

        if 'important' in result:
            r = result['important']
            self.important_view.set_todos(r['tree'], total_count=r['total'])

        if 'done' in result:
            r = result['done']
            self.done_view.set_todos(r['tree'], total_count=r['total'])

        if 'categories' in result:
            for cat_id, cat_data in result['categories'].items():
                if cat_id in self._category_nav_items:
                    view, _ = self._category_nav_items[cat_id]
                    view.set_todos(cat_data['tree'], total_count=cat_data['total'])

        if self.floating.isVisible():
            self._update_floating_data(self._floating_view_key)

        # 如果在加载期间有新的刷新请求，执行延迟刷新
        if getattr(self, '_pending_load', False):
            self._pending_load = False
            self._load_todos()

    def _refresh_all_views(self):
        self._load_todos()

    def _on_page_changed(self, view_key: str, page: int, page_size: int):
        sort_rules = settings.sort_rules
        done_at_bottom = settings.done_at_bottom

        if view_key in ("done", "today"):
            if view_key == "today":
                if settings.show_done_tasks:
                    todos = self.todo_service.get_all_including_done(
                        sort_rules=sort_rules, done_at_bottom=done_at_bottom,
                        page=page, page_size=page_size,
                    )
                else:
                    todos = self.todo_service.get_all(
                        status=STATUS_TODO, sort_rules=sort_rules,
                        page=page, page_size=page_size,
                    )
                tree = self._build_todo_tree(todos, truncate_desc=True)
                self._inject_completed_dates(tree, done_at_bottom=done_at_bottom)
                self.today_view.set_todos(tree)
            else:
                done_filter = getattr(self, '_done_filter', 'done')
                status = STATUS_ARCHIVED if done_filter == 'archived' else STATUS_DONE
                todos = self.todo_service.get_all(
                    status=status, page=page, page_size=page_size,
                )
                tree = self._build_todo_tree(todos, truncate_desc=True)
                self._inject_completed_dates(tree)
                self.done_view.set_todos(tree)
            return

        self._reload_view_with_time_filter(view_key, page=page)

    def _open_todo_dialog(self, todo_id: int = None):
        todo_data = None
        edit_mode = None
        template_data = None
        if todo_id:
            todo = self.todo_service.get_by_id(todo_id)
            if todo:
                todo_data = todo.to_dict()
                if todo.recurrence_template_id and todo.recurrence_type:
                    dlg = RecurrenceEditDialog(parent=self)
                    if not dlg.exec():
                        return
                    edit_mode = dlg.result_mode
                    if edit_mode == "this_and_future":
                        template = self.todo_service.get_by_id(todo.recurrence_template_id)
                        if template:
                            template_data = template.to_dict()

        dialog = TodoDialog(todo_data=todo_data, parent=self,
                            edit_mode=edit_mode, template_data=template_data)
        dialog.todo_saved.connect(self._on_todo_saved)
        dialog.exec()

    def _on_todo_saved(self, data: dict):
        temp_files = data.pop("temp_files", [])
        edit_mode = data.pop("edit_mode", None)

        try:
            if "id" in data:
                todo_id = data.pop("id")
                if edit_mode == "this_and_future":
                    todo = self.todo_service.split_and_update_from_instance(todo_id, **data)
                elif edit_mode == "this":
                    data["is_exception"] = True
                    todo = self.todo_service.update(todo_id, **data)
                else:
                    todo = self.todo_service.update(todo_id, **data)
            else:
                todo = self.todo_service.create(**data)
        except ValueError as e:
            InfoBar.error(title="保存失败", content=str(e), parent=self,
                         position=InfoBarPosition.TOP, duration=3000)
            return

        # 保存关联文件
        if todo and temp_files:
            for file_path in temp_files:
                try:
                    self.file_service.save_file(todo.id, file_path)
                except Exception as e:
                    print(f"保存文件失败: {e}")

        if todo:
            self._refresh_all_views()
            InfoBar.success(title="成功", content="任务已保存", parent=self,
                           position=InfoBarPosition.TOP, duration=2000)

    def _delete_todo(self, todo_id: int):
        todo = self.todo_service.get_by_id(todo_id)
        file_count = self.file_service.get_file_count(todo_id)

        if todo and todo.recurrence_template_id and todo.recurrence_type:
            dlg = RecurrenceDeleteDialog(file_count, parent=self)
            if dlg.exec() and dlg.result_mode:
                mode = dlg.result_mode
                if dlg.delete_files:
                    affected_ids = self.todo_service.get_affected_instance_ids(todo_id, mode)
                    for aid in affected_ids:
                        self.file_service.delete_task_folder(aid)
                self.todo_service.delete_instance(todo_id, mode=mode)
                self._refresh_all_views()
                InfoBar.success(title="已删除", content="任务已删除", parent=self,
                               position=InfoBarPosition.TOP, duration=2000)
            return

        dlg = DeleteTodoDialog(todo_id, file_count, parent=self)
        if dlg.exec():
            if self.todo_service.delete(todo_id):
                if dlg.delete_files:
                    self.file_service.delete_task_folder(todo_id)
                self._refresh_all_views()
                InfoBar.success(title="已删除", content="任务已删除", parent=self,
                               position=InfoBarPosition.TOP, duration=2000)

    def _toggle_todo_done(self, todo_id: int):
        if self.todo_service.toggle_done(todo_id):
            self._refresh_all_views()

    def _archive_todo(self, todo_id: int):
        msg = MessageBox("确认归档", "确定要归档这个任务吗？归档后可在「已完成」页面筛选查看。", self)
        msg.yesButton.setText("归档")
        msg.cancelButton.setText("取消")
        if msg.exec():
            self.todo_service.update(todo_id, status=STATUS_ARCHIVED)
            self._refresh_all_views()
            InfoBar.success(title="已归档", content="任务已归档", parent=self,
                           position=InfoBarPosition.TOP, duration=2000)

    def _archive_all_done(self):
        done_count = self.todo_service.count_by_status(STATUS_DONE)
        if done_count == 0:
            InfoBar.info(title="提示", content="没有可归档的已完成任务", parent=self,
                        position=InfoBarPosition.TOP, duration=2000)
            return
        dlg = ConfirmDialog("确认归档", f"确定要归档全部 {done_count} 个已完成任务吗？\n归档后可在「已完成」页面筛选查看。",
                            confirm_text="全部归档", cancel_text="取消", parent=self)
        if dlg.exec():
            count = self.todo_service.archive_all_done()
            self._refresh_all_views()
            InfoBar.success(title="已归档", content=f"已归档 {count} 个任务", parent=self,
                           position=InfoBarPosition.TOP, duration=2000)

    def _on_done_filter_changed(self, filter_key: str):
        PAGE_SIZE = 100
        self._done_filter = filter_key
        self.done_view.archive_all_btn.setVisible(filter_key == 'done')
        status = STATUS_ARCHIVED if filter_key == 'archived' else STATUS_DONE
        todos = self.todo_service.get_all(
            status=status, page=0, page_size=PAGE_SIZE,
        )
        total = self.todo_service.count_filtered(status=status)
        tree = self._build_todo_tree(todos, truncate_desc=True)
        self._inject_completed_dates(tree)
        self.done_view.set_todos(tree, total_count=total)

    @staticmethod
    def _get_date_range(filter_key: str):
        if filter_key == "week":
            today = date.today()
            weekday = today.weekday()
            start = today - timedelta(days=weekday)
            end = start + timedelta(days=6)
            return start, end
        elif filter_key == "month":
            today = date.today()
            start = today.replace(day=1)
            if today.month == 12:
                end = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
            else:
                end = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
            return start, end
        elif filter_key == "year":
            today = date.today()
            start = today.replace(month=1, day=1)
            end = today.replace(month=12, day=31)
            return start, end
        return None, None

    def _on_time_filter_changed(self, view_key: str, filter_key: str):
        self._reload_view_with_time_filter(view_key, page=0)

    def _reload_view_with_time_filter(self, view_key: str, page: int = 0):
        PAGE_SIZE = 100
        sort_rules = settings.sort_rules
        done_at_bottom = settings.done_at_bottom

        if view_key in ("done", "today"):
            return

        view = self._get_view_by_key(view_key)
        if not view:
            return

        filter_key = view.current_time_filter()
        due_start, due_end = self._get_date_range(filter_key)

        if view_key == "all":
            if settings.show_done_tasks:
                todos = self.todo_service.get_all_including_done(
                    sort_rules=sort_rules, done_at_bottom=done_at_bottom,
                    page=page, page_size=PAGE_SIZE,
                    due_start=due_start, due_end=due_end,
                )
                total = self.todo_service.count_filtered_including_done(
                    due_start=due_start, due_end=due_end,
                )
            else:
                todos = self.todo_service.get_all(
                    status=STATUS_TODO, sort_rules=sort_rules,
                    page=page, page_size=PAGE_SIZE,
                    due_start=due_start, due_end=due_end,
                )
                total = self.todo_service.count_filtered(
                    status=STATUS_TODO, due_start=due_start, due_end=due_end,
                )
            tree = self._build_todo_tree(todos, truncate_desc=True)
            self._inject_completed_dates(tree, done_at_bottom=done_at_bottom)
            view.set_todos(tree, total_count=total)

        elif view_key == "important":
            todos = self.todo_service.get_high_priority(
                page=page, page_size=PAGE_SIZE,
                due_start=due_start, due_end=due_end,
            )
            total = self.todo_service.count_high_priority(
                due_start=due_start, due_end=due_end,
            )
            tree = self._build_todo_tree(todos, truncate_desc=True)
            self._inject_completed_dates(tree)
            view.set_todos(tree, total_count=total)

        elif view_key == "recent":
            recent_todos = self.todo_service.get_all_including_done(
                sort_rules=sort_rules, done_at_bottom=False,
                page=page, page_size=PAGE_SIZE,
                due_start=due_start, due_end=due_end,
            )
            recent_total = self.todo_service.count_filtered_including_done(
                due_start=due_start, due_end=due_end,
            )
            recent_tree = self._build_todo_tree(recent_todos, truncate_desc=True)
            self._inject_completed_dates(recent_tree)
            view.set_todos(recent_tree, total_count=recent_total)

        elif view_key.startswith("cat_"):
            cat_id = int(view_key.split("_")[1])
            item = self._category_nav_items.get(cat_id)
            if item:
                cat_view = item[0]
                cat_filter_key = cat_view.current_time_filter()
                cat_due_start, cat_due_end = self._get_date_range(cat_filter_key)
                todos = self.todo_service.get_by_category(
                    cat_id, page=page, page_size=PAGE_SIZE,
                    due_start=cat_due_start, due_end=cat_due_end,
                )
                total = self.todo_service.count_by_category(
                    cat_id, due_start=cat_due_start, due_end=cat_due_end,
                )
                tree = self._build_todo_tree(todos, truncate_desc=True)
                self._inject_completed_dates(tree)
                cat_view.set_todos(tree, total_count=total)

    def _get_view_by_key(self, view_key: str):
        if view_key == "all":
            return self.todo_list_view
        elif view_key == "today":
            return self.today_view
        elif view_key == "important":
            return self.important_view
        elif view_key == "done":
            return self.done_view
        elif view_key == "recent":
            return self.recent_view
        elif view_key.startswith("cat_"):
            cat_id = int(view_key.split("_")[1])
            item = self._category_nav_items.get(cat_id)
            if item:
                return item[0]
        return None

    def _on_card_clicked(self, todo_id: int):
        """父任务卡片点击 - 弹出详情对话框"""
        todo = self.todo_service.get_by_id(todo_id)
        if todo:
            todo_tree = self._build_todo_tree([todo])
            self._inject_completed_dates(todo_tree)
            if todo_tree:
                dialog = TodoDetailDialog(todo_tree[0], parent=self)
                dialog.exec()
                if dialog._pending_action:
                    action, tid = dialog._pending_action
                    if action == "toggle_done":
                        self._toggle_todo_done(tid)
                    elif action == "edit":
                        self._open_todo_dialog(tid)
                    elif action == "delete":
                        self._delete_todo(tid)
                    elif action == "subtask_toggle_done":
                        self._toggle_todo_done(tid)
                    elif action == "archive":
                        self._archive_todo(tid)

    def _open_todo_dialog_for_subtask(self, parent_id: int):
        """为父任务新建子任务"""
        # 检查子任务数量限制
        children_count = self.todo_service.get_children_count(parent_id)
        if children_count >= 15:
            InfoBar.warning(
                title="子任务已达上限",
                content="每个父任务最多创建 15 个子任务",
                parent=self,
                position=InfoBarPosition.TOP,
                duration=3000
            )
            return
        dialog = TodoDialog(pid=parent_id, parent=self)
        dialog.todo_saved.connect(self._on_todo_saved)
        dialog.exec()

    def _show_calendar_view(self):
        """打开日程视图弹窗"""
        from views.calendar_view import CalendarDialog
        todos = self.todo_service.get_all_including_done() if settings.show_done_tasks else self.todo_service.get_all()
        tree = self._build_todo_tree(todos, truncate_desc=True)
        self._inject_completed_dates(tree)
        templates = self.todo_service.get_all_templates()
        tpl_dicts = [t.to_dict(truncate_desc=True) for t in templates]
        dialog = CalendarDialog(tree + tpl_dicts, parent=self)
        dialog.exec()

    def _on_reorder_todos(self, from_id: int, to_id: int, insert_after: bool, current_order: list):
        """处理任务拖拽排序 - 基于当前视图显示的顺序"""
        todo_ids = current_order.copy()

        if from_id not in todo_ids or to_id not in todo_ids:
            return

        # 如果不是自定义排序，先记录当前顺序到数据库，再执行拖拽
        if settings.sort_rules != ["custom"]:
            self.todo_service.reorder(todo_ids)
            settings.sort_rules = ["custom"]
            settings.sort_rule = "custom"
            self.settings_page._update_sort_ui(["custom"])

        # 重新排序：将 from_id 放到 to_id 的上方或下方
        from_idx = todo_ids.index(from_id)
        to_idx = todo_ids.index(to_id)

        # 移除源元素
        todo_ids.pop(from_idx)

        # 重新计算目标位置（因为可能已移除一个元素）
        if from_idx < to_idx:
            to_idx -= 1

        # 根据 insert_after 决定插入位置
        if insert_after:
            to_idx += 1

        # 插入到目标位置
        todo_ids.insert(to_idx, from_id)

        # 更新排序
        self.todo_service.reorder(todo_ids)

        self._refresh_all_views()

    # ---- 导入导出 ----

    def _export_data(self):
        """导出数据"""
        path, _ = QFileDialog.getSaveFileName(
            self, "导出数据", "easy_todo_backup.json", "JSON 文件 (*.json)"
        )
        if not path:
            return
        try:
            from services.import_export_service import ImportExportService
            service = ImportExportService(self.todo_service, self.category_service)
            data = service.export_data()
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            todo_count = len(data.get("todos", []))
            InfoBar.success(title="导出成功", content=f"已导出 {todo_count} 个任务", parent=self,
                           position=InfoBarPosition.TOP, duration=2000)
        except Exception as e:
            InfoBar.error(title="导出失败", content=str(e), parent=self,
                         position=InfoBarPosition.TOP, duration=3000)

    def _import_data(self):
        """导入数据"""
        path, _ = QFileDialog.getOpenFileName(
            self, "导入数据", "", "JSON 文件 (*.json)"
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            from services.import_export_service import ImportExportService
            service = ImportExportService(self.todo_service, self.category_service)
            preview = service.preview(data)

            from views.import_preview_dialog import ImportPreviewDialog
            dlg = ImportPreviewDialog(preview, parent=self)
            if not preview.get("valid", False):
                dlg.exec()
                return
            if not dlg.exec():
                return

            mode = dlg.selected_mode
            result = service.import_data(data, mode=mode)
            self._refresh_all_views()

            total = result.get("imported", 0)
            cats = result.get("categories", 0)
            parts = [f"{total} 个任务"]
            if cats > 0:
                parts.append(f"{cats} 个分类")
            InfoBar.success(title="导入成功", content="已导入 " + "，".join(parts),
                           parent=self, position=InfoBarPosition.TOP, duration=2000)
        except Exception as e:
            InfoBar.error(title="导入失败", content=str(e), parent=self,
                         position=InfoBarPosition.TOP, duration=3000)

    # ---- 设置回调 ----

    def _on_theme_changed(self, theme: str):
        if theme == "light":
            setTheme(Theme.LIGHT)
        elif theme == "dark":
            setTheme(Theme.DARK)
        else:
            try:
                import darkdetect
                setTheme(Theme.DARK if darkdetect.isDark() else Theme.LIGHT)
            except Exception:
                pass
        
        # 刷新浮窗样式
        self.floating.refresh_theme()
        # 刷新卡片样式
        self._refresh_all_views()

    def _on_show_done_changed(self, checked: bool):
        self._refresh_all_views()

    def _on_show_week_view_changed(self, show: bool):
        self.todo_list_view.set_show_week_view(show)
        self.today_view.set_show_week_view(show)
        self.important_view.set_show_week_view(show)
        self.done_view.set_show_week_view(show)
        self.recent_view.set_show_week_view(show)
        for view, _ in self._category_nav_items.values():
            view.set_show_week_view(show)

    def _on_sort_rule_changed(self, rule: str):
        self._refresh_all_views()

    def _on_done_at_bottom_changed(self, checked: bool):
        self._refresh_all_views()

    def _on_floating_top_changed(self, enabled: bool):
        self.floating.set_always_on_top(enabled)

    def _setup_category_navigation(self):
        """设置分类导航"""
        categories = self.category_service.get_all()
        for cat in categories:
            if not cat.is_system:
                self._add_category_nav_item(cat)

    def _add_category_nav_item(self, cat):
        view = TodoListView(view_name=cat.name)
        view.setObjectName(f"categoryView_{cat.id}")
        view.set_time_filter_visible(True)

        self.addSubInterface(view, FluentIcon.BOOK_SHELF, cat.name,
                             position=NavigationItemPosition.SCROLL)

        cat_key = f"cat_{cat.id}"

        # 连接信号
        view.add_clicked.connect(lambda: self._open_todo_dialog())
        view.edit_clicked.connect(self._open_todo_dialog)
        view.delete_clicked.connect(self._delete_todo)
        view.toggle_done.connect(self._toggle_todo_done)
        view.reorder_requested.connect(self._on_reorder_todos)
        view.add_subtask_clicked.connect(self._open_todo_dialog_for_subtask)
        view.card_clicked.connect(self._on_card_clicked)
        view.archive_clicked.connect(self._archive_todo)
        view.float_clicked.connect(lambda k=cat_key: self._toggle_floating(k))
        view.page_changed.connect(lambda page, ps, k=cat_key: self._on_page_changed(k, page, ps))
        view.time_filter_changed.connect(
            lambda fk, k=cat_key: self._on_time_filter_changed(k, fk)
        )

        # 缓存
        self._category_nav_items[cat.id] = (view, cat.name)

    def _on_categories_changed(self):
        """分类变更时刷新导航"""
        current_order = list(settings.system_view_order)
        order_changed = self._last_system_view_order != current_order
        self._last_system_view_order = current_order

        for cat_id, (view, _) in list(self._category_nav_items.items()):
            try:
                self.removeInterface(view)
            except Exception:
                pass
            view.deleteLater()
        self._category_nav_items.clear()

        if order_changed:
            for key in current_order:
                if key in self._view_instances:
                    view = self._view_instances[key]
                    if view is None:
                        continue
                    try:
                        self.removeInterface(view, isDelete=False)
                    except Exception:
                        pass

            if self.settings_page is not None:
                try:
                    self.removeInterface(self.settings_page, isDelete=False)
                except Exception:
                    pass

            QApplication.processEvents()  # 确保 removeInterface 布局变更生效后再 addSubInterface

            for key in current_order:
                if key in self._view_instances:
                    view = self._view_instances[key]
                    if view is None:
                        continue
                    icon = self._view_map[key]
                    name = self._view_names[key]
                    try:
                        self.addSubInterface(view, icon, name)
                    except Exception:
                        pass

            if self.settings_page is not None:
                try:
                    self.addSubInterface(
                        self.settings_page, FluentIcon.SETTING,
                        "设置",
                        position=NavigationItemPosition.BOTTOM,
                    )
                except Exception:
                    pass

        self._setup_category_navigation()
        self._refresh_all_views()

    def _on_floating_pin_changed(self, pinned: bool):
        """浮窗固定状态变更"""
        settings.floating_pinned = pinned
        if pinned:
            g = self.floating.geometry()
            settings.floating_geometry = {
                "x": g.x(), "y": g.y(), "w": g.width(), "h": g.height()
            }
            settings.floating_view = self._floating_view_key
            self._update_floating_data(self._floating_view_key)
            self.floating.show()
        else:
            settings.floating_geometry = None

    def _on_floating_quick_add(self, title: str):
        """浮窗快速新建任务"""
        self.todo_service.create(title=title)
        self._refresh_all_views()

    def _on_auto_start_changed(self, enabled: bool):
        """设置开机自启"""
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0, winreg.KEY_SET_VALUE
            )
            app_name = "EasyTodo"
            if enabled:
                exe_path = sys.executable
                winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, f'"{exe_path}"')
            else:
                winreg.DeleteValue(key, app_name)
            winreg.CloseKey(key)
            InfoBar.success(
                title="成功",
                content="已开启开机自启" if enabled else "已关闭开机自启",
                parent=self, position=InfoBarPosition.TOP, duration=2000
            )
        except Exception as e:
            InfoBar.error(
                title="设置失败",
                content=str(e),
                parent=self, position=InfoBarPosition.TOP, duration=3000
            )

    def _on_resize(self, event):
        settings.window_size = (self.width(), self.height())
        super().resizeEvent(event)

    def _on_move(self, event):
        settings.window_pos = (self.x(), self.y())
        super().moveEvent(event)

    def closeEvent(self, event):
        # 最小化到系统托盘
        event.ignore()
        self.hide()
        if not self._tray_tip_shown:
            self.tray_icon.showMessage(
                APP_NAME,
                "已最小化到系统托盘，双击图标可恢复窗口",
                QSystemTrayIcon.MessageIcon.Information,
                2000
            )
            self._tray_tip_shown = True
