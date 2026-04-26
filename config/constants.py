"""应用常量定义"""

# 优先级
PRIORITY_NONE = 0
PRIORITY_LOW = 1
PRIORITY_MEDIUM = 2
PRIORITY_HIGH = 3

PRIORITY_MAP = {
    PRIORITY_NONE: "无",
    PRIORITY_LOW: "低",
    PRIORITY_MEDIUM: "中",
    PRIORITY_HIGH: "高",
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

# 应用信息
APP_NAME = "Easy Todo"
APP_VERSION = "1.1.0"
APP_ID = "com.easy.todo"
