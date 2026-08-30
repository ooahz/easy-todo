"""
 * @description 主题与样式统一配置
 *   集中管理应用中重复使用的字体大小、颜色、背景、tooltip 等公共样式。
 * @author 十玖八柒（Ahzoo）
"""
from __future__ import annotations

import json
import re
from pathlib import Path

try:
    from qfluentwidgets import isDarkTheme
except Exception:
    def isDarkTheme() -> bool:
        return False


# ============================================================
# 字体大小
# ============================================================
class FontSize:
    """统一字体大小（像素）

    通用档位与场景档位并列：
    - 通用档位（TINY/CAPTION/SMALL/BODY/MEDIUM/SUBTITLE/LARGE/H3/H2/H1）
      适用于浮窗、详情、弹窗等多数界面。
    - 任务列表档位（TASK_*）仅服务于 todo_card / subtask_card 等
      任务列表区域，独立可调以避免影响其它场景。
    """
    TINY = 10
    CAPTION = 11          # 辅助说明、标签头
    SMALL = 12            # 普通正文、按钮
    BODY = 13             # 内容、标题
    MEDIUM = 14           # 描述、卡片标题
    LARGE = 16            # 详情副标题
    H3 = 18               # H3 标题
    H2 = 20               # 大标题
    H1 = 22               # 详情 H1

    # ---- 任务列表专属字号（独立于通用档位）----
    TASK_TITLE = 14       # 任务卡片标题（原 MEDIUM）
    TASK_DESC = 12        # 任务卡片描述（原 SMALL）
    TASK_INFO = 12        # 任务卡片信息行（原 SMALL）
    TASK_SUBTASK = 13     # 子任务标题（原硬编码 13px）

    # ---- 浮窗列表专属字号（独立于通用档位）----
    FLOATING_ITEM_TITLE = 15        # 浮窗列表项父任务（原硬编码 15px）
    FLOATING_CHILD_ITEM_TITLE = 13  # 浮窗列表项子任务（原硬编码 13px）


# ============================================================
# 字体族
# ============================================================
class FontFamily:
    """应用全局字体族（按优先级排列，第一个系统中可用的会被使用）。

    可通过 theme.json 中 `font_family` 字段覆盖整个列表；
    也可仅覆盖 `default_size` 调整应用级默认字号。
    """
    FAMILIES = ["Microsoft YaHei", "Segoe UI", "PingFang SC"]
    MONO_FAMILIES = ["Cascadia Code", "Consolas", "monospace"]
    DEFAULT_SIZE = 10     # main.py 中 QFont 的 point size 起点


def font_family_list() -> list[str]:
    """返回当前配置的字体族列表（顺序即优先级）。"""
    return list(FontFamily.FAMILIES)


def font_family_str() -> str:
    """生成 CSS / QSS 通用的字体族字符串（自动加引号并以 sans-serif 兜底）。"""
    return ", ".join(f'"{f}"' for f in FontFamily.FAMILIES) + ', "sans-serif"'


def mono_family_str() -> str:
    """生成等宽字体族字符串"""
    return ", ".join(f'"{f}"' for f in FontFamily.MONO_FAMILIES)


def app_default_font_size() -> int:
    """main.py 中 QFont 使用的默认字号。"""
    return int(FontFamily.DEFAULT_SIZE)


