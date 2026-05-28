"""重复任务逐次完成记录"""
from datetime import datetime

from sqlalchemy import Column, Integer, Date, DateTime, ForeignKey, UniqueConstraint

from models.database import Base


class RecurrenceCompletion(Base):
    __tablename__ = "recurrence_completions"
    __table_args__ = (
        UniqueConstraint("todo_id", "completed_date", name="uq_todo_completed_date"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    todo_id = Column(Integer, ForeignKey("todos.id", ondelete="CASCADE"), nullable=False)
    completed_date = Column(Date, nullable=False)
    completed_at = Column(DateTime, default=datetime.now)
