"""Todo 业务逻辑服务"""
from __future__ import annotations
import logging
from datetime import datetime, date, timedelta
from typing import Optional

from sqlalchemy import func, case, literal, and_, or_
from sqlalchemy.orm import selectinload, joinedload

from models.database import db
from models.todo import Todo
from config.constants import STATUS_TODO, STATUS_DONE, STATUS_ARCHIVED, PRIORITY_NONE

logger = logging.getLogger(__name__)

INSTANCE_WINDOW_DAYS = 14
RECURRENCE_END_MAX_DAYS = 365


class TodoService:
    """待办事项业务逻辑"""

    @staticmethod
    def _coerce_date(value, field_name: str):
        """将各种日期输入统一转为 date/datetime 对象"""
        if value is None:
            return None
        if isinstance(value, (date, datetime)):
            return value
        if isinstance(value, str) and value:
            try:
                if 'completed_at' in field_name or 'created_at' in field_name or 'updated_at' in field_name:
                    return datetime.fromisoformat(value)
                return date.fromisoformat(value)
            except (ValueError, TypeError):
                return None
        if hasattr(value, 'year') and callable(value.year):
            from datetime import date as pydate
            try:
                return pydate(value.year(), value.month(), value.day())
            except Exception:
                return None
        return None

    @staticmethod
    def _validate_recurrence_end_date(end_date):
        if end_date is None:
            return
        if not isinstance(end_date, date):
            return
        today = date.today()
        if end_date < today:
            raise ValueError("重复结束日期不能早于今日")
        if end_date > today + timedelta(days=RECURRENCE_END_MAX_DAYS):
            raise ValueError("重复结束日期不能超过一年")

    # ---- 内部查询辅助 ----

    @staticmethod
    def _get_by_id(session, todo_id: int) -> Optional[Todo]:
        """根据 ID 获取"""
        return session.query(Todo).options(
            joinedload(Todo.category)
        ).filter(Todo.id == todo_id).first()

    # ---- CRUD ----

    def create(self, title: str, description: str = "", priority: int = 0,
               color_tag: Optional[str] = None, due_date=None,
               start_date=None,
               auto_postpone: bool = False, category_id: Optional[int] = None,
               pid: Optional[int] = None,
               recurrence_type: Optional[str] = None,
               recurrence_interval: int = 1,
               recurrence_day: Optional[str] = None,
               recurrence_start_date=None,
               recurrence_end_date=None,
               task_type: Optional[str] = None) -> Todo:
        """创建待办事项。有重复规则且为顶级任务时，创建模板+生成实例"""
        if due_date is not None and hasattr(due_date, 'year') and not isinstance(due_date, date):
            from datetime import date as pydate
            due_date = pydate(due_date.year(), due_date.month(), due_date.day())

        if start_date is not None and hasattr(start_date, 'year') and not isinstance(start_date, date):
            from datetime import date as pydate
            start_date = pydate(start_date.year(), start_date.month(), start_date.day())

        if recurrence_end_date is not None and hasattr(recurrence_end_date, 'year') and not isinstance(recurrence_end_date, date):
            from datetime import date as pydate
            recurrence_end_date = pydate(recurrence_end_date.year(), recurrence_end_date.month(), recurrence_end_date.day())

        if recurrence_start_date is not None and hasattr(recurrence_start_date, 'year') and not isinstance(recurrence_start_date, date):
            from datetime import date as pydate
            recurrence_start_date = pydate(recurrence_start_date.year(), recurrence_start_date.month(), recurrence_start_date.day())

        self._validate_recurrence_end_date(recurrence_end_date)

        # 周期任务
        if task_type == "periodic":
            auto_postpone = False
        # 根据 recurrence_type 自动设置 task_type
        if task_type is None:
            if recurrence_type:
                task_type = "recurrence"
            else:
                task_type = "default"

        is_template = bool(recurrence_type and pid is None)

        with db.session_scope() as session:
            max_order = session.query(Todo).filter(
                Todo.pid == pid
            ).count()

            todo = Todo(
                title=title.strip(),
                description=description.strip(),
                priority=priority,
                status=STATUS_TODO,
                color_tag=color_tag,
                start_date=start_date,
                due_date=due_date,
                task_type=task_type,
                auto_postpone=auto_postpone,
                sort_order=max_order,
                category_id=category_id,
                pid=pid,
                recurrence_type=recurrence_type,
                recurrence_interval=recurrence_interval,
                recurrence_day=recurrence_day,
                recurrence_start_date=recurrence_start_date,
                recurrence_end_date=recurrence_end_date,
                is_recurrence_template=is_template,
            )
            session.add(todo)
            session.flush()

            if is_template:
                self._ensure_instances(session, todo.id)

            return todo

    def create_raw(self, **kwargs) -> Todo:
        """直接创建待办事项"""
        for key in ('due_date', 'start_date', 'recurrence_end_date',
                     'recurrence_start_date', 'occurrence_date'):
            if key in kwargs:
                kwargs[key] = self._coerce_date(kwargs[key], key)

        # DateTime 类型字段转换
        for key in ('completed_at',):
            if key in kwargs:
                kwargs[key] = self._coerce_date(kwargs[key], key)

        with db.session_scope() as session:
            if 'sort_order' not in kwargs:
                pid = kwargs.get('pid')
                max_order = session.query(Todo).filter(
                    Todo.pid == pid
                ).count()
                kwargs['sort_order'] = max_order

            if 'status' not in kwargs:
                kwargs['status'] = STATUS_TODO

            todo = Todo(**kwargs)
            session.add(todo)
            session.flush()
            return todo

    def update(self, todo_id: int, **kwargs) -> Optional[Todo]:
        """更新待办事项"""
        with db.session_scope() as session:
            todo = session.query(Todo).filter(Todo.id == todo_id).first()
            if not todo:
                return None

            # 周期任务不允许开启自动延期
            task_type = kwargs.get("task_type") or todo.task_type or "default"
            if task_type == "periodic" and kwargs.get("auto_postpone"):
                kwargs["auto_postpone"] = False

            # Date 类型字段转换
            for key in ('due_date', 'start_date', 'recurrence_end_date',
                         'recurrence_start_date'):
                if key in kwargs:
                    kwargs[key] = self._coerce_date(kwargs[key], key)

            # DateTime 类型字段转换
            for key in ('completed_at',):
                if key in kwargs:
                    kwargs[key] = self._coerce_date(kwargs[key], key)

            if 'recurrence_end_date' in kwargs:
                self._validate_recurrence_end_date(kwargs['recurrence_end_date'])

            old_recurrence_type = todo.recurrence_type
            was_template = todo.is_recurrence_template

            update_fields = set(kwargs.keys())
            for key, value in kwargs.items():
                if hasattr(todo, key) and (value is not None or key in update_fields):
                    setattr(todo, key, value)

            todo.updated_at = datetime.now()

            new_recurrence_type = todo.recurrence_type
            is_instance = bool(todo.recurrence_template_id) and bool(todo.recurrence_type)

            if not is_instance and not was_template and new_recurrence_type and todo.pid is None:
                todo.is_recurrence_template = True
                session.flush()
                self._ensure_instances(session, todo.id)
                return todo

            if was_template and not new_recurrence_type:
                todo.is_recurrence_template = False
                session.query(Todo).filter(
                    Todo.recurrence_template_id == todo.id
                ).delete()
                session.flush()
                return todo

            if was_template and new_recurrence_type:
                session.flush()
                session.query(Todo).filter(
                    Todo.recurrence_template_id == todo.id,
                    Todo.is_exception == False,
                    Todo.occurrence_date >= date.today(),
                ).delete()
                self._ensure_instances(session, todo.id)
                return todo

            session.flush()
            return todo

    def delete(self, todo_id: int) -> bool:
        """删除待办事项"""
        with db.session_scope() as session:
            todo = session.query(Todo).filter(Todo.id == todo_id).first()
            if not todo:
                return False
            session.query(Todo).filter(Todo.pid == todo_id).delete(synchronize_session=False)
            session.delete(todo)
            return True

    def get_by_id(self, todo_id: int) -> Optional[Todo]:
        with db.session_scope() as session:
            return self._get_by_id(session, todo_id)

    # ---- 状态操作 ----

    def toggle_done(self, todo_id: int) -> Optional[Todo]:
        """切换完成状态，子任务全部完成时自动完成父任务"""
        with db.session_scope() as session:
            todo = self._get_by_id(session, todo_id)
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

            if new_status == STATUS_DONE:
                todo.completed_at = datetime.now()
            else:
                todo.completed_at = None

            if new_status == STATUS_DONE and todo.recurrence_template_id is not None and not todo.is_recurrence_template:
                todo.recurrence_type = None
                todo.recurrence_interval = 1
                todo.recurrence_day = None
                todo.recurrence_end_date = None

            if todo.pid is not None:
                parent = self._get_by_id(session, todo.pid)
                if parent and not parent.is_recurrence_template:
                    all_done = self._check_children_all_done(session, todo.pid)
                    if parent.status != (STATUS_DONE if all_done else STATUS_TODO):
                        parent.status = STATUS_DONE if all_done else STATUS_TODO
                        parent.updated_at = datetime.now()
                        parent.completed_at = datetime.now() if all_done else None
            else:
                children = session.query(Todo).filter(Todo.pid == todo.id).all()
                for child in children:
                    child.status = new_status
                    child.updated_at = datetime.now()
                    child.completed_at = datetime.now() if new_status == STATUS_DONE else None

            session.flush()
            return todo

    @staticmethod
    def _check_children_all_done(session, parent_id: int) -> bool:
        """检查父任务下所有子任务是否全部完成"""
        children = session.query(Todo).filter(Todo.pid == parent_id).all()
        if not children:
            return False
        return all(c.status == STATUS_DONE for c in children)

    def get_children_count(self, parent_id: int) -> int:
        with db.session_scope() as session:
            return session.query(Todo).filter(Todo.pid == parent_id).count()

    # ---- 自动延期 ----

    def process_auto_postpone(self) -> int:
        """自动延期过期任务"""
        today = date.today()
        with db.session_scope() as session:
            count = session.query(Todo).filter(
                Todo.pid.is_(None),
                Todo.status == STATUS_TODO,
                Todo.auto_postpone == True,
                Todo.due_date < today,
                Todo.is_recurrence_template == False,
                Todo.recurrence_type.is_(None),
                or_(Todo.task_type != "periodic", Todo.task_type.is_(None)),
            ).update({Todo.due_date: today, Todo.updated_at: datetime.now()},
                     synchronize_session=False)
            session.flush()
            self._ensure_instances(session)
            return count

    # ---- 查询：返回所有任务 ----

    @staticmethod
    def _apply_recurrence_dedup(session, query):
        """在 SQL 层完成循环任务去重，每个 recurrence_template_id 只保留最优实例"""
        today = date.today()
        T2 = Todo.__table__.alias("t2")
        score_expr = case(
            (and_(T2.c.status == STATUS_TODO, T2.c.due_date >= today), literal(0)),
            (and_(T2.c.status == STATUS_TODO, T2.c.due_date < today), literal(1)),
            else_=literal(2),
        )
        distance_expr = func.abs(func.julianday(T2.c.due_date) - func.julianday(today))
        best_id = (
            session.query(T2.c.id)
            .filter(
                T2.c.recurrence_template_id == Todo.recurrence_template_id,
                T2.c.is_recurrence_template == False,
                T2.c.status != STATUS_ARCHIVED,
            )
            .order_by(score_expr.asc(), distance_expr.asc())
            .limit(1)
            .correlate(Todo)
            .scalar_subquery()
        )
        return query.filter(
            (Todo.recurrence_template_id == None) | (Todo.id == best_id)
        )

    @staticmethod
    def _apply_date_filter(query, due_start: date = None, due_end: date = None):
        """应用日期过滤，周期任务按生效区间交集匹配，其他任务按 due_date 范围过滤"""
        # 非周期任务：按 due_date 范围过滤
        non_periodic_cond = []
        if due_start is not None:
            non_periodic_cond.append(Todo.due_date >= due_start)
        if due_end is not None:
            non_periodic_cond.append(Todo.due_date <= due_end)

        # 周期任务：按生效区间与筛选范围的交集匹配
        periodic_cond = []
        if due_start is not None:
            periodic_cond.append(Todo.due_date >= due_start)  # due_date 作为生效结束
        if due_end is not None:
            periodic_cond.append(Todo.start_date <= due_end)  # start_date 作为生效开始

        if non_periodic_cond and periodic_cond:
            query = query.filter(
                or_(
                    and_(Todo.task_type != "periodic", *non_periodic_cond),
                    and_(Todo.task_type == "periodic", *periodic_cond),
                )
            )
        elif non_periodic_cond:
            query = query.filter(
                or_(
                    Todo.task_type == "periodic",
                    and_(*non_periodic_cond),
                )
            )
        return query

    @staticmethod
    def get_periodic_status(todo_or_dict) -> Optional[str]:
        """判断周期任务状态"""
        if isinstance(todo_or_dict, dict):
            task_type = todo_or_dict.get("task_type", "default")
            if task_type != "periodic":
                return None
            start_str = todo_or_dict.get("start_date")
            due_str = todo_or_dict.get("due_date")
            if not start_str or not due_str:
                return None
            try:
                start_date = date.fromisoformat(start_str)
                due_date = date.fromisoformat(due_str)
            except (ValueError, TypeError):
                return None
        else:
            if (todo_or_dict.task_type or "default") != "periodic":
                return None
            start_date = todo_or_dict.start_date
            due_date = todo_or_dict.due_date
            if not start_date or not due_date:
                return None

        today = date.today()
        if today < start_date:
            return "not_started"
        elif today > due_date:
            return "expired"
        else:
            return "active"

    @staticmethod
    def _build_get_all_query(session, status: int = STATUS_TODO,
                            priority: Optional[int] = None, color_tag: Optional[str] = None,
                            category_id: Optional[int] = None,
                            due_start: date = None, due_end: date = None,
                            dedup_recurrence: bool = False):
        query = session.query(Todo).options(
            selectinload(Todo.children),
            joinedload(Todo.category),
        ).filter(
            Todo.status == status,
            Todo.is_recurrence_template == False,
        )

        if priority is not None:
            query = query.filter(Todo.priority == priority)
        if color_tag is not None:
            query = query.filter(Todo.color_tag == color_tag)
        if category_id is not None:
            query = query.filter(Todo.category_id == category_id)
        if due_start is not None or due_end is not None:
            query = TodoService._apply_date_filter(query, due_start, due_end)
        if dedup_recurrence:
            query = TodoService._apply_recurrence_dedup(session, query)
        return query

    def get_all(self, status: int = STATUS_TODO,
                priority: Optional[int] = None, color_tag: Optional[str] = None,
                category_id: Optional[int] = None,
                sort_by: str = "created_at", sort_order: str = "desc",
                sort_rules: list[str] = None,
                page: int = 0, page_size: int = 0,
                due_start: date = None, due_end: date = None,
                dedup_recurrence: bool = False) -> list[Todo]:
        with db.session_scope() as session:
            query = self._build_get_all_query(
                session, status=status, priority=priority, color_tag=color_tag,
                category_id=category_id, due_start=due_start, due_end=due_end,
                dedup_recurrence=dedup_recurrence,
            )

            if sort_rules:
                query = self._apply_multi_sort(query, sort_rules)
            else:
                query = self._apply_sort(query, sort_by, sort_order)

            if page_size > 0:
                query = query.offset(page * page_size).limit(page_size)

            return query.all()

    def get_all_with_count(self, status: int = STATUS_TODO,
                           priority: Optional[int] = None, color_tag: Optional[str] = None,
                           category_id: Optional[int] = None,
                           sort_by: str = "created_at", sort_order: str = "desc",
                           sort_rules: list[str] = None,
                           page: int = 0, page_size: int = 0,
                           due_start: date = None, due_end: date = None,
                           dedup_recurrence: bool = False) -> tuple[list[Todo], int]:
        with db.session_scope() as session:
            query = self._build_get_all_query(
                session, status=status, priority=priority, color_tag=color_tag,
                category_id=category_id, due_start=due_start, due_end=due_end,
                dedup_recurrence=dedup_recurrence,
            )
            total = query.with_entities(func.count(Todo.id)).scalar()

            if sort_rules:
                query = self._apply_multi_sort(query, sort_rules)
            else:
                query = self._apply_sort(query, sort_by, sort_order)

            if page_size > 0:
                query = query.offset(page * page_size).limit(page_size)

            return query.all(), total

    def get_all_including_archived(self) -> list[Todo]:
        """获取所有任务"""
        with db.session_scope() as session:
            return session.query(Todo).options(
                joinedload(Todo.category)
            ).all()

    @staticmethod
    def _build_get_all_including_done_query(session,
                                           category_id: Optional[int] = None,
                                           due_start: date = None, due_end: date = None,
                                           dedup_recurrence: bool = False,
                                           **kwargs):
        query = session.query(Todo).options(
            selectinload(Todo.children),
            joinedload(Todo.category),
        ).filter(
            Todo.status.in_([STATUS_TODO, STATUS_DONE]),
            Todo.is_recurrence_template == False,
        )

        priority = kwargs.get('priority')
        if priority is not None:
            query = query.filter(Todo.priority == priority)
        color_tag = kwargs.get('color_tag')
        if color_tag is not None:
            query = query.filter(Todo.color_tag == color_tag)
        if category_id is not None:
            query = query.filter(Todo.category_id == category_id)
        if due_start is not None or due_end is not None:
            query = TodoService._apply_date_filter(query, due_start, due_end)
        if dedup_recurrence:
            query = TodoService._apply_recurrence_dedup(session, query)
        return query

    def get_all_including_done(self, sort_by: str = "created_at",
                                sort_order: str = "desc",
                                sort_rules: list[str] = None,
                                category_id: Optional[int] = None,
                                page: int = 0, page_size: int = 0,
                                due_start: date = None, due_end: date = None,
                                dedup_recurrence: bool = False,
                                **kwargs) -> list[Todo]:
        """获取所有任务"""
        with db.session_scope() as session:
            query = self._build_get_all_including_done_query(
                session, category_id=category_id, due_start=due_start, due_end=due_end,
                dedup_recurrence=dedup_recurrence, **kwargs,
            )

            if not sort_rules and sort_by == "custom":
                sort_rules = ["custom"]
            if sort_rules:
                sort_exprs = [self._sort_expr_for_field(f) for f in sort_rules]
            else:
                sort_exprs = self._build_sort_expr(sort_by, sort_order)
            query = query.order_by(Todo.status.asc(), *sort_exprs)

            if page_size > 0:
                query = query.offset(page * page_size).limit(page_size)

            return query.all()

    def get_all_including_done_with_count(self, sort_by: str = "created_at",
                                          sort_order: str = "desc",
                                          sort_rules: list[str] = None,
                                          category_id: Optional[int] = None,
                                          page: int = 0, page_size: int = 0,
                                          due_start: date = None, due_end: date = None,
                                          dedup_recurrence: bool = False,
                                          **kwargs) -> tuple[list[Todo], int]:
        with db.session_scope() as session:
            query = self._build_get_all_including_done_query(
                session, category_id=category_id, due_start=due_start, due_end=due_end,
                dedup_recurrence=dedup_recurrence, **kwargs,
            )
            total = query.with_entities(func.count(Todo.id)).scalar()

            if not sort_rules and sort_by == "custom":
                sort_rules = ["custom"]
            if sort_rules:
                sort_exprs = [self._sort_expr_for_field(f) for f in sort_rules]
            else:
                sort_exprs = self._build_sort_expr(sort_by, sort_order)
            query = query.order_by(Todo.status.asc(), *sort_exprs)

            if page_size > 0:
                query = query.offset(page * page_size).limit(page_size)

            return query.all(), total

    @staticmethod
    def _build_count_query(session, status=None, status_list=None,
                           priority: Optional[int] = None,
                           priority_op: str = "==",
                           color_tag: Optional[str] = None,
                           category_id: Optional[int] = None,
                           due_date=None, due_date_lt=None,
                           exclude_recurrence: bool = False,
                           due_start: date = None, due_end: date = None):
        """构建计数查询的通用方法"""
        query = session.query(func.count(Todo.id)).filter(
            Todo.is_recurrence_template == False,
        )
        if status is not None:
            query = query.filter(Todo.status == status)
        if status_list is not None:
            query = query.filter(Todo.status.in_(status_list))
        if priority is not None:
            if priority_op == "!=":
                query = query.filter(Todo.priority != priority)
            else:
                query = query.filter(Todo.priority == priority)
        if color_tag is not None:
            query = query.filter(Todo.color_tag == color_tag)
        if category_id is not None:
            query = query.filter(Todo.category_id == category_id)
        if due_date is not None:
            query = query.filter(Todo.due_date == due_date)
        if due_date_lt is not None:
            query = query.filter(Todo.due_date < due_date_lt)
            if exclude_recurrence:
                query = query.filter(Todo.recurrence_type.is_(None))
        if due_start is not None:
            query = query.filter(Todo.due_date >= due_start)
        if due_end is not None:
            query = query.filter(Todo.due_date <= due_end)
        return query.scalar()

    def count_filtered(self, status: int = STATUS_TODO,
                       priority: Optional[int] = None,
                       color_tag: Optional[str] = None,
                       category_id: Optional[int] = None,
                       due_start: date = None, due_end: date = None) -> int:
        with db.session_scope() as session:
            return self._build_count_query(session, status=status, priority=priority,
                                           color_tag=color_tag, category_id=category_id,
                                           due_start=due_start, due_end=due_end)

    def count_filtered_including_done(self,
                                      priority: Optional[int] = None,
                                      color_tag: Optional[str] = None,
                                      category_id: Optional[int] = None,
                                      due_start: date = None, due_end: date = None) -> int:
        with db.session_scope() as session:
            return self._build_count_query(session, status_list=[STATUS_TODO, STATUS_DONE],
                                           priority=priority, color_tag=color_tag,
                                           category_id=category_id,
                                           due_start=due_start, due_end=due_end)

    @staticmethod
    def _apply_sort(query, sort_by: str = "created_at", sort_order: str = "desc"):
        """应用排序规则"""
        sort_expr = TodoService._build_sort_expr(sort_by, sort_order)
        return query.order_by(*sort_expr)

    @staticmethod
    def _sort_expr_for_field(field: str):
        """根据字段名返回排序表达式（降序）"""
        if field == "custom":
            return Todo.sort_order.asc()
        elif field == "priority":
            return Todo.priority.asc()
        elif field == "due_date":
            return Todo.due_date.asc().nullslast()
        else:
            return Todo.created_at.desc()

    @staticmethod
    def _build_sort_expr(sort_by: str, sort_order: str):
        """构建排序表达式"""
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
                return [Todo.created_at.asc(), Todo.priority.asc()]
            else:
                return [Todo.created_at.desc(), Todo.priority.asc()]

    @staticmethod
    def _apply_multi_sort(query, sort_rules: list[str]):
        """应用多级排序规则"""
        if not sort_rules:
            return query
        seen = set()
        exprs = []
        for field in sort_rules:
            if field not in seen:
                seen.add(field)
                exprs.append(TodoService._sort_expr_for_field(field))
        return query.order_by(*exprs)

    @staticmethod
    def _build_today_query(session):
        today = date.today()
        return session.query(Todo).options(
            selectinload(Todo.children),
            joinedload(Todo.category),
        ).filter(
            Todo.status == STATUS_TODO,
            Todo.due_date == today,
            Todo.is_recurrence_template == False,
        )

    def get_today(self, page: int = 0, page_size: int = 0) -> list[Todo]:
        """获取今日到期的所有任务"""
        with db.session_scope() as session:
            query = self._build_today_query(session).order_by(Todo.priority.asc(), Todo.created_at.desc())
            if page_size > 0:
                query = query.offset(page * page_size).limit(page_size)
            return query.all()

    def get_today_with_count(self, page: int = 0, page_size: int = 0) -> tuple[list[Todo], int]:
        with db.session_scope() as session:
            query = self._build_today_query(session)
            total = query.with_entities(func.count(Todo.id)).scalar()
            query = query.order_by(Todo.priority.asc(), Todo.created_at.desc())
            if page_size > 0:
                query = query.offset(page * page_size).limit(page_size)
            return query.all(), total

    @staticmethod
    def _build_high_priority_query(session, due_start: date = None, due_end: date = None,
                                    dedup_recurrence: bool = False,
                                    include_done: bool = False):
        status_filter = Todo.status.in_([STATUS_TODO, STATUS_DONE]) if include_done else Todo.status == STATUS_TODO
        query = session.query(Todo).options(
            selectinload(Todo.children),
            joinedload(Todo.category),
        ).filter(
            status_filter,
            Todo.priority != PRIORITY_NONE,
            Todo.is_recurrence_template == False,
        )
        if due_start is not None or due_end is not None:
            query = TodoService._apply_date_filter(query, due_start, due_end)
        if dedup_recurrence:
            query = TodoService._apply_recurrence_dedup(session, query)
        return query

    def get_high_priority(self, page: int = 0, page_size: int = 0,
                          due_start: date = None, due_end: date = None,
                          dedup_recurrence: bool = False) -> list[Todo]:
        with db.session_scope() as session:
            query = self._build_high_priority_query(session, due_start=due_start, due_end=due_end,
                                                    dedup_recurrence=dedup_recurrence)
            query = query.order_by(Todo.priority.asc(), Todo.created_at.desc())
            if page_size > 0:
                query = query.offset(page * page_size).limit(page_size)
            return query.all()

    def get_high_priority_including_done(self, page: int = 0, page_size: int = 0,
                                          due_start: date = None, due_end: date = None,
                                          dedup_recurrence: bool = False) -> list[Todo]:
        with db.session_scope() as session:
            query = self._build_high_priority_query(session, due_start=due_start, due_end=due_end,
                                                    dedup_recurrence=dedup_recurrence,
                                                    include_done=True)
            query = query.order_by(Todo.priority.asc(), Todo.created_at.desc())
            if page_size > 0:
                query = query.offset(page * page_size).limit(page_size)
            return query.all()

    def get_high_priority_with_count(self, page: int = 0, page_size: int = 0,
                                     due_start: date = None, due_end: date = None,
                                     dedup_recurrence: bool = False) -> tuple[list[Todo], int]:
        with db.session_scope() as session:
            query = self._build_high_priority_query(session, due_start=due_start, due_end=due_end,
                                                    dedup_recurrence=dedup_recurrence)
            total = query.with_entities(func.count(Todo.id)).scalar()
            query = query.order_by(Todo.priority.asc(), Todo.created_at.desc())
            if page_size > 0:
                query = query.offset(page * page_size).limit(page_size)
            return query.all(), total

    def get_high_priority_including_done_with_count(self, page: int = 0, page_size: int = 0,
                                                     due_start: date = None, due_end: date = None,
                                                     dedup_recurrence: bool = False) -> tuple[list[Todo], int]:
        with db.session_scope() as session:
            query = self._build_high_priority_query(session, due_start=due_start, due_end=due_end,
                                                    dedup_recurrence=dedup_recurrence,
                                                    include_done=True)
            total = query.with_entities(func.count(Todo.id)).scalar()
            query = query.order_by(Todo.priority.asc(), Todo.created_at.desc())
            if page_size > 0:
                query = query.offset(page * page_size).limit(page_size)
            return query.all(), total

    @staticmethod
    def _build_by_category_query(session, category_id: int,
                                  due_start: date = None, due_end: date = None,
                                  dedup_recurrence: bool = False):
        query = session.query(Todo).options(
            selectinload(Todo.children),
            joinedload(Todo.category),
        ).filter(
            Todo.status == STATUS_TODO,
            Todo.category_id == category_id,
            Todo.is_recurrence_template == False,
        )
        if due_start is not None or due_end is not None:
            query = TodoService._apply_date_filter(query, due_start, due_end)
        if dedup_recurrence:
            query = TodoService._apply_recurrence_dedup(session, query)
        return query

    def get_by_category(self, category_id: int, page: int = 0, page_size: int = 0,
                        due_start: date = None, due_end: date = None,
                        dedup_recurrence: bool = False) -> list[Todo]:
        with db.session_scope() as session:
            query = self._build_by_category_query(session, category_id, due_start=due_start, due_end=due_end,
                                                  dedup_recurrence=dedup_recurrence)
            query = query.order_by(Todo.created_at.desc())
            if page_size > 0:
                query = query.offset(page * page_size).limit(page_size)
            return query.all()

    def get_by_category_with_count(self, category_id: int, page: int = 0, page_size: int = 0,
                                    due_start: date = None, due_end: date = None,
                                    dedup_recurrence: bool = False) -> tuple[list[Todo], int]:
        with db.session_scope() as session:
            query = self._build_by_category_query(session, category_id, due_start=due_start, due_end=due_end,
                                                  dedup_recurrence=dedup_recurrence)
            total = query.with_entities(func.count(Todo.id)).scalar()
            query = query.order_by(Todo.created_at.desc())
            if page_size > 0:
                query = query.offset(page * page_size).limit(page_size)
            return query.all(), total

    def get_overdue(self) -> list[Todo]:
        """获取已过期的所有任务（排除模板和重复实例）"""
        today = date.today()
        with db.session_scope() as session:
            return session.query(Todo).options(
                selectinload(Todo.children),
                joinedload(Todo.category),
            ).filter(
                Todo.status == STATUS_TODO,
                Todo.due_date < today,
                Todo.is_recurrence_template == False,
                Todo.recurrence_type.is_(None),
            ).order_by(Todo.due_date.asc()).all()

    # ---- 统计 ----

    def count_by_status(self, status: int) -> int:
        """统计父任务数量"""
        with db.session_scope() as session:
            return session.query(Todo).filter(
                Todo.pid.is_(None),
                Todo.status == status,
                Todo.is_recurrence_template == False,
            ).count()

    def count_today(self) -> int:
        today = date.today()
        with db.session_scope() as session:
            return session.query(Todo).filter(
                Todo.pid.is_(None),
                Todo.status == STATUS_TODO,
                Todo.due_date == today,
                Todo.is_recurrence_template == False,
            ).count()

    def count_overdue(self) -> int:
        today = date.today()
        with db.session_scope() as session:
            return session.query(Todo).filter(
                Todo.pid.is_(None),
                Todo.status == STATUS_TODO,
                Todo.due_date < today,
                Todo.is_recurrence_template == False,
                Todo.recurrence_type.is_(None),
            ).count()

    def count_all_view_stats(self, due_start: date = None, due_end: date = None) -> dict:
        """统计全部任务视图的数据（仅父任务）：总数、已完成数和已超期数"""
        today = date.today()
        with db.session_scope() as session:
            base = session.query(Todo).filter(
                Todo.pid.is_(None),
                Todo.is_recurrence_template == False,
            )
            if due_start is not None or due_end is not None:
                base = self._apply_date_filter(base, due_start, due_end)

            all_count = base.filter(Todo.status.in_([STATUS_TODO, STATUS_DONE])).count()
            done_count = base.filter(Todo.status == STATUS_DONE).count()
            overdue_count = base.filter(
                Todo.status == STATUS_TODO,
                Todo.due_date < today,
            ).count()
            return {"all_count": all_count, "done_count": done_count, "overdue_count": overdue_count}

    def count_today_view_stats(self) -> dict:
        """统计今日任务视图的数据（仅父任务）：已完成数"""
        today = date.today()
        with db.session_scope() as session:
            done_count = session.query(Todo).filter(
                Todo.pid.is_(None),
                Todo.status == STATUS_DONE,
                Todo.due_date == today,
                Todo.is_recurrence_template == False,
            ).count()
            return {"done_count": done_count}

    def count_today_all(self) -> int:
        """统计今日到期的任务总数"""
        today = date.today()
        with db.session_scope() as session:
            return self._build_count_query(session, status=STATUS_TODO, due_date=today)

    def count_high_priority(self, due_start: date = None, due_end: date = None) -> int:
        with db.session_scope() as session:
            return self._build_count_query(session, status=STATUS_TODO, priority=PRIORITY_NONE,
                                           priority_op="!=", due_start=due_start, due_end=due_end)

    def count_by_category(self, category_id: int,
                          due_start: date = None, due_end: date = None) -> int:
        with db.session_scope() as session:
            return self._build_count_query(session, status=STATUS_TODO, category_id=category_id,
                                           due_start=due_start, due_end=due_end)

    # ---- 清理 ----

    def clear_completed(self) -> int:
        """清除所有已完成的父任务"""
        with db.session_scope() as session:
            count = session.query(Todo).filter(
                Todo.pid.is_(None),
                Todo.status == STATUS_DONE,
                Todo.is_recurrence_template == False,
            ).delete(synchronize_session=False)
            return count

    def archive_all_done(self) -> int:
        """归档所有已完成的任务"""
        with db.session_scope() as session:
            count = session.query(Todo).filter(
                Todo.status == STATUS_DONE,
                Todo.is_recurrence_template == False,
            ).update({Todo.status: STATUS_ARCHIVED, Todo.updated_at: datetime.now()},
                     synchronize_session=False)
            return count

    def reorder(self, todo_ids: list[int]):
        """重新排序父任务"""
        with db.session_scope() as session:
            for order, todo_id in enumerate(todo_ids):
                todo = session.query(Todo).filter(Todo.id == todo_id).first()
                if todo:
                    todo.sort_order = order * 10

    # ---- 重复任务：模板+实例 ----

    def _ensure_instances(self, session, template_id: int = None):
        """为模板生成 [today, today+14] 范围内缺失的实例"""
        from services.recurrence_utils import generate_occurrences
        from services.holiday_service import holiday_service
        today = date.today()
        end = today + timedelta(days=INSTANCE_WINDOW_DAYS)

        if template_id:
            templates = [session.query(Todo).filter(
                Todo.id == template_id,
                Todo.is_recurrence_template == True,
            ).first()]
            templates = [t for t in templates if t]
        else:
            templates = session.query(Todo).filter(
                Todo.is_recurrence_template == True,
            ).all()

        for tmpl in templates:
            if not tmpl.due_date or not tmpl.recurrence_type:
                continue
            # 工作日重复需要节日数据，如果获取不到则跳过此模板
            if tmpl.recurrence_type == "workday":
                holiday_service.load_for_date(today)
                if not holiday_service.has_data_for_year(today.year):
                    logger.warning(f"模板 {tmpl.id} 为工作日重复，但无法获取节日数据，跳过生成")
                    continue
            # 重复序列起点：优先使用 recurrence_start_date，否则使用 due_date
            start_date = tmpl.recurrence_start_date or tmpl.due_date
            occurrences = generate_occurrences(
                start_date, today, end,
                tmpl.recurrence_type, tmpl.recurrence_interval,
                tmpl.recurrence_end_date, tmpl.recurrence_day,
            )
            existing_dates = {r[0] for r in session.query(
                Todo.occurrence_date
            ).filter(
                Todo.recurrence_template_id == tmpl.id,
                Todo.occurrence_date.in_(occurrences),
            ).all()} if occurrences else set()

            for occ_date in occurrences:
                if occ_date not in existing_dates:
                    self._create_instance_from_template(session, tmpl, occ_date)

    @staticmethod
    def _create_instance_from_template(session, template: Todo, occurrence_date: date) -> Todo:
        """从模板创建一个实例及其子任务蓝图副本"""
        instance = Todo(
            title=template.title,
            description=template.description,
            priority=template.priority,
            status=STATUS_TODO,
            color_tag=template.color_tag,
            start_date=TodoService._coerce_date(template.start_date, 'start_date'),
            due_date=occurrence_date,
            task_type=template.task_type or "recurrence",
            auto_postpone=False,
            sort_order=template.sort_order,
            category_id=template.category_id,
            recurrence_type=template.recurrence_type,
            recurrence_interval=template.recurrence_interval,
            recurrence_day=template.recurrence_day,
            recurrence_start_date=TodoService._coerce_date(template.recurrence_start_date, 'recurrence_start_date'),
            recurrence_end_date=TodoService._coerce_date(template.recurrence_end_date, 'recurrence_end_date'),
            is_recurrence_template=False,
            recurrence_template_id=template.id,
            occurrence_date=occurrence_date,
        )
        session.add(instance)
        session.flush()

        blueprints = session.query(Todo).filter(Todo.pid == template.id).all()
        for bp in blueprints:
            child = Todo(
                title=bp.title,
                description=bp.description,
                priority=bp.priority,
                status=STATUS_TODO,
                color_tag=bp.color_tag,
                sort_order=bp.sort_order,
                category_id=bp.category_id,
                pid=instance.id,
            )
            session.add(child)

        return instance

    def get_template_for_instance(self, instance: Todo) -> Optional[Todo]:
        """获取实例对应的模板"""
        if not instance.recurrence_template_id:
            return None
        with db.session_scope() as session:
            return session.query(Todo).options(
                joinedload(Todo.category)
            ).filter(
                Todo.id == instance.recurrence_template_id
            ).first()

    def get_all_templates(self) -> list[Todo]:
        """获取所有重复模板"""
        with db.session_scope() as session:
            return session.query(Todo).options(
                joinedload(Todo.category)
            ).filter(
                Todo.is_recurrence_template == True,
            ).all()

    def update_template(self, template_id: int, apply_to_future_only: bool = False, **kwargs):
        """更新模板并重新生成实例"""
        with db.session_scope() as session:
            template = session.query(Todo).filter(Todo.id == template_id).first()
            if not template:
                return None

            for key, value in kwargs.items():
                if hasattr(template, key):
                    setattr(template, key, value)
            template.updated_at = datetime.now()

            today = date.today()
            if apply_to_future_only:
                session.query(Todo).filter(
                    Todo.recurrence_template_id == template_id,
                    Todo.occurrence_date > today,
                    Todo.is_exception == False,
                ).delete(synchronize_session=False)
            else:
                session.query(Todo).filter(
                    Todo.recurrence_template_id == template_id,
                    Todo.is_exception == False,
                ).delete(synchronize_session=False)

            session.flush()
            self._ensure_instances(session, template_id)
            return template

    def get_affected_instance_ids(self, todo_id: int, mode: str) -> list[int]:
        with db.session_scope() as session:
            instance = self._get_by_id(session, todo_id)
            if not instance:
                return [todo_id]

            template_id = instance.recurrence_template_id
            ids = [todo_id]

            if mode == "this_and_future" and template_id:
                occ_date = instance.occurrence_date or instance.due_date
                future = session.query(Todo).filter(
                    Todo.recurrence_template_id == template_id,
                    Todo.occurrence_date >= occ_date,
                    Todo.id != todo_id,
                ).all()
                ids.extend([t.id for t in future])
            elif mode == "all" and template_id:
                all_instances = session.query(Todo).filter(
                    Todo.recurrence_template_id == template_id,
                    Todo.id != todo_id,
                ).all()
                ids.extend([t.id for t in all_instances])
                ids.append(template_id)

            return ids

    def delete_instance(self, todo_id: int, mode: str = "this") -> bool:
        """删除重复实例: this=仅此次, this_and_future=此次及之后, all=删除模板和所有实例"""
        with db.session_scope() as session:
            instance = self._get_by_id(session, todo_id)
            if not instance:
                return False

            template_id = instance.recurrence_template_id

            if mode == "this":
                session.query(Todo).filter(Todo.pid == todo_id).delete(synchronize_session=False)
                session.delete(instance)
                return True

            if not template_id:
                session.query(Todo).filter(Todo.pid == todo_id).delete(synchronize_session=False)
                session.delete(instance)
                return True

            template = self._get_by_id(session, template_id)

            if mode == "this_and_future":
                occ_date = instance.occurrence_date or instance.due_date
                future_instances = session.query(Todo).filter(
                    Todo.recurrence_template_id == template_id,
                    Todo.occurrence_date >= occ_date,
                ).all()
                for inst in future_instances:
                    session.query(Todo).filter(Todo.pid == inst.id).delete(synchronize_session=False)
                    session.delete(inst)
                if template:
                    template.recurrence_end_date = occ_date - timedelta(days=1)
                    template.updated_at = datetime.now()
                return True

            if mode == "all":
                all_instances = session.query(Todo).filter(
                    Todo.recurrence_template_id == template_id,
                ).all()
                for inst in all_instances:
                    session.query(Todo).filter(Todo.pid == inst.id).delete(synchronize_session=False)
                    session.delete(inst)
                if template:
                    session.query(Todo).filter(Todo.pid == template.id).delete(synchronize_session=False)
                    session.delete(template)
                return True

            return False

    def split_and_update_from_instance(self, instance_id: int, **kwargs) -> Optional[Todo]:
        """拆分重复系列：从当前实例起，用新属性创建新模板并生成后续实例"""
        with db.session_scope() as session:
            instance = self._get_by_id(session, instance_id)
            if not instance or not instance.recurrence_template_id:
                return None

            old_template = self._get_by_id(session, instance.recurrence_template_id)
            if not old_template:
                return None

            occ_date = instance.occurrence_date or instance.due_date

            old_template.recurrence_end_date = occ_date - timedelta(days=1)
            old_template.updated_at = datetime.now()

            future_instances = session.query(Todo).filter(
                Todo.recurrence_template_id == old_template.id,
                Todo.occurrence_date >= occ_date,
            ).all()
            for inst in future_instances:
                session.query(Todo).filter(Todo.pid == inst.id).delete(synchronize_session=False)
                session.delete(inst)

            new_template = Todo(
                title=kwargs.get("title", old_template.title),
                description=kwargs.get("description", old_template.description),
                priority=kwargs.get("priority", old_template.priority),
                status=STATUS_TODO,
                color_tag=kwargs.get("color_tag", old_template.color_tag),
                start_date=self._coerce_date(kwargs.get("start_date", old_template.start_date), 'start_date'),
                due_date=occ_date,
                task_type=kwargs.get("task_type") or old_template.task_type or "recurrence",
                auto_postpone=False,
                sort_order=old_template.sort_order,
                category_id=kwargs.get("category_id", old_template.category_id),
                recurrence_type=kwargs.get("recurrence_type", old_template.recurrence_type),
                recurrence_interval=kwargs.get("recurrence_interval", old_template.recurrence_interval),
                recurrence_day=kwargs.get("recurrence_day", old_template.recurrence_day),
                recurrence_start_date=self._coerce_date(kwargs.get("recurrence_start_date", old_template.recurrence_start_date), 'recurrence_start_date'),
                recurrence_end_date=self._coerce_date(kwargs.get("recurrence_end_date", old_template.recurrence_end_date), 'recurrence_end_date'),
                is_recurrence_template=True,
            )
            session.add(new_template)
            session.flush()

            for child in (old_template.children or []):
                bp = Todo(
                    title=child.title,
                    description=child.description,
                    priority=child.priority,
                    status=STATUS_TODO,
                    color_tag=child.color_tag,
                    sort_order=child.sort_order,
                    category_id=child.category_id,
                    pid=new_template.id,
                )
                session.add(bp)

            self._ensure_instances(session, new_template.id)
            return new_template

    def cleanup_old_instances(self, days_before: int = 30):
        """清理过期的已完成实例（仅清理仍为重复实例的，已转为普通任务的不清理）"""
        cutoff = date.today() - timedelta(days=days_before)
        with db.session_scope() as session:
            old_instances = session.query(Todo).filter(
                Todo.recurrence_template_id.isnot(None),
                Todo.recurrence_type.isnot(None),
                Todo.occurrence_date < cutoff,
                Todo.status == STATUS_DONE,
            ).all()
            for inst in old_instances:
                session.query(Todo).filter(Todo.pid == inst.id).delete(synchronize_session=False)
                session.delete(inst)