# ============================================================
# 颜色配置（按主题分组）
# ============================================================
class _LightColors:
    """浅色主题颜色"""
    # 文本
    TITLE = "#1A1A1A"
    SUBTITLE = "#444"
    BODY = "#555"
    BODY_LIGHT = "#333"
    MUTED = "#999"
    MUTED_LIGHT = "#888"
    DISABLED = "#AAA"
    DONE = "#999"
    # 背景 / 边框
    BG = "#FAFAFA"
    CARD_BG = "#FFFFFF"
    CARD_HOVER = "#F5F5F5"
    INPUT_BG = "#FFF"
    CODE_BG = "#F5F5F5"
    HEADER_BG = "#F0F0F0"
    BORDER = "#e2e8f0"
    BORDER_STRONG = "#202935"
    DIVIDER = "#DDD"
    DIVIDER_FALLBACK = "rgba(0, 0, 0, 0.06)"
    HOVER_BG = "rgba(0, 0, 0, 0.02)"
    HOVER_BG_STRONG = "rgba(0, 0, 0, 0.04)"
    HOVER_BG_SOFT = "rgba(0, 120, 212, 0.05)"
    HOVER_BORDER = "rgba(0, 0, 0, 0.06)"
    INPUT_BORDER = "rgb(200, 200, 200)"
    SELECTED_BG = "rgba(0, 120, 212, 0.05)"
    SELECTED_BORDER = "rgba(0, 120, 212, 0.3)"
    DROP_BG = "rgba(0, 120, 212, 0.1)"
    # 语义色
    ACCENT = "#0078D4"
    LINK = "#0078D4"
    WARNING = "#FF8C00"
    DANGER = "#D13438"
    DANGER_ALT = "#FF6B6B"
    DONE_GREEN = "#107C10"
    DONE_GREEN_ALT = "#6BCB77"
    ICON = "rgba(0, 0, 0, 0.35)"
    TAG_BG = "rgba(0, 0, 0, 0.04)"
    BLOCKQUOTE = "#666"
    # 浮窗
    FLOATING_FONT_COLOR = "#1A1A1A"   # 浮窗任务列表默认字体颜色
    FLOATING_SUB_FONT_COLOR = "#999999"  # 浮窗副字体颜色：已完成任务、顶部数量等
    FLOATING_BG = "rgb(255, 255, 255)" # 浮窗背景色（alpha 由 settings.floating_opacity 控制）
    # 弹窗 / Tooltip
    TOOLTIP_BG = "#FFF"
    OVERLAY_BG = "rgba(255, 255, 255, 245)"
    # 标签 badge
    SYS_TAG_BG = "rgba(0,0,0,0.06)"
    SYS_TAG_FG = "#888"


class _DarkColors:
    """深色主题颜色"""
    # 文本
    TITLE = "#EEE"
    SUBTITLE = "#CCC"
    BODY = "#BBB"
    BODY_LIGHT = "#DDD"
    MUTED = "#888"
    MUTED_LIGHT = "#999"
    DISABLED = "#666"
    DONE = "#666"
    # 背景 / 边框
    BG = "#1F1F1F"
    CARD_BG = "#2D2D2D"
    CARD_HOVER = "#333333"
    INPUT_BG = "rgb(59, 59, 59)"
    CODE_BG = "#3A3A3A"
    HEADER_BG = "#262626"
    BORDER = "rgba(255, 255, 255, 0.06)"
    BORDER_STRONG = "rgba(255, 255, 255, 0.08)"
    DIVIDER = "#444"
    DIVIDER_FALLBACK = "rgba(255, 255, 255, 0.06)"
    HOVER_BG = "rgba(255, 255, 255, 0.04)"
    HOVER_BG_STRONG = "rgba(255, 255, 255, 0.06)"
    HOVER_BG_SOFT = "rgba(96, 205, 255, 0.05)"
    HOVER_BORDER = "rgba(255, 255, 255, 0.08)"
    INPUT_BORDER = "rgb(80, 80, 80)"
    SELECTED_BG = "rgba(96, 205, 255, 0.08)"
    SELECTED_BORDER = "rgba(96, 205, 255, 0.3)"
    DROP_BG = "rgba(96, 205, 255, 0.1)"
    # 语义色
    ACCENT = "#60CDFF"
    LINK = "#60CDFF"
    WARNING = "#FFB347"
    DANGER = "#FF6B6B"
    DANGER_ALT = "#FF6B6B"
    DONE_GREEN = "#6BCB77"
    DONE_GREEN_ALT = "#6BCB77"
    ICON = "rgba(255, 255, 255, 0.45)"
    TAG_BG = "rgba(255, 255, 255, 0.06)"
    BLOCKQUOTE = "#AAA"
    # 浮窗
    FLOATING_FONT_COLOR = "#EEE"       # 浮窗任务列表默认字体颜色
    FLOATING_SUB_FONT_COLOR = "#888888"   # 浮窗副字体颜色：已完成任务、顶部数量等
    FLOATING_BG = "rgb(45, 45, 45)"    # 浮窗背景色（alpha 由 settings.floating_opacity 控制）
    # 弹窗 / Tooltip
    TOOLTIP_BG = "#3C3C3C"
    OVERLAY_BG = "rgba(43, 43, 43, 240)"
    # 标签 badge
    SYS_TAG_BG = "rgba(255,255,255,0.08)"
    SYS_TAG_FG = "#AAA"


LIGHT = _LightColors()
DARK = _DarkColors()


