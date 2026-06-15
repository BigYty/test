"""闹钟列表视图 — 自定义 Frame 列表，确保班次颜色正确显示"""

from __future__ import annotations

import tkinter as tk
from datetime import datetime
from tkinter import ttk

from config.constants import ShiftType, SHIFT_NAMES, SHIFT_COLORS

STATUS_TEXT: dict[int, str] = {0: "待触发", 1: "已触发", 2: "已关闭", 3: "已延迟"}


def build(parent: ttk.Frame, app):
    d = app.design

    # 清空
    for w in parent.winfo_children():
        w.destroy()

    page = tk.Frame(parent, bg=d["page_bg"])
    page.pack(fill=tk.BOTH, expand=True)

    # ── 标题 ──
    header = tk.Frame(page, bg=d["page_bg"])
    header.pack(fill=tk.X, padx=24, pady=(20, 4))

    tk.Label(header, text="闹钟列表",
             font=("Microsoft YaHei UI", 20, "bold"),
             fg=d["text_primary"], bg=d["page_bg"]).pack(side=tk.LEFT)

    tk.Label(header, text="未来即将触发的闹钟",
             font=("Microsoft YaHei UI", 10),
             fg=d["text_secondary"], bg=d["page_bg"]).pack(side=tk.LEFT, padx=(12, 0))

    refresh_btn = ttk.Button(header, text="刷新", command=lambda: _refresh())
    refresh_btn.pack(side=tk.RIGHT)

    # ── 列表卡片 ──
    list_card = tk.Frame(page, bg=d["card_bg"], highlightthickness=1, highlightbackground=d["border"])
    list_card.pack(fill=tk.BOTH, expand=True, padx=24, pady=(8, 0))

    # 表头
    col_header = tk.Frame(list_card, bg="#f8fafc")
    col_header.pack(fill=tk.X, padx=16, pady=(10, 0))

    tk.Label(col_header, text="触发时间", font=("Microsoft YaHei UI", 9, "bold"),
             fg=d["text_secondary"], bg="#f8fafc", width=16, anchor="w").pack(side=tk.LEFT)
    tk.Label(col_header, text="班次", font=("Microsoft YaHei UI", 9, "bold"),
             fg=d["text_secondary"], bg="#f8fafc", width=12, anchor="w").pack(side=tk.LEFT, padx=(24, 0))
    tk.Label(col_header, text="状态", font=("Microsoft YaHei UI", 9, "bold"),
             fg=d["text_secondary"], bg="#f8fafc", width=8, anchor="w").pack(side=tk.LEFT, padx=(24, 0))

    tk.Frame(list_card, bg=d["border"], height=1).pack(fill=tk.X, padx=16, pady=(6, 0))

    # 可滚动列表区
    canvas = tk.Canvas(list_card, bg=d["card_bg"], highlightthickness=0)
    scrollbar = ttk.Scrollbar(list_card, orient="vertical", command=canvas.yview)
    rows_frame = tk.Frame(canvas, bg=d["card_bg"])

    rows_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.create_window((0, 0), window=rows_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)

    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(16, 0), pady=(0, 12))
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=(0, 12), padx=(0, 4))

    # 鼠标滚轮
    def _on_mousewheel(event):
        canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
    canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _on_mousewheel))
    canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))

    # ── 空状态 ──
    empty_lbl = tk.Label(page, text="暂无即将触发的闹钟",
                         font=("Microsoft YaHei UI", 13),
                         fg=d["text_muted"], bg=d["page_bg"])

    # ── 底部状态 ──
    status_frame = tk.Frame(page, bg=d["page_bg"])
    status_frame.pack(fill=tk.X, padx=24, pady=(4, 16))
    status_var = tk.StringVar(value="")
    tk.Label(status_frame, textvariable=status_var, font=("Segoe UI", 9),
             fg=d["text_muted"], bg=d["page_bg"]).pack(side=tk.LEFT)

    # ── 自动刷新 ──
    _auto_id: list[int | None] = [None]

    def _refresh():
        for w in rows_frame.winfo_children():
            w.destroy()

        if not hasattr(app, "scheduler") or app.scheduler is None:
            status_var.set("调度器不可用")
            return

        try:
            alarms = app.scheduler.get_upcoming_alarms(limit=30)
        except Exception as e:
            status_var.set(f"获取失败: {e}")
            return

        if not alarms:
            canvas.pack_forget()
            scrollbar.pack_forget()
            empty_lbl.pack(fill=tk.BOTH, expand=True, pady=50)
        else:
            empty_lbl.pack_forget()
            canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(16, 0), pady=(0, 12))
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=(0, 12), padx=(0, 4))

            for idx, alarm in enumerate(alarms):
                try:
                    adt = datetime.fromisoformat(alarm["alarm_time"])
                    time_str = adt.strftime("%m/%d %H:%M")
                except (ValueError, KeyError):
                    time_str = alarm.get("alarm_time", "未知")

                shift_val = alarm.get("shift_type", 0)
                try:
                    st = ShiftType(shift_val)
                    sname = SHIFT_NAMES.get(st, alarm.get("shift_name", "?"))
                    scolor = SHIFT_COLORS.get(st, "#999")
                except ValueError:
                    sname = alarm.get("shift_name", "?")
                    scolor = "#999"

                astatus = alarm.get("status", 0)
                status_disp = STATUS_TEXT.get(astatus, f"状态{astatus}")

                # 行
                row_bg = d["card_bg"] if idx % 2 == 0 else "#f8fafc"
                row = tk.Frame(rows_frame, bg=row_bg, height=40)
                row.pack(fill=tk.X)
                row.pack_propagate(False)

                # 颜色圆点 + 时间
                c0 = tk.Frame(row, bg=row_bg)
                c0.pack(side=tk.LEFT, fill=tk.Y)
                dot = tk.Canvas(c0, width=10, height=10, bg=row_bg, highlightthickness=0)
                dot.pack(side=tk.LEFT, padx=(12, 8))
                dot.create_oval(1, 1, 9, 9, fill=scolor, outline="")
                tk.Label(c0, text=time_str, bg=row_bg, fg=d["text_primary"],
                         font=("Consolas", 10), width=14, anchor="w").pack(side=tk.LEFT)

                # 班次标签
                tag = tk.Frame(row, bg=scolor)
                tag.pack(side=tk.LEFT, padx=(24, 0), pady=6)
                tk.Label(tag, text=f" {sname} ",
                         bg=scolor, fg=_text_fg(scolor),
                         font=("Microsoft YaHei UI", 9, "bold")).pack(padx=10, pady=1)

                # 状态
                status_colors = {"待触发": d["accent"], "已触发": d["success"],
                                 "已关闭": d["text_muted"], "已延迟": "#f59e0b"}
                sf = status_colors.get(status_disp, d["text_muted"])
                tk.Label(row, text=status_disp,
                         bg=row_bg, fg=sf,
                         font=("Microsoft YaHei UI", 9), width=8, anchor="w").pack(
                    side=tk.LEFT, padx=(24, 0))

        status_var.set(f"共 {len(alarms)} 条  ·  更新时间: {datetime.now().strftime('%H:%M:%S')}")

    def _auto():
        _refresh()
        try:
            if parent.winfo_exists():
                _auto_id[0] = parent.after(30000, _auto)
        except Exception:
            pass

    def _on_destroy(*_):
        if _auto_id[0] is not None:
            try:
                parent.after_cancel(_auto_id[0])
            except Exception:
                pass

    parent.bind("<Destroy>", _on_destroy)
    _refresh()
    _auto_id[0] = parent.after(30000, _auto)


def _text_fg(hex_color: str) -> str:
    hex_color = hex_color.lstrip("#")
    r = int(hex_color[0:2], 16); g = int(hex_color[2:4], 16); b = int(hex_color[4:6], 16)
    return "#ffffff" if (0.299 * r + 0.587 * g + 0.114 * b) < 150 else "#000000"
