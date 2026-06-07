"""任务详情对话框 - 支持单栏/分栏双模式"""
from __future__ import annotations
from datetime import date, datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame, QLabel,
    QSizePolicy, QScrollArea, QTextBrowser
)

from qfluentwidgets import (
    BodyLabel, CaptionLabel, SubtitleLabel, TitleLabel,
    TransparentToolButton, FluentIcon, isDarkTheme, CheckBox,
    ToolButton, PrimaryPushButton, PushButton, CardWidget, IconWidget,
    MessageBoxBase
)

from config.constants import PRIORITY_MAP, STATUS_MAP
from config.settings import settings
from services.file_service import FileService


def _tc():
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
            "priority_urgent_important": "#FF6B6B",
            "priority_important": "#FFB347",
            "priority_urgent": "#60CDFF",
            "priority_minor": "#8764B8",
            "overdue": "#FF6B6B",
            "done_green": "#6BCB77",
            "code_bg": "#3A3A3A",
            "code_border": "#555",
            "link_color": "#60CDFF",
            "blockquote_color": "#AAA",
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
        "priority_urgent_important": "#D13438",
        "priority_important": "#0078D4",
        "priority_urgent": "#CA5010",
        "priority_minor": "#8764B8",
        "overdue": "#D13438",
        "done_green": "#107C10",
        "code_bg": "#F5F5F5",
        "code_border": "#DDD",
        "link_color": "#0078D4",
        "blockquote_color": "#666",
    }


def _markdown_css(c: dict) -> str:
    return f"""
        body {{
            font-family: "Segoe UI", "Microsoft YaHei", "PingFang SC", sans-serif;
            font-size: 14px;
            line-height: 1.7;
            color: {c['body']};
            background-color: transparent;
            padding: 0;
            margin: 0;
        }}
        h1, h2, h3, h4, h5, h6 {{
            margin: 12px 0 6px;
            font-weight: bold;
            color: {c['title']};
        }}
        h1 {{ font-size: 22px; }}
        h2 {{ font-size: 18px; }}
        h3 {{ font-size: 16px; }}
        h4 {{ font-size: 14px; }}
        p {{ margin: 6px 0; }}
        code {{
            background-color: {c['code_bg']};
            border: 1px solid {c['code_border']};
            border-radius: 3px;
            padding: 1px 5px;
            font-family: "Cascadia Code", "Consolas", monospace;
            font-size: 13px;
        }}
        pre {{
            background-color: {c['code_bg']};
            border: 1px solid {c['code_border']};
            border-radius: 6px;
            padding: 10px 12px;
            overflow-x: auto;
        }}
        pre code {{
            border: none;
            padding: 0;
            background: transparent;
        }}
        blockquote {{
            border-left: 3px solid {c['link_color']};
            margin: 8px 0;
            padding: 4px 12px;
            color: {c['blockquote_color']};
            background-color: {c['tag_bg']};
            border-radius: 0 4px 4px 0;
        }}
        a {{
            color: {c['link_color']};
            text-decoration: none;
        }}
        ul, ol {{
            margin: 6px 0;
            padding-left: 22px;
        }}
        li {{ margin: 3px 0; }}
        hr {{
            border: none;
            border-top: 1px solid {c['code_border']};
            margin: 12px 0;
        }}
        table {{
            border-collapse: collapse;
            margin: 8px 0;
        }}
        th, td {{
            border: 1px solid {c['code_border']};
            padding: 6px 10px;
        }}
        th {{
            background-color: {c['code_bg']};
        }}
        img {{
            max-width: 100%;
            border-radius: 4px;
        }}
    """


class InfoRow(QWidget):
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
        value_w.setStyleSheet(f"color: {vc}; font-size: 12px;")
        value_w.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        value_w.setWordWrap(True)
        layout.addWidget(value_w, 1)


