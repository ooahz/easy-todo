"""设置页面 - 使用 QFluentWidgets 设置卡组件重构"""
from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QFont, QKeySequence, QKeyEvent, QMovie
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QLineEdit
from qfluentwidgets import (
    BodyLabel, CaptionLabel, ComboBox, PushButton, FluentIcon, SmoothScrollArea,
    setCustomStyleSheet, SettingCardGroup, ComboBoxSettingCard, OptionsSettingCard,
    SwitchSettingCard, RangeSettingCard, PushSettingCard,
    HyperlinkCard, SettingCard,
    ConfigItem, OptionsConfigItem, RangeConfigItem,
    OptionsValidator, RangeValidator, BoolValidator,
    FlyoutViewBase, PopupTeachingTip, TeachingTipTailPosition,
)

from config.constants import APP_NAME, APP_VERSION
from config.settings import settings
from views.style_sheet import StyleSheet


class _DataPathCard(SettingCard):
    """数据保存路径设置卡"""

    browse_clicked = Signal()
    reset_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(
            FluentIcon.FOLDER,
            "数据保存路径",
            settings.data_path or "默认路径",
            parent,
        )

        self.browse_btn = PushButton("浏览")
        self.browse_btn.setFixedWidth(72)
        self.browse_btn.clicked.connect(self.browse_clicked.emit)

        self.reset_btn = PushButton("重置")
        self.reset_btn.setFixedWidth(72)
        self.reset_btn.clicked.connect(self.reset_clicked.emit)

        self.hBoxLayout.addWidget(self.reset_btn)
        self.hBoxLayout.addSpacing(8)
        self.hBoxLayout.addWidget(self.browse_btn)
        self.hBoxLayout.addSpacing(16)

    def update_path(self, path: str):
        self.contentLabel.setText(path or "默认路径")


class _ExportDataCard(SettingCard):
    """导出数据设置卡"""

    export_json_clicked = Signal()
    export_excel_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(
            FluentIcon.SAVE,
            "导出数据",
            "支持导出为 JSON 或 Excel 格式",
            parent,
        )

        self.export_json_btn = PushButton("导出JSON")
        self.export_json_btn.setFixedWidth(100)
        self.export_json_btn.clicked.connect(self.export_json_clicked.emit)

        self.export_excel_btn = PushButton("导出Excel")
        self.export_excel_btn.setFixedWidth(100)
        self.export_excel_btn.clicked.connect(self.export_excel_clicked.emit)

        self.hBoxLayout.addWidget(self.export_excel_btn)
        self.hBoxLayout.addSpacing(8)
        self.hBoxLayout.addWidget(self.export_json_btn)
        self.hBoxLayout.addSpacing(16)


class SortSettingCard(SettingCard):
    """排序规则设置卡"""

    sort_changed = Signal(list)

    SORT_OPTIONS = [
        ("自定义", "custom"),
        ("优先级", "priority"),
        ("创建时间", "created_at"),
        ("截止时间", "due_date"),
    ]

    def __init__(self, parent=None):
        super().__init__(FluentIcon.UP, "排序规则", "设置任务列表的排序方式", parent)

        self.primary_combo = ComboBox()
        self.primary_combo.addItems([label for label, _ in self.SORT_OPTIONS])
        self.primary_combo.setFixedWidth(140)

        rules = settings.sort_rules
        primary = rules[0] if rules else "priority"
        for i, (_, val) in enumerate(self.SORT_OPTIONS):
            if val == primary:
                self.primary_combo.setCurrentIndex(i)
                break

        self.secondary_combo = ComboBox()
        self.secondary_combo.addItems(
            ["无"] + [label for label, _ in self.SORT_OPTIONS if _ != "custom"]
        )
        self.secondary_combo.setFixedWidth(140)

        secondary = rules[1] if len(rules) > 1 else ""
        if secondary:
            field_options = [
                (label, val) for label, val in self.SORT_OPTIONS if val != "custom"
            ]
            for i, (_, val) in enumerate(field_options):
                if val == secondary:
                    self.secondary_combo.setCurrentIndex(i + 1)
                    break
        else:
            self.secondary_combo.setCurrentIndex(0)

        if primary == "custom":
            self.secondary_combo.hide()

        self.primary_combo.currentIndexChanged.connect(self._on_changed)
        self.secondary_combo.currentIndexChanged.connect(self._on_changed)

        self.hBoxLayout.addSpacing(8)
        self.hBoxLayout.addWidget(self.primary_combo)
        self.hBoxLayout.addSpacing(12)
        self.hBoxLayout.addWidget(self.secondary_combo)
        self.hBoxLayout.addSpacing(16)

    def _on_changed(self):
        primary_idx = self.primary_combo.currentIndex()
        primary_val = self.SORT_OPTIONS[primary_idx][1]

        if primary_val == "custom":
            self.secondary_combo.hide()
            self.sort_changed.emit(["custom"])
            return

        self.secondary_combo.show()

        secondary_idx = self.secondary_combo.currentIndex()
        rules = [primary_val]
        field_options = [
            (label, val) for label, val in self.SORT_OPTIONS if val != "custom"
        ]
        if secondary_idx > 0:
            secondary_val = field_options[secondary_idx - 1][1]
            if secondary_val != rules[0]:
                rules.append(secondary_val)

        self.sort_changed.emit(rules)

    def update_sort_ui(self, rules: list[str]):
        """外部更新排序 UI 状态"""
        primary = rules[0] if rules else "priority"
        for i, (_, val) in enumerate(self.SORT_OPTIONS):
            if val == primary:
                self.primary_combo.setCurrentIndex(i)
                break
        self._on_changed()


