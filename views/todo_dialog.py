"""新建/编辑待办对话框"""
from __future__ import annotations

from datetime import date, timedelta

from PySide6.QtCore import Signal, Qt, QDate, QSize, QPoint, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QPainter, QColor, QPainterPath
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFileDialog, QFrame, QWidget, QSizePolicy, QGraphicsOpacityEffect, QApplication
)
from qfluentwidgets import (
    LineEdit, ComboBox, FastCalendarPicker,
    PrimaryPushButton, PushButton, SubtitleLabel, CheckBox,
    FluentIcon, isDarkTheme, BodyLabel, TransparentToolButton, CompactSpinBox,
    InfoBar, InfoBarPosition, CaptionLabel
)

from config.constants import PRIORITY_MAP, PRIORITY_NONE, TODO_COLORS, RECURRENCE_TYPES, WEEKDAY_LABELS, TASK_TYPE_MAP, parse_recurrence_day
from config.settings import settings
from services.category_service import CategoryService
from services.file_service import FileService
from services.holiday_service import holiday_service
from views.markdown_editor import MarkdownEditor


class TodoDialog(QDialog):
    """新建/编辑待办对话框"""

    todo_saved = Signal(dict)

    def __init__(self, todo_data: dict = None, parent=None, pid: int = None,
                 edit_mode: str = None, template_data: dict = None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.todo_data = todo_data
        self._is_edit = todo_data is not None
        self._edit_mode = edit_mode
        self._template_data = template_data
        self._pid = pid if pid is not None else (todo_data.get("pid") if todo_data else None)
        self._selected_color = None
        self._category_service = CategoryService()
        self._file_service = FileService()
        self._temp_files = []
        self._is_widescreen = (settings.dialog_mode == "widescreen")
        self._task_mode = "default"  # "default" / "recurrence" / "periodic"

        if self._pid is not None:
            self.setFixedSize(400, 160)
        elif self._is_widescreen:
            self.setMinimumSize(810, 520)
        else:
            self.setMinimumSize(410, 500)

        self._setup_ui()
        self._connect_signals()
        self._load_categories()

        if self._is_edit:
            self._fill_data(todo_data)
            self._load_files()

        self.setAcceptDrops(True)
        self.setMouseTracking(True)
        self._drag_pos = None
        self._resize_edge = 0  # 0=none, 边缘标志: 1=left, 2=right, 4=top, 8=bottom
        self._resize_start_geo = None
        self._resize_start_pos = None

    _RESIZE_MARGIN = 6

    def _detect_edge(self, pos) -> int:
        """检测鼠标位置所在的边缘"""
        m = self._RESIZE_MARGIN
        edge = 0
        if pos.x() < m:
            edge |= 1  # left
        elif pos.x() > self.width() - m:
            edge |= 2  # right
        if pos.y() < m:
            edge |= 4  # top
        elif pos.y() > self.height() - m:
            edge |= 8  # bottom
        return edge

    @staticmethod
    def _edge_cursor(edge) -> Qt.CursorShape:
        """根据边缘标志返回光标形状"""
        cursor_map = {
            1: Qt.CursorShape.SizeHorCursor,
            2: Qt.CursorShape.SizeHorCursor,
            4: Qt.CursorShape.SizeVerCursor,
            8: Qt.CursorShape.SizeVerCursor,
            5: Qt.CursorShape.SizeFDiagCursor,   # top-left
            6: Qt.CursorShape.SizeBDiagCursor,   # top-right
            9: Qt.CursorShape.SizeBDiagCursor,   # bottom-left
            10: Qt.CursorShape.SizeFDiagCursor,  # bottom-right
        }
        return cursor_map.get(edge, Qt.CursorShape.ArrowCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            edge = self._detect_edge(event.position().toPoint())
            if edge:
                self._resize_edge = edge
                self._resize_start_geo = self.geometry()
                self._resize_start_pos = event.globalPosition().toPoint()
            else:
                self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton:
            if self._resize_edge:
                # 拖拽调整大小
                delta = event.globalPosition().toPoint() - self._resize_start_pos
                geo = self._resize_start_geo
                min_w = self.minimumWidth()
                min_h = self.minimumHeight()

                new_left = geo.left()
                new_top = geo.top()
                new_right = geo.right()
                new_bottom = geo.bottom()

                if self._resize_edge & 1:  # left
                    new_left = min(geo.left() + delta.x(), geo.right() - min_w)
                if self._resize_edge & 2:  # right
                    new_right = max(geo.right() + delta.x(), geo.left() + min_w)
                if self._resize_edge & 4:  # top
                    new_top = min(geo.top() + delta.y(), geo.bottom() - min_h)
                if self._resize_edge & 8:  # bottom
                    new_bottom = max(geo.bottom() + delta.y(), geo.top() + min_h)

                self.setGeometry(new_left, new_top, new_right - new_left, new_bottom - new_top)
            elif self._drag_pos is not None:
                self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()
        else:
            # 无按键时更新光标形状
            edge = self._detect_edge(event.position().toPoint())
            self.setCursor(self._edge_cursor(edge))

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        self._resize_edge = 0
        self._resize_start_geo = None
        self._resize_start_pos = None

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        dark = isDarkTheme()
        bg_color = QColor(43, 43, 43) if dark else QColor(249, 249, 249)
        border_color = QColor(60, 60, 60) if dark else QColor(210, 210, 210)
        path = QPainterPath()
        path.addRoundedRect(0.5, 0.5, self.width() - 1, self.height() - 1, 10, 10)
        painter.fillPath(path, bg_color)
        painter.setPen(border_color)
        painter.drawPath(path)
        super().paintEvent(event)

    def closeEvent(self, event):
        # 保存窗口尺寸
        settings.todo_dialog_size = (self.width(), self.height())
        if hasattr(self, '_category_service') and self._category_service:
            self._category_service.close()
        if hasattr(self, '_file_service') and self._file_service:
            self._file_service.close()
        super().closeEvent(event)

    def _setup_ui(self):
        if self._pid is not None:
            self._setup_subtask_ui()
        elif self._is_widescreen:
            self._setup_widescreen_ui()
        else:
            self._setup_default_ui()

    def _setup_subtask_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 12, 20, 16)
        layout.setSpacing(10)

        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)
        panel_title = SubtitleLabel("编辑子任务" if self._is_edit else "新建子任务")
        panel_title.setStyleSheet("font-weight: bold;")
        top_bar.addWidget(panel_title, 1)
        close_btn = TransparentToolButton(FluentIcon.CLOSE)
        close_btn.setFixedSize(28, 28)
        close_btn.clicked.connect(self.reject)
        top_bar.addWidget(close_btn)
        layout.addLayout(top_bar)

        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet(f"background-color: {'#444' if isDarkTheme() else '#DDD'};")
        layout.addWidget(divider)

        self.title_edit = LineEdit()
        self.title_edit.setPlaceholderText("输入任务标题...")
        self.title_edit.setClearButtonEnabled(True)
        self.title_edit.setMaxLength(100)
        layout.addWidget(self.title_edit)

        layout.addStretch()

        btn_layout = QHBoxLayout()
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

    def _setup_default_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 12, 20, 16)
        layout.setSpacing(10)

        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)
        panel_title = SubtitleLabel("编辑任务" if self._is_edit else "新建任务")
        panel_title.setStyleSheet("font-weight: bold;")
        top_bar.addWidget(panel_title, 1)
        self._mode_combo = self._create_mode_combo()
        top_bar.addWidget(self._mode_combo)
        close_btn = TransparentToolButton(FluentIcon.CLOSE)
        close_btn.setFixedSize(28, 28)
        close_btn.clicked.connect(self.reject)
        top_bar.addWidget(close_btn)
        layout.addLayout(top_bar)
        layout.addSpacing(6)

        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet(f"background-color: {'#444' if isDarkTheme() else '#DDD'};")
        layout.addWidget(divider)

        self.title_edit = LineEdit()
        self.title_edit.setPlaceholderText("输入任务标题（必填）")
        self.title_edit.setClearButtonEnabled(True)
        self.title_edit.setMaxLength(100)
        layout.addWidget(self.title_edit)

        if self._pid is None:
            self.desc_edit = MarkdownEditor()
            self.desc_edit.setPlaceholderText("添加详细描述（支持Markdown语法）...")
            self.desc_edit.setMinimumHeight(72)
            self.desc_edit.setMaximumHeight(110)
            layout.addWidget(self.desc_edit)

        self._create_meta_widgets()
        self._layout_meta_default(layout)

        layout.addStretch()
        self._create_buttons(layout)

    def _setup_widescreen_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 12, 20, 16)
        layout.setSpacing(0)

        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)
        panel_title = SubtitleLabel("编辑任务" if self._is_edit else "新建任务")
        panel_title.setStyleSheet("font-weight: bold;")
        top_bar.addWidget(panel_title, 1)
        self._mode_combo = self._create_mode_combo()
        top_bar.addWidget(self._mode_combo)
        close_btn = TransparentToolButton(FluentIcon.CLOSE)
        close_btn.setFixedSize(28, 28)
        close_btn.clicked.connect(self.reject)
        top_bar.addWidget(close_btn)
        layout.addLayout(top_bar)
        layout.addSpacing(6)

        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet(f"background-color: {'#444' if isDarkTheme() else '#DDD'};")
        layout.addWidget(divider)

        content_layout = QHBoxLayout()
        content_layout.setSpacing(16)
        content_layout.setContentsMargins(0, 10, 0, 0)

        left_panel = QVBoxLayout()
        left_panel.setSpacing(8)

        self.title_edit = LineEdit()
        self.title_edit.setPlaceholderText("输入任务标题（必填）")
        self.title_edit.setClearButtonEnabled(True)
        self.title_edit.setMaxLength(100)
        left_panel.addWidget(self.title_edit)

        self.desc_edit = MarkdownEditor()
        self.desc_edit.setPlaceholderText("添加详细描述（支持Markdown语法）...")
        self.desc_edit.setMinimumHeight(200)
        left_panel.addWidget(self.desc_edit, 1)

        content_layout.addLayout(left_panel, 3)

        right_card = QFrame()
        right_card.setObjectName("widescreenRightCard")
        right_card.setFixedWidth(250)
        right_layout = QVBoxLayout(right_card)
        right_layout.setContentsMargins(12, 10, 12, 10)
        right_layout.setSpacing(6)

        self._create_meta_widgets()
        self._layout_meta_widescreen(right_layout)

        content_layout.addWidget(right_card)
        layout.addLayout(content_layout, 1)
        layout.addSpacing(12)

        self._create_buttons(layout)

    def _create_meta_widgets(self):
        self.priority_combo = ComboBox()
        self.priority_combo.addItem("选择优先级", userData=PRIORITY_NONE)
        for val, name in PRIORITY_MAP.items():
            if val == PRIORITY_NONE:
                continue
            self.priority_combo.addItem(name, userData=val)
        self.priority_combo.setCurrentIndex(0)

        self.category_combo = ComboBox()
        self.category_combo.addItem("无分类", userData=None)

        self.due_container = QWidget()
        due_container_layout = QHBoxLayout(self.due_container)
        due_container_layout.setContentsMargins(0, 0, 0, 0)
        due_container_layout.setSpacing(0)

        self.due_picker = FastCalendarPicker()
        self.due_picker.setToolTip("选择截止日期")
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

        self.auto_postpone_cb = CheckBox("自动延期")
        self.auto_postpone_cb.setToolTip("开启后，过期未完成的任务会自动延期到当天")

        self.recurrence_combo = ComboBox()
        self.recurrence_combo.setToolTip("任务重复设置")
        self.recurrence_combo.addItem("不重复", userData=None)
        # 检查节日数据是否可用，决定是否显示"工作日"选项
        self._workday_available = self._check_workday_available()
        for key, label in RECURRENCE_TYPES.items():
            if key == "workday" and not self._workday_available:
                continue
            self.recurrence_combo.addItem(label, userData=key)

        self.recurrence_interval_spin = CompactSpinBox()
        self.recurrence_interval_spin.setRange(1, 99)
        self.recurrence_interval_spin.setValue(1)
        self.recurrence_interval_spin.setVisible(False)
        self.recurrence_interval_spin.setToolTip("重复间隔")

        # 周重复：星期按钮
        self.weekday_container = QWidget()
        weekday_layout = QHBoxLayout(self.weekday_container)
        weekday_layout.setContentsMargins(0, 0, 0, 0)
        weekday_layout.setSpacing(4)
        self.weekday_btns: dict[int, QPushButton] = {}
        for day_num, day_label in WEEKDAY_LABELS.items():
            btn = QPushButton(day_label[-1])
            btn.setFixedSize(26, 26)
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setProperty("day_num", day_num)
            weekday_layout.addWidget(btn)
            self.weekday_btns[day_num] = btn
        self._apply_weekday_btn_style()
        self.weekday_container.setVisible(False)

        # 月重复：日期选择
        self.recurrence_day_spin = CompactSpinBox()
        self.recurrence_day_spin.setRange(1, 31)
        self.recurrence_day_spin.setValue(1)
        self.recurrence_day_spin.setVisible(False)
        self.recurrence_day_spin.setSuffix(" 号")

        self.recurrence_start_picker = FastCalendarPicker()
        self.recurrence_start_picker.setToolTip("开始日期（不早于今日）")
        self.recurrence_start_picker.setVisible(False)
        try:
            self.recurrence_start_picker.setText("开始日期")
        except Exception:
            pass

        self.recurrence_end_picker = FastCalendarPicker()
        self.recurrence_end_picker.setToolTip("结束日期（不早于今日，不超过一年）")
        self.recurrence_end_picker.setVisible(False)
        try:
            self.recurrence_end_picker.setText("结束日期")
        except Exception:
            pass

        self.recurrence_instance_label = BodyLabel("🔁 此任务属于重复系列")
        self.recurrence_instance_label.setVisible(False)

        self.color_buttons = []
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
            self.color_buttons.append(btn)

        self.drop_area = QLabel("📎 点击选择 或拖拽文件到此")
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

        self.recurrence_combo.currentIndexChanged.connect(self._on_recurrence_changed)

    def _create_mode_combo(self) -> ComboBox:
        """创建任务模式下拉框（默认任务 / 重复任务 / 周期任务）"""
        combo = ComboBox()
        combo.addItem("默认任务", userData="default")
        combo.addItem("重复任务", userData="recurrence")
        combo.addItem("周期任务", userData="periodic")
        combo.setCurrentIndex(0)
        combo.setFixedWidth(110)
        combo.currentIndexChanged.connect(self._on_mode_combo_changed)
        return combo

    def _on_mode_combo_changed(self, index: int):
        """下拉框切换时更新任务模式"""
        mode = self._mode_combo.currentData()
        if mode:
            self._on_task_mode_changed(mode)

    def _on_task_mode_changed(self, mode: str):
        """切换任务模式（默认任务 / 重复任务 / 周期任务）"""
        if self._task_mode == mode:
            return
        self._task_mode = mode
        is_recurrence = mode == "recurrence"
        is_periodic = mode == "periodic"

        # 同步下拉框选中状态
        for i in range(self._mode_combo.count()):
            if self._mode_combo.itemData(i) == mode:
                self._mode_combo.setCurrentIndex(i)
                break

        # 显示/隐藏截止日期区域
        self._due_section.setVisible(not is_recurrence and not is_periodic)

        # 显示/隐藏重复任务区域
        self._recurrence_section.setVisible(is_recurrence)

        # 显示/隐藏周期任务区域
        if hasattr(self, '_periodic_section'):
            self._periodic_section.setVisible(is_periodic)

        if is_recurrence:
            if self.recurrence_combo.currentData() is None and self.recurrence_combo.count() > 1:
                self.recurrence_combo.setCurrentIndex(1)
            else:
                self._on_recurrence_changed(self.recurrence_combo.currentIndex())
        elif is_periodic:
            self.auto_postpone_cb.setChecked(False)
        else:
            self.recurrence_combo.setCurrentIndex(0)

    def _layout_meta_default(self, layout):
        row1 = QHBoxLayout()
        row1.setSpacing(10)
        self.priority_combo.setFixedWidth(180)
        row1.addWidget(self.priority_combo)
        self.category_combo.setFixedWidth(180)
        row1.addWidget(self.category_combo)
        row1.addStretch()
        layout.addLayout(row1)

        # 截止日期区域
        self._due_section = QWidget()
        due_section_layout = QVBoxLayout(self._due_section)
        due_section_layout.setContentsMargins(0, 0, 0, 0)
        due_section_layout.setSpacing(0)

        due_row = QHBoxLayout()
        due_row.setSpacing(10)
        self.due_container.setFixedWidth(180)
        self.due_picker.setFixedWidth(150)
        due_row.addWidget(self.due_container)
        due_row.addWidget(self.auto_postpone_cb)
        due_row.addStretch()
        due_section_layout.addLayout(due_row)

        layout.addWidget(self._due_section)

        # 重复任务区域
        self._recurrence_section = QWidget()
        rec_section_layout = QVBoxLayout(self._recurrence_section)
        rec_section_layout.setContentsMargins(0, 0, 0, 0)
        rec_section_layout.setSpacing(8)

        recurrence_row = QHBoxLayout()
        recurrence_row.setSpacing(10)
        self.recurrence_combo.setFixedWidth(180)
        recurrence_row.addWidget(self.recurrence_combo)
        self.recurrence_interval_spin.setFixedWidth(85)
        recurrence_row.addWidget(self.recurrence_interval_spin)
        self.recurrence_day_spin.setFixedWidth(85)
        recurrence_row.addWidget(self.recurrence_day_spin)
        recurrence_row.addStretch()
        rec_section_layout.addLayout(recurrence_row)

        # 周几选择行
        self.recurrence_day_row = QHBoxLayout()
        self.recurrence_day_row.setSpacing(10)
        self.recurrence_day_row.addWidget(self.weekday_container)
        self.recurrence_day_row.addStretch()
        rec_section_layout.addLayout(self.recurrence_day_row)

        recurrence_date_row = QHBoxLayout()
        recurrence_date_row.setSpacing(10)
        self.recurrence_start_picker.setFixedWidth(180)
        recurrence_date_row.addWidget(self.recurrence_start_picker)
        self.recurrence_end_picker.setFixedWidth(180)
        recurrence_date_row.addWidget(self.recurrence_end_picker)
        recurrence_date_row.addStretch()
        rec_section_layout.addLayout(recurrence_date_row)

        rec_section_layout.addWidget(self.recurrence_instance_label)

        layout.addWidget(self._recurrence_section)

        # 默认隐藏重复区域
        self._recurrence_section.setVisible(False)

        # 周期任务区域
        self._periodic_section = QWidget()
        periodic_section_layout = QVBoxLayout(self._periodic_section)
        periodic_section_layout.setContentsMargins(0, 0, 0, 0)
        periodic_section_layout.setSpacing(8)

        self.periodic_start_picker = FastCalendarPicker()
        self.periodic_start_picker.setToolTip("生效开始日期（必填）")
        self.periodic_start_picker.setFixedWidth(180)
        try:
            self.periodic_start_picker.setText("开始日期")
        except Exception:
            pass

        self.periodic_end_picker = FastCalendarPicker()
        self.periodic_end_picker.setToolTip("生效结束日期（必填）")
        self.periodic_end_picker.setFixedWidth(180)
        try:
            self.periodic_end_picker.setText("结束日期")
        except Exception:
            pass

        periodic_date_row = QHBoxLayout()
        periodic_date_row.setSpacing(10)
        periodic_date_row.addWidget(self.periodic_start_picker)
        periodic_date_row.addWidget(self.periodic_end_picker)
        periodic_date_row.addStretch()
        periodic_section_layout.addLayout(periodic_date_row)

        layout.addWidget(self._periodic_section)

        # 默认隐藏周期区域
        self._periodic_section.setVisible(False)

        color_row = QHBoxLayout()
        color_row.setSpacing(8)
        for btn in self.color_buttons:
            color_row.addWidget(btn)
        color_row.addStretch()
        layout.addLayout(color_row)

        layout.addWidget(self.drop_area)

    def _layout_meta_widescreen(self, layout):
        lbl_style = "color: #888; font-size: 11px; font-weight: bold;"

        priority_label = CaptionLabel("优先级")
        priority_label.setStyleSheet(lbl_style)
        layout.addWidget(priority_label)
        layout.addWidget(self.priority_combo)

        category_label = CaptionLabel("分类")
        category_label.setStyleSheet(lbl_style)
        layout.addWidget(category_label)
        layout.addWidget(self.category_combo)

        # 截止日期区域
        self._due_section = QWidget()
        due_section_layout = QVBoxLayout(self._due_section)
        due_section_layout.setContentsMargins(0, 0, 0, 0)
        due_section_layout.setSpacing(6)

        self.due_label = CaptionLabel("截止日期")
        self.due_label.setStyleSheet(lbl_style)
        due_section_layout.addWidget(self.due_label)
        due_section_layout.addWidget(self.due_container)
        due_section_layout.addWidget(self.auto_postpone_cb)

        sep1 = QFrame()
        sep1.setFixedHeight(1)
        sep1.setStyleSheet(f"background-color: {'#444' if isDarkTheme() else '#DDD'};")
        due_section_layout.addWidget(sep1)

        layout.addWidget(self._due_section)

        # 重复任务区域
        self._recurrence_section = QWidget()
        rec_section_layout = QVBoxLayout(self._recurrence_section)
        rec_section_layout.setContentsMargins(0, 0, 0, 0)
        rec_section_layout.setSpacing(6)

        recurrence_label = CaptionLabel("重复")
        recurrence_label.setStyleSheet(lbl_style)
        rec_section_layout.addWidget(recurrence_label)
        rec_section_layout.addWidget(self.recurrence_combo)
        recurrence_spin_row = QHBoxLayout()
        recurrence_spin_row.setSpacing(6)
        self.recurrence_interval_spin.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        recurrence_spin_row.addWidget(self.recurrence_interval_spin, 1)
        self.recurrence_day_spin.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        recurrence_spin_row.addWidget(self.recurrence_day_spin, 1)
        rec_section_layout.addLayout(recurrence_spin_row)
        rec_section_layout.addWidget(self.weekday_container)
        self.recurrence_start_picker.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        rec_section_layout.addWidget(self.recurrence_start_picker)
        self.recurrence_end_picker.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        rec_section_layout.addWidget(self.recurrence_end_picker)
        rec_section_layout.addWidget(self.recurrence_instance_label)

        sep2 = QFrame()
        sep2.setFixedHeight(1)
        sep2.setStyleSheet(f"background-color: {'#444' if isDarkTheme() else '#DDD'};")
        rec_section_layout.addWidget(sep2)

        layout.addWidget(self._recurrence_section)

        # 默认隐藏重复区域
        self._recurrence_section.setVisible(False)

        # 周期任务区域
        self._periodic_section = QWidget()
        periodic_section_layout = QVBoxLayout(self._periodic_section)
        periodic_section_layout.setContentsMargins(0, 0, 0, 0)
        periodic_section_layout.setSpacing(6)

        periodic_label = CaptionLabel("任务周期")
        periodic_label.setStyleSheet(lbl_style)
        periodic_section_layout.addWidget(periodic_label)
        self.periodic_start_picker = FastCalendarPicker()
        self.periodic_start_picker.setToolTip("周期开始日期（必填）")
        self.periodic_start_picker.setText("开始日期")
        self.periodic_start_picker.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        periodic_section_layout.addWidget(self.periodic_start_picker)
        self.periodic_end_picker = FastCalendarPicker()
        self.periodic_end_picker.setToolTip("周期结束日期（必填）")
        self.periodic_end_picker.setText("结束日期")
        self.periodic_end_picker.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        periodic_section_layout.addWidget(self.periodic_end_picker)

        sep_p = QFrame()
        sep_p.setFixedHeight(1)
        sep_p.setStyleSheet(f"background-color: {'#444' if isDarkTheme() else '#DDD'};")
        periodic_section_layout.addWidget(sep_p)

        layout.addWidget(self._periodic_section)

        # 默认隐藏周期区域
        self._periodic_section.setVisible(False)

        color_label = CaptionLabel("颜色标签")
        color_label.setStyleSheet(lbl_style)
        layout.addWidget(color_label)
        color_row = QHBoxLayout()
        color_row.setSpacing(6)
        for btn in self.color_buttons:
            btn.setFixedSize(20, 20)
            color_row.addWidget(btn)
        color_row.addStretch()
        layout.addLayout(color_row)

        sep3 = QFrame()
        sep3.setFixedHeight(1)
        sep3.setStyleSheet(f"background-color: {'#444' if isDarkTheme() else '#DDD'};")
        layout.addWidget(sep3)

        layout.addWidget(self.drop_area)
        layout.addStretch()

    def _create_buttons(self, layout):
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
        if hasattr(self, 'desc_edit') and self._pid is None:
            self.desc_edit.textChanged.connect(self._on_desc_changed)

    def _on_desc_changed(self):
        text = self.desc_edit.toPlainText()
        if len(text) > 1000:
            cursor = self.desc_edit.textCursor()
            cursor.movePosition(cursor.MoveOperation.End)
            cursor.deletePreviousChar()

    def _check_workday_available(self) -> bool:
        """检查节日数据是否可用，用于决定是否显示"工作日"选项"""
        if settings.holiday_source == "none":
            return False
        from datetime import date as pydate
        today = pydate.today()
        holiday_service.load_for_date(today)
        return holiday_service.has_data_for_year(today.year)

    def _on_recurrence_changed(self, index: int):
        show = index > 0
        self.recurrence_start_picker.setVisible(show)
        self.recurrence_end_picker.setVisible(show)

        recurrence_type = self.recurrence_combo.currentData()
        is_weekly = recurrence_type == "weekly"
        is_monthly = recurrence_type == "monthly"
        is_workday = recurrence_type == "workday"

        self.recurrence_interval_spin.setVisible(show and not is_workday)

        self.weekday_container.setVisible(show and is_weekly)
        self.recurrence_day_spin.setVisible(show and is_monthly)

        if is_monthly:
            self.recurrence_day_spin.setRange(1, 31)
            self.recurrence_day_spin.setPrefix("")
            self.recurrence_day_spin.setSuffix(" 号")
            self.recurrence_day_spin.setValue(1)

    def _on_clear_due_date(self):
        self.due_picker.setDate(QDate())
        try:
            self.due_picker.setText("截止日期")
        except Exception:
            pass

    def _get_weekday_value(self) -> str | None:
        """获取选中的星期几，返回逗号分隔字符串如 '1,3,5'，未选返回 None"""
        selected = [str(n) for n, btn in self.weekday_btns.items() if btn.isChecked()]
        return ",".join(selected) if selected else None

    def _set_weekday_value(self, value):
        """设置星期几按钮，value 可以是 int、str 或 None"""
        days = parse_recurrence_day(value)
        for n, btn in self.weekday_btns.items():
            btn.setChecked(n in days)

    def _apply_weekday_btn_style(self):
        """应用星期按钮样式"""
        dark = isDarkTheme()
        for btn in self.weekday_btns.values():
            if dark:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #3C3C3C;
                        color: #CCC;
                        border: 1px solid #555;
                        border-radius: 13px;
                        font-size: 12px;
                        font-weight: bold;
                    }
                    QPushButton:checked {
                        background-color: #0078D4;
                        color: #FFF;
                        border: 1px solid #0078D4;
                    }
                    QPushButton:hover {
                        border: 1px solid #888;
                    }
                    QPushButton:checked:hover {
                        border: 1px solid #006CBD;
                    }
                """)
            else:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #F5F5F5;
                        color: #666;
                        border: 1px solid #DDD;
                        border-radius: 13px;
                        font-size: 12px;
                        font-weight: bold;
                    }
                    QPushButton:checked {
                        background-color: #0078D4;
                        color: #FFF;
                        border: 1px solid #0078D4;
                    }
                    QPushButton:hover {
                        border: 1px solid #BBB;
                    }
                    QPushButton:checked:hover {
                        border: 1px solid #006CBD;
                    }
                """)

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
            self.drop_area.setText("📎 点击选择 或拖拽文件到此")
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

            is_instance = bool(data.get("recurrence_template_id")) and bool(data.get("recurrence_type"))
            if is_instance and self._edit_mode == "this_and_future":
                # 编辑重复系列"此次及之后"，切换到重复任务模式
                self.recurrence_instance_label.setVisible(False)
                if self._template_data:
                    tpl = self._template_data
                    r_type = tpl.get("recurrence_type")
                    if r_type:
                        # 如果是工作日类型但下拉框中没有该选项，动态添加
                        if r_type == "workday":
                            has_workday = False
                            for i in range(self.recurrence_combo.count()):
                                if self.recurrence_combo.itemData(i) == "workday":
                                    has_workday = True
                                    break
                            if not has_workday:
                                self.recurrence_combo.addItem("工作日", userData="workday")
                        for i in range(self.recurrence_combo.count()):
                            if self.recurrence_combo.itemData(i) == r_type:
                                self.recurrence_combo.setCurrentIndex(i)
                                break
                        self.recurrence_interval_spin.setValue(tpl.get("recurrence_interval", 1))
                        r_day = tpl.get("recurrence_day")
                        r_type = tpl.get("recurrence_type")
                        if r_day:
                            if r_type == "weekly":
                                self._set_weekday_value(r_day)
                            else:
                                self.recurrence_day_spin.setValue(int(parse_recurrence_day(r_day)[0]) if parse_recurrence_day(r_day) else 1)
                        start_str = tpl.get("recurrence_start_date")
                        if start_str:
                            try:
                                from PySide6.QtCore import QDate
                                if isinstance(start_str, str):
                                    pyd = date.fromisoformat(start_str)
                                    self.recurrence_start_picker.setDate(QDate(pyd.year, pyd.month, pyd.day))
                                else:
                                    self.recurrence_start_picker.setDate(QDate(start_str.year, start_str.month, start_str.day))
                            except Exception:
                                pass
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
                # 切换到重复任务模式
                self._task_mode = "recurrence"
                self._mode_combo.setCurrentIndex(1)
                self._due_section.setVisible(False)
                self._recurrence_section.setVisible(True)
            elif is_instance:
                # 编辑重复系列的单个实例，隐藏下拉框和两个区域
                self._mode_combo.setVisible(False)
                self._due_section.setVisible(False)
                self._recurrence_section.setVisible(False)
                self.recurrence_instance_label.setVisible(True)
                # 将 instance_label 移到可见区域
                if hasattr(self, '_due_section'):
                    parent_layout = self._due_section.parent().layout()
                    if parent_layout:
                        parent_layout.addWidget(self.recurrence_instance_label)
            else:
                recurrence_type = data.get("recurrence_type")
                task_type = data.get("task_type", "default")
                if task_type == "periodic":
                    # 编辑周期任务，切换到周期任务模式
                    start_str = data.get("start_date")
                    if start_str:
                        try:
                            if isinstance(start_str, str):
                                pyd = date.fromisoformat(start_str)
                                self.periodic_start_picker.setDate(QDate(pyd.year, pyd.month, pyd.day))
                            else:
                                self.periodic_start_picker.setDate(QDate(start_str.year, start_str.month, start_str.day))
                        except Exception:
                            pass
                    end_str = data.get("due_date")
                    if end_str:
                        try:
                            if isinstance(end_str, str):
                                pyd = date.fromisoformat(end_str)
                                self.periodic_end_picker.setDate(QDate(pyd.year, pyd.month, pyd.day))
                            else:
                                self.periodic_end_picker.setDate(QDate(end_str.year, end_str.month, end_str.day))
                        except Exception:
                            pass
                    self._task_mode = "periodic"
                    self._mode_combo.setCurrentIndex(2)
                    self._due_section.setVisible(False)
                    self._recurrence_section.setVisible(False)
                    self._periodic_section.setVisible(True)
                elif recurrence_type:
                    # 编辑有重复设置的任务，切换到重复任务模式
                    if recurrence_type == "workday":
                        has_workday = False
                        for i in range(self.recurrence_combo.count()):
                            if self.recurrence_combo.itemData(i) == "workday":
                                has_workday = True
                                break
                        if not has_workday:
                            self.recurrence_combo.addItem("工作日", userData="workday")
                    for i in range(self.recurrence_combo.count()):
                        if self.recurrence_combo.itemData(i) == recurrence_type:
                            self.recurrence_combo.setCurrentIndex(i)
                            break
                    self.recurrence_interval_spin.setValue(data.get("recurrence_interval", 1))
                    recurrence_day = data.get("recurrence_day")
                    if recurrence_day:
                        if recurrence_type == "weekly":
                            self._set_weekday_value(recurrence_day)
                        else:
                            self.recurrence_day_spin.setValue(int(parse_recurrence_day(recurrence_day)[0]) if parse_recurrence_day(recurrence_day) else 1)
                    start_str = data.get("recurrence_start_date")
                    if start_str:
                        try:
                            from PySide6.QtCore import QDate
                            if isinstance(start_str, str):
                                pyd = date.fromisoformat(start_str)
                                self.recurrence_start_picker.setDate(QDate(pyd.year, pyd.month, pyd.day))
                            else:
                                self.recurrence_start_picker.setDate(QDate(start_str.year, start_str.month, start_str.day))
                        except Exception:
                            pass
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
                    # 切换到重复任务模式
                    self._task_mode = "recurrence"
                    self._mode_combo.setCurrentIndex(1)
                    self._due_section.setVisible(False)
                    self._recurrence_section.setVisible(True)

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

        if self._pid is None:
            data["description"] = self.desc_edit.toPlainText().strip()

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

            is_instance = self._is_edit and self.todo_data and self.todo_data.get(
                "recurrence_template_id") and self.todo_data.get("recurrence_type")
            if is_instance and self._edit_mode == "this_and_future":
                data["edit_mode"] = "this_and_future"
                data["recurrence_type"] = self.recurrence_combo.currentData() if hasattr(self,
                                                                                         'recurrence_combo') else None
                data["recurrence_interval"] = self.recurrence_interval_spin.value() if hasattr(self,
                                                                                               'recurrence_interval_spin') else 1
                recurrence_type = data.get("recurrence_type")
                if recurrence_type == "weekly" and hasattr(self, 'weekday_btns'):
                    data["recurrence_day"] = self._get_weekday_value()
                elif recurrence_type == "monthly" and hasattr(self, 'recurrence_day_spin'):
                    data["recurrence_day"] = str(self.recurrence_day_spin.value())
                else:
                    data["recurrence_day"] = None
                recurrence_start = None
                if hasattr(self, 'recurrence_start_picker') and data.get("recurrence_type"):
                    try:
                        qdate = self.recurrence_start_picker.date
                        if qdate is not None and hasattr(qdate, 'isValid') and qdate.isValid():
                            recurrence_start = date(qdate.year(), qdate.month(), qdate.day())
                    except Exception:
                        pass
                data["recurrence_start_date"] = recurrence_start
                recurrence_end = None
                if hasattr(self, 'recurrence_end_picker') and data.get("recurrence_type"):
                    try:
                        qdate = self.recurrence_end_picker.date
                        if qdate is not None and hasattr(qdate, 'isValid') and qdate.isValid():
                            recurrence_end = date(qdate.year(), qdate.month(), qdate.day())
                    except Exception:
                        pass
                data["recurrence_end_date"] = recurrence_end
                if recurrence_type and data["due_date"] is None:
                    data["due_date"] = date.today() + timedelta(days=365)
                if recurrence_start is not None:
                    today = date.today()
                    if recurrence_start < today:
                        InfoBar.error(title="日期无效", content="开始日期不能早于今日", parent=self,
                                      position=InfoBarPosition.TOP, duration=3000)
                        return
                if recurrence_end is not None:
                    today = date.today()
                    max_end = today + timedelta(days=365)
                    if recurrence_end < today:
                        InfoBar.error(title="日期无效", content="结束日期不能早于今日", parent=self,
                                      position=InfoBarPosition.TOP, duration=3000)
                        return
                    if recurrence_end > max_end:
                        InfoBar.error(title="日期无效", content="结束日期不能超过一年", parent=self,
                                      position=InfoBarPosition.TOP, duration=3000)
                        return
                if recurrence_start and recurrence_end and recurrence_start > recurrence_end:
                    InfoBar.error(title="日期无效", content="开始日期不能晚于结束日期", parent=self,
                                  position=InfoBarPosition.TOP, duration=3000)
                    return
                # 周重复必须至少选择一天
                if recurrence_type == "weekly" and not data.get("recurrence_day"):
                    InfoBar.error(title="设置无效", content="周重复至少需要选择一天", parent=self,
                                  position=InfoBarPosition.TOP, duration=3000)
                    return
            elif is_instance:
                data["edit_mode"] = "this"
            elif not is_instance:
                # 周期任务处理
                if self._task_mode == "periodic":
                    data["task_type"] = "periodic"
                    data["auto_postpone"] = False
                    data["recurrence_type"] = None
                    data["recurrence_interval"] = 1
                    data["recurrence_day"] = None
                    data["recurrence_start_date"] = None
                    data["recurrence_end_date"] = None

                    periodic_start = None
                    if hasattr(self, 'periodic_start_picker'):
                        try:
                            qdate = self.periodic_start_picker.date
                            if qdate is not None and hasattr(qdate, 'isValid') and qdate.isValid():
                                periodic_start = date(qdate.year(), qdate.month(), qdate.day())
                        except Exception:
                            pass
                    periodic_end = None
                    if hasattr(self, 'periodic_end_picker'):
                        try:
                            qdate = self.periodic_end_picker.date
                            if qdate is not None and hasattr(qdate, 'isValid') and qdate.isValid():
                                periodic_end = date(qdate.year(), qdate.month(), qdate.day())
                        except Exception:
                            pass

                    if not periodic_start:
                        InfoBar.error(title="设置无效", content="周期任务必须选择开始日期", parent=self,
                                      position=InfoBarPosition.TOP, duration=3000)
                        return
                    if not periodic_end:
                        InfoBar.error(title="设置无效", content="周期任务必须选择结束日期", parent=self,
                                      position=InfoBarPosition.TOP, duration=3000)
                        return
                    if periodic_start > periodic_end:
                        InfoBar.error(title="日期无效", content="开始日期不能晚于结束日期", parent=self,
                                      position=InfoBarPosition.TOP, duration=3000)
                        return

                    data["start_date"] = periodic_start
                    data["due_date"] = periodic_end
                else:
                    data["recurrence_type"] = self.recurrence_combo.currentData() if hasattr(self,
                                                                                             'recurrence_combo') else None
                    data["recurrence_interval"] = self.recurrence_interval_spin.value() if hasattr(self,
                                                                                                   'recurrence_interval_spin') else 1
                    recurrence_type = data.get("recurrence_type")
                    if recurrence_type == "weekly" and hasattr(self, 'weekday_btns'):
                        data["recurrence_day"] = self._get_weekday_value()
                    elif recurrence_type == "monthly" and hasattr(self, 'recurrence_day_spin'):
                        data["recurrence_day"] = str(self.recurrence_day_spin.value())
                    else:
                        data["recurrence_day"] = None

                    if recurrence_type:
                        data["auto_postpone"] = False
                        # 重复任务未设置截止日期时，自动填充为一年后
                        if data["due_date"] is None:
                            data["due_date"] = date.today() + timedelta(days=365)
                    recurrence_start = None
                    if hasattr(self, 'recurrence_start_picker') and data.get("recurrence_type"):
                        try:
                            qdate = self.recurrence_start_picker.date
                            if qdate is not None and hasattr(qdate, 'isValid') and qdate.isValid():
                                recurrence_start = date(qdate.year(), qdate.month(), qdate.day())
                        except Exception:
                            pass
                    data["recurrence_start_date"] = recurrence_start
                    recurrence_end = None
                    if hasattr(self, 'recurrence_end_picker') and data.get("recurrence_type"):
                        try:
                            qdate = self.recurrence_end_picker.date
                            if qdate is not None and hasattr(qdate, 'isValid') and qdate.isValid():
                                recurrence_end = date(qdate.year(), qdate.month(), qdate.day())
                        except Exception:
                            pass
                    data["recurrence_end_date"] = recurrence_end
                    if recurrence_start is not None:
                        today = date.today()
                        if recurrence_start < today:
                            InfoBar.error(title="日期无效", content="开始日期不能早于今日", parent=self,
                                          position=InfoBarPosition.TOP, duration=3000)
                            return
                    if recurrence_end is not None:
                        today = date.today()
                        max_end = today + timedelta(days=365)
                        if recurrence_end < today:
                            InfoBar.error(title="日期无效", content="结束日期不能早于今日", parent=self,
                                          position=InfoBarPosition.TOP, duration=3000)
                            return
                        if recurrence_end > max_end:
                            InfoBar.error(title="日期无效", content="结束日期不能超过一年", parent=self,
                                          position=InfoBarPosition.TOP, duration=3000)
                            return
                    if recurrence_start and recurrence_end and recurrence_start > recurrence_end:
                        InfoBar.error(title="日期无效", content="开始日期不能晚于结束日期", parent=self,
                                      position=InfoBarPosition.TOP, duration=3000)
                        return
                    # 周重复必须至少选择一天
                    if recurrence_type == "weekly" and not data.get("recurrence_day"):
                        InfoBar.error(title="设置无效", content="周重复至少需要选择一天", parent=self,
                                      position=InfoBarPosition.TOP, duration=3000)
                        return
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
        # 恢复窗口尺寸
        saved_size = settings.todo_dialog_size
        if saved_size:
            self.resize(saved_size[0], saved_size[1])
        screen = self.screen().availableGeometry()
        x = screen.x() + (screen.width() - self.width()) // 2
        y = screen.y() + (screen.height() - self.height()) // 2
        self.move(x, y)
        self.title_edit.setFocus()
        self.title_edit.setStyleSheet("")
        if hasattr(self, 'weekday_btns'):
            self._apply_weekday_btn_style()

        dark = isDarkTheme()
        if dark:
            base_style = """
                QDialog {
                    background-color: transparent;
                }
                SubtitleLabel { color: #EEE; }
                QLabel { color: #DDD; }
                LineEdit { background-color: rgb(59, 59, 59); color: #EEE; border: 1px solid rgb(80,80,80); border-radius: 6px; }
                TextEdit { background-color: rgb(59, 59, 59); color: #EEE; border: 1px solid rgb(80,80,80); border-radius: 6px; }
                QTextEdit { background-color: rgb(59, 59, 59); color: #EEE; border: 1px solid rgb(80,80,80); border-radius: 6px; }
                QTextBrowser { background-color: rgb(59, 59, 59); color: #EEE; border: 1px solid rgb(80,80,80); border-radius: 6px; }
                CheckBox { color: #DDD; }
                CompactSpinBox { background-color: rgb(59, 59, 59); color: #EEE; border: 1px solid rgb(80,80,80); border-radius: 6px; }
            """
            if self._is_widescreen:
                base_style += """
                    QFrame#widescreenRightCard {
                        background-color: rgb(50, 50, 50);
                        border: 1px solid rgb(70, 70, 70);
                        border-radius: 8px;
                    }
                """
            self.setStyleSheet(base_style)
        else:
            base_style = """
                QDialog {
                    background-color: transparent;
                }
                SubtitleLabel { color: #111; }
                QLabel { color: #333; }
                LineEdit { background-color: #FFF; color: #333; }
                TextEdit { background-color: #FFF; color: #333; }
                QTextEdit { background-color: #FFF; color: #333; border: 1px solid #DDD; border-radius: 6px; }
                QTextBrowser { background-color: #FFF; color: #333; border: 1px solid #DDD; border-radius: 6px; }
                CheckBox { color: #333; }
                CompactSpinBox { background-color: #FFF; color: #333; }
            """
            if self._is_widescreen:
                base_style += """
                    QFrame#widescreenRightCard {
                        background-color: #FFF;
                        border: 1px solid #E0E0E0;
                        border-radius: 8px;
                    }
                """
            self.setStyleSheet(base_style)
