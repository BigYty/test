"""数据访问仓库 —— 所有 CRUD 操作"""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Optional

from config.constants import (
    ShiftType, WorkMode, SHIFT_NAMES, DEFAULT_SHIFT_TIMES,
    DEFAULT_REMINDER_MINUTES, DEFAULT_WEEKLY_PATTERN,
)
from config.settings import AppSettings
from db.connection import Database
from db.models import ShiftConfig, CyclePattern, ScheduleDay, AlarmLog, HolidayCache


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return dict(row)


class Repository:
    """统一数据访问层"""

    def __init__(self):
        self.db = Database()

    # ─── 初始化 ───────────────────────────────────────

    def init_tables(self):
        """创建所有表"""
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS shift_config (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                shift_type INTEGER NOT NULL UNIQUE,
                shift_name TEXT NOT NULL DEFAULT '',
                start_time INTEGER NOT NULL,
                end_time   INTEGER NOT NULL,
                reminder   INTEGER NOT NULL DEFAULT 0,
                is_active  INTEGER NOT NULL DEFAULT 1
            )
        """)
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS cycle_pattern (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                position   INTEGER NOT NULL,
                shift_type INTEGER NOT NULL,
                FOREIGN KEY (shift_type) REFERENCES shift_config(shift_type)
            )
        """)
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS schedule (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                date        TEXT NOT NULL UNIQUE,
                shift_type  INTEGER NOT NULL,
                is_holiday  INTEGER NOT NULL DEFAULT 0,
                is_override INTEGER NOT NULL DEFAULT 0,
                note        TEXT DEFAULT ''
            )
        """)
        self.db.execute("""
            CREATE INDEX IF NOT EXISTS idx_schedule_date ON schedule(date)
        """)
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS alarm_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                schedule_id INTEGER NOT NULL,
                alarm_time  TEXT NOT NULL,
                shift_type  INTEGER NOT NULL,
                status      INTEGER NOT NULL DEFAULT 0,
                fired_at    TEXT
            )
        """)
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS holiday_cache (
                date       TEXT PRIMARY KEY,
                year       INTEGER NOT NULL,
                is_holiday INTEGER NOT NULL,
                is_workday INTEGER NOT NULL,
                name       TEXT DEFAULT ''
            )
        """)
        self.db.execute("""
            CREATE INDEX IF NOT EXISTS idx_holiday_year ON holiday_cache(year)
        """)
        self.db.commit()

    def seed_defaults(self):
        """首次运行时填充默认数据"""
        # 班次配置
        existing = self.db.execute("SELECT COUNT(*) FROM shift_config").fetchone()[0]
        if existing == 0:
            for st in ShiftType:
                start, end = DEFAULT_SHIFT_TIMES.get(st, (0, 0))
                self.db.execute(
                    "INSERT INTO shift_config (shift_type, shift_name, start_time, end_time, reminder) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (st.value, SHIFT_NAMES.get(st, ""), start, end, DEFAULT_REMINDER_MINUTES)
                )
            self.db.commit()

        # 默认设置
        if not self.get_setting("work_mode"):
            self.save_settings(AppSettings())

        # 默认工作日循环（正常模式）
        pattern_count = self.db.execute("SELECT COUNT(*) FROM cycle_pattern").fetchone()[0]
        if pattern_count == 0:
            for pos, (dow, st) in enumerate(sorted(DEFAULT_WEEKLY_PATTERN.items())):
                self.db.execute(
                    "INSERT INTO cycle_pattern (position, shift_type) VALUES (?, ?)",
                    (dow, st.value)
                )
            self.db.commit()

    # ─── 设置 ─────────────────────────────────────────

    def get_setting(self, key: str) -> str | None:
        row = self.db.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else None

    def set_setting(self, key: str, value: str):
        self.db.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (key, value)
        )
        self.db.commit()

    def save_settings(self, s: AppSettings):
        for k, v in s.to_dict().items():
            self.set_setting(k, json.dumps(v) if isinstance(v, (bool, list, dict)) else str(v))

    def load_settings(self) -> AppSettings:
        d = {}
        for key in ["work_mode", "cycle_start_date", "cycle_reference_index",
                     "auto_start", "alarm_sound_path", "alarm_volume",
                     "snooze_minutes", "first_run"]:
            val = self.get_setting(key)
            if val is not None:
                # 尝试 JSON 解析
                try:
                    d[key] = json.loads(val)
                except (json.JSONDecodeError, TypeError):
                    d[key] = val
        return AppSettings.from_dict(d)

    # ─── 班次配置 ─────────────────────────────────────

    def get_all_shifts(self) -> list[ShiftConfig]:
        rows = self.db.execute("SELECT * FROM shift_config ORDER BY shift_type").fetchall()
        return [ShiftConfig(
            id=row["id"],
            shift_type=ShiftType(row["shift_type"]),
            shift_name=row["shift_name"],
            start_time=row["start_time"],
            end_time=row["end_time"],
            reminder=row["reminder"],
            is_active=bool(row["is_active"]),
        ) for row in rows]

    def get_shift(self, shift_type: ShiftType) -> ShiftConfig | None:
        row = self.db.execute(
            "SELECT * FROM shift_config WHERE shift_type=?", (shift_type.value,)
        ).fetchone()
        if not row:
            return None
        return ShiftConfig(
            id=row["id"],
            shift_type=ShiftType(row["shift_type"]),
            shift_name=row["shift_name"],
            start_time=row["start_time"],
            end_time=row["end_time"],
            reminder=row["reminder"],
            is_active=bool(row["is_active"]),
        )

    def update_shift(self, config: ShiftConfig):
        self.db.execute(
            "UPDATE shift_config SET shift_name=?, start_time=?, end_time=?, "
            "reminder=?, is_active=? WHERE shift_type=?",
            (config.shift_name, config.start_time, config.end_time,
             config.reminder, int(config.is_active), config.shift_type.value)
        )
        self.db.commit()

    # ─── 循环顺序 (特殊工种) ──────────────────────────

    def get_cycle_pattern(self) -> list[CyclePattern]:
        rows = self.db.execute(
            "SELECT * FROM cycle_pattern ORDER BY position"
        ).fetchall()
        return [CyclePattern(
            id=row["id"],
            position=row["position"],
            shift_type=ShiftType(row["shift_type"]),
        ) for row in rows]

    def save_cycle_pattern(self, patterns: list[CyclePattern]):
        self.db.execute("DELETE FROM cycle_pattern")
        for p in patterns:
            self.db.execute(
                "INSERT INTO cycle_pattern (position, shift_type) VALUES (?, ?)",
                (p.position, p.shift_type.value)
            )
        self.db.commit()

    # ─── 排班表 ───────────────────────────────────────

    def get_schedules(self, start_date: date, end_date: date) -> list[ScheduleDay]:
        rows = self.db.execute(
            "SELECT * FROM schedule WHERE date BETWEEN ? AND ? ORDER BY date",
            (start_date.isoformat(), end_date.isoformat())
        ).fetchall()
        return [ScheduleDay(
            id=row["id"],
            date=date.fromisoformat(row["date"]),
            shift_type=ShiftType(row["shift_type"]),
            is_holiday=bool(row["is_holiday"]),
            is_override=bool(row["is_override"]),
            note=row["note"],
        ) for row in rows]

    def get_schedule(self, d: date) -> ScheduleDay | None:
        row = self.db.execute(
            "SELECT * FROM schedule WHERE date=?", (d.isoformat(),)
        ).fetchone()
        if not row:
            return None
        return ScheduleDay(
            id=row["id"],
            date=date.fromisoformat(row["date"]),
            shift_type=ShiftType(row["shift_type"]),
            is_holiday=bool(row["is_holiday"]),
            is_override=bool(row["is_override"]),
            note=row["note"],
        )

    def save_schedule(self, sd: ScheduleDay):
        self.db.execute(
            "INSERT OR REPLACE INTO schedule (date, shift_type, is_holiday, is_override, note) "
            "VALUES (?, ?, ?, ?, ?)",
            (sd.date.isoformat(), sd.shift_type.value,
             int(sd.is_holiday), int(sd.is_override), sd.note)
        )
        self.db.commit()

    def save_schedules_bulk(self, schedules: list[ScheduleDay]):
        for sd in schedules:
            self.db.execute(
                "INSERT OR REPLACE INTO schedule (date, shift_type, is_holiday, is_override, note) "
                "VALUES (?, ?, ?, ?, ?)",
                (sd.date.isoformat(), sd.shift_type.value,
                 int(sd.is_holiday), int(sd.is_override), sd.note)
            )
        self.db.commit()

    def delete_schedules_from(self, start_date: date):
        self.db.execute(
            "DELETE FROM schedule WHERE date >= ?", (start_date.isoformat(),)
        )
        self.db.commit()

    # ─── 闹钟日志 ─────────────────────────────────────

    def get_pending_alarms(self, before: datetime | None = None) -> list[AlarmLog]:
        if before:
            rows = self.db.execute(
                "SELECT * FROM alarm_log WHERE status=0 AND alarm_time <= ?",
                (before.isoformat(),)
            ).fetchall()
        else:
            rows = self.db.execute(
                "SELECT * FROM alarm_log WHERE status=0"
            ).fetchall()
        return [AlarmLog(
            id=row["id"],
            schedule_id=row["schedule_id"],
            alarm_time=datetime.fromisoformat(row["alarm_time"]),
            shift_type=ShiftType(row["shift_type"]),
            status=row["status"],
            fired_at=datetime.fromisoformat(row["fired_at"]) if row["fired_at"] else None,
        ) for row in rows]

    def create_alarm(self, log: AlarmLog) -> int:
        cur = self.db.execute(
            "INSERT INTO alarm_log (schedule_id, alarm_time, shift_type) VALUES (?, ?, ?)",
            (log.schedule_id, log.alarm_time.isoformat(), log.shift_type.value)
        )
        self.db.commit()
        return cur.lastrowid

    def update_alarm_status(self, alarm_id: int, status: int, fired_at: datetime | None = None):
        self.db.execute(
            "UPDATE alarm_log SET status=?, fired_at=? WHERE id=?",
            (status, fired_at.isoformat() if fired_at else None, alarm_id)
        )
        self.db.commit()

    def delete_future_alarms(self):
        self.db.execute("DELETE FROM alarm_log WHERE status=0")
        self.db.commit()

    # ─── 节假日缓存 ───────────────────────────────────

    def get_holiday(self, d: date) -> HolidayCache | None:
        row = self.db.execute(
            "SELECT * FROM holiday_cache WHERE date=?", (d.isoformat(),)
        ).fetchone()
        if not row:
            return None
        return HolidayCache(
            date=date.fromisoformat(row["date"]),
            year=row["year"],
            is_holiday=bool(row["is_holiday"]),
            is_workday=bool(row["is_workday"]),
            name=row["name"],
        )

    def save_holidays(self, holidays: list[HolidayCache]):
        for h in holidays:
            self.db.execute(
                "INSERT OR REPLACE INTO holiday_cache (date, year, is_holiday, is_workday, name) "
                "VALUES (?, ?, ?, ?, ?)",
                (h.date.isoformat(), h.year, int(h.is_holiday), int(h.is_workday), h.name)
            )
        self.db.commit()
