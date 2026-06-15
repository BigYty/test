"""
排班闹钟 - 主入口
启动 Web 服务器 + 系统托盘 + 闹钟调度 + Windows 通知
"""

import os
import sys
import json
import threading
import webbrowser
import logging
from datetime import date, datetime, timedelta
from pathlib import Path

# 配置日志
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


def create_tray_icon():
    """创建托盘图标（生成简单的 64x64 PNG）"""
    from PIL import Image, ImageDraw

    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 圆形背景
    draw.ellipse([4, 4, size - 4, size - 4], fill="#0078d4")

    # 钟表图标
    draw.ellipse([16, 16, 48, 48], fill="white")
    # 时针
    draw.line([32, 32, 32, 20], fill="#0078d4", width=4)
    # 分针
    draw.line([32, 32, 42, 32], fill="#0078d4", width=3)

    # 保存
    icon_path = os.path.join(log_dir, "tray_icon.png")
    img.save(icon_path, "PNG")
    return icon_path


# 延迟绑定的调度器引用，用于 Web API 路由在调度器就绪后访问
_scheduler_ref: dict = {"instance": None}


def _create_reschedule_callback(repo):
    """创建一个可延迟绑定的闹钟重调度回调。

    Web 服务器在调度器之前启动，因此回调使用可变引用在调用时查找调度器。
    """
    from config.constants import WorkMode

    def _reschedule():
        scheduler = _scheduler_ref.get("instance")
        if scheduler is None:
            logger.warning("重调度请求被忽略：调度器尚未就绪")
            return
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
            settings.work_mode,
            cycle_start,
            cycle_pattern,
            settings.cycle_reference_index,
        )
        logger.info("已通过 API 触发闹钟重调度")

    return _reschedule


def run_web_server(repo, reschedule_callback=None, host="127.0.0.1", port=8765):
    """在独立线程中启动 FastAPI 服务器"""
    from web.server import create_app

    app = create_app(repo, reschedule_callback=reschedule_callback)

    import uvicorn
    uvicorn.run(app, host=host, port=port, log_level="warning")


def run_alarm_scheduler(repo, on_alarm_callback):
    """启动闹钟调度器"""
    from core.alarm_scheduler import AlarmScheduler
    from config.constants import WorkMode

    settings = repo.load_settings()
    try:
        cycle_start = date.fromisoformat(settings.cycle_start_date) if settings.cycle_start_date else date.today()
    except ValueError:
        cycle_start = date.today()

    cycle_pattern = repo.get_cycle_pattern()
    ref_index = settings.cycle_reference_index

    scheduler = AlarmScheduler(repo)
    scheduler.set_callback(on_alarm_callback)
    scheduler.start()
    scheduler.reschedule_all(
        settings.work_mode, cycle_start, cycle_pattern, ref_index
    )

    # 注册每日凌晨重算
    from apscheduler.triggers.cron import CronTrigger
    scheduler.scheduler.add_job(
        lambda: _daily_reschedule(scheduler, repo),
        trigger=CronTrigger(hour=2, minute=0),
        id="daily_reschedule",
        replace_existing=True,
    )

    return scheduler


def _daily_reschedule(scheduler, repo):
    """每日凌晨重新计算闹钟"""
    logger.info("每日闹钟重算...")
    settings = repo.load_settings()
    try:
        cycle_start = date.fromisoformat(settings.cycle_start_date) if settings.cycle_start_date else date.today()
    except ValueError:
        cycle_start = date.today()

    cycle_pattern = repo.get_cycle_pattern()
    scheduler.reschedule_all(
        settings.work_mode, cycle_start,
        cycle_pattern, settings.cycle_reference_index
    )


def send_windows_notification(alarm_log):
    """发送 Windows 原生通知"""
    try:
        from winotify import Notification, audio

        # 获取班次名称
        from config.constants import SHIFT_NAMES, ShiftType
        shift_name = SHIFT_NAMES.get(alarm_log.shift_type, "未知班次")

        # 格式化时间
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


def setup_tray(repo, scheduler, host, port):
    """设置系统托盘图标"""
    try:
        import pystray
        from PIL import Image

        icon_path = create_tray_icon()
        icon_img = Image.open(icon_path)

        def on_open(icon, item):
            """打开 Web 界面"""
            webbrowser.open(f"http://{host}:{port}")

        def on_quit(icon, item):
            """退出应用"""
            logger.info("正在退出...")
            if scheduler:
                scheduler.shutdown()
            icon.stop()
            os._exit(0)

        menu = pystray.Menu(
            pystray.MenuItem("打开界面", on_open, default=True),
            pystray.MenuItem("退出", on_quit),
        )

        tray_icon = pystray.Icon(
            "ShiftAlarm",
            icon_img,
            "排班闹钟",
            menu,
        )

        logger.info("系统托盘已创建")
        return tray_icon

    except Exception as e:
        logger.warning(f"创建托盘失败: {e}，将以命令行模式运行")
        return None


def main():
    """主入口"""
    print("=" * 50)
    print("  排班闹钟 v1.0")
    print("  Windows 11 排班提醒工具")
    print("=" * 50)
    print()

    # 初始化数据库
    from db.repository import Repository
    repo = Repository()
    repo.init_tables()
    repo.seed_defaults()

    # 配置
    HOST = "127.0.0.1"
    PORT = 8765

    # 创建延迟绑定的重调度回调（调度器尚未创建，回调内部使用可变引用）
    reschedule_callback = _create_reschedule_callback(repo)

    # 启动 Web 服务器（后台线程）
    server_thread = threading.Thread(
        target=run_web_server, args=(repo, reschedule_callback, HOST, PORT),
        daemon=True,
    )
    server_thread.start()
    logger.info(f"Web 服务器已启动: http://{HOST}:{PORT}")

    # 启动闹钟调度器并注册到全局引用
    scheduler = run_alarm_scheduler(repo, send_windows_notification)
    _scheduler_ref["instance"] = scheduler
    logger.info("闹钟调度器已启动")

    # 刷新节假日数据
    try:
        from core.holiday_service import HolidayService
        holiday_svc = HolidayService(repo)
        holiday_svc.refresh_year(date.today().year)
    except Exception as e:
        logger.warning(f"节假日数据刷新失败: {e}")

    # 创建系统托盘
    tray = setup_tray(repo, scheduler, HOST, PORT)

    # 自动打开浏览器
    webbrowser.open(f"http://{HOST}:{PORT}")
    print(f"\n✅ 服务已启动！浏览器将自动打开 http://{HOST}:{PORT}")
    print("📌 应用在系统托盘中运行，右键托盘图标可退出。\n")

    # 运行托盘或等待
    if tray:
        try:
            tray.run()
        except KeyboardInterrupt:
            pass
    else:
        # 没有托盘时，命令行等待
        try:
            print("按 Ctrl+C 退出...")
            import time
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass

    # 清理
    if scheduler:
        scheduler.shutdown()
    logger.info("应用已退出")


if __name__ == "__main__":
    main()
