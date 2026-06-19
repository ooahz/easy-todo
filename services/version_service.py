"""版本管理服务 - 处理版本检测、迁移控制等版本相关操作"""
from __future__ import annotations

from sqlalchemy import text

from config.constants import APP_VERSION


class VersionService:
    """版本管理服务

    通过数据库 _meta 表记录和查询版本信息，
    用于控制迁移执行时机及未来其它版本相关操作。
    """

    def __init__(self, engine):
        self._engine = engine

    def _ensure_meta_table(self):
        """确保 _meta 表存在"""
        with self._engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS _meta (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """))
            conn.commit()

    def get_version(self, key: str = "migration_version") -> str | None:
        """获取指定 key 的版本号，未记录时返回 None"""
        try:
            self._ensure_meta_table()
            with self._engine.connect() as conn:
                result = conn.execute(text(
                    "SELECT value FROM _meta WHERE key = :key"
                ), {"key": key})
                row = result.fetchone()
                return row[0] if row else None
        except Exception:
            return None

    def set_version(self, version: str, key: str = "migration_version"):
        """记录版本号"""
        self._ensure_meta_table()
        with self._engine.connect() as conn:
            conn.execute(text(
                "INSERT OR REPLACE INTO _meta (key, value) VALUES (:key, :value)"
            ), {"key": key, "value": version})
            conn.commit()

    def needs_migration(self) -> bool:
        """判断是否需要执行迁移：当前版本与记录的版本不同时返回 True"""
        return self.get_version() != APP_VERSION

    def mark_migrated(self):
        """标记迁移已完成，记录当前版本号"""
        self.set_version(APP_VERSION)

    def get_current_version(self) -> str:
        """获取应用当前版本号"""
        return APP_VERSION

    def get_meta(self, key: str) -> str | None:
        """获取 _meta 表中指定 key 的值"""
        return self.get_version(key)

    def set_meta(self, key: str, value: str):
        """设置 _meta 表中指定 key 的值"""
        self.set_version(value, key)