class GifFlyoutView(FlyoutViewBase):

    def __init__(self, gif_path: str, parent=None):
        super().__init__(parent)
        self._movie = QMovie(gif_path)
        self._gif_label = QLabel(self)
        self._gif_label.setMovie(self._movie)
        self._gif_label.setFixedSize(30, 30)
        self._gif_label.setScaledContents(True)
        self._movie.start()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addWidget(self._gif_label)


class ShortcutEdit(QLineEdit):
    """快捷键录制输入框"""

    shortcut_changed = Signal(str)

    def __init__(self, shortcut: str = "", parent=None):
        super().__init__(parent)
        self._shortcut = shortcut
        self.setReadOnly(True)
        self.setPlaceholderText("点击后按下快捷键...")
        self.setText(shortcut)
        self.setFixedWidth(180)
        self._update_style(False)

    def _update_style(self, recording: bool):
        from qfluentwidgets import isDarkTheme
        dark = isDarkTheme()
        if recording:
            text_color = "#FFF" if dark else "#000"
            self.setStyleSheet(
                f"border: 2px solid #0078D4; border-radius: 5px; padding: 4px 8px; color: {text_color};"
            )
        else:
            border_color = "rgba(255,255,255,0.15)" if dark else "rgba(0,0,0,0.15)"
            text_color = "#FFF" if dark else "#000"
            bg_color = "rgba(255,255,255,0.05)" if dark else "#FFF"
            self.setStyleSheet(
                f"border: 1px solid {border_color}; border-radius: 5px; "
                f"padding: 4px 8px; color: {text_color}; background: {bg_color};"
            )

    def showEvent(self, event):
        super().showEvent(event)
        self._update_style(False)

    def focusInEvent(self, event):
        self._update_style(True)
        self.setText("请按下快捷键...")
        super().focusInEvent(event)

    def focusOutEvent(self, event):
        self._update_style(False)
        self.setText(self._shortcut)
        super().focusOutEvent(event)

    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        if key in (Qt.Key.Key_Control, Qt.Key.Key_Shift, Qt.Key.Key_Alt, Qt.Key.Key_Meta):
            return
        modifiers = event.modifiers()
        if modifiers == Qt.KeyboardModifier.NoModifier:
            if key == Qt.Key.Key_Escape:
                self._shortcut = ""
                self.setText("")
                self.shortcut_changed.emit("")
                self.clearFocus()
                return
            if key == Qt.Key.Key_Backspace:
                self._shortcut = ""
                self.setText("")
                self.shortcut_changed.emit("")
                self.clearFocus()
                return
            return
        key_seq = QKeySequence(event.keyCombination())
        key_str = key_seq.toString()
        self._shortcut = key_str
        self.setText(key_str)
        self.shortcut_changed.emit(key_str)
        self.clearFocus()

    def get_shortcut(self) -> str:
        return self._shortcut

    def set_shortcut(self, shortcut: str):
        self._shortcut = shortcut
        self.setText(shortcut)


