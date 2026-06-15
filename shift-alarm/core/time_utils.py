"""跨日期时间转换工具函数"""

from datetime import date, datetime, time, timedelta


def minutes_to_time_str(minutes: int) -> str:
    """将分钟数转换为时间字符串。
    0~1439 → "HH:MM"
    1440+ → "次日HH:MM"
    """
    days = minutes // (24 * 60)
    remain = minutes % (24 * 60)
    h, m = divmod(remain, 60)
    if days > 0:
        return f"次日{h:02d}:{m:02d}"
    return f"{h:02d}:{m:02d}"


def time_str_to_minutes(s: str) -> int:
    """将时间字符串转换为分钟数。
    "08:30" → 510
    "次日08:30" → 1950 (24*60 + 510)
    """
    s = s.strip()
    prefix_days = 0
    if s.startswith("次日"):
        prefix_days = 1
        s = s[2:]
    parts = s.split(":")
    h, m = int(parts[0]), int(parts[1]) if len(parts) > 1 else 0
    return prefix_days * 24 * 60 + h * 60 + m


def is_overnight_shift(start_min: int, end_min: int) -> bool:
    """判断班次是否跨日"""
    if end_min == 0 and start_min == 0:
        return False  # 休息
    return end_min <= start_min or end_min >= 24 * 60


def calculate_alarm_time(
    shift_date: date,
    shift_start_minutes: int,
    reminder_minutes_before: int,
) -> datetime:
    """计算闹钟实际触发时间。

    规则：提醒时间不可跨天。
    如果提醒时间早于当日 00:00，则截断到当日 00:00。

    Args:
        shift_date: 班次所在日期
        shift_start_minutes: 班次开始分钟数 (0~2879)
        reminder_minutes_before: 提前提醒分钟数 (>= 0)

    Returns:
        闹钟触发 datetime
    """
    # 班次开始的实际 datetime
    shift_start_dt = datetime.combine(shift_date, time(0, 0)) + timedelta(
        minutes=shift_start_minutes
    )

    # 提醒时间 = 班次开始 - 提前量
    alarm_dt = shift_start_dt - timedelta(minutes=reminder_minutes_before)

    # 约束：不可跨到前一天
    day_start = datetime.combine(shift_date, time(0, 0))
    if alarm_dt < day_start:
        alarm_dt = day_start

    return alarm_dt


def get_shift_start_datetime(shift_date: date, shift_start_minutes: int) -> datetime:
    """获取班次开始的完整 datetime"""
    return datetime.combine(shift_date, time(0, 0)) + timedelta(
        minutes=shift_start_minutes
    )


def get_shift_end_datetime(shift_date: date, shift_end_minutes: int) -> datetime:
    """获取班次结束的完整 datetime（正确处理跨日）"""
    return datetime.combine(shift_date, time(0, 0)) + timedelta(
        minutes=shift_end_minutes
    )


def format_shift_time_range(start_min: int, end_min: int) -> str:
    """格式化班次时间范围，如 '08:00 - 20:00' 或 '20:00 - 次日08:00'"""
    start_str = minutes_to_time_str(start_min)
    end_str = minutes_to_time_str(end_min)
    return f"{start_str} - {end_str}"
