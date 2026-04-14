"""设置页面 - 内嵌导航子页面"""
from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame

from qfluentwidgets import (
    BodyLabel, CaptionLabel, Slider, ComboBox, CheckBox,
    PrimaryPushButton, PushButton, FluentIcon, SmoothScrollArea,
    setTheme, Theme, isDarkTheme, setCustomStyleSheet
)

from config.settings import settings
from config.constants import APP_NAME, APP_VERSION
from views.style_sheet import StyleSheet


class SettingsPage(QWidget):
    """设置页面"""

    opacity_changed = Signal(float)
    theme_changed = Signal(str)
    show_done_changed = Signal(bool)
    auto_start_changed = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cards: list[QFrame] = []
        self._setup_ui()

    def _setup_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(20, 16, 20, 8)
        self.main_layout.setSpacing(12)

        # ---- 顶部工具栏（与其他页面一致） ----
        self.toolbar = QHBoxLayout()
        self.toolbar.setSpacing(8)
        self.toolbar.addStretch()
        self.main_layout.addLayout(self.toolbar)

        # ---- 统计行（占位，与其他页面一致） ----
        self.stats_label = CaptionLabel("")
        self.main_layout.addWidget(self.stats_label)

        # ---- 滚动区域 ----
        self.scroll_area = SmoothScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet(
            "SmoothScrollArea { border: none; background: transparent; }"
        )
        self.scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        self.scroll_widget = QWidget()
        self.scroll_widget.setStyleSheet("background: transparent;")
        self.list_layout = QVBoxLayout(self.scroll_widget)
        self.list_layout.setContentsMargins(0, 0, 8, 0)
        self.list_layout.setSpacing(10)

        # ---- 设置卡片 ----
        self.list_layout.addWidget(self._make_card("主题", [
            self._make_combo_row("外观", self._create_theme_combo()),
        ]))

        self.list_layout.addWidget(self._make_card("列表显示", [
            self._create_show_done_cb(),
        ]))

        self.list_layout.addWidget(self._make_card("浮窗", [
            self._make_slider_row(),
        ]))

        self.list_layout.addWidget(self._make_card("数据管理", [
            self._make_data_btns(),
        ]))

        self.list_layout.addWidget(self._make_card("通用", [
            self._create_auto_start_cb(),
        ]))

        self.list_layout.addWidget(self._make_about_card())

        self.list_layout.addStretch()

        self.scroll_area.setWidget(self.scroll_widget)
        self.main_layout.addWidget(self.scroll_area, 1)

    def _make_card(self, title: str, rows: list) -> QFrame:
        """创建设置卡片"""
        card = QFrame()
        card.setObjectName("settingsCard")
        self._cards.append(card)

        StyleSheet.SETTINGS_CARD.apply(card)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 12, 16, 12)
        card_layout.setSpacing(8)

        title_label = BodyLabel(title)
        title_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        card_layout.addWidget(title_label)

        for row in rows:
            if isinstance(row, QWidget):
                card_layout.addWidget(row)
            else:
                card_layout.addLayout(row)

        return card

    def _make_about_card(self) -> QFrame:
        """创建关于卡片"""
        card = QFrame()
        card.setObjectName("settingsCard")
        self._cards.append(card)

        StyleSheet.SETTINGS_CARD.apply(card)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 16, 16, 16)
        card_layout.setSpacing(6)

        # 应用名 + 版本
        header = QHBoxLayout()
        header.setSpacing(8)

        name_label = BodyLabel(APP_NAME)
        name_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        name_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        header.addWidget(name_label)

        ver_label = BodyLabel(f"v{APP_VERSION}")
        ver_label.setStyleSheet("color: #888; font-size: 12px;")
        ver_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        header.addWidget(ver_label)

        header.addStretch()
        card_layout.addLayout(header)

        # 分隔线
        sep = QLabel()
        sep.setFixedHeight(1)
        sep.setObjectName("aboutSep")
        setCustomStyleSheet(
            sep,
            "#aboutSep { background-color: rgba(0,0,0,0.06); }",
            "#aboutSep { background-color: rgba(255,255,255,0.06); }"
        )
        card_layout.addWidget(sep)

        # 描述
        desc_label = BodyLabel("现代化本地待办管理应用")
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #888; font-size: 12px;")
        card_layout.addWidget(desc_label)

        # 作者
        author_row = QHBoxLayout()
        author_row.setSpacing(6)
        author_key = BodyLabel("作者")
        author_key.setStyleSheet("color: #888; font-size: 12px;")
        author_row.addWidget(author_key)
        author_val = BodyLabel("十玖八柒")
        author_val.setStyleSheet("font-size: 12px;")
        author_val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        author_row.addWidget(author_val)
        author_row.addStretch()
        card_layout.addLayout(author_row)

        # 开源仓库
        repo_row = QHBoxLayout()
        repo_row.setSpacing(6)
        repo_key = BodyLabel("仓库")
        repo_key.setStyleSheet("color: #888; font-size: 12px;")
        repo_row.addWidget(repo_key)
        repo_val = BodyLabel("github.com/ooahz")
        repo_val.setStyleSheet("color: #0078D4; font-size: 12px;")
        repo_val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        repo_row.addWidget(repo_val)
        repo_row.addStretch()
        card_layout.addLayout(repo_row)

        return card

    def _create_theme_combo(self) -> ComboBox:
        self.theme_combo = ComboBox()
        self.theme_combo.addItems(["浅色", "深色", "跟随系统"])
        current = settings.theme
        idx = {"light": 0, "dark": 1, "system": 2}.get(current, 0)
        self.theme_combo.setCurrentIndex(idx)
        self.theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        return self.theme_combo

    def _make_combo_row(self, label_text: str, combo: ComboBox) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(12)
        label = BodyLabel(label_text)
        label.setFixedWidth(60)
        row.addWidget(label)
        row.addWidget(combo)
        row.addStretch()
        return row

    def _create_show_done_cb(self) -> CheckBox:
        self.show_done_cb = CheckBox("在任务列表中展示已完成的任务")
        self.show_done_cb.setChecked(settings.show_done_tasks)
        self.show_done_cb.checkStateChanged.connect(self._on_show_done_changed)
        return self.show_done_cb

    def _create_auto_start_cb(self) -> CheckBox:
        self.auto_start_cb = CheckBox("开机自动启动")
        self.auto_start_cb.setChecked(settings.auto_start)
        self.auto_start_cb.checkStateChanged.connect(self._on_auto_start_changed)
        return self.auto_start_cb

    def _make_slider_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(12)

        label = BodyLabel("透明度")
        label.setFixedWidth(60)
        row.addWidget(label)

        self.opacity_slider = Slider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(10, 100)
        self.opacity_slider.setValue(int(settings.floating_opacity * 100))
        self.opacity_slider.valueChanged.connect(self._on_opacity_changed)
        row.addWidget(self.opacity_slider)

        self.opacity_value_label = BodyLabel(f"{int(settings.floating_opacity * 100)}%")
        self.opacity_value_label.setFixedWidth(36)
        row.addWidget(self.opacity_value_label)

        return row

    def _make_data_btns(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(10)

        self.export_btn = PushButton(FluentIcon.SAVE.icon(), "导出数据")
        row.addWidget(self.export_btn)

        self.import_btn = PushButton(FluentIcon.FOLDER.icon(), "导入数据")
        row.addWidget(self.import_btn)

        row.addStretch()
        return row

    def _on_opacity_changed(self, value: int):
        percent = value / 100.0
        self.opacity_value_label.setText(f"{value}%")
        self.opacity_changed.emit(percent)
        settings.floating_opacity = percent

    def _on_theme_changed(self, index: int):
        themes = ["light", "dark", "system"]
        theme = themes[index] if index < len(themes) else "light"
        settings.theme = theme
        self.theme_changed.emit(theme)

    def _on_show_done_changed(self, state):
        checked = (state == Qt.CheckState.Checked)
        settings.show_done_tasks = checked
        self.show_done_changed.emit(checked)

    def _on_auto_start_changed(self, state):
        checked = (state == Qt.CheckState.Checked)
        settings.auto_start = checked
        self.auto_start_changed.emit(checked)
