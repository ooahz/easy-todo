"""任务详情 webview 子进程入口"""
from __future__ import annotations

import atexit
import json
import os
import sys
import tempfile
import threading
import time
import traceback
from datetime import date, datetime
from html import escape
from pathlib import Path

from config.theme_config import theme_colors_by_name, font_family_str, mono_family_str

# 在 import qtpy 之前设置 Qt 后端
os.environ.setdefault("QT_API", "pyside6")


# ============== 详情页 HTML 临时文件 ==============
_HTML_TMP_PATH: str | None = None


def _write_html_to_tempfile(html: str) -> str | None:
    """把 HTML 写入复用的临时文件,返回 file:// URL;失败返回 None。"""
    global _HTML_TMP_PATH
    try:
        if _HTML_TMP_PATH is None:
            fd, _HTML_TMP_PATH = tempfile.mkstemp(suffix=".html", prefix="easytodo_detail_")
            os.close(fd)
        with open(_HTML_TMP_PATH, "w", encoding="utf-8") as f:
            f.write(html)
    except Exception:
        return None
    return "file:///" + _HTML_TMP_PATH.replace(os.sep, "/")


def _cleanup_html_tmp_file() -> None:
    global _HTML_TMP_PATH
    if _HTML_TMP_PATH is not None:
        try:
            os.unlink(_HTML_TMP_PATH)
        except Exception:
            pass
        _HTML_TMP_PATH = None


atexit.register(_cleanup_html_tmp_file)


# ============== 详情弹窗尺寸 ==============
_WEBVIEW_DEFAULT_SIZE = (480, 520)
_WEBVIEW_MIN_SIZE = (400, 300)


def _load_webview_size(data: dict) -> tuple[int, int]:
    """从主进程传入的数据中读取弹窗尺寸,失败或越界时回退到默认值。"""
    try:
        w = int(data.get("dialog_width", _WEBVIEW_DEFAULT_SIZE[0]))
        h = int(data.get("dialog_height", _WEBVIEW_DEFAULT_SIZE[1]))
        if w < _WEBVIEW_MIN_SIZE[0] or h < _WEBVIEW_MIN_SIZE[1]:
            return _WEBVIEW_DEFAULT_SIZE
        return (w, h)
    except Exception:
        return _WEBVIEW_DEFAULT_SIZE


# ============== 主题 ==============
# 颜色取自 config.theme_config，与主进程保持统一。
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
    """把 <img src='相对路径或绝对路径'> 改写为 file:// 绝对路径(供 webview 直接显示)。"""
    import re
    from html import unescape
    from urllib.parse import quote

    def repl(m):
        prefix, raw_src = m.group(1), m.group(2)
        # markdown 可能输出 HTML 实体(如 &amp;),先反转义再解析路径
        src = unescape(raw_src)
        if not src or src.startswith(("file://", "http://", "https://", "data:")):
            return m.group(0)
        # Windows 绝对路径(C:\...)直接使用,相对路径基于 task folder 解析
        if os.path.isabs(src):
            candidate = Path(src)
        else:
            candidate = folder / src
        if candidate.exists():
            abs_path = candidate.resolve().as_posix()
            # 完整 URL 编码(保留 / 和 : 以兼容 Windows 盘符路径)
            # 修复中文、空格等非 ASCII 字符导致 WebView2 无法加载 file:// 的问题
            encoded = quote(abs_path, safe="/:")
            return f'{prefix}="file:///{encoded}"'
        return m.group(0)

    return re.sub(r'(<img\s+[^>]*?src)="([^"]+)"', repl, html_str)


def build_html(data: dict) -> str:
    theme_mode = data.get("theme", "light")
    c = theme_colors_by_name(theme_mode)
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
    font-family: {font_family_str()};
    -webkit-user-select: text; user-select: text;
}}
::-webkit-scrollbar {{ width: 6px; height: 6px; }}
::-webkit-scrollbar-track {{ background: transparent; }}
::-webkit-scrollbar-thumb {{ background-color: rgba(128, 128, 128, 0.3); border-radius: 3px; }}
::-webkit-scrollbar-thumb:hover {{ background-color: rgba(128, 128, 128, 0.5); }}
::-webkit-scrollbar-corner {{ background: transparent; }}
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
.markdown-body {{ font-family: {font_family_str()};
    font-size: 14px; line-height: 1.7; color: var(--body);
    background-color: transparent; padding: 0; margin: 0; }}
.markdown-body h1,.markdown-body h2,.markdown-body h3,
.markdown-body h4,.markdown-body h5,.markdown-body h6 {{
    margin: 12px 0 6px; font-weight: bold; color: var(--title); }}
