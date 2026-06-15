"""排班设置视图 — 工作模式、循环构建、日期设置、预览"""

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date, timedelta

from config.constants import (ShiftType, WorkMode, SHIFT_NAMES, SHIFT_COLORS,
                              NORMAL_MODE_SHIFTS, DEFAULT_WEEKLY_PATTERN)
from config.settings import AppSettings
from db.models import CyclePattern


def build(parent: ttk.Frame, app):
    for w in parent.winfo_children():
        w.destroy()

    d = app.design
    settings = app.repo.load_settings()
    cycle_patterns = app.repo.get_cycle_pattern()

    work_mode_var = tk.IntVar(value=int(settings.work_mode))

    page = tk.Frame(parent, bg=d["page_bg"])
    page.pack(fill=tk.BOTH, expand=True)

    # ── 标题 ──
    header = tk.Frame(page, bg=d["page_bg"])
    header.pack(fill=tk.X, padx=24, pady=(20, 4))
    tk.Label(header, text="排班设置",
             font=("Microsoft YaHei UI", 20, "bold"),
             fg=d["text_primary"], bg=d["page_bg"]).pack(side=tk.LEFT)
    tk.Label(header, text="设置工作模式、循环顺序和起始日期",
             font=("Microsoft YaHei UI", 10),
             fg=d["text_secondary"], bg=d["page_bg"]).pack(side=tk.LEFT, padx=(12, 0))

    # 可滚动内容区
    canvas = tk.Canvas(page, bg=d["page_bg"], highlightthickness=0)
    scrollbar = ttk.Scrollbar(page, orient="vertical", command=canvas.yview)
    content = tk.Frame(canvas, bg=d["page_bg"])

    content.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    _canvas_window = canvas.create_window((0, 0), window=content, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)

    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(24, 0), pady=(12, 0))
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 24), pady=(12, 0))

    # 让内嵌窗口宽度跟随 canvas
    def _resize_inner(event):
        canvas.itemconfig(_canvas_window, width=event.width)
    canvas.bind("<Configure>", _resize_inner)

    # 鼠标滚轮
    def _on_mousewheel(event):
        canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
    canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _on_mousewheel))
    canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))

    # ── 工作模式卡片 ──
    mode_card = tk.Frame(content, bg=d["card_bg"], highlightthickness=1, highlightbackground=d["border"])
    mode_card.pack(fill=tk.X, pady=(0, 12))

    mode_inner = tk.Frame(mode_card, bg=d["card_bg"])
    mode_inner.pack(fill=tk.X, padx=16, pady=12)

    tk.Label(mode_inner, text="工作模式", font=("Microsoft YaHei UI", 12, "bold"),
             fg=d["text_primary"], bg=d["card_bg"]).pack(anchor="w", pady=(0, 8))

    def on_mode_change():
        settings.work_mode = WorkMode(work_mode_var.get())
        app.repo.save_settings(settings)
        _refresh_mode_ui()

    ttk.Radiobutton(mode_inner, text="正常工作表 (周循环 + 法定节假日)",
                    variable=work_mode_var, value=WorkMode.NORMAL.value,
                    command=on_mode_change).pack(anchor="w", pady=(0, 3))
    ttk.Radiobutton(mode_inner, text="特殊工种 (自定义循环顺序)",
                    variable=work_mode_var, value=WorkMode.SPECIAL.value,
                    command=on_mode_change).pack(anchor="w")

    # ── 循环构建卡片（仅特殊工种）─
    cycle_card = tk.Frame(content, bg=d["card_bg"], highlightthickness=1, highlightbackground=d["border"])

    from ui.widgets.cycle_builder import CycleBuilder
    builder = CycleBuilder(cycle_card, app)
    builder.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)
    builder.set_pattern(cycle_patterns)

    # ── 起始设置卡片 ──
    start_card = tk.Frame(content, bg=d["card_bg"], highlightthickness=1, highlightbackground=d["border"])
    start_card.pack(fill=tk.X, pady=(12, 12))

    start_inner = tk.Frame(start_card, bg=d["card_bg"])
    start_inner.pack(fill=tk.X, padx=16, pady=12)

    tk.Label(start_inner, text="起始设置", font=("Microsoft YaHei UI", 12, "bold"),
             fg=d["text_primary"], bg=d["card_bg"]).pack(anchor="w", pady=(0, 8))

    # 日期
    dr = tk.Frame(start_inner, bg=d["card_bg"])
    dr.pack(fill=tk.X, pady=(0, 6))
    tk.Label(dr, text="起始日期", fg=d["text_secondary"], bg=d["card_bg"],
             font=("Microsoft YaHei UI", 9), width=12, anchor="e").pack(side=tk.LEFT)
    sd_str = settings.cycle_start_date or date.today().isoformat()
    sd_var = tk.StringVar(value=sd_str)
    ttk.Entry(dr, textvariable=sd_var, width=14).pack(side=tk.LEFT, padx=(8, 6))
    tk.Label(dr, text="YYYY-MM-DD", fg=d["text_muted"], bg=d["card_bg"],
             font=("Segoe UI", 8)).pack(side=tk.LEFT)

    # 起始位置
    pr = tk.Frame(start_inner, bg=d["card_bg"])
    pr.pack(fill=tk.X)
    tk.Label(pr, text="起始循环位置", fg=d["text_secondary"], bg=d["card_bg"],
             font=("Microsoft YaHei UI", 9), width=12, anchor="e").pack(side=tk.LEFT)
    pos_var = tk.StringVar()
    pos_combo = ttk.Combobox(pr, textvariable=pos_var, state="readonly", width=30)
    pos_combo.pack(side=tk.LEFT, padx=(8, 0))

    def _update_position_combo():
        wm = WorkMode(work_mode_var.get())
        pos_combo["values"] = []
        if wm == WorkMode.SPECIAL:
            pat = builder.get_pattern()
            if pat:
                vals = [f"第 {i+1} 天: {SHIFT_NAMES.get(ShiftType(v), '?')}" for i, v in enumerate(pat)]
                pos_combo["values"] = vals
                ri = settings.cycle_reference_index
                pos_var.set(vals[ri] if 0 <= ri < len(vals) else (vals[0] if vals else ""))
                return
        else:
            wns = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
            vals = [f"{wns[i]}: {SHIFT_NAMES.get(DEFAULT_WEEKLY_PATTERN.get(i, ShiftType.REST), '?')}"
                    for i in range(7)]
            pos_combo["values"] = vals
            ri = settings.cycle_reference_index
            pos_var.set(vals[ri] if 0 <= ri < len(vals) else vals[0])

    _update_position_combo()

    # ── 预览卡片 ──
    preview_card = tk.Frame(content, bg=d["card_bg"], highlightthickness=1, highlightbackground=d["border"])
    preview_card.pack(fill=tk.BOTH, expand=True, pady=(0, 12))

    pv_header = tk.Frame(preview_card, bg=d["card_bg"])
    pv_header.pack(fill=tk.X, padx=16, pady=(12, 0))
    tk.Label(pv_header, text="未来 14 天预览", font=("Microsoft YaHei UI", 12, "bold"),
             fg=d["text_primary"], bg=d["card_bg"]).pack(side=tk.LEFT)
    refresh_preview_btn = ttk.Button(pv_header, text="刷新预览")
    refresh_preview_btn.pack(side=tk.RIGHT)

    tk.Frame(preview_card, bg=d["border"], height=1).pack(fill=tk.X, padx=16, pady=(8, 0))

    preview_table = tk.Frame(preview_card, bg=d["card_bg"])
    preview_table.pack(fill=tk.BOTH, expand=True, padx=16, pady=(4, 12))

    def _resolve_ref_index():
        pt = pos_var.get()
        wm = WorkMode(work_mode_var.get())
        if wm == WorkMode.SPECIAL:
            pat = builder.get_pattern()
            if pat:
                for idx, sv in enumerate(pat):
                    if pt == f"第 {idx+1} 天: {SHIFT_NAMES.get(ShiftType(sv), '?')}":
                        return idx
        else:
            wns = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
            for idx in range(7):
                if pt == f"{wns[idx]}: {SHIFT_NAMES.get(DEFAULT_WEEKLY_PATTERN.get(idx, ShiftType.REST), '?')}":
                    return idx
        return 0

    def _refresh_preview():
        for w in preview_table.winfo_children():
            w.destroy()

        try:
            s_date = date.fromisoformat(sd_var.get().strip())
        except (ValueError, TypeError):
            s_date = date.today()

        wm = WorkMode(work_mode_var.get())
        ref_idx = _resolve_ref_index()

        if wm == WorkMode.SPECIAL:
            rp = builder.get_pattern()
            if not rp:
                tk.Label(preview_table, text="请先设置自定义循环顺序",
                         fg=d["text_muted"], bg=d["card_bg"],
                         font=("Microsoft YaHei UI", 10)).pack(pady=20)
                return
            cycles = [CyclePattern(position=i, shift_type=ShiftType(v)) for i, v in enumerate(rp)]
        else:
            cycles = [CyclePattern(position=i, shift_type=st) for i, st in
                      sorted(DEFAULT_WEEKLY_PATTERN.items())]

        # 缩略表头
        hdr = tk.Frame(preview_table, bg="#f8fafc")
        hdr.pack(fill=tk.X)
        for txt, wd in [("日期", 12), ("星期", 6), ("班次", 10), ("时间", 20)]:
            tk.Label(hdr, text=txt, font=("Microsoft YaHei UI", 9, "bold"),
                     fg=d["text_secondary"], bg="#f8fafc", width=wd, anchor="w").pack(side=tk.LEFT, padx=2)

        wns = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

        for do in range(14):
            cd = s_date + timedelta(days=do)
            try:
                shift, is_hol = app.engine.get_shift_for_date(cd, wm, s_date, cycles, ref_idx)
            except Exception:
                shift, is_hol = ShiftType.REST, False

            sname = SHIFT_NAMES.get(shift, "?")
            sc = SHIFT_COLORS.get(shift, "#ccc")
            scfg = app.repo.get_shift(shift)
            from core.time_utils import format_shift_time_range
            tr = format_shift_time_range(scfg.start_time, scfg.end_time) if scfg else "-"
            wd_name = wns[cd.weekday()]

            row = tk.Frame(preview_table, bg=d["card_bg"] if do % 2 == 0 else "#f8fafc")
            row.pack(fill=tk.X)

            tk.Label(row, text=cd.isoformat(), fg=d["text_primary"], bg=row["bg"],
                     font=("Segoe UI", 9), width=12, anchor="w").pack(side=tk.LEFT, padx=2)
            tk.Label(row, text=wd_name, fg=d["text_secondary"], bg=row["bg"],
                     font=("Microsoft YaHei UI", 9), width=6, anchor="w").pack(side=tk.LEFT, padx=2)

            sf = tk.Frame(row, bg=row["bg"])
            sf.pack(side=tk.LEFT, padx=2)
            dot = tk.Canvas(sf, width=12, height=12, bg=row["bg"], highlightthickness=0)
            dot.pack(side=tk.LEFT, padx=(0, 4))
            dot.create_oval(1, 1, 11, 11, fill=sc, outline="")
            tk.Label(sf, text=sname, fg=d["text_primary"], bg=row["bg"],
                     font=("Microsoft YaHei UI", 9), width=10, anchor="w").pack(side=tk.LEFT)

            tk.Label(row, text=tr, fg=d["text_muted"], bg=row["bg"],
                     font=("Segoe UI", 9), width=20, anchor="w").pack(side=tk.LEFT, padx=2)

            if is_hol:
                tk.Label(row, text="休", fg="#dc2626", bg=row["bg"],
                         font=("Microsoft YaHei UI", 9, "bold"), width=3).pack(side=tk.LEFT)

    _refresh_preview()

    # 绑定刷新按钮（必须在函数定义之后）
    refresh_preview_btn.configure(command=_refresh_preview)

    # ── 模式 UI 切换 ──
    def _refresh_mode_ui():
        if WorkMode(work_mode_var.get()) == WorkMode.SPECIAL:
            cycle_card.pack(fill=tk.BOTH, expand=True, pady=(0, 12), before=start_card)
        else:
            cycle_card.pack_forget()
        _update_position_combo()
        _refresh_preview()

    _refresh_mode_ui()

    # ── 保存按钮 ──
    bottom = tk.Frame(page, bg=d["page_bg"])
    bottom.pack(fill=tk.X, padx=24, pady=(0, 16))

    def _on_save():
        wm = WorkMode(work_mode_var.get())
        try:
            s_date = date.fromisoformat(sd_var.get().strip())
        except (ValueError, TypeError):
            messagebox.showerror("格式错误", "起始日期格式无效，请使用 YYYY-MM-DD 格式。")
            return

        ref_idx = _resolve_ref_index()
        ns = AppSettings(work_mode=wm, cycle_start_date=s_date.isoformat(),
                         cycle_reference_index=ref_idx,
                         auto_start=settings.auto_start, alarm_sound_path=settings.alarm_sound_path,
                         alarm_volume=settings.alarm_volume, snooze_minutes=settings.snooze_minutes,
                         first_run=settings.first_run)
        app.repo.save_settings(ns)

        if wm == WorkMode.SPECIAL:
            cycles = [CyclePattern(position=i, shift_type=ShiftType(v))
                      for i, v in enumerate(builder.get_pattern())]
        else:
            cycles = [CyclePattern(position=d, shift_type=st)
                      for d, st in sorted(DEFAULT_WEEKLY_PATTERN.items())]
        app.repo.save_cycle_pattern(cycles)
        app.after_save()
        messagebox.showinfo("保存成功", "排班设置已保存。")

    ttk.Button(bottom, text="保存设置", command=_on_save).pack(side=tk.RIGHT)
