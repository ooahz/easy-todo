"""分类业务逻辑"""
from __future__ import annotations
from typing import Optional

from PySide6.QtCore import QObject, Signal

from models.database import db
from models.category import Category
from config.settings import settings


SYSTEM_VIEW_KEYS = {"recent", "today", "important", "all", "done"}


class _CategoryEventBus(QObject):
    """分类事件总线（单例 QObject），用于跨组件通知分类变更。"""

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

    def create(self, name: str, color: str = "#00000000") -> Category:
        """创建分类"""
        with db.session_scope() as session:
            max_order = session.query(Category.sort_order).order_by(
                Category.sort_order.desc()
            ).first()
            sort_order = (max_order[0] + 1) if max_order else 0

            category = Category(
                name=name.strip(),
                color=color,
                sort_order=sort_order,
            )
            session.add(category)
            session.flush()
            cat_id = category.id
        # 信号在 session 提交后发射，避免监听器查询时连接被占用
        category_event_bus().created.emit(cat_id)
        return category

    def update(self, category_id: int, **kwargs) -> Optional[Category]:
        """更新分类"""
        with db.session_scope() as session:
            category = session.query(Category).filter(
                Category.id == category_id
            ).first()
            if not category:
                return None

            if category.is_system:
                return None

            for key, value in kwargs.items():
                if hasattr(category, key):
                    setattr(category, key, value)
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

        with db.session_scope() as session:
            category = session.query(Category).filter(
                Category.id == category_id
            ).first()
            if not category:
                return False

            if category.is_system:
                return False

            if move_to_id:
                session.query(Todo).filter(
                    Todo.category_id == category_id
                ).update({"category_id": move_to_id})
            else:
                session.query(Todo).filter(
                    Todo.category_id == category_id
                ).update({"category_id": None})

            session.delete(category)
        category_event_bus().deleted.emit(category_id)
        return True

    def get_all(self) -> list[Category]:
        """获取所有分类"""
        with db.session_scope() as session:
            return session.query(Category).order_by(
                Category.sort_order.asc()
            ).all()

    def get_by_id(self, category_id: int) -> Optional[Category]:
        """根据ID获取分类"""
        with db.session_scope() as session:
            return session.query(Category).filter(
                Category.id == category_id
            ).first()

    def get_by_name(self, name: str) -> Optional[Category]:
        """根据名称获取分类"""
        with db.session_scope() as session:
            return session.query(Category).filter(
                Category.name == name
            ).first()

    def reorder(self, category_ids: list[int]) -> bool:
        """重新排序分类"""
        with db.session_scope() as session:
            for index, category_id in enumerate(category_ids):
                session.query(Category).filter(
                    Category.id == category_id
                ).update({"sort_order": index})
        category_event_bus().reordered.emit()
        return True

    def get_count(self) -> int:
        """获取分类数量"""
        with db.session_scope() as session:
            return session.query(Category).count()

    def get_navigation_order(self) -> list[str]:
        """获取混排导航顺序，未设置时按系统视图+自定义分类默认顺序返回"""
        order = settings.navigation_order
        if order:
            return list(order)

        sys_order = [
            f"sys:{key}"
            for key in settings.system_view_order
            if key in SYSTEM_VIEW_KEYS
        ]
        cat_order = [
            f"cat:{c.id}"
            for c in self.get_all()
            if not c.is_system
        ]
        return sys_order + cat_order

    def save_navigation_order(self, order: list[str]) -> None:
        """保存混排导航顺序"""
        settings.navigation_order = list(order)

    def is_mixed_navigation_order(self) -> bool:
        """是否存在自定义分类排在系统视图前面的混排情况"""
        order = settings.navigation_order
        if order is None:
            return False
        seen_cat = False
        for token in order:
            if token.startswith("cat:"):
                seen_cat = True
            elif token.startswith("sys:") and seen_cat:
                return True
        return False

    def append_navigation_order(self, item: str) -> None:
        """在混排导航顺序末尾追加一项（仅在已启用混排时写入）"""
        if settings.navigation_order is None:
            return
        order = list(settings.navigation_order)
        if item not in order:
            order.append(item)
            self.save_navigation_order(order)

    def remove_navigation_order(self, item: str) -> None:
        """从混排导航顺序中移除一项（仅在已启用混排时写入）"""
        if settings.navigation_order is None:
            return
        order = list(settings.navigation_order)
        if item in order:
            order.remove(item)
            self.save_navigation_order(order)
