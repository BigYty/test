"""系统设置视图"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from config.constants import ShiftType, SHIFT_NAMES, SHIFT_COLORS
from core.holiday_service import HolidayService
from ui.dialogs import show_info, show_confirm, show_error


def build(parent: ttk.Frame, app):
    """构建系统设置视图

    Args:
        parent: 父 Frame (ttk.Frame)
        app: MainApp 实例，提供 app.repo, app.after_save, app.show_view 等
    """
    # ── 标题 ─────────────────────────────────────
    title_label = ttk.Label(
        parent,
        text="系统设置",
        font=("", 14, "bold"),
    )
    title_label.pack(fill="x", padx=12, pady=(12, 12))

    # ── Notebook 分页 ────────────────────────────
    notebook = ttk.Notebook(parent)
    notebook.pack(fill="both", expand=True, padx=12, pady=(0, 12))

    # ── 闹钟设置页 ───────────────────────────────
    alarm_page = ttk.Frame(notebook)
    notebook.add(alarm_page, text="闹钟设置")

    # ── 节假日设置页 ─────────────────────────────
    holiday_page = ttk.Frame(notebook)
    notebook.add(holiday_page, text="节假日管理")

    # ===============================================
    # 闹钟设置页
    # ===============================================

    # 加载当前设置
    settings = app.repo.load_settings()

    # ── 延迟分钟数 ────────────────────────────
    snooze_frame = ttk.Frame(alarm_page)
    snooze_frame.pack(fill="x", padx=12, pady=(12, 4))

    snooze_label = ttk.Label(snooze_frame, text="延迟分钟数:", width=14, anchor="e")
    snooze_label.pack(side="left", padx=(0, 8))

    snooze_var = tk.IntVar(value=settings.snooze_minutes)

    def _validate_snooze(P):
        """验证 Spinbox 输入"""
        if P == "":
            return True
        try:
            val = int(P)
            return 1 <= val <= 60
        except ValueError:
            return False

    vcmd = (alarm_page.register(_validate_snooze), "%P")

    snooze_spin = ttk.Spinbox(
        snooze_frame,
        from_=1,
        to=60,
        textvariable=snooze_var,
        width=6,
        validate="key",
        validatecommand=vcmd,
    )
    snooze_spin.pack(side="left")

    snooze_hint = ttk.Label(
        snooze_frame,
        text="分钟 (1-60)  —  闹钟触发后延迟再响的时间",
        foreground="gray",
    )
    snooze_hint.pack(side="left", padx=8)

    # ── 闹钟音量 ──────────────────────────────
    volume_frame = ttk.Frame(alarm_page)
    volume_frame.pack(fill="x", padx=12, pady=(12, 4))

    volume_label = ttk.Label(volume_frame, text="闹钟音量:", width=14, anchor="e")
    volume_label.pack(side="left", padx=(0, 8))

    volume_var = tk.IntVar(value=settings.alarm_volume)

    volume_scale = ttk.Scale(
        volume_frame,
        from_=0,
        to=100,
        variable=volume_var,
        orient="horizontal",
        length=200,
    )
    volume_scale.pack(side="left")

    volume_display = ttk.Label(
        volume_frame,
        text=f"{settings.alarm_volume}%",
        width=5,
    )
    volume_display.pack(side="left", padx=8)

    def _on_volume_change(*args):
        volume_display.config(text=f"{volume_var.get()}%")

    volume_var.trace_add("write", _on_volume_change)

    # ===============================================
    # 节假日设置页
    # ===============================================

    # ── 年份输入 ──────────────────────────────
    year_frame = ttk.Frame(holiday_page)
    year_frame.pack(fill="x", padx=12, pady=(12, 8))

    year_label = ttk.Label(year_frame, text="年份:", width=10, anchor="e")
    year_label.pack(side="left", padx=(0, 8))

    year_var = tk.IntVar(value=2024)

    year_spin = ttk.Spinbox(
        year_frame,
        from_=2024,
        to=2030,
        textvariable=year_var,
        width=8,
    )
    year_spin.pack(side="left")

    holiday_status_var = tk.StringVar(value="")

    def _refresh_holiday():
        """刷新节假日数据"""
        year = year_var.get()
        holiday_status_var.set(f"正在获取 {year} 年节假日数据...")
        year_spin.config(state="disabled")
        refresh_btn.config(state="disabled")

        try:
            service = HolidayService(app.repo)
            service.refresh_year(year)
            holiday_status_var.set(f"{year} 年节假日数据已刷新")
            show_info(parent, "完成", f"{year} 年节假日数据已成功刷新。")
        except Exception as e:
            holiday_status_var.set(f"刷新失败: {e}")
            show_error(parent, "刷新失败", str(e))
        finally:
            year_spin.config(state="normal")
            refresh_btn.config(state="normal")

    refresh_btn = ttk.Button(
        year_frame,
        text="刷新节假日数据",
        command=_refresh_holiday,
    )
    refresh_btn.pack(side="left", padx=8)

    # 状态显示
    holiday_status_label = ttk.Label(
        holiday_page,
        textvariable=holiday_status_var,
        foreground="gray",
    )
    holiday_status_label.pack(fill="x", padx=12, pady=(8, 4))

    # 节假日说明
    holiday_info = ttk.Label(
        holiday_page,
        text=(
            "节假日数据来源于 holidays-calendar.net，\n"
            "用于自动识别假期并减少非必要的闹钟提醒。\n"
            "建议每年初刷新一次。"
        ),
        foreground="gray",
        justify="left",
    )
    holiday_info.pack(fill="x", padx=12, pady=(8, 12))

    # ===============================================
    # 底部保存按钮
    # ===============================================
    bottom_frame = ttk.Frame(parent)
    bottom_frame.pack(fill="x", padx=12, pady=(0, 12))

    def _save_settings():
        """保存所有设置"""
        try:
            # 保存延迟分钟数
            app.repo.set_setting("snooze_minutes", str(snooze_var.get()))

            # 保存音量
            app.repo.set_setting("alarm_volume", str(volume_var.get()))

            # 触发后处理
            app.after_save()
            show_info(parent, "保存成功", "系统设置已保存。")
        except Exception as e:
            show_error(parent, "保存失败", str(e))

    save_btn = ttk.Button(
        bottom_frame,
        text="保存设置",
        command=_save_settings,
    )
    save_btn.pack(side="right")
