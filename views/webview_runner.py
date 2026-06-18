"""任务详情 webview 子进程入口（长驻版）

主进程通过 stdin 每行发送一个 JSON 对象，本进程复用 WebView2 引擎渲染多个任务详情。
首次启动初始化引擎（约 1s），后续点击仅更新 HTML（约 100ms）。
完全与主 Qt 进程解耦，不会影响主程序的事件循环。
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
import traceback
from datetime import date, datetime
from html import escape
from pathlib import Path

# 在 import qtpy 之前设置 Qt 后端
os.environ.setdefault("QT_API", "pyside6")


# ============== 主题 ==============
THEMES = {
    "dark": {
        "bg": "#1F1F1F",
        "card_bg": "#2D2D2D",
        "card_hover": "#333333",
        "border": "rgba(255, 255, 255, 0.08)",
        "title": "#EEE",
        "subtitle": "#CCC",
        "body": "#BBB",
        "muted": "#888",
        "icon": "rgba(255, 255, 255, 0.45)",
        "accent": "#60CDFF",
        "divider": "rgba(255, 255, 255, 0.06)",
        "tag_bg": "rgba(255, 255, 255, 0.06)",
        "priority_urgent_important": "#FF6B6B",
        "priority_important": "#FFB347",
        "priority_urgent": "#60CDFF",
        "priority_minor": "#8764B8",
        "overdue": "#FF6B6B",
        "done_green": "#6BCB77",
        "code_bg": "#3A3A3A",
        "code_border": "#555",
        "link_color": "#60CDFF",
        "blockquote_color": "#AAA",
        "header_bg": "#262626",
    },
    "light": {
        "bg": "#FAFAFA",
        "card_bg": "#FFFFFF",
        "card_hover": "#F5F5F5",
        "border": "rgba(0, 0, 0, 0.06)",
        "title": "#1A1A1A",
        "subtitle": "#444",
        "body": "#555",
        "muted": "#999",
        "icon": "rgba(0, 0, 0, 0.35)",
        "accent": "#0078D4",
        "divider": "rgba(0, 0, 0, 0.06)",
        "tag_bg": "rgba(0, 0, 0, 0.04)",
        "priority_urgent_important": "#D13438",
        "priority_important": "#0078D4",
        "priority_urgent": "#CA5010",
        "priority_minor": "#8764B8",
        "overdue": "#D13438",
        "done_green": "#107C10",
        "code_bg": "#F5F5F5",
        "code_border": "#DDD",
        "link_color": "#0078D4",
        "blockquote_color": "#666",
        "header_bg": "#F0F0F0",
    },
}

# ============== CSS 外挂文件 ==============
# 内置 CSS 文件路径（相对于项目根目录）
_BUILTIN_CSS_PATH = Path(__file__).resolve().parent.parent / "css" / "detail.css"
# 用户自定义 CSS 路径（优先级高于内置）
_USER_CSS_DIR = Path.home() / ".com.easy.todo" / "css"
_USER_CSS_PATH = _USER_CSS_DIR / "detail.css"


def _load_detail_css() -> str:
    """加载详情弹窗 CSS，优先使用用户自定义文件，回退到内置文件。"""
    # 1. 用户自定义 CSS（优先）
    if _USER_CSS_PATH.exists():
        try:
            return _USER_CSS_PATH.read_text(encoding="utf-8")
        except Exception:
            pass
    # 2. 内置 CSS
    if _BUILTIN_CSS_PATH.exists():
        try:
            return _BUILTIN_CSS_PATH.read_text(encoding="utf-8")
        except Exception:
            pass
    # 3. 回退：返回空（build_html 会使用内联兜底样式）
    return ""


def _build_css_vars(c: dict) -> str:
    """将主题色字典转为 CSS 自定义属性声明。"""
    # Python key → CSS 变量名: card_bg → --card-bg, done_green → --done-green
    lines = []
    for key, value in c.items():
        css_name = "--" + key.replace("_", "-")
        lines.append(f"    {css_name}: {value};")
    return ":root {\n" + "\n".join(lines) + "\n}"

PRIORITY_MAP = {
    0: "无",
    1: "重要且紧急",
    2: "重要不紧急",
    3: "不重要但紧急",
    4: "不重要不紧急",
}
STATUS_MAP = {0: "待办", 1: "已完成", 2: "已归档"}
RECURRENCE_TYPES = {"daily": "每天", "weekly": "每周", "monthly": "每月", "workday": "工作日"}
WEEKDAY_NAMES = {1: "一", 2: "二", 3: "三", 4: "四", 5: "五", 6: "六", 7: "日"}


def _parse_recurrence_day(value) -> list:
    if value is None:
        return []
    if isinstance(value, int):
        return [value]
    if isinstance(value, str):
        out = []
        for p in value.split(","):
            p = p.strip()
            if p:
                try:
                    out.append(int(p))
                except ValueError:
                    pass
        return out
    return []


def _render_priority(priority: int, c: dict) -> tuple:
    text = PRIORITY_MAP.get(priority, "无")
    color = {
        1: c["priority_urgent_important"],
        2: c["priority_important"],
        3: c["priority_urgent"],
        4: c["priority_minor"],
    }.get(priority, c["muted"])
    return text, color


def _render_due(due, is_done, c):
    if not due:
        return None
    try:
        due_date = date.fromisoformat(due)
        today = date.today()
        if due_date < today and not is_done:
            return f"{due} (已过期)", c["overdue"]
        if due_date == today:
            return f"{due} (今天)", c["accent"]
        return due, c["body"]
    except (ValueError, TypeError):
        return due, c["body"]


def _render_recurrence(todo: dict):
    rt = todo.get("recurrence_type")
    if not rt:
        return None
    interval = todo.get("recurrence_interval", 1)
    rd = todo.get("recurrence_day")
    if rt == "weekly" and rd:
        days = _parse_recurrence_day(rd)
        names = "".join(WEEKDAY_NAMES.get(d, "") for d in sorted(days))
        text = f"每{interval}周周{names}" if interval > 1 else f"每周{names}"
    elif rt == "monthly" and rd:
        dl = _parse_recurrence_day(rd)
        dv = dl[0] if dl else ""
        text = f"每{interval}月{dv}号" if interval > 1 else f"每月{dv}号"
    elif interval > 1:
        unit = {"daily": "天", "weekly": "周", "monthly": "月"}.get(rt, "")
        text = f"每{interval}{unit}"
    else:
        text = RECURRENCE_TYPES.get(rt, "")
    s, e = todo.get("recurrence_start_date"), todo.get("recurrence_end_date")
    if s and e:
        text += f" ({s} ~ {e})"
    elif s:
        text += f" (从 {s})"
    elif e:
        text += f" (至 {e})"
    return text


def _format_dt(v):
    if not v:
        return None
    try:
        return datetime.fromisoformat(v).strftime("%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        return v


def _rewrite_image_paths(html_str: str, folder: Path) -> str:
    """把 <img src='相对路径'> 改写为 file:// 绝对路径(供 webview 直接显示)。"""
    import re

    def repl(m):
        prefix, src = m.group(1), m.group(2)
        if not src or src.startswith(("file://", "http://", "https://", "data:")):
            return m.group(0)
        candidate = folder / src
        if candidate.exists():
            abs_path = (folder / src).as_posix()
            return f'{prefix}="file:///{abs_path.replace(" ", "%20")}"'
        return m.group(0)

    return re.sub(r'(<img\s+[^>]*?src)="([^"]+)"', repl, html_str)


