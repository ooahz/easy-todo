"""任务详情对话框 - 模态弹窗展示任务详情"""
from __future__ import annotations
from datetime import date, datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame, QLabel,
    QSizePolicy, QScrollArea, QDialog, QTextBrowser
)

from qfluentwidgets import (
    BodyLabel, CaptionLabel, SubtitleLabel, TitleLabel,
    TransparentToolButton, FluentIcon, isDarkTheme, CheckBox,
    ToolButton, PrimaryPushButton, CardWidget, IconWidget,
    MessageBoxBase
)

from config.constants import PRIORITY_MAP, STATUS_MAP
from config.settings import settings
from services.file_service import FileService


def _tc():
    """根据主题返回颜色字典"""
    if isDarkTheme():
        return {
            "bg": "#1F1F1F",
            "card_bg": "#2D2D2D",
            "card_hover": "#333333",
            "border": "rgba(255, 255, 255, 0.08)",
            "title": "#EEE",
            "subtitle": "#CCC",
            "body": "#BBB",
            "muted": "#888",
            "icon": "rgba(255, 255, 255, 0.45)",
            "accent": "#60CDFF",
            "divider": "rgba(255, 255, 255, 0.06)",
            "tag_bg": "rgba(255, 255, 255, 0.06)",
            "priority_high": "#FF6B6B",
            "priority_medium": "#FFB347",
            "priority_low": "#60CDFF",
            "overdue": "#FF6B6B",
            "done_green": "#6BCB77",
        }
    return {
        "bg": "#FAFAFA",
        "card_bg": "#FFFFFF",
        "card_hover": "#F5F5F5",
        "border": "rgba(0, 0, 0, 0.06)",
        "title": "#1A1A1A",
        "subtitle": "#444",
        "body": "#555",
        "muted": "#999",
        "icon": "rgba(0, 0, 0, 0.35)",
        "accent": "#0078D4",
        "divider": "rgba(0, 0, 0, 0.06)",
        "tag_bg": "rgba(0, 0, 0, 0.04)",
        "priority_high": "#D13438",
        "priority_medium": "#FF8C00",
        "priority_low": "#0078D4",
        "overdue": "#D13438",
        "done_green": "#107C10",
    }


class InfoRow(QWidget):
    """信息行组件 - 图标 + 标签 + 值"""

    def __init__(self, icon: FluentIcon, label: str, value: str,
                 value_color: str = None, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 6, 0, 6)
        layout.setSpacing(10)

        c = _tc()

        icon_w = IconWidget(icon)
        icon_w.setFixedSize(14, 14)
        icon_w.setStyleSheet(f"color: {c['icon']};")
        layout.addWidget(icon_w)

        label_w = CaptionLabel(label)
        label_w.setFixedWidth(56)
        label_w.setStyleSheet(f"color: {c['muted']}; font-size: 12px;")
        layout.addWidget(label_w)

        value_w = BodyLabel(value)
        vc = value_color or c['body']
        value_w.setStyleSheet(f"color: {vc}; font-size: 13px;")
        value_w.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        value_w.setWordWrap(True)
        layout.addWidget(value_w, 1)


class SubtaskItem(CardWidget):
    """详情中的子任务项"""

    toggle_done = Signal(int)

    def __init__(self, data: dict, parent=None):
        super().__init__(parent)
        self.todo_id = data["id"]
        self._is_done = data.get("status", 0) == 1
        self._setup_ui(data)

    def _setup_ui(self, data: dict):
        c = _tc()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(8)

        self.checkbox = CheckBox()
        self.checkbox.setFixedSize(14, 14)
        self.checkbox.setChecked(self._is_done)
        self.checkbox.checkStateChanged.connect(lambda: self.toggle_done.emit(self.todo_id))
        layout.addWidget(self.checkbox)

        title = BodyLabel(data.get("title", ""))
        if self._is_done:
            title.setStyleSheet(f"color: {c['muted']}; text-decoration: line-through; font-size: 13px;")
        else:
            title.setStyleSheet(f"color: {c['body']}; font-size: 13px;")
        title.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        title.setWordWrap(True)
        layout.addWidget(title, 1)

        self.setStyleSheet(f"""
            CardWidget {{
                border: 1px solid {c['divider']};
                border-radius: 6px;
                background-color: {c['card_bg']};
            }}
            CardWidget:hover {{
                background-color: {c['card_hover']};
            }}
        """)


