"""班次配置视图 —— 6 种班次的编辑卡片"""

import tkinter as tk
from tkinter import ttk, messagebox

from config.constants import ShiftType, SHIFT_NAMES, SHIFT_COLORS
from core.time_utils import minutes_to_time_str, time_str_to_minutes
from db.models import ShiftConfig


def build(parent: ttk.Frame, app):
    """构建班次配置视图。

    显示 6 种班次（白班/夜班A/早班/休息/夜班B/值班）的编辑卡片，
    每个卡片包含时间设置和保存按钮。
    """
    # ── 清空父容器 ──
    for w in parent.winfo_children():
        w.destroy()

    # ── 主容器 ──
    main = ttk.Frame(parent, padding=(16, 12))
    main.pack(fill=tk.BOTH, expand=True)

    # ── 标题区域 ──
    title = ttk.Label(main, text="班次配置", font=("", 16, "bold"))
    title.pack(anchor=tk.W, pady=(0, 4))

    desc = ttk.Label(
        main,
        text="设置每种班次的开始/结束时间及提前提醒分钟数。"
             '跨日班次请勾选"次日"复选框。',
        foreground="gray",
    )
    desc.pack(anchor=tk.W, pady=(0, 16))

    # ── 加载数据 ──
    shifts = app.repo.get_all_shifts()
    shift_map: dict[ShiftType, ShiftConfig] = {s.shift_type: s for s in shifts}

    # ── 卡片网格 (2 列 x 3 行) ──
    cards_frame = ttk.Frame(main)
    cards_frame.pack(fill=tk.BOTH, expand=True)

    # 配置网格权重
    cards_frame.columnconfigure(0, weight=1, uniform="card_col")
    cards_frame.columnconfigure(1, weight=1, uniform="card_col")

    # 需要创建输入变量的 dict，key 为 shift_type
    entry_vars: dict[ShiftType, dict] = {}

    shift_order = list(ShiftType)  # 按枚举顺序

    for i, st in enumerate(shift_order):
        row = i // 2
        col = i % 2

        config = shift_map.get(st)
        if config is None:
            # 如果数据库中没有，用默认值创建
            from config.constants import DEFAULT_SHIFT_TIMES, DEFAULT_REMINDER_MINUTES
            default_start, default_end = DEFAULT_SHIFT_TIMES.get(st, (0, 0))
            config = ShiftConfig(
                shift_type=st,
                shift_name=SHIFT_NAMES.get(st, ""),
                start_time=default_start,
                end_time=default_end,
                reminder=DEFAULT_REMINDER_MINUTES,
            )

        card = _create_shift_card(cards_frame, st, config, entry_vars)
        card.grid(row=row, column=col, padx=6, pady=6, sticky="nsew")

    # ── 底部全局操作区 ──
    bottom = ttk.Frame(main)
    bottom.pack(fill=tk.X, pady=(12, 0))

    ttk.Button(
        bottom,
        text="保存所有班次",
        command=lambda: _save_all_shifts(app, entry_vars, shift_map),
    ).pack(side=tk.RIGHT)


def _create_shift_card(
    parent: ttk.Frame,
    shift_type: ShiftType,
    config: ShiftConfig,
    entry_vars: dict,
) -> ttk.LabelFrame:
    """创建单个班次编辑卡片。"""
    name = SHIFT_NAMES.get(shift_type, "未知")
    color = SHIFT_COLORS.get(shift_type, "#CCCCCC")

    card = ttk.LabelFrame(parent, text=f"  {name}  ", padding=(10, 8))

    # ── 左侧：彩色圆形标识 ──
    left_frame = ttk.Frame(card)
    left_frame.pack(side=tk.LEFT, padx=(0, 12), anchor=tk.N)

    circle_size = 24
    circle_canvas = tk.Canvas(
        left_frame, width=circle_size, height=circle_size,
        highlightthickness=0,
    )
    circle_canvas.pack(pady=(2, 4))
    circle_canvas.create_oval(
        2, 2, circle_size - 2, circle_size - 2,
        fill=color, outline="",
    )

    name_lbl = ttk.Label(left_frame, text=name, font=("", 8), foreground="gray")
    name_lbl.pack()

    # ── 右侧：编辑区 ──
    right_frame = ttk.Frame(card)
    right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    # 存储变量
    vars_dict = {}

    if shift_type == ShiftType.REST:
        # 休息班次无需设置时间
        rest_lbl = ttk.Label(
            right_frame,
            text="休息日无需设置时间",
            foreground="gray",
            font=("", 10),
        )
        rest_lbl.pack(pady=8)

        # 休息班次也有 reminder（可为 0）
        rem_frame = ttk.Frame(right_frame)
        rem_frame.pack(fill=tk.X, pady=(8, 0))
        ttk.Label(rem_frame, text="提前提醒 (分钟):").pack(side=tk.LEFT)
        rem_var = tk.StringVar(value=str(config.reminder))
        rem_spin = ttk.Spinbox(
            rem_frame, textvariable=rem_var, from_=0, to=1440,
            width=6,
        )
        rem_spin.pack(side=tk.LEFT, padx=(6, 0))
        vars_dict["reminder"] = rem_var
    else:
        # 非休息班次：开始时间、结束时间、次日复选框、提醒
        _build_time_row(right_frame, config, vars_dict)

    entry_vars[shift_type] = vars_dict
    return card


