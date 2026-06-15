"""排班循环计算引擎"""

from datetime import date, datetime, timedelta
from typing import Optional

from config.constants import (
    ShiftType, WorkMode, NORMAL_MODE_SHIFTS, DEFAULT_WEEKLY_PATTERN,
)
from db.repository import Repository
from db.models import ScheduleDay, CyclePattern


class ShiftEngine:
    """排班引擎 —— 负责计算任意日期的班次"""

    def __init__(self, repo: Repository):
        self.repo = repo
        self._holiday_service = None  # 延迟导入避免循环依赖

    @property
    def holiday_service(self):
        if self._holiday_service is None:
            from core.holiday_service import HolidayService
            self._holiday_service = HolidayService(self.repo)
        return self._holiday_service

    def get_shift_for_date(
        self,
        target_date: date,
        work_mode: WorkMode,
        cycle_start_date: date,
        cycle_pattern: list[CyclePattern],
        reference_index: int = 0,
    ) -> tuple[ShiftType, bool]:
        """计算 target_date 的班次。

        Returns:
            (shift_type, is_holiday_override): 班次类型, 是否被节假日覆盖
        """
        is_holiday_override = False

        if work_mode == WorkMode.NORMAL:
            shift = self._get_normal_shift(target_date)
            # 节假日覆盖
            is_holiday = self.holiday_service.is_holiday(target_date)
            is_workday = self.holiday_service.is_workday(target_date)
            if is_holiday and not is_workday:
                shift = ShiftType.REST
                is_holiday_override = True
            elif is_workday:
                shift = ShiftType.DAY_SHIFT
                is_holiday_override = True
        else:
            shift = self._get_special_shift(
                target_date, cycle_start_date, cycle_pattern, reference_index
            )

        return shift, is_holiday_override

    def _get_normal_shift(self, target_date: date) -> ShiftType:
        """正常工作表：按周几循环"""
        dow = target_date.weekday()  # 0=周一, 6=周日
        return DEFAULT_WEEKLY_PATTERN.get(dow, ShiftType.REST)

    def _get_special_shift(
        self,
        target_date: date,
        cycle_start_date: date,
        cycle_pattern: list[CyclePattern],
        reference_index: int,
    ) -> ShiftType:
        """特殊工种：按自定义顺序循环"""
        if not cycle_pattern:
            return ShiftType.REST

        days_delta = (target_date - cycle_start_date).days
        if days_delta < 0:
            return ShiftType.REST

        cycle_len = len(cycle_pattern)
        index = (reference_index + days_delta) % cycle_len
        return cycle_pattern[index].shift_type

    def generate_schedules(
        self,
        start_date: date,
        end_date: date,
        work_mode: WorkMode,
        cycle_start_date: date,
        cycle_pattern: list[CyclePattern],
        reference_index: int = 0,
        force_regenerate: bool = False,
    ) -> list[ScheduleDay]:
        """生成日期范围内的排班表。

        如果 force_regenerate=False 且已有排班未被手动覆盖，则跳过。
        """
        schedules = []
        current = start_date
        while current <= end_date:
            # 检查是否已有手动覆盖
            existing = self.repo.get_schedule(current)
            if existing and existing.is_override and not force_regenerate:
                schedules.append(existing)
            else:
                shift, is_holiday = self.get_shift_for_date(
                    current, work_mode, cycle_start_date,
                    cycle_pattern, reference_index
                )
                sd = ScheduleDay(
                    date=current,
                    shift_type=shift,
                    is_holiday=is_holiday,
                    is_override=False,
                )
                schedules.append(sd)
                self.repo.save_schedule(sd)
            current += timedelta(days=1)

        return schedules

    def get_today_shift(
        self,
        work_mode: WorkMode,
        cycle_start_date: date,
        cycle_pattern: list[CyclePattern],
        reference_index: int = 0,
    ) -> ScheduleDay:
        """获取今日排班"""
        today = date.today()
        existing = self.repo.get_schedule(today)
        if existing:
            return existing

        shift, is_holiday = self.get_shift_for_date(
            today, work_mode, cycle_start_date, cycle_pattern, reference_index
        )
        sd = ScheduleDay(date=today, shift_type=shift, is_holiday=is_holiday)
        self.repo.save_schedule(sd)
        return sd

    def get_tomorrow_shift(
        self,
        work_mode: WorkMode,
        cycle_start_date: date,
        cycle_pattern: list[CyclePattern],
        reference_index: int = 0,
    ) -> ScheduleDay:
        """获取明日排班"""
        tomorrow = date.today() + timedelta(days=1)
        shift, is_holiday = self.get_shift_for_date(
            tomorrow, work_mode, cycle_start_date, cycle_pattern, reference_index
        )
        sd = ScheduleDay(date=tomorrow, shift_type=shift, is_holiday=is_holiday)
        self.repo.save_schedule(sd)
        return sd
