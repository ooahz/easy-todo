"""
 * @author 十玖八柒（Ahzoo）
 * @description Easy Todo - 待办事项管理工具
 * @github https://github.com/ooahz
 * @date 2026/04
"""

import sys
import os
import warnings

os.environ.setdefault("QT_API", "pyside6")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
warnings.filterwarnings("ignore", category=DeprecationWarning)

from PySide6.QtCore import Qt, QObject, QEvent, QSharedMemory
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont, QColor, QIcon
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from qfluentwidgets import FluentIcon

from config.constants import APP_NAME, APP_VERSION
from config.settings import settings
from config.theme_config import font_family_list, app_default_font_size, show_themed_tooltip
from models.database import db
from views.main_window import MainWindow


class _GlobalToolTipFilter(QObject):
    """全局 tooltip 过滤器"""

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.ToolTip:
            text = obj.toolTip()
            if text:
                return show_themed_tooltip(event.globalPos(), text)
        return False


_INSTANCE_SERVER_NAME = "EasyTodo_SingleInstance"


def _notify_running_instance():
    """尝试连接已运行实例的本地服务端（Windows 命名管道） """
    probe = QLocalSocket()
    probe.connectToServer(_INSTANCE_SERVER_NAME)
    if not probe.waitForConnected(500):
        return False
    # 已有实例运行，通知其显示主窗口
    probe.write(b"show")
    probe.flush()
    probe.waitForBytesWritten(500)
    probe.disconnectFromServer()
    if probe.state() != QLocalSocket.LocalSocketState.UnconnectedState:
        probe.waitForDisconnected(500)
    return True


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

    # 设置字体（字体族与默认字号均来自 theme_config，可被 theme.json 覆盖）
    families = font_family_list()
    font = QFont(families[0] if families else "Microsoft YaHei", app_default_font_size())
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
