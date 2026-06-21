"""重复任务日期匹配工具"""
from __future__ import annotations

from calendar import monthrange
from datetime import date, timedelta
from typing import Optional

from config.constants import parse_recurrence_day


def _is_workday(target_date: date) -> Optional[bool]:
    """判断指定日期是否为工作日，使用节日数据"""
    from services.holiday_service import holiday_service
    holiday_service.load_for_date(target_date)
    return holiday_service.is_workday(target_date)


def matches_recurrence(due_date: date, target_date: date,
                       recurrence_type: str, interval: int,
                       end_date: date | None,
                       recurrence_day=None) -> bool:
    """判断 target_date 是否在以 due_date 为起点的重复序列上

    recurrence_day: int | str | None
        - 周重复: 逗号分隔的字符串如 "1,3,5" 或单个 int
        - 月重复: 单个数字（字符串或 int）
    """
    if target_date < due_date:
        return False
    if end_date and target_date > end_date:
        return False
    if target_date == due_date:
        return True

    if recurrence_type == "daily":
        return (target_date - due_date).days % interval == 0
    elif recurrence_type == "weekly":
        days = parse_recurrence_day(recurrence_day)
        if days:
            target_weekday = target_date.weekday() + 1
            if target_weekday not in days:
                return False
            days_diff = (target_date - due_date).days
            if days_diff <= 0:
                return False
            weeks_diff = days_diff // 7
            return weeks_diff % interval == 0
        return (target_date - due_date).days % (interval * 7) == 0
    elif recurrence_type == "monthly":
        day_list = parse_recurrence_day(recurrence_day)
        day_to_use = day_list[0] if day_list else None
        month_diff = (target_date.year - due_date.year) * 12 + (target_date.month - due_date.month)
        if month_diff <= 0 or month_diff % interval != 0:
            return False
        if day_to_use is not None:
            max_day = monthrange(target_date.year, target_date.month)[1]
            expected_day = min(day_to_use, max_day)
            return target_date.day == expected_day
        max_day = monthrange(target_date.year, target_date.month)[1]
        expected_day = min(due_date.day, max_day)
        return target_date.day == expected_day
    elif recurrence_type == "workday":
        if _is_workday(target_date) is not True:
            return False
        # 计算从 due_date 到 target_date 之间的工作日数
        cursor = due_date
        workday_count = 0
        while cursor < target_date:
            cursor += timedelta(days=1)
            if _is_workday(cursor) is True:
                workday_count += 1
        return workday_count % interval == 0
    return False


def generate_occurrences(due_date: date, start: date, end: date,
                         recurrence_type: str, interval: int,
                         end_date: date | None,
                         recurrence_day=None) -> list[date]:
    """生成 [start, end] 范围内的所有重复日期

    recurrence_day: int | str | None
        - 周重复: 逗号分隔的字符串如 "1,3,5" 或单个 int，支持多选
        - 月重复: 单个数字（字符串或 int）
    """
    if end_date and start > end_date:
        return []
    actual_end = min(end, end_date) if end_date else end

    results = []

    if recurrence_type == "daily":
        if due_date >= start:
            cursor = due_date
        else:
            days_diff = (start - due_date).days
            skip = (days_diff + interval - 1) // interval
            cursor = due_date + timedelta(days=skip * interval)
        while cursor <= actual_end:
            results.append(cursor)
            cursor += timedelta(days=interval)

    elif recurrence_type == "weekly":
        days = parse_recurrence_day(recurrence_day)
        if days:
            # 为每个选中的星期几生成日期
            for day_num in sorted(days):
                target_weekday = day_num - 1
                if due_date >= start:
                    cursor = due_date
                else:
                    cursor = start
                days_ahead = (target_weekday - cursor.weekday()) % 7
                cursor = cursor + timedelta(days=days_ahead)
                if cursor < due_date:
                    cursor += timedelta(days=7)
                while cursor <= actual_end:
                    if cursor >= start:
                        results.append(cursor)
                    cursor += timedelta(days=interval * 7)
            results.sort()
        else:
            step = interval * 7
            if due_date >= start:
                cursor = due_date
            else:
                days_diff = (start - due_date).days
                skip = (days_diff + step - 1) // step
                cursor = due_date + timedelta(days=skip * step)
            while cursor <= actual_end:
                results.append(cursor)
                cursor += timedelta(days=step)

    elif recurrence_type == "monthly":
        day_list = parse_recurrence_day(recurrence_day)
        day_to_use = day_list[0] if day_list else due_date.day
        if due_date >= start:
            y, m = due_date.year, due_date.month
        else:
            month_diff = (start.year - due_date.year) * 12 + (start.month - due_date.month)
            skip = ((month_diff + interval - 1) // interval) * interval
            total_months = (due_date.year * 12 + due_date.month - 1) + skip
            y, m = divmod(total_months, 12)
            m += 1
        while True:
            max_day = monthrange(y, m)[1]
            d = min(day_to_use, max_day)
            candidate = date(y, m, d)
            if candidate > actual_end:
                break
            if candidate >= start and candidate >= due_date:
                results.append(candidate)
            total_months = y * 12 + (m - 1) + interval
            y, m = divmod(total_months, 12)
            m += 1

    elif recurrence_type == "workday":
        # 工作日重复：逐日扫描，只保留工作日
        cursor = max(due_date, start)
        workday_count = 0
        # 先计算从 due_date 到 start 之间已过的工作日数
        if start > due_date:
            tmp = due_date
            while tmp < start:
                tmp += timedelta(days=1)
                if _is_workday(tmp) is True:
                    workday_count += 1
        while cursor <= actual_end:
            is_wd = _is_workday(cursor)
            if is_wd is None:
                # 节日数据不可用，中止生成
                break
            if is_wd and workday_count % interval == 0:
                results.append(cursor)
            if is_wd:
                workday_count += 1
            cursor += timedelta(days=1)

    return results
