"""
系统托盘图标

使用 pystray + Pillow 创建系统托盘：
- 右键菜单：打开主界面 / 退出
- 双击托盘图标：显示主窗口
"""

import logging
import os
import threading

from PIL import Image

logger = logging.getLogger(__name__)

# 图标缓存路径（全局单例）
_tray_icon_path: str | None = None


def _get_icon_path() -> str:
    """生成托盘图标 PNG，返回文件路径（缓存复用）"""
    global _tray_icon_path
    if _tray_icon_path and os.path.exists(_tray_icon_path):
        return _tray_icon_path

    from PIL import Image, ImageDraw

    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 圆形蓝色背景
    draw.ellipse([4, 4, size - 4, size - 4], fill="#0078d4")

    # 钟表外圈
    draw.ellipse([16, 16, 48, 48], fill="white")
    # 时针
    draw.line([32, 32, 32, 20], fill="#0078d4", width=4)
    # 分针
    draw.line([32, 32, 42, 32], fill="#0078d4", width=3)

    log_dir = os.path.join(os.path.expanduser("~"), "AppData", "Local", "ShiftAlarm")
    icon_path = os.path.join(log_dir, "tray_icon.png")
    img.save(icon_path, "PNG")

    _tray_icon_path = icon_path
    return icon_path


def create_tray(root_app, on_open, on_quit):
    """创建系统托盘图标并启动后台线程。

    Args:
        root_app:   tkinter 主窗口（用于 attach/detach）
        on_open:   可调用对象，无参数 —— 打开/显示主界面
        on_quit:   可调用对象，无参数 —— 完全退出应用

    Returns:
        pystray.Icon 实例，或 None（创建失败时）
    """
    try:
        import pystray
    except ImportError:
        logger.warning("pystray 未安装，系统托盘不可用")
        return None

    try:
        icon_path = _get_icon_path()
        icon_img = Image.open(icon_path)
    except Exception:
        logger.exception("托盘图标创建失败")
        return None

    def _on_open(icon, item):
        on_open()

    def _on_quit(icon, item):
        on_quit()

    menu = pystray.Menu(
        pystray.MenuItem("打开主界面", _on_open, default=True),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("退出", _on_quit),
    )

    icon = pystray.Icon(
        "ShiftAlarm",
        icon_img,
        "排班闹钟",
        menu,
    )

    # 在守护线程中运行托盘事件循环
    tray_thread = threading.Thread(target=icon.run, daemon=True)
    tray_thread.start()

    logger.info("系统托盘已创建")
    return icon


