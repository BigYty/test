"""REST API 路由"""

from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import date, datetime, timedelta
from typing import Callable, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from config.constants import ShiftType, WorkMode, SHIFT_NAMES, SHIFT_COLORS
from config.settings import AppSettings
from db.repository import Repository
from db.models import ShiftConfig, CyclePattern, ScheduleDay, AlarmLog
from core.shift_engine import ShiftEngine
from core.holiday_service import HolidayService
from core.time_utils import minutes_to_time_str, format_shift_time_range


# ─── Pydantic 模型 ──────────────────────────────────

class ShiftConfigUpdate(BaseModel):
    shift_name: str = ""
    start_time: int = 0
    end_time: int = 0
    reminder: int = 0
    is_active: bool = True


class CyclePatternSave(BaseModel):
    patterns: list[int]   # shift_type 值列表，按顺序


class WorkModeUpdate(BaseModel):
    work_mode: int        # 1=正常, 2=特殊


class ScheduleOverride(BaseModel):
    date: str
    shift_type: int
    note: str = ""


class SettingsUpdate(BaseModel):
    cycle_start_date: str = ""
    cycle_reference_index: int = 0
    snooze_minutes: int = 5
    alarm_volume: int = 80


# ─── 路由工厂 ───────────────────────────────────────

def create_router(
    repo: Repository,
    reschedule_callback: Callable[[], None] | None = None,
) -> APIRouter:
    router = APIRouter()
    engine = ShiftEngine(repo)
    holiday_svc = HolidayService(repo)

    # ─── 状态 ────────────────────────────────────────

    @router.get("/status")
    def get_status():
        """获取应用当前状态"""
        settings = repo.load_settings()
        today = date.today()

        # 获取循环模式
        cycle_pattern = repo.get_cycle_pattern()

        # 获取今日排班
        try:
            cycle_start = date.fromisoformat(settings.cycle_start_date) if settings.cycle_start_date else today
        except ValueError:
            cycle_start = today

        today_schedule = engine.get_today_shift(
            settings.work_mode, cycle_start, cycle_pattern,
            settings.cycle_reference_index
        )
        tomorrow_schedule = engine.get_tomorrow_shift(
            settings.work_mode, cycle_start, cycle_pattern,
            settings.cycle_reference_index
        )

        shift_configs = repo.get_all_shifts()

        return {
            "work_mode": settings.work_mode.value,
            "cycle_start_date": settings.cycle_start_date,
            "cycle_reference_index": settings.cycle_reference_index,
            "today": today_schedule.to_dict(),
            "tomorrow": tomorrow_schedule.to_dict(),
            "shifts": {sc.shift_type.value: sc.to_dict() for sc in shift_configs},
            "first_run": settings.first_run,
        }

    # ─── 班次配置 ─────────────────────────────────────

    @router.get("/shifts")
    def get_shifts():
        """获取所有班次配置"""
        configs = repo.get_all_shifts()
        result = []
        for sc in configs:
            d = sc.to_dict()
            d["shift_name"] = d["shift_name"] or SHIFT_NAMES.get(sc.shift_type, "")
            d["color"] = SHIFT_COLORS.get(sc.shift_type, "#999")
            d["time_range"] = format_shift_time_range(sc.start_time, sc.end_time)
            result.append(d)
        return result

    @router.put("/shifts/{shift_type}")
    def update_shift(shift_type: int, body: ShiftConfigUpdate):
        """更新班次配置"""
        try:
            st = ShiftType(shift_type)
        except ValueError:
            raise HTTPException(400, "无效的班次类型")

        config = ShiftConfig(
            shift_type=st,
            shift_name=body.shift_name,
            start_time=body.start_time,
            end_time=body.end_time,
            reminder=body.reminder,
            is_active=body.is_active,
        )
        repo.update_shift(config)
        # 班次时间/提醒变更后重算闹钟
        _try_reschedule(reschedule_callback)
        return {"ok": True}

    # ─── 工作模式 ─────────────────────────────────────

    @router.put("/work-mode")
    def set_work_mode(body: WorkModeUpdate):
        """设置工作模式"""
        try:
            mode = WorkMode(body.work_mode)
        except ValueError:
            raise HTTPException(400, "无效的工作模式")

        settings = repo.load_settings()
        settings.work_mode = mode
        repo.save_settings(settings)
        # 工作模式变更也需要重算闹钟
        _try_reschedule(reschedule_callback)
        return {"ok": True, "work_mode": mode.value}

    # ─── 排班循环 (特殊工种) ──────────────────────────

    @router.get("/cycle-pattern")
    def get_cycle_pattern():
        """获取排班循环"""
        patterns = repo.get_cycle_pattern()
        shift_configs = {sc.shift_type: sc for sc in repo.get_all_shifts()}
        return [{
            "position": p.position,
            "shift_type": p.shift_type.value,
            "shift_name": SHIFT_NAMES.get(p.shift_type, ""),
            "color": SHIFT_COLORS.get(p.shift_type, "#999"),
        } for p in patterns]

    @router.put("/cycle-pattern")
    def save_cycle_pattern(body: CyclePatternSave):
        """保存排班循环"""
        if not body.patterns:
            raise HTTPException(400, "循环不能为空")

        patterns = []
        for i, st_val in enumerate(body.patterns):
            try:
                st = ShiftType(st_val)
            except ValueError:
                raise HTTPException(400, f"无效的班次类型: {st_val}")
            patterns.append(CyclePattern(position=i, shift_type=st))

        repo.save_cycle_pattern(patterns)
        # 保存后触发闹钟重调度
        _try_reschedule(reschedule_callback)
        return {"ok": True, "count": len(patterns)}

    # ─── 日历视图 ─────────────────────────────────────

    @router.get("/calendar")
    def get_calendar(
        year: int = Query(...),
        month: int = Query(...),
    ):
        """获取指定月份的排班日历"""
        settings = repo.load_settings()
        try:
            cycle_start = date.fromisoformat(settings.cycle_start_date) if settings.cycle_start_date else date.today()
        except ValueError:
            cycle_start = date.today()

        cycle_pattern = repo.get_cycle_pattern()

        # 计算月份范围
        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = date(year, month + 1, 1) - timedelta(days=1)

        # 包含前后填充天
        cal_start = start_date - timedelta(days=start_date.weekday())
        cal_end = end_date + timedelta(days=6 - end_date.weekday())

        # 生成排班
        schedules = engine.generate_schedules(
            cal_start, cal_end, settings.work_mode,
            cycle_start, cycle_pattern, settings.cycle_reference_index,
        )

        schedule_map = {sd.date.isoformat(): sd for sd in schedules}

        # 转换为前端日历数据
        days = []
        current = cal_start
        while current <= cal_end:
            sd = schedule_map.get(current.isoformat())
            if sd:
                days.append({
                    "date": current.isoformat(),
                    "day": current.day,
                    "month": current.month,
                    "weekday": current.weekday(),
                    "shift_type": sd.shift_type.value,
                    "shift_name": SHIFT_NAMES.get(sd.shift_type, ""),
                    "color": SHIFT_COLORS.get(sd.shift_type, "#999"),
                    "is_holiday": sd.is_holiday,
                    "is_override": sd.is_override,
                    "is_today": current == date.today(),
                    "in_month": current.month == month,
                })
            else:
                shift_type = ShiftType.REST
                days.append({
                    "date": current.isoformat(),
                    "day": current.day,
                    "month": current.month,
                    "weekday": current.weekday(),
                    "shift_type": shift_type.value,
                    "shift_name": SHIFT_NAMES.get(shift_type, ""),
                    "color": SHIFT_COLORS.get(shift_type, "#999"),
                    "is_holiday": False,
                    "is_override": False,
                    "is_today": current == date.today(),
                    "in_month": current.month == month,
                })
            current += timedelta(days=1)

        return {
            "year": year,
            "month": month,
            "days": days,
        }

    # ─── 手动覆盖排班 ─────────────────────────────────

    @router.put("/schedule/override")
    def override_schedule(body: ScheduleOverride):
        """手动覆盖某天排班"""
        try:
            d = date.fromisoformat(body.date)
            st = ShiftType(body.shift_type)
        except (ValueError, KeyError):
            raise HTTPException(400, "参数无效")

        sd = ScheduleDay(date=d, shift_type=st, is_override=True, note=body.note)
        repo.save_schedule(sd)
        return {"ok": True}

    # ─── 节假日刷新 ───────────────────────────────────

    @router.post("/holidays/refresh")
    def refresh_holidays(year: int = Query(...)):
        """刷新指定年份的节假日数据"""
        try:
            holiday_svc.refresh_year(year)
            return {"ok": True, "year": year}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    @router.get("/holidays/check/{date_str}")
    def check_holiday(date_str: str):
        """检查某天是否为节假日"""
        try:
            d = date.fromisoformat(date_str)
        except ValueError:
            raise HTTPException(400, "日期格式无效，应为 YYYY-MM-DD")

        return {
            "date": date_str,
            "is_holiday": holiday_svc.is_holiday(d),
            "is_workday": holiday_svc.is_workday(d),
            "name": holiday_svc.get_holiday_name(d),
        }

    # ─── 设置 ─────────────────────────────────────────

    @router.get("/settings")
    def get_settings():
        """获取全局设置"""
        settings = repo.load_settings()
        return settings.to_dict()

    @router.put("/settings")
    def update_settings(body: SettingsUpdate):
        """更新全局设置"""
        settings = repo.load_settings()
        settings.cycle_start_date = body.cycle_start_date
        settings.cycle_reference_index = body.cycle_reference_index
        settings.snooze_minutes = body.snooze_minutes
        settings.alarm_volume = body.alarm_volume
        repo.save_settings(settings)
        # 保存后触发闹钟重调度
        _try_reschedule(reschedule_callback)
        return {"ok": True}

    @router.put("/settings/first-run-done")
    def mark_first_run_done():
        """标记首次运行完成"""
        settings = repo.load_settings()
        settings.first_run = False
        repo.save_settings(settings)
        return {"ok": True}

    # ─── 闹钟管理 ─────────────────────────────────────

    @router.get("/alarms")
    def get_upcoming_alarms():
        """获取即将到来的闹钟"""
        from core.alarm_scheduler import AlarmScheduler
        scheduler = AlarmScheduler(repo)
        return scheduler.get_upcoming_alarms(limit=20)

    @router.post("/alarms/reschedule")
    def trigger_reschedule():
        """手动触发闹钟重调度（排班设置变更后由前端调用）"""
        if reschedule_callback is None:
            return {
                "ok": False,
                "message": "闹钟调度器尚未初始化，请稍后重试或重启应用。"
            }
        try:
            reschedule_callback()
            return {"ok": True, "message": "闹钟已重新调度"}
        except Exception as e:
            return {"ok": False, "message": f"重调度失败: {e}"}

    return router


def _try_reschedule(callback: Callable[[], None] | None) -> None:
    """安全地触发重调度回调，忽略未初始化或异常情况"""
    if callback is None:
        return
    try:
        callback()
    except Exception:
        pass  # 静默失败，不影响保存操作的返回
