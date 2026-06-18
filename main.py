"""
 * @author 十玖八柒（Ahzoo）
 * @description Easy Todo - 待办事项管理工具
 * @github https://github.com/ooahz
 * @date 2026/04
"""

import sys
import os
import warnings

# 在 import qtpy 之前设置 Qt 后端,让 pywebview 的 Qt 平台能找到 PySide6
os.environ.setdefault("QT_API", "pyside6")

# 将项目根目录加入 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 抑制 PySide6 弃用警告
warnings.filterwarnings("ignore", category=DeprecationWarning)

# 打包模式下，通过 --webview-runner 标志启动长驻 webview 子进程，
# 避免重新加载整个主程序。必须在 PySide6 等重模块 import 之前拦截。
if "--webview-runner" in sys.argv:
    from views.webview_runner import main as _runner_main
    _runner_main()
    sys.exit(0)

from PySide6.QtCore import Qt, QSharedMemory
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont, QColor, QIcon
from qfluentwidgets import FluentIcon

from config.constants import APP_NAME, APP_VERSION
from config.settings import settings
from models.database import db
from views.main_window import MainWindow

_shared_memory = None


def main():
    global _shared_memory

    # 单实例检测
    _shared_memory = QSharedMemory(f"EasyTodo_SingleInstance")
    if _shared_memory.attach():
        _shared_memory.detach()
    if not _shared_memory.create(1):
        # 已有实例运行，退出
        sys.exit(0)

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)

    # 设置应用图标
    icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "icon.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    # 设置字体
    font = QFont("Microsoft YaHei", 10)
    font.setStyleStrategy(QFont.PreferAntialias)
    app.setFont(font)

    # 初始化数据库
    db.create_tables()

    # 设置主题色
    try:
        from qfluentwidgets import qconfig
        qconfig.set(qconfig.themeColor, QColor(settings.theme_color))
    except Exception:
        pass

    # 创建并显示主窗口
    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
