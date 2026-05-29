"""重复任务删除对话框"""
from __future__ import annotations

from qfluentwidgets import MessageBoxBase, SubtitleLabel, BodyLabel, PushButton


class RecurrenceDeleteDialog(MessageBoxBase):
    """三选项删除对话框：仅此次 / 此次及之后 / 所有重复"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.result_mode: str | None = None

        self.yesButton.hide()
        self.cancelButton.setText("取消")

        self.widget.setMinimumWidth(360)

        title = SubtitleLabel("删除重复任务")
        self.viewLayout.addWidget(title)

        hint = BodyLabel("请选择删除范围：")
        self.viewLayout.addWidget(hint)

        btn_this = PushButton("仅删除此次")
        btn_this.clicked.connect(lambda: self._choose("this"))
        self.viewLayout.addWidget(btn_this)

        btn_future = PushButton("删除此次及之后")
        btn_future.clicked.connect(lambda: self._choose("this_and_future"))
        self.viewLayout.addWidget(btn_future)

        btn_all = PushButton("删除所有重复")
        btn_all.clicked.connect(lambda: self._choose("all"))
        self.viewLayout.addWidget(btn_all)

    def _choose(self, mode: str):
        self.result_mode = mode
        self.accept()