class ShortcutSettingCard(SettingCard):
    """新建任务快捷键设置卡"""

    shortcut_changed = Signal(str)
    reset_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(
            FluentIcon.ADD,
            "快速新建任务",
            "设置全局快捷键以快速打开新建任务对话框",
            parent,
        )

        self.shortcut_edit = ShortcutEdit(settings.shortcut_new_task)
        self.shortcut_edit.shortcut_changed.connect(self._on_shortcut_changed)
        self.shortcut_edit.setFixedWidth(160)

        self.reset_btn = PushButton("重置")
        self.reset_btn.setFixedWidth(60)
        self.reset_btn.clicked.connect(self._on_reset_clicked)

        self.hBoxLayout.addWidget(self.reset_btn)
        self.hBoxLayout.addSpacing(8)
        self.hBoxLayout.addWidget(self.shortcut_edit)
        self.hBoxLayout.addSpacing(16)

    def _on_shortcut_changed(self, key_str: str):
        if key_str != settings.shortcut_new_task:
            settings.shortcut_new_task = key_str
            self.shortcut_changed.emit(key_str)

    def _on_reset_clicked(self):
        self.shortcut_edit.set_shortcut("")
        if "" != settings.shortcut_new_task:
            settings.shortcut_new_task = ""
            self.shortcut_changed.emit("")
        self.reset_clicked.emit()


