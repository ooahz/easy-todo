"""Markdown 编辑器组件 - 支持编辑和预览切换"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextBrowser, QLabel
)

from qfluentwidgets import (
    TextEdit, isDarkTheme
)


class TabButton(QLabel):
    """文字标签切换按钮"""

    clicked = Signal()

    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self._active = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(26)
        self._update_style()

    def set_active(self, active: bool):
        self._active = active
        self._update_style()

    def _update_style(self):
        dark = isDarkTheme()
        if self._active:
            color = "#0078D4"
            bg = "rgba(0, 120, 212, 0.1)"
            border = "rgba(0, 120, 212, 0.3)"
            weight = "bold"
        else:
            color = "#888" if not dark else "#777"
            bg = "transparent"
            border = "transparent"
            weight = "normal"

        self.setStyleSheet(f"""
            QLabel {{
                color: {color};
                background-color: {bg};
                border: 1px solid {border};
                border-radius: 4px;
                padding: 2px 10px;
                font-size: 12px;
                font-weight: {weight};
            }}
            QLabel:hover {{
                color: #0078D4;
                background-color: rgba(0, 120, 212, 0.08);
                border: 1px solid rgba(0, 120, 212, 0.2);
            }}
        """)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class MarkdownEditor(QWidget):
    """Markdown 编辑器，支持编辑/预览切换"""

    textChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_preview = False
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 工具栏
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(0, 0, 0, 6)
        toolbar.setSpacing(4)

        self.edit_btn = TabButton("编辑")
        self.edit_btn.clicked.connect(self._switch_to_edit)

        self.preview_btn = TabButton("预览")
        self.preview_btn.clicked.connect(self._switch_to_preview)

        toolbar.addStretch()
        toolbar.addWidget(self.edit_btn)
        toolbar.addWidget(self.preview_btn)

        layout.addLayout(toolbar)

        # 编辑器
        self.editor = TextEdit()
        self.editor.setPlaceholderText("支持 Markdown 语法输入...")
        self.editor.textChanged.connect(self._on_text_changed)
        layout.addWidget(self.editor)

        # 预览器
        self.preview = QTextBrowser()
        self.preview.setOpenExternalLinks(True)
        self.preview.hide()
        layout.addWidget(self.preview)

        self._update_toolbar_state()

    def _update_toolbar_state(self):
        """更新工具栏按钮状态"""
        self.edit_btn.set_active(not self._is_preview)
        self.preview_btn.set_active(self._is_preview)

    def _switch_to_edit(self):
        if not self._is_preview:
            return
        self._is_preview = False
        self.preview.hide()
        self.editor.show()
        self._update_toolbar_state()

    def _switch_to_preview(self):
        if self._is_preview:
            return
        self._is_preview = True
        md_text = self.editor.toPlainText()
        self._render_preview(md_text)
        self.editor.hide()
        self.preview.show()
        self._update_toolbar_state()

    def _render_preview(self, text: str):
        """渲染 Markdown 预览"""
        dark = isDarkTheme()
        bg = "#2D2D2D" if dark else "#FFFFFF"
        color = "#DDD" if dark else "#333"
        link_color = "#60CDFF" if dark else "#0078D4"
        code_bg = "#3A3A3A" if dark else "#F5F5F5"
        code_border = "#555" if dark else "#DDD"

        css = f"""
            body {{
                font-family: "Segoe UI", "Microsoft YaHei", "PingFang SC", sans-serif;
                font-size: 13px;
                line-height: 1.6;
                color: {color};
                background-color: {bg};
                padding: 4px;
                margin: 0;
            }}
            h1, h2, h3, h4, h5, h6 {{
                margin: 8px 0 4px;
                font-weight: bold;
            }}
            h1 {{ font-size: 20px; }}
            h2 {{ font-size: 17px; }}
            h3 {{ font-size: 15px; }}
            p {{ margin: 4px 0; }}
            code {{
                background-color: {code_bg};
                border: 1px solid {code_border};
                border-radius: 3px;
                padding: 1px 4px;
                font-family: "Cascadia Code", "Consolas", monospace;
                font-size: 12px;
            }}
            pre {{
                background-color: {code_bg};
                border: 1px solid {code_border};
                border-radius: 4px;
                padding: 8px;
                overflow-x: auto;
            }}
            pre code {{
                border: none;
                padding: 0;
                background: transparent;
            }}
            blockquote {{
                border-left: 3px solid {link_color};
                margin: 4px 0;
                padding: 2px 8px;
                color: {"#AAA" if dark else "#666"};
            }}
            a {{
                color: {link_color};
                text-decoration: none;
            }}
            ul, ol {{
                margin: 4px 0;
                padding-left: 20px;
            }}
            li {{ margin: 2px 0; }}
            hr {{
                border: none;
                border-top: 1px solid {code_border};
                margin: 8px 0;
            }}
            table {{
                border-collapse: collapse;
                margin: 4px 0;
            }}
            th, td {{
                border: 1px solid {code_border};
                padding: 4px 8px;
            }}
            th {{
                background-color: {code_bg};
            }}
            img {{
                max-width: 100%;
            }}
        """
        self.preview.document().setDefaultStyleSheet(css)
        self.preview.setMarkdown(text)

    def _on_text_changed(self):
        self.textChanged.emit()
        # 如果正在预览，实时更新
        if self._is_preview:
            self._render_preview(self.editor.toPlainText())

    # ---- 公共接口 ----
    def toPlainText(self) -> str:
        return self.editor.toPlainText()

    def setPlainText(self, text: str):
        self.editor.setPlainText(text)

    def setPlaceholderText(self, text: str):
        self.editor.setPlaceholderText(text)

    def setMinimumHeight(self, h: int):
        self.editor.setMinimumHeight(h)
        self.preview.setMinimumHeight(h)

    def setMaximumHeight(self, h: int):
        self.editor.setMaximumHeight(h)
        self.preview.setMaximumHeight(h)

    def textCursor(self):
        return self.editor.textCursor()
