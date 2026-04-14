"""主窗口"""
import json
import sys
import winreg
from pathlib import Path

from PySide6.QtWidgets import QApplication, QWidget, QFileDialog

from qfluentwidgets import (
    FluentWindow, NavigationItemPosition, FluentIcon, Theme,
    setTheme, InfoBar, InfoBarPosition, MessageBox
)

from views.todo_list_view import TodoListView
from views.todo_dialog import TodoDialog
from views.settings_dialog import SettingsPage
from views.floating_widget import FloatingWidget
from services.todo_service import TodoService
from config.constants import STATUS_TODO, STATUS_DONE, APP_NAME
from config.settings import settings


class MainWindow(FluentWindow):
    """Easy Todo 主窗口"""

    def __init__(self):
        super().__init__()
        self.todo_service = TodoService()

        # 当前视图标识
        self._current_view_key = "all"

        self._setup_ui()
        self._setup_navigation()
        self._setup_floating()
        self._connect_signals()
        self._apply_initial_theme()

        # 启动时处理自动延期
        self.todo_service.process_auto_postpone()

        self._load_todos()

    def _setup_ui(self):
        """初始化窗口"""
        self.setWindowTitle(APP_NAME)
        self.resize(*settings.window_size)

        pos = settings.window_pos
        if pos:
            self.move(*pos)

        self.setMinimumSize(400, 400)

        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)

    def _setup_navigation(self):
        """设置导航栏"""
        self.todo_list_view = TodoListView()
        self.todo_list_view.setObjectName("todoListView")
        self.addSubInterface(self.todo_list_view, FluentIcon.HOME, "全部任务")

        self.today_view = TodoListView()
        self.today_view.setObjectName("todayView")
        self.addSubInterface(self.today_view, FluentIcon.CALENDAR, "今日任务")

        self.important_view = TodoListView()
        self.important_view.setObjectName("importantView")
        self.addSubInterface(self.important_view, FluentIcon.HEART, "重要任务")

        self.done_view = TodoListView()
        self.done_view.setObjectName("doneView")
        self.addSubInterface(self.done_view, FluentIcon.COMPLETED, "已完成")

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
        self._position_floating()

    def _position_floating(self):
        """将浮窗定位到主窗口右侧"""
        main_geo = self.geometry()
        fx = main_geo.right() + 10
        fy = main_geo.y() + 50
        screen = QApplication.primaryScreen().geometry()
        if fx + 300 > screen.right():
            fx = main_geo.left() - 310
        self.floating.move(fx, fy)

    def _connect_signals(self):
        """连接信号"""
        view_map = {
            "all": self.todo_list_view,
            "today": self.today_view,
            "important": self.important_view,
            "done": self.done_view,
        }

        for key, view in view_map.items():
            view.add_clicked.connect(lambda: self._open_todo_dialog())
            view.edit_clicked.connect(self._open_todo_dialog)
            view.delete_clicked.connect(self._delete_todo)
            view.toggle_done.connect(self._toggle_todo_done)
            # 浮窗按钮 - 传递视图标识
            view.float_clicked.connect(lambda k=key: self._toggle_floating(k))

        # 浮窗点击完成待办
        self.floating.todo_toggled.connect(self._toggle_todo_done)

        # 设置页面信号
        self.settings_page.opacity_changed.connect(self.floating.set_opacity)
        self.settings_page.theme_changed.connect(self._on_theme_changed)
        self.settings_page.show_done_changed.connect(self._on_show_done_changed)
        self.settings_page.auto_start_changed.connect(self._on_auto_start_changed)
        self.settings_page.export_btn.clicked.connect(self._export_data)
        self.settings_page.import_btn.clicked.connect(self._import_data)

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
        elif widget == self.important_view:
            self._current_view_key = "important"
        elif widget == self.done_view:
            self._current_view_key = "done"

    def _toggle_floating(self, view_key: str = None):
        """切换浮窗显示/隐藏"""
        if self.floating.isVisible():
            self.floating.hide()
        else:
            self._position_floating()
            self._update_floating_data(view_key or self._current_view_key)
            self.floating.show()

    def _update_floating_data(self, view_key: str):
        """根据视图标识更新浮窗数据"""
        title_map = {"all": "全部任务", "today": "今日任务", "important": "重要任务", "done": "已完成"}
        self.floating.title_label.setText(f"📋 {title_map.get(view_key, '任务列表')}")

        if view_key == "today":
            todos = self.todo_service.get_today()
        elif view_key == "important":
            todos = self.todo_service.get_high_priority()
        elif view_key == "done":
            todos = self.todo_service.get_all(status=STATUS_DONE)
        else:
            if settings.show_done_tasks:
                todos = self.todo_service.get_all_including_done()
            else:
                todos = self.todo_service.get_all(status=STATUS_TODO)

        self.floating.set_todos([t.to_dict() for t in todos])

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

    def _load_todos(self):
        """加载待办数据"""
        if settings.show_done_tasks:
            todos = self.todo_service.get_all_including_done()
        else:
            todos = self.todo_service.get_all(status=STATUS_TODO)
        self.todo_list_view.set_todos([t.to_dict() for t in todos])

        today_todos = self.todo_service.get_today()
        self.today_view.set_todos([t.to_dict() for t in today_todos])

        important_todos = self.todo_service.get_high_priority()
        self.important_view.set_todos([t.to_dict() for t in important_todos])

        done_todos = self.todo_service.get_all(status=STATUS_DONE)
        self.done_view.set_todos([t.to_dict() for t in done_todos])

        if self.floating.isVisible():
            self._update_floating_data(self._current_view_key)

    def _refresh_all_views(self):
        self._load_todos()

    def _open_todo_dialog(self, todo_id: int = None):
        todo_data = None
        if todo_id:
            todo = self.todo_service.get_by_id(todo_id)
            if todo:
                todo_data = todo.to_dict()

        dialog = TodoDialog(todo_data=todo_data, parent=self)
        dialog.todo_saved.connect(self._on_todo_saved)
        dialog.exec()

    def _on_todo_saved(self, data: dict):
        if "id" in data:
            todo = self.todo_service.update(data["id"], **data)
        else:
            todo = self.todo_service.create(**data)

        if todo:
            self._refresh_all_views()
            InfoBar.success(title="成功", content="任务已保存", parent=self,
                           position=InfoBarPosition.TOP, duration=2000)

    def _delete_todo(self, todo_id: int):
        msg = MessageBox("确认删除", "确定要删除这个任务吗？此操作不可撤销。", self)
        msg.yesButton.setText("删除")
        msg.cancelButton.setText("取消")
        if msg.exec():
            if self.todo_service.delete(todo_id):
                self._refresh_all_views()
                InfoBar.success(title="已删除", content="任务已删除", parent=self,
                               position=InfoBarPosition.TOP, duration=2000)

    def _toggle_todo_done(self, todo_id: int):
        if self.todo_service.toggle_done(todo_id):
            self._refresh_all_views()

    # ---- 导入导出 ----

    def _export_data(self):
        """导出数据为 JSON"""
        path, _ = QFileDialog.getSaveFileName(
            self, "导出数据", "easy_todo_backup.json", "JSON 文件 (*.json)"
        )
        if not path:
            return
        try:
            todos = self.todo_service.get_all_including_done()
            data = [t.to_dict() for t in todos]
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            InfoBar.success(title="导出成功", content=f"已导出 {len(data)} 个任务", parent=self,
                           position=InfoBarPosition.TOP, duration=2000)
        except Exception as e:
            InfoBar.error(title="导出失败", content=str(e), parent=self,
                         position=InfoBarPosition.TOP, duration=3000)

    def _import_data(self):
        """从 JSON 导入数据"""
        path, _ = QFileDialog.getOpenFileName(
            self, "导入数据", "", "JSON 文件 (*.json)"
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if not isinstance(data, list):
                InfoBar.error(title="导入失败", content="文件格式不正确", parent=self,
                             position=InfoBarPosition.TOP, duration=3000)
                return

            count = 0
            for item in data:
                title = item.get("title", "").strip()
                if not title:
                    continue
                # due_date 字符串转 date 对象
                due = item.get("due_date")
                if isinstance(due, str) and due:
                    try:
                        from datetime import date as _date
                        item["due_date"] = _date.fromisoformat(due)
                    except Exception:
                        item["due_date"] = None
                # 检查是否已存在（按 id）
                existing_id = item.get("id")
                if existing_id and self.todo_service.get_by_id(existing_id):
                    update_data = {k: v for k, v in item.items()
                                   if k in ("title", "description", "priority",
                                            "status", "color_tag", "due_date",
                                            "auto_postpone")}
                    self.todo_service.update(existing_id, **update_data)
                else:
                    for key in ("id", "created_at", "updated_at", "sort_order", "status"):
                        item.pop(key, None)
                    self.todo_service.create(**item)
                count += 1

            self._refresh_all_views()
            InfoBar.success(title="导入成功", content=f"已导入 {count} 个任务", parent=self,
                           position=InfoBarPosition.TOP, duration=2000)
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

    def _on_show_done_changed(self, checked: bool):
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
        if self.floating.isVisible():
            self._position_floating()
        super().resizeEvent(event)

    def _on_move(self, event):
        settings.window_pos = (self.x(), self.y())
        super().moveEvent(event)

    def closeEvent(self, event):
        settings.window_size = (self.width(), self.height())
        settings.window_pos = (self.x(), self.y())
        self.floating.close()
        self.todo_service.close()
        super().closeEvent(event)
