"""数据库连接与会话管理"""
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from config.constants import APP_ID


class Base(DeclarativeBase):
    pass


class Database:
    """数据库对象"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        db_dir = Path.home() / f".{APP_ID}"
        db_dir.mkdir(parents=True, exist_ok=True)
        db_path = db_dir / "todo_v3.db"

        self.engine = create_engine(
            f"sqlite:///{db_path}",
            echo=False,
            pool_pre_ping=True,
        )
        self.SessionLocal = sessionmaker(
            bind=self.engine,
            expire_on_commit=False,
        )

    def create_tables(self):
        """创建所有数据表"""
        # 导入所有模型以确保表被创建
        from models.todo import Todo  # noqa: F401
        from models.category import Category  # noqa: F401
        from models.recurrence_completion import RecurrenceCompletion  # noqa: F401

        Base.metadata.create_all(self.engine)
        self._migrate_add_category_id()
        self._migrate_add_pid()
        self._migrate_add_recurrence()
        self._migrate_add_recurrence_day()
        self._migrate_add_category_is_system()
        self._init_default_categories()

    def _migrate_add_category_id(self):
        """迁移：为 todos 表添加 category_id 列"""
        from sqlalchemy import inspect, text

        inspector = inspect(self.engine)
        columns = [c["name"] for c in inspector.get_columns("todos")]
        if "category_id" not in columns:
            with self.engine.connect() as conn:
                conn.execute(text(
                    "ALTER TABLE todos ADD COLUMN category_id INTEGER REFERENCES categories(id)"
                ))
                conn.commit()

    def _migrate_add_pid(self):
        """迁移：为 todos 表添加 pid 列（父任务ID）"""
        from sqlalchemy import inspect, text

        inspector = inspect(self.engine)
        columns = [c["name"] for c in inspector.get_columns("todos")]
        print(f"[DB Migration] Current columns: {columns}")
        if "pid" not in columns:
            print("[DB Migration] Adding pid column...")
            with self.engine.connect() as conn:
                conn.execute(text(
                    "ALTER TABLE todos ADD COLUMN pid INTEGER REFERENCES todos(id) ON DELETE CASCADE"
                ))
                conn.commit()
            print("[DB Migration] pid column added successfully")
        else:
            print("[DB Migration] pid column already exists")

    def _migrate_add_recurrence(self):
        """迁移：为 todos 表添加重复任务相关列"""
        from sqlalchemy import inspect, text

        inspector = inspect(self.engine)
        columns = [c["name"] for c in inspector.get_columns("todos")]
        with self.engine.connect() as conn:
            if "recurrence_type" not in columns:
                conn.execute(text("ALTER TABLE todos ADD COLUMN recurrence_type VARCHAR(20)"))
            if "recurrence_interval" not in columns:
                conn.execute(text("ALTER TABLE todos ADD COLUMN recurrence_interval INTEGER DEFAULT 1"))
            if "recurrence_end_date" not in columns:
                conn.execute(text("ALTER TABLE todos ADD COLUMN recurrence_end_date DATE"))
            conn.commit()

    def _migrate_add_recurrence_day(self):
        """迁移：为 todos 表添加 recurrence_day 列"""
        from sqlalchemy import inspect, text

        inspector = inspect(self.engine)
        columns = [c["name"] for c in inspector.get_columns("todos")]
        if "recurrence_day" not in columns:
            with self.engine.connect() as conn:
                conn.execute(text("ALTER TABLE todos ADD COLUMN recurrence_day INTEGER"))
                conn.commit()

    def _migrate_add_category_is_system(self):
        """迁移：为 categories 表添加 is_system 列"""
        from sqlalchemy import inspect, text

        inspector = inspect(self.engine)
        columns = [c["name"] for c in inspector.get_columns("categories")]
        if "is_system" not in columns:
            with self.engine.connect() as conn:
                conn.execute(text("ALTER TABLE categories ADD COLUMN is_system BOOLEAN DEFAULT 0"))
                conn.commit()

    def _init_default_categories(self):
        """清理旧的系统分类（系统视图由导航栏硬编码，不存入数据库）"""
        from models.category import Category
        from models.todo import Todo

        session = self.get_session()
        try:
            system_cats = session.query(Category).filter(
                Category.is_system == True
            ).all()
            if not system_cats:
                return

            system_ids = [c.id for c in system_cats]
            session.query(Todo).filter(
                Todo.category_id.in_(system_ids)
            ).update({"category_id": None}, synchronize_session=False)

            for cat in system_cats:
                session.delete(cat)

            session.commit()
        except Exception:
            session.rollback()
        finally:
            session.close()

    def get_session(self):
        """获取数据库会话"""
        return self.SessionLocal()


# 全局数据库实例
db = Database()
