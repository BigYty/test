"""全局配置管理 (单例)"""

from __future__ import annotations

from dataclasses import dataclass, field
from config.constants import WorkMode


@dataclass
class AppSettings:
    """应用全局设置"""
    work_mode: WorkMode = WorkMode.NORMAL
    cycle_start_date: str = ""          # YYYY-MM-DD，排班起始日期
    cycle_reference_index: int = 0      # 起始日期在循环中的索引
    auto_start: bool = False            # 开机自启
    alarm_sound_path: str = ""          # 自定义铃声路径（空=默认）
    alarm_volume: int = 80              # 音量 0-100
    snooze_minutes: int = 5             # 延迟分钟数
    first_run: bool = True              # 是否首次运行

    def to_dict(self) -> dict:
        return {
            "work_mode": self.work_mode.value,
            "cycle_start_date": self.cycle_start_date,
            "cycle_reference_index": self.cycle_reference_index,
            "auto_start": self.auto_start,
            "alarm_sound_path": self.alarm_sound_path,
            "alarm_volume": self.alarm_volume,
            "snooze_minutes": self.snooze_minutes,
            "first_run": self.first_run,
        }

    @classmethod
    def from_dict(cls, d: dict) -> AppSettings:
        return cls(
            work_mode=WorkMode(d.get("work_mode", 1)),
            cycle_start_date=d.get("cycle_start_date", ""),
            cycle_reference_index=d.get("cycle_reference_index", 0),
            auto_start=d.get("auto_start", False),
            alarm_sound_path=d.get("alarm_sound_path", ""),
            alarm_volume=d.get("alarm_volume", 80),
            snooze_minutes=d.get("snooze_minutes", 5),
            first_run=d.get("first_run", True),
        )
