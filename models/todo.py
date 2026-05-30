"""Todo 数据模型"""
from __future__ import annotations
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
    recurrence_type = Column(String(20), default=None, nullable=True)  # daily/weekly/monthly
    recurrence_interval = Column(Integer, default=1)  # 间隔数
    recurrence_day = Column(Integer, default=None, nullable=True)  # 周几(1-7)或几号(1-31)
    recurrence_end_date = Column(Date, nullable=True)  # 重复结束日期
    is_recurrence_template = Column(Boolean, default=False)  # 是否为重复模板
    recurrence_template_id = Column(Integer, ForeignKey("todos.id", ondelete="SET NULL"), nullable=True)  # 所属模板ID
    occurrence_date = Column(Date, nullable=True)  # 实例对应的重复日期
    is_exception = Column(Boolean, default=False)  # 是否为例外实例（已被单独编辑）
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
        foreign_keys="Todo.pid",
    )
    # 模板关联：实例指向模板
    template = relationship(
        "Todo",
        remote_side="Todo.id",
        foreign_keys="Todo.recurrence_template_id",
    )

    def to_dict(self):
        """序列化为字典"""
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
            "recurrence_type": self.recurrence_type,
            "recurrence_interval": self.recurrence_interval,
            "recurrence_day": self.recurrence_day,
            "recurrence_end_date": self.recurrence_end_date.isoformat() if self.recurrence_end_date else None,
            "is_recurrence_template": self.is_recurrence_template,
            "recurrence_template_id": self.recurrence_template_id,
            "occurrence_date": self.occurrence_date.isoformat() if self.occurrence_date else None,
            "is_exception": self.is_exception,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "sort_order": self.sort_order,
            "category_id": self.category_id,
            "category": self.category.to_dict() if self.category else None,
            "children": [],  # 由调用方填充
        }

    def to_export_dict(self) -> dict:
        """导出专用序列化，排除 ID 和内部引用字段，使用 category_name"""
        return {
            "title": self.title,
            "description": self.description or "",
            "priority": self.priority,
            "status": self.status,
            "color_tag": self.color_tag,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "auto_postpone": self.auto_postpone,
            "sort_order": self.sort_order,
            "category_name": self.category.name if self.category else None,
            "recurrence_type": self.recurrence_type,
            "recurrence_interval": self.recurrence_interval,
            "recurrence_day": self.recurrence_day,
            "recurrence_end_date": self.recurrence_end_date.isoformat() if self.recurrence_end_date else None,
            "is_recurrence_template": self.is_recurrence_template,
            "occurrence_date": self.occurrence_date.isoformat() if self.occurrence_date else None,
            "is_exception": self.is_exception,
        }
