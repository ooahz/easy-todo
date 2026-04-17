"""Easy Todo App - 应用入口"""
import sys
import os
import warnings

# 将项目根目录加入 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 抑制 PySide6 弃用警告
warnings.filterwarnings("ignore", category=DeprecationWarning)

from PySide6.QtCore import Qt, QSharedMemory
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont, QColor, QIcon
from qfluentwidgets import FluentIcon

from config.constants import APP_NAME, APP_VERSION
from config.settings import settings
from models.database import db
from views.main_window import MainWindow

# 全局共享内存，用于单实例检测
_shared_memory = None


def main():
    global _shared_memory

    # 单实例检测
    _shared_memory = QSharedMemory(f"EasyTodo_SingleInstance")
    if not _shared_memory.create(1):
        # 已有实例运行，退出
        _shared_memory.detach()
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
