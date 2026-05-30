"""删除任务确认对话框"""
from __future__ import annotations

from qfluentwidgets import MessageBoxBase, SubtitleLabel, BodyLabel, CheckBox


class DeleteTodoDialog(MessageBoxBase):
    """删除任务确认对话框，可选是否同时删除关联文件"""

    def __init__(self, todo_id: int, file_count: int = 0, parent=None):
        super().__init__(parent)
        self._delete_files = False

        self.widget.setMinimumWidth(360)

        title = SubtitleLabel("确认删除")
        self.viewLayout.addWidget(title)

        content = BodyLabel("确定要删除这个任务吗？此操作不可撤销。")
        content.setWordWrap(True)
        self.viewLayout.addWidget(content)

        if file_count > 0:
            self._file_checkbox = CheckBox(f"同时删除关联的 {file_count} 个文件")
            self._file_checkbox.setChecked(True)
            self.viewLayout.addWidget(self._file_checkbox)
        else:
            self._file_checkbox = None

        self.yesButton.setText("删除")
        self.cancelButton.setText("取消")

    @property
    def delete_files(self) -> bool:
        if self._file_checkbox is None:
            return False
        return self._file_checkbox.isChecked()
