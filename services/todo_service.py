"""Todo 业务逻辑服务"""
from datetime import datetime, date
from typing import Optional

from sqlalchemy.orm import Session

from models.database import db
from models.todo import Todo
from config.constants import STATUS_TODO, STATUS_DONE, STATUS_ARCHIVED, PRIORITY_HIGH


class TodoService:
    """待办事项业务逻辑"""

    def __init__(self):
        self.session: Session = db.get_session()

    def _refresh_session(self):
        """刷新会话"""
        try:
            self.session.commit()
        except Exception:
            self.session.rollback()

    # ---- CRUD ----

    def create(self, title: str, description: str = "", priority: int = 0,
               color_tag: Optional[str] = None, due_date=None,
               auto_postpone: bool = False, category_id: Optional[int] = None,
               pid: Optional[int] = None) -> Todo:
        """创建待办事项，pid 为 None 则创建父任务，否则创建子任务"""
        if due_date is not None and hasattr(due_date, 'year') and not isinstance(due_date, date):
            from datetime import date as pydate
            due_date = pydate(due_date.year(), due_date.month(), due_date.day())

        # 子任务：在父任务下按 sort_order 追加；父任务：在同级中追加
        max_order = self.session.query(Todo).filter(
            Todo.pid == pid
        ).count()

        todo = Todo(
            title=title.strip(),
            description=description.strip(),
            priority=priority,
            status=STATUS_TODO,
            color_tag=color_tag,
            due_date=due_date,
            auto_postpone=auto_postpone,
            sort_order=max_order,
            category_id=category_id,
            pid=pid,
        )
        self.session.add(todo)
        self.session.commit()
        self.session.refresh(todo)
        return todo

    def update(self, todo_id: int, **kwargs) -> Optional[Todo]:
        """更新待办事项"""
        todo = self.session.query(Todo).filter(Todo.id == todo_id).first()
        if not todo:
            return None

        # 日期转换
        if 'due_date' in kwargs and kwargs['due_date'] is not None and hasattr(kwargs['due_date'], 'year') and not isinstance(kwargs['due_date'], date):
            from datetime import date as pydate
            qd = kwargs['due_date']
            kwargs['due_date'] = pydate(qd.year(), qd.month(), qd.day())

        update_fields = set(kwargs.keys())
        for key, value in kwargs.items():
            if hasattr(todo, key) and (value is not None or key in update_fields):
                setattr(todo, key, value)

        todo.updated_at = datetime.now()
        self.session.commit()
        self.session.refresh(todo)
        return todo

    def delete(self, todo_id: int) -> bool:
        """删除待办事项（子任务级联删除由数据库处理）"""
        todo = self.session.query(Todo).filter(Todo.id == todo_id).first()
        if not todo:
            return False
        self.session.delete(todo)
        self.session.commit()
        return True

    def get_by_id(self, todo_id: int) -> Optional[Todo]:
        """根据 ID 获取"""
        return self.session.query(Todo).filter(Todo.id == todo_id).first()

    # ---- 状态操作 ----

    def toggle_done(self, todo_id: int) -> Optional[Todo]:
        """切换完成状态，子任务全部完成时自动完成父任务"""
        todo = self.get_by_id(todo_id)
        if not todo:
            return None

        if todo.status == STATUS_TODO:
            new_status = STATUS_DONE
        elif todo.status == STATUS_DONE:
            new_status = STATUS_TODO
        else:
            return todo

        todo.status = new_status
        todo.updated_at = datetime.now()

        # 如果是子任务：切换后检查父任务下所有子任务是否全部完成
        if todo.pid is not None:
            all_done = self._check_children_all_done(todo.pid)
            parent = self.get_by_id(todo.pid)
            if parent and parent.status != all_done:
                parent.status = STATUS_DONE if all_done else STATUS_TODO
                parent.updated_at = datetime.now()
        else:
            # 如果是父任务：切换时同时切换所有子任务
            children = self.session.query(Todo).filter(Todo.pid == todo.id).all()
            for child in children:
                child.status = new_status
                child.updated_at = datetime.now()

        self.session.commit()
        self.session.refresh(todo)
        return todo

    def _check_children_all_done(self, parent_id: int) -> bool:
        """检查父任务下所有子任务是否全部完成"""
        children = self.session.query(Todo).filter(Todo.pid == parent_id).all()
        if not children:
            return False
        return all(c.status == STATUS_DONE for c in children)

    # ---- 自动延期 ----

    def process_auto_postpone(self) -> int:
        """自动延期过期任务（仅父任务，不处理子任务）"""
        today = date.today()
        count = self.session.query(Todo).filter(
            Todo.pid.is_(None),  # 只处理父任务
            Todo.status == STATUS_TODO,
            Todo.auto_postpone == True,
            Todo.due_date < today,
        ).update({Todo.due_date: today, Todo.updated_at: datetime.now()},
                 synchronize_session=False)
        self.session.commit()
        return count

    # ---- 查询：返回所有任务（含子任务），由调用方构建树形结构 ----

    def get_all(self, status: int = STATUS_TODO,
                priority: Optional[int] = None, color_tag: Optional[str] = None,
                category_id: Optional[int] = None,
                sort_by: str = "created_at", sort_order: str = "desc",
                sort_rules: list[str] = None) -> list[Todo]:
        """获取所有任务（含子任务），由调用方在内存中构建树形"""
        query = self.session.query(Todo).filter(Todo.status == status)

        if priority is not None:
            query = query.filter(Todo.priority == priority)

        if color_tag is not None:
            query = query.filter(Todo.color_tag == color_tag)

        if category_id is not None:
            query = query.filter(Todo.category_id == category_id)

        if sort_rules:
            query = self._apply_multi_sort(query, sort_rules)
        else:
            query = self._apply_sort(query, sort_by, sort_order)

        return query.all()

    def get_all_including_done(self, sort_by: str = "created_at",
                                sort_order: str = "desc",
                                done_at_bottom: bool = True,
                                sort_rules: list[str] = None,
                                category_id: Optional[int] = None,
                                **kwargs) -> list[Todo]:
        """获取所有任务（含已完成），由调用方在内存中构建树形"""
        query = self.session.query(Todo).filter(
            Todo.status.in_([STATUS_TODO, STATUS_DONE])
        )

        priority = kwargs.get('priority')
        if priority is not None:
            query = query.filter(Todo.priority == priority)

        color_tag = kwargs.get('color_tag')
        if color_tag is not None:
            query = query.filter(Todo.color_tag == color_tag)

        if category_id is not None:
            query = query.filter(Todo.category_id == category_id)

        if done_at_bottom:
            if not sort_rules and sort_by == "custom":
                sort_rules = ["custom"]
            if sort_rules:
                sort_exprs = [self._sort_expr_for_field(f) for f in sort_rules]
            else:
                sort_exprs = self._build_sort_expr(sort_by, sort_order)
            query = query.order_by(Todo.status.asc(), *sort_exprs)
        else:
            if sort_rules:
                query = self._apply_multi_sort(query, sort_rules)
            else:
                query = self._apply_sort(query, sort_by, sort_order)

        return query.all()

    def _apply_sort(self, query, sort_by: str = "created_at", sort_order: str = "desc"):
        """应用排序规则"""
        sort_expr = self._build_sort_expr(sort_by, sort_order)
        return query.order_by(*sort_expr)

    @staticmethod
    def _sort_expr_for_field(field: str):
        """根据字段名返回排序表达式（降序，无截止日期排最后）"""
        if field == "custom":
            return Todo.sort_order.asc()
        elif field == "priority":
            return Todo.priority.desc()
        elif field == "due_date":
            return Todo.due_date.asc().nullslast()
        else:
            return Todo.created_at.desc()

    def _build_sort_expr(self, sort_by: str, sort_order: str):
        """构建排序表达式，主排序 + 副排序"""
        if sort_by == "sort_order":
            if sort_order == "asc":
                return [Todo.sort_order.asc(), Todo.created_at.desc()]
            else:
                return [Todo.sort_order.desc(), Todo.created_at.desc()]
        elif sort_by == "priority":
            if sort_order == "asc":
                return [Todo.priority.asc(), Todo.created_at.desc()]
            else:
                return [Todo.priority.desc(), Todo.created_at.desc()]
        elif sort_by == "due_date":
            if sort_order == "asc":
                return [Todo.due_date.asc().nullslast(), Todo.created_at.desc()]
            else:
                return [Todo.due_date.desc().nullsfirst(), Todo.created_at.desc()]
        else:
            if sort_order == "asc":
                return [Todo.created_at.asc(), Todo.priority.desc()]
            else:
                return [Todo.created_at.desc(), Todo.priority.desc()]

    def _apply_multi_sort(self, query, sort_rules: list[str]):
        """应用多级排序规则"""
        if not sort_rules:
            return query
        seen = set()
        exprs = []
        for field in sort_rules:
            if field not in seen:
                seen.add(field)
                exprs.append(self._sort_expr_for_field(field))
        return query.order_by(*exprs)

    def get_today(self) -> list[Todo]:
        """获取今日到期的所有任务"""
        today = date.today()
        return self.session.query(Todo).filter(
            Todo.status == STATUS_TODO,
            Todo.due_date == today,
        ).order_by(Todo.priority.desc(), Todo.created_at.desc()).all()

    def get_high_priority(self) -> list[Todo]:
        """获取高优先级所有任务"""
        return self.session.query(Todo).filter(
            Todo.status == STATUS_TODO,
            Todo.priority == PRIORITY_HIGH,
        ).order_by(Todo.created_at.desc()).all()

    def get_by_category(self, category_id: int) -> list[Todo]:
        """获取指定分类的所有任务"""
        return self.session.query(Todo).filter(
            Todo.status == STATUS_TODO,
            Todo.category_id == category_id,
        ).order_by(Todo.created_at.desc()).all()

    def get_overdue(self) -> list[Todo]:
        """获取已过期的所有任务"""
        today = date.today()
        return self.session.query(Todo).filter(
            Todo.status == STATUS_TODO,
            Todo.due_date < today,
        ).order_by(Todo.due_date.asc()).all()

    # ---- 统计 ----

    def count_by_status(self, status: int) -> int:
        """统计父任务数量"""
        return self.session.query(Todo).filter(
            Todo.pid.is_(None),
            Todo.status == status,
        ).count()

    def count_today(self) -> int:
        today = date.today()
        return self.session.query(Todo).filter(
            Todo.pid.is_(None),
            Todo.status == STATUS_TODO,
            Todo.due_date == today,
        ).count()

    def count_overdue(self) -> int:
        today = date.today()
        return self.session.query(Todo).filter(
            Todo.pid.is_(None),
            Todo.status == STATUS_TODO,
            Todo.due_date < today,
        ).count()

    # ---- 清理 ----

    def clear_completed(self) -> int:
        """清除所有已完成的父任务（子任务级联删除）"""
        count = self.session.query(Todo).filter(
            Todo.pid.is_(None),
            Todo.status == STATUS_DONE,
        ).delete(synchronize_session=False)
        self.session.commit()
        return count

    def reorder(self, todo_ids: list[int]):
        """重新排序父任务"""
        for order, todo_id in enumerate(todo_ids):
            todo = self.session.query(Todo).filter(Todo.id == todo_id).first()
            if todo:
                todo.sort_order = order * 10
        self.session.commit()

    def close(self):
        """关闭会话"""
        try:
            self.session.close()
        except Exception:
            pass