class FileItem(CardWidget):
    """详情中的文件项"""

    def __init__(self, file_info: dict, todo_id: int, parent=None):
        super().__init__(parent)
        self._todo_id = todo_id
        c = _tc()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(8)

        icon_w = IconWidget(FluentIcon.DOCUMENT)
        icon_w.setFixedSize(14, 14)
        icon_w.setStyleSheet(f"color: {c['icon']};")
        layout.addWidget(icon_w)

        name = BodyLabel(file_info.get("name", ""))
        name.setStyleSheet(f"color: {c['body']}; font-size: 12px;")
        name.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout.addWidget(name, 1)

        size_kb = file_info.get("size", 0) / 1024
        size_text = f"{size_kb:.0f}KB" if size_kb < 1024 else f"{size_kb/1024:.1f}MB"
        size_label = CaptionLabel(size_text)
        size_label.setStyleSheet(f"color: {c['muted']}; font-size: 11px;")
        layout.addWidget(size_label)

        self.setStyleSheet(f"""
            CardWidget {{
                border: 1px solid {c['divider']};
                border-radius: 6px;
                background-color: {c['card_bg']};
            }}
            CardWidget:hover {{
                background-color: {c['card_hover']};
            }}
        """)


class TodoDetailDialog(MessageBoxBase):
    """任务详情对话框 - 模态弹窗"""

    edit_clicked = Signal(int)
    delete_clicked = Signal(int)
    toggle_done = Signal(int)
    subtask_toggle_done = Signal(int)

    def __init__(self, todo_data: dict, parent=None):
        super().__init__(parent)
        self._todo_data = todo_data
        self._file_service = FileService()
        self._current_todo_id = todo_data["id"]

        self.widget.setMinimumWidth(480)
        self.widget.setMaximumWidth(560)

        self._setup_content()
        self._rebuild_content()

    def _setup_content(self):
        """构建对话框内容 - 使用 viewLayout 而非覆盖 vBoxLayout"""
        c = _tc()

        # 隐藏默认按钮，用自定义操作栏替代
        self.yesButton.hide()
        self.cancelButton.hide()
        self.buttonGroup.setFixedHeight(64)

        # 调整 buttonLayout 边距
        self.buttonLayout.setContentsMargins(20, 12, 20, 16)
        self.buttonLayout.setSpacing(8)

        # 清空 buttonLayout，添加自定义按钮
        while self.buttonLayout.count():
            item = self.buttonLayout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.done_btn = PrimaryPushButton(FluentIcon.COMPLETED, "标记完成")
        self.done_btn.setFixedHeight(32)
        self.done_btn.clicked.connect(self._on_toggle_done)
        self.buttonLayout.addWidget(self.done_btn, 1)

        self.edit_btn = ToolButton(FluentIcon.EDIT)
        self.edit_btn.setFixedSize(28, 28)
        self.edit_btn.setToolTip("编辑")
        self.edit_btn.clicked.connect(self._on_edit)
        self.buttonLayout.addWidget(self.edit_btn)

        self.delete_btn = ToolButton(FluentIcon.DELETE)
        self.delete_btn.setFixedSize(28, 28)
        self.delete_btn.setToolTip("删除")
        self.delete_btn.clicked.connect(self._on_delete)
        self.buttonLayout.addWidget(self.delete_btn)

        # ---- 顶部栏 ----
        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)

        self.panel_title = SubtitleLabel("任务详情")
        self.panel_title.setStyleSheet(f"color: {c['title']}; font-weight: bold;")
        top_bar.addWidget(self.panel_title, 1)

        self.close_btn = TransparentToolButton(FluentIcon.CLOSE)
        self.close_btn.setFixedSize(28, 28)
        self.close_btn.clicked.connect(self.reject)
        top_bar.addWidget(self.close_btn)

        self.viewLayout.addLayout(top_bar)

        # 分隔线
        divider1 = QFrame()
        divider1.setFixedHeight(1)
        divider1.setStyleSheet(f"background-color: {c['divider']};")
        self.viewLayout.addWidget(divider1)

        # ---- 滚动内容区 ----
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setMinimumHeight(300)
        self.scroll.setMaximumHeight(500)
        self.scroll.setStyleSheet(f"""
            QScrollArea {{
                border: none;
                background-color: transparent;
            }}
            QScrollBar:vertical {{
                border: none;
                background: transparent;
                width: 6px;
            }}
            QScrollBar::handle:vertical {{
                background: {c['divider']};
                border-radius: 3px;
                min-height: 30px;
            }}
        """)

        self.content_widget = QWidget()
        self.content_widget.setObjectName("detailContent")
        self.content_widget.setStyleSheet("background-color: transparent;")
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 8, 0, 0)
        self.content_layout.setSpacing(0)

        self.scroll.setWidget(self.content_widget)
        self.viewLayout.addWidget(self.scroll, 1)

        # 调整 viewLayout 边距
        self.viewLayout.setContentsMargins(20, 16, 20, 8)
        self.viewLayout.setSpacing(8)

    def _rebuild_content(self):
        """重建详情内容"""
        c = _tc()
        todo = self._todo_data
        if not todo:
            return

        # 清空旧内容
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                while item.layout().count():
                    sub = item.layout().takeAt(0)
                    if sub.widget():
                        sub.widget().deleteLater()

        is_done = todo.get("status", 0) == 1

        # ---- 标题区 ----
        title_layout = QVBoxLayout()
        title_layout.setSpacing(8)
        title_layout.setContentsMargins(0, 0, 0, 0)

        # 颜色标签 + 标题
        title_row = QHBoxLayout()
        title_row.setSpacing(10)

        color_tag = todo.get("color_tag")
        if color_tag:
            color_dot = QFrame()
            color_dot.setFixedSize(12, 12)
            color_dot.setStyleSheet(f"""
                background-color: {color_tag};
                border-radius: 6px;
            """)
            title_row.addWidget(color_dot)

        self.title_label = TitleLabel(todo.get("title", ""))
        self.title_label.setWordWrap(True)
        self.title_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        if is_done:
            self.title_label.setStyleSheet(f"""
                color: {c['muted']};
                text-decoration: line-through;
                font-size: 20px;
                font-weight: bold;
            """)
        else:
            self.title_label.setStyleSheet(f"""
                color: {c['title']};
                font-size: 20px;
                font-weight: bold;
            """)
        title_row.addWidget(self.title_label, 1)
        title_layout.addLayout(title_row)

        # 状态标签
        status = todo.get("status", 0)
        status_text = STATUS_MAP.get(status, "未知")
        status_tag = QLabel(f"  {status_text}  ")
        if is_done:
            status_tag.setStyleSheet(f"""
                background-color: rgba(16, 124, 16, 0.12);
                color: {c['done_green']};
                border-radius: 10px;
                font-size: 11px;
                padding: 2px 8px;
            """)
        else:
            status_tag.setStyleSheet(f"""
                background-color: {c['tag_bg']};
                color: {c['accent']};
                border-radius: 10px;
                font-size: 11px;
                padding: 2px 8px;
            """)
        title_layout.addWidget(status_tag)

        self.content_layout.addLayout(title_layout)
        self.content_layout.addSpacing(16)

        # ---- 描述区 ----
        desc = todo.get("description", "")
        if desc:
            desc_card = QFrame()
            desc_card.setObjectName("descCard")
            desc_card.setStyleSheet(f"""
                QFrame#descCard {{
                    background-color: {c['card_bg']};
                    border: 1px solid {c['divider']};
                    border-radius: 8px;
                }}
            """)
            desc_layout = QVBoxLayout(desc_card)
            desc_layout.setContentsMargins(12, 10, 12, 10)
            desc_layout.setSpacing(4)

            desc_header = CaptionLabel("描述")
            desc_header.setStyleSheet(f"color: {c['muted']}; font-size: 11px; font-weight: bold;")
            desc_layout.addWidget(desc_header)

            if settings.description_mode == "markdown":
                desc_body = QTextBrowser()
                desc_body.setOpenExternalLinks(True)
                desc_body.setMarkdown(desc)
                desc_body.setReadOnly(True)
                desc_body.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
                desc_body.setStyleSheet(f"""
                    QTextBrowser {{
                        background-color: transparent;
                        border: none;
                        color: {c['body']};
                        font-size: 13px;
                        line-height: 1.5;
                        padding: 0;
                    }}
                """)
            else:
                desc_body = BodyLabel(desc)
                desc_body.setWordWrap(True)
                desc_body.setStyleSheet(f"color: {c['body']}; font-size: 13px; line-height: 1.5;")
                desc_body.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            desc_layout.addWidget(desc_body)

            self.content_layout.addWidget(desc_card)
            self.content_layout.addSpacing(12)

        # ---- 信息区 ----
        info_card = QFrame()
        info_card.setObjectName("infoCard")
        info_card.setStyleSheet(f"""
            QFrame#infoCard {{
                background-color: {c['card_bg']};
                border: 1px solid {c['divider']};
                border-radius: 8px;
            }}
        """)
        info_layout = QVBoxLayout(info_card)
        info_layout.setContentsMargins(14, 8, 14, 8)
        info_layout.setSpacing(0)

        # 优先级
        priority = todo.get("priority", 0)
        if priority > 0:
            priority_text = PRIORITY_MAP.get(priority, "无")
            priority_color = c['muted']
            if priority == 3:
                priority_color = c['priority_high']
            elif priority == 2:
                priority_color = c['priority_medium']
            elif priority == 1:
                priority_color = c['priority_low']
            row = InfoRow(FluentIcon.HEART, "优先级", priority_text, priority_color)
            info_layout.addWidget(row)
            line = QFrame()
            line.setFixedHeight(1)
            line.setStyleSheet(f"background-color: {c['divider']};")
            info_layout.addWidget(line)

        # 分类
        category = todo.get("category")
        if category:
            row = InfoRow(FluentIcon.TAG, "分类", category.get("name", ""))
            info_layout.addWidget(row)
            line = QFrame()
            line.setFixedHeight(1)
            line.setStyleSheet(f"background-color: {c['divider']};")
            info_layout.addWidget(line)

        # 截止日期
        due = todo.get("due_date")
        if due:
            try:
                due_date = date.fromisoformat(due)
                today = date.today()
                if due_date < today and not is_done:
                    due_text = f"{due}（已过期）"
                    due_color = c['overdue']
                elif due_date == today:
                    due_text = f"{due}（今天）"
                    due_color = c['accent']
                else:
                    due_text = due
                    due_color = None
            except (ValueError, TypeError):
                due_text = due
                due_color = None
            row = InfoRow(FluentIcon.CALENDAR, "截止日期", due_text, due_color)
            info_layout.addWidget(row)
            line = QFrame()
            line.setFixedHeight(1)
            line.setStyleSheet(f"background-color: {c['divider']};")
            info_layout.addWidget(line)

        # 自动延期
        auto_postpone = todo.get("auto_postpone", False)
        if auto_postpone:
            row = InfoRow(FluentIcon.SYNC, "自动延期", "开启")
            info_layout.addWidget(row)
            line = QFrame()
            line.setFixedHeight(1)
            line.setStyleSheet(f"background-color: {c['divider']};")
            info_layout.addWidget(line)

        # 创建时间
        created = todo.get("created_at")
        if created:
            try:
                dt = datetime.fromisoformat(created)
                created_text = dt.strftime("%Y-%m-%d %H:%M")
            except (ValueError, TypeError):
                created_text = created
            row = InfoRow(FluentIcon.HISTORY, "创建时间", created_text)
            info_layout.addWidget(row)
            line = QFrame()
            line.setFixedHeight(1)
            line.setStyleSheet(f"background-color: {c['divider']};")
            info_layout.addWidget(line)

        # 更新时间
        updated = todo.get("updated_at")
        if updated:
            try:
                dt = datetime.fromisoformat(updated)
                updated_text = dt.strftime("%Y-%m-%d %H:%M")
            except (ValueError, TypeError):
                updated_text = updated
            row = InfoRow(FluentIcon.INFO, "更新时间", updated_text)
            info_layout.addWidget(row)

        self.content_layout.addWidget(info_card)
        self.content_layout.addSpacing(12)

        # ---- 子任务区 ----
        children = todo.get("children", [])
        if children:
            subtask_header = QHBoxLayout()
            subtask_header.setSpacing(6)

            subtask_title = CaptionLabel("子任务")
            subtask_title.setStyleSheet(f"color: {c['muted']}; font-size: 11px; font-weight: bold;")
            subtask_header.addWidget(subtask_title)

            done_count = sum(1 for ch in children if ch.get("status", 0) == 1)
            count_label = CaptionLabel(f"{done_count}/{len(children)}")
            count_label.setStyleSheet(f"color: {c['accent']}; font-size: 11px;")
            subtask_header.addWidget(count_label)
            subtask_header.addStretch()

            self.content_layout.addLayout(subtask_header)
            self.content_layout.addSpacing(6)

            for child in children:
                item = SubtaskItem(child)
                item.toggle_done.connect(self.subtask_toggle_done.emit)
                self.content_layout.addWidget(item)
                self.content_layout.addSpacing(4)

            self.content_layout.addSpacing(12)

        # ---- 附件区 ----
        file_count = self._file_service.get_file_count(self._current_todo_id)
        if file_count > 0:
            file_header = QHBoxLayout()
            file_header.setSpacing(6)

            file_title = CaptionLabel("附件")
            file_title.setStyleSheet(f"color: {c['muted']}; font-size: 11px; font-weight: bold;")
            file_header.addWidget(file_title)

            file_count_label = CaptionLabel(f"{file_count}")
            file_count_label.setStyleSheet(f"color: {c['accent']}; font-size: 11px;")
            file_header.addWidget(file_count_label)
            file_header.addStretch()

            self.content_layout.addLayout(file_header)
            self.content_layout.addSpacing(6)

            files = self._file_service.get_files(self._current_todo_id)
            for f_info in files[:5]:
                item = FileItem(f_info, self._current_todo_id)
                self.content_layout.addWidget(item)
                self.content_layout.addSpacing(4)

            if file_count > 5:
                more = CaptionLabel(f"还有 {file_count - 5} 个文件...")
                more.setStyleSheet(f"color: {c['muted']}; font-size: 11px;")
                self.content_layout.addWidget(more)

        # 底部弹性空间
        self.content_layout.addStretch()

        # 更新底部按钮状态
        if is_done:
            self.done_btn.setText("标记待办")
            self.done_btn.setIcon(FluentIcon.CANCEL)
        else:
            self.done_btn.setText("标记完成")
            self.done_btn.setIcon(FluentIcon.COMPLETED)

    def _on_toggle_done(self):
        self.toggle_done.emit(self._current_todo_id)
        self.reject()

    def _on_edit(self):
        self.edit_clicked.emit(self._current_todo_id)
        self.reject()

    def _on_delete(self):
        self.delete_clicked.emit(self._current_todo_id)
        self.reject()