def build_html(data: dict) -> str:
    theme_mode = data.get("theme", "light")
    c = THEMES.get(theme_mode, THEMES["light"])
    todo = data.get("todo", {})
    is_done = bool(todo.get("_is_done"))
    is_archived = bool(todo.get("_is_archived"))

    # 描述
    md_text = todo.get("description", "") or ""
    task_folder_str = data.get("task_folder", "")
    try:
        import markdown as _md
        md_html = _md.markdown(
            md_text,
            extensions=["fenced_code", "tables", "sane_lists", "nl2br"],
        )
    except ImportError:
        # 简单 fallback:把 \n\n 转 <p>
        import re as _re
        md_html = _re.sub(r"\n\n+", "</p><p>", _re.sub(r"\n", "<br>", escape(md_text)))
        md_html = f"<p>{md_html}</p>"

    if task_folder_str:
        md_html = _rewrite_image_paths(md_html, Path(task_folder_str))

    # CSS：注入主题变量 + 加载外部 CSS 文件
    css_vars = _build_css_vars(c)
    external_css = _load_detail_css()
    if external_css:
        style_block = f"{css_vars}\n{external_css}"
    else:
        # 回退：内置 CSS 文件不存在时使用内联兜底样式
        style_block = f"""{css_vars}
* {{ box-sizing: border-box; }}
html, body {{
    margin: 0; padding: 0;
    background-color: var(--bg); color: var(--body);
    font-family: "Segoe UI", "Microsoft YaHei", "PingFang SC", sans-serif;
    -webkit-user-select: text; user-select: text;
}}
.page {{ margin: 0 auto; padding: 20px 24px 40px; }}
.info-strip {{ display: flex; flex-wrap: wrap; gap: 8px 16px;
    background-color: var(--card-bg); border: 1px solid var(--border);
    border-radius: 10px; padding: 10px 16px; margin-bottom: 14px; font-size: 12px; }}
.info-item {{ display: inline-flex; align-items: center; gap: 6px; color: var(--muted); }}
.info-item .label {{ color: var(--muted); }}
.info-item .value {{ color: var(--body); }}
.info-item .value.accent {{ color: var(--accent); }}
.info-item .value.overdue {{ color: var(--overdue); }}
.info-item .value.done {{ color: var(--done-green); }}
.section {{ background-color: var(--card-bg); border: 1px solid var(--border);
    border-radius: 10px; padding: 16px 20px; margin-bottom: 14px; }}
.section-header {{ color: var(--muted); font-size: 11px; font-weight: bold;
    margin-bottom: 10px; letter-spacing: 0.5px; }}
.desc-empty {{ color: var(--muted); font-size: 13px; text-align: center; padding: 24px 0; }}
.subtask-list {{ list-style: none; padding: 0; margin: 0; }}
.subtask-item {{ display: flex; align-items: center; gap: 8px;
    padding: 6px 0; border-bottom: 1px solid var(--divider); font-size: 13px; }}
.subtask-item:last-child {{ border-bottom: none; }}
.subtask-check {{ width: 14px; height: 14px; border: 1.5px solid var(--muted);
    border-radius: 3px; flex-shrink: 0; display: inline-flex; align-items: center;
    justify-content: center; font-size: 11px; color: var(--done-green); }}
.subtask-check.done {{ border-color: var(--done-green); background-color: var(--done-green); color: white; }}
.subtask-title {{ color: var(--body); }}
.subtask-title.done {{ color: var(--muted); text-decoration: line-through; }}
.file-list {{ list-style: none; padding: 0; margin: 0; }}
.file-item {{ display: flex; align-items: center; gap: 8px;
    padding: 6px 0; border-bottom: 1px solid var(--divider); font-size: 13px;
    cursor: pointer; border-radius: 4px; transition: background-color 0.15s; }}
.file-item:hover {{ background-color: var(--card-hover); }}
.file-item:last-child {{ border-bottom: none; }}
.file-name {{ color: var(--accent); flex: 1; word-break: break-all; }}
.file-size {{ color: var(--muted); font-size: 11px; flex-shrink: 0; }}
.file-folder-btn {{ cursor: pointer; opacity: 0.4; font-size: 14px; padding: 2px 4px;
    border-radius: 4px; transition: opacity 0.15s, background-color 0.15s; flex-shrink: 0; }}
.file-folder-btn:hover {{ opacity: 1; background-color: var(--tag-bg); }}
.markdown-body {{ font-family: "Segoe UI", "Microsoft YaHei", "PingFang SC", sans-serif;
    font-size: 14px; line-height: 1.7; color: var(--body);
    background-color: transparent; padding: 0; margin: 0; }}
.markdown-body h1,.markdown-body h2,.markdown-body h3,
.markdown-body h4,.markdown-body h5,.markdown-body h6 {{
    margin: 12px 0 6px; font-weight: bold; color: var(--title); }}
.markdown-body h1 {{ font-size: 22px; }} .markdown-body h2 {{ font-size: 18px; }}
.markdown-body h3 {{ font-size: 16px; }} .markdown-body h4 {{ font-size: 14px; }}
.markdown-body p {{ margin: 6px 0; }}
.markdown-body code {{ background-color: var(--code-bg); border: 1px solid var(--code-border);
    border-radius: 3px; padding: 1px 5px; font-family: "Cascadia Code", "Consolas", monospace; font-size: 13px; }}
.markdown-body pre {{ background-color: var(--code-bg); border: 1px solid var(--code-border);
    border-radius: 6px; padding: 10px 12px; overflow-x: auto; }}
.markdown-body pre code {{ border: none; padding: 0; background: transparent; }}
.markdown-body blockquote {{ border-left: 3px solid var(--link-color); margin: 8px 0;
    padding: 4px 12px; color: var(--blockquote-color); background-color: var(--tag-bg);
    border-radius: 0 4px 4px 0; }}
.markdown-body a {{ color: var(--link-color); text-decoration: none; }}
.markdown-body ul,.markdown-body ol {{ margin: 6px 0; padding-left: 22px; }}
.markdown-body li {{ margin: 3px 0; }}
.markdown-body hr {{ border: none; border-top: 1px solid var(--code-border); margin: 12px 0; }}
.markdown-body table {{ border-collapse: collapse; margin: 8px 0; }}
.markdown-body th,.markdown-body td {{ border: 1px solid var(--code-border); padding: 6px 10px; }}
.markdown-body th {{ background-color: var(--code-bg); }}
.markdown-body img {{ max-width: 100%; max-height: 480px; border-radius: 4px; }}
"""

    # 状态（移入信息条，标题由原生窗口标题栏显示）
    status = todo.get("status", 0)
    status_text = STATUS_MAP.get(status, "未知")
    if is_archived:
        status_item = (
            f'<span class="info-item"><span class="label">状态</span>'
            f'<span class="value" style="color:{c["muted"]}">已归档</span></span>'
        )
    elif is_done:
        status_item = (
            f'<span class="info-item"><span class="label">状态</span>'
            f'<span class="value done">已完成</span></span>'
        )
    else:
        status_item = (
            f'<span class="info-item"><span class="label">状态</span>'
            f'<span class="value">{escape(status_text)}</span></span>'
        )

    # 信息条
    items = [status_item]
    p = todo.get("priority", 0)
    if p > 0:
        ptext, pcolor = _render_priority(p, c)
        items.append(
            f'<span class="info-item"><span class="label">优先级</span>'
            f'<span class="value" style="color:{pcolor}">{escape(ptext)}</span></span>'
        )
    cat = todo.get("category")
    if cat:
        items.append(
            f'<span class="info-item"><span class="label">分类</span>'
            f'<span class="value">{escape(cat.get("name", ""))}</span></span>'
        )
    s = todo.get("start_date")
    if s:
        items.append(
            f'<span class="info-item"><span class="label">起始</span>'
            f'<span class="value">{escape(s)}</span></span>'
        )
    due = _render_due(todo.get("due_date"), is_done, c)
    if due:
        text, color = due
        cls = "overdue" if color == c["overdue"] else ("accent" if color == c["accent"] else "")
        items.append(
            f'<span class="info-item"><span class="label">截止</span>'
            f'<span class="value {cls}" style="color:{color}">{escape(text)}</span></span>'
        )
    if todo.get("auto_postpone"):
        items.append('<span class="info-item"><span class="value accent">自动延期</span></span>')
    rt_text = _render_recurrence(todo)
    if rt_text:
        items.append(
            f'<span class="info-item"><span class="label">重复</span>'
            f'<span class="value">{escape(rt_text)}</span></span>'
        )
    if is_done:
        comp = _format_dt(todo.get("completed_at"))
        if comp:
            items.append(
                f'<span class="info-item"><span class="label">完成</span>'
                f'<span class="value done">{escape(comp)}</span></span>'
            )
    created = _format_dt(todo.get("created_at"))
    if created:
        items.append(
            f'<span class="info-item"><span class="label">创建</span>'
            f'<span class="value">{escape(created)}</span></span>'
        )
    updated = _format_dt(todo.get("updated_at"))
    if updated:
        items.append(
            f'<span class="info-item"><span class="label">更新</span>'
            f'<span class="value">{escape(updated)}</span></span>'
        )
    info_strip = (
        f'<div class="info-strip">{"".join(items)}</div>' if items else ""
    )

    # 描述
    if md_html.strip():
        desc = f'<div class="section"><div class="section-header">描述</div><div class="markdown-body">{md_html}</div></div>'
    else:
        desc = '<div class="section"><div class="section-header">描述</div><div class="desc-empty">暂无描述</div></div>'

    # 子任务
    children = todo.get("children", []) or []
    if children:
        done_n = sum(1 for ch in children if ch.get("_is_done"))
        total = len(children)
        pct = int(done_n / total * 100) if total else 0
        lis = []
        for ch in children:
            ch_done = bool(ch.get("_is_done"))
            mark = "✓" if ch_done else ""
            cc = "subtask-check done" if ch_done else "subtask-check"
            tc = "subtask-title done" if ch_done else "subtask-title"
            lis.append(
                f'<li class="subtask-item"><span class="{cc}">{mark}</span>'
                f'<span class="{tc}">{escape(ch.get("title", ""))}</span></li>'
            )
        subtasks = (
            f'<div class="section"><div class="section-header">子任务 &nbsp;·&nbsp; '
            f'{done_n}/{total} ({pct}%)</div><ul class="subtask-list">{"".join(lis)}</ul></div>'
        )
    else:
        subtasks = ""

    # 附件
    files = data.get("files", []) or []
    if files:
        lis = []
        for f_info in files:
            name = f_info.get("name", "")
            fpath = f_info.get("path", "")
            size = f_info.get("size", 0) / 1024
            size_text = f"{size:.0f}KB" if size < 1024 else f"{size/1024:.1f}MB"
            safe_path = escape(fpath)
            lis.append(
                f'<li class="file-item" data-path="{safe_path}">'
                f'<span class="file-name">{escape(name)}</span>'
                f'<span class="file-size">{size_text}</span>'
                f'<span class="file-folder-btn" data-path="{safe_path}" title="打开所在文件夹">&#128193;</span>'
                f'</li>'
            )
        files_html = (
            f'<div class="section"><div class="section-header">附件 &nbsp;·&nbsp; '
            f'{len(files)} 个</div><ul class="file-list">{"".join(lis)}</ul></div>'
        )
    else:
        files_html = ""

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>任务详情</title>
<style>
{style_block}
</style>
</head>
<body>
<div class="page">
    {info_strip}
    {desc}
    {subtasks}
    {files_html}