# 保存原始默认值，以便 theme.json 热重载时恢复被移除的覆盖项
_DEFAULT_FONT_SIZE = {k: v for k, v in vars(FontSize).items() if not k.startswith("_") and not callable(v)}
_DEFAULT_FONT_FAMILY = {
    k: (v[:] if isinstance(v, list) else v)
    for k, v in vars(FontFamily).items() if not k.startswith("_") and not callable(v)
}
_DEFAULT_LIGHT_COLORS = {k: v for k, v in vars(_LightColors).items() if not k.startswith("_") and not callable(v)}
_DEFAULT_DARK_COLORS = {k: v for k, v in vars(_DarkColors).items() if not k.startswith("_") and not callable(v)}
# ============================================================
_USER_THEME_PATH: Path | None = None


def _user_theme_path() -> Path:
    """延迟解析用户主题文件路径（避免 import 时与 constants 形成循环）。"""
    global _USER_THEME_PATH
    if _USER_THEME_PATH is None:
        try:
            from config.constants import user_config_dir
            _USER_THEME_PATH = Path(user_config_dir()) / "theme.json"
        except Exception:
            _USER_THEME_PATH = Path.home() / ".com.easy.todo" / "config" / "theme.json"
    return _USER_THEME_PATH


def _apply_overrides_to_class(cls, overrides: dict, value_type: type) -> None:
    """把 dict 中的合法字段写回类属性；类型不匹配或字段不存在则跳过。"""
    if not isinstance(overrides, dict):
        return
    valid_names = {n for n in vars(cls) if not n.startswith("_")}
    for key, value in overrides.items():
        if key not in valid_names:
            continue
        if not isinstance(value, value_type):
            continue
        try:
            setattr(cls, key, value)
        except Exception:
            pass


def _load_user_overrides() -> None:
    """从用户 theme.json 合并覆盖到 FontSize / FontFamily / _LightColors / _DarkColors。

    覆盖范围：
    - FontSize 任意字段（含任务列表专属 TASK_* / 浮窗 FLOATING_*）
    - FontFamily.FAMILIES（整个列表） / FontFamily.MONO_FAMILIES /
      FontFamily.DEFAULT_SIZE
    - 颜色字段（文本、背景、边框、强调色、警示色等）

    失败（文件不存在、格式错误、权限不足）一律静默回退到内置默认值。
    """
    data = load_user_theme()
    _apply_theme_overrides(data)


def _apply_font_family_overrides(overrides) -> None:
    """把 dict 中的合法字段写回 FontFamily 类属性。

    支持字段：
    - families: list[str] 替换整个字体族列表
    - mono_families: list[str] 替换等宽字体族列表
    - default_size: int 调整 main.py 中 QFont 默认字号
    """
    if not isinstance(overrides, dict):
        return
    families = overrides.get("families")
    if isinstance(families, list) and families and all(isinstance(f, str) and f.strip() for f in families):
        FontFamily.FAMILIES = [f.strip() for f in families]
    mono = overrides.get("mono_families")
    if isinstance(mono, list) and mono and all(isinstance(f, str) and f.strip() for f in mono):
        FontFamily.MONO_FAMILIES = [f.strip() for f in mono]
    size = overrides.get("default_size")
    if isinstance(size, int) and size > 0:
        FontFamily.DEFAULT_SIZE = size


def _apply_theme_overrides(data: dict) -> None:
    """把 theme.json 数据中的覆盖项应用到内置类属性。

    先恢复原始默认值，再应用 ``font_size`` / ``font_family`` / ``light`` / ``dark``
    四个顶层键，确保被用户移除的覆盖项能回到内置默认值。
    """
    if not isinstance(data, dict):
        return

    # 恢复原始默认值，确保本次未覆盖的字段回到初始状态
    for k, v in _DEFAULT_FONT_SIZE.items():
        setattr(FontSize, k, v)
    for k, v in _DEFAULT_FONT_FAMILY.items():
        setattr(FontFamily, k, v[:] if isinstance(v, list) else v)
    for k, v in _DEFAULT_LIGHT_COLORS.items():
        setattr(_LightColors, k, v)
    for k, v in _DEFAULT_DARK_COLORS.items():
        setattr(_DarkColors, k, v)

    _apply_overrides_to_class(FontSize, data.get("font_size"), int)
    _apply_font_family_overrides(data.get("font_family"))
    _apply_overrides_to_class(_LightColors, data.get("light"), str)
    _apply_overrides_to_class(_DarkColors, data.get("dark"), str)