.markdown-body h1 {{ font-size: 22px; }} .markdown-body h2 {{ font-size: 18px; }}
.markdown-body h3 {{ font-size: 16px; }} .markdown-body h4 {{ font-size: 14px; }}
.markdown-body p {{ margin: 6px 0; }}
.markdown-body code {{ background-color: var(--code-bg); border: 1px solid var(--code-border);
    border-radius: 3px; padding: 1px 5px; font-family: {mono_family_str()}; font-size: 13px; }}
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

    # 头部
    color_tag = todo.get("color_tag")
    color_dot = (
        f'<span class="color-dot" style="background-color: {escape(color_tag)};"></span>'
        if color_tag else ""
    )
    title_cls = "title done" if is_done else "title"
    status = todo.get("status", 0)
    status_text = STATUS_MAP.get(status, "未知")
    if is_archived:
        tag_cls, tag_text = "status-tag archived", "已归档"
    elif is_done:
        tag_cls, tag_text = "status-tag done", "已完成"
    else:
        tag_cls, tag_text = "status-tag", status_text
    header = f"""
<div class="header">
    {color_dot}
    <h1 class="{title_cls}">{escape(todo.get('title', ''))}</h1>
    <span class="{tag_cls}">{escape(tag_text)}</span>
</div>"""

    # 信息条
    items = []
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
    {header}
    {info_strip}
    {desc}
    {subtasks}
    {files_html}
</div>
<script>
// 把 file:// URL 还原成本地路径,供 open_file 使用
function fileUrlToPath(url) {{
    if (!url || url.indexOf('file://') !== 0) return null;
    var p = url.substring(7);  // 去掉 'file://'
    // Windows: file:///C:/path -> C:/path
    if (/^\/[A-Za-z]:/.test(p)) p = p.substring(1);
    try {{ return decodeURIComponent(p); }} catch (e) {{ return p; }}
}}

// 描述区图片:双击/右键 → 调系统看图器打开
function openDescImage(img) {{
    if (!img || !img.src) return;
    var path = fileUrlToPath(img.src);
    if (!path) return;  // http(s)/data 之类的非本地图,忽略
    if (window.pywebview && window.pywebview.api) {{
        window.pywebview.api.open_file(path);
    }}
}}

document.addEventListener('dblclick', function(e) {{
    var img = e.target.closest('.markdown-body img');
    if (img) {{
        e.preventDefault();
        openDescImage(img);
    }}
}});

document.addEventListener('contextmenu', function(e) {{
    var img = e.target.closest('.markdown-body img');
    if (img) {{
        e.preventDefault();
        openDescImage(img);
    }}
}});

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
    """长驻模式：从 stdin 读取 JSON 命令行，复用 webview 引擎渲染任务详情。"""
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

    def _on_resized(*args):
        """webview 弹窗尺寸变化时通过 stdout 通知主进程保存。"""
        w, h = None, None
        if len(args) >= 2:
            w, h = args[0], args[1]
        elif len(args) == 1 and isinstance(args[0], (tuple, list)) and len(args[0]) == 2:
            w, h = args[0]
        if w is None or h is None:
            return
        try:
            w, h = int(w), int(h)
        except (TypeError, ValueError):
            return
        if w < _WEBVIEW_MIN_SIZE[0] or h < _WEBVIEW_MIN_SIZE[1]:
            return
        # 通过 stdout 通知主进程保存尺寸
        try:
            msg = json.dumps({"type": "resized", "width": w, "height": h})
            sys.stdout.write(msg + "\n")
            sys.stdout.flush()
        except Exception:
            pass

    def _handle_data(data: dict):
        try:
            html = build_html(data)
        except Exception:
            traceback.print_exc()
            return
        title = "任务详情"
        theme_mode = data.get("theme", "light")
        # 标题栏背景与弹窗内容背景保持一致(取自统一主题色配置)
        c = theme_colors_by_name(theme_mode)
        caption_bg = c["bg"]
        caption_text = c["title"]
        popup_pos = data.get("popup_pos")
        existing = state["task_window"]

        # 把 HTML 写到临时文件,以 file:// 加载,这样图片资源(file://)能被同源加载。
        # 直接用 html= 加载会被 WebView2 视为 data: origin,从而拦截 file:// 图片。
        page_url = _write_html_to_tempfile(html)

        if existing is not None:
            try:
                saved_w, saved_h = existing.width, existing.height
            except Exception:
                saved_w, saved_h = _load_webview_size(data)
        else:
            saved_w, saved_h = _load_webview_size(data)

        def _load_into(window):
            if page_url is not None:
                window.load_url(page_url)
            else:
                window.load_html(html, '')

        # 快速路径：复用已存在的任务窗口，仅更新内容
        if existing is not None:
            try:
                existing.set_title(title)
                _load_into(existing)
                existing.show()
                existing.restore()
                _apply_native_title_bar_color(title, caption_bg, caption_text)
                if popup_pos and isinstance(popup_pos, (list, tuple)) and len(popup_pos) == 2:
                    _apply_window_position(title, popup_pos[0], popup_pos[1])
                return
            except Exception:
                state["task_window"] = None
        try:
            kwargs = dict(
                width=saved_w,
                height=saved_h,
                resizable=True,
                text_select=True,
                on_top=False,
                background_color=caption_bg,
                js_api=api,
            )
            if page_url is not None:
                win = webview.create_window(title, url=page_url, **kwargs)
            else:
                win = webview.create_window(title, html=html, **kwargs)
            win.events.closed += _on_task_closed
            win.events.resized += _on_resized
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
        try:
            keepalive.destroy()
        except Exception:
            pass

    webview.start(func=reader_loop)


if __name__ == "__main__":
    main()
