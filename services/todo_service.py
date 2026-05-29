"""Todo 业务逻辑服务"""
from __future__ import annotations
from datetime import datetime, date, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from models.database import db
from models.todo import Todo
from config.constants import STATUS_TODO, STATUS_DONE, STATUS_ARCHIVED, PRIORITY_HIGH

INSTANCE_WINDOW_DAYS = 14


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
        """创建待办事项。有重复规则且为顶级任务时，创建模板+生成实例"""
        if due_date is not None and hasattr(due_date, 'year') and not isinstance(due_date, date):
            from datetime import date as pydate
            due_date = pydate(due_date.year(), due_date.month(), due_date.day())

        if recurrence_end_date is not None and hasattr(recurrence_end_date, 'year') and not isinstance(recurrence_end_date, date):
            from datetime import date as pydate
            recurrence_end_date = pydate(recurrence_end_date.year(), recurrence_end_date.month(), recurrence_end_date.day())

        is_template = bool(recurrence_type and pid is None)

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
            is_recurrence_template=is_template,
        )
        self.session.add(todo)
        self.session.commit()
        self.session.refresh(todo)

        if is_template:
            self.ensure_instances(todo.id)

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

        if todo.status == STATUS_TODO:
            new_status = STATUS_DONE
        elif todo.status == STATUS_DONE:
            new_status = STATUS_TODO
        else:
            return todo

        todo.status = new_status
        todo.updated_at = datetime.now()

        if todo.pid is not None:
            parent = self.get_by_id(todo.pid)
            if parent and not parent.is_recurrence_template:
                all_done = self._check_children_all_done(todo.pid)
                if parent.status != (STATUS_DONE if all_done else STATUS_TODO):
                    parent.status = STATUS_DONE if all_done else STATUS_TODO
                    parent.updated_at = datetime.now()
        else:
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
        """自动延期过期任务（排除模板和重复实例），并生成重复实例"""
        today = date.today()
        count = self.session.query(Todo).filter(
            Todo.pid.is_(None),
            Todo.status == STATUS_TODO,
            Todo.auto_postpone == True,
            Todo.due_date < today,
            Todo.is_recurrence_template == False,
            Todo.recurrence_template_id.is_(None),
        ).update({Todo.due_date: today, Todo.updated_at: datetime.now()},
                 synchronize_session=False)
        self.session.commit()
        self.ensure_instances()
        return count

    # ---- 查询：返回所有任务（含子任务） ----
    def get_all(self, status: int = STATUS_TODO,
                priority: Optional[int] = None, color_tag: Optional[str] = None,
                category_id: Optional[int] = None,
                sort_by: str = "created_at", sort_order: str = "desc",
                sort_rules: list[str] = None) -> list[Todo]:
        query = self.session.query(Todo).filter(
            Todo.status == status,
            Todo.is_recurrence_template == False,
        )

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
        """获取今日到期的所有任务（实例已通过 ensure_instances 生成）"""
        today = date.today()
        return self.session.query(Todo).filter(
            Todo.status == STATUS_TODO,
            Todo.due_date == today,
            Todo.is_recurrence_template == False,
        ).order_by(Todo.priority.desc(), Todo.created_at.desc()).all()

    def get_high_priority(self) -> list[Todo]:
        """获取高优先级所有任务"""
        return self.session.query(Todo).filter(
            Todo.status == STATUS_TODO,
            Todo.priority == PRIORITY_HIGH,
            Todo.is_recurrence_template == False,
        ).order_by(Todo.created_at.desc()).all()

    def get_by_category(self, category_id: int) -> list[Todo]:
        """获取指定分类的所有任务"""
        return self.session.query(Todo).filter(
            Todo.status == STATUS_TODO,
            Todo.category_id == category_id,
            Todo.is_recurrence_template == False,
        ).order_by(Todo.created_at.desc()).all()

    def get_overdue(self) -> list[Todo]:
        """获取已过期的所有任务（排除模板和重复实例）"""
        today = date.today()
        return self.session.query(Todo).filter(
            Todo.status == STATUS_TODO,
            Todo.due_date < today,
            Todo.is_recurrence_template == False,
            Todo.recurrence_template_id.is_(None),
        ).order_by(Todo.due_date.asc()).all()

    # ---- 统计 ----

    def count_by_status(self, status: int) -> int:
        """统计父任务数量（不含模板）"""
        return self.session.query(Todo).filter(
            Todo.pid.is_(None),
            Todo.status == status,
            Todo.is_recurrence_template == False,
        ).count()

    def count_today(self) -> int:
        today = date.today()
        return self.session.query(Todo).filter(
            Todo.pid.is_(None),
            Todo.status == STATUS_TODO,
            Todo.due_date == today,
            Todo.is_recurrence_template == False,
        ).count()

    def count_overdue(self) -> int:
        today = date.today()
        return self.session.query(Todo).filter(
            Todo.pid.is_(None),
            Todo.status == STATUS_TODO,
            Todo.due_date < today,
            Todo.is_recurrence_template == False,
            Todo.recurrence_template_id.is_(None),
        ).count()

    # ---- 清理 ----

    def clear_completed(self) -> int:
        """清除所有已完成的父任务（子任务级联删除，不含模板）"""
        count = self.session.query(Todo).filter(
            Todo.pid.is_(None),
            Todo.status == STATUS_DONE,
            Todo.is_recurrence_template == False,
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

    # ---- 重复任务：模板+实例 ----

    def ensure_instances(self, template_id: int = None):
        """为模板生成 [today, today+14] 范围内缺失的实例"""
        from services.recurrence_utils import generate_occurrences
        today = date.today()
        end = today + timedelta(days=INSTANCE_WINDOW_DAYS)

        if template_id:
            templates = [self.session.query(Todo).filter(
                Todo.id == template_id,
                Todo.is_recurrence_template == True,
            ).first()]
            templates = [t for t in templates if t]
        else:
            templates = self.session.query(Todo).filter(
                Todo.is_recurrence_template == True,
            ).all()

        for tmpl in templates:
            if not tmpl.due_date or not tmpl.recurrence_type:
                continue
            occurrences = generate_occurrences(
                tmpl.due_date, today, end,
                tmpl.recurrence_type, tmpl.recurrence_interval,
                tmpl.recurrence_end_date, tmpl.recurrence_day,
            )
            existing_dates = {r[0] for r in self.session.query(
                Todo.occurrence_date
            ).filter(
                Todo.recurrence_template_id == tmpl.id,
                Todo.occurrence_date.in_(occurrences),
            ).all()} if occurrences else set()

            for occ_date in occurrences:
                if occ_date not in existing_dates:
                    self._create_instance_from_template(tmpl, occ_date)

        self.session.commit()

    def _create_instance_from_template(self, template: Todo, occurrence_date: date) -> Todo:
        """从模板创建一个实例及其子任务蓝图副本"""
        instance = Todo(
            title=template.title,
            description=template.description,
            priority=template.priority,
            status=STATUS_TODO,
            color_tag=template.color_tag,
            due_date=occurrence_date,
            auto_postpone=False,
            sort_order=template.sort_order,
            category_id=template.category_id,
            recurrence_type=template.recurrence_type,
            recurrence_interval=template.recurrence_interval,
            recurrence_day=template.recurrence_day,
            recurrence_end_date=template.recurrence_end_date,
            is_recurrence_template=False,
            recurrence_template_id=template.id,
            occurrence_date=occurrence_date,
        )
        self.session.add(instance)
        self.session.flush()

        blueprints = self.session.query(Todo).filter(Todo.pid == template.id).all()
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
            self.session.add(child)

        return instance

    def get_template_for_instance(self, instance: Todo) -> Optional[Todo]:
        """获取实例对应的模板"""
        if not instance.recurrence_template_id:
            return None
        return self.session.query(Todo).filter(
            Todo.id == instance.recurrence_template_id
        ).first()

    def get_all_templates(self) -> list[Todo]:
        """获取所有重复模板"""
        return self.session.query(Todo).filter(
            Todo.is_recurrence_template == True,
        ).all()

    def update_template(self, template_id: int, apply_to_future_only: bool = False, **kwargs):
        """更新模板并重新生成实例"""
        template = self.session.query(Todo).filter(Todo.id == template_id).first()
        if not template:
            return None

        for key, value in kwargs.items():
            if hasattr(template, key):
                setattr(template, key, value)
        template.updated_at = datetime.now()

        today = date.today()
        if apply_to_future_only:
            self.session.query(Todo).filter(
                Todo.recurrence_template_id == template_id,
                Todo.occurrence_date > today,
                Todo.is_exception == False,
            ).delete(synchronize_session=False)
        else:
            self.session.query(Todo).filter(
                Todo.recurrence_template_id == template_id,
                Todo.is_exception == False,
            ).delete(synchronize_session=False)

        self.session.commit()
        self.ensure_instances(template_id)
        return template

    def delete_instance(self, todo_id: int, mode: str = "this") -> bool:
        """删除重复实例: this=仅此次, this_and_future=此次及之后, all=删除模板和所有实例"""
        instance = self.get_by_id(todo_id)
        if not instance:
            return False

        template_id = instance.recurrence_template_id

        if mode == "this":
            self.session.query(Todo).filter(Todo.pid == todo_id).delete(synchronize_session=False)
            self.session.delete(instance)
            self.session.commit()
            return True

        if not template_id:
            self.session.query(Todo).filter(Todo.pid == todo_id).delete(synchronize_session=False)
            self.session.delete(instance)
            self.session.commit()
            return True

        template = self.get_by_id(template_id)

        if mode == "this_and_future":
            occ_date = instance.occurrence_date or instance.due_date
            future_instances = self.session.query(Todo).filter(
                Todo.recurrence_template_id == template_id,
                Todo.occurrence_date >= occ_date,
            ).all()
            for inst in future_instances:
                self.session.query(Todo).filter(Todo.pid == inst.id).delete(synchronize_session=False)
                self.session.delete(inst)
            if template:
                template.recurrence_end_date = occ_date - timedelta(days=1)
                template.updated_at = datetime.now()
            self.session.commit()
            return True

        if mode == "all":
            all_instances = self.session.query(Todo).filter(
                Todo.recurrence_template_id == template_id,
            ).all()
            for inst in all_instances:
                self.session.query(Todo).filter(Todo.pid == inst.id).delete(synchronize_session=False)
                self.session.delete(inst)
            if template:
                self.session.query(Todo).filter(Todo.pid == template.id).delete(synchronize_session=False)
                self.session.delete(template)
            self.session.commit()
            return True

        return False

    def cleanup_old_instances(self, days_before: int = 30):
        """清理过期的已完成实例"""
        cutoff = date.today() - timedelta(days=days_before)
        old_instances = self.session.query(Todo).filter(
            Todo.recurrence_template_id.isnot(None),
            Todo.occurrence_date < cutoff,
            Todo.status == STATUS_DONE,
        ).all()
        for inst in old_instances:
            self.session.query(Todo).filter(Todo.pid == inst.id).delete(synchronize_session=False)
            self.session.delete(inst)
        self.session.commit()

    def close(self):
        """关闭会话"""
        try:
            self.session.close()
        except Exception:
            pass
