"""数据库连接与会话管理"""
from pathlib import Path

from sqlalchemy import create_engine, event
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

        # 启用 WAL 模式，避免写操作独占锁阻塞读操作
        @event.listens_for(self.engine, "connect")
        def _set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            try:
                cursor.execute("PRAGMA journal_mode=WAL")
            except Exception:
                pass  # 某些环境不支持 WAL（如网络驱动器），回退到默认模式
            try:
                cursor.execute("PRAGMA busy_timeout=5000")
            except Exception:
                pass
            try:
                cursor.execute("PRAGMA synchronous=NORMAL")
            except Exception:
                pass
            cursor.close()

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
        self._migrate_add_recurrence_template()
        self._migrate_add_completed_at()
        self._migrate_add_recurrence_start_date()
        self._migrate_add_start_date()
        self._init_default_categories()
        self._migrate_add_indexes()

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

    def _migrate_add_recurrence_template(self):
        """迁移：为 todos 表添加重复模板相关列"""
        from sqlalchemy import inspect, text

        inspector = inspect(self.engine)
        columns = [c["name"] for c in inspector.get_columns("todos")]
        with self.engine.connect() as conn:
            if "is_recurrence_template" not in columns:
                conn.execute(text("ALTER TABLE todos ADD COLUMN is_recurrence_template BOOLEAN DEFAULT 0"))
            if "recurrence_template_id" not in columns:
                conn.execute(text("ALTER TABLE todos ADD COLUMN recurrence_template_id INTEGER REFERENCES todos(id) ON DELETE SET NULL"))
            if "occurrence_date" not in columns:
                conn.execute(text("ALTER TABLE todos ADD COLUMN occurrence_date DATE"))
            if "is_exception" not in columns:
                conn.execute(text("ALTER TABLE todos ADD COLUMN is_exception BOOLEAN DEFAULT 0"))
            conn.commit()

    def _migrate_add_completed_at(self):
        """迁移：为 todos 表添加 completed_at 列，并用 updated_at 回填历史已完成数据"""
        from sqlalchemy import inspect, text

        inspector = inspect(self.engine)
        columns = [c["name"] for c in inspector.get_columns("todos")]
        if "completed_at" not in columns:
            with self.engine.connect() as conn:
                conn.execute(text("ALTER TABLE todos ADD COLUMN completed_at DATETIME"))
                conn.execute(text(
                    "UPDATE todos SET completed_at = updated_at WHERE status = 1 AND completed_at IS NULL"
                ))
                conn.commit()

    def _migrate_add_recurrence_start_date(self):
        """迁移：为 todos 表添加 recurrence_start_date 列"""
        from sqlalchemy import inspect, text

        inspector = inspect(self.engine)
        columns = [c["name"] for c in inspector.get_columns("todos")]
        if "recurrence_start_date" not in columns:
            with self.engine.connect() as conn:
                conn.execute(text("ALTER TABLE todos ADD COLUMN recurrence_start_date DATE"))
                conn.commit()

    def _migrate_add_start_date(self):
        """迁移：为 todos 表添加 start_date 列"""
        from sqlalchemy import inspect, text

        inspector = inspect(self.engine)
        columns = [c["name"] for c in inspector.get_columns("todos")]
        if "start_date" not in columns:
            with self.engine.connect() as conn:
                conn.execute(text("ALTER TABLE todos ADD COLUMN start_date DATE"))
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

    def _migrate_add_indexes(self):
        """迁移：为 todos 表补建索引"""
        from sqlalchemy import text

        indexes = [
            ("idx_todos_pid", "CREATE INDEX IF NOT EXISTS idx_todos_pid ON todos(pid)"),
            ("idx_todos_category_id", "CREATE INDEX IF NOT EXISTS idx_todos_category_id ON todos(category_id)"),
            ("idx_todos_due_date", "CREATE INDEX IF NOT EXISTS idx_todos_due_date ON todos(due_date)"),
            ("idx_todos_recurrence_template_id", "CREATE INDEX IF NOT EXISTS idx_todos_recurrence_template_id ON todos(recurrence_template_id)"),
            ("idx_todos_status_template", "CREATE INDEX IF NOT EXISTS idx_todos_status_template ON todos(status, is_recurrence_template)"),
        ]
        with self.engine.connect() as conn:
            for _, ddl in indexes:
                conn.execute(text(ddl))
            conn.commit()

    def get_session(self):
        """获取数据库会话"""
        return self.SessionLocal()


# 全局数据库实例
db = Database()