</div>
<script>
document.addEventListener('click', function(e) {{
    // 点击文件夹按钮 → 打开所在文件夹
    var folderBtn = e.target.closest('.file-folder-btn');
    if (folderBtn && folderBtn.dataset.path) {{
        e.stopPropagation();
        if (window.pywebview && window.pywebview.api) {{
            window.pywebview.api.open_file_folder(folderBtn.dataset.path);
        }}
        return;
    }}
    // 点击文件项 → 以系统默认方式打开文件
    var item = e.target.closest('.file-item');
    if (item && item.dataset.path) {{
        if (window.pywebview && window.pywebview.api) {{
            window.pywebview.api.open_file(item.dataset.path);
        }}
    }}
}});
</script>
</body>
</html>"""


def main():
    """长驻模式：从 stdin 读取 JSON 命令行，复用 webview 引擎渲染任务详情。

    首次启动初始化 WebView2 引擎（约 1s），后续点击仅更新 HTML（约 100ms）。
    主进程通过 stdin 每行发送一个 JSON 对象，EOF 时子进程退出。
    """
    try:
        import webview
    except ImportError as e:
        print(f"缺少 pywebview: {e}", file=sys.stderr)
        sys.exit(3)

    # JS API：供前端调用打开文件或文件夹
    class _Api:
        def open_file(self, file_path: str):
            """以系统默认方式打开文件。"""
            if not file_path:
                return
            import platform
            system = platform.system()
            try:
                if system == "Windows":
                    os.startfile(file_path)
                elif system == "Darwin":
                    os.system(f'open "{file_path}"')
                else:
                    import subprocess
                    subprocess.Popen(["xdg-open", file_path])
            except Exception:
                pass

        def open_file_folder(self, file_path: str):
            """在系统文件管理器中打开并定位到指定文件。"""
            if not file_path:
                return
            import platform
            system = platform.system()
            try:
                if system == "Windows":
                    os.system(f'explorer /select,"{file_path}"')
                elif system == "Darwin":
                    os.system(f'open -R "{file_path}"')
                else:
                    import subprocess
                    subprocess.Popen(["xdg-open", str(Path(file_path).parent)])
            except Exception:
                pass

    api = _Api()

    # 隐藏的保活窗口：确保任务窗口关闭后 webview.start() 不会退出
    try:
        keepalive = webview.create_window(
            "__keepalive__", html="<!DOCTYPE html><html></html>", hidden=True
        )
    except Exception as e:
        print(f"创建保活窗口失败: {e}", file=sys.stderr)
        sys.exit(4)

    # task_window 状态：None 表示需要新建，否则复用现有窗口
    state = {"task_window": None}

    def _on_task_closed(*_args, **_kwargs):
        state["task_window"] = None

    def _find_hwnd_by_title(window_title: str) -> int | None:
        """通过 EnumWindows 按窗口标题(精确匹配)查找可见窗口的 HWND。"""
        if sys.platform != "win32":
            return None
        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.windll.user32
            WNDENUMPROC = ctypes.WINFUNCTYPE(
                ctypes.c_bool, wintypes.HWND, wintypes.LPARAM
            )
            found = []

            def callback(hwnd, _lParam):
                if user32.IsWindowVisible(hwnd):
                    length = user32.GetWindowTextLengthW(hwnd)
                    if length > 0:
                        buff = ctypes.create_unicode_buffer(length + 1)
                        user32.GetWindowTextW(hwnd, buff, length + 1)
                        if buff.value == window_title:
                            found.append(hwnd)
                return True

            user32.EnumWindows(WNDENUMPROC(callback), 0)
            return found[0] if found else None
        except Exception:
            return None

    def _apply_window_position(window_title: str, x: int, y: int):
        """轮询找到任务窗口后,通过 SetWindowPos 移动到 (x, y)(尺寸保持不变)。"""
        if sys.platform != "win32":
            return
        try:
            x, y = int(x), int(y)
        except (TypeError, ValueError):
            return

        def _worker():
            try:
                import ctypes
                user32 = ctypes.windll.user32
                SWP_NOSIZE = 0x0001
                SWP_NOZORDER = 0x0004
                SWP_SHOWWINDOW = 0x0040
                for _ in range(50):
                    hwnd = _find_hwnd_by_title(window_title)
                    if hwnd:
                        user32.SetWindowPos(
                            hwnd, 0, x, y, 0, 0,
                            SWP_NOSIZE | SWP_NOZORDER | SWP_SHOWWINDOW,
                        )
                        return
                    time.sleep(0.1)
            except Exception:
                pass

        threading.Thread(target=_worker, daemon=True).start()

    def _apply_native_title_bar_color(window_title: str, bg_hex: str, text_hex: str):
        """通过 Windows DWM API 把原生窗口标题栏背景设为指定背景色（仅 Windows 11+ 生效）。

        任务窗口由 pywebview 在 GUI 线程创建,这里启动守护线程轮询窗口句柄,
        找到后调用 DwmSetWindowAttribute 设置 DWMWA_CAPTION_COLOR / DWMWA_TEXT_COLOR。
        """
        if sys.platform != "win32":
            return
        if not bg_hex or len(bg_hex) != 7 or not bg_hex.startswith("#"):
            return
        if not text_hex or len(text_hex) != 7 or not text_hex.startswith("#"):
            text_hex = "#FFFFFF"

        def _worker():
            try:
                import ctypes
                from ctypes import wintypes

                user32 = ctypes.windll.user32
                dwmapi = ctypes.windll.dwmapi
                DWMWA_CAPTION_COLOR = 35  # Windows 11 22H2+
                DWMWA_TEXT_COLOR = 36
                DWMWA_BORDER_COLOR = 34  # Windows 11 22H2+,设置窗口外边框颜色

                def _to_colorref(hex_color: str) -> int:
                    r = int(hex_color[1:3], 16)
                    g = int(hex_color[3:5], 16)
                    b = int(hex_color[5:7], 16)
                    return (b << 16) | (g << 8) | r

                caption_color = ctypes.c_int(_to_colorref(bg_hex))
                text_color = ctypes.c_int(_to_colorref(text_hex))
                border_color = ctypes.c_int(_to_colorref(bg_hex))

                # 最多轮询 5 秒,等待 pywebview 完成窗口创建
                for _ in range(50):
                    hwnd = _find_hwnd_by_title(window_title)
                    if hwnd:
                        dwmapi.DwmSetWindowAttribute(
                            hwnd, DWMWA_CAPTION_COLOR,
                            ctypes.byref(caption_color),
                            ctypes.sizeof(caption_color),
                        )
                        dwmapi.DwmSetWindowAttribute(
                            hwnd, DWMWA_TEXT_COLOR,
                            ctypes.byref(text_color),
                            ctypes.sizeof(text_color),
                        )
                        dwmapi.DwmSetWindowAttribute(
                            hwnd, DWMWA_BORDER_COLOR,
                            ctypes.byref(border_color),
                            ctypes.sizeof(border_color),
                        )
                        return
                    time.sleep(0.1)
            except Exception:
                pass

        threading.Thread(target=_worker, daemon=True).start()

    def _handle_data(data: dict):
        try:
            html = build_html(data)
        except Exception:
            traceback.print_exc()
            return
        title = "任务详情"
        theme_mode = data.get("theme", "light")
        # 标题栏背景与弹窗内容背景保持一致(深色 #1F1F1F / 浅色 #FAFAFA)
        theme_colors = THEMES.get(theme_mode, THEMES["light"])
        caption_bg = theme_colors["bg"]
        caption_text = theme_colors["title"]
        popup_pos = data.get("popup_pos")
        existing = state["task_window"]
        # 快速路径：复用已存在的任务窗口，仅更新内容
        if existing is not None:
            try:
                existing.set_title(title)
                existing.load_html(html)
                existing.show()
                existing.restore()
                _apply_native_title_bar_color(title, caption_bg, caption_text)
                if popup_pos and isinstance(popup_pos, (list, tuple)) and len(popup_pos) == 2:
                    _apply_window_position(title, popup_pos[0], popup_pos[1])
                return
            except Exception:
                state["task_window"] = None
        # 慢速路径：任务窗口已被关闭，新建一个（引擎已就绪，耗时远低于冷启动）
        try:
            win = webview.create_window(
                title,
                html=html,
                width=900,
                height=720,
                resizable=True,
                text_select=True,
                on_top=False,
                background_color=caption_bg,
                js_api=api,
            )
            win.events.closed += _on_task_closed
            state["task_window"] = win
            _apply_native_title_bar_color(title, caption_bg, caption_text)
            if popup_pos and isinstance(popup_pos, (list, tuple)) and len(popup_pos) == 2:
                _apply_window_position(title, popup_pos[0], popup_pos[1])
        except Exception:
            traceback.print_exc()

    def reader_loop():
        """在 webview 事件循环启动后的独立线程中读取 stdin。"""
        stdin = sys.stdin
        # 优先用二进制读取，避免 Windows 默认编码非 UTF-8 导致乱码
        buf = getattr(stdin, "buffer", None)
        while True:
            try:
                raw = buf.readline() if buf is not None else stdin.readline()
            except Exception:
                break
            if not raw:
                break  # EOF：主进程已退出
            line = raw.decode("utf-8", errors="ignore").strip() if isinstance(raw, (bytes, bytearray)) else raw.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            _handle_data(data)
        # stdin 关闭 → 销毁保活窗口，让 webview.start() 返回
        try:
            keepalive.destroy()
        except Exception:
            pass

    webview.start(func=reader_loop)


if __name__ == "__main__":
    main()
