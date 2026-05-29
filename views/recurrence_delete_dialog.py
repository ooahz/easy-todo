"""重复任务删除对话框"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout

from qfluentwidgets import (
    SubtitleLabel, BodyLabel, PrimaryPushButton, PushButton
)


class RecurrenceDeleteDialog(QDialog):
    """三选项删除对话框：仅此次 / 此次及之后 / 所有重复"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setFixedSize(360, 200)
        self.result_mode: str | None = None
        self._drag_pos = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        title = SubtitleLabel("删除重复任务")
        layout.addWidget(title)

        hint = BodyLabel("请选择删除范围：")
        layout.addWidget(hint)

        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(8)

        btn_this = PushButton("仅删除此次")
        btn_this.clicked.connect(lambda: self._choose("this"))
        btn_layout.addWidget(btn_this)

        btn_future = PushButton("删除此次及之后")
        btn_future.clicked.connect(lambda: self._choose("this_and_future"))
        btn_layout.addWidget(btn_future)

        btn_all = PushButton("删除所有重复")
        btn_all.clicked.connect(lambda: self._choose("all"))
        btn_layout.addWidget(btn_all)

        layout.addLayout(btn_layout)

        cancel_row = QHBoxLayout()
        cancel_row.addStretch()
        cancel_btn = PushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        cancel_row.addWidget(cancel_btn)
        layout.addLayout(cancel_row)

    def _choose(self, mode: str):
        self.result_mode = mode
        self.accept()

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
