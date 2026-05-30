"""Todo 业务逻辑服务"""
from __future__ import annotations
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
               pid: Optional[int] = None,
               recurrence_type: Optional[str] = None,
               recurrence_interval: int = 1,
               recurrence_day: Optional[int] = None,
               recurrence_end_date=None) -> Todo:
        """创建待办事项，pid 为 None 则创建父任务，否则创建子任务"""
        if due_date is not None and hasattr(due_date, 'year') and not isinstance(due_date, date):
            from datetime import date as pydate
            due_date = pydate(due_date.year(), due_date.month(), due_date.day())

        if recurrence_end_date is not None and hasattr(recurrence_end_date, 'year') and not isinstance(recurrence_end_date, date):
            from datetime import date as pydate
            recurrence_end_date = pydate(recurrence_end_date.year(), recurrence_end_date.month(), recurrence_end_date.day())

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
            recurrence_type=recurrence_type,
            recurrence_interval=recurrence_interval,
            recurrence_day=recurrence_day,
            recurrence_end_date=recurrence_end_date,
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

        if 'recurrence_end_date' in kwargs and kwargs['recurrence_end_date'] is not None and hasattr(kwargs['recurrence_end_date'], 'year') and not isinstance(kwargs['recurrence_end_date'], date):
            from datetime import date as pydate
            qd = kwargs['recurrence_end_date']
            kwargs['recurrence_end_date'] = pydate(qd.year(), qd.month(), qd.day())

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
        """切换完成状态，子任务全部完成时自动完成父任务"""
        todo = self.get_by_id(todo_id)
        if not todo:
            return None

        # 重复任务
        if todo.recurrence_type and todo.pid is None:
            is_now_done = self.toggle_occurrence_done(todo_id, date.today())
            new_status = STATUS_DONE if is_now_done else STATUS_TODO
            children = self.session.query(Todo).filter(Todo.pid == todo.id).all()
            for child in children:
                child.status = new_status
                child.updated_at = datetime.now()
            self.session.commit()
            self.session.refresh(todo)
            return todo

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
            parent = self.get_by_id(todo.pid)
            if parent and not parent.recurrence_type:
                all_done = self._check_children_all_done(todo.pid)
                if parent.status != (STATUS_DONE if all_done else STATUS_TODO):
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

    def get_children_count(self, parent_id: int) -> int:
        """获取父任务的子任务数量"""
        return self.session.query(Todo).filter(Todo.pid == parent_id).count()

    # ---- 自动延期 ----

    def process_auto_postpone(self) -> int:
        """自动延期过期任务（排除重复任务），并重置重复任务子任务的隔日残留状态"""
        today = date.today()
        count = self.session.query(Todo).filter(
            Todo.pid.is_(None),
            Todo.status == STATUS_TODO,
            Todo.auto_postpone == True,
            Todo.due_date < today,
            Todo.recurrence_type.is_(None),
        ).update({Todo.due_date: today, Todo.updated_at: datetime.now()},
                 synchronize_session=False)

        from models.recurrence_completion import RecurrenceCompletion
        recurring_parents = self.session.query(Todo.id).filter(
            Todo.pid.is_(None),
            Todo.recurrence_type.isnot(None),
        ).all()
        if recurring_parents:
            today_done_ids = {r[0] for r in self.session.query(
                RecurrenceCompletion.todo_id
            ).filter(
                RecurrenceCompletion.todo_id.in_([p[0] for p in recurring_parents]),
                RecurrenceCompletion.completed_date == today,
            ).all()}
            not_done_ids = [p[0] for p in recurring_parents if p[0] not in today_done_ids]
            if not_done_ids:
                self.session.query(Todo).filter(
                    Todo.pid.in_(not_done_ids),
                    Todo.status == STATUS_DONE,
                ).update({Todo.status: STATUS_TODO, Todo.updated_at: datetime.now()},
                         synchronize_session=False)

        self.session.commit()
        return count

    # ---- 查询：返回所有任务（含子任务） ----
    def get_all(self, status: int = STATUS_TODO,
                priority: Optional[int] = None, color_tag: Optional[str] = None,
                category_id: Optional[int] = None,
                sort_by: str = "created_at", sort_order: str = "desc",
                sort_rules: list[str] = None) -> list[Todo]:
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
        """获取所有任务（含已完成，不含已归档）"""
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
        """获取今日到期的所有任务（含今日匹配的重复任务）"""
        from services.recurrence_utils import matches_recurrence
        today = date.today()
        normal = self.session.query(Todo).filter(
            Todo.status == STATUS_TODO,
            Todo.due_date == today,
            Todo.recurrence_type.is_(None),
        ).order_by(Todo.priority.desc(), Todo.created_at.desc()).all()

        recurring = self.session.query(Todo).filter(
            Todo.pid.is_(None),
            Todo.recurrence_type.isnot(None),
            Todo.due_date <= today,
        ).all()
        matched = [t for t in recurring if matches_recurrence(
            t.due_date, today, t.recurrence_type, t.recurrence_interval,
            t.recurrence_end_date, t.recurrence_day
        )]

        existing_ids = {t.id for t in normal}
        return normal + [t for t in matched if t.id not in existing_ids]

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
        """获取已过期的所有任务（排除重复任务）"""
        today = date.today()
        return self.session.query(Todo).filter(
            Todo.status == STATUS_TODO,
            Todo.due_date < today,
            Todo.recurrence_type.is_(None),
        ).order_by(Todo.due_date.asc()).all()

    # ---- 统计 ----

    def count_by_status(self, status: int) -> int:
        """统计父任务数量"""
        return self.session.query(Todo).filter(
            Todo.pid.is_(None),
            Todo.status == status,
        ).count()

    def count_today(self) -> int:
        from services.recurrence_utils import matches_recurrence
        today = date.today()
        normal_count = self.session.query(Todo).filter(
            Todo.pid.is_(None),
            Todo.status == STATUS_TODO,
            Todo.due_date == today,
            Todo.recurrence_type.is_(None),
        ).count()

        recurring = self.session.query(Todo).filter(
            Todo.pid.is_(None),
            Todo.recurrence_type.isnot(None),
            Todo.due_date <= today,
        ).all()
        recurring_count = sum(1 for t in recurring if matches_recurrence(
            t.due_date, today, t.recurrence_type, t.recurrence_interval,
            t.recurrence_end_date, t.recurrence_day
        ))
        return normal_count + recurring_count

    def count_overdue(self) -> int:
        today = date.today()
        return self.session.query(Todo).filter(
            Todo.pid.is_(None),
            Todo.status == STATUS_TODO,
            Todo.due_date < today,
            Todo.recurrence_type.is_(None),
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

    # ---- 重复任务完成记录 ----

    def toggle_occurrence_done(self, todo_id: int, occurrence_date: date) -> bool:
        """切换重复任务某次重复日期的完成状态，返回新状态（True=完成）"""
        from models.recurrence_completion import RecurrenceCompletion
        existing = self.session.query(RecurrenceCompletion).filter_by(
            todo_id=todo_id, completed_date=occurrence_date
        ).first()
        if existing:
            self.session.delete(existing)
        else:
            comp = RecurrenceCompletion(todo_id=todo_id, completed_date=occurrence_date)
            self.session.add(comp)
        self.session.commit()
        return existing is None

    def get_completed_dates(self, todo_id: int) -> set[date]:
        """获取重复任务已完成的日期集合"""
        from models.recurrence_completion import RecurrenceCompletion
        rows = self.session.query(RecurrenceCompletion.completed_date).filter_by(
            todo_id=todo_id
        ).all()
        return {r[0] for r in rows}

    def get_all_completed_dates(self, todo_ids: list[int]) -> dict[int, set[date]]:
        """批量获取多个重复任务的已完成日期"""
        if not todo_ids:
            return {}
        from models.recurrence_completion import RecurrenceCompletion
        rows = self.session.query(
            RecurrenceCompletion.todo_id, RecurrenceCompletion.completed_date
        ).filter(RecurrenceCompletion.todo_id.in_(todo_ids)).all()
        result: dict[int, set[date]] = {}
        for tid, d in rows:
            result.setdefault(tid, set()).add(d)
        return result

    def get_today_completed_recurring(self) -> list[Todo]:
        """获取今天已完成的重复任务"""
        from models.recurrence_completion import RecurrenceCompletion
        today = date.today()
        todo_ids = self.session.query(RecurrenceCompletion.todo_id).filter(
            RecurrenceCompletion.completed_date == today
        ).all()
        if not todo_ids:
            return []
        ids = [r[0] for r in todo_ids]
        return self.session.query(Todo).filter(
            Todo.id.in_(ids),
            Todo.recurrence_type.isnot(None),
            Todo.pid.is_(None),
        ).all()

    def close(self):
        """关闭会话"""
        try:
            self.session.close()
        except Exception:
            pass
