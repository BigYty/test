"""仪表盘视图 —— 应用首页，展示今日/明日班次、工作模式和月历"""

from __future__ import annotations

import tkinter as tk
from datetime import date
from tkinter import messagebox, ttk
from typing import Any

from config.constants import (
    SHIFT_COLORS,
    SHIFT_NAMES,
    ShiftType,
    WorkMode,
)
from core.time_utils import format_shift_time_range
from ui.widgets.calendar_grid import CalendarGrid, lighten_color


def build(parent: ttk.Frame, app: Any) -> None:
    """在 parent_frame 中构建仪表盘视图的 UI。

    Args:
        parent: 父容器 ttk.Frame
        app: MainApp 实例，提供 repo / engine / scheduler / show_view / after_save 等
    """
    # 清理已有内容（支持 refresh_current_view）
    for w in parent.winfo_children():
        w.destroy()

    # ── 顶部标题栏 ──────────────────────────────────
    _build_title_bar(parent, app)

    # ── 今日 / 明日班次卡片 ─────────────────────────
    cards_frame = ttk.Frame(parent)
    cards_frame.pack(fill="x", pady=(8, 4))
    cards_frame.columnconfigure(0, weight=1)
    cards_frame.columnconfigure(1, weight=1)

    _build_shift_card(cards_frame, app, col=0, label="今日班次", shift_getter=_get_today)
    _build_shift_card(cards_frame, app, col=1, label="明日班次", shift_getter=_get_tomorrow)

    # ── 工作模式指示 ────────────────────────────────
    _build_mode_indicator(parent, app)

    # ── 月历 ────────────────────────────────────────
    cal_container = ttk.Frame(parent)
    cal_container.pack(fill="both", expand=True, pady=(8, 0))
    cal_container.columnconfigure(0, weight=1)
    cal_container.rowconfigure(0, weight=1)

    cal = CalendarGrid(cal_container, app)
    cal.grid(row=0, column=0, sticky="nsew")
    # 将 calendar 引用挂在 parent 上供外部刷新使用
    parent._calendar = cal


# ═══════════════════════════════════════════════════════
# 内部辅助
# ═══════════════════════════════════════════════════════

def _get_settings(app: Any):
    """安全加载应用设置"""
    from config.settings import AppSettings
    try:
        return app.repo.load_settings()
    except Exception:
        return AppSettings()


def _get_today(app: Any):
    """获取今日排班 ScheduleDay"""
    settings = _get_settings(app)
    try:
        cycle_start = date.fromisoformat(settings.cycle_start_date) if settings.cycle_start_date else date.today()
    except ValueError:
        cycle_start = date.today()
    cycle_pattern = app.repo.get_cycle_pattern()
    return app.engine.get_today_shift(
        settings.work_mode, cycle_start, cycle_pattern,
        settings.cycle_reference_index,
    )


def _get_tomorrow(app: Any):
    """获取明日排班 ScheduleDay"""
    settings = _get_settings(app)
    try:
        cycle_start = date.fromisoformat(settings.cycle_start_date) if settings.cycle_start_date else date.today()
    except ValueError:
        cycle_start = date.today()
    cycle_pattern = app.repo.get_cycle_pattern()
    return app.engine.get_tomorrow_shift(
        settings.work_mode, cycle_start, cycle_pattern,
        settings.cycle_reference_index,
    )


# ─── 标题栏 ──────────────────────────────────────────

def _build_title_bar(parent: ttk.Frame, app: Any) -> None:
    bar = ttk.Frame(parent)
    bar.pack(fill="x")

    ttk.Label(bar, text="工作台", font=("TkDefaultFont", 16, "bold")).pack(side="left")

    def _refresh_holidays():
        today = date.today()
        try:
            from core.holiday_service import HolidayService
            svc = HolidayService(app.repo)
            svc.refresh_year(today.year)
            messagebox.showinfo("刷新完成", f"{today.year} 年节假日数据已更新。")
            app.refresh_current_view()
        except Exception as e:
            messagebox.showerror("刷新失败", str(e))

    ttk.Button(bar, text="刷新节假日", command=_refresh_holidays).pack(side="right")


# ─── 班次卡片 ────────────────────────────────────────

def _build_shift_card(
    parent: ttk.Frame,
    app: Any,
    col: int,
    label: str,
    shift_getter,
) -> None:
    """构建一个今日/明日班次卡片。

    卡片左边框使用班次颜色标识。
    """
    try:
        sd = shift_getter(app)
        shift_type = sd.shift_type
        is_holiday = sd.is_holiday
    except Exception:
        shift_type = ShiftType.REST
        is_holiday = False

    color = SHIFT_COLORS.get(shift_type, "#999999")
    shift_name = SHIFT_NAMES.get(shift_type, "未知")
    bg_color = lighten_color(color, 0.75)

    # 外层容器
    card = ttk.LabelFrame(parent, text=label, padding=(0, 4))
    card.grid(row=0, column=col, sticky="nsew", padx=(0 if col == 0 else 4, 4 if col == 0 else 0))

    inner = tk.Frame(card, bg=bg_color)
    inner.pack(fill="both", expand=True, padx=1, pady=1)

    # 左边框色条
    color_bar = tk.Frame(inner, bg=color, width=5)
    color_bar.pack(side="left", fill="y")

    # 内容区
    content = tk.Frame(inner, bg=bg_color)
    content.pack(side="left", fill="both", expand=True, padx=10, pady=8)

    # 班次名称（大字）
    name_lbl = tk.Label(
        content, text=shift_name,
        bg=bg_color, fg=color,
        font=("TkDefaultFont", 22, "bold"),
        anchor="w",
    )
    name_lbl.pack(anchor="w")

    # 时间范围
    try:
        shift_config = app.repo.get_shift(shift_type)
        time_range = format_shift_time_range(shift_config.start_time, shift_config.end_time)
    except Exception:
        time_range = "—"

    time_lbl = tk.Label(
        content, text=time_range,
        bg=bg_color, fg="#555555",
        font=("TkDefaultFont", 10),
        anchor="w",
    )
    time_lbl.pack(anchor="w", pady=(2, 0))

    # 节假日标记
    if is_holiday:
        holiday_lbl = tk.Label(
            content, text="🎌 节假日",
            bg=bg_color, fg="#E65100",
            font=("TkDefaultFont", 9, "bold"),
            anchor="w",
        )
        holiday_lbl.pack(anchor="w", pady=(4, 0))


# ─── 工作模式指示 ────────────────────────────────────

def _build_mode_indicator(parent: ttk.Frame, app: Any) -> None:
    settings = _get_settings(app)
    mode = settings.work_mode
    mode_text = "正常工作表" if mode == WorkMode.NORMAL else "特殊工种"
    mode_color = "#1976D2" if mode == WorkMode.NORMAL else "#7B1FA2"

    indicator = ttk.Frame(parent)
    indicator.pack(fill="x", pady=(6, 0))

    ttk.Label(indicator, text="当前模式：", font=("TkDefaultFont", 9)).pack(side="left")

    mode_lbl = tk.Label(
        indicator, text=mode_text,
        fg=mode_color, font=("TkDefaultFont", 9, "bold"),
        bg=_get_default_bg(),
    )
    mode_lbl.pack(side="left")


def _get_default_bg() -> str:
    try:
        return ttk.Style().lookup("TFrame", "background") or "#f0f0f0"
    except Exception:
        return "#f0f0f0"
