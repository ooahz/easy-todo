"""新手指南对话框"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QColor, QPainterPath
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QWidget, QLabel, QFrame,
)

from qfluentwidgets import (
    FluentIcon, TransparentToolButton, SubtitleLabel, BodyLabel, CaptionLabel,
    isDarkTheme, SmoothScrollArea,
)

from config.theme_config import FontSize, palette


class _GuideItem(QWidget):
    """单个指南条目（支持多段内容）"""

    def __init__(self, title: str, segments, index: int, parent=None):
        super().__init__(parent)
        # 允许传入 str / list[str] / tuple[str, ...]，统一为 list[str]
        if isinstance(segments, str):
            self._segments = [segments]
        else:
            self._segments = [s for s in segments if s]
        self._setup_ui(title, self._segments, index)

    def _setup_ui(self, title: str, segments: list[str], index: int):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 16)
        layout.setSpacing(8)

        c = palette()
        title_color = c.TITLE
        accent = c.ACCENT

        # 标题行
        title_row = QHBoxLayout()
        title_row.setSpacing(8)

        index_label = QLabel(str(index))
        index_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        index_label.setFixedSize(22, 22)
        index_label.setStyleSheet(
            f"color: #FFF; background-color: {accent}; border-radius: 11px; "
            f"font-size: {FontSize.SMALL}px; font-weight: bold;"
        )
        title_row.addWidget(index_label)

        title_lbl = BodyLabel(title)
        title_lbl.setStyleSheet(
            f"color: {title_color}; font-size: {FontSize.MEDIUM}px; font-weight: bold;"
        )
        title_row.addWidget(title_lbl)
        title_row.addStretch()

        layout.addLayout(title_row)

        # 多段内容：每段渲染为独立的 BodyLabel，分段之间增加纵向间距
        for seg in segments:
            content_lbl = BodyLabel(seg)
            content_lbl.setWordWrap(True)
            content_lbl.setTextFormat(Qt.TextFormat.PlainText)
            content_lbl.setStyleSheet(
                f"color: {c.BODY}; font-size: {FontSize.BODY}px; line-height: 1.6;"
            )
            layout.addWidget(content_lbl)


class BeginnerGuideDialog(QDialog):
    """新手指南对话框"""
    GUIDE_ITEMS = [
        (
            "自定义配置",
            [
                "大部分配置项均可在设置中配置",
                "部分字体大小和背景颜色等配置项，支持在本地文件 theme.json 中配置",
            ],
        ),
        (
            "浮窗模式",
            [
                "拖动浮窗边缘调整浮窗尺寸",
                "点击固定按钮，会记录浮窗的位置和尺寸",
                "浮窗的任务列表是根据打开浮窗时所在的视图的列表加载的（包括过滤条件）",
            ],
        ),
        (
            "日程视图",
            [
                "日程视图支持联网/本地加载节假日信息（需要在设置中开启/本地配置）",
                "当获取到节假日信息后，可以在重复任务中选择工作日重复功能",
            ],
        ),
        (
            "新建任务",
            [
                "新建任务弹窗支持调整尺寸，在当前任务“保存”后会记录当前窗口尺寸",
                "新建任务弹窗右上角可选切换任务类型（默认任务、重复任务、周期任务）",
            ],
        ),
        (
            "归档功能",
            [
                "已完成的任务支持归档，可以在已完成的任务视图中选择一键归档",
                "归档后的任务只能查看和删除不能编辑和恢复，请谨慎操作",
            ],
        ),
        (
            "窗口尺寸",
            "大部分窗口都支持调节尺寸，并支持记忆，只是记忆触发的方式不同",
        ),
        (
            "任务详情",
            [
                "点击任务列表，会打开任务详情",
                "任务详情的图片支持双击或者右键查看",
                "任务详情可以查看任务关联的文件，这些文件都是储存在本地，可以在设置中调整保存的路径",
            ],
        ),
        (
            "布局模式",
            [
                "在设置中切换布局模式后，新建任务和任务详情的样式均会改变",
                "分栏模式适合描述内容较多的场景，任务详情对富文本的支持也会更加友好",
            ],
        ),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(520, 520)
        self._setup_ui()
        self._drag_pos = None

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        # ---- 顶部栏 ----
        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)

        title_label = SubtitleLabel("新手指南")
        title_label.setStyleSheet(
            f"font-weight: bold; color: {palette().TITLE if isDarkTheme() else '#111'};"
        )
        top_bar.addWidget(title_label, 1)

        close_btn = TransparentToolButton(FluentIcon.CLOSE)
        close_btn.setFixedSize(28, 28)
        close_btn.clicked.connect(self.reject)
        top_bar.addWidget(close_btn)

        layout.addLayout(top_bar)

        # 分隔线
        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet(f"background-color: {palette().DIVIDER};")
        layout.addWidget(divider)

        # ---- 提示语 ----
        tip_label = CaptionLabel("快速了解 Easy Todo 的小技巧")
        tip_label.setStyleSheet(f"color: {palette().MUTED}; font-size: {FontSize.SMALL}px;")
        layout.addWidget(tip_label)

        # ---- 滚动内容区 ----
        self.scroll_area = SmoothScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet(
            "SmoothScrollArea { border: none; background: transparent; }"
        )
        self.scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        self.scroll_widget = QWidget(self.scroll_area)
        self.scroll_widget.setStyleSheet("background: transparent;")
        content_layout = QVBoxLayout(self.scroll_widget)
        content_layout.setContentsMargins(4, 4, 12, 4)
        content_layout.setSpacing(0)

        # 每条指南的格式：(title, content_or_segments)
        # - content_or_segments 可以是 str（一段）
        # - 也可以是 list[str] / tuple[str, ...]（多段，每段独立成行）
        for i, item in enumerate(self.GUIDE_ITEMS, start=1):
            title, content = item[0], item[1]
            guide_item = _GuideItem(title, content, i)
            content_layout.addWidget(guide_item)

            if i < len(self.GUIDE_ITEMS):
                sep = QFrame()
                sep.setFixedHeight(1)
                sep.setStyleSheet(f"background-color: {palette().DIVIDER}; margin: 4px 0;")
                content_layout.addWidget(sep)

        content_layout.addStretch()

        self.scroll_area.setWidget(self.scroll_widget)
        layout.addWidget(self.scroll_area, 1)

    def showEvent(self, event):
        super().showEvent(event)
        screen = self.screen().availableGeometry()
        x = screen.x() + (screen.width() - self.width()) // 2
        y = screen.y() + (screen.height() - self.height()) // 2
        self.move(x, y)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and self._drag_pos is not None:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        dark = isDarkTheme()
        bg_color = QColor(43, 43, 43) if dark else QColor(249, 249, 249)
        border_color = QColor(60, 60, 60) if dark else QColor(210, 210, 210)
        path = QPainterPath()
        path.addRoundedRect(0.5, 0.5, self.width() - 1, self.height() - 1, 10, 10)
        painter.fillPath(path, bg_color)
        painter.setPen(border_color)
        painter.drawPath(path)
        super().paintEvent(event)
