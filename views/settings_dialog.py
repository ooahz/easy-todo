"""设置页面 - 内嵌导航子页面"""
from __future__ import annotations
import os
import sys
from pathlib import Path

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame
from PySide6.QtGui import QFont

from qfluentwidgets import (
    BodyLabel, CaptionLabel, Slider, ComboBox, CheckBox,
    PrimaryPushButton, PushButton, FluentIcon, SmoothScrollArea,
    setTheme, Theme, isDarkTheme, setCustomStyleSheet, IconWidget,
)

from config.settings import settings
from config.constants import APP_NAME, APP_VERSION
from views.style_sheet import StyleSheet


class SettingsPage(QWidget):
    """设置页面"""

    opacity_changed = Signal(float)
    theme_changed = Signal(str)
    show_done_changed = Signal(bool)
    show_week_view_changed = Signal(bool)
    auto_start_changed = Signal(bool)
    sort_rule_changed = Signal(str)
    sort_rules_changed = Signal(list)
    done_at_bottom_changed = Signal(bool)
    floating_top_changed = Signal(bool)
    categories_changed = Signal()
    description_mode_changed = Signal(str)
    dialog_mode_changed = Signal(str)
    manual_refresh_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cards: list[QFrame] = []
        self._setup_ui()

    def _setup_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(20, 16, 20, 8)
        self.main_layout.setSpacing(12)

        # ---- 顶部工具栏 ----
        self.toolbar = QHBoxLayout()
        self.toolbar.setSpacing(8)
        self.toolbar.addStretch()
        self.main_layout.addLayout(self.toolbar)

        # ---- 统计行 ----
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
            self._create_show_week_view_cb(),
        ]))

        self.list_layout.addWidget(self._make_card("编辑器", [
            self._make_combo_row("输入模式", self._create_description_mode_combo()),
            self._make_combo_row("布局模式", self._create_dialog_mode_combo()),
        ]))

        self.list_layout.addWidget(self._make_card("排序规则", [
            self._create_sort_row(),
        ]))

        self.list_layout.addWidget(self._make_card("分类", [
            self._make_category_manage_row(),
        ]))

        self.list_layout.addWidget(self._make_card("浮窗设置", [
            self._make_slider_row(),
            self._create_floating_top_cb(),
            self._create_floating_show_subtasks_cb(),
        ]))

        self.list_layout.addWidget(self._make_card("数据", [
            self._make_data_btns(),
        ]))

        self.list_layout.addWidget(self._make_card("自动刷新", [
            self._create_manual_refresh_btn(),
        ]))

        self.list_layout.addWidget(self._make_card("启动", [
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
        font = QFont()
        font.setBold(True)
        font.setPointSize(11)
        title_label.setFont(font)
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
        card_layout.setSpacing(12)

        # 应用名
        name_label = BodyLabel(APP_NAME)
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_font = QFont()
        name_font.setBold(True)
        name_font.setPointSize(13)
        name_label.setFont(name_font)
        name_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        card_layout.addWidget(name_label)

        # 版本号
        ver_label = BodyLabel(f"v{APP_VERSION}")
        ver_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ver_label.setStyleSheet("color: #0078D4; font-size: 13px; font-weight: bold;")
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
        self.show_done_cb = CheckBox("显示已完成的任务")
        self.show_done_cb.setChecked(settings.show_done_tasks)
        self.show_done_cb.checkStateChanged.connect(self._on_show_done_changed)
        return self.show_done_cb

    def _create_description_mode_combo(self) -> ComboBox:
        self.desc_mode_combo = ComboBox()
        self.desc_mode_combo.addItems(["默认", "Markdown"])
        idx = 0 if settings.description_mode == "default" else 1
        self.desc_mode_combo.setCurrentIndex(idx)
        self.desc_mode_combo.currentIndexChanged.connect(self._on_description_mode_changed)
        return self.desc_mode_combo

    def _create_dialog_mode_combo(self) -> ComboBox:
        self.dialog_mode_combo = ComboBox()
        self.dialog_mode_combo.addItems(["单栏", "分栏"])
        idx = 0 if settings.dialog_mode == "default" else 1
        self.dialog_mode_combo.setCurrentIndex(idx)
        self.dialog_mode_combo.currentIndexChanged.connect(self._on_dialog_mode_changed)
        return self.dialog_mode_combo

    def _create_done_at_bottom_cb(self) -> CheckBox:
        self.done_at_bottom_cb = CheckBox("已完成任务置底")
        self.done_at_bottom_cb.setChecked(settings.done_at_bottom)
        self.done_at_bottom_cb.checkStateChanged.connect(self._on_done_at_bottom_changed)
        return self.done_at_bottom_cb

    def _create_show_week_view_cb(self) -> CheckBox:
        self.show_week_view_cb = CheckBox("显示周日程视图")
        self.show_week_view_cb.setChecked(settings.show_week_view)
        self.show_week_view_cb.checkStateChanged.connect(self._on_show_week_view_changed)
        return self.show_week_view_cb

    def _make_category_manage_row(self) -> QHBoxLayout:
        """创建分类管理行"""
        from services.category_service import CategoryService

        row = QHBoxLayout()
        row.setSpacing(12)

        self.category_count_label = BodyLabel("加载中...")
        row.addWidget(self.category_count_label)
        row.addStretch()

        manage_btn = PushButton("管理分类")
        manage_btn.clicked.connect(self._on_manage_categories)
        row.addWidget(manage_btn)

        self._update_category_count()
        return row

    def _update_category_count(self):
        """更新分类数量显示"""
        from services.category_service import CategoryService
        cs = CategoryService()
        try:
            count = cs.get_count()
            self.category_count_label.setText(f"当前有 {count} 个分类")
        finally:
            cs.close()

    def _on_manage_categories(self):
        """打开分类管理对话框"""
        from views.category_dialog import CategoryDialog
        dialog = CategoryDialog(self)
        dialog.categories_changed.connect(self._update_category_count)
        dialog.categories_changed.connect(self.categories_changed.emit)
        dialog.exec()

    SORT_OPTIONS = [
        ("自定义", "custom"),
        ("优先级", "priority"),
        ("创建时间", "created_at"),
        ("截止时间", "due_date"),
    ]

    def _create_sort_row(self):
        """创建排序规则行（并列布局）"""
        row = QHBoxLayout()
        row.setSpacing(12)

        self.sort_primary_combo = ComboBox()
        self.sort_primary_combo.addItems([label for label, _ in self.SORT_OPTIONS])
        self.sort_primary_combo.setFixedWidth(150)
        rules = settings.sort_rules
        primary = rules[0] if rules else "priority"
        for i, (_, val) in enumerate(self.SORT_OPTIONS):
            if val == primary:
                self.sort_primary_combo.setCurrentIndex(i)
                break
        self.sort_primary_combo.currentIndexChanged.connect(self._on_sort_rules_changed)
        row.addWidget(self.sort_primary_combo)

        self.sort_secondary_combo = ComboBox()
        self.sort_secondary_combo.addItems(["无"] + [label for label, _ in self.SORT_OPTIONS if _ != "custom"])
        self.sort_secondary_combo.setFixedWidth(150)
        secondary = rules[1] if len(rules) > 1 else ""
        if secondary:
            field_options = [(label, val) for label, val in self.SORT_OPTIONS if val != "custom"]
            for i, (_, val) in enumerate(field_options):
                if val == secondary:
                    self.sort_secondary_combo.setCurrentIndex(i + 1)
                    break
        else:
            self.sort_secondary_combo.setCurrentIndex(0)
        self.sort_secondary_combo.currentIndexChanged.connect(self._on_sort_rules_changed)
        row.addWidget(self.sort_secondary_combo)

        row.addStretch()

        # 初始状态：自定义时隐藏二级排序
        if primary == "custom":
            self.sort_secondary_combo.hide()

        return row

    def _on_sort_rules_changed(self):
        primary_idx = self.sort_primary_combo.currentIndex()
        primary_val = self.SORT_OPTIONS[primary_idx][1]

        # 自定义排序时隐藏二级排序
        if primary_val == "custom":
            self.sort_secondary_combo.hide()
            settings.sort_rules = ["custom"]
            settings.sort_rule = "custom"
            self.sort_rules_changed.emit(["custom"])
            self.sort_rule_changed.emit("custom")
            return

        self.sort_secondary_combo.show()

        secondary_idx = self.sort_secondary_combo.currentIndex()
        rules = [primary_val]
        field_options = [(label, val) for label, val in self.SORT_OPTIONS if val != "custom"]
        if secondary_idx > 0:
            secondary_val = field_options[secondary_idx - 1][1]
            if secondary_val != rules[0]:
                rules.append(secondary_val)
        settings.sort_rules = rules
        settings.sort_rule = rules[0]
        self.sort_rules_changed.emit(rules)
        self.sort_rule_changed.emit(rules[0])

    def _update_sort_ui(self, rules: list[str]):
        """外部更新排序 UI 状态"""
        primary = rules[0] if rules else "priority"
        for i, (_, val) in enumerate(self.SORT_OPTIONS):
            if val == primary:
                self.sort_primary_combo.setCurrentIndex(i)
                break
        self._on_sort_rules_changed()

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

    def _create_floating_show_subtasks_cb(self) -> CheckBox:
        self.floating_show_subtasks_cb = CheckBox("浮窗显示子任务")
        self.floating_show_subtasks_cb.setChecked(settings.floating_show_subtasks)
        self.floating_show_subtasks_cb.checkStateChanged.connect(self._on_floating_show_subtasks_changed)
        return self.floating_show_subtasks_cb

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

    def _make_data_btns(self) -> QVBoxLayout:
        layout = QVBoxLayout()
        layout.setSpacing(12)

        # 数据保存路径
        path_row = QHBoxLayout()
        path_row.setSpacing(10)

        path_label = BodyLabel("保存路径")
        path_label.setFixedWidth(60)
        path_row.addWidget(path_label)

        self.data_path_label = BodyLabel(settings.data_path or "默认路径")
        self.data_path_label.setWordWrap(True)
        path_row.addWidget(self.data_path_label, 1)

        self.browse_path_btn = PushButton(FluentIcon.FOLDER, "浏览")
        self.browse_path_btn.clicked.connect(self._on_browse_data_path)
        path_row.addWidget(self.browse_path_btn)

        self.reset_path_btn = PushButton("重置")
        self.reset_path_btn.clicked.connect(self._on_reset_data_path)
        path_row.addWidget(self.reset_path_btn)

        layout.addLayout(path_row)

        # 导入导出按钮
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self.export_btn = PushButton(FluentIcon.SAVE, "导出数据")
        btn_row.addWidget(self.export_btn)

        self.import_btn = PushButton(FluentIcon.FOLDER, "导入数据")
        btn_row.addWidget(self.import_btn)

        btn_row.addStretch()
        layout.addLayout(btn_row)

        return layout

    def _on_browse_data_path(self):
        """浏览选择数据保存路径"""
        from PySide6.QtWidgets import QFileDialog

        path = QFileDialog.getExistingDirectory(
            self, "选择数据保存路径", settings.data_path or str(Path.home())
        )
        if path:
            settings.data_path = path
            self.data_path_label.setText(path)

    def _on_reset_data_path(self):
        """重置为默认路径"""
        settings.data_path = ""
        self.data_path_label.setText("默认路径")

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

    def _on_show_week_view_changed(self, state):
        checked = (state == Qt.CheckState.Checked)
        settings.show_week_view = checked
        self.show_week_view_changed.emit(checked)

    def _on_auto_start_changed(self, state):
        checked = (state == Qt.CheckState.Checked)
        settings.auto_start = checked
        self.auto_start_changed.emit(checked)

    def _on_done_at_bottom_changed(self, state):
        checked = (state == Qt.CheckState.Checked)
        settings.done_at_bottom = checked
        self.done_at_bottom_changed.emit(checked)

    def _on_floating_top_changed(self, state):
        checked = (state == Qt.CheckState.Checked)
        settings.floating_top = checked
        self.floating_top_changed.emit(checked)

    def _on_floating_show_subtasks_changed(self, state):
        checked = (state == Qt.CheckState.Checked)
        settings.floating_show_subtasks = checked

    def _on_description_mode_changed(self, index: int):
        mode = "default" if index == 0 else "markdown"
        settings.description_mode = mode
        self.description_mode_changed.emit(mode)

    def _on_dialog_mode_changed(self, index: int):
        mode = "default" if index == 0 else "widescreen"
        settings.dialog_mode = mode
        self.dialog_mode_changed.emit(mode)

    def _create_manual_refresh_btn(self) -> QHBoxLayout:
        """创建手动刷新按钮行"""
        row = QHBoxLayout()
        row.setSpacing(12)

        desc_label = BodyLabel("立即执行一次刷新（自动延期 + 刷新列表）")
        row.addWidget(desc_label)
        row.addStretch()

        self.manual_refresh_btn = PushButton(FluentIcon.SYNC, "立即刷新")
        self.manual_refresh_btn.clicked.connect(self.manual_refresh_clicked.emit)
        row.addWidget(self.manual_refresh_btn)

        return row
