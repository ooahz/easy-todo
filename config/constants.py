"""应用常量定义"""
from __future__ import annotations

# 优先级（艾森豪威尔矩阵）
PRIORITY_NONE = 0
PRIORITY_IMPORTANT_URGENT = 1      # 重要且紧急
PRIORITY_IMPORTANT_NOT_URGENT = 2  # 重要不紧急
PRIORITY_NOT_IMPORTANT_URGENT = 3  # 不重要但紧急
PRIORITY_NOT_IMPORTANT_NOT_URGENT = 4  # 不重要不紧急

PRIORITY_MAP = {
    PRIORITY_NONE: "无",
    PRIORITY_IMPORTANT_URGENT: "重要且紧急",
    PRIORITY_IMPORTANT_NOT_URGENT: "重要不紧急",
    PRIORITY_NOT_IMPORTANT_URGENT: "不重要但紧急",
    PRIORITY_NOT_IMPORTANT_NOT_URGENT: "不重要不紧急",
}

# 重要任务视图分组颜色
PRIORITY_GROUP_COLORS = {
    PRIORITY_IMPORTANT_URGENT: "#D13438",
    PRIORITY_IMPORTANT_NOT_URGENT: "#FFB900",
    PRIORITY_NOT_IMPORTANT_URGENT: "#0078D4",
    PRIORITY_NOT_IMPORTANT_NOT_URGENT: "#107C10",
}

# 状态
STATUS_TODO = 0
STATUS_DONE = 1
STATUS_ARCHIVED = 2

STATUS_MAP = {
    STATUS_TODO: "待办",
    STATUS_DONE: "已完成",
    STATUS_ARCHIVED: "已归档",
}

# 排序方式
SORT_BY_CREATED = "created_at"
SORT_BY_DUE_DATE = "due_date"
SORT_BY_PRIORITY = "priority"
SORT_BY_TITLE = "title"

# 颜色标识列表
TODO_COLORS = [
    ("红色", "#D13438"),
    ("橙色", "#CA5010"),
    ("黄色", "#FFB900"),
    ("绿色", "#107C10"),
    ("青色", "#00B7C3"),
    ("蓝色", "#0078D4"),
    ("紫色", "#8764B8"),
    ("粉色", "#C239B3"),
    ("棕色", "#8B4513"),
]

# 重复类型
RECURRENCE_TYPES = {
    "daily": "每天",
    "weekly": "每周",
    "monthly": "每月",
    "workday": "工作日",
}

# 任务类型
TASK_TYPE_MAP = {
    "default": "默认任务",
    "recurrence": "重复任务",
    "periodic": "周期任务",
}

# 星期名称映射（1=周一, 7=周日）
WEEKDAY_NAMES = {1: "一", 2: "二", 3: "三", 4: "四", 5: "五", 6: "六", 7: "日"}
WEEKDAY_LABELS = {1: "周一", 2: "周二", 3: "周三", 4: "周四", 5: "周五", 6: "周六", 7: "周日"}


def parse_recurrence_day(value) -> list[int]:
    """解析 recurrence_day 字段为整数列表

    兼容旧数据（int）和新数据（逗号分隔字符串），返回 [1,3,5] 形式的列表。
    """
    if value is None:
        return []
    if isinstance(value, int):
        return [value]
    if isinstance(value, str):
        parts = [p.strip() for p in value.split(",") if p.strip()]
        result = []
        for p in parts:
            try:
                result.append(int(p))
            except ValueError:
                pass
        return result
    return []

# 应用信息
APP_NAME = "Easy Todo"
APP_VERSION = "2.0.0"
APP_ID = "com.easy.todo"
