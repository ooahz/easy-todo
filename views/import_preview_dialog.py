"""导入预览对话框"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QButtonGroup

from qfluentwidgets import (
    MessageBoxBase, SubtitleLabel, BodyLabel, RadioButton, PushButton,
)


class ImportPreviewDialog(MessageBoxBase):

    def __init__(self, preview_data: dict, parent=None):
        super().__init__(parent)
        self._selected_mode = "merge"

        self.widget.setMinimumWidth(400)

        title = SubtitleLabel("导入预览")
        self.viewLayout.addWidget(title)

        if not preview_data.get("valid", False):
            error_label = BodyLabel(f"文件格式错误：{preview_data.get('error', '未知错误')}")
            error_label.setWordWrap(True)
            self.viewLayout.addWidget(error_label)
            self.yesButton.hide()
            self.cancelButton.setText("关闭")
            return

        version = preview_data.get("version", "1.0")
        version_label = BodyLabel(f"文件版本：{version}")
        self.viewLayout.addWidget(version_label)

        stats_layout = QVBoxLayout()
        stats_layout.setSpacing(6)

        cat_count = preview_data.get("categories_count", 0)
        if cat_count > 0:
            stats_layout.addWidget(BodyLabel(f"📋 分类：{cat_count} 个"))

        todo_count = preview_data.get("todos_count", 0)
        stats_layout.addWidget(BodyLabel(f"📝 顶级任务：{todo_count} 个"))

        child_count = preview_data.get("children_count", 0)
        if child_count > 0:
            stats_layout.addWidget(BodyLabel(f"  └ 子任务：{child_count} 个"))

        instance_count = preview_data.get("instances_count", 0)
        if instance_count > 0:
            stats_layout.addWidget(BodyLabel(f"🔄 重复实例：{instance_count} 个"))

        dup_count = preview_data.get("duplicate_count", 0)
        if dup_count > 0:
            dup_label = BodyLabel(f"⚠️ 重复任务：{dup_count} 个（合并模式下将跳过）")
            stats_layout.addWidget(dup_label)

        self.viewLayout.addLayout(stats_layout)

        mode_layout = QVBoxLayout()
        mode_layout.setSpacing(8)

        mode_title = BodyLabel("导入模式：")
        mode_title.setStyleSheet("font-weight: bold;")
        mode_layout.addWidget(mode_title)

        self._btn_group = QButtonGroup(self)

        self._merge_radio = RadioButton("合并导入 — 保留现有数据，追加新数据")
        self._merge_radio.setChecked(True)
        mode_layout.addWidget(self._merge_radio)
        self._btn_group.addButton(self._merge_radio)

        self._replace_radio = RadioButton("替换导入 — 清空现有数据后导入")
        mode_layout.addWidget(self._replace_radio)
        self._btn_group.addButton(self._replace_radio)

        self._btn_group.buttonClicked.connect(self._on_mode_changed)

        self.viewLayout.addLayout(mode_layout)

        self.yesButton.setText("开始导入")
        self.cancelButton.setText("取消")

    def _on_mode_changed(self, btn):
        if btn == self._merge_radio:
            self._selected_mode = "merge"
        elif btn == self._replace_radio:
            self._selected_mode = "replace"

    @property
    def selected_mode(self) -> str:
        return self._selected_mode
