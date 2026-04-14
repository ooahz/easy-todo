"""数据库连接与会话管理"""
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from config.constants import APP_ID


class Base(DeclarativeBase):
    pass


class Database:
    """数据库管理器（单例）"""

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
        )
        self.SessionLocal = sessionmaker(
            bind=self.engine,
            expire_on_commit=False,
        )

    def create_tables(self):
        """创建所有数据表"""
        Base.metadata.create_all(self.engine)

    def get_session(self):
        """获取数据库会话"""
        return self.SessionLocal()


# 全局数据库实例
db = Database()