def _build_time_row(parent: ttk.Frame, config: ShiftConfig, vars_dict: dict):
    """构建时间编辑行（非休息班次）。"""

    # ── 开始时间 ──
    row1 = ttk.Frame(parent)
    row1.pack(fill=tk.X, pady=(0, 6))

    ttk.Label(row1, text="开始时间:", width=9).pack(side=tk.LEFT)
    start_str = minutes_to_time_str(config.start_time)
    # 去掉"次日"前缀，用复选框表示跨日
    start_display = start_str
    start_next_day = config.start_time >= 1440
    if start_next_day:
        remain = config.start_time % 1440
        h, m = divmod(remain, 60)
        start_display = f"{h:02d}:{m:02d}"

    start_var = tk.StringVar(value=start_display)
    start_entry = ttk.Entry(row1, textvariable=start_var, width=7)
    start_entry.pack(side=tk.LEFT, padx=(4, 4))

    start_next_var = tk.BooleanVar(value=start_next_day)
    start_cb = ttk.Checkbutton(row1, text="次日", variable=start_next_var)
    start_cb.pack(side=tk.LEFT, padx=(0, 12))

    vars_dict["start_time"] = start_var
    vars_dict["start_next_day"] = start_next_var

    # ── 结束时间 ──
    row2 = ttk.Frame(parent)
    row2.pack(fill=tk.X, pady=(0, 6))

    ttk.Label(row2, text="结束时间:", width=9).pack(side=tk.LEFT)
    end_next_day = config.end_time >= 1440
    if end_next_day:
        remain = config.end_time % 1440
    else:
        remain = config.end_time
    h, m = divmod(remain, 60)
    end_display = f"{h:02d}:{m:02d}"

    end_var = tk.StringVar(value=end_display)
    end_entry = ttk.Entry(row2, textvariable=end_var, width=7)
    end_entry.pack(side=tk.LEFT, padx=(4, 4))

    end_next_var = tk.BooleanVar(value=end_next_day)
    end_cb = ttk.Checkbutton(row2, text="次日", variable=end_next_var)
    end_cb.pack(side=tk.LEFT, padx=(0, 12))

    vars_dict["end_time"] = end_var
    vars_dict["end_next_day"] = end_next_var

    # ── 提前提醒 ──
    row3 = ttk.Frame(parent)
    row3.pack(fill=tk.X, pady=(0, 4))

    ttk.Label(row3, text="提前提醒:", width=9).pack(side=tk.LEFT)
    rem_var = tk.StringVar(value=str(config.reminder))
    rem_spin = ttk.Spinbox(
        row3, textvariable=rem_var, from_=0, to=1440,
        width=6,
    )
    rem_spin.pack(side=tk.LEFT, padx=(4, 4))
    ttk.Label(row3, text="分钟", foreground="gray").pack(side=tk.LEFT)

    vars_dict["reminder"] = rem_var


def _parse_time(entry_str: str, is_next_day: bool) -> int | None:
    """解析用户输入的时间字符串为绝对分钟数。

    复选框是跨日标志的唯一来源。若 Entry 中误含"次日"前缀则自动剥离，
    避免与复选框叠加造成双重偏移。

    Returns:
        绝对分钟数 (0~2879)，解析失败返回 None。
    """
    try:
        s = entry_str.strip()
        if not s:
            return None
        # 剥离"次日"前缀 —— 跨日只通过复选框控制
        if s.startswith("次日"):
            s = s[2:]
        minutes = time_str_to_minutes(s)
        if is_next_day:
            minutes += 1440
        return minutes
    except (ValueError, IndexError):
        return None


def _save_all_shifts(app, entry_vars: dict, shift_map: dict):
    """收集所有卡片的输入值并批量保存。"""
    errors = []

    for st, vars_dict in entry_vars.items():
        name = SHIFT_NAMES.get(st, "未知")

        # 提醒分钟数
        try:
            reminder = int(vars_dict.get("reminder", tk.StringVar(value="0")).get())
        except ValueError:
            reminder = 0

        if st == ShiftType.REST:
            config = ShiftConfig(
                shift_type=st,
                shift_name=name,
                start_time=0,
                end_time=0,
                reminder=reminder,
                is_active=True,
            )
            # 保留原有 id
            existing = shift_map.get(st)
            if existing and existing.id is not None:
                config.id = existing.id
        else:
            start_str = vars_dict.get("start_time", tk.StringVar(value="00:00")).get()
            end_str = vars_dict.get("end_time", tk.StringVar(value="00:00")).get()
            start_next = vars_dict.get("start_next_day", tk.BooleanVar(value=False)).get()
            end_next = vars_dict.get("end_next_day", tk.BooleanVar(value=False)).get()

            start_min = _parse_time(start_str, start_next)
            end_min = _parse_time(end_str, end_next)

            if start_min is None:
                errors.append(f"{name}：开始时间格式无效，请输入 HH:MM 格式")
                continue
            if end_min is None:
                errors.append(f"{name}：结束时间格式无效，请输入 HH:MM 格式")
                continue

            config = ShiftConfig(
                shift_type=st,
                shift_name=name,
                start_time=start_min,
                end_time=end_min,
                reminder=reminder,
                is_active=True,
            )
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
