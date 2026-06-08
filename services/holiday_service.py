"""
节日数据服务
从 CDN 获取中国法定节假日数据并持久化到本地
"""
from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path
from typing import Optional

from config.constants import APP_ID
from config.settings import settings

logger = logging.getLogger(__name__)

HOLIDAY_CDN_URL = "https://cdn.jsdelivr.net/gh/NateScarlet/holiday-cn@master/{year}.json"


class HolidayService:
    """节日数据服务，负责获取、缓存和查询节日数据"""

    def __init__(self):
        self._cache_dir = Path.home() / f".{APP_ID}" / "holidays"
        self._data: dict[str, dict] = {}  # key: "2026-01-01", value: {"name": "元旦", "isOffDay": True}

    def _cache_path(self, year: int) -> Path:
        return self._cache_dir / f"{year}.json"

    def _load_local(self, year: int) -> Optional[list]:
        """从本地缓存加载节日数据，返回 days 列表"""
        path = self._cache_path(year)
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                # 兼容旧格式（完整对象）和新格式（仅 days 数组）
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict):
                    return data.get("days", [])
            except Exception as e:
                logger.warning(f"读取本地节日数据失败: {e}")
        return None

    def _save_local(self, year: int, data: dict):
        """持久化节日数据到本地，只保存 days 数组"""
        try:
            self._cache_dir.mkdir(parents=True, exist_ok=True)
            days = data.get("days", [])
            with open(self._cache_path(year), "w", encoding="utf-8") as f:
                json.dump(days, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"保存节日数据失败: {e}")

    def _fetch_remote(self, year: int) -> Optional[dict]:
        """从 CDN 获取节日数据"""
        url = HOLIDAY_CDN_URL.format(year=year)
        try:
            from urllib.request import urlopen
            from urllib.error import URLError, HTTPError
            with urlopen(url, timeout=5) as resp:
                if resp.status == 200:
                    return json.loads(resp.read().decode("utf-8"))
        except HTTPError as e:
            logger.warning(f"获取节日数据 HTTP 错误 ({year}): {e.code}")
        except (URLError, TimeoutError, OSError) as e:
            logger.warning(f"获取节日数据网络错误 ({year}): {e}")
        except Exception as e:
            logger.warning(f"获取节日数据失败 ({year}): {e}")
        return None

    def _parse_data(self, days: list):
        """解析节日数据到内存缓存"""
        for day in days:
            date_str = day.get("date", "")
            if date_str:
                self._data[date_str] = {
                    "name": day.get("name", ""),
                    "isOffDay": day.get("isOffDay", False),
                }

    def load_year(self, year: int):
        """加载指定年份的节日数据，优先本地，否则从远程获取"""
        # 优先从本地取
        days = self._load_local(year)
        if days:
            self._parse_data(days)
            return

        # 本地无数据，从远程获取
        data = self._fetch_remote(year)
        if data:
            self._save_local(year, data)
            self._parse_data(data.get("days", []))

    def get_holiday(self, target_date: date) -> Optional[dict]:
        """获取指定日期的节日信息，返回 {"name": str, "isOffDay": bool} 或 None"""
        date_str = target_date.isoformat()
        return self._data.get(date_str)

    def load_for_date(self, target_date: date):
        """确保指定日期所在年份的节日数据已加载"""
        year = target_date.year
        key_prefix = f"{year}-"
        if not any(k.startswith(key_prefix) for k in self._data):
            self.load_year(year)

    def clear_cache(self, year: Optional[int] = None):
        """清除本地缓存"""
        if year:
            path = self._cache_path(year)
            if path.exists():
                path.unlink()
        else:
            import shutil
            if self._cache_dir.exists():
                shutil.rmtree(self._cache_dir)
        self._data.clear()


# 全局单例
holiday_service = HolidayService()