class SettingsPage(QWidget):
    """设置页面"""

    opacity_changed = Signal(float)
    theme_changed = Signal(str)
    show_done_changed = Signal(bool)
    show_week_view_changed = Signal(bool)
    auto_start_changed = Signal(bool)
    holiday_source_changed = Signal(str)
    sort_rule_changed = Signal(str)
    sort_rules_changed = Signal(list)
    floating_top_changed = Signal(bool)
    dialog_mode_changed = Signal(str)
    shortcut_new_task_changed = Signal(str)
    manual_refresh_clicked = Signal()
    export_json_clicked = Signal()
    export_excel_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(28, 16, 28, 8)
        self.main_layout.setSpacing(0)

        # ---- 滚动区域 ----
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
        self.list_layout = QVBoxLayout(self.scroll_widget)
        self.list_layout.setContentsMargins(0, 0, 8, 0)
        self.list_layout.setSpacing(16)

        # ---- 个性化组 ----
        self.list_layout.addWidget(self._create_appearance_group())

        # ---- 任务列表组 ----
        self.list_layout.addWidget(self._create_task_group())

        # ---- 编辑器组 ----
        self.list_layout.addWidget(self._create_editor_group())

        # ---- 排序规则组 ----
        self.list_layout.addWidget(self._create_sort_group())

        # ---- 分类组 ----
        self.list_layout.addWidget(self._create_category_group())

        # ---- 浮窗组 ----
        self.list_layout.addWidget(self._create_floating_group())

        # ---- 数据组 ----
        self.list_layout.addWidget(self._create_data_group())

        # ---- 启动组 ----
        self.list_layout.addWidget(self._create_startup_group())

        # ---- 关于组 ----
        self.list_layout.addWidget(self._create_about_group())

        # ---- 关于卡片 ----
        self.list_layout.addWidget(self._make_about_card())


        self.list_layout.addStretch()

        self.scroll_area.setWidget(self.scroll_widget)
        self.main_layout.addWidget(self.scroll_area, 1)

        # 转发快捷键卡片信号
        self.shortcut_new_task_card.shortcut_changed.connect(
            self.shortcut_new_task_changed.emit
        )

    # ================================================================
    #  设置组创建
    # ================================================================

    def _create_appearance_group(self) -> SettingCardGroup:
        group = SettingCardGroup("个性化", self.scroll_widget)

        self.theme_cfg = OptionsConfigItem(
            "Appearance", "Theme", settings.theme,
            OptionsValidator(["light", "dark", "system"]),
        )
        self.theme_card = OptionsSettingCard(
            self.theme_cfg,
            FluentIcon.BRUSH,
            "应用主题",
            "调整应用的外观",
            texts=["浅色", "深色", "跟随系统设置"],
        )
        self.theme_card.optionChanged.connect(self._on_theme_changed)
        group.addSettingCard(self.theme_card)

        return group

    def _create_task_group(self) -> SettingCardGroup:
        group = SettingCardGroup("任务列表", self.scroll_widget)

        self.show_done_cfg = ConfigItem(
            "TaskList", "ShowDoneTasks", settings.show_done_tasks, BoolValidator()
        )
        self.show_done_card = SwitchSettingCard(
            FluentIcon.COMPLETED,
            "显示已完成的任务",
            "在任务列表中显示已完成的任务",
            configItem=self.show_done_cfg,
        )
        self.show_done_card.checkedChanged.connect(self._on_show_done_changed)
        group.addSettingCard(self.show_done_card)

        self.show_week_view_cfg = ConfigItem(
            "TaskList", "ShowWeekView", settings.show_week_view, BoolValidator()
        )
        self.show_week_view_card = SwitchSettingCard(
            FluentIcon.CALENDAR,
            "显示周日程视图",
            "在任务列表显示周视图",
            configItem=self.show_week_view_cfg,
        )
        self.show_week_view_card.checkedChanged.connect(self._on_show_week_view_changed)
        group.addSettingCard(self.show_week_view_card)

        self.refresh_card = PushSettingCard(
            "刷新列表",
            FluentIcon.SYNC,
            "手动刷新列表",
            "列表跨天自动刷新，存在5分钟延迟，可点击按钮立即刷新",
        )
        self.refresh_card.clicked.connect(self.manual_refresh_clicked.emit)
        group.addSettingCard(self.refresh_card)

        self.manual_refresh_btn = self.refresh_card.button

        self.holiday_source_cfg = OptionsConfigItem(
            "TaskList", "HolidaySource", settings.holiday_source,
            OptionsValidator(["none", "default"]),
        )
        self.holiday_source_card = ComboBoxSettingCard(
            self.holiday_source_cfg,
            FluentIcon.CALENDAR,
            "节日数据来源",
            "在日程视图中显示中国法定节假日信息",
            texts=["无", "默认"],
        )
        self.holiday_source_card.comboBox.currentIndexChanged.connect(
            self._on_holiday_source_changed
        )
        group.addSettingCard(self.holiday_source_card)

        return group

    def _create_editor_group(self) -> SettingCardGroup:
        group = SettingCardGroup("编辑器", self.scroll_widget)

        self.dialog_mode_cfg = OptionsConfigItem(
            "Editor", "DialogMode", settings.dialog_mode,
            OptionsValidator(["default", "widescreen"]),
        )
        self.dialog_mode_card = ComboBoxSettingCard(
            self.dialog_mode_cfg,
            FluentIcon.ZOOM,
            "布局模式",
            "选择任务编辑对话框的布局方式",
            texts=["单栏", "分栏"],
        )
        self.dialog_mode_card.comboBox.currentIndexChanged.connect(
            self._on_dialog_mode_changed
        )
        group.addSettingCard(self.dialog_mode_card)

        self.shortcut_new_task_card = ShortcutSettingCard(parent=group)
        group.addSettingCard(self.shortcut_new_task_card)

        return group

    def _create_sort_group(self) -> SettingCardGroup:
        group = SettingCardGroup("排序规则", self.scroll_widget)

        self.sort_card = SortSettingCard()
        self.sort_card.sort_changed.connect(self._on_sort_rules_changed)
        group.addSettingCard(self.sort_card)

        return group

    def _create_category_group(self) -> SettingCardGroup:
        group = SettingCardGroup("分类", self.scroll_widget)

        self.category_card = PushSettingCard(
            "管理分类",
            FluentIcon.BOOK_SHELF,
            "分类管理",
            "当前有 0 个分类",
        )
        self.category_card.clicked.connect(self._on_manage_categories)
        group.addSettingCard(self.category_card)

        self._update_category_count()
        return group

    def _create_floating_group(self) -> SettingCardGroup:
        group = SettingCardGroup("浮窗", self.scroll_widget)

        self.opacity_cfg = RangeConfigItem(
            "Floating", "Opacity", int(settings.floating_opacity * 100),
            RangeValidator(10, 100),
        )
        self.opacity_card = RangeSettingCard(
            self.opacity_cfg,
            FluentIcon.TRANSPARENT,
            "透明度",
            "调整浮窗的透明度",
        )
        self.opacity_card.valueChanged.connect(self._on_opacity_changed)
        group.addSettingCard(self.opacity_card)

        self.floating_top_cfg = ConfigItem(
            "Floating", "Top", settings.floating_top, BoolValidator()
        )
        self.floating_top_card = SwitchSettingCard(
            FluentIcon.PIN,
            "浮窗始终置顶",
            "使浮窗始终保持在其他窗口之上",
            configItem=self.floating_top_cfg,
        )
        self.floating_top_card.checkedChanged.connect(self._on_floating_top_changed)
        group.addSettingCard(self.floating_top_card)

        self.floating_subtasks_cfg = ConfigItem(
            "Floating", "ShowSubtasks", settings.floating_show_subtasks, BoolValidator()
        )
        self.floating_subtasks_card = SwitchSettingCard(
            FluentIcon.DOCUMENT,
            "浮窗显示子任务",
            "在浮窗中显示任务的子任务列表",
            configItem=self.floating_subtasks_cfg,
        )
        self.floating_subtasks_card.checkedChanged.connect(
            self._on_floating_show_subtasks_changed
        )
        group.addSettingCard(self.floating_subtasks_card)

        self.floating_due_date_cfg = ConfigItem(
            "Floating", "ShowDueDate", settings.floating_show_due_date, BoolValidator()
        )
        self.floating_due_date_card = SwitchSettingCard(
            FluentIcon.CALENDAR,
            "浮窗显示截止时间",
            "在浮窗任务行中显示截止时间",
            configItem=self.floating_due_date_cfg,
        )
        self.floating_due_date_card.checkedChanged.connect(
            self._on_floating_show_due_date_changed
        )
        group.addSettingCard(self.floating_due_date_card)

        return group

    def _create_data_group(self) -> SettingCardGroup:
        group = SettingCardGroup("数据", self.scroll_widget)

        self.data_path_card = _DataPathCard()
        self.data_path_card.browse_clicked.connect(self._on_browse_data_path)
        self.data_path_card.reset_clicked.connect(self._on_reset_data_path)
        group.addSettingCard(self.data_path_card)

        self.export_data_card = _ExportDataCard()
        self.export_data_card.export_json_clicked.connect(self.export_json_clicked.emit)
        self.export_data_card.export_excel_clicked.connect(self.export_excel_clicked.emit)
        group.addSettingCard(self.export_data_card)

        self.import_btn = PushSettingCard(
            "导入",
            FluentIcon.DOWNLOAD,
            "导入数据",
            "从 JSON 文件导入任务数据",
        )
        group.addSettingCard(self.import_btn)

        return group

    def _create_startup_group(self) -> SettingCardGroup:
        group = SettingCardGroup("启动", self.scroll_widget)

        self.auto_start_cfg = ConfigItem(
            "Startup", "AutoStart", settings.auto_start, BoolValidator()
        )
        self.auto_start_card = SwitchSettingCard(
            FluentIcon.POWER_BUTTON,
            "开机自动启动",
            "系统启动时自动运行应用",
            configItem=self.auto_start_cfg,
        )
        self.auto_start_card.switchButton.setOnText("开")
        self.auto_start_card.switchButton.setOffText("关")
        self.auto_start_card.checkedChanged.connect(self._on_auto_start_changed)
        group.addSettingCard(self.auto_start_card)

        return group

    def _create_about_group(self):
        group = SettingCardGroup("关于", self.scroll_widget)

        self.repo_card = HyperlinkCard(
            "https://github.com/ooahz",
            "查看仓库",
            FluentIcon.INFO,
            "项目仓库",
            "https://github.com/ooahz",
        )
        group.addSettingCard(self.repo_card)

        self.homepage_card = HyperlinkCard(
            "https://ahzoo.cn",
            "查看主页",
            FluentIcon.HOME,
            "个人主页",
            "https://ahzoo.cn",
        )
        self.homepage_card.mousePressEvent = lambda e: self._show_gif_tip(self.homepage_card)
        group.addSettingCard(self.homepage_card)

        return group

    # ================================================================
    #  信号处理
    # ================================================================

    def _show_gif_tip(self, target):
        gif_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "kotone.gif")
        if not os.path.exists(gif_path):
            return
        view = GifFlyoutView(gif_path)
        PopupTeachingTip.make(
            view, target, -1,
            TeachingTipTailPosition.BOTTOM,
            self,
        )

    def _on_theme_changed(self, item: OptionsConfigItem):
        theme = item.value
        settings.theme = theme
        self.theme_changed.emit(theme)

    def _on_show_done_changed(self, checked: bool):
        settings.show_done_tasks = checked
        self.show_done_changed.emit(checked)

    def _on_show_week_view_changed(self, checked: bool):
        settings.show_week_view = checked
        self.show_week_view_changed.emit(checked)

    def _on_holiday_source_changed(self, index: int):
        source = "none" if index == 0 else "default"
        settings.holiday_source = source
        self.holiday_source_changed.emit(source)

    def _on_dialog_mode_changed(self, index: int):
        mode = "default" if index == 0 else "widescreen"
        settings.dialog_mode = mode
        self.dialog_mode_changed.emit(mode)

    def _on_sort_rules_changed(self, rules: list):
        settings.sort_rules = rules
        settings.sort_rule = rules[0]
        self.sort_rules_changed.emit(rules)
        self.sort_rule_changed.emit(rules[0])

    def _on_opacity_changed(self, value: int):
        percent = value / 100.0
        settings.floating_opacity = percent
        self.opacity_changed.emit(percent)

    def _on_floating_top_changed(self, checked: bool):
        settings.floating_top = checked
        self.floating_top_changed.emit(checked)

    def _on_floating_show_subtasks_changed(self, checked: bool):
        settings.floating_show_subtasks = checked

    def _on_floating_show_due_date_changed(self, checked: bool):
        settings.floating_show_due_date = checked

    def _on_auto_start_changed(self, checked: bool):
        settings.auto_start = checked
        self.auto_start_changed.emit(checked)

    def _on_browse_data_path(self):
        """浏览选择数据保存路径"""
        from PySide6.QtWidgets import QFileDialog

        path = QFileDialog.getExistingDirectory(
            self, "选择数据保存路径", settings.data_path or str(Path.home())
        )
        if path:
            settings.data_path = path
            self.data_path_card.update_path(path)

    def _on_reset_data_path(self):
        """重置为默认路径"""
        settings.data_path = ""
        self.data_path_card.update_path("")

    def _on_manage_categories(self):
        """打开分类管理对话框"""
        from views.category_dialog import CategoryDialog

        # WA_DeleteOnClose 让 Qt 在窗口关闭后自动释放底层 C++ 对象，
        # 避免每次打开都残留一个挂在 SettingsPage 子树上的 CategoryDialog 实例
        # （同时挂着事件总线的 4 条 connect，闭包不释放就泄漏）。
        dialog = CategoryDialog(self)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        dialog.exec()
        # CategoryDialog 内部已订阅事件总线，自身数据已自动同步。
        # 主窗口侧由 MainWindow 订阅同一总线完成导航增量更新，
        # 关闭的瞬间不会再触发任何"延迟全量重建"。
        self._update_category_count()

    def _update_category_count(self):
        """更新分类数量显示"""
        from services.category_service import CategoryService

        cs = CategoryService()
        try:
            count = cs.get_count()
            self.category_card.contentLabel.setText(f"当前有 {count} 个分类")
        finally:
            cs.close()

    def _make_about_card(self) -> QFrame:
        """创建关于卡片"""
        card = QFrame()
        card.setObjectName("settingsCard")

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
        author_val.setCursor(Qt.CursorShape.PointingHandCursor)
        author_val.mousePressEvent = lambda e: self._show_gif_tip(author_val)
        author_row.addWidget(author_val)
        author_row.addStretch()
        info_container.addLayout(author_row)
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
    def _create_shortcut_new_task_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(12)

        label = BodyLabel("快速新建任务")
        label.setFixedWidth(90)
        row.addWidget(label)

        self.shortcut_new_task_edit = ShortcutEdit(settings.shortcut_new_task)
        self.shortcut_new_task_edit.shortcut_changed.connect(self._on_shortcut_new_task_changed)
        row.addWidget(self.shortcut_new_task_edit)

        reset_btn = PushButton("重置")
        reset_btn.setFixedWidth(60)
        reset_btn.clicked.connect(self._on_reset_shortcut_new_task)
        row.addWidget(reset_btn)

        row.addStretch()
        return row

    def _update_sort_ui(self, rules: list[str]):
        """外部更新排序 UI 状态"""
        self.sort_card.update_sort_ui(rules)
