"""Markdown 编辑器组件 - 支持编辑和预览切换（右键菜单）"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QBuffer, QIODevice
from PySide6.QtGui import QAction, QCursor, QImage
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTextBrowser, QMenu
)

from qfluentwidgets import (
    TextEdit, isDarkTheme
)

from config.theme_config import font_family_str, mono_family_str


class PasteImageTextEdit(TextEdit):
    """支持粘贴图片的 TextEdit：拦截 QMimeData.imageData，发送 imagePasted 信号。"""

    imagePasted = Signal(str, bytes)

    def canInsertFromMimeData(self, source):  # noqa: N802 (Qt API)
        if source is not None and source.hasImage():
            return True
        return super().canInsertFromMimeData(source)

    def insertFromMimeData(self, source):  # noqa: N802 (Qt API)
        if source is not None and source.hasImage():
            image: QImage = source.imageData()
            if image is None or image.isNull():
                return
            buf = self._qimage_to_bytes(image, "PNG")
            self.imagePasted.emit("png", buf)
            return
        super().insertFromMimeData(source)

    @staticmethod
    def _qimage_to_bytes(image: QImage, fmt: str = "PNG") -> bytes:
        ba = QBuffer()
        ba.open(QIODevice.OpenModeFlag.WriteOnly)
        if not image.save(ba, fmt):
            ba.close()
            return b""
        data = bytes(ba.data())
        ba.close()
        return data


class MarkdownEditor(QWidget):
    """Markdown 编辑器，支持编辑/预览切换（右键菜单）"""

    textChanged = Signal()
    imagePasted = Signal(str, bytes)
    """imagePasted(ext, data) - 剪贴板里有图片被粘贴时发出，由宿主保存到任务文件夹。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_preview = False
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 编辑器
        self.editor = PasteImageTextEdit()
        self.editor.setPlaceholderText("支持 Markdown 语法输入（右键唤起菜单，可直接 Ctrl+V 粘贴图片）")
        self.editor.textChanged.connect(self._on_text_changed)
        self.editor.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.editor.customContextMenuRequested.connect(self._show_edit_menu)
        self.editor.imagePasted.connect(self.imagePasted)
        layout.addWidget(self.editor)

        # 预览器
        self.preview = QTextBrowser()
        self.preview.setOpenExternalLinks(True)
        self.preview.hide()
        self.preview.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.preview.customContextMenuRequested.connect(self._show_preview_menu)
        layout.addWidget(self.preview)

    def _show_edit_menu(self, pos):
        """编辑模式下显示右键菜单"""
        menu = QMenu(self)
        menu.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        preview_action = QAction("预览", self)
        preview_action.triggered.connect(self._switch_to_preview)
        menu.addAction(preview_action)

        menu.addSeparator()

        # 保留编辑器默认的右键操作
        standard_menu = self.editor.createStandardContextMenu()
        for action in standard_menu.actions():
            menu.addAction(action)

        menu.exec(QCursor.pos())

    def _show_preview_menu(self, pos):
        """预览模式下显示右键菜单"""
        menu = QMenu(self)
        menu.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        edit_action = QAction("编辑", self)
        edit_action.triggered.connect(self._switch_to_edit)
        menu.addAction(edit_action)

        menu.exec(QCursor.pos())

    def _switch_to_edit(self):
        if not self._is_preview:
            return
        self._is_preview = False
        self.preview.hide()
        self.editor.show()

    def _switch_to_preview(self):
        if self._is_preview:
            return
        self._is_preview = True
        md_text = self.editor.toPlainText()
        self._render_preview(md_text)
        self.editor.hide()
        self.preview.show()

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
                font-family: {font_family_str()};
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
                font-family: {mono_family_str()};
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
                max-width: 90%;
                max-height: 300px;
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

    def setTextCursor(self, cursor):
        self.editor.setTextCursor(cursor)

    def setSearchPaths(self, paths):
        """设置图片搜索路径（用于预览渲染时解析 markdown 里的相对图片引用）。"""
        self.preview.setSearchPaths(paths or [])