def load_user_theme() -> dict:
    """读取用户 theme.json，返回完整 dict；文件不存在或解析失败返回空 dict。"""
    path = _user_theme_path()
    try:
        if not path.exists():
            return {}
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_user_theme(data: dict) -> None:
    """保存完整 theme.json 数据到用户配置目录。"""
    path = _user_theme_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def update_user_theme(updates: dict) -> dict:
    """合并用户提供的覆盖项到现有 theme.json 并保存，返回保存后的完整数据。"""
    data = load_user_theme()
    if not isinstance(data, dict):
        data = {}
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(data.get(key), dict):
            data[key].update(value)
        else:
            data[key] = value
    save_user_theme(data)
    return data


def reload_user_overrides() -> None:
    """重新从用户 theme.json 加载并覆盖到内置类属性。

    供设置界面在修改 theme.json 后调用，使浮窗等组件能立即使用最新配置。
    """
    _load_user_overrides()


def reset_user_theme() -> None:
    """删除用户主题文件并恢复内置默认主题覆盖"""
    path = _user_theme_path()
    try:
        if path.exists():
            path.unlink()
    except Exception:
        pass
    _apply_theme_overrides({})


# 启动时执行一次（模块级副作用，业务代码无需感知）
_load_user_overrides()


# ============================================================
# 主题切换工具
# ============================================================
def palette() -> "_LightColors | _DarkColors":
    """根据当前主题返回对应的调色板实例"""
    return DARK if isDarkTheme() else LIGHT


def is_dark() -> bool:
    """当前是否为深色主题"""
    return isDarkTheme()


# ============================================================
# 颜色集合：按用途聚合（便于一处取齐多种语义色）
# ============================================================
def theme_colors() -> dict:
    """返回完整主题色字典，键名与原各模块保持一致以兼容现有调用。

    结构:
      bg / card_bg / card_hover / border / title / subtitle / body / muted /
      icon / accent / divider / tag_bg / done / info / hover_bg / hover_border /
      overdue / done_green / code_bg / code_border / link_color / blockquote_color /
      warning / danger / header_bg / priority_urgent_important / priority_important /
      priority_urgent / priority_minor / sep / cell_bg / cell_border / text / done_text /
      hover / empty / close / close_hover / close_hover_bg / row_hover / done_green_alt /
      option_bg / option_selected_bg / option_selected_border / drop_bg
    """
    c = palette()
    if isDarkTheme():
        return {
            "bg": c.BG,
            "card_bg": c.CARD_BG,
            "card_hover": c.CARD_HOVER,
            "border": c.BORDER_STRONG,
            "title": c.TITLE,
            "subtitle": c.SUBTITLE,
            "body": c.BODY,
            "muted": c.MUTED,
            "icon": c.ICON,
            "accent": c.ACCENT,
            "divider": c.DIVIDER_FALLBACK,
            "tag_bg": c.TAG_BG,
            "done": c.DONE,
            "info": c.MUTED_LIGHT,
            "hover_bg": c.HOVER_BG,
            "hover_border": c.HOVER_BORDER,
            "overdue": c.DANGER_ALT,
            "done_green": c.DONE_GREEN,
            "done_green_alt": c.DONE_GREEN_ALT,
            "code_bg": c.CODE_BG,
            "code_border": "#555",
            "link_color": c.LINK,
            "blockquote_color": c.BLOCKQUOTE,
            "warning": c.WARNING,
            "danger": c.DANGER,
            "danger_alt": c.DANGER_ALT,
            "header_bg": c.HEADER_BG,
            "priority_urgent_important": "#FF6B6B",
            "priority_important": "#FFB347",
            "priority_urgent": "#60CDFF",
            "priority_minor": "#8764B8",
            "sep": c.DIVIDER_FALLBACK,
            "cell_bg": c.HOVER_BG,
            "cell_border": c.BORDER,
            "text": c.BODY_LIGHT,
            "done_text": c.DONE,
            "hover": c.HOVER_BG_STRONG,
            "empty": c.MUTED,
            "close": c.MUTED,
            "close_hover": "#FFF",
            "close_hover_bg": "rgba(255,255,255,0.1)",
            "row_hover": c.HOVER_BG_STRONG,
            "option_bg": c.CARD_BG,
            "option_selected_bg": c.SELECTED_BG,
            "option_selected_border": c.SELECTED_BORDER,
            "drop_bg": c.DROP_BG,
            "floating_font_color": c.FLOATING_FONT_COLOR,
            "floating_sub_font_color": c.FLOATING_SUB_FONT_COLOR,
        }
    return {
        "bg": c.BG,
        "card_bg": c.CARD_BG,
        "card_hover": c.CARD_HOVER,
        "border": c.BORDER,
        "title": c.TITLE,
        "subtitle": c.SUBTITLE,
        "body": c.BODY,
        "muted": c.MUTED,
        "icon": c.ICON,
        "accent": c.ACCENT,
        "divider": c.DIVIDER_FALLBACK,
        "tag_bg": c.TAG_BG,
        "done": "gray",
        "info": "#888",
        "hover_bg": c.HOVER_BG,
        "hover_border": c.HOVER_BORDER,
        "overdue": c.DANGER,
        "done_green": c.DONE_GREEN,
        "done_green_alt": c.DONE_GREEN_ALT,
        "code_bg": c.CODE_BG,
        "code_border": "#DDD",
        "link_color": c.LINK,
        "blockquote_color": c.BLOCKQUOTE,
        "warning": c.WARNING,
        "danger": c.DANGER,
        "danger_alt": c.DANGER_ALT,
        "header_bg": c.HEADER_BG,
        "priority_urgent_important": "#D13438",
        "priority_important": "#0078D4",
        "priority_urgent": "#CA5010",
        "priority_minor": "#8764B8",
        "sep": c.DIVIDER_FALLBACK,
        "cell_bg": c.HOVER_BG,
        "cell_border": c.BORDER,
        "text": c.BODY_LIGHT,
        "done_text": "#999",
        "hover": c.HOVER_BG_STRONG,
        "empty": c.MUTED,
        "close": "#999",
        "close_hover": "#333",
        "close_hover_bg": "rgba(0,0,0,0.06)",
        "row_hover": "rgba(0,0,0,0.04)",
        "option_bg": c.CARD_BG,
        "option_selected_bg": c.SELECTED_BG,
        "option_selected_border": c.SELECTED_BORDER,
        "drop_bg": c.DROP_BG,
        "floating_font_color": c.FLOATING_FONT_COLOR,
        "floating_sub_font_color": c.FLOATING_SUB_FONT_COLOR,
    }


