"""新建/编辑待办对话框"""
import os
from datetime import date, datetime

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFileDialog
)

from qfluentwidgets import (
    LineEdit, TextEdit, ComboBox, CalendarPicker,
    PrimaryPushButton, PushButton, SubtitleLabel, CheckBox,
    FluentIcon, isDarkTheme, setCustomStyleSheet, BodyLabel, CaptionLabel
)

from config.constants import PRIORITY_MAP, TODO_COLORS
from services.category_service import CategoryService
from services.file_service import FileService


class TodoDialog(QDialog):
    """新建/编辑待办对话框"""

    todo_saved = Signal(dict)

    def __init__(self, todo_data: dict = None, parent=None):
        super().__init__(parent)
        self.todo_data = todo_data
        self._is_edit = todo_data is not None
        self._selected_color = None
        self._category_service = CategoryService()
        self._file_service = FileService()
        self._temp_files = []  # 临时存储待上传的文件

        self.setWindowTitle("编辑任务" if self._is_edit else "新建任务")
        self.setFixedSize(480, 580)

        self._setup_ui()
        self._connect_signals()
        self._load_categories()

        if self._is_edit:
            self._fill_data(todo_data)
            self._load_files()

        # 启用拖放
        self.setAcceptDrops(True)

    def _setup_ui(self):
        """构建对话框 UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 20)
        layout.setSpacing(12)

        # 标题
        title = SubtitleLabel("编辑任务" if self._is_edit else "新建任务")
        layout.addWidget(title)

        # 分隔线
        sep = QLabel()
        sep.setFixedHeight(1)
        sep.setObjectName("dialogSep")
        setCustomStyleSheet(
            sep,
            "#dialogSep { background-color: rgba(0,0,0,0.08); }",
            "#dialogSep { background-color: rgba(255,255,255,0.06); }"
        )
        layout.addWidget(sep)

        # 标题输入
        self.title_edit = LineEdit()
        self.title_edit.setPlaceholderText("输入任务标题...")
        self.title_edit.setClearButtonEnabled(True)
        self.title_edit.setMaxLength(100)
        layout.addWidget(self.title_edit)

        # 描述输入
        self.desc_edit = TextEdit()
        self.desc_edit.setPlaceholderText("添加详细描述（可选）...")
        self.desc_edit.setMinimumHeight(72)
        self.desc_edit.setMaximumHeight(120)
        layout.addWidget(self.desc_edit)

        # 优先级 + 截止日期
        row1 = QHBoxLayout()
        row1.setSpacing(20)

        self.priority_combo = ComboBox()
        self.priority_combo.setFixedWidth(210)
        self.priority_combo.addItem("选择优先级", userData=None)
        for val, name in PRIORITY_MAP.items():
            self.priority_combo.addItem(name, userData=val)
        self.priority_combo.setCurrentIndex(0)
        row1.addWidget(self.priority_combo)

        self.due_picker = CalendarPicker()
        self.due_picker.setFixedWidth(210)
        try:
            self.due_picker.setText("截止日期")
        except Exception:
            pass
        row1.addWidget(self.due_picker)

        row1.addStretch()
        layout.addLayout(row1)

        # 分类选择
        self.category_combo = ComboBox()
        self.category_combo.setFixedWidth(210)
        self.category_combo.addItem("无分类", userData=None)
        layout.addWidget(self.category_combo)

        # 自动延期
        self.auto_postpone_cb = CheckBox("自动延期")
        self.auto_postpone_cb.setToolTip("开启后，过期未完成的任务会自动延期到当天")
        layout.addWidget(self.auto_postpone_cb)

        # 颜色标签
        color_row = QHBoxLayout()
        color_row.setSpacing(8)

        self.color_buttons = []
        dark = isDarkTheme()
        for name, color in TODO_COLORS:
            btn = QPushButton()
            btn.setFixedSize(24, 24)
            btn.setCheckable(True)
            checked_border = "border: 2px solid #AAA;" if dark else "border: 2px solid #333;"
            hover_border = "border: 2px solid #888;" if dark else "border: 2px solid #666;"
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {color};
                    border-radius: 12px;
                    border: 2px solid transparent;
                }}
                QPushButton:checked {{
                    {checked_border}
                }}
                QPushButton:hover {{
                    {hover_border}
                }}
            """)
            btn.setToolTip(name)
            btn.setProperty("color_value", color)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked, c=color, b=btn: self._on_color_clicked(c, b))
            color_row.addWidget(btn)
            self.color_buttons.append(btn)

        color_row.addStretch()
        layout.addLayout(color_row)

        # 文件上传区域
        self.drop_area = QLabel("📎 拖放文件到此处，或点击选择文件")
        self.drop_area.setFixedHeight(40)
        self.drop_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drop_area.setStyleSheet("""
            QLabel {
                border: 2px dashed #888;
                border-radius: 6px;
                color: #888;
            }
        """)
        self.drop_area.setCursor(Qt.PointingHandCursor)
        self.drop_area.mousePressEvent = lambda e: self._on_select_file()
        layout.addWidget(self.drop_area)

        # 文件数量
        self.file_count_label = QLabel("")
        self.file_count_label.setStyleSheet("color: #666; font-size: 12px;")
        layout.addWidget(self.file_count_label)

        # 打开文件夹按钮（仅编辑模式）
        if self._is_edit:
            self.open_folder_btn = PushButton(FluentIcon.FOLDER, "打开文件夹")
            self.open_folder_btn.clicked.connect(self._on_open_folder)
            layout.addWidget(self.open_folder_btn)

        layout.addStretch()

        # 按钮区
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        btn_layout.addStretch()

        self.cancel_btn = PushButton("取消")
        self.cancel_btn.setFixedWidth(100)
        self.cancel_btn.clicked.connect(self.close)

        self.save_btn = PrimaryPushButton("保存")
        self.save_btn.setFixedWidth(100)
        self.save_btn.setIcon(FluentIcon.SAVE)
        self.save_btn.clicked.connect(self._on_save)

        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addWidget(self.save_btn)
        layout.addLayout(btn_layout)

    def _connect_signals(self):
        self.title_edit.returnPressed.connect(self._on_save)
        self.desc_edit.textChanged.connect(self._on_desc_changed)

    def _on_desc_changed(self):
        """限制描述最多1000字符"""
        text = self.desc_edit.toPlainText()
        if len(text) > 1000:
            cursor = self.desc_edit.textCursor()
            cursor.setPosition(1000)
            cursor.movePosition(cursor.MoveOperation.End, cursor.MoveMode.KeepAnchor)
            cursor.removeSelectedText()

    def _on_color_clicked(self, color: str, btn: QPushButton):
        if self._selected_color == color:
            btn.setChecked(False)
            self._selected_color = None
        else:
            for b in self.color_buttons:
                b.setChecked(False)
            btn.setChecked(True)
            self._selected_color = color

    def _on_select_file(self):
        """选择文件"""
        files, _ = QFileDialog.getOpenFileNames(
            self, "选择文件", "", "所有文件 (*.*)"
        )
        if files:
            for f in files:
                self._add_file(f)

    def _add_file(self, file_path: str):
        """添加文件到列表"""
        if file_path not in self._temp_files:
            self._temp_files.append(file_path)
            self._update_file_list()

    def _update_file_list(self):
        """更新文件数量显示"""
        count = len(self._temp_files)
        if count == 0:
            self.file_count_label.setText("")
        else:
            self.file_count_label.setText(f"待上传 {count} 个文件")

    def _load_files(self):
        """加载已关联的文件数量"""
        if not self.todo_data:
            return

        todo_id = self.todo_data.get("id")
        if not todo_id:
            return

        count = self._file_service.get_file_count(todo_id)
        if count > 0:
            self.file_count_label.setText(f"已关联 {count} 个文件")

    def _on_open_folder(self):
        """打开任务关联文件夹"""
        if self.todo_data and self.todo_data.get("id"):
            self._file_service.open_folder(self.todo_data["id"])

    def _save_files(self, todo_id: int):
        """保存临时文件到任务文件夹"""
        saved_files = []
        for file_path in self._temp_files:
            try:
                saved_name = self._file_service.save_file(todo_id, file_path)
                saved_files.append(saved_name)
            except Exception as e:
                print(f"保存文件失败: {e}")
        return saved_files

    def _fill_data(self, data: dict):
        self.title_edit.setText(data.get("title", ""))
        self.desc_edit.setPlainText(data.get("description", ""))

        priority = data.get("priority", 0)
        for i in range(self.priority_combo.count()):
            if self.priority_combo.itemData(i) == priority:
                self.priority_combo.setCurrentIndex(i)
                break

        color_tag = data.get("color_tag")
        if color_tag:
            self._selected_color = color_tag
            for btn in self.color_buttons:
                if btn.property("color_value") == color_tag:
                    btn.setChecked(True)
                    break

        # 自动延期
        self.auto_postpone_cb.setChecked(data.get("auto_postpone", False))

        # 分类
        category_id = data.get("category_id")
        for i in range(self.category_combo.count()):
            if self.category_combo.itemData(i) == category_id:
                self.category_combo.setCurrentIndex(i)
                break

        due_str = data.get("due_date")
        if due_str:
            try:
                from PySide6.QtCore import QDate
                if isinstance(due_str, str):
                    pyd = date.fromisoformat(due_str)
                    self.due_picker.setDate(QDate(pyd.year, pyd.month, pyd.day))
                else:
                    self.due_picker.setDate(QDate(due_str.year, due_str.month, due_str.day))
            except Exception:
                pass

    def _on_save(self):
        title = self.title_edit.text().strip()
        if not title:
            self.title_edit.setStyleSheet(
                "LineEdit { border: 2px solid #D13438; border-radius: 6px; }"
            )
            return

        due_date = None
        try:
            qdate = self.due_picker.date
            if qdate is not None and hasattr(qdate, 'isValid') and qdate.isValid():
                due_date = date(qdate.year(), qdate.month(), qdate.day())
        except Exception:
            pass

        priority_val = self.priority_combo.currentData()
        priority = priority_val if priority_val is not None else 0

        data = {
            "title": title,
            "description": self.desc_edit.toPlainText().strip(),
            "priority": priority,
            "color_tag": self._selected_color,
            "due_date": due_date,
            "auto_postpone": self.auto_postpone_cb.isChecked(),
            "category_id": self.category_combo.currentData(),
            "temp_files": self._temp_files,  # 传递待上传的文件
        }

        if self._is_edit:
            data["id"] = self.todo_data["id"]

        self.todo_saved.emit(data)
        self.close()

    def _load_categories(self):
        """加载分类列表"""
        self.category_combo.clear()
        self.category_combo.addItem("无分类", userData=None)
        categories = self._category_service.get_all()
        for cat in categories:
            self.category_combo.addItem(cat.name, userData=cat.id)

    # ---- 拖放支持 ----
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.drop_area.setStyleSheet("""
                QLabel {
                    border: 2px dashed #0078D4;
                    border-radius: 6px;
                    color: #0078D4;
                    background-color: rgba(0, 120, 212, 0.1);
                }
            """)

    def dragLeaveEvent(self, event):
        self.drop_area.setStyleSheet("""
            QLabel {
                border: 2px dashed #888;
                border-radius: 6px;
                color: #888;
            }
        """)

    def dropEvent(self, event):
        self.drop_area.setStyleSheet("""
            QLabel {
                border: 2px dashed #888;
                border-radius: 6px;
                color: #888;
            }
        """)

        urls = event.mimeData().urls()
        for url in urls:
            file_path = url.toLocalFile()
            if file_path:
                self._add_file(file_path)

    def showEvent(self, event):
        super().showEvent(event)
        self.title_edit.setFocus()
        self.title_edit.setStyleSheet("")
        # 对话框背景跟随主题
        if isDarkTheme():
            self.setStyleSheet(
                "QDialog { background-color: rgb(43, 43, 43); }"
                "SubtitleLabel { color: #EEE; }"
                "BodyLabel { color: #DDD; }"
                "CaptionLabel { color: #AAA; }"
                "QLabel { color: #DDD; }"
                "LineEdit { background-color: rgb(59, 59, 59); color: #EEE; border: 1px solid rgb(80,80,80); border-radius: 6px; }"
                "TextEdit { background-color: rgb(59, 59, 59); color: #EEE; border: 1px solid rgb(80,80,80); border-radius: 6px; }"
                "CheckBox { color: #DDD; }"
            )
        else:
            self.setStyleSheet(
                "QDialog { background-color: rgb(249, 249, 249); }"
                "SubtitleLabel { color: #111; }"
                "BodyLabel { color: #333; }"
                "CaptionLabel { color: #666; }"
                "QLabel { color: #333; }"
                "LineEdit { background-color: #FFF; color: #333; }"
                "TextEdit { background-color: #FFF; color: #333; }"
                "CheckBox { color: #333; }"
            )
