"""班次配置视图 — 6 种班次的编辑卡片"""

import tkinter as tk
from tkinter import ttk, messagebox

from config.constants import ShiftType, SHIFT_NAMES, SHIFT_COLORS, DEFAULT_SHIFT_TIMES, DEFAULT_REMINDER_MINUTES
from core.time_utils import minutes_to_time_str, time_str_to_minutes
from db.models import ShiftConfig


def build(parent: ttk.Frame, app):
    for w in parent.winfo_children():
        w.destroy()

    d = app.design
    page = tk.Frame(parent, bg=d["page_bg"])
    page.pack(fill=tk.BOTH, expand=True)

    # ── 标题 ──
    header = tk.Frame(page, bg=d["page_bg"])
    header.pack(fill=tk.X, padx=24, pady=(20, 4))
    tk.Label(header, text="班次配置",
             font=("Microsoft YaHei UI", 20, "bold"),
             fg=d["text_primary"], bg=d["page_bg"]).pack(side=tk.LEFT)
    tk.Label(header, text='设置每种班次的时间及提醒。跨日班次请勾选"次日"',
             font=("Microsoft YaHei UI", 10),
             fg=d["text_secondary"], bg=d["page_bg"]).pack(side=tk.LEFT, padx=(12, 0))

    # ── 卡片网格 ──
    grid_frame = tk.Frame(page, bg=d["page_bg"])
    grid_frame.pack(fill=tk.BOTH, expand=True, padx=24, pady=(12, 0))
    grid_frame.columnconfigure(0, weight=1, uniform="col")
    grid_frame.columnconfigure(1, weight=1, uniform="col")

    shifts = app.repo.get_all_shifts()
    shift_map: dict[ShiftType, ShiftConfig] = {s.shift_type: s for s in shifts}
    entry_vars: dict[ShiftType, dict] = {}

    for i, st in enumerate(ShiftType):
        row, col = i // 2, i % 2
        config = shift_map.get(st)
        if config is None:
            ds, de = DEFAULT_SHIFT_TIMES.get(st, (0, 0))
            config = ShiftConfig(shift_type=st, shift_name=SHIFT_NAMES.get(st, ""),
                                 start_time=ds, end_time=de, reminder=DEFAULT_REMINDER_MINUTES)
        card = _build_card(grid_frame, app, st, config, entry_vars, row, col)
        card.grid(row=row, column=col, padx=4, pady=4, sticky="nsew")

    # ── 底部保存 ──
    bottom = tk.Frame(page, bg=d["page_bg"])
    bottom.pack(fill=tk.X, padx=24, pady=(10, 16))
    ttk.Button(bottom, text="保存所有班次",
               command=lambda: _save_all(app, entry_vars, shift_map)).pack(side=tk.RIGHT)


def _build_card(parent, app, st, config, entry_vars, row, col):
    d = app.design
    color = SHIFT_COLORS.get(st, "#ccc")
    name = SHIFT_NAMES.get(st, "未知")

    card = tk.Frame(parent, bg=d["card_bg"], highlightthickness=1, highlightbackground=d["border"])
    # 顶条
    top_bar = tk.Frame(card, bg=color, height=3)
    top_bar.pack(fill=tk.X)
    top_bar.pack_propagate(False)

    inner = tk.Frame(card, bg=d["card_bg"])
    inner.pack(fill=tk.BOTH, expand=True, padx=16, pady=12)

    # 标题行：圆点 + 名称
    title_row = tk.Frame(inner, bg=d["card_bg"])
    title_row.pack(fill=tk.X, pady=(0, 8))
    dot = tk.Canvas(title_row, width=10, height=10, bg=d["card_bg"], highlightthickness=0)
    dot.pack(side=tk.LEFT, padx=(0, 6))
    dot.create_oval(1, 1, 9, 9, fill=color, outline="")
    tk.Label(title_row, text=name, font=("Microsoft YaHei UI", 12, "bold"),
             fg=d["text_primary"], bg=d["card_bg"]).pack(side=tk.LEFT)

    vars_dict = {}

    if st == ShiftType.REST:
        tk.Label(inner, text="休息日无需设置时间",
                 fg=d["text_muted"], bg=d["card_bg"], font=("Microsoft YaHei UI", 10)).pack(pady=4)
        rem_frame = tk.Frame(inner, bg=d["card_bg"])
        rem_frame.pack(fill=tk.X, pady=(8, 0))
        tk.Label(rem_frame, text="提前提醒", fg=d["text_secondary"], bg=d["card_bg"],
                 font=("Microsoft YaHei UI", 9)).pack(side=tk.LEFT)
        rv = tk.StringVar(value=str(config.reminder))
        ttk.Spinbox(rem_frame, textvariable=rv, from_=0, to=1440, width=6).pack(side=tk.LEFT, padx=(6, 4))
        tk.Label(rem_frame, text="分钟", fg=d["text_muted"], bg=d["card_bg"],
                 font=("Microsoft YaHei UI", 9)).pack(side=tk.LEFT)
        vars_dict["reminder"] = rv
    else:
        _time_row(inner, app, config, vars_dict)

    entry_vars[st] = vars_dict
    return card


