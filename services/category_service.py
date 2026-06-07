"""分类业务逻辑"""
from __future__ import annotations
from typing import Optional

from PySide6.QtCore import QObject, Signal

from models.database import db
from models.category import Category


class _CategoryEventBus(QObject):
    """分类事件总线（单例 QObject），用于跨组件通知分类变更。
    """

    created = Signal(int)
    updated = Signal(int)
    deleted = Signal(int)
    reordered = Signal()


_event_bus_instance: _CategoryEventBus | None = None


def category_event_bus() -> _CategoryEventBus:
    """获取分类事件总线单例"""
    global _event_bus_instance
    if _event_bus_instance is None:
        _event_bus_instance = _CategoryEventBus()
    return _event_bus_instance


class CategoryService:
    """分类服务"""

    def __init__(self):
        self.session = db.get_session()

    def reset_session(self):
        """重置会话"""
        try:
            self.session.close()
        except Exception:
            pass
        self.session = db.get_session()

    def create(self, name: str, color: str = "#0078D4") -> Category:
        """创建分类"""
        # 获取当前最大排序值
        max_order = self.session.query(Category.sort_order).order_by(
            Category.sort_order.desc()
        ).first()
        sort_order = (max_order[0] + 1) if max_order else 0

        category = Category(
            name=name.strip(),
            color=color,
            sort_order=sort_order,
        )
        self.session.add(category)
        self.session.commit()
        category_event_bus().created.emit(category.id)
        return category

    def update(self, category_id: int, **kwargs) -> Optional[Category]:
        """更新分类"""
        category = self.session.query(Category).filter(
            Category.id == category_id
        ).first()
        if not category:
            return None

        if category.is_system:
            return None

        for key, value in kwargs.items():
            if hasattr(category, key):
                setattr(category, key, value)

        self.session.commit()
        category_event_bus().updated.emit(category_id)
        return category

    def delete(self, category_id: int, move_to_id: Optional[int] = None) -> bool:
        """删除分类

        Args:
            category_id: 要删除的分类ID
            move_to_id: 将关联任务移动到的分类ID，None表示设为无分类

        Returns:
            是否删除成功
        """
        from models.todo import Todo

        category = self.session.query(Category).filter(
            Category.id == category_id
        ).first()
        if not category:
            return False

        if category.is_system:
            return False

        if move_to_id:
            self.session.query(Todo).filter(
                Todo.category_id == category_id
            ).update({"category_id": move_to_id})
        else:
            self.session.query(Todo).filter(
                Todo.category_id == category_id
            ).update({"category_id": None})

        self.session.delete(category)
        self.session.commit()
        category_event_bus().deleted.emit(category_id)
        return True

    def get_all(self) -> list[Category]:
        """获取所有分类"""
        return self.session.query(Category).order_by(
            Category.sort_order.asc()
        ).all()

    def get_by_id(self, category_id: int) -> Optional[Category]:
        """根据ID获取分类"""
        return self.session.query(Category).filter(
            Category.id == category_id
        ).first()

    def get_by_name(self, name: str) -> Optional[Category]:
        """根据名称获取分类"""
        return self.session.query(Category).filter(
            Category.name == name
        ).first()

    def reorder(self, category_ids: list[int]) -> bool:
        """重新排序分类"""
        for index, category_id in enumerate(category_ids):
            self.session.query(Category).filter(
                Category.id == category_id
            ).update({"sort_order": index})
        self.session.commit()
        category_event_bus().reordered.emit()
        return True

    def get_count(self) -> int:
        """获取分类数量"""
        return self.session.query(Category).count()

    def close(self):
        """关闭数据库会话"""
        try:
            self.session.close()
        except Exception:
            pass
