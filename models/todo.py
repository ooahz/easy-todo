"""Todo 数据模型"""
from datetime import datetime

from sqlalchemy import Column, Integer, String, Text, Date, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship

from models.database import Base


class Todo(Base):
    __tablename__ = "todos"

    id = Column(Integer, primary_key=True, autoincrement=True)
    pid = Column(Integer, ForeignKey("todos.id", ondelete="CASCADE"), nullable=True)  # 父任务ID，NULL 表示顶级任务
    title = Column(String(200), nullable=False)
    description = Column(Text, default="")
    priority = Column(Integer, default=0)       # 0=无, 1=低, 2=中, 3=高
    status = Column(Integer, default=0)          # 0=待办, 1=已完成, 2=已归档
    color_tag = Column(String(7), default=None, nullable=True)
    due_date = Column(Date, nullable=True)
    auto_postpone = Column(Boolean, default=False)  # 自动延期
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    sort_order = Column(Integer, default=0)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)

    # 关联关系
    category = relationship("Category", back_populates="todos")
    # 自引用：子任务列表（按 sort_order 排序）
    children = relationship(
        "Todo",
        backref="parent",
        remote_side="Todo.id",
        order_by="Todo.sort_order",
    )

    def to_dict(self):
        """序列化为字典，不包含 children（由调用方在内存中构建树形）"""
        return {
            "id": self.id,
            "pid": self.pid,
            "title": self.title,
            "description": self.description or "",
            "priority": self.priority,
            "status": self.status,
            "color_tag": self.color_tag,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "auto_postpone": self.auto_postpone,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "sort_order": self.sort_order,
            "category_id": self.category_id,
            "category": self.category.to_dict() if self.category else None,
            "children": [],  # 由调用方填充
        }
