"""系统设置视图 — 闹钟参数 + 节假日管理"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from core.holiday_service import HolidayService
from ui.dialogs import show_info, show_error


def build(parent: ttk.Frame, app):
    for w in parent.winfo_children():
        w.destroy()

    d = app.design
    settings = app.repo.load_settings()

    page = tk.Frame(parent, bg=d["page_bg"])
    page.pack(fill=tk.BOTH, expand=True)

    # ── 标题 ──
    header = tk.Frame(page, bg=d["page_bg"])
    header.pack(fill=tk.X, padx=24, pady=(20, 4))
    tk.Label(header, text="系统设置",
             font=("Microsoft YaHei UI", 20, "bold"),
             fg=d["text_primary"], bg=d["page_bg"]).pack(side=tk.LEFT)
    tk.Label(header, text="闹钟参数、节假日数据管理",
             font=("Microsoft YaHei UI", 10),
             fg=d["text_secondary"], bg=d["page_bg"]).pack(side=tk.LEFT, padx=(12, 0))

    # ── 闹钟设置卡片 ──
    card1 = tk.Frame(page, bg=d["card_bg"], highlightthickness=1, highlightbackground=d["border"])
    card1.pack(fill=tk.X, padx=24, pady=(12, 12))

    c1_inner = tk.Frame(card1, bg=d["card_bg"])
    c1_inner.pack(fill=tk.X, padx=20, pady=16)

    tk.Label(c1_inner, text="闹钟参数", font=("Microsoft YaHei UI", 13, "bold"),
             fg=d["text_primary"], bg=d["card_bg"]).pack(anchor="w", pady=(0, 12))

    # 延迟分钟
    r1 = tk.Frame(c1_inner, bg=d["card_bg"])
    r1.pack(fill=tk.X, pady=(0, 10))
    tk.Label(r1, text="延迟分钟", fg=d["text_secondary"], bg=d["card_bg"],
             font=("Microsoft YaHei UI", 10), width=10, anchor="e").pack(side=tk.LEFT)
    snooze_var = tk.IntVar(value=settings.snooze_minutes)
    ttk.Spinbox(r1, from_=1, to=60, textvariable=snooze_var, width=6).pack(side=tk.LEFT, padx=(10, 6))
    tk.Label(r1, text="闹钟触发后延迟再响的时间 (1-60 分钟)",
             fg=d["text_muted"], bg=d["card_bg"], font=("Microsoft YaHei UI", 9)).pack(side=tk.LEFT)

    # 音量
    r2 = tk.Frame(c1_inner, bg=d["card_bg"])
    r2.pack(fill=tk.X)
    tk.Label(r2, text="闹钟音量", fg=d["text_secondary"], bg=d["card_bg"],
             font=("Microsoft YaHei UI", 10), width=10, anchor="e").pack(side=tk.LEFT)
    vol_var = tk.IntVar(value=settings.alarm_volume)
    ttk.Scale(r2, from_=0, to=100, variable=vol_var, orient="horizontal", length=200).pack(side=tk.LEFT, padx=(10, 8))
    vol_disp = tk.Label(r2, text=f"{settings.alarm_volume}%", fg=d["text_primary"], bg=d["card_bg"],
                        font=("Segoe UI", 10), width=5)
    vol_disp.pack(side=tk.LEFT)
    vol_var.trace_add("write", lambda *_: vol_disp.configure(text=f"{vol_var.get()}%"))

    # ── 节假日卡片 ──
    card2 = tk.Frame(page, bg=d["card_bg"], highlightthickness=1, highlightbackground=d["border"])
    card2.pack(fill=tk.X, padx=24, pady=(0, 12))

    c2_inner = tk.Frame(card2, bg=d["card_bg"])
    c2_inner.pack(fill=tk.X, padx=20, pady=16)

    tk.Label(c2_inner, text="节假日管理", font=("Microsoft YaHei UI", 13, "bold"),
             fg=d["text_primary"], bg=d["card_bg"]).pack(anchor="w", pady=(0, 8))

    tk.Label(c2_inner, text="数据来源于 holidays-calendar.net，用于自动识别法定假期。建议每年初刷新一次。",
             fg=d["text_muted"], bg=d["card_bg"], font=("Microsoft YaHei UI", 9)).pack(anchor="w", pady=(0, 10))

    yr_row = tk.Frame(c2_inner, bg=d["card_bg"])
    yr_row.pack(fill=tk.X)
    tk.Label(yr_row, text="年份", fg=d["text_secondary"], bg=d["card_bg"],
             font=("Microsoft YaHei UI", 10), width=10, anchor="e").pack(side=tk.LEFT)
    yr_var = tk.IntVar(value=2026)
    ttk.Spinbox(yr_row, from_=2024, to=2030, textvariable=yr_var, width=8).pack(side=tk.LEFT, padx=(10, 10))

    status_var = tk.StringVar(value="")

    def _refresh():
        year = yr_var.get()
        status_var.set(f"正在获取 {year} 年节假日数据...")
        try:
            HolidayService(app.repo).refresh_year(year)
            status_var.set(f"{year} 年节假日数据已刷新")
            show_info(parent, "完成", f"{year} 年节假日数据已成功刷新。")
        except Exception as e:
            status_var.set(f"刷新失败: {e}")
            show_error(parent, "刷新失败", str(e))

    ttk.Button(yr_row, text="刷新节假日", command=_refresh).pack(side=tk.LEFT)

    tk.Label(c2_inner, textvariable=status_var, fg=d["text_muted"], bg=d["card_bg"],
             font=("Microsoft YaHei UI", 9)).pack(anchor="w", pady=(8, 0))

    # ── 保存按钮 ──
    bottom = tk.Frame(page, bg=d["page_bg"])
    bottom.pack(fill=tk.X, padx=24, pady=(0, 16))

    def _save():
        try:
            app.repo.set_setting("snooze_minutes", str(snooze_var.get()))
            app.repo.set_setting("alarm_volume", str(vol_var.get()))
            app.after_save()
            show_info(parent, "保存成功", "系统设置已保存。")
        except Exception as e:
            show_error(parent, "保存失败", str(e))

    ttk.Button(bottom, text="保存设置", command=_save).pack(side=tk.RIGHT)
