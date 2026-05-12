"""分类模型"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import relationship
from models.database import Base


class Category(Base):
    """任务分类"""
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False)
    color = Column(String(7), default="#0078D4")  # 十六进制颜色，用于导航栏标识
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.now)

    # 关联关系
    todos = relationship("Todo", back_populates="category")

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "color": self.color,
            "sort_order": self.sort_order,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