class SubtaskItem(CardWidget):
    toggle_done = Signal(int)

    def __init__(self, data: dict, parent=None):
        super().__init__(parent)
        self.todo_id = data["id"]
        self._is_done = data.get("_is_done", False)
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
    def __init__(self, file_info: dict, todo_id: int, parent=None):
        super().__init__(parent)
        self._todo_id = todo_id
        self._file_path = file_info.get("path", "")
        c = _tc()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(8)

        icon_w = IconWidget(FluentIcon.DOCUMENT)
        icon_w.setFixedSize(14, 14)
        icon_w.setStyleSheet(f"color: {c['icon']};")
        layout.addWidget(icon_w)

        file_name = file_info.get("name", "")
        display_name = file_name
        if len(file_name) > 28:
            display_name = file_name[:12] + "..." + file_name[-13:]
        name = BodyLabel(display_name)
        name.setStyleSheet(f"color: {c['accent']}; font-size: 12px;")
        name.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        if display_name != file_name:
            name.setToolTip(file_name)
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

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._open_file()
        super().mouseReleaseEvent(event)

    def _open_file(self):
        import os
        import platform
        if not self._file_path or not os.path.exists(self._file_path):
            return
        system = platform.system()
        try:
            if system == "Windows":
                os.startfile(self._file_path)
            elif system == "Darwin":
                os.system(f'open "{self._file_path}"')
            else:
                os.system(f'xdg-open "{self._file_path}"')
        except Exception:
            pass


