"""Todo 数据模型"""
from datetime import datetime, date

from sqlalchemy import Column, Integer, String, Text, Date, DateTime, Boolean

from models.database import Base


class Todo(Base):
    __tablename__ = "todos"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, default="")
    priority = Column(Integer, default=0)       # 0=无, 1=低, 2=中, 3=高
    status = Column(Integer, default=0)          # 0=待办, 1=已完成, 2=已归档
    color_tag = Column(String(7), default=None, nullable=True)
    due_date = Column(Date, nullable=True)
    auto_postpone = Column(Boolean, default=False)  # 自动延期：过期时自动延到明天
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    sort_order = Column(Integer, default=0)

    def to_dict(self):
        return {
            "id": self.id,
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
        }
