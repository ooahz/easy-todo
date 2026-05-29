"""重复任务日期匹配工具"""
from __future__ import annotations

from calendar import monthrange
from datetime import date, timedelta


def matches_recurrence(due_date: date, target_date: date,
                       recurrence_type: str, interval: int,
                       end_date: date | None,
                       recurrence_day: int | None = None) -> bool:
    """判断 target_date 是否在以 due_date 为起点的重复序列上"""
    if target_date < due_date:
        return False
    if end_date and target_date > end_date:
        return False
    if target_date == due_date:
        return True

    if recurrence_type == "daily":
        return (target_date - due_date).days % interval == 0
    elif recurrence_type == "weekly":
        if recurrence_day is not None:
            target_weekday = target_date.weekday() + 1
            if target_weekday != recurrence_day:
                return False
            days_diff = (target_date - due_date).days
            if days_diff <= 0:
                return False
            weeks_diff = days_diff // 7
            return weeks_diff % interval == 0
        return (target_date - due_date).days % (interval * 7) == 0
    elif recurrence_type == "monthly":
        month_diff = (target_date.year - due_date.year) * 12 + (target_date.month - due_date.month)
        if month_diff <= 0 or month_diff % interval != 0:
            return False
        if recurrence_day is not None:
            max_day = monthrange(target_date.year, target_date.month)[1]
            expected_day = min(recurrence_day, max_day)
            return target_date.day == expected_day
        max_day = monthrange(target_date.year, target_date.month)[1]
        expected_day = min(due_date.day, max_day)
        return target_date.day == expected_day
    return False


def generate_occurrences(due_date: date, start: date, end: date,
                         recurrence_type: str, interval: int,
                         end_date: date | None,
                         recurrence_day: int | None = None) -> list[date]:
    """生成 [start, end] 范围内的所有重复日期"""
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
        if recurrence_day is not None:
            target_weekday = recurrence_day - 1
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
        day_to_use = recurrence_day if recurrence_day is not None else due_date.day
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

    return results
