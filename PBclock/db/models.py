"""数据模型 (dataclass)"""

from dataclasses import dataclass, field
from datetime import date, datetime
from config.constants import ShiftType, WorkMode


@dataclass
class ShiftConfig:
    """班次配置"""
    shift_type: ShiftType
    shift_name: str = ""
    start_time: int = 0         # 当日开始分钟数 0~2879
    end_time: int = 0           # 当日结束分钟数 0~2879
    reminder: int = 0           # 提前提醒分钟数，0=不提醒
    is_active: bool = True
    id: int | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "shift_type": self.shift_type.value,
            "shift_name": self.shift_name,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "reminder": self.reminder,
            "is_active": self.is_active,
        }


@dataclass
class CyclePattern:
    """排班循环顺序（特殊工种）"""
    position: int               # 循环中位置 (0-based)
    shift_type: ShiftType
    id: int | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "position": self.position,
            "shift_type": self.shift_type.value,
        }


@dataclass
class ScheduleDay:
    """每日排班"""
    date: date
    shift_type: ShiftType
    is_holiday: bool = False
    is_override: bool = False   # 用户手动覆盖
    note: str = ""
    id: int | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "date": self.date.isoformat(),
            "shift_type": self.shift_type.value,
            "is_holiday": self.is_holiday,
            "is_override": self.is_override,
            "note": self.note,
        }


@dataclass
class AlarmLog:
    """闹钟日志"""
    schedule_id: int
    alarm_time: datetime
    shift_type: ShiftType
    status: int = 0             # 0=待触发, 1=已触发, 2=已关闭, 3=已延迟
    fired_at: datetime | None = None
    id: int | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "schedule_id": self.schedule_id,
            "alarm_time": self.alarm_time.isoformat() if self.alarm_time else "",
            "shift_type": self.shift_type.value,
            "status": self.status,
            "fired_at": self.fired_at.isoformat() if self.fired_at else None,
        }


@dataclass
class HolidayCache:
    """节假日缓存"""
    date: date
    year: int
    is_holiday: bool
    is_workday: bool            # 调休上班日
    name: str = ""


@dataclass
class AppSettingKV:
    """键值设置"""
    key: str
    value: str
