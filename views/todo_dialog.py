"""新建/编辑待办对话框"""
from __future__ import annotations
import os
from datetime import date

from PySide6.QtCore import Signal, Qt, QDate, QSize
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFileDialog, QFrame, QWidget,
    QTextEdit
)

from qfluentwidgets import (
    LineEdit, TextEdit, ComboBox, CalendarPicker,
    PrimaryPushButton, PushButton, SubtitleLabel, CheckBox,
    FluentIcon, isDarkTheme, setCustomStyleSheet, BodyLabel, SpinBox, TransparentToolButton, CompactSpinBox
)

from config.constants import PRIORITY_MAP, TODO_COLORS, RECURRENCE_TYPES
from config.settings import settings
from services.category_service import CategoryService
from services.file_service import FileService


class TodoDialog(QDialog):
    """新建/编辑待办对话框，支持父任务和子任务"""

    todo_saved = Signal(dict)

    def __init__(self, todo_data: dict = None, parent=None, pid: int = None,
                 edit_mode: str = None, template_data: dict = None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)

        self.todo_data = todo_data
        self._is_edit = todo_data is not None
        self._edit_mode = edit_mode
        self._template_data = template_data
        # 父任务ID：新建时传入，编辑时从数据读取
        self._pid = pid if pid is not None else (todo_data.get("pid") if todo_data else None)
        self._selected_color = None
        self._category_service = CategoryService()
        self._file_service = FileService()
        self._temp_files = []

        # 子任务窗口更小、更简洁
        if self._pid is not None:
            self.setFixedSize(400, 160)
        else:
            self.setFixedSize(480, 500)

        self._setup_ui()
        self._connect_signals()
        self._load_categories()

        if self._is_edit:
            self._fill_data(todo_data)
            self._load_files()

        self.setAcceptDrops(True)

        # 窗口拖动相关
        self._drag_pos = None

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

    def closeEvent(self, event):
        """关闭时释放数据库连接"""
        if hasattr(self, '_category_service') and self._category_service:
            self._category_service.close()
        if hasattr(self, '_file_service') and self._file_service:
            self._file_service.close()
        super().closeEvent(event)

    def _setup_ui(self):
        """构建对话框 UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 12, 20, 16)
        layout.setSpacing(10)

        # ---- 顶部栏 ----
        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)

        panel_title = SubtitleLabel("编辑任务" if self._is_edit else "新建任务")
        panel_title.setStyleSheet("font-weight: bold;")
        top_bar.addWidget(panel_title, 1)

        close_btn = TransparentToolButton(FluentIcon.CLOSE)
        close_btn.setFixedSize(28, 28)
        close_btn.clicked.connect(self.reject)
        top_bar.addWidget(close_btn)

        layout.addLayout(top_bar)

        # 分隔线
        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet(f"background-color: {'#444' if isDarkTheme() else '#DDD'};")
        layout.addWidget(divider)

        # 标题输入
        self.title_edit = LineEdit()
        self.title_edit.setPlaceholderText("输入任务标题...")
        self.title_edit.setClearButtonEnabled(True)
        self.title_edit.setMaxLength(100)
        layout.addWidget(self.title_edit)

        # 子任务不需要以下字段
        if self._pid is None:
            # 描述输入
            self.desc_edit = QTextEdit()
            self.desc_edit.setAcceptRichText(True)
            self.desc_edit.setPlaceholderText("添加详细描述（可选）...")
            self.desc_edit.setMinimumHeight(72)
            self.desc_edit.setMaximumHeight(110)
            layout.addWidget(self.desc_edit)

            # 优先级 + 分类选择
            row1 = QHBoxLayout()
            row1.setSpacing(20)

            self.priority_combo = ComboBox()
            self.priority_combo.setFixedWidth(205)
            self.priority_combo.addItem("选择优先级", userData=None)
            for val, name in PRIORITY_MAP.items():
                self.priority_combo.addItem(name, userData=val)
            self.priority_combo.setCurrentIndex(0)
            row1.addWidget(self.priority_combo)

            self.category_combo = ComboBox()
            self.category_combo.setFixedWidth(205)
            self.category_combo.addItem("无分类", userData=None)
            row1.addWidget(self.category_combo)
            row1.addStretch()
            layout.addLayout(row1)

            # 截止日期 + 自动延期
            due_row = QHBoxLayout()
            due_row.setSpacing(20)

            self.due_container = QWidget()
            self.due_container.setFixedWidth(240)
            due_container_layout = QHBoxLayout(self.due_container)
            due_container_layout.setContentsMargins(0, 0, 0, 0)
            due_container_layout.setSpacing(0)

            self.due_picker = CalendarPicker()
            self.due_picker.setFixedWidth(205)
            if not self._is_edit:
                self.due_picker.setDate(QDate.currentDate())
            else:
                try:
                    self.due_picker.setText("截止日期")
                except Exception:
                    pass
            due_container_layout.addWidget(self.due_picker)

            dark = isDarkTheme()
            btn_bg = "rgba(255,255,255,1)" if dark else "rgba(0,0,0,0.04)"
            btn_hover = "rgba(255,255,255,0.5)" if dark else "rgba(0,0,0,0.08)"
            btn_border = "#555" if dark else "#ccc"
            icon_color = "#aaa" if dark else "#888"

            self._clear_due_btn = TransparentToolButton(FluentIcon.CLOSE)
            self._clear_due_btn.setFixedSize(30, 30)
            self._clear_due_btn.setIconSize(QSize(12, 12))
            self._clear_due_btn.setToolTip("清除截止日期")
            self._clear_due_btn.clicked.connect(self._on_clear_due_date)
            self._clear_due_btn.setStyleSheet(f"""
                TransparentToolButton {{
                    border: 1px solid {btn_border};
                    border-radius: 6px;
                    color: {icon_color};
                }}
                TransparentToolButton:hover {{
                    background: {btn_hover};
                }}
            """)
            due_container_layout.addWidget(self._clear_due_btn)

            due_row.addWidget(self.due_container)

            self.auto_postpone_cb = CheckBox("自动延期")
            self.auto_postpone_cb.setToolTip("开启后，过期未完成的任务会自动延期到当天")
            due_row.addWidget(self.auto_postpone_cb)
            due_row.addStretch()
            layout.addLayout(due_row)

            # 重复设置行
            recurrence_row = QHBoxLayout()
            recurrence_row.setSpacing(10)

            self.recurrence_combo = ComboBox()
            self.recurrence_combo.setFixedWidth(110)
            self.recurrence_combo.addItem("不重复", userData=None)
            for key, label in RECURRENCE_TYPES.items():
                self.recurrence_combo.addItem(label, userData=key)
            recurrence_row.addWidget(self.recurrence_combo)

            self.recurrence_interval_spin = CompactSpinBox()
            self.recurrence_interval_spin.setRange(1, 99)
            self.recurrence_interval_spin.setValue(1)
            self.recurrence_interval_spin.setFixedWidth(80)
            self.recurrence_interval_spin.setVisible(False)
            self.recurrence_interval_spin.setToolTip("重复间隔")
            recurrence_row.addWidget(self.recurrence_interval_spin)

            self.recurrence_day_spin = CompactSpinBox()
            self.recurrence_day_spin.setRange(1, 7)
            self.recurrence_day_spin.setValue(1)
            self.recurrence_day_spin.setFixedWidth(80)
            self.recurrence_day_spin.setVisible(False)
            recurrence_row.addWidget(self.recurrence_day_spin)

            self.recurrence_end_picker = CalendarPicker()
            self.recurrence_end_picker.setFixedWidth(130)
            self.recurrence_end_picker.setToolTip("选择日期")
            self.recurrence_end_picker.setVisible(False)
            try:
                self.recurrence_end_picker.setText("结束日期")
            except Exception:
                pass
            recurrence_row.addWidget(self.recurrence_end_picker)

            recurrence_row.addStretch()
            layout.addLayout(recurrence_row)

            self.recurrence_combo.currentIndexChanged.connect(self._on_recurrence_changed)

            # 重复实例只读标签（默认隐藏）
            self.recurrence_instance_label = BodyLabel("🔁 此任务属于重复系列")
            self.recurrence_instance_label.setVisible(False)
            layout.addWidget(self.recurrence_instance_label)

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
            self.drop_area.setFixedHeight(36)
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

        layout.addStretch()

        # 按钮区
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        if self._pid is None and self._is_edit:
            self.open_folder_btn = PushButton(FluentIcon.FOLDER, "打开文件夹")
            self.open_folder_btn.clicked.connect(self._on_open_folder)
            btn_layout.addWidget(self.open_folder_btn)

        btn_layout.addStretch()

        self.cancel_btn = PushButton("取消")
        self.cancel_btn.setFixedWidth(100)
        self.cancel_btn.clicked.connect(self.reject)

        self.save_btn = PrimaryPushButton("保存")
        self.save_btn.setFixedWidth(100)
        self.save_btn.setIcon(FluentIcon.SAVE)
        self.save_btn.clicked.connect(self._on_save)

        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addWidget(self.save_btn)
        layout.addLayout(btn_layout)

    def _connect_signals(self):
        self.title_edit.returnPressed.connect(self._on_save)
        if hasattr(self, 'desc_edit'):
            self.desc_edit.textChanged.connect(self._on_desc_changed)

    def _on_desc_changed(self):
        text = self.desc_edit.toPlainText()
        if len(text) > 1000:
            cursor = self.desc_edit.textCursor()
            cursor.movePosition(cursor.MoveOperation.End)
            cursor.deletePreviousChar()

    def _on_recurrence_changed(self, index: int):
        show = index > 0
        self.recurrence_end_picker.setVisible(show)

        recurrence_type = self.recurrence_combo.currentData()
        is_weekly = recurrence_type == "weekly"
        is_monthly = recurrence_type == "monthly"

        self.recurrence_interval_spin.setVisible(show)
        self.recurrence_day_spin.setVisible(show and (is_weekly or is_monthly))

        if is_weekly:
            self.recurrence_day_spin.setRange(1, 7)
            self.recurrence_day_spin.setPrefix("周 ")
            self.recurrence_day_spin.setSuffix("")
            self.recurrence_day_spin.setValue(1)
        elif is_monthly:
            self.recurrence_day_spin.setRange(1, 31)
            self.recurrence_day_spin.setPrefix("")
            self.recurrence_day_spin.setSuffix(" 号")
            self.recurrence_day_spin.setValue(1)

        self.due_container.setVisible(not show)
        self.auto_postpone_cb.setVisible(not show)

    def _on_clear_due_date(self):
        self.due_picker.setDate(QDate())
        try:
            self.due_picker.setText("截止日期")
        except Exception:
            pass

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
        files, _ = QFileDialog.getOpenFileNames(
            self, "选择文件", "", "所有文件 (*.*)"
        )
        if files:
            for f in files:
                self._add_file(f)

    def _add_file(self, file_path: str):
        if file_path not in self._temp_files:
            self._temp_files.append(file_path)
            self._update_file_list()

    def _update_file_list(self):
        count = len(self._temp_files)
        if count == 0:
            self.drop_area.setText("📎 拖放文件到此处，或点击选择文件")
        else:
            self.drop_area.setText(f"📎 待上传 {count} 个文件")

    def _load_files(self):
        if not self.todo_data:
            return
        todo_id = self.todo_data.get("id")
        if not todo_id or not hasattr(self, 'drop_area'):
            return
        count = self._file_service.get_file_count(todo_id)
        template_id = self.todo_data.get("recurrence_template_id")
        if template_id and self.todo_data.get("recurrence_type"):
            count += self._file_service.get_file_count(template_id)
        if count > 0:
            self.drop_area.setText(f"📎 已关联 {count} 个文件")

    def _on_open_folder(self):
        if self.todo_data and self.todo_data.get("id"):
            self._file_service.open_folder(self.todo_data["id"])
            template_id = self.todo_data.get("recurrence_template_id")
            if template_id and self.todo_data.get("recurrence_type"):
                self._file_service.open_folder(template_id)

    def _save_files(self, todo_id: int):
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

        if hasattr(self, 'desc_edit'):
            desc = data.get("description", "")
            if desc:
                self.desc_edit.setMarkdown(desc)

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

            self.auto_postpone_cb.setChecked(data.get("auto_postpone", False))

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

            # 重复设置
            is_instance = bool(data.get("recurrence_template_id")) and bool(data.get("recurrence_type"))
            if is_instance and self._edit_mode == "this_and_future":
                self.due_container.setVisible(False)
                self.auto_postpone_cb.setVisible(False)
                self.recurrence_instance_label.setVisible(False)
                if self._template_data:
                    tpl = self._template_data
                    r_type = tpl.get("recurrence_type")
                    if r_type:
                        for i in range(self.recurrence_combo.count()):
                            if self.recurrence_combo.itemData(i) == r_type:
                                self.recurrence_combo.setCurrentIndex(i)
                                break
                        self.recurrence_interval_spin.setValue(tpl.get("recurrence_interval", 1))
                        r_day = tpl.get("recurrence_day")
                        if r_day:
                            self.recurrence_day_spin.setValue(r_day)
                        end_str = tpl.get("recurrence_end_date")
                        if end_str:
                            try:
                                from PySide6.QtCore import QDate
                                if isinstance(end_str, str):
                                    pyd = date.fromisoformat(end_str)
                                    self.recurrence_end_picker.setDate(QDate(pyd.year, pyd.month, pyd.day))
                                else:
                                    self.recurrence_end_picker.setDate(QDate(end_str.year, end_str.month, end_str.day))
                            except Exception:
                                pass
            elif is_instance:
                self.due_container.setVisible(False)
                self.auto_postpone_cb.setVisible(False)
                self.recurrence_combo.setVisible(False)
                self.recurrence_interval_spin.setVisible(False)
                self.recurrence_day_spin.setVisible(False)
                self.recurrence_end_picker.setVisible(False)
                self.recurrence_instance_label.setVisible(True)
            else:
                recurrence_type = data.get("recurrence_type")
                if recurrence_type:
                    for i in range(self.recurrence_combo.count()):
                        if self.recurrence_combo.itemData(i) == recurrence_type:
                            self.recurrence_combo.setCurrentIndex(i)
                            break
                    self.recurrence_interval_spin.setValue(data.get("recurrence_interval", 1))
                    recurrence_day = data.get("recurrence_day")
                    if recurrence_day:
                        self.recurrence_day_spin.setValue(recurrence_day)
                    end_str = data.get("recurrence_end_date")
                    if end_str:
                        try:
                            from PySide6.QtCore import QDate
                            if isinstance(end_str, str):
                                pyd = date.fromisoformat(end_str)
                                self.recurrence_end_picker.setDate(QDate(pyd.year, pyd.month, pyd.day))
                            else:
                                self.recurrence_end_picker.setDate(QDate(end_str.year, end_str.month, end_str.day))
                        except Exception:
                            pass

    def _on_save(self):
        title = self.title_edit.text().strip()
        if not title:
            self.title_edit.setStyleSheet(
                "LineEdit { border: 2px solid #D13438; border-radius: 6px; }"
            )
            return

        data = {
            "title": title,
            "temp_files": self._temp_files,
        }

        # 子任务只传 title
        if self._pid is None:
            data["description"] = self.desc_edit.toMarkdown().strip()

            due_date = None
            if hasattr(self, 'due_picker'):
                try:
                    qdate = self.due_picker.date
                    if qdate is not None and hasattr(qdate, 'isValid') and qdate.isValid():
                        due_date = date(qdate.year(), qdate.month(), qdate.day())
                except Exception:
                    pass
            data["due_date"] = due_date

            priority_val = getattr(self, 'priority_combo', None)
            if priority_val:
                data["priority"] = priority_val.currentData() or 0
            else:
                data["priority"] = 0

            data["color_tag"] = self._selected_color
            data["auto_postpone"] = self.auto_postpone_cb.isChecked() if hasattr(self, 'auto_postpone_cb') else False
            data["category_id"] = self.category_combo.currentData() if hasattr(self, 'category_combo') else None

            # 重复设置（实例编辑时根据 edit_mode 处理）
            is_instance = self._is_edit and self.todo_data and self.todo_data.get("recurrence_template_id") and self.todo_data.get("recurrence_type")
            if is_instance and self._edit_mode == "this_and_future":
                data["edit_mode"] = "this_and_future"
                data["recurrence_type"] = self.recurrence_combo.currentData() if hasattr(self, 'recurrence_combo') else None
                data["recurrence_interval"] = self.recurrence_interval_spin.value() if hasattr(self, 'recurrence_interval_spin') else 1
                recurrence_type = data.get("recurrence_type")
                if recurrence_type in ("weekly", "monthly") and hasattr(self, 'recurrence_day_spin'):
                    data["recurrence_day"] = self.recurrence_day_spin.value()
                else:
                    data["recurrence_day"] = None
                recurrence_end = None
                if hasattr(self, 'recurrence_end_picker') and data.get("recurrence_type"):
                    try:
                        qdate = self.recurrence_end_picker.date
                        if qdate is not None and hasattr(qdate, 'isValid') and qdate.isValid():
                            recurrence_end = date(qdate.year(), qdate.month(), qdate.day())
                    except Exception:
                        pass
                data["recurrence_end_date"] = recurrence_end
            elif is_instance:
                data["edit_mode"] = "this"
            elif not is_instance:
                data["recurrence_type"] = self.recurrence_combo.currentData() if hasattr(self, 'recurrence_combo') else None
                data["recurrence_interval"] = self.recurrence_interval_spin.value() if hasattr(self, 'recurrence_interval_spin') else 1
                recurrence_type = data.get("recurrence_type")
                if recurrence_type in ("weekly", "monthly") and hasattr(self, 'recurrence_day_spin'):
                    data["recurrence_day"] = self.recurrence_day_spin.value()
                else:
                    data["recurrence_day"] = None

                if recurrence_type:
                    data["auto_postpone"] = False
                recurrence_end = None
                if hasattr(self, 'recurrence_end_picker') and data.get("recurrence_type"):
                    try:
                        qdate = self.recurrence_end_picker.date
                        if qdate is not None and hasattr(qdate, 'isValid') and qdate.isValid():
                            recurrence_end = date(qdate.year(), qdate.month(), qdate.day())
                    except Exception:
                        pass
                data["recurrence_end_date"] = recurrence_end
        else:
            data["pid"] = self._pid

        if self._is_edit:
            data["id"] = self.todo_data["id"]

        self.todo_saved.emit(data)
        self.close()

    def _load_categories(self):
        if hasattr(self, 'category_combo'):
            self.category_combo.clear()
            self.category_combo.addItem("无分类", userData=None)
            categories = self._category_service.get_all()
            for cat in categories:
                self.category_combo.addItem(cat.name, userData=cat.id)

    # ---- 拖放支持 ----
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() and hasattr(self, 'drop_area'):
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
        if hasattr(self, 'drop_area'):
            self.drop_area.setStyleSheet("""
                QLabel {
                    border: 2px dashed #888;
                    border-radius: 6px;
                    color: #888;
                }
            """)

    def dropEvent(self, event):
        if hasattr(self, 'drop_area'):
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
        screen = self.screen().availableGeometry()
        x = screen.x() + (screen.width() - self.width()) // 2
        y = screen.y() + (screen.height() - self.height()) // 2
        self.move(x, y)
        self.title_edit.setFocus()
        self.title_edit.setStyleSheet("")
        if isDarkTheme():
            self.setStyleSheet("""
                QDialog {
                    background-color: rgb(43, 43, 43);
                }
                SubtitleLabel { color: #EEE; }
                QLabel { color: #DDD; }
                LineEdit { background-color: rgb(59, 59, 59); color: #EEE; border: 1px solid rgb(80,80,80); border-radius: 6px; }
                TextEdit { background-color: rgb(59, 59, 59); color: #EEE; border: 1px solid rgb(80,80,80); border-radius: 6px; }
                QTextEdit { background-color: rgb(59, 59, 59); color: #EEE; border: 1px solid rgb(80,80,80); border-radius: 6px; }
                QTextBrowser { background-color: rgb(59, 59, 59); color: #EEE; border: 1px solid rgb(80,80,80); border-radius: 6px; }
                CheckBox { color: #DDD; }
                CompactSpinBox { background-color: rgb(59, 59, 59); color: #EEE; border: 1px solid rgb(80,80,80); border-radius: 6px; }
            """)
        else:
            self.setStyleSheet("""
                QDialog {
                    background-color: rgb(249, 249, 249);
                }
                SubtitleLabel { color: #111; }
                QLabel { color: #333; }
                LineEdit { background-color: #FFF; color: #333; }
                TextEdit { background-color: #FFF; color: #333; }
                QTextEdit { background-color: #FFF; color: #333; border: 1px solid #DDD; border-radius: 6px; }
                QTextBrowser { background-color: #FFF; color: #333; border: 1px solid #DDD; border-radius: 6px; }
                CheckBox { color: #333; }
                CompactSpinBox { background-color: #FFF; color: #333; }
            """)
