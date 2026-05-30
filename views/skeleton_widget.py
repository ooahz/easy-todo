"""骨架加载占位组件"""
from __future__ import annotations

from PySide6.QtCore import QPropertyAnimation, QEasingCurve
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame, QGraphicsOpacityEffect
)
from qfluentwidgets import CardWidget, isDarkTheme


class SkeletonBar(QFrame):
    """单个骨架条"""

    def __init__(self, width: int, height: int, parent=None):
        super().__init__(parent)
        self.setFixedSize(width, height)
        radius = min(height // 2, 4)
        bg = "#3C3C3C" if isDarkTheme() else "#E8E8E8"
        self.setStyleSheet(f"background: {bg}; border-radius: {radius}px;")


def _make_pulse_anim(target: QWidget) -> tuple[QGraphicsOpacityEffect, QPropertyAnimation]:
    """创建脉冲透明度动画，返回 (effect, animation)"""
    effect = QGraphicsOpacityEffect(target)
    effect.setOpacity(1.0)
    target.setGraphicsEffect(effect)

    anim = QPropertyAnimation(effect, b"opacity")
    anim.setDuration(900)
    anim.setStartValue(1.0)
    anim.setEndValue(0.4)
    anim.setEasingCurve(QEasingCurve.InOutSine)
    anim.setLoopCount(-1)
    anim.start()
    return effect, anim


class SkeletonCard(CardWidget):
    """模拟 TodoCard 的骨架卡片（72px 高）"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(72)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 8, 8)
        layout.setSpacing(0)

        row = QHBoxLayout()
        row.setSpacing(8)

        row.addWidget(SkeletonBar(4, 40, self))
        row.addWidget(SkeletonBar(20, 20, self))

        content = QVBoxLayout()
        content.setSpacing(6)
        content.addWidget(SkeletonBar(180, 14, self))
        content.addWidget(SkeletonBar(100, 10, self))
        row.addLayout(content, 1)

        layout.addLayout(row)

        self._effect, self._anim = _make_pulse_anim(self)

    def stop(self):
        self._anim.stop()


class SkeletonSubtaskCard(CardWidget):
    """模拟 SubtaskCard 的骨架（52px 高）"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(52)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 6, 8, 6)
        layout.setSpacing(0)

        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(SkeletonBar(18, 18, self))
        row.addWidget(SkeletonBar(140, 14, self), 1)
        layout.addLayout(row)

        self._effect, self._anim = _make_pulse_anim(self)

    def stop(self):
        self._anim.stop()
