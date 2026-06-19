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
except Exception:  # 子进程（如 webview_runner）无 Qt 上下文时的安全回退
    def isDarkTheme() -> bool:  # type: ignore[no-redef]
        return False


# ============================================================
# 字体大小
# ============================================================
class FontSize:
    """统一字体大小（像素）"""
    TINY = 10
    CAPTION = 11          # 辅助说明、标签头
    SMALL = 12            # 普通正文、按钮
    BODY = 13             # 内容、标题
    MEDIUM = 14           # 描述、卡片标题
    SUBTITLE = 15         # 浮窗标题
    LARGE = 16            # 详情副标题
    H3 = 18               # H3 标题
    H2 = 20               # 大标题
    H1 = 22               # 详情 H1


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
    BORDER = "rgba(0, 0, 0, 0.06)"
    BORDER_STRONG = "rgba(0, 0, 0, 0.08)"
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
    WARNING_ALT = "#FFB900"
    WARNING_HOVER = "#FFB347"
    DANGER = "#D13438"
    DANGER_ALT = "#FF6B6B"
    DONE_GREEN = "#107C10"
    DONE_GREEN_ALT = "#6BCB77"
    ICON = "rgba(0, 0, 0, 0.35)"
    TAG_BG = "rgba(0, 0, 0, 0.04)"
    BLOCKQUOTE = "#666"
    # 浮窗
    FLOATING_BG = "rgba(255, 255, 255, 245)"
    FLOATING_BG_OPAQUE = "rgb(255, 255, 255)"
    # 弹窗 / Tooltip
    TOOLTIP_BG = "#FFF"
    OVERLAY_BG = "rgba(255, 255, 255, 245)"
    # 标签 badge
    SYS_TAG_BG = "rgba(0,0,0,0.06)"
    SYS_TAG_FG = "#888"
    # 拖拽高亮
    DRAG_BORDER = "#0078D4"
    SELECTED_BORDER_LINE = "#0078D4"


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
    WARNING_ALT = "#FFB347"
    WARNING_HOVER = "#FFB347"
    DANGER = "#FF6B6B"
    DANGER_ALT = "#FF6B6B"
    DONE_GREEN = "#6BCB77"
    DONE_GREEN_ALT = "#6BCB77"
    ICON = "rgba(255, 255, 255, 0.45)"
    TAG_BG = "rgba(255, 255, 255, 0.06)"
    BLOCKQUOTE = "#AAA"
    # 浮窗
    FLOATING_BG = "rgba(45, 45, 45, 245)"
    FLOATING_BG_OPAQUE = "rgb(45, 45, 45)"
    # 弹窗 / Tooltip
    TOOLTIP_BG = "#3C3C3C"
    OVERLAY_BG = "rgba(43, 43, 43, 240)"
    # 标签 badge
    SYS_TAG_BG = "rgba(255,255,255,0.08)"
    SYS_TAG_FG = "#AAA"
    # 拖拽高亮
    DRAG_BORDER = "#60CDFF"
    SELECTED_BORDER_LINE = "#0078D4"


LIGHT = _LightColors()
DARK = _DarkColors()


# ============================================================
# 外挂主题配置（启动时一次性合并，运行时不支持热更新）
# ============================================================
_USER_THEME_PATH: Path | None = None


def _user_theme_path() -> Path:
    """延迟解析用户主题文件路径（避免 import 时与 constants 形成循环）。"""
    global _USER_THEME_PATH
    if _USER_THEME_PATH is None:
        try:
            from config.constants import APP_ID
            _USER_THEME_PATH = Path.home() / f".{APP_ID}" / "theme.json"
        except Exception:
            _USER_THEME_PATH = Path.home() / ".com.easy.todo" / "theme.json"
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
    """从用户 theme.json 合并覆盖到 FontSize / _LightColors / _DarkColors。

    失败（文件不存在、格式错误、权限不足）一律静默回退到内置默认值。
    """
    path = _user_theme_path()
    try:
        if not path.exists():
            return
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return
    if not isinstance(data, dict):
        return

    _apply_overrides_to_class(FontSize, data.get("font_size"), int)
    _apply_overrides_to_class(_LightColors, data.get("light"), str)
    _apply_overrides_to_class(_DarkColors, data.get("dark"), str)


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


def pick(light_value: str, dark_value: str) -> str:
    """根据主题选择颜色值（短写）"""
    return dark_value if isDarkTheme() else light_value


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
    }


# ============================================================
# Tooltip 样式片段
# ============================================================
def card_hover_style(bg_var: str = "hover_bg", selector: str = "CardWidget") -> str:
    """生成带 hover 背景的卡片样式片段"""
    c = theme_colors()
    return f"""
        {selector} {{
            border: none;
            border-radius: 8px;
            background-color: transparent;
        }}
        {selector}:hover {{
            background-color: {c[bg_var]};
        }}
    """


def divider_color() -> str:
    """统一分隔线颜色"""
    return palette().DIVIDER


def accent_color() -> str:
    """主题强调色"""
    return palette().ACCENT


def warning_color() -> str:
    """统一警告色（与 settings.warning_color 保持一致）"""
    return palette().WARNING


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
        a = int(float(a_val) * 255) if a_val is not None else alpha
        return r, g, b, a

    # 解析失败 → 使用调色板兜底
    fallback = palette().FLOATING_BG_OPAQUE
    fr, fg, fb, fa = color_to_rgba(fallback, alpha)
    return fr, fg, fb, fa


def bg_rgba(alpha: int = 255) -> tuple[int, int, int, int]:
    """当前主题 BG 的 rgba 拆分（用于浮窗等需要叠加 alpha 的场景）。"""
    return color_to_rgba(palette().BG, alpha)