class TodoDetailDialog(MessageBoxBase):
    edit_clicked = Signal(int)
    delete_clicked = Signal(int)
    toggle_done = Signal(int)
    subtask_toggle_done = Signal(int)
    archive_clicked = Signal(int)

    def __init__(self, todo_data: dict, parent=None):
        super().__init__(parent)
        self._todo_data = todo_data
        self._file_service = FileService()
        self._current_todo_id = todo_data["id"]
        self._pending_action = None
        self._is_widescreen = (settings.dialog_mode == "widescreen")

        if self._is_widescreen:
            self.widget.setMinimumWidth(720)
            self.widget.setMaximumWidth(880)
            self.widget.setMinimumHeight(350)
        else:
            self.widget.setMinimumWidth(480)
            self.widget.setMaximumWidth(560)

        self._setup_content()
        self._rebuild_content()

    def closeEvent(self, event):
        if hasattr(self, '_file_service') and self._file_service:
            self._file_service.close()
        super().closeEvent(event)

    def _setup_content(self):
        c = _tc()

        self.yesButton.hide()
        self.cancelButton.hide()

        if self._is_widescreen:
            self.buttonGroup.setFixedHeight(52)
            self.buttonLayout.setContentsMargins(24, 6, 24, 10)
            self.buttonLayout.setSpacing(6)
        else:
            self.buttonGroup.setFixedHeight(64)
            self.buttonLayout.setContentsMargins(20, 12, 20, 16)
            self.buttonLayout.setSpacing(8)

        while self.buttonLayout.count():
            item = self.buttonLayout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if self._is_widescreen:
            self.archive_btn = ToolButton(FluentIcon.FOLDER)
            self.archive_btn.setFixedSize(30, 30)
            self.archive_btn.setToolTip("归档")
            self.archive_btn.clicked.connect(self._on_archive)
            self.buttonLayout.addWidget(self.archive_btn)

            self.edit_btn = ToolButton(FluentIcon.EDIT)
            self.edit_btn.setFixedSize(30, 30)
            self.edit_btn.setToolTip("编辑")
            self.edit_btn.clicked.connect(self._on_edit)
            self.buttonLayout.addWidget(self.edit_btn)

            self.delete_btn = ToolButton(FluentIcon.DELETE)
            self.delete_btn.setFixedSize(30, 30)
            self.delete_btn.setToolTip("删除")
            self.delete_btn.clicked.connect(self._on_delete)
            self.buttonLayout.addWidget(self.delete_btn)

            self.buttonLayout.addStretch(1)

            self.done_btn = PrimaryPushButton(FluentIcon.COMPLETED, "标记完成")
            self.done_btn.setFixedHeight(30)
            self.done_btn.clicked.connect(self._on_toggle_done)
            self.buttonLayout.addWidget(self.done_btn)
        else:
            self.done_btn = PrimaryPushButton(FluentIcon.COMPLETED, "标记完成")
            self.done_btn.setFixedHeight(32)
            self.done_btn.clicked.connect(self._on_toggle_done)
            self.buttonLayout.addWidget(self.done_btn, 1)

            self.archive_btn = ToolButton(FluentIcon.FOLDER)
            self.archive_btn.setFixedSize(28, 28)
            self.archive_btn.setToolTip("归档")
            self.archive_btn.clicked.connect(self._on_archive)
            self.buttonLayout.addWidget(self.archive_btn)

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

        # ---- 顶部标题栏 ----
        top_bar = QHBoxLayout()
        top_bar.setSpacing(10)

        is_done = self._todo_data.get("_is_done", False)

        if self._is_widescreen:
            color_tag = self._todo_data.get("color_tag")
            if color_tag:
                color_dot = QFrame()
                color_dot.setFixedSize(10, 10)
                color_dot.setStyleSheet(f"background-color: {color_tag}; border-radius: 5px;")
                top_bar.addWidget(color_dot)

            self.title_label = TitleLabel(self._todo_data.get("title", ""))
            self.title_label.setWordWrap(True)
            if is_done:
                self.title_label.setStyleSheet(f"""
                    color: {c['muted']};
                    text-decoration: line-through;
                    font-size: 18px;
                    font-weight: bold;
                """)
            else:
                self.title_label.setStyleSheet(f"""
                    color: {c['title']};
                    font-size: 18px;
                    font-weight: bold;
                """)

            status = self._todo_data.get("status", 0)
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
            top_bar.addWidget(status_tag)
        else:
            self.title_label = TitleLabel("任务详情")
            self.title_label.setStyleSheet(f"""
                color: {c['title']};
                font-size: 18px;
                font-weight: bold;
            """)

        self.title_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        top_bar.addWidget(self.title_label, 1)

        if self._is_widescreen:
            self._toggle_detail_btn = TransparentToolButton(FluentIcon.ALIGNMENT)
            self._toggle_detail_btn.setFixedSize(28, 28)
            self._toggle_detail_btn.setToolTip("显示/隐藏任务信息")
            self._toggle_detail_btn.clicked.connect(self._toggle_detail_panel)
            top_bar.addWidget(self._toggle_detail_btn)

        self.close_btn = TransparentToolButton(FluentIcon.CLOSE)
        self.close_btn.setFixedSize(28, 28)
        self.close_btn.clicked.connect(self.reject)
        top_bar.addWidget(self.close_btn)

        self.viewLayout.addLayout(top_bar)

        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet(f"background-color: {c['divider']};")
        self.viewLayout.addWidget(divider)

        if self._is_widescreen:
            self._setup_widescreen_body()
        else:
            self._setup_default_body()

        if self._is_widescreen:
            self.viewLayout.setContentsMargins(24, 16, 24, 4)
        else:
            self.viewLayout.setContentsMargins(20, 16, 20, 8)
        self.viewLayout.setSpacing(8)

    def _setup_default_body(self):
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setMinimumHeight(300)
        self.scroll.setMaximumHeight(500)
        self.scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
        """)

        self.content_widget = QWidget()
        self.content_widget.setObjectName("detailContent")
        self.content_widget.setStyleSheet("background-color: transparent;")
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 8, 0, 0)
        self.content_layout.setSpacing(0)

        self.scroll.setWidget(self.content_widget)
        self.viewLayout.addWidget(self.scroll, 1)

    def _setup_widescreen_body(self):
        self.body_layout = QHBoxLayout()
        self.body_layout.setSpacing(16)
        self.body_layout.setContentsMargins(0, 0, 0, 0)

        self.left_panel = QWidget()
        self.left_panel.setObjectName("leftPanel")
        self.left_layout = QVBoxLayout(self.left_panel)
        self.left_layout.setContentsMargins(0, 0, 0, 0)
        self.left_layout.setSpacing(0)

        self.right_panel = QWidget()
        self.right_panel.setObjectName("rightPanel")
        self.right_panel.setFixedWidth(240)
        self.right_layout = QVBoxLayout(self.right_panel)
        self.right_layout.setContentsMargins(0, 0, 0, 0)
        self.right_layout.setSpacing(8)
        self.right_layout.addStretch()

        self.body_layout.addWidget(self.left_panel, 1)
        self.body_layout.addWidget(self.right_panel)

        self.viewLayout.addLayout(self.body_layout, 1)

    def _rebuild_content(self):
        c = _tc()
        todo = self._todo_data
        if not todo:
            return

        is_done = todo.get("_is_done", False)
        is_archived = todo.get("_is_archived", False)

        if self._is_widescreen:
            self._clear_layout(self.left_layout)
            self._clear_layout(self.right_layout)
            self._build_widescreen_content(c, todo, is_done)
        else:
            self._clear_layout(self.content_layout)
            self._build_default_content(c, todo, is_done)

        if is_done and not is_archived:
            self.done_btn.setText("标记待办")
            self.done_btn.setIcon(FluentIcon.CANCEL)
        else:
            self.done_btn.setText("标记完成")
            self.done_btn.setIcon(FluentIcon.COMPLETED)

        if is_archived:
            self.edit_btn.hide()
            self.archive_btn.hide()
            self.done_btn.hide()
        elif is_done:
            self.edit_btn.show()
            self.archive_btn.show()
            self.done_btn.show()
        else:
            self.edit_btn.show()
            self.archive_btn.hide()

    # ---- 单栏模式内容 ----

    def _build_default_content(self, c: dict, todo: dict, is_done: bool):
        layout = self.content_layout

        # 标题区
        title_layout = QVBoxLayout()
        title_layout.setSpacing(8)
        title_layout.setContentsMargins(0, 0, 0, 0)

        title_row = QHBoxLayout()
        title_row.setSpacing(10)

        color_tag = todo.get("color_tag")
        if color_tag:
            color_dot = QFrame()
            color_dot.setFixedSize(12, 12)
            color_dot.setStyleSheet(f"background-color: {color_tag}; border-radius: 6px;")
            title_row.addWidget(color_dot)

        title_label = TitleLabel(todo.get("title", ""))
        title_label.setWordWrap(True)
        title_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        if is_done:
            title_label.setStyleSheet(f"color: {c['muted']}; text-decoration: line-through; font-size: 20px; font-weight: bold;")
        else:
            title_label.setStyleSheet(f"color: {c['title']}; font-size: 20px; font-weight: bold;")
        title_row.addWidget(title_label, 1)
        title_layout.addLayout(title_row)

        status = todo.get("status", 0)
        status_text = STATUS_MAP.get(status, "未知")
        status_tag = QLabel(f"  {status_text}  ")
        if is_done:
            status_tag.setStyleSheet(f"background-color: rgba(16, 124, 16, 0.12); color: {c['done_green']}; border-radius: 10px; font-size: 11px; padding: 2px 8px;")
        else:
            status_tag.setStyleSheet(f"background-color: {c['tag_bg']}; color: {c['accent']}; border-radius: 10px; font-size: 11px; padding: 2px 8px;")
        title_layout.addWidget(status_tag)

        layout.addLayout(title_layout)
        layout.addSpacing(16)

        # 描述区
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

            desc_body = QTextBrowser()
            desc_body.setOpenExternalLinks(True)
            desc_body.document().setDefaultStyleSheet(_markdown_css(c))
            desc_body.setMarkdown(desc)
            desc_body.setReadOnly(True)
            desc_body.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            desc_body.setStyleSheet(f"""
                QTextBrowser {{
                    background-color: transparent;
                    border: none;
                    color: {c['body']};
                    font-size: 13px;
                    padding: 0;
                }}
            """)
            desc_layout.addWidget(desc_body)

            layout.addWidget(desc_card)

        # 弹性空间，将信息区推到底部
        layout.addStretch(1)

        # 信息区
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

        self._build_info_rows(c, todo, is_done, info_layout)

        layout.addWidget(info_card)
        layout.addSpacing(12)

        # 子任务区
        children = todo.get("children", [])
        if children:
            self._build_subtask_section(c, children, layout)
            layout.addSpacing(12)

        # 附件区
        files = self._get_files(todo)
        file_count = len(files)
        if file_count > 0:
            self._build_file_section(c, files, file_count, layout)

    # ---- 分栏模式内容 ----

    def _build_widescreen_content(self, c: dict, todo: dict, is_done: bool):
        # 左侧：描述预览
        desc = todo.get("description", "")
        if desc:
            desc_browser = QTextBrowser()
            desc_browser.setOpenExternalLinks(True)
            desc_browser.document().setDefaultStyleSheet(_markdown_css(c))
            desc_browser.setMarkdown(desc)
            desc_browser.setReadOnly(True)
            desc_browser.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            desc_browser.setMinimumHeight(200)
            desc_browser.setStyleSheet(f"""
                QTextBrowser {{
                    background-color: {c['card_bg']};
                    border: 1px solid {c['divider']};
                    border-radius: 8px;
                    padding: 16px 20px;
                    color: {c['body']};
                }}
            """)
            self.left_layout.addWidget(desc_browser)
        else:
            empty_hint = QLabel("暂无描述")
            empty_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_hint.setStyleSheet(f"""
                color: {c['muted']};
                font-size: 14px;
                background-color: {c['card_bg']};
                border: 1px solid {c['divider']};
                border-radius: 8px;
                padding: 40px 20px;
            """)
            self.left_layout.addWidget(empty_hint, 1)

        # 右侧：元信息
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
        info_layout.setContentsMargins(12, 8, 12, 8)
        info_layout.setSpacing(0)

        info_header = CaptionLabel("任务信息")
        info_header.setStyleSheet(f"color: {c['muted']}; font-size: 11px; font-weight: bold; margin-bottom: 4px;")
        info_layout.addWidget(info_header)

        self._build_info_rows(c, todo, is_done, info_layout)

        self.right_layout.addWidget(info_card)

        # 子任务卡片
        children = todo.get("children", [])
        if children:
            subtask_card = QFrame()
            subtask_card.setObjectName("subtaskCard")
            subtask_card.setStyleSheet(f"""
                QFrame#subtaskCard {{
                    background-color: {c['card_bg']};
                    border: 1px solid {c['divider']};
                    border-radius: 8px;
                }}
            """)
            subtask_layout = QVBoxLayout(subtask_card)
            subtask_layout.setContentsMargins(12, 8, 12, 8)
            subtask_layout.setSpacing(4)

            subtask_header = QHBoxLayout()
            subtask_header.setSpacing(6)
            subtask_title = CaptionLabel("子任务")
            subtask_title.setStyleSheet(f"color: {c['muted']}; font-size: 11px; font-weight: bold;")
            subtask_header.addWidget(subtask_title)
            done_count = sum(1 for ch in children if ch.get("_is_done", False))
            count_label = CaptionLabel(f"{done_count}/{len(children)}")
            count_label.setStyleSheet(f"color: {c['accent']}; font-size: 11px;")
            subtask_header.addWidget(count_label)

            progress_pct = int(done_count / len(children) * 100) if children else 0
            progress_bar = QFrame()
            progress_bar.setFixedHeight(3)
            progress_bar.setStyleSheet(f"background-color: {c['divider']}; border-radius: 1px;")
            progress_fill = QFrame(progress_bar)
            progress_fill.setFixedHeight(3)
            fill_width = max(1, int(200 * progress_pct / 100))
            progress_fill.setFixedWidth(fill_width)
            progress_fill.setStyleSheet(f"background-color: {c['accent']}; border-radius: 1px;")
            subtask_header.addWidget(progress_bar, 1)

            subtask_layout.addLayout(subtask_header)

            for child in children:
                item = SubtaskItem(child)
                item.toggle_done.connect(self.subtask_toggle_done.emit)
                subtask_layout.addWidget(item)

            self.right_layout.addWidget(subtask_card)

        # 附件卡片
        files = self._get_files(todo)
        file_count = len(files)
        if file_count > 0:
            file_card = QFrame()
            file_card.setObjectName("fileCard")
            file_card.setStyleSheet(f"""
                QFrame#fileCard {{
                    background-color: {c['card_bg']};
                    border: 1px solid {c['divider']};
                    border-radius: 8px;
                }}
            """)
            file_layout = QVBoxLayout(file_card)
            file_layout.setContentsMargins(12, 8, 12, 8)
            file_layout.setSpacing(4)

            file_header = QHBoxLayout()
            file_header.setSpacing(6)
            file_title = CaptionLabel("附件")
            file_title.setStyleSheet(f"color: {c['muted']}; font-size: 11px; font-weight: bold;")
            file_header.addWidget(file_title)
            file_count_label = CaptionLabel(f"{file_count}")
            file_count_label.setStyleSheet(f"color: {c['accent']}; font-size: 11px;")
            file_header.addWidget(file_count_label)
            file_header.addStretch()
            file_layout.addLayout(file_header)

            for f_info in files[:5]:
                fid = todo.get("recurrence_template_id") if f_info.get("_from_template") else self._current_todo_id
                item = FileItem(f_info, fid)
                file_layout.addWidget(item)

            if file_count > 5:
                more_btn = PushButton(f"查看全部 ({file_count})")
                more_btn.setFixedHeight(26)
                more_btn.setStyleSheet(f"font-size: 12px; padding: 0 8px; color: {c['accent']}; background-color: {c['card_bg']}; border: 1px solid {c['divider']}; border-radius: 4px;")
                more_btn.clicked.connect(lambda: self._open_task_folder())
                file_layout.addWidget(more_btn)
            elif file_count > 0:
                view_all_btn = PushButton("打开文件夹")
                view_all_btn.setFixedHeight(26)
                view_all_btn.setStyleSheet(f"font-size: 12px; padding: 0 8px; color: {c['accent']}; background-color: {c['card_bg']}; border: 1px solid {c['divider']}; border-radius: 4px;")
                view_all_btn.clicked.connect(lambda: self._open_task_folder())
                file_layout.addWidget(view_all_btn)

            self.right_layout.addWidget(file_card)

    # ---- 共用构建方法 ----

    def _build_info_rows(self, c: dict, todo: dict, is_done: bool, layout: QVBoxLayout):
        priority = todo.get("priority", 0)
        if priority > 0:
            priority_text = PRIORITY_MAP.get(priority, "无")
            priority_color = c['muted']
            if priority == 1:
                priority_color = c['priority_urgent_important']
            elif priority == 2:
                priority_color = c['priority_important']
            elif priority == 3:
                priority_color = c['priority_urgent']
            elif priority == 4:
                priority_color = c['priority_minor']
            row = InfoRow(FluentIcon.HEART, "优先级", priority_text, priority_color)
            layout.addWidget(row)
            self._add_divider(layout, c)

        category = todo.get("category")
        if category:
            row = InfoRow(FluentIcon.TAG, "分类", category.get("name", ""))
            layout.addWidget(row)
            self._add_divider(layout, c)

        start = todo.get("start_date")
        if start:
            row = InfoRow(FluentIcon.CALENDAR, "起始日期", start)
            layout.addWidget(row)
            self._add_divider(layout, c)

        due = todo.get("due_date")
        if due:
            try:
                due_date = date.fromisoformat(due)
                today = date.today()
                if due_date < today and not is_done:
                    due_text = f"{due} | 已过期"
                    due_color = c['overdue']
                elif due_date == today:
                    due_text = f"{due} | 今天"
                    due_color = c['accent']
                else:
                    due_text = due
                    due_color = None
            except (ValueError, TypeError):
                due_text = due
                due_color = None
            row = InfoRow(FluentIcon.CALENDAR, "截止日期", due_text, due_color)
            layout.addWidget(row)
            self._add_divider(layout, c)

        auto_postpone = todo.get("auto_postpone", False)
        if auto_postpone:
            row = InfoRow(FluentIcon.SYNC, "自动延期", "开启")
            layout.addWidget(row)
            self._add_divider(layout, c)

        recurrence_type = todo.get("recurrence_type")
        if recurrence_type:
            from config.constants import RECURRENCE_TYPES, WEEKDAY_NAMES, parse_recurrence_day
            interval = todo.get("recurrence_interval", 1)
            recurrence_day = todo.get("recurrence_day")
            type_name = RECURRENCE_TYPES.get(recurrence_type, "")
            if recurrence_type == "weekly" and recurrence_day:
                days = parse_recurrence_day(recurrence_day)
                day_names = "".join(WEEKDAY_NAMES.get(d, "") for d in sorted(days))
                if interval > 1:
                    text = f"每{interval}周周{day_names}"
                else:
                    text = f"每周{day_names}"
            elif recurrence_type == "monthly" and recurrence_day:
                day_list = parse_recurrence_day(recurrence_day)
                day_val = day_list[0] if day_list else ""
                if interval > 1:
                    text = f"每{interval}月{day_val}号"
                else:
                    text = f"每月{day_val}号"
            elif interval > 1:
                unit = {"daily": "天", "weekly": "周", "monthly": "月"}.get(recurrence_type, "")
                text = f"每{interval}{unit}"
            else:
                text = type_name
            start_str = todo.get("recurrence_start_date")
            end_str = todo.get("recurrence_end_date")
            if start_str and end_str:
                text += f"（{start_str} ~ {end_str}）"
            elif start_str:
                text += f"（从 {start_str}）"
            elif end_str:
                text += f"（至 {end_str}）"
            row = InfoRow(FluentIcon.UPDATE, "重复", text)
            layout.addWidget(row)
            self._add_divider(layout, c)

        if is_done:
            completed = todo.get("completed_at")
            if completed:
                try:
                    dt = datetime.fromisoformat(completed)
                    completed_text = dt.strftime("%Y-%m-%d %H:%M")
                except (ValueError, TypeError):
                    completed_text = completed
                row = InfoRow(FluentIcon.COMPLETED, "完成时间", completed_text, c['done_green'])
                layout.addWidget(row)
                self._add_divider(layout, c)

        created = todo.get("created_at")
        if created:
            try:
                dt = datetime.fromisoformat(created)
                created_text = dt.strftime("%Y-%m-%d %H:%M")
            except (ValueError, TypeError):
                created_text = created
            row = InfoRow(FluentIcon.HISTORY, "创建时间", created_text)
            layout.addWidget(row)
            self._add_divider(layout, c)

        updated = todo.get("updated_at")
        if updated:
            try:
                dt = datetime.fromisoformat(updated)
                updated_text = dt.strftime("%Y-%m-%d %H:%M")
            except (ValueError, TypeError):
                updated_text = updated
            row = InfoRow(FluentIcon.INFO, "更新时间", updated_text)
            layout.addWidget(row)

    def _build_subtask_section(self, c: dict, children: list, layout: QVBoxLayout):
        subtask_header = QHBoxLayout()
        subtask_header.setSpacing(6)

        subtask_title = CaptionLabel("子任务")
        subtask_title.setStyleSheet(f"color: {c['muted']}; font-size: 11px; font-weight: bold;")
        subtask_header.addWidget(subtask_title)

        done_count = sum(1 for ch in children if ch.get("_is_done", False))
        count_label = CaptionLabel(f"{done_count}/{len(children)}")
        count_label.setStyleSheet(f"color: {c['accent']}; font-size: 11px;")
        subtask_header.addWidget(count_label)
        subtask_header.addStretch()

        layout.addLayout(subtask_header)
        layout.addSpacing(6)

        for child in children:
            item = SubtaskItem(child)
            item.toggle_done.connect(self.subtask_toggle_done.emit)
            layout.addWidget(item)
            layout.addSpacing(4)

    def _build_file_section(self, c: dict, files: list, file_count: int, layout: QVBoxLayout):
        file_header = QHBoxLayout()
        file_header.setSpacing(6)

        file_title = CaptionLabel("附件")
        file_title.setStyleSheet(f"color: {c['muted']}; font-size: 11px; font-weight: bold;")
        file_header.addWidget(file_title)

        file_count_label = CaptionLabel(f"{file_count}")
        file_count_label.setStyleSheet(f"color: {c['accent']}; font-size: 11px;")
        file_header.addWidget(file_count_label)
        file_header.addStretch()

        layout.addLayout(file_header)
        layout.addSpacing(6)

        template_id = self._todo_data.get("recurrence_template_id")
        for f_info in files[:5]:
            fid = template_id if f_info.get("_from_template") else self._current_todo_id
            item = FileItem(f_info, fid)
            layout.addWidget(item)
            layout.addSpacing(4)

        if file_count > 5:
            more_btn = PushButton("查看全部")
            more_btn.setFixedHeight(28)
            more_btn.setStyleSheet(f"font-size: 12px; padding: 0 8px; color: {c['accent']}; background-color: {c['card_bg']}; border: 1px solid {c['divider']}; border-radius: 4px;")
            more_btn.clicked.connect(lambda: self._open_task_folder())
            layout.addWidget(more_btn)
        elif file_count > 0:
            view_all_btn = PushButton("查看全部")
            view_all_btn.setFixedHeight(28)
            view_all_btn.setStyleSheet(f"font-size: 12px; padding: 0 8px; color: {c['accent']}; background-color: {c['card_bg']}; border: 1px solid {c['divider']}; border-radius: 4px;")
            view_all_btn.clicked.connect(lambda: self._open_task_folder())
            layout.addWidget(view_all_btn)

    def _get_files(self, todo: dict) -> list:
        files = self._file_service.get_files(self._current_todo_id)
        template_id = todo.get("recurrence_template_id")
        if template_id and todo.get("recurrence_type"):
            template_files = self._file_service.get_files(template_id)
            existing_paths = {f["path"] for f in files}
            for tf in template_files:
                if tf["path"] not in existing_paths:
                    tf["_from_template"] = True
                    files.append(tf)
        return files

    def _add_divider(self, layout: QVBoxLayout, c: dict):
        line = QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet(f"background-color: {c['divider']};")
        layout.addWidget(line)

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

    def _on_toggle_done(self):
        self._pending_action = ("toggle_done", self._current_todo_id)
        self.reject()

    def _toggle_detail_panel(self):
        """切换宽屏模式下右侧任务信息面板的显示/隐藏"""
        if hasattr(self, 'right_panel'):
            self.right_panel.setVisible(not self.right_panel.isVisible())

    def _on_edit(self):
        self._pending_action = ("edit", self._current_todo_id)
        self.reject()

    def _on_archive(self):
        self._pending_action = ("archive", self._current_todo_id)
        self.reject()

    def _on_delete(self):
        self._pending_action = ("delete", self._current_todo_id)
        self.reject()

    def _on_subtask_toggle(self, todo_id: int):
        self._pending_action = ("subtask_toggle_done", todo_id)
        self.reject()

    def _open_task_folder(self):
        self._file_service.open_folder(self._current_todo_id)
        template_id = self._todo_data.get("recurrence_template_id")
        if template_id and self._todo_data.get("recurrence_type"):
            self._file_service.open_folder(template_id)
