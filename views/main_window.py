"""主窗口"""
from __future__ import annotations

import json
import os
import sys
import winreg
from datetime import date, timedelta

from PySide6.QtCore import Qt, QTimer, QRunnable, QThreadPool, QObject, Signal
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QSystemTrayIcon, QMenu, QFileDialog, QApplication
)

import ctypes
from ctypes import wintypes
from qfluentwidgets import (
    FluentWindow, NavigationItemPosition, FluentIcon, Theme,
    setTheme, InfoBar, InfoBarPosition, MessageBox, MessageBoxBase,
    SubtitleLabel, BodyLabel
)

from config.constants import STATUS_TODO, STATUS_DONE, STATUS_ARCHIVED, APP_NAME
from config.settings import settings
from services.category_service import CategoryService, category_event_bus
from services.file_service import FileService
from services.todo_service import TodoService
from views.delete_todo_dialog import DeleteTodoDialog
from views.floating_widget import FloatingWidget
from views.recurrence_delete_dialog import RecurrenceDeleteDialog
from views.recurrence_edit_dialog import RecurrenceEditDialog
from views.settings_dialog import SettingsPage
from views.todo_detail_panel import TodoDetailDialog
from views.todo_detail_webview import TodoDetailWebView
from views.todo_dialog import TodoDialog
from views.todo_list_view import TodoListView


class _LoadTodosSignals(QObject):
    """后台加载待办数据的信号"""
    done = Signal(dict)


class _LoadViewSignals(QObject):
    """后台加载单个视图的信号"""
    done = Signal(str, list, int, int, dict)  # view_key, tree, total, generation, stats


class _LoadViewWorker(QRunnable):
    """后台线程加载单个视图数据"""

    def __init__(self, view_key: str, query_func, generation: int):
        super().__init__()
        self._signals = _LoadViewSignals()
        self._view_key = view_key
        self._query_func = query_func
        self._generation = generation
        self.setAutoDelete(True)

    @property
    def signals(self):
        return self._signals

    def run(self):
        try:
            result = self._query_func()
            if len(result) == 3:
                tree, total, stats = result
            else:
                tree, total = result
                stats = None
            self._signals.done.emit(self._view_key, tree, total, self._generation, stats or {})
        except Exception:
            self._signals.done.emit(self._view_key, [], 0, self._generation, {})


def _build_todo_tree(todos, truncate_desc=False):
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


