"""Todo 业务逻辑服务"""
from datetime import datetime, date, timedelta
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
               auto_postpone: bool = False, category_id: Optional[int] = None) -> Todo:
        """创建待办事项"""
        if due_date is not None and hasattr(due_date, 'year') and not isinstance(due_date, date):
            from datetime import date as pydate
            due_date = pydate(due_date.year(), due_date.month(), due_date.day())

        max_order = self.session.query(Todo).filter(
            Todo.status == STATUS_TODO
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
        """删除待办事项"""
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
        """切换完成状态"""
        todo = self.get_by_id(todo_id)
        if not todo:
            return None
        if todo.status == STATUS_TODO:
            todo.status = STATUS_DONE
        elif todo.status == STATUS_DONE:
            todo.status = STATUS_TODO
        todo.updated_at = datetime.now()
        self.session.commit()
        self.session.refresh(todo)
        return todo

    # ---- 自动延期 ----

    def process_auto_postpone(self) -> int:
        today = date.today()
        count = self.session.query(Todo).filter(
            Todo.status == STATUS_TODO,
            Todo.auto_postpone == True,
            Todo.due_date < today,
            Todo.due_date.isnot(None),
        ).update({Todo.due_date: today, Todo.updated_at: datetime.now()},
                  synchronize_session=False)
        self.session.commit()
        return count

    # ---- 查询 ----

    def get_all(self, status: int = STATUS_TODO,
                priority: Optional[int] = None, color_tag: Optional[str] = None,
                category_id: Optional[int] = None,
                sort_by: str = "created_at", sort_order: str = "desc",
                sort_rules: list[str] = None) -> list[Todo]:
        """获取待办列表"""
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
        """获取所有任务"""
        query = self.session.query(Todo).filter(Todo.status.in_([STATUS_TODO, STATUS_DONE]))

        priority = kwargs.get('priority')
        if priority is not None:
            query = query.filter(Todo.priority == priority)

        color_tag = kwargs.get('color_tag')
        if color_tag is not None:
            query = query.filter(Todo.color_tag == color_tag)

        if category_id is not None:
            query = query.filter(Todo.category_id == category_id)

        if done_at_bottom:
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
        if field == "priority":
            return Todo.priority.desc()
        elif field == "due_date":
            return Todo.due_date.asc().nullslast()
        else:
            return Todo.created_at.desc()

    def _build_sort_expr(self, sort_by: str, sort_order: str):
        """构建排序表达式，主排序 + 副排序"""
        if sort_by == "priority":
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
        """获取今日到期任务"""
        today = date.today()
        return self.session.query(Todo).filter(
            Todo.status == STATUS_TODO,
            Todo.due_date == today,
        ).order_by(Todo.priority.desc(), Todo.created_at.desc()).all()

    def get_high_priority(self) -> list[Todo]:
        """获取高优先级任务"""
        return self.session.query(Todo).filter(
            Todo.status == STATUS_TODO,
            Todo.priority == PRIORITY_HIGH,
        ).order_by(Todo.created_at.desc()).all()

    def get_by_category(self, category_id: int) -> list[Todo]:
        """获取指定分类的任务"""
        return self.session.query(Todo).filter(
            Todo.status == STATUS_TODO,
            Todo.category_id == category_id,
        ).order_by(Todo.created_at.desc()).all()

    def get_overdue(self) -> list[Todo]:
        """获取已过期任务"""
        today = date.today()
        return self.session.query(Todo).filter(
            Todo.status == STATUS_TODO,
            Todo.due_date < today,
        ).order_by(Todo.due_date.asc()).all()

    # ---- 统计 ----

    def count_by_status(self, status: int) -> int:
        return self.session.query(Todo).filter(Todo.status == status).count()

    def count_today(self) -> int:
        today = date.today()
        return self.session.query(Todo).filter(
            Todo.status == STATUS_TODO,
            Todo.due_date == today,
        ).count()

    def count_overdue(self) -> int:
        today = date.today()
        return self.session.query(Todo).filter(
            Todo.status == STATUS_TODO,
            Todo.due_date < today,
        ).count()

    # ---- 清理 ----

    def clear_completed(self) -> int:
        """清除所有已完成的任务"""
        count = self.session.query(Todo).filter(
            Todo.status == STATUS_DONE
        ).delete(synchronize_session=False)
        self.session.commit()
        return count

    def close(self):
        """关闭会话"""
        try:
            self.session.close()
        except Exception:
            pass
