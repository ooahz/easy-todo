"""重复任务编辑范围选择对话框"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QButtonGroup

from qfluentwidgets import (
    MessageBoxBase, SubtitleLabel, BodyLabel, CaptionLabel,
    RadioButton, IconWidget, FluentIcon, isDarkTheme,
    CardWidget,
)


def _colors():
    if isDarkTheme():
        return {
            "option_bg": "#2D2D2D",
            "option_selected_bg": "rgba(96, 205, 255, 0.08)",
            "option_selected_border": "rgba(96, 205, 255, 0.3)",
            "border": "rgba(255, 255, 255, 0.06)",
            "muted": "#999",
            "body": "#BBB",
            "accent": "#60CDFF",
            "warning": "#FFB347",
        }
    return {
        "option_bg": "#FFFFFF",
        "option_selected_bg": "rgba(0, 120, 212, 0.05)",
        "option_selected_border": "rgba(0, 120, 212, 0.3)",
        "border": "rgba(0, 0, 0, 0.06)",
        "muted": "#999",
        "body": "#555",
        "accent": "#0078D4",
        "warning": "#FF8C00",
    }


class _OptionCard(CardWidget):

    def __init__(self, icon: FluentIcon, title: str, desc: str,
                 color: str, parent=None):
        super().__init__(parent)
        self._selected = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(64)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)

        icon_w = IconWidget(icon)
        icon_w.setFixedSize(20, 20)
        icon_w.setStyleSheet(f"color: {color};")
        layout.addWidget(icon_w)

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(1)

        title_label = BodyLabel(title)
        title_label.setStyleSheet(f"color: {_colors()['body']}; font-size: 13px; font-weight: 500;")
        text_layout.addWidget(title_label)

        desc_label = CaptionLabel(desc)
        desc_label.setStyleSheet(f"color: {_colors()['muted']}; font-size: 11px;")
        desc_label.setWordWrap(True)
        text_layout.addWidget(desc_label)

        layout.addLayout(text_layout, 1)
        self._apply_style()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            parent_dlg = self.parent()
            while parent_dlg and not isinstance(parent_dlg, RecurrenceEditDialog):
                parent_dlg = parent_dlg.parent()
            if parent_dlg:
                for i, card in enumerate(parent_dlg._cards):
                    if card is self:
                        parent_dlg._radios[i].setChecked(True)
                        break
        super().mousePressEvent(event)

    def set_selected(self, selected: bool):
        self._selected = selected
        self._apply_style()

    def _apply_style(self):
        c = _colors()
        if self._selected:
            self.setStyleSheet(f"""
                _OptionCard {{
                    background-color: {c['option_selected_bg']};
                    border: 1px solid {c['option_selected_border']};
                    border-radius: 8px;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                _OptionCard {{
                    background-color: {c['option_bg']};
                    border: 1px solid {c['border']};
                    border-radius: 8px;
                }}
            """)


class RecurrenceEditDialog(MessageBoxBase):
    """重复任务编辑范围选择对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)

        self.yesButton.setText("确认")
        self.cancelButton.setText("取消")

        self.widget.setMinimumWidth(420)

        title = SubtitleLabel("编辑重复任务")
        self.viewLayout.addWidget(title)

        hint = BodyLabel("这是一个重复任务，请选择编辑范围：")
        hint.setWordWrap(True)
        self.viewLayout.addWidget(hint)

        self._btn_group = QButtonGroup(self)
        c = _colors()

        options = [
            ("this", FluentIcon.CALENDAR, "仅修改当前任务",
             "只修改当前这一项，其他重复任务不受影响",
             c["accent"]),
            ("this_and_future", FluentIcon.CALENDAR, "修改此次及之后",
             "修改当前及之后的所有重复任务",
             c["warning"]),
        ]

        self._radios: list[RadioButton] = []
        self._cards: list[_OptionCard] = []

        for i, (mode, icon, opt_title, desc, color) in enumerate(options):
            row = QHBoxLayout()
            row.setSpacing(8)

            radio = RadioButton()
            if i == 0:
                radio.setChecked(True)
            radio.setProperty("_mode", mode)
            self._btn_group.addButton(radio)
            self._radios.append(radio)

            card = _OptionCard(icon, opt_title, desc, color)
            self._cards.append(card)

            radio.toggled.connect(
                lambda checked, idx=i: self._on_radio_toggled(idx, checked)
            )

            row.addWidget(radio)
            row.addWidget(card, 1)
            self.viewLayout.addLayout(row)

        self._update_card_selection()

    def _on_radio_toggled(self, idx: int, checked: bool):
        if checked:
            self._cards[idx].set_selected(True)
            for j, card in enumerate(self._cards):
                if j != idx:
                    card.set_selected(False)

    def _update_card_selection(self):
        for i, radio in enumerate(self._radios):
            self._cards[i].set_selected(radio.isChecked())

    @property
    def result_mode(self) -> str | None:
        for radio in self._radios:
            if radio.isChecked():
                return radio.property("_mode")
        return None