# ============================================================
# Tooltip 样式
# ============================================================
def tooltip_style(font_size: int = FontSize.SMALL) -> str:
    """统一生成 QToolTip 样式，参数可自定义字号"""
    c = palette()
    return f"""
        QToolTip {{
            background-color: {c.TOOLTIP_BG};
            color: {c.BODY_LIGHT};
            border: 1px solid {c.DIVIDER};
            border-radius: 6px;
            padding: 6px 10px;
            font-size: {font_size}px;
        }}
    """


def show_themed_tooltip(global_pos, text: str) -> bool:
    """以独立顶层窗口弹出 tooltip，避免浮窗 WA_TranslucentBackground 透明污染。

    parent=None 切断对父窗口透明属性的继承，QToolTip 使用系统原生外观
    （可读、不双层、不黑底）。代价：不跟随应用明暗主题色。
    如需跟随主题色，可在此处设置 QApplication 调色板的 ToolTipBase/ToolTipText。

    Returns True 供 eventFilter 直接返回。
    """
    if not text:
        return True
    from PySide6.QtWidgets import QToolTip
    QToolTip.showText(global_pos, text, None)
    return True


# ============================================================
# 独立子进程友好的主题色接口（不依赖 qfluentwidgets）
# ============================================================
def theme_colors_by_name(theme_name: str) -> dict:
    """按主题名直接返回颜色字典，供无 Qt/qfluentwidgets 环境的子进程使用。

    可选值: "light" / "dark"，其它值回退为 light。
    与 theme_colors() 输出的键名一致，可直接被 webview_runner 注入 CSS 变量。
    """
    c = DARK if (theme_name or "").lower() == "dark" else LIGHT
    return {
        "bg": c.BG,
        "card_bg": c.CARD_BG,
        "card_hover": c.CARD_HOVER,
        "border": c.BORDER_STRONG if theme_name == "dark" else c.BORDER,
        "title": c.TITLE,
        "subtitle": c.SUBTITLE,
        "body": c.BODY,
        "muted": c.MUTED,
        "icon": c.ICON,
        "accent": c.ACCENT,
        "divider": c.DIVIDER_FALLBACK,
        "tag_bg": c.TAG_BG,
        "done": c.DONE,
        "info": c.MUTED_LIGHT,
        "hover_bg": c.HOVER_BG,
        "hover_border": c.HOVER_BORDER,
        "overdue": c.DANGER_ALT if theme_name == "dark" else c.DANGER,
        "done_green": c.DONE_GREEN,
        "done_green_alt": c.DONE_GREEN_ALT,
        "code_bg": c.CODE_BG,
        "code_border": "#555" if theme_name == "dark" else "#DDD",
        "link_color": c.LINK,
        "blockquote_color": c.BLOCKQUOTE,
        "warning": c.WARNING,
        "danger": c.DANGER,
        "danger_alt": c.DANGER_ALT,
        "header_bg": c.HEADER_BG,
        "priority_urgent_important": "#FF6B6B" if theme_name == "dark" else "#D13438",
        "priority_important": "#FFB347" if theme_name == "dark" else "#0078D4",
        "priority_urgent": "#60CDFF" if theme_name == "dark" else "#CA5010",
        "priority_minor": "#8764B8",
        "sep": c.DIVIDER_FALLBACK,
        "cell_bg": c.HOVER_BG,
        "cell_border": c.BORDER,
        "text": c.BODY_LIGHT,
        "done_text": c.DONE,
        "hover": c.HOVER_BG_STRONG,
        "empty": c.MUTED,
        "close": c.MUTED,
        "close_hover": "#FFF" if theme_name == "dark" else "#333",
        "close_hover_bg": "rgba(255,255,255,0.1)" if theme_name == "dark" else "rgba(0,0,0,0.06)",
        "row_hover": c.HOVER_BG_STRONG,
        "option_bg": c.CARD_BG,
        "option_selected_bg": c.SELECTED_BG,
        "option_selected_border": c.SELECTED_BORDER,
        "drop_bg": c.DROP_BG,
        "floating_font_color": c.FLOATING_FONT_COLOR,
        "floating_sub_font_color": c.FLOATING_SUB_FONT_COLOR,
    }


