"""仪表盘视图 — 现代 SaaS 风格"""

from __future__ import annotations

import tkinter as tk
from datetime import date
from tkinter import messagebox, ttk
from typing import Any

from config.constants import SHIFT_COLORS, SHIFT_NAMES, ShiftType, WorkMode
from core.time_utils import format_shift_time_range
from ui.widgets.calendar_grid import CalendarGrid, lighten_color


def build(parent: ttk.Frame, app: Any) -> None:
    for w in parent.winfo_children():
        w.destroy()

    d = app.design
    today = date.today()

    # ── 页面容器 ──
    page = tk.Frame(parent, bg=d["page_bg"])
    page.pack(fill=tk.BOTH, expand=True)

    # ── 顶部标题栏 ──
    header = tk.Frame(page, bg=d["page_bg"])
    header.pack(fill=tk.X, padx=24, pady=(20, 0))

    tk.Label(header, text="工作台",
             font=("Microsoft YaHei UI", 20, "bold"),
             fg=d["text_primary"], bg=d["page_bg"]).pack(side=tk.LEFT)

    # 当前日期
    weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    wd = weekday_names[today.weekday()]
    tk.Label(header,
             text=f"{today.year}年{today.month}月{today.day}日 {wd}",
             font=("Microsoft YaHei UI", 11),
             fg=d["text_secondary"], bg=d["page_bg"]).pack(side=tk.LEFT, padx=(16, 0))

    # 模式标签
    settings = _get_settings(app)
    mode = settings.work_mode
    mode_text = "正常工作表" if mode == WorkMode.NORMAL else "特殊工种"
    mode_color = d["success"] if mode == WorkMode.NORMAL else "#7c3aed"

    mode_tag = tk.Frame(header, bg=_lighten_hex(mode_color, 0.88))
    mode_tag.pack(side=tk.RIGHT)
    tk.Label(mode_tag, text=f"  {mode_text}  ",
             fg=mode_color, bg=_lighten_hex(mode_color, 0.88),
             font=("Microsoft YaHei UI", 9, "bold")).pack(padx=8, pady=2)

    # 刷新节假日
    def _refresh_holidays():
        try:
            from core.holiday_service import HolidayService
            HolidayService(app.repo).refresh_year(date.today().year)
            messagebox.showinfo("完成", "节假日数据已刷新。")
            app.refresh_current_view()
        except Exception as e:
            messagebox.showerror("失败", str(e))

    ttk.Button(header, text="刷新节假日", command=_refresh_holidays).pack(side=tk.RIGHT, padx=(0, 12))

    # ── 今日/明日卡片行 ──
    cards_row = tk.Frame(page, bg=d["page_bg"])
    cards_row.pack(fill=tk.X, padx=24, pady=(16, 0))

    _build_day_card(cards_row, app, "left", "今日班次", _get_today(app))
    _build_day_card(cards_row, app, "right", "明日班次", _get_tomorrow(app))

    # ── 月历 ──
    cal_section = tk.Frame(page, bg=d["card_bg"], highlightthickness=1, highlightbackground=d["border"])
    cal_section.pack(fill=tk.BOTH, expand=True, padx=24, pady=(16, 20))

    cal_header = tk.Frame(cal_section, bg=d["card_bg"])
    cal_header.pack(fill=tk.X, padx=16, pady=(12, 0))
    tk.Label(cal_header, text="月度排班",
             font=("Microsoft YaHei UI", 13, "bold"),
             fg=d["text_primary"], bg=d["card_bg"]).pack(side=tk.LEFT)

    cal = CalendarGrid(cal_section, app)
    cal.pack(fill=tk.BOTH, expand=True, padx=12, pady=(4, 12))
    parent._calendar = cal


# ═══════════════════════════════════════════════════════
# 今日/明日卡片
# ═══════════════════════════════════════════════════════

def _build_day_card(parent: tk.Frame, app: Any, side: str, label: str, sd):
    d = app.design

    try:
        shift_type = sd.shift_type
        is_holiday = sd.is_holiday
    except Exception:
        shift_type = ShiftType.REST
        is_holiday = False

    color = SHIFT_COLORS.get(shift_type, "#999999")
    shift_name = SHIFT_NAMES.get(shift_type, "未知")

    # 时间范围
    time_range = "—"
    try:
        sc = app.repo.get_shift(shift_type)
        if sc and sc.start_time != sc.end_time:
            time_range = format_shift_time_range(sc.start_time, sc.end_time)
    except Exception:
        pass

    # 卡片 — 白色底，彩色顶条
    card_w = tk.Frame(parent, bg=d["card_bg"], highlightthickness=1, highlightbackground=d["border"])
    pad_x = (0, 6) if side == "left" else (6, 0)
    card_w.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=pad_x)

    # 顶部 4px 彩色条
    top_bar = tk.Frame(card_w, bg=color, height=4)
    top_bar.pack(fill=tk.X)
    top_bar.pack_propagate(False)

    # 内容
    inner = tk.Frame(card_w, bg=d["card_bg"])
    inner.pack(fill=tk.BOTH, expand=True, padx=20, pady=16)

    # 标签
    tk.Label(inner, text=label,
             font=("Microsoft YaHei UI", 10),
             fg=d["text_secondary"], bg=d["card_bg"]).pack(anchor="w")

    # 班次名 — 大号彩色
    tk.Label(inner, text=shift_name,
             font=("Microsoft YaHei UI", 26, "bold"),
             fg=color, bg=d["card_bg"]).pack(anchor="w", pady=(4, 2))

    # 时间
    tk.Label(inner, text=time_range,
             font=("Segoe UI", 11),
             fg=d["text_muted"], bg=d["card_bg"]).pack(anchor="w")

    if is_holiday:
        tag = tk.Frame(inner, bg="#fef2f2")
        tag.pack(anchor="w", pady=(8, 0))
        tk.Label(tag, text="  法定节假日  ",
                 fg="#dc2626", bg="#fef2f2",
                 font=("Microsoft YaHei UI", 8, "bold")).pack(padx=6, pady=2)


# ═══════════════════════════════════════════════════════
# 辅助
# ═══════════════════════════════════════════════════════

def _get_settings(app):
    from config.settings import AppSettings
    try:
        return app.repo.load_settings()
    except Exception:
        return AppSettings()


def _get_today(app):
    settings = _get_settings(app)
    try:
        cs = date.fromisoformat(settings.cycle_start_date) if settings.cycle_start_date else date.today()
    except ValueError:
        cs = date.today()
    return app.engine.get_today_shift(
        settings.work_mode, cs, app.repo.get_cycle_pattern(), settings.cycle_reference_index)


def _get_tomorrow(app):
    settings = _get_settings(app)
    try:
        cs = date.fromisoformat(settings.cycle_start_date) if settings.cycle_start_date else date.today()
    except ValueError:
        cs = date.today()
    return app.engine.get_tomorrow_shift(
        settings.work_mode, cs, app.repo.get_cycle_pattern(), settings.cycle_reference_index)


def _lighten_hex(hex_color: str, factor: float = 0.7) -> str:
    hex_color = hex_color.lstrip("#")
    r = int(hex_color[0:2], 16); g = int(hex_color[2:4], 16); b = int(hex_color[4:6], 16)
    r = int(r + (255 - r) * factor); g = int(g + (255 - g) * factor); b = int(b + (255 - b) * factor)
    return f"#{r:02x}{g:02x}{b:02x}"
