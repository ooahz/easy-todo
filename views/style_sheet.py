"""样式表管理"""
from enum import Enum
from qfluentwidgets import StyleSheetBase, Theme, qconfig


class StyleSheet(StyleSheetBase, Enum):
    """样式表枚举"""
    SETTINGS_CARD = "settings_card"

    def path(self, theme=Theme.AUTO):
        theme = qconfig.theme if theme == Theme.AUTO else theme
        return f"qss/{theme.value.lower()}/{self.value}.qss"