def _inject_completed_flags(tree):
    """为任务树设置完成/归档标志，已完成任务置底"""
    from services.todo_service import TodoService
    for t in tree:
        t["_is_done"] = t.get("status", 0) == 1
        t["_is_archived"] = t.get("status", 0) == 2
        # 周期任务状态标记
        periodic_status = TodoService.get_periodic_status(t)
        t["_is_not_started"] = periodic_status == "not_started"
        t["_is_expired"] = periodic_status == "expired" and not t["_is_done"]
        for ch in t.get("children", []):
            ch["_is_done"] = ch.get("status", 0) == 1
            ch["_is_archived"] = ch.get("status", 0) == 2
            ch["_is_not_started"] = False
            ch["_is_expired"] = False
    tree.sort(key=lambda t: t.get("status", 0))


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

    def run(self):
        from services.todo_service import TodoService
        svc = TodoService()
        try:
            p = self.params
            PAGE_SIZE = 100
            sort_rules = p['sort_rules']
            show_done = p['show_done_tasks']
            view_keys = p.get('view_keys')
            result = {}

            # ---- 全部任务 ----
            if view_keys is None or 'all' in view_keys:
                due_start, due_end = p.get('all_due_start'), p.get('all_due_end')
                if show_done:
                    todos, total = svc.get_all_including_done_with_count(
                        sort_rules=sort_rules,
                        page=0, page_size=PAGE_SIZE,
                        due_start=due_start, due_end=due_end,
                        dedup_recurrence=True,
                    )
                else:
                    todos, total = svc.get_all_with_count(
                        status=STATUS_TODO, sort_rules=sort_rules,
                        page=0, page_size=PAGE_SIZE,
                        due_start=due_start, due_end=due_end,
                        dedup_recurrence=True,
                    )
                tree = _build_todo_tree(todos, truncate_desc=True)
                _inject_completed_flags(tree)
                all_stats = svc.count_all_view_stats(due_start=due_start, due_end=due_end)
                result['all'] = {'tree': tree, 'total': total, 'stats': all_stats}

            # ---- 最近待办 ----
            if view_keys is None or 'recent' in view_keys:
                due_start, due_end = p.get('recent_due_start'), p.get('recent_due_end')
                if show_done:
                    recent_todos, recent_total = svc.get_all_including_done_with_count(
                        sort_rules=sort_rules,
                        page=0, page_size=0,
                        due_start=due_start, due_end=due_end,
                        dedup_recurrence=True,
                    )
                else:
                    recent_todos, recent_total = svc.get_all_with_count(
                        status=STATUS_TODO, sort_rules=sort_rules,
                        page=0, page_size=0,
                        due_start=due_start, due_end=due_end,
                        dedup_recurrence=True,
                    )
                recent_tree = _build_todo_tree(recent_todos, truncate_desc=True)
                _inject_completed_flags(recent_tree)
                result['recent'] = {'tree': recent_tree, 'total': recent_total}

            # ---- 今日任务 ----
            if view_keys is None or 'today' in view_keys:
                if show_done:
                    today_todos, today_total = svc.get_all_including_done_with_count(
                        sort_rules=sort_rules,
                        page=0, page_size=PAGE_SIZE,
                    )
                else:
                    today_todos, today_total = svc.get_all_with_count(
                        status=STATUS_TODO, sort_rules=sort_rules,
                        page=0, page_size=PAGE_SIZE,
                    )
                today_tree = _build_todo_tree(today_todos, truncate_desc=True)
                _inject_completed_flags(today_tree)
                today_stats = svc.count_today_view_stats()
                result['today'] = {'tree': today_tree, 'total': today_total, 'stats': today_stats}

            # ---- 重要任务 ----
            if view_keys is None or 'important' in view_keys:
                due_start, due_end = p.get('imp_due_start'), p.get('imp_due_end')
                if show_done:
                    important_todos, important_total = svc.get_high_priority_including_done_with_count(
                        page=0, page_size=0,
                        due_start=due_start, due_end=due_end,
                        dedup_recurrence=True,
                    )
                else:
                    important_todos, important_total = svc.get_high_priority_with_count(
                        page=0, page_size=0,
                        due_start=due_start, due_end=due_end,
                        dedup_recurrence=True,
                    )
                important_tree = _build_todo_tree(important_todos, truncate_desc=True)
                _inject_completed_flags(important_tree)
                result['important'] = {'tree': important_tree, 'total': important_total}

            # ---- 已完成/已归档 ----
            if view_keys is None or 'done' in view_keys:
                done_filter = p.get('done_filter', 'done')
                if done_filter == 'archived':
                    done_todos, done_total = svc.get_all_with_count(
                        status=STATUS_ARCHIVED, page=0, page_size=PAGE_SIZE,
                    )
                else:
                    done_todos, done_total = svc.get_all_with_count(
                        status=STATUS_DONE, page=0, page_size=PAGE_SIZE,
                    )
                done_tree = _build_todo_tree(done_todos, truncate_desc=True)
                _inject_completed_flags(done_tree)
                result['done'] = {'tree': done_tree, 'total': done_total}

            # ---- 分类视图 ----
            cat_results = {}
            for cat_id, due_start, due_end in p.get('categories', []):
                if view_keys is not None and f"cat_{cat_id}" not in view_keys:
                    continue
                cat_todos, cat_total = svc.get_by_category_with_count(
                    cat_id, page=0, page_size=PAGE_SIZE,
                    due_start=due_start, due_end=due_end,
                    dedup_recurrence=True,
                )
                cat_tree = _build_todo_tree(cat_todos, truncate_desc=True)
                _inject_completed_flags(cat_tree)
                cat_results[cat_id] = {'tree': cat_tree, 'total': cat_total}
            result['categories'] = cat_results

            self._signals.done.emit(result)
        except Exception:
            self._signals.done.emit({})


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
        # 初始化完成前禁止任何子界面被渲染到屏幕，避免 Windows 上短暂弹出空窗口
        self.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        self.stackedWidget.setAnimationEnabled(False)

        self.todo_service = TodoService()
        self.category_service = CategoryService()
        self.file_service = FileService()

        # 当前视图标识
        self._current_view_key = "all"
        self._floating_view_key = "all"
        self._tray_tip_shown = False
        self._detail_dialog = None  # 任务详情对话框引用
        self._loaded_views: set[str] = set()  # 已加载过数据的视图集合
        self._load_generation: int = 0  # 异步加载代数，防止旧请求覆盖新数据
        self._view_load_in_progress: set[str] = set()  # 正在异步加载的视图集合

        # 分类导航项缓存 {category_id: (interface, name)}
        self._category_nav_items: dict[int, tuple] = {}

        # 防抖定时器：避免开关快速切换时重复触发重操作
        self._refresh_debounce_timer = QTimer(self)
        self._refresh_debounce_timer.setSingleShot(True)
        self._refresh_debounce_timer.setInterval(150)  # 150ms 防抖
        self._refresh_debounce_timer.timeout.connect(self._do_debounced_refresh)

        self._debounced_refresh_pending: str | None = None  # "all" | "current"

        self._setup_ui()
        self._setup_navigation()

        # 根据导航顺序确定初始视图（FluentWindow 默认显示第一个添加的视图）
        order = settings.system_view_order
        for key in order:
            if key in self._view_instances:
                self._current_view_key = key
                break

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

        self._load_todos(view_keys={self._current_view_key})

        self.stackedWidget.setAnimationEnabled(True)
        self.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, False)

        # 双栏模式：延迟预热 webview 子进程，让用户首次点击即可秒开
        # 子进程在后台初始化 WebView2 引擎，不阻塞主界面
        if settings.dialog_mode == "widescreen":
            QTimer.singleShot(3000, self._prewarm_webview)

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
            "all": TodoListView(parent=self, view_name="全部任务"),
            "today": TodoListView(parent=self, view_name="今日任务"),
            "important": TodoListView(parent=self, view_name="重要任务"),
            "done": TodoListView(parent=self, view_name="已完成", readonly=True),
            "recent": TodoListView(parent=self, view_name="最近待办"),
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

        # 日程视图弹窗
        self.settings_page = SettingsPage(parent=self)
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
            # 恢复浮窗模式和按钮可见性
            self.floating.set_view_key(self._floating_view_key)
            if self._floating_view_key == "important":
                self.floating.set_mode("quadrant")
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
            # 根据视图设置浮窗模式
            self.floating.set_view_key(self._floating_view_key)
            if self._floating_view_key == "important":
                self.floating.set_mode("quadrant")
            else:
                self.floating.set_mode("list")
            self._update_floating_data(self._floating_view_key)
        self.floating.show()
        self.floating.activateWindow()

    def _tray_quit(self):
        """从托盘退出应用"""
        self._unregister_global_hotkey()
        settings.flush()
        self.tray_icon.hide()
        self.floating.close()
        # 关闭长驻 webview 子进程
        try:
            from views.todo_detail_webview import stop_webview
            stop_webview()
        except Exception:
            pass
        QApplication.quit()

    def _prewarm_webview(self):
        """预热 webview 子进程：提前启动并初始化引擎，首次点击即可秒开。"""
        try:
            from views.todo_detail_webview import ensure_webview_running
            ensure_webview_running()
        except Exception:
            pass

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
        self.settings_page.floating_top_changed.connect(self._on_floating_top_changed)
        self.settings_page.manual_refresh_clicked.connect(self._manual_refresh)
        self.settings_page.export_json_clicked.connect(self._export_json)
        self.settings_page.export_excel_clicked.connect(self._export_excel)
        self.settings_page.import_btn.clicked.connect(self._import_data)
        # 分类变更走事件总线订阅，settings_page 自身不再需要 categories_changed 信号

        # 快捷键
        self._setup_shortcuts()
        self.settings_page.shortcut_new_task_changed.connect(self.update_shortcut_new_task)

        # 导航切换时记录当前视图
        self.stackedWidget.currentChanged.connect(self._on_view_changed)

        self.resizeEvent = self._on_resize
        self.moveEvent = self._on_move

    # ---- 全局热键常量 ----
    _HOTKEY_ID_NEW_TASK = 1
    _WM_HOTKEY = 0x0312

    _MOD_MAP = {
        "Ctrl": 0x0002,   # MOD_CONTROL
        "Shift": 0x0004,  # MOD_SHIFT
        "Alt": 0x0001,    # MOD_ALT
    }

    _KEY_MAP = {
        "0": 0x30, "1": 0x31, "2": 0x32, "3": 0x33, "4": 0x34,
        "5": 0x35, "6": 0x36, "7": 0x37, "8": 0x38, "9": 0x39,
        "A": 0x41, "B": 0x42, "C": 0x43, "D": 0x44, "E": 0x45,
        "F": 0x46, "G": 0x47, "H": 0x48, "I": 0x49, "J": 0x4A,
        "K": 0x4B, "L": 0x4C, "M": 0x4D, "N": 0x4E, "O": 0x4F,
        "P": 0x50, "Q": 0x51, "R": 0x52, "S": 0x53, "T": 0x54,
        "U": 0x55, "V": 0x56, "W": 0x57, "X": 0x58, "Y": 0x59,
        "Z": 0x5A,
        "F1": 0x70, "F2": 0x71, "F3": 0x72, "F4": 0x73,
        "F5": 0x74, "F6": 0x75, "F7": 0x76, "F8": 0x77,
        "F9": 0x78, "F10": 0x79, "F11": 0x7A, "F12": 0x7B,
        "Space": 0x20, "Return": 0x0D, "Backspace": 0x08,
        "Tab": 0x09, "Escape": 0x1B, "Delete": 0x2E,
        "Insert": 0x2D, "Home": 0x24, "End": 0x23,
        "Page Up": 0x21, "Page Down": 0x22,
        "Left": 0x25, "Up": 0x26, "Right": 0x27, "Down": 0x28,
    }

    @staticmethod
    def _parse_shortcut(key_str: str):
        """解析快捷键字符串为 (modifiers, vk) 元组"""
        if not key_str:
            return None, None
        parts = key_str.split("+")
        mods = 0
        vk = None
        for p in parts:
            p = p.strip()
            if p in MainWindow._MOD_MAP:
                mods |= MainWindow._MOD_MAP[p]
            else:
                vk = MainWindow._KEY_MAP.get(p)
        return mods, vk

    def _setup_shortcuts(self):
        """注册全局快捷键"""
        self._register_global_hotkey()

    def _register_global_hotkey(self):
        """注册 Windows 全局热键"""
        self._unregister_global_hotkey()
        mods, vk = self._parse_shortcut(settings.shortcut_new_task)
        if mods is None or vk is None:
            return
        try:
            ctypes.windll.user32.RegisterHotKey(
                int(self.winId()), self._HOTKEY_ID_NEW_TASK, mods, vk
            )
        except Exception:
            pass

    def _unregister_global_hotkey(self):
        """注销 Windows 全局热键"""
        try:
            ctypes.windll.user32.UnregisterHotKey(
                int(self.winId()), self._HOTKEY_ID_NEW_TASK
            )
        except Exception:
            pass

    def update_shortcut_new_task(self, key_str: str):
        """更新新建任务快捷键"""
        self._register_global_hotkey()

    def nativeEvent(self, eventType, message):
        """处理 Windows 原生消息，响应全局热键"""
        if eventType == b"windows_generic_MSG":
            msg = ctypes.wintypes.MSG.from_address(int(message))
            if msg.message == self._WM_HOTKEY and msg.wParam == self._HOTKEY_ID_NEW_TASK:
                self._on_hotkey_new_task()
                return True, 0
        return super().nativeEvent(eventType, message)

    def _on_hotkey_new_task(self):
        """全局热键触发：打开新建任务对话框"""
        # 防止重复触发：如果已有对话框打开则激活它
        if hasattr(self, '_todo_dialog') and self._todo_dialog is not None and self._todo_dialog.isVisible():
            self._todo_dialog.raise_()
            self._todo_dialog.activateWindow()
            return
        self._open_todo_dialog()

    def _on_view_changed(self, index):
        """导航切换时记录当前视图，并按需加载未加载的视图"""
        widget = self.stackedWidget.widget(index)
        view_key = None
        if widget == self.todo_list_view:
            view_key = "all"
        elif widget == self.today_view:
            view_key = "today"
            self._reset_today_filter()
        elif widget == self.important_view:
            view_key = "important"
        elif widget == self.done_view:
            view_key = "done"
        elif widget == self.recent_view:
            view_key = "recent"
        else:
            for cat_id, (view, name) in self._category_nav_items.items():
                if widget == view:
                    view_key = f"cat_{cat_id}"
                    break

        if view_key:
            self._current_view_key = view_key
            # 懒加载：如果该视图尚未加载过数据，则加载
            if view_key not in self._loaded_views:
                self._load_view_async(view_key)

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
        # 控制四象限按钮可见性
        self.floating.set_view_key(key)
        # 重要任务视图默认打开四象限模式
        if key == "important":
            self.floating.set_mode("quadrant")
        else:
            self.floating.set_mode("list")
        self._update_floating_data(key)
        self.floating.show()
        self.floating.activateWindow()

    def _update_floating_data(self, view_key: str):
        """根据视图标识更新浮窗数据"""
        view = self._get_view_by_key(view_key)
        filter_key = view.current_time_filter() if view else "all"
        due_start, due_end = self._get_date_range(filter_key, view) if view else (None, None)

        # 处理分类视图
        if view_key.startswith("cat_"):
            cat_id = int(view_key.split("_")[1])
            cat_name = self._category_nav_items.get(cat_id, (None, "任务列表"))[1]
            self.floating.title_label.setText(cat_name)
            todos = self.todo_service.get_by_category(
                cat_id, dedup_recurrence=True,
                due_start=due_start, due_end=due_end,
            )
            tree = self._build_todo_tree(todos, truncate_desc=True)
            self._inject_completed_dates(tree)
            self.floating.set_todos(tree)
            return

        title_map = {"all": "全部任务", "today": "今日任务", "important": "重要任务", "done": "已完成",
                     "recent": "最近待办"}
        self.floating.title_label.setText(title_map.get(view_key, "任务列表"))

        if view_key == "done":
            done_filter = getattr(self, '_done_filter', 'done')
            done_todos = self.todo_service.get_all(
                status=STATUS_ARCHIVED if done_filter == 'archived' else STATUS_DONE,
            )
            todos = done_todos
        elif view_key == "today":
            if settings.show_done_tasks:
                todos = self.todo_service.get_all_including_done(
                    sort_rules=settings.sort_rules,
                )
            else:
                todos = self.todo_service.get_all(
                    status=STATUS_TODO, sort_rules=settings.sort_rules
                )
        elif view_key == "important":
            if settings.show_done_tasks:
                todos = self.todo_service.get_high_priority_including_done(
                    dedup_recurrence=True,
                    due_start=due_start, due_end=due_end,
                )
            else:
                todos = self.todo_service.get_high_priority(
                    dedup_recurrence=True,
                    due_start=due_start, due_end=due_end,
                )
        elif view_key == "recent":
            if settings.show_done_tasks:
                todos = self.todo_service.get_all_including_done(
                    sort_rules=settings.sort_rules,
                    dedup_recurrence=True,
                    due_start=due_start, due_end=due_end,
                )
            else:
                todos = self.todo_service.get_all(
                    status=STATUS_TODO, sort_rules=settings.sort_rules,
                    dedup_recurrence=True,
                    due_start=due_start, due_end=due_end,
                )
        else:
            if settings.show_done_tasks:
                todos = self.todo_service.get_all_including_done(
                    sort_rules=settings.sort_rules,
                    dedup_recurrence=True,
                    due_start=due_start, due_end=due_end,
                )
            else:
                todos = self.todo_service.get_all(
                    status=STATUS_TODO, sort_rules=settings.sort_rules,
                    dedup_recurrence=True,
                    due_start=due_start, due_end=due_end,
                )

        tree = self._build_todo_tree(todos, truncate_desc=True)
        if view_key == "today":
            self._inject_completed_dates(tree)
            tree = self.today_view._filter_todos_by_date(tree, date.today())
        elif view_key == "recent":
            self._inject_completed_dates(tree)
            tree = self._sort_for_recent(tree)
        else:
            self._inject_completed_dates(tree)
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
        """执行每日维护：自动延期 + 刷新列表"""
        self._last_refresh_date = date.today()
        self._start_postpone_worker()

    def _manual_refresh(self):
        """手动刷新任务"""
        if getattr(self, '_refresh_in_progress', False):
            return
        self._refresh_in_progress = True
        self.settings_page.manual_refresh_btn.setEnabled(False)
        InfoBar.info(title="刷新中", content="正在刷新列表...", parent=self,
                     position=InfoBarPosition.TOP, duration=1500)
        self._start_postpone_worker(show_done_info=True)

    def _start_postpone_worker(self, show_done_info=False):
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
                svc.process_auto_postpone()
                self._signals.done.emit({})

        def _on_done():
            self._refresh_in_progress = False
            self.settings_page.manual_refresh_btn.setEnabled(True)
            self._load_todos()
            if show_done_info:
                InfoBar.success(title="刷新完成", content="列表已更新", parent=self,
                                position=InfoBarPosition.TOP, duration=2000)

        worker = _RefreshWorker(_on_done)
        QThreadPool.globalInstance().start(worker)

    def changeEvent(self, event):
        """窗口激活时检测跨天，应对系统休眠"""
        super().changeEvent(event)
        if event.type() == event.Type.ActivationChange and self.isActiveWindow():
            self._check_daily_refresh()

    def _build_todo_tree(self, todos: list, truncate_desc: bool = False) -> list[dict]:
        """在内存中构建任务树形结构"""
        return _build_todo_tree(todos, truncate_desc=truncate_desc)

    def _inject_completed_dates(self, tree: list[dict]):
        """为任务树设置完成/归档标志"""
        _inject_completed_flags(tree)

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

    def _load_todos(self, view_keys: set[str] | None = None):
        """加载待办数据（后台线程查询，避免阻塞 UI）

        :param view_keys: 要加载的视图 key 集合，None 表示全部
        """
        if getattr(self, '_load_in_progress', False):
            self._pending_load = True
            self._pending_view_keys = view_keys
            return

        self._load_in_progress = True
        self._pending_load = False

        if view_keys is None:
            self.todo_list_view.show_loading()
            self.today_view.show_loading()
            self.important_view.show_loading()
            self.done_view.show_loading()
            self.recent_view.show_loading()
            for cat_id, (view, _) in self._category_nav_items.items():
                view.show_loading()
        else:
            for key in view_keys:
                v = self._get_view_by_key(key)
                if v:
                    v.show_loading()

        params = self._collect_load_params()
        params['view_keys'] = view_keys
        worker = _LoadTodosWorker(params)
        worker.signals.done.connect(self._on_todos_loaded)
        QThreadPool.globalInstance().start(worker)

    def _load_view(self, view_key: str):
        """加载单个视图的数据"""
        PAGE_SIZE = 100
        sort_rules = settings.sort_rules
        show_done = settings.show_done_tasks

        view = self._get_view_by_key(view_key)
        if not view:
            return

        if view_key == "all":
            due_start, due_end = self._get_date_range(
                view.current_time_filter(), view)
            if show_done:
                todos, total = self.todo_service.get_all_including_done_with_count(
                    sort_rules=sort_rules,
                    page=0, page_size=PAGE_SIZE,
                    due_start=due_start, due_end=due_end,
                    dedup_recurrence=True,
                )
            else:
                todos, total = self.todo_service.get_all_with_count(
                    status=STATUS_TODO, sort_rules=sort_rules,
                    page=0, page_size=PAGE_SIZE,
                    due_start=due_start, due_end=due_end,
                    dedup_recurrence=True,
                )
            tree = self._build_todo_tree(todos, truncate_desc=True)
            self._inject_completed_dates(tree)
            all_stats = self.todo_service.count_all_view_stats(due_start=due_start, due_end=due_end)
            view.set_todos(tree, total_count=total, stats=all_stats)

        elif view_key == "recent":
            due_start, due_end = self._get_date_range(
                view.current_time_filter(), view)
            if show_done:
                recent_todos, recent_total = self.todo_service.get_all_including_done_with_count(
                    sort_rules=sort_rules,
                    page=0, page_size=0,
                    due_start=due_start, due_end=due_end,
                    dedup_recurrence=True,
                )
            else:
                recent_todos, recent_total = self.todo_service.get_all_with_count(
                    status=STATUS_TODO, sort_rules=sort_rules,
                    page=0, page_size=0,
                    due_start=due_start, due_end=due_end,
                    dedup_recurrence=True,
                )
            recent_tree = self._build_todo_tree(recent_todos, truncate_desc=True)
            self._inject_completed_dates(recent_tree)
            view.set_todos(recent_tree, total_count=recent_total)

        elif view_key == "today":
            if show_done:
                todos, total = self.todo_service.get_all_including_done_with_count(
                    sort_rules=sort_rules,
                    page=0, page_size=PAGE_SIZE,
                )
            else:
                todos, total = self.todo_service.get_all_with_count(
                    status=STATUS_TODO, sort_rules=sort_rules,
                    page=0, page_size=PAGE_SIZE,
                )
            tree = self._build_todo_tree(todos, truncate_desc=True)
            self._inject_completed_dates(tree)
            view._filter_date = date.today()
            view.week_view.set_selected_date(date.today())
            today_stats = self.todo_service.count_today_view_stats()
            view.set_todos(tree, total_count=total, stats=today_stats)

        elif view_key == "important":
            due_start, due_end = self._get_date_range(
                view.current_time_filter(), view)
            if show_done:
                important_todos, important_total = self.todo_service.get_high_priority_including_done_with_count(
                    page=0, page_size=0,
                    due_start=due_start, due_end=due_end,
                    dedup_recurrence=True,
                )
            else:
                important_todos, important_total = self.todo_service.get_high_priority_with_count(
                    page=0, page_size=0,
                    due_start=due_start, due_end=due_end,
                    dedup_recurrence=True,
                )
            important_tree = self._build_todo_tree(important_todos, truncate_desc=True)
            self._inject_completed_dates(important_tree)
            view.set_todos(important_tree, total_count=important_total)

        elif view_key == "done":
            done_filter = getattr(self, '_done_filter', 'done')
            status = STATUS_ARCHIVED if done_filter == 'archived' else STATUS_DONE
            todos, total = self.todo_service.get_all_with_count(
                status=status, page=0, page_size=PAGE_SIZE,
            )
            tree = self._build_todo_tree(todos, truncate_desc=True)
            self._inject_completed_dates(tree)
            view.set_todos(tree, total_count=total)

        elif view_key.startswith("cat_"):
            cat_id = int(view_key.split("_")[1])
            cat_filter_key = view.current_time_filter()
            cat_due_start, cat_due_end = self._get_date_range(cat_filter_key, view)
            todos, total = self.todo_service.get_by_category_with_count(
                cat_id, page=0, page_size=PAGE_SIZE,
                due_start=cat_due_start, due_end=cat_due_end,
                dedup_recurrence=True,
            )
            tree = self._build_todo_tree(todos, truncate_desc=True)
            self._inject_completed_dates(tree)
            view.set_todos(tree, total_count=total)

        self._loaded_views.add(view_key)

    def _load_view_async(self, view_key: str):
        """异步加载单个视图数据"""
        if view_key in self._view_load_in_progress:
            return
        view = self._get_view_by_key(view_key)
        if not view:
            return
        self._view_load_in_progress.add(view_key)

        view.show_loading()
        self._load_generation += 1
        gen = self._load_generation

        sort_rules = settings.sort_rules
        show_done = settings.show_done_tasks
        PAGE_SIZE = 100

        if view_key == "all":
            due_start, due_end = self._get_date_range(view.current_time_filter(), view)
            if show_done:
                def query():
                    svc = TodoService()
                    todos, total = svc.get_all_including_done_with_count(
                        sort_rules=sort_rules,
                        page=0, page_size=PAGE_SIZE,
                        due_start=due_start, due_end=due_end,
                        dedup_recurrence=True,
                    )
                    tree = _build_todo_tree(todos, truncate_desc=True)
                    _inject_completed_flags(tree)
                    stats = svc.count_all_view_stats(due_start=due_start, due_end=due_end)
                    return tree, total, stats
            else:
                def query():
                    svc = TodoService()
                    todos, total = svc.get_all_with_count(
                        status=STATUS_TODO, sort_rules=sort_rules,
                        page=0, page_size=PAGE_SIZE,
                        due_start=due_start, due_end=due_end,
                        dedup_recurrence=True,
                    )
                    tree = _build_todo_tree(todos, truncate_desc=True)
                    _inject_completed_flags(tree)
                    stats = svc.count_all_view_stats(due_start=due_start, due_end=due_end)
                    return tree, total, stats

        elif view_key == "recent":
            due_start, due_end = self._get_date_range(view.current_time_filter(), view)
            if show_done:
                def query():
                    svc = TodoService()
                    todos, total = svc.get_all_including_done_with_count(
                        sort_rules=sort_rules,
                        page=0, page_size=0,
                        due_start=due_start, due_end=due_end,
                        dedup_recurrence=True,
                    )
                    tree = _build_todo_tree(todos, truncate_desc=True)
                    _inject_completed_flags(tree)
                    return tree, total
            else:
                def query():
                    svc = TodoService()
                    todos, total = svc.get_all_with_count(
                        status=STATUS_TODO, sort_rules=sort_rules,
                        page=0, page_size=0,
                        due_start=due_start, due_end=due_end,
                        dedup_recurrence=True,
                    )
                    tree = _build_todo_tree(todos, truncate_desc=True)
                    _inject_completed_flags(tree)
                    return tree, total

        elif view_key == "today":
            if show_done:
                def query():
                    svc = TodoService()
                    todos, total = svc.get_all_including_done_with_count(
                        sort_rules=sort_rules,
                        page=0, page_size=PAGE_SIZE,
                    )
                    tree = _build_todo_tree(todos, truncate_desc=True)
                    _inject_completed_flags(tree)
                    stats = svc.count_today_view_stats()
                    return tree, total, stats
            else:
                def query():
                    svc = TodoService()
                    todos, total = svc.get_all_with_count(
                        status=STATUS_TODO, sort_rules=sort_rules,
                        page=0, page_size=PAGE_SIZE,
                    )
                    tree = _build_todo_tree(todos, truncate_desc=True)
                    _inject_completed_flags(tree)
                    stats = svc.count_today_view_stats()
                    return tree, total, stats

        elif view_key == "important":
            due_start, due_end = self._get_date_range(view.current_time_filter(), view)
            if show_done:
                def query():
                    svc = TodoService()
                    todos, total = svc.get_high_priority_including_done_with_count(
                        page=0, page_size=0,
                        due_start=due_start, due_end=due_end,
                        dedup_recurrence=True,
                    )
                    tree = _build_todo_tree(todos, truncate_desc=True)
                    _inject_completed_flags(tree)
                    return tree, total
            else:
                def query():
                    svc = TodoService()
                    todos, total = svc.get_high_priority_with_count(
                        page=0, page_size=0,
                        due_start=due_start, due_end=due_end,
                        dedup_recurrence=True,
                    )
                    tree = _build_todo_tree(todos, truncate_desc=True)
                    _inject_completed_flags(tree)
                    return tree, total

        elif view_key == "done":
            done_filter = getattr(self, '_done_filter', 'done')
            status = STATUS_ARCHIVED if done_filter == 'archived' else STATUS_DONE
            def query():
                svc = TodoService()
                todos, total = svc.get_all_with_count(
                    status=status, page=0, page_size=PAGE_SIZE,
                )
                tree = _build_todo_tree(todos, truncate_desc=True)
                _inject_completed_flags(tree)
                return tree, total

        elif view_key.startswith("cat_"):
            cat_id = int(view_key.split("_")[1])
            cat_filter_key = view.current_time_filter()
            cat_due_start, cat_due_end = self._get_date_range(cat_filter_key, view)
            def query():
                svc = TodoService()
                todos, total = svc.get_by_category_with_count(
                    cat_id, page=0, page_size=PAGE_SIZE,
                    due_start=cat_due_start, due_end=cat_due_end,
                    dedup_recurrence=True,
                )
                tree = _build_todo_tree(todos, truncate_desc=True)
                _inject_completed_flags(tree)
                return tree, total
        else:
            self._view_load_in_progress.discard(view_key)
            return

        worker = _LoadViewWorker(view_key, query, gen)
        worker.signals.done.connect(self._on_view_loaded)
        QThreadPool.globalInstance().start(worker)

    def _on_view_loaded(self, view_key: str, tree: list, total: int, generation: int, stats: dict = None):
        """异步加载完成回调"""
        self._view_load_in_progress.discard(view_key)
        if generation < self._load_generation:
            return

        view = self._get_view_by_key(view_key)
        if not view:
            return

        if view_key == "today":
            view._filter_date = date.today()
            view.week_view.set_selected_date(date.today())

        view.set_todos(tree, total_count=total, stats=stats or None)
        self._loaded_views.add(view_key)

    def _refresh_current_view(self):
        """只刷新当前可见的视图"""
        self._schedule_debounced_refresh("current")

    def _refresh_all_views(self):
        """刷新所有视图"""
        self._schedule_debounced_refresh("all")

    def _schedule_debounced_refresh(self, level: str):
        if self._debounced_refresh_pending == "all" and level == "current":
            return
        self._debounced_refresh_pending = level
        self._refresh_debounce_timer.start()

    def _do_debounced_refresh(self):
        """执行防抖后的实际刷新"""
        level = self._debounced_refresh_pending
        self._debounced_refresh_pending = None
        if level == "all":
            self._loaded_views.clear()
            self._load_todos()
        elif level == "current":
            current = self._current_view_key
            self._loaded_views.clear()
            self._load_view(current)
            if self.floating.isVisible():
                self._update_floating_data(self._floating_view_key)

    def _refresh_all_views_immediate(self):
        """立即刷新所有视图"""
        self._loaded_views.clear()
        self._load_todos()

    def _refresh_current_view_immediate(self):
        """立即刷新当前视图"""
        current = self._current_view_key
        self._loaded_views.clear()
        self._load_view(current)
        if self.floating.isVisible():
            self._update_floating_data(self._floating_view_key)

    def _collect_load_params(self):
        """收集查询参数"""
        all_filter = self.todo_list_view.current_time_filter()
        recent_filter = self.recent_view.current_time_filter()
        imp_filter = self.important_view.current_time_filter()

        all_due_start, all_due_end = self._get_date_range(all_filter, self.todo_list_view)
        recent_due_start, recent_due_end = self._get_date_range(recent_filter, self.recent_view)
        imp_due_start, imp_due_end = self._get_date_range(imp_filter, self.important_view)

        categories = []
        for cat_id, (view, _) in self._category_nav_items.items():
            cat_filter = view.current_time_filter()
            cat_due_start, cat_due_end = self._get_date_range(cat_filter, view)
            categories.append((cat_id, cat_due_start, cat_due_end))

        return {
            'sort_rules': settings.sort_rules,
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
            self.todo_list_view.set_todos(r['tree'], total_count=r['total'],
                                          stats=r.get('stats'))
            self._loaded_views.add("all")

        if 'recent' in result:
            r = result['recent']
            self.recent_view.set_todos(r['tree'], total_count=r['total'])
            self._loaded_views.add("recent")

        if 'today' in result:
            r = result['today']
            self.today_view._filter_date = date.today()
            self.today_view.week_view.set_selected_date(date.today())
            self.today_view.set_todos(r['tree'], total_count=r['total'],
                                      stats=r.get('stats'))
            self._loaded_views.add("today")

        if 'important' in result:
            r = result['important']
            self.important_view.set_todos(r['tree'], total_count=r['total'])
            self._loaded_views.add("important")

        if 'done' in result:
            r = result['done']
            self.done_view.set_todos(r['tree'], total_count=r['total'])
            self._loaded_views.add("done")

        if 'categories' in result:
            for cat_id, cat_data in result['categories'].items():
                if cat_id in self._category_nav_items:
                    view, _ = self._category_nav_items[cat_id]
                    view.set_todos(cat_data['tree'], total_count=cat_data['total'])
                    self._loaded_views.add(f"cat_{cat_id}")

        if self.floating.isVisible():
            self._update_floating_data(self._floating_view_key)

        # 如果在加载期间有新的刷新请求，执行延迟刷新
        if getattr(self, '_pending_load', False):
            self._pending_load = False
            self._load_todos(view_keys=getattr(self, '_pending_view_keys', None))

    def _on_page_changed(self, view_key: str, page: int, page_size: int):
        sort_rules = settings.sort_rules

        if view_key in ("done", "today"):
            if view_key == "today":
                if settings.show_done_tasks:
                    todos = self.todo_service.get_all_including_done(
                        sort_rules=sort_rules,
                        page=page, page_size=page_size,
                    )
                else:
                    todos = self.todo_service.get_all(
                        status=STATUS_TODO, sort_rules=sort_rules,
                        page=page, page_size=page_size,
                    )
                tree = self._build_todo_tree(todos, truncate_desc=True)
                self._inject_completed_dates(tree)
                today_stats = self.todo_service.count_today_view_stats()
                self.today_view.set_todos(tree, stats=today_stats)
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
        # 防止重复点击：若已有任务弹窗打开，则激活现有窗口而不是新建
        if hasattr(self, '_todo_dialog') and self._todo_dialog is not None and self._todo_dialog.isVisible():
            self._todo_dialog.raise_()
            self._todo_dialog.activateWindow()
            return

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
        self._todo_dialog = dialog
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()
        dialog.exec()
        self._todo_dialog = None

    def _on_todo_saved(self, data: dict):
        temp_files = data.pop("temp_files", [])
        pending_paste_id = data.pop("pending_paste_id", None)
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
            # 任务创建失败，清理粘贴图暂存（避免遗留）
            if pending_paste_id:
                try:
                    self.file_service.cleanup_pending(pending_paste_id)
                except Exception:
                    pass
            return

        # 保存关联文件
        if todo and temp_files:
            for file_path in temp_files:
                try:
                    self.file_service.save_file(todo.id, file_path)
                except Exception as e:
                    print(f"保存文件失败: {e}")

        # 迁移粘贴图暂存到 task_{todo_id}/（与新建任务上传文件路径完全一致）
        if todo and pending_paste_id:
            try:
                self.file_service.save_paste_to_task(pending_paste_id, todo.id)
            except Exception as e:
                print(f"迁移粘贴图失败: {e}")

        if todo:
            self._refresh_current_view_immediate()
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
                self._refresh_current_view_immediate()
                InfoBar.success(title="已删除", content="任务已删除", parent=self,
                                position=InfoBarPosition.TOP, duration=2000)
            return

        dlg = DeleteTodoDialog(todo_id, file_count, parent=self)
        if dlg.exec():
            if self.todo_service.delete(todo_id):
                if dlg.delete_files:
                    self.file_service.delete_task_folder(todo_id)
                self._refresh_current_view_immediate()
                InfoBar.success(title="已删除", content="任务已删除", parent=self,
                                position=InfoBarPosition.TOP, duration=2000)

    def _toggle_todo_done(self, todo_id: int):
        if self.todo_service.toggle_done(todo_id):
            self._refresh_current_view_immediate()

    def _archive_todo(self, todo_id: int):
        msg = MessageBox("确认归档", "确定要归档这个任务吗？归档后可在「已完成」页面筛选查看。", self)
        msg.yesButton.setText("归档")
        msg.cancelButton.setText("取消")
        if msg.exec():
            self.todo_service.update(todo_id, status=STATUS_ARCHIVED)
            self._refresh_current_view_immediate()
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
            self._refresh_current_view_immediate()
            InfoBar.success(title="已归档", content=f"已归档 {count} 个任务", parent=self,
                            position=InfoBarPosition.TOP, duration=2000)

    def _on_done_filter_changed(self, filter_key: str):
        PAGE_SIZE = 100
        self._done_filter = filter_key
        self.done_view.archive_all_btn.setVisible(filter_key == 'done')
        status = STATUS_ARCHIVED if filter_key == 'archived' else STATUS_DONE
        todos, total = self.todo_service.get_all_with_count(
            status=status, page=0, page_size=PAGE_SIZE,
        )
        tree = self._build_todo_tree(todos, truncate_desc=True)
        self._inject_completed_dates(tree)
        self.done_view.set_todos(tree, total_count=total)

    @staticmethod
    def _get_date_range(filter_key: str, view=None):
        if filter_key == "custom" and view is not None:
            return view.get_custom_date_range()
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

        if view_key in ("done", "today"):
            return

        view = self._get_view_by_key(view_key)
        if not view:
            return

        filter_key = view.current_time_filter()
        due_start, due_end = self._get_date_range(filter_key, view)

        if view_key == "all":
            if settings.show_done_tasks:
                todos, total = self.todo_service.get_all_including_done_with_count(
                    sort_rules=sort_rules,
                    page=page, page_size=PAGE_SIZE,
                    due_start=due_start, due_end=due_end,
                    dedup_recurrence=True,
                )
            else:
                todos, total = self.todo_service.get_all_with_count(
                    status=STATUS_TODO, sort_rules=sort_rules,
                    page=page, page_size=PAGE_SIZE,
                    due_start=due_start, due_end=due_end,
                    dedup_recurrence=True,
                )
            tree = self._build_todo_tree(todos, truncate_desc=True)
            self._inject_completed_dates(tree)
            all_stats = self.todo_service.count_all_view_stats(due_start=due_start, due_end=due_end)
            view.set_todos(tree, total_count=total, stats=all_stats)

        elif view_key == "important":
            todos, total = self.todo_service.get_high_priority_with_count(
                page=0, page_size=0,
                due_start=due_start, due_end=due_end,
                dedup_recurrence=True,
            )
            tree = self._build_todo_tree(todos, truncate_desc=True)
            self._inject_completed_dates(tree)
            view.set_todos(tree, total_count=total)

        elif view_key == "recent":
            if settings.show_done_tasks:
                recent_todos, recent_total = self.todo_service.get_all_including_done_with_count(
                    sort_rules=sort_rules,
                    page=0, page_size=0,
                    due_start=due_start, due_end=due_end,
                    dedup_recurrence=True,
                )
            else:
                recent_todos, recent_total = self.todo_service.get_all_with_count(
                    status=STATUS_TODO, sort_rules=sort_rules,
                    page=0, page_size=0,
                    due_start=due_start, due_end=due_end,
                    dedup_recurrence=True,
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
                cat_due_start, cat_due_end = self._get_date_range(cat_filter_key, cat_view)
                todos, total = self.todo_service.get_by_category_with_count(
                    cat_id, page=page, page_size=PAGE_SIZE,
                    due_start=cat_due_start, due_end=cat_due_end,
                    dedup_recurrence=True,
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

    def _calc_popup_position(self) -> tuple[int, int] | None:
        """计算双栏模式任务详情弹窗的位置:紧贴主窗口右侧 10px,垂直居中。

        若右侧放不下,回退到主窗口左侧;再放不下则夹回当前屏幕工作区。
        """
        try:
            from PySide6.QtWidgets import QApplication
            main_geo = self.frameGeometry()
            screen = (
                QApplication.screenAt(main_geo.center())
                or QApplication.primaryScreen()
            )
            if screen is None:
                return None
            screen_geo = screen.availableGeometry()
            popup_w, popup_h = 900, 720
            # 优先:主窗口右侧 10px
            x = main_geo.right() + 10
            y = main_geo.top() + (main_geo.height() - popup_h) // 2
            if x + popup_w > screen_geo.right():
                # 右侧放不下,放到主窗口左侧
                x = main_geo.left() - popup_w - 10
            if x < screen_geo.left():
                x = screen_geo.left()
            if y + popup_h > screen_geo.bottom():
                y = max(screen_geo.top(), screen_geo.bottom() - popup_h)
            if y < screen_geo.top():
                y = screen_geo.top()
            return (int(x), int(y))
        except Exception:
            return None

    def _on_card_clicked(self, todo_id: int):
        """父任务卡片点击 - 弹出详情对话框"""
        todo = self.todo_service.get_by_id(todo_id)
        if todo:
            todo_tree = self._build_todo_tree([todo])
            self._inject_completed_dates(todo_tree)
            if not todo_tree:
                return
            node = todo_tree[0]
            if settings.dialog_mode == "widescreen":
                # 双栏模式:用 pywebview 子进程渲染只读预览
                # webview 窗口在独立子进程中,关闭不影响主程序
                popup_pos = self._calc_popup_position()
                preview = TodoDetailWebView(node, todo_id=node["id"], popup_pos=popup_pos)
                preview.show()
                return
            dialog = TodoDetailDialog(node, parent=self)
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

        self._refresh_current_view_immediate()

    # ---- 导入导出 ----

    def _set_io_buttons_enabled(self, enabled: bool):
        """启用/禁用导入导出相关按钮"""
        buttons = [
            self.settings_page.import_btn,
            self.settings_page.export_data_card.export_json_btn,
            self.settings_page.export_data_card.export_excel_btn,
        ]
        for btn in buttons:
            btn.setEnabled(enabled)

    def _export_json(self):
        """导出JSON（支持恢复数据）"""
        path, _ = QFileDialog.getSaveFileName(
            self, "导出JSON", "easy_todo_backup.json", "JSON 文件 (*.json)"
        )
        if not path:
            return

        self._set_io_buttons_enabled(False)
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
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
        finally:
            QApplication.restoreOverrideCursor()
            self._set_io_buttons_enabled(True)

    def _export_excel(self):
        """导出Excel（仅用于查看，不支持恢复）"""
        from views.excel_export_filter_dialog import ExcelExportFilterDialog

        dlg = ExcelExportFilterDialog(parent=self)
        if not dlg.exec():
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "导出Excel", "easy_todo_data.xlsx", "Excel 文件 (*.xlsx)"
        )
        if not path:
            return

        self._set_io_buttons_enabled(False)
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            from services.import_export_service import ImportExportService
            service = ImportExportService(self.todo_service, self.category_service)
            count = service.export_to_excel(
                path,
                date_field=dlg.date_field or None,
                start_date=dlg.start_date,
                end_date=dlg.end_date,
            )
            if dlg.date_field:
                content = f"按 {dlg.date_field_label} 筛选，已导出 {count} 个任务"
            else:
                content = f"已导出 {count} 个任务"
            InfoBar.success(title="导出成功", content=content, parent=self,
                            position=InfoBarPosition.TOP, duration=2000)
        except Exception as e:
            InfoBar.error(title="导出失败", content=str(e), parent=self,
                          position=InfoBarPosition.TOP, duration=3000)
        finally:
            QApplication.restoreOverrideCursor()
            self._set_io_buttons_enabled(True)

    def _import_data(self):
        """导入数据"""
        path, _ = QFileDialog.getOpenFileName(
            self, "导入数据", "", "JSON 文件 (*.json)"
        )
        if not path:
            return
        self._set_io_buttons_enabled(False)
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
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
            self._refresh_all_views_immediate()

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
        finally:
            QApplication.restoreOverrideCursor()
            self._set_io_buttons_enabled(True)

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

    def _on_floating_top_changed(self, enabled: bool):
        self.floating.set_always_on_top(enabled)

    def _setup_category_navigation(self):
        """启动时一次性建立分类导航"""
        bus = category_event_bus()
        bus.created.connect(self._on_category_created)
        bus.updated.connect(self._on_category_updated)
        bus.deleted.connect(self._on_category_deleted)
        bus.reordered.connect(self._on_category_reordered)

        for cat in self.category_service.get_all():
            if not cat.is_system:
                self._add_category_nav_item(cat)

    def _add_category_nav_item(self, cat):
        view = TodoListView(parent=self, view_name=cat.name)
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

    # ---- 分类变更增量处理（订阅事件总线）----
    def _on_category_created(self, category_id: int):
        if category_id in self._category_nav_items:
            return
        cat = self.category_service.get_by_id(category_id)
        if not cat or cat.is_system:
            return
        self._add_category_nav_item(cat)

    def _on_category_updated(self, category_id: int):
        item = self._category_nav_items.get(category_id)
        if not item:
            return
        cat = self.category_service.get_by_id(category_id)
        if not cat:
            return
        view, _ = item
        try:
            self.navigationInterface.widget(view.objectName()).setText(cat.name)
        except Exception:
            pass
        self._category_nav_items[category_id] = (view, cat.name)

    def _on_category_deleted(self, category_id: int):
        item = self._category_nav_items.pop(category_id, None)
        if not item:
            return
        view, _ = item
        cat_key = f"cat_{category_id}"

        if self.stackedWidget.currentWidget() is view:
            self.stackedWidget.setCurrentWidget(self.todo_list_view)

        try:
            self.removeInterface(view, isDelete=True)
        except Exception:
            try:
                view.deleteLater()
            except Exception:
                pass

        # 清理与该分类相关的加载缓存与当前视图标记
        self._loaded_views.discard(cat_key)
        if self._current_view_key == cat_key:
            self._current_view_key = "all"

    def _on_category_reordered(self):
        """分类顺序变化：仅调整导航项顺序，复用已有视图避免泄漏"""
        ordered_ids = [c.id for c in self.category_service.get_all() if not c.is_system]
        cached_ids = list(self._category_nav_items.keys())
        if ordered_ids == cached_ids:
            return

        # 从导航中移除所有分类项（不删除视图对象）
        for cat_id in cached_ids:
            item = self._category_nav_items.get(cat_id)
            if not item:
                continue
            view, _ = item
            try:
                self.removeInterface(view, isDelete=False)
            except Exception:
                pass

        # 按新顺序重新添加已有视图到导航（不创建新视图）
        for cat_id in ordered_ids:
            item = self._category_nav_items.get(cat_id)
            if not item:
                # 新分类（兜底，理论上已被 _on_category_created 处理）
                cat = self.category_service.get_by_id(cat_id)
                if cat:
                    self._add_category_nav_item(cat)
                continue
            view, name = item
            self.addSubInterface(view, FluentIcon.BOOK_SHELF, name,
                                 position=NavigationItemPosition.SCROLL)

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
        self._refresh_current_view_immediate()

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
