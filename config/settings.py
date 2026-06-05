"""
 * @description 应用设置管理
 * @author 十玖八柒（Ahzoo）
 * @date 2026/04
"""
from __future__ import annotations
import json
from pathlib import Path


class Settings:
    """应用设置"""

    DEFAULT = {
        "theme": "light",  # light / dark / system
        "theme_color": "#0078D4",
        "warning_color": "#FF8C00",
        "window_width": 720,
        "window_height": 520,
        "window_x": None,
        "window_y": None,
        "sort_by": "created_at",
        "sort_order": "desc",
        "floating_opacity": 0.95,
        "show_done_tasks": False,
        "show_week_view": True,
        "auto_start": False,
        "sort_rule": "created_at",
        "sort_rules": ["priority", "created_at"],
        "done_at_bottom": True,
        "floating_top": False,
        "floating_pinned": False,
        "floating_geometry": None,
        "floating_view": "all",
        "floating_show_subtasks": True,  # 浮窗是否显示子任务
        "data_path": "",  # 数据保存路径，空则使用默认路径
        "description_mode": "default",  # default / markdown
        "dialog_mode": "default",  # default / widescreen
        "detail_dialog_width": 480,
        "detail_dialog_height": 520,
        "todo_dialog_width": None,
        "todo_dialog_height": None,
        "system_view_order": ["recent", "today", "important", "all", "done"],
    }

    def __init__(self):
        self._data = dict(self.DEFAULT)
        self._path = Path.home() / f".{APP_ID}" / "settings.json"
        self._save_timer = None
        self._load()

    def _load(self):
        try:
            if self._path.exists():
                with open(self._path, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    self._data = {**self.DEFAULT, **saved}
                    if "recent" not in self._data.get("system_view_order", []):
                        self._data["system_view_order"] = list(self.DEFAULT["system_view_order"])
        except Exception:
            pass

    def save(self):
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def save_debounced(self):
        if self._save_timer is None:
            from PySide6.QtCore import QTimer
            self._save_timer = QTimer()
            self._save_timer.setSingleShot(True)
            self._save_timer.setInterval(500)
            self._save_timer.timeout.connect(self.save)
        self._save_timer.start()

    def flush(self):
        if self._save_timer is not None and self._save_timer.isActive():
            self._save_timer.stop()
        self.save()

    # ---- 属性访问 ----
    @property
    def theme(self) -> str:
        return self._data.get("theme", "light")

    @theme.setter
    def theme(self, value: str):
        self._data["theme"] = value
        self.save()

    @property
    def theme_color(self) -> str:
        return self._data.get("theme_color", "#0078D4")

    @theme_color.setter
    def theme_color(self, value: str):
        self._data["theme_color"] = value
        self.save()

    @property
    def warning_color(self) -> str:
        return self._data.get("warning_color", "#FF8C00")

    @warning_color.setter
    def warning_color(self, value: str):
        self._data["warning_color"] = value
        self.save()

    @property
    def window_size(self) -> tuple:
        return (self._data.get("window_width", 1100),
                self._data.get("window_height", 700))

    @window_size.setter
    def window_size(self, value: tuple):
        self._data["window_width"], self._data["window_height"] = value
        self.save_debounced()

    @property
    def window_pos(self) -> tuple | None:
        x = self._data.get("window_x")
        y = self._data.get("window_y")
        if x is not None and y is not None:
            return (x, y)
        return None

    @window_pos.setter
    def window_pos(self, value: tuple | None):
        if value:
            self._data["window_x"], self._data["window_y"] = value
        else:
            self._data["window_x"] = None
            self._data["window_y"] = None
        self.save_debounced()

    @property
    def sort_by(self) -> str:
        return self._data.get("sort_by", "created_at")

    @sort_by.setter
    def sort_by(self, value: str):
        self._data["sort_by"] = value
        self.save()

    @property
    def sort_order(self) -> str:
        return self._data.get("sort_order", "desc")

    @sort_order.setter
    def sort_order(self, value: str):
        self._data["sort_order"] = value
        self.save()

    @property
    def floating_opacity(self) -> float:
        return self._data.get("floating_opacity", 0.95)

    @floating_opacity.setter
    def floating_opacity(self, value: float):
        self._data["floating_opacity"] = value
        self.save()

    @property
    def show_done_tasks(self) -> bool:
        return self._data.get("show_done_tasks", False)

    @show_done_tasks.setter
    def show_done_tasks(self, value: bool):
        self._data["show_done_tasks"] = value
        self.save()

    @property
    def show_week_view(self) -> bool:
        return self._data.get("show_week_view", True)

    @show_week_view.setter
    def show_week_view(self, value: bool):
        self._data["show_week_view"] = value
        self.save()

    @property
    def auto_start(self) -> bool:
        return self._data.get("auto_start", False)

    @auto_start.setter
    def auto_start(self, value: bool):
        self._data["auto_start"] = value
        self.save()

    @property
    def sort_rule(self) -> str:
        return self._data.get("sort_rule", "created_at")

    @sort_rule.setter
    def sort_rule(self, value: str):
        self._data["sort_rule"] = value
        self.save()

    @property
    def sort_rules(self) -> list[str]:
        return self._data.get("sort_rules", ["priority", "created_at"])

    @sort_rules.setter
    def sort_rules(self, value: list[str]):
        self._data["sort_rules"] = value
        self.save()

    @property
    def done_at_bottom(self) -> bool:
        return self._data.get("done_at_bottom", True)

    @done_at_bottom.setter
    def done_at_bottom(self, value: bool):
        self._data["done_at_bottom"] = value
        self.save()

    @property
    def floating_top(self) -> bool:
        return self._data.get("floating_top", False)

    @floating_top.setter
    def floating_top(self, value: bool):
        self._data["floating_top"] = value
        self.save()

    @property
    def floating_pinned(self) -> bool:
        return self._data.get("floating_pinned", False)

    @floating_pinned.setter
    def floating_pinned(self, value: bool):
        self._data["floating_pinned"] = value
        self.save()

    @property
    def floating_geometry(self) -> dict | None:
        return self._data.get("floating_geometry")

    @floating_geometry.setter
    def floating_geometry(self, value: dict | None):
        self._data["floating_geometry"] = value
        self.save_debounced()

    @property
    def floating_view(self) -> str:
        return self._data.get("floating_view", "all")

    @floating_view.setter
    def floating_view(self, value: str):
        self._data["floating_view"] = value
        self.save()

    @property
    def floating_show_subtasks(self) -> bool:
        return self._data.get("floating_show_subtasks", True)

    @floating_show_subtasks.setter
    def floating_show_subtasks(self, value: bool):
        self._data["floating_show_subtasks"] = value
        self.save()

    @property
    def data_path(self) -> str:
        """数据保存路径"""
        return self._data.get("data_path", "")

    @data_path.setter
    def data_path(self, value: str):
        self._data["data_path"] = value
        self.save()

    @property
    def description_mode(self) -> str:
        """描述输入模式：default / markdown"""
        return self._data.get("description_mode", "default")

    @description_mode.setter
    def description_mode(self, value: str):
        self._data["description_mode"] = value
        self.save()

    @property
    def dialog_mode(self) -> str:
        """对话框模式：default / widescreen"""
        return self._data.get("dialog_mode", "default")

    @dialog_mode.setter
    def dialog_mode(self, value: str):
        self._data["dialog_mode"] = value
        self.save()

    @property
    def detail_dialog_size(self) -> tuple:
        return (self._data.get("detail_dialog_width", 480),
                self._data.get("detail_dialog_height", 520))

    @detail_dialog_size.setter
    def detail_dialog_size(self, value: tuple):
        self._data["detail_dialog_width"], self._data["detail_dialog_height"] = value
        self.save_debounced()

    @property
    def todo_dialog_size(self) -> tuple | None:
        w = self._data.get("todo_dialog_width")
        h = self._data.get("todo_dialog_height")
        if w is not None and h is not None:
            return (w, h)
        return None

    @todo_dialog_size.setter
    def todo_dialog_size(self, value: tuple | None):
        if value:
            self._data["todo_dialog_width"], self._data["todo_dialog_height"] = value
        else:
            self._data["todo_dialog_width"] = None
            self._data["todo_dialog_height"] = None
        self.save_debounced()

    @property
    def system_view_order(self) -> list:
        return self._data.get("system_view_order", ["all", "today", "important", "done"])

    @system_view_order.setter
    def system_view_order(self, value: list):
        self._data["system_view_order"] = value
        self.save()


# 全局单例
from config.constants import APP_ID

settings = Settings()
