"""
 * @description 应用设置管理
 * @author 十玖八柒（Ahzoo）
 * @date 2026/04
"""
import json
from pathlib import Path


class Settings:
    """应用设置"""

    DEFAULT = {
        "theme": "light",  # light / dark / system
        "theme_color": "#0078D4",
        "window_width": 520,
        "window_height": 520,
        "window_x": None,
        "window_y": None,
        "sort_by": "created_at",
        "sort_order": "desc",
        "floating_opacity": 0.95,
        "show_done_tasks": False,
        "auto_start": False,
        "home_page": "all",
        "sort_rule": "created_at",
        "done_at_bottom": True,
        "floating_top": False,
        "important_priorities": [3],
        "floating_pinned": False,
        "floating_geometry": None,
        "floating_view": "all",
    }

    def __init__(self):
        self._data = dict(self.DEFAULT)
        self._path = Path.home() / f".{APP_ID}" / "settings.json"
        self._load()

    def _load(self):
        try:
            if self._path.exists():
                with open(self._path, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    self._data = {**self.DEFAULT, **saved}
        except Exception:
            pass

    def save(self):
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

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
    def window_size(self) -> tuple:
        return (self._data.get("window_width", 1100),
                self._data.get("window_height", 700))

    @window_size.setter
    def window_size(self, value: tuple):
        self._data["window_width"], self._data["window_height"] = value
        self.save()

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
        self.save()

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
    def auto_start(self) -> bool:
        return self._data.get("auto_start", False)

    @auto_start.setter
    def auto_start(self, value: bool):
        self._data["auto_start"] = value
        self.save()

    @property
    def home_page(self) -> str:
        return self._data.get("home_page", "all")

    @home_page.setter
    def home_page(self, value: str):
        self._data["home_page"] = value
        self.save()

    @property
    def sort_rule(self) -> str:
        return self._data.get("sort_rule", "created_at")

    @sort_rule.setter
    def sort_rule(self, value: str):
        self._data["sort_rule"] = value
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
    def important_priorities(self) -> list[int]:
        return self._data.get("important_priorities", [3])

    @important_priorities.setter
    def important_priorities(self, value: list[int]):
        self._data["important_priorities"] = value
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
        self.save()

    @property
    def floating_view(self) -> str:
        return self._data.get("floating_view", "all")

    @floating_view.setter
    def floating_view(self, value: str):
        self._data["floating_view"] = value
        self.save()


# 全局单例
from config.constants import APP_ID

settings = Settings()
