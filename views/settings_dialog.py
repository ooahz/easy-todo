"""设置页面 - 内嵌导航子页面"""
from PySide6.QtCore import Signal, Qt, QSize
from PySide6.QtGui import QPixmap, QFont
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QGraphicsOpacityEffect

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
    home_page_changed = Signal(str)
    sort_rule_changed = Signal(str)
    done_at_bottom_changed = Signal(bool)
    floating_top_changed = Signal(bool)

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
        self.list_layout.addWidget(self._make_card("外观", [
            self._make_combo_row("主题", self._create_theme_combo()),
        ]))

        self.list_layout.addWidget(self._make_card("任务列表", [
            self._create_show_done_cb(),
            self._create_done_at_bottom_cb(),
        ]))

        self.list_layout.addWidget(self._make_card("排序规则", [
            self._make_combo_row("排序", self._create_sort_rule_combo()),
        ]))

        self.list_layout.addWidget(self._make_card("浮窗设置", [
            self._make_slider_row(),
            self._create_floating_top_cb(),
        ]))

        self.list_layout.addWidget(self._make_card("数据", [
            self._make_data_btns(),
        ]))

        self.list_layout.addWidget(self._make_card("启动", [
            self._make_combo_row("首屏", self._create_home_page_combo()),
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
        title_label.setFont(QFont("Microsoft YaHei", 12))
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
        card_layout.setContentsMargins(20, 20, 20, 20)
        card_layout.setSpacing(0)

        # 应用名区域
        header_container = QVBoxLayout()
        header_container.setSpacing(12)

        # 应用名
        name_label = BodyLabel(APP_NAME)
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_label.setFont(QFont("Microsoft YaHei", 15))
        name_label.setMargin(7)
        name_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        card_layout.addWidget(name_label)

        # 版本号
        ver_label = BodyLabel(f"v{APP_VERSION}")
        ver_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ver_label.setStyleSheet("""
            color: #0078D4;
            font-size: 13px;
            font-weight: 500;
        """)
        ver_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        card_layout.addWidget(ver_label)

        # 分隔线
        sep1 = QLabel()
        sep1.setFixedHeight(1)
        sep1.setObjectName("aboutSep1")
        setCustomStyleSheet(
            sep1,
            "#aboutSep1 { background-color: rgba(0,0,0,0.08); margin: 12px 0; }",
            "#aboutSep1 { background-color: rgba(255,255,255,0.08); margin: 12px 0; }"
        )
        card_layout.addWidget(sep1)

        # 描述
        desc_label = BodyLabel("现代化本地待办管理应用")
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("""
            color: #666;
            font-size: 13px;
            line-height: 1.5;
            margin-bottom: 18px;
        """)
        setCustomStyleSheet(
            desc_label,
            "color: #666;",
            "color: #AAA;"
        )
        card_layout.addWidget(desc_label)

        # 信息容器
        info_container = QVBoxLayout()
        info_container.setSpacing(10)

        # 作者信息
        author_row = QHBoxLayout()
        author_row.setSpacing(8)
        author_row.addStretch()

        author_icon = QLabel()
        author_icon.setFixedSize(16, 16)
        author_icon.setStyleSheet("""
            background: #0078D4;
            border-radius: 8px;
        """)
        author_row.addWidget(author_icon)

        author_key = BodyLabel("作者")
        author_key.setStyleSheet("color: #888; font-size: 13px;")
        author_row.addWidget(author_key)

        author_val = BodyLabel("十玖八柒")
        author_val.setStyleSheet("font-size: 13px; font-weight: 500;")
        author_val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        author_row.addWidget(author_val)
        author_row.addStretch()
        info_container.addLayout(author_row)

        # 仓库信息
        repo_row = QHBoxLayout()
        repo_row.setSpacing(8)
        repo_row.addStretch()

        repo_icon = QLabel()
        repo_icon.setFixedSize(16, 16)
        repo_icon.setStyleSheet("""
            background: #8764B8;
            border-radius: 8px;
        """)
        repo_row.addWidget(repo_icon)

        repo_key = BodyLabel("仓库")
        repo_key.setStyleSheet("color: #888; font-size: 13px;")
        repo_row.addWidget(repo_key)

        repo_val = BodyLabel("github.com/ooahz")
        repo_val.setStyleSheet("""
            color: #0078D4;
            font-size: 13px;
            font-weight: 500;
            text-decoration: none;
        """)
        repo_val.setCursor(Qt.CursorShape.PointingHandCursor)
        repo_val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        repo_row.addWidget(repo_val)
        repo_row.addStretch()
        info_container.addLayout(repo_row)

        card_layout.addLayout(info_container)

        # 底部分隔线
        sep2 = QLabel()
        sep2.setFixedHeight(1)
        sep2.setObjectName("aboutSep2")
        setCustomStyleSheet(
            sep2,
            "#aboutSep2 { background-color: rgba(0,0,0,0.08); margin-top: 16px; }",
            "#aboutSep2 { background-color: rgba(255,255,255,0.08); margin-top: 16px; }"
        )
        card_layout.addWidget(sep2)

        # 版权信息
        copyright_label = CaptionLabel("© 2026 Easy Todo. All rights reserved.")
        copyright_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        copyright_label.setStyleSheet("""
            color: #999;
            font-size: 11px;
            margin-top: 18px;
        """)
        setCustomStyleSheet(
            copyright_label,
            "color: #999;",
            "color: #777;"
        )
        card_layout.addWidget(copyright_label)

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

    def _create_done_at_bottom_cb(self) -> CheckBox:
        self.done_at_bottom_cb = CheckBox("已完成任务置底")
        self.done_at_bottom_cb.setChecked(settings.done_at_bottom)
        self.done_at_bottom_cb.checkStateChanged.connect(self._on_done_at_bottom_changed)
        return self.done_at_bottom_cb

    def _create_sort_rule_combo(self) -> ComboBox:
        self.sort_rule_combo = ComboBox()
        self.sort_rule_combo.addItems(["创建时间", "优先级"])
        idx = {"created_at": 0, "priority": 1}.get(settings.sort_rule, 0)
        self.sort_rule_combo.setCurrentIndex(idx)
        self.sort_rule_combo.currentIndexChanged.connect(self._on_sort_rule_changed)
        return self.sort_rule_combo

    def _create_home_page_combo(self) -> ComboBox:
        self.home_page_combo = ComboBox()
        self.home_page_combo.addItems(["全部任务", "今日任务", "重要任务", "已完成"])
        idx = {"all": 0, "today": 1, "important": 2, "done": 3}.get(settings.home_page, 0)
        self.home_page_combo.setCurrentIndex(idx)
        self.home_page_combo.currentIndexChanged.connect(self._on_home_page_changed)
        return self.home_page_combo

    def _create_auto_start_cb(self) -> CheckBox:
        self.auto_start_cb = CheckBox("开机自动启动")
        self.auto_start_cb.setChecked(settings.auto_start)
        self.auto_start_cb.checkStateChanged.connect(self._on_auto_start_changed)
        return self.auto_start_cb

    def _create_floating_top_cb(self) -> CheckBox:
        self.floating_top_cb = CheckBox("浮窗始终置顶")
        self.floating_top_cb.setChecked(settings.floating_top)
        self.floating_top_cb.checkStateChanged.connect(self._on_floating_top_changed)
        return self.floating_top_cb

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

        self.export_btn = PushButton(FluentIcon.SAVE, "导出数据")
        row.addWidget(self.export_btn)

        self.import_btn = PushButton(FluentIcon.FOLDER, "导入数据")
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

    def _on_home_page_changed(self, index: int):
        pages = ["all", "today", "important", "done"]
        page = pages[index] if index < len(pages) else "all"
        settings.home_page = page
        self.home_page_changed.emit(page)

    def _on_sort_rule_changed(self, index: int):
        rules = ["created_at", "priority"]
        rule = rules[index] if index < len(rules) else "created_at"
        settings.sort_rule = rule
        self.sort_rule_changed.emit(rule)

    def _on_done_at_bottom_changed(self, state):
        checked = (state == Qt.CheckState.Checked)
        settings.done_at_bottom = checked
        self.done_at_bottom_changed.emit(checked)

    def _on_floating_top_changed(self, state):
        checked = (state == Qt.CheckState.Checked)
        settings.floating_top = checked
        self.floating_top_changed.emit(checked)