def _time_row(parent, app, config, vars_dict):
    d = app.design

    # 开始时间
    r1 = tk.Frame(parent, bg=d["card_bg"])
    r1.pack(fill=tk.X, pady=(0, 6))
    tk.Label(r1, text="开始时间", fg=d["text_secondary"], bg=d["card_bg"],
             font=("Microsoft YaHei UI", 9), width=8, anchor="e").pack(side=tk.LEFT)

    start_disp = minutes_to_time_str(config.start_time)
    snd = config.start_time >= 1440
    if snd:
        rm = config.start_time % 1440
        hh, mm = divmod(rm, 60)
        start_disp = f"{hh:02d}:{mm:02d}"

    sv = tk.StringVar(value=start_disp)
    ttk.Entry(r1, textvariable=sv, width=7).pack(side=tk.LEFT, padx=(6, 4))
    snv = tk.BooleanVar(value=snd)
    ttk.Checkbutton(r1, text="次日", variable=snv).pack(side=tk.LEFT, padx=(0, 8))
    vars_dict["start_time"] = sv
    vars_dict["start_next_day"] = snv

    # 结束时间
    r2 = tk.Frame(parent, bg=d["card_bg"])
    r2.pack(fill=tk.X, pady=(0, 6))
    tk.Label(r2, text="结束时间", fg=d["text_secondary"], bg=d["card_bg"],
             font=("Microsoft YaHei UI", 9), width=8, anchor="e").pack(side=tk.LEFT)

    end_nd = config.end_time >= 1440
    rm2 = config.end_time % 1440 if end_nd else config.end_time
    hh2, mm2 = divmod(rm2, 60)
    ev = tk.StringVar(value=f"{hh2:02d}:{mm2:02d}")
    ttk.Entry(r2, textvariable=ev, width=7).pack(side=tk.LEFT, padx=(6, 4))
    env = tk.BooleanVar(value=end_nd)
    ttk.Checkbutton(r2, text="次日", variable=env).pack(side=tk.LEFT, padx=(0, 8))
    vars_dict["end_time"] = ev
    vars_dict["end_next_day"] = env

    # 提醒
    r3 = tk.Frame(parent, bg=d["card_bg"])
    r3.pack(fill=tk.X)
    tk.Label(r3, text="提前提醒", fg=d["text_secondary"], bg=d["card_bg"],
             font=("Microsoft YaHei UI", 9), width=8, anchor="e").pack(side=tk.LEFT)
    rv = tk.StringVar(value=str(config.reminder))
    ttk.Spinbox(r3, textvariable=rv, from_=0, to=1440, width=6).pack(side=tk.LEFT, padx=(6, 4))
    tk.Label(r3, text="分钟", fg=d["text_muted"], bg=d["card_bg"],
             font=("Microsoft YaHei UI", 9)).pack(side=tk.LEFT)
    vars_dict["reminder"] = rv


def _parse_time(entry_str: str, is_next_day: bool) -> int | None:
    try:
        s = entry_str.strip()
        if not s:
            return None
        if s.startswith("次日"):
            s = s[2:]
        minutes = time_str_to_minutes(s)
        if is_next_day:
            minutes += 1440
        return minutes
    except (ValueError, IndexError):
        return None


def _save_all(app, entry_vars, shift_map):
    errors = []
    for st, vs in entry_vars.items():
        name = SHIFT_NAMES.get(st, "未知")
        try:
            reminder = int(vs.get("reminder", tk.StringVar(value="0")).get())
        except ValueError:
            reminder = 0

        if st == ShiftType.REST:
            config = ShiftConfig(shift_type=st, shift_name=name, start_time=0, end_time=0,
                                 reminder=reminder, is_active=True)
        else:
            sm = _parse_time(vs.get("start_time", tk.StringVar(value="00:00")).get(),
                             vs.get("start_next_day", tk.BooleanVar(value=False)).get())
            em = _parse_time(vs.get("end_time", tk.StringVar(value="00:00")).get(),
                             vs.get("end_next_day", tk.BooleanVar(value=False)).get())
            if sm is None:
                errors.append(f"{name}：开始时间无效")
                continue
            if em is None:
                errors.append(f"{name}：结束时间无效")
                continue
            config = ShiftConfig(shift_type=st, shift_name=name, start_time=sm, end_time=em,
                                 reminder=reminder, is_active=True)

        existing = shift_map.get(st)
        if existing and existing.id is not None:
            config.id = existing.id

        try:
            app.repo.update_shift(config)
        except Exception as e:
            errors.append(f"{name}：保存失败 — {e}")

    if errors:
        messagebox.showerror("保存失败", "\n".join(errors))
    else:
        app.after_save()
        messagebox.showinfo("保存成功", "所有班次配置已保存。")