# ============================================================
# Tooltip 样式片段
# ============================================================
def accent_color() -> str:
    """主题强调色"""
    return palette().ACCENT


# ============================================================
# 颜色解析工具（用于浮窗等需要把 BG 拆成 rgba 的场景）
# ============================================================
def color_to_rgba(color_str: str, alpha: int = 255) -> tuple[int, int, int, int]:
    """把 CSS 颜色字符串解析为 (r, g, b, a) 元组"""
    if not color_str:
        return 0, 0, 0, alpha
    s = color_str.strip()

    m = re.fullmatch(r"#([0-9a-fA-F]{3})", s)
    if m:
        h = m.group(1)
        r, g, b = int(h[0] * 2, 16), int(h[1] * 2, 16), int(h[2] * 2, 16)
        return r, g, b, alpha

    m = re.fullmatch(r"#([0-9a-fA-F]{6})", s)
    if m:
        h = m.group(1)
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return r, g, b, alpha

    m = re.fullmatch(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)(?:\s*,\s*([\d.]+))?\s*\)", s)
    if m:
        r, g, b = int(m.group(1)), int(m.group(2)), int(m.group(3))
        a_val = m.group(4)
        if a_val is not None:
            a_float = float(a_val)
            # 同时兼容 CSS 规范的 0-1 与本项目约定的 0-255：
            # >1 即视为 0-255 范围（取整），否则按 0-1 换算。
            a = int(a_float) if a_float > 1 else int(a_float * 255)
        else:
            a = alpha
        return r, g, b, a

    # 解析失败 → 使用调色板兜底
    fallback = palette().FLOATING_BG
    fr, fg, fb, fa = color_to_rgba(fallback, alpha)
    return fr, fg, fb, fa


def floating_bg_rgba(alpha: int = 255) -> tuple[int, int, int, int]:
    """浮窗专用背景的 rgba 拆分（从 palette().FLOATING_BG 取色，可被 theme.json 覆盖）。

    浮窗渲染应使用本函数，否则用户在 theme.json 中覆盖 FLOATING_BG 不会生效。
    """
    return color_to_rgba(palette().FLOATING_BG, alpha)
