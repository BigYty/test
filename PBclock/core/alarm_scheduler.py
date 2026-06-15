"""闹钟调度器 —— 基于 APScheduler"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Callable, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.jobstores.base import JobLookupError

from config.constants import ShiftType, WorkMode
from db.repository import Repository
from db.models import ScheduleDay, ShiftConfig, AlarmLog, CyclePattern
from core.time_utils import calculate_alarm_time

logger = logging.getLogger(__name__)


class AlarmScheduler:
    """闹钟调度器"""

    def __init__(self, repo: Repository):
        self.repo = repo
        self._scheduler = BackgroundScheduler(
            job_defaults={"misfire_grace_time": 300}  # 5分钟容错
        )
        self._on_alarm_callback: Callable[[AlarmLog], None] | None = None
        self._running = False

    @property
    def scheduler(self) -> BackgroundScheduler:
        return self._scheduler

    def set_callback(self, callback: Callable[[AlarmLog], None]):
        """设置闹钟触发回调"""
        self._on_alarm_callback = callback

    def start(self):
        """启动调度器"""
        if not self._running:
            self._scheduler.start()
            self._running = True
            logger.info("闹钟调度器已启动")

    def shutdown(self):
        """关闭调度器"""
        if self._running:
            self._scheduler.shutdown(wait=False)
            self._running = False
            logger.info("闹钟调度器已关闭")

    def reschedule_all(
        self,
        work_mode: WorkMode,
        cycle_start_date: date,
        cycle_pattern: list[CyclePattern],
        reference_index: int = 0,
    ):
        """重新计算并注册所有闹钟（未来14天）"""
        # 清除所有未触发的闹钟
        self._clear_pending_jobs()
        self.repo.delete_future_alarms()

        # 获取班次配置
        shift_configs = {sc.shift_type: sc for sc in self.repo.get_all_shifts()}

        # 生成未来14天的排班并注册闹钟
        from core.shift_engine import ShiftEngine
        engine = ShiftEngine(self.repo)

        today = date.today()
        end_date = today + timedelta(days=14)

        schedules = engine.generate_schedules(
            today, end_date, work_mode, cycle_start_date,
            cycle_pattern, reference_index, force_regenerate=True
        )

        for sd in schedules:
            self._schedule_alarms_for_day(sd, shift_configs)

        logger.info(f"已重新调度闹钟，覆盖 {today} ~ {end_date}")

    def _schedule_alarms_for_day(self, sd: ScheduleDay, shift_configs: dict):
        """为某天的排班注册闹钟"""
        config = shift_configs.get(sd.shift_type)
        if not config or not config.is_active:
            return
        if config.reminder <= 0:
            return  # 未设置提醒
        if sd.shift_type == ShiftType.REST:
            return  # 休息日不设闹钟

        alarm_dt = calculate_alarm_time(
            sd.date, config.start_time, config.reminder
        )

        # 只注册未来的闹钟
        if alarm_dt <= datetime.now():
            return

        # 写入数据库
        log = AlarmLog(
            schedule_id=sd.id or 0,
            alarm_time=alarm_dt,
            shift_type=sd.shift_type,
        )
        alarm_id = self.repo.create_alarm(log)

        # 注册 APScheduler 任务
        self._scheduler.add_job(
            self._on_alarm_trigger,
            trigger=DateTrigger(run_date=alarm_dt),
            args=[alarm_id],
            id=f"alarm_{alarm_id}",
            replace_existing=True,
        )
        logger.debug(f"已注册闹钟: {sd.date} {sd.shift_type.name} @ {alarm_dt}")

    def _on_alarm_trigger(self, alarm_id: int):
        """闹钟触发时的内部回调"""
        logger.info(f"闹钟触发: alarm_id={alarm_id}")
        # 从数据库获取最新状态
        rows = self.repo.db.execute(
            "SELECT * FROM alarm_log WHERE id=?", (alarm_id,)
        ).fetchall()
        if not rows:
            return

        row = rows[0]
        log = AlarmLog(
            id=row["id"],
            schedule_id=row["schedule_id"],
            alarm_time=datetime.fromisoformat(row["alarm_time"]),
            shift_type=ShiftType(row["shift_type"]),
            status=row["status"],
            fired_at=datetime.fromisoformat(row["fired_at"]) if row["fired_at"] else None,
        )

        # 更新状态为已触发
        now = datetime.now()
        self.repo.update_alarm_status(alarm_id, 1, now)
        log.status = 1
        log.fired_at = now

        # 调用外部回调
        if self._on_alarm_callback:
            self._on_alarm_callback(log)

    def snooze(self, alarm_id: int, minutes: int = 5):
        """延迟闹钟"""
        snooze_time = datetime.now() + timedelta(minutes=minutes)
        self._scheduler.add_job(
            self._on_alarm_trigger,
            trigger=DateTrigger(run_date=snooze_time),
            args=[alarm_id],
            id=f"alarm_{alarm_id}_snooze",
            replace_existing=True,
        )
        self.repo.update_alarm_status(alarm_id, 3)
        logger.info(f"闹钟 {alarm_id} 已延迟 {minutes} 分钟")

    def dismiss(self, alarm_id: int):
        """关闭闹钟"""
        self.repo.update_alarm_status(alarm_id, 2)
        try:
            self._scheduler.remove_job(f"alarm_{alarm_id}")
            self._scheduler.remove_job(f"alarm_{alarm_id}_snooze")
        except JobLookupError:
            pass

    def _clear_pending_jobs(self):
        """清除所有待触发任务"""
        for job in self._scheduler.get_jobs():
            if job.id.startswith("alarm_"):
                try:
                    self._scheduler.remove_job(job.id)
                except JobLookupError:
                    pass

    def get_upcoming_alarms(self, limit: int = 10) -> list[dict]:
        """获取即将到来的闹钟列表"""
        rows = self.repo.db.execute(
            "SELECT al.*, sc.shift_name FROM alarm_log al "
            "LEFT JOIN shift_config sc ON al.shift_type = sc.shift_type "
            "WHERE al.status = 0 AND al.alarm_time > datetime('now', 'localtime') "
            "ORDER BY al.alarm_time LIMIT ?",
            (limit,)
        ).fetchall()

        return [{
            "id": row["id"],
            "alarm_time": row["alarm_time"],
            "shift_name": row["shift_name"] or ShiftType(row["shift_type"]).name,
            "shift_type": row["shift_type"],
            "status": row["status"],
        } for row in rows]
