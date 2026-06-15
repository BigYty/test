"""
排班闹钟 - 主入口（tkinter 原生桌面版）

启动流程：
  初始化数据库 → 创建 ShiftEngine → 创建 AlarmScheduler
  → 创建主窗口 MainApp → 创建系统托盘 → 进入 tkinter 主循环
"""

import os
import sys
import logging
from datetime import date, datetime, timedelta

# 确保项目根目录在 sys.path 中，支持绝对导入
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── 日志配置 ─────────────────────────────────────────

log_dir = os.path.join(os.path.expanduser("~"), "AppData", "Local", "ShiftAlarm")
os.makedirs(log_dir, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(log_dir, "app.log"), encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


# ── 通知回调 ─────────────────────────────────────────

def send_windows_notification(alarm_log):
    """发送 Windows 原生通知"""
    try:
        from winotify import Notification, audio
        from config.constants import SHIFT_NAMES

        shift_name = SHIFT_NAMES.get(alarm_log.shift_type, "未知班次")
        alarm_time_str = alarm_log.alarm_time.strftime("%H:%M") if alarm_log.alarm_time else ""

        toast = Notification(
            app_id="ShiftAlarm",
            title=f"⏰ 排班闹钟 - {shift_name}",
            msg=f"您的 {shift_name} 将于 {alarm_time_str} 开始\n请做好准备！",
            duration="long",
        )
        toast.set_audio(audio.Default, loop=False)
        toast.show()
        logger.info(f"已发送通知: {shift_name} @ {alarm_time_str}")
    except Exception as e:
        logger.warning(f"发送通知失败: {e}")


# ── 每日重算 ─────────────────────────────────────────

def _daily_reschedule(scheduler, repo):
    """每日凌晨重新计算闹钟"""
    logger.info("每日闹钟重算...")
    settings = repo.load_settings()
    try:
        cycle_start = (
            date.fromisoformat(settings.cycle_start_date)
            if settings.cycle_start_date
            else date.today()
        )
    except ValueError:
        cycle_start = date.today()

    cycle_pattern = repo.get_cycle_pattern()
    scheduler.reschedule_all(
        settings.work_mode, cycle_start,
        cycle_pattern, settings.cycle_reference_index,
    )


# ── 主入口 ───────────────────────────────────────────

def main():
    """主入口"""
    print("=" * 50)
    print("  排班闹钟 v2.0")
    print("  Windows 11 排班提醒工具（原生桌面版）")
    print("=" * 50)
    print()

    # 1. 初始化数据库
    from db.repository import Repository
    repo = Repository()
    repo.init_tables()
    repo.seed_defaults()

    # 2. 创建排班引擎
    from core.shift_engine import ShiftEngine
    engine = ShiftEngine(repo)

    # 3. 创建闹钟调度器
    from core.alarm_scheduler import AlarmScheduler
    from config.constants import WorkMode

    scheduler = AlarmScheduler(repo)
    scheduler.set_callback(send_windows_notification)
    scheduler.start()

    # 初始排程
    settings = repo.load_settings()
    try:
        cycle_start = (
            date.fromisoformat(settings.cycle_start_date)
            if settings.cycle_start_date
            else date.today()
        )
    except ValueError:
        cycle_start = date.today()
    cycle_pattern = repo.get_cycle_pattern()
    scheduler.reschedule_all(
        settings.work_mode, cycle_start,
        cycle_pattern, settings.cycle_reference_index,
    )
    logger.info("闹钟调度器已启动")

    # 每日凌晨重算
    from apscheduler.triggers.cron import CronTrigger
    scheduler.scheduler.add_job(
        lambda: _daily_reschedule(scheduler, repo),
        trigger=CronTrigger(hour=2, minute=0),
        id="daily_reschedule",
        replace_existing=True,
    )

    # 4. 重调度回调（供 UI 中使用）
    def reschedule():
        settings_ = repo.load_settings()
        try:
            cs = (
                date.fromisoformat(settings_.cycle_start_date)
                if settings_.cycle_start_date
                else date.today()
            )
        except ValueError:
            cs = date.today()
        cp = repo.get_cycle_pattern()
        scheduler.reschedule_all(
            settings_.work_mode, cs, cp, settings_.cycle_reference_index,
        )
        logger.info("已通过 UI 触发闹钟重调度")

    # 5. 创建主窗口
    from ui.app import MainApp
    app = MainApp(repo, engine, scheduler, reschedule)

    # 6. 创建系统托盘
    from ui.tray import create_tray
    tray = create_tray(
        root_app=app,
        on_open=app.show_window,
        on_quit=app.quit_app,
    )

    # 7. 刷新节假日数据（后台执行）
    try:
        from core.holiday_service import HolidayService
        holiday_svc = HolidayService(repo)
        holiday_svc.refresh_year(date.today().year)
    except Exception as e:
        logger.warning(f"节假日数据刷新失败: {e}")

    # 8. 进入 tkinter 主循环
    print("\n✅ 应用已启动！")
    print("📌 应用在系统托盘中运行，右键托盘图标可退出。\n")
    app.mainloop()

    # 清理
    if scheduler:
        scheduler.shutdown()
    logger.info("应用已退出")


if __name__ == "__main__":
    main()
