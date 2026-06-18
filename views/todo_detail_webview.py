"""任务详情预览 - pywebview 子进程长驻版(只读,上下结构)

通过单例 _WebViewProcessManager 复用 webview 子进程，
避免每次点击都重新启动 Python + 导入 pywebview + 初始化 WebView2 引擎。
首次点击后引擎常驻，后续点击仅通过 stdin 发送数据 + 更新 HTML。
"""
from __future__ import annotations

import json
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any

from config.settings import settings
from services.file_service import FileService


def _is_dark() -> bool:
    """读取应用当前主题(优先 qfluentwidgets 的运行时状态,fallback 到 settings)。"""
    try:
        from qfluentwidgets import isDarkTheme
        return bool(isDarkTheme())
    except Exception:
        # settings.theme: "light" / "dark" / "system"
        theme = (settings.theme or "system").lower()
        if theme == "dark":
            return True
        if theme == "light":
            return False
        # system:回退到 darkdetect
        try:
            import darkdetect
            return bool(darkdetect.isDark())
        except Exception:
            return False


def _runner_command() -> list[str] | None:
    """构造启动 webview_runner 子进程的命令。

    源码模式: python webview_runner.py
    打包模式: EasyTodo.exe --webview-runner (由 main.py 早期拦截)
    """
    if getattr(sys, "frozen", False):
        return [sys.executable, "--webview-runner"]
    runner_path = Path(__file__).parent / "webview_runner.py"
    if not runner_path.exists():
        return None
    return [sys.executable, str(runner_path)]


class _WebViewProcessManager:
    """管理长驻 webview 子进程，复用引擎以加速后续渲染。"""

    def __init__(self):
        self._process: subprocess.Popen | None = None
        self._lock = threading.Lock()

    def ensure_running(self) -> bool:
        """确保子进程已启动（幂等）。返回是否可用。"""
        with self._lock:
            if self._process is not None and self._process.poll() is None:
                return True
            return self._start()

    def _start(self) -> bool:
        cmd = _runner_command()
        if not cmd:
            self._on_failure("找不到 webview_runner.py")
            return False
        try:
            self._process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
                close_fds=True,
            )
        except Exception as e:
            self._process = None
            self._on_failure(f"启动子进程失败: {e}")
            return False
        return True

    def send(self, data: dict):
        """发送任务数据到子进程渲染。子进程不可用时会自动重启一次。"""
        if not self.ensure_running():
            return
        proc = self._process
        if proc is None or proc.stdin is None:
            self._on_failure("webview 子进程未就绪")
            return
        payload = (json.dumps(data, ensure_ascii=False, default=str) + "\n").encode("utf-8")
        try:
            proc.stdin.write(payload)
            proc.stdin.flush()
        except (BrokenPipeError, OSError, ValueError):
            # 子进程已退出，重启并重试一次
            self._process = None
            if self._start():
                proc = self._process
                if proc and proc.stdin:
                    try:
                        proc.stdin.write(payload)
                        proc.stdin.flush()
                    except Exception as e:
                        self._on_failure(f"发送数据失败: {e}")
            else:
                self._on_failure("webview 子进程重启失败")

    def stop(self):
        """关闭子进程（应用退出时调用）。"""
        with self._lock:
            proc = self._process
            self._process = None
        if proc is None:
            return
        try:
            if proc.stdin:
                proc.stdin.close()
        except Exception:
            pass
        try:
            proc.wait(timeout=2)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass

    def _on_failure(self, msg: str):
        try:
            from qfluentwidgets import InfoBar
            from qfluentwidgets import InfoBarPosition
            from PySide6.QtWidgets import QApplication
            parent = QApplication.activeWindow()
            InfoBar.error(
                title="任务详情预览启动失败",
                content=msg,
                parent=parent,
                position=InfoBarPosition.TOP,
                duration=5000,
            )
        except Exception:
            pass


# 全局单例
_manager = _WebViewProcessManager()


def ensure_webview_running():
    """预热：提前启动 webview 子进程以初始化引擎（不阻塞主线程）。"""
    _manager.ensure_running()


def stop_webview():
    """退出时关闭 webview 子进程。"""
    _manager.stop()


class TodoDetailWebView:
    """在复用的子进程中渲染任务详情(只读,上下结构)。"""

    def __init__(self, todo_data: dict, todo_id: int,
                 popup_pos: tuple[int, int] | None = None):
        self._todo_data = todo_data
        self._current_todo_id = todo_id
        self._popup_pos = popup_pos
        self._file_service = FileService()

    def show(self):
        """预处理数据 + 发送到常驻子进程渲染。"""
        data = self._prepare_data()
        _manager.send(data)

    def _prepare_data(self) -> dict[str, Any]:
        """把 todo 数据 + 主题 + 文件清单打包成 dict 传给子进程。"""
        todo = self._todo_data
        task_folder = ""
        try:
            task_folder = str(self._file_service._get_task_folder(self._current_todo_id))
        except Exception:
            pass

        files = self._collect_files(todo)
        return {
            "theme": "dark" if _is_dark() else "light",
            "popup_pos": list(self._popup_pos) if self._popup_pos else None,
            "task_folder": task_folder,
            "files": files,
            "todo": todo,
        }

    def _collect_files(self, todo: dict) -> list[dict]:
        files: list[dict] = []
        try:
            files = self._file_service.get_files(self._current_todo_id)
        except Exception:
            return []
        template_id = todo.get("recurrence_template_id")
        if template_id and todo.get("recurrence_type"):
            try:
                template_files = self._file_service.get_files(template_id)
                existing = {f["path"] for f in files}
                for tf in template_files:
                    if tf["path"] not in existing:
                        tf["_from_template"] = True
                        files.append(tf)
            except Exception:
                pass
        return files
