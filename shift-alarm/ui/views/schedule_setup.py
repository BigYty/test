"""排班设置视图 —— 工作模式切换、循环构建、日期设置、预览"""

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date, timedelta

from config.constants import (
    ShiftType, WorkMode, SHIFT_NAMES, SHIFT_COLORS,
    NORMAL_MODE_SHIFTS, SPECIAL_MODE_SHIFTS, DEFAULT_WEEKLY_PATTERN,
)
from config.settings import AppSettings
from db.models import CyclePattern


def build(parent: ttk.Frame, app):
    """构建排班设置视图。"""
    # ── 清空父容器 ──
    for w in parent.winfo_children():
        w.destroy()

    # ── 加载当前设置 ──
    settings = app.repo.load_settings()
    cycle_patterns = app.repo.get_cycle_pattern()

    # ── 容器变量 ──
    work_mode_var = tk.IntVar(value=int(settings.work_mode))

    # ── 主容器 ──
    main = ttk.Frame(parent, padding=(16, 12))
    main.pack(fill=tk.BOTH, expand=True)

    # ── 标题 ──
    title = ttk.Label(main, text="排班设置", font=("", 16, "bold"))
    title.pack(anchor=tk.W, pady=(0, 16))

    # ══════════════════════════════════════════════════════
    # 第 1 节：工作模式
    # ══════════════════════════════════════════════════════
    mode_frame = ttk.LabelFrame(main, text=" 工作模式 ", padding=(12, 10))
    mode_frame.pack(fill=tk.X, pady=(0, 12))

    def on_mode_change():
        new_mode = WorkMode(work_mode_var.get())
        settings.work_mode = new_mode
        app.repo.save_settings(settings)
        # 刷新视图以显示/隐藏相关组件
        _refresh_mode_dependent_ui()

    rb1 = ttk.Radiobutton(
        mode_frame, text="正常工作表 (周循环)",
        variable=work_mode_var, value=WorkMode.NORMAL.value,
        command=on_mode_change,
    )
    rb1.pack(anchor=tk.W, pady=(0, 4))

    rb2 = ttk.Radiobutton(
        mode_frame, text="特殊工种 (自定义循环)",
        variable=work_mode_var, value=WorkMode.SPECIAL.value,
        command=on_mode_change,
    )
    rb2.pack(anchor=tk.W)

    # ══════════════════════════════════════════════════════
    # 第 2 节：自定义循环（仅特殊工种）
    # ══════════════════════════════════════════════════════
    cycle_frame = ttk.LabelFrame(main, text=" 自定义循环顺序 ", padding=(12, 10))

    # 创建 CycleBuilder（延迟导入避免循环依赖）
    from ui.widgets.cycle_builder import CycleBuilder
    builder = CycleBuilder(cycle_frame, app)
    builder.pack(fill=tk.BOTH, expand=True)
    builder.set_pattern(cycle_patterns)

    # ══════════════════════════════════════════════════════
    # 第 3 节：起始设置
    # ══════════════════════════════════════════════════════
    start_frame = ttk.LabelFrame(main, text=" 排班起始设置 ", padding=(12, 10))
    start_frame.pack(fill=tk.X, pady=(12, 12))

    # ── 起始日期 ──
    date_row = ttk.Frame(start_frame)
    date_row.pack(fill=tk.X, pady=(0, 8))

    ttk.Label(date_row, text="起始日期:", width=14).pack(side=tk.LEFT)
    start_date_str = settings.cycle_start_date or date.today().isoformat()
    start_date_var = tk.StringVar(value=start_date_str)
    date_entry = ttk.Entry(date_row, textvariable=start_date_var, width=14)
    date_entry.pack(side=tk.LEFT, padx=(4, 0))
    ttk.Label(
        date_row, text="  格式: YYYY-MM-DD", foreground="gray"
    ).pack(side=tk.LEFT)

    # ── 起始循环位置 ──
    pos_row = ttk.Frame(start_frame)
    pos_row.pack(fill=tk.X)

    ttk.Label(pos_row, text="起始循环位置:", width=14).pack(side=tk.LEFT)
    pos_var = tk.StringVar()
    pos_combo = ttk.Combobox(pos_row, textvariable=pos_var, state="readonly", width=30)
    pos_combo.pack(side=tk.LEFT, padx=(4, 0))

    def _update_position_combo():
        """根据当前循环模式更新位置下拉选项。"""
        current_mode = WorkMode(work_mode_var.get())
        pos_combo["values"] = []

        if current_mode == WorkMode.SPECIAL:
            pattern = builder.get_pattern()
            if pattern:
                values = []
                for idx, shift_val in enumerate(pattern):
                    st = ShiftType(shift_val)
                    name = SHIFT_NAMES.get(st, "未知")
                    values.append(f"第 {idx + 1} 天: {name}")
                pos_combo["values"] = values
                ref_idx = settings.cycle_reference_index
                if 0 <= ref_idx < len(values):
                    pos_var.set(values[ref_idx])
                elif values:
                    pos_var.set(values[0])
                return
        else:
            # 正常模式也显示一周的默认循环
            values = []
            for dow_idx in range(7):
                st = DEFAULT_WEEKLY_PATTERN.get(dow_idx, ShiftType.REST)
                name = SHIFT_NAMES.get(st, "未知")
                weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
                values.append(f"{weekday_names[dow_idx]}: {name}")
            pos_combo["values"] = values
            ref_idx = settings.cycle_reference_index
            if 0 <= ref_idx < len(values):
                pos_var.set(values[ref_idx])
            elif values:
                pos_var.set(values[0])

    _update_position_combo()

    # ══════════════════════════════════════════════════════
    # 第 4 节：14 天预览
    # ══════════════════════════════════════════════════════
    preview_frame = ttk.LabelFrame(main, text=" 未来 14 天预览 ", padding=(12, 10))
    preview_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 12))

    # 预览表格容器
    preview_table = ttk.Frame(preview_frame)
    preview_table.pack(fill=tk.BOTH, expand=True)

    def _resolve_ref_index_from_combo() -> int:
        """从 combobox 当前选择解析 cycle_reference_index。"""
        pos_text = pos_var.get()
        current_mode = WorkMode(work_mode_var.get())
        if current_mode == WorkMode.SPECIAL:
            pattern = builder.get_pattern()
            if pattern:
                for idx, shift_val in enumerate(pattern):
                    st = ShiftType(shift_val)
                    name = SHIFT_NAMES.get(st, "未知")
                    expected = f"第 {idx + 1} 天: {name}"
                    if pos_text == expected:
                        return idx
        else:
            weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
            for idx in range(7):
                st = DEFAULT_WEEKLY_PATTERN.get(idx, ShiftType.REST)
                name = SHIFT_NAMES.get(st, "未知")
                expected = f"{weekday_names[idx]}: {name}"
                if pos_text == expected:
                    return idx
        return 0

    def _refresh_preview():
        """刷新 14 天预览。"""
        for w in preview_table.winfo_children():
            w.destroy()

        # 解析起始日期
        s_date_str = start_date_var.get().strip()
        try:
            s_date = date.fromisoformat(s_date_str)
        except (ValueError, TypeError):
            s_date = date.today()

        current_mode = WorkMode(work_mode_var.get())

        # 从 combobox 当前选择解析 ref_index
        ref_index = _resolve_ref_index_from_combo()

        # 构建 CyclePattern 列表
        if current_mode == WorkMode.SPECIAL:
            raw_pattern = builder.get_pattern()
            if not raw_pattern:
                # 无循环时显示提示
                ttk.Label(
                    preview_table,
                    text="请先设置自定义循环顺序",
                    foreground="gray",
                ).pack(padx=8, pady=16)
                return
            cycles = [
                CyclePattern(position=i, shift_type=ShiftType(v))
                for i, v in enumerate(raw_pattern)
            ]
        else:
            raw_pattern = [
                DEFAULT_WEEKLY_PATTERN.get(d, ShiftType.REST) for d in range(7)
            ]
            cycles = [
                CyclePattern(position=i, shift_type=st)
                for i, st in enumerate(raw_pattern)
            ]

        # 表头
        header_frame = ttk.Frame(preview_table)
        header_frame.pack(fill=tk.X, pady=(0, 4))

        headers = [
            ("日期", 12), ("星期", 6), ("班次", 10), ("时间范围", 20)
        ]
        for text, width in headers:
            lbl = ttk.Label(header_frame, text=text, width=width,
                          font=("", 9, "bold"))
            lbl.pack(side=tk.LEFT, padx=2)

        ttk.Separator(preview_table, orient=tk.HORIZONTAL).pack(fill=tk.X)

        # 数据行
        weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

        for day_offset in range(14):
            current_date = s_date + timedelta(days=day_offset)

            # 计算班次
            try:
                shift, is_holiday = app.engine.get_shift_for_date(
                    current_date, current_mode,
                    s_date, cycles, ref_index,
                )
            except Exception:
                shift = ShiftType.REST
                is_holiday = False

            shift_name = SHIFT_NAMES.get(shift, "未知")
            shift_color = SHIFT_COLORS.get(shift, "#CCCCCC")
            weekday = weekday_names[current_date.weekday()]

            # 获取时间范围
            shift_config = app.repo.get_shift(shift)
            if shift_config:
                from core.time_utils import format_shift_time_range
                time_range = format_shift_time_range(
                    shift_config.start_time, shift_config.end_time
                )
            else:
                time_range = "-"

            # 行
            row_frame = ttk.Frame(preview_table)
            row_frame.pack(fill=tk.X, pady=1)

            # 日期列
            date_lbl = ttk.Label(
                row_frame,
                text=current_date.isoformat(),
                width=12,
            )
            date_lbl.pack(side=tk.LEFT, padx=2)

            # 星期列
            week_lbl = ttk.Label(row_frame, text=weekday, width=6)
            week_lbl.pack(side=tk.LEFT, padx=2)

            # 班次列（带颜色标识）
            shift_frame = tk.Frame(row_frame)
            shift_frame.pack(side=tk.LEFT, padx=2)

            color_indicator = tk.Canvas(
                shift_frame, width=14, height=14,
                highlightthickness=0,
            )
            color_indicator.pack(side=tk.LEFT)
            color_indicator.create_oval(
                1, 1, 13, 13, fill=shift_color, outline=""
            )

            shift_lbl = ttk.Label(shift_frame, text=shift_name, width=10)
            shift_lbl.pack(side=tk.LEFT, padx=(4, 0))

            # 时间范围列
            time_lbl = ttk.Label(row_frame, text=time_range, width=20)
            time_lbl.pack(side=tk.LEFT, padx=2)

            # 节假日标记
            if is_holiday:
                holiday_mark = ttk.Label(
                    row_frame, text="[休]", foreground="red", width=4
                )
                holiday_mark.pack(side=tk.LEFT)

    # ── 预览区域按钮 ──
    preview_btn_frame = ttk.Frame(preview_frame)
    preview_btn_frame.pack(fill=tk.X, pady=(8, 0))

    ttk.Button(
        preview_btn_frame, text="刷新预览", command=_refresh_preview,
    ).pack(side=tk.LEFT)

    _refresh_preview()

    # ══════════════════════════════════════════════════════
    # 底部保存按钮
    # ══════════════════════════════════════════════════════
    bottom = ttk.Frame(main)
    bottom.pack(fill=tk.X, pady=(4, 0))

    def _on_save():
        """保存所有排班设置。"""
        current_mode = WorkMode(work_mode_var.get())

        # 解析起始日期
        s_date_str = start_date_var.get().strip()
        try:
            s_date = date.fromisoformat(s_date_str)
        except (ValueError, TypeError):
            messagebox.showerror("格式错误", "起始日期格式无效，请使用 YYYY-MM-DD 格式。")
            return

        # 解析起始循环位置
        ref_index = _resolve_ref_index_from_combo()

        # 保存设置
        new_settings = AppSettings(
            work_mode=current_mode,
            cycle_start_date=s_date_str,
            cycle_reference_index=ref_index,
            auto_start=settings.auto_start,
            alarm_sound_path=settings.alarm_sound_path,
            alarm_volume=settings.alarm_volume,
            snooze_minutes=settings.snooze_minutes,
            first_run=settings.first_run,
        )
        app.repo.save_settings(new_settings)

        # 保存循环模式（特殊工种）
        if current_mode == WorkMode.SPECIAL:
            raw_pattern = builder.get_pattern()
            cycles = [
                CyclePattern(position=i, shift_type=ShiftType(v))
                for i, v in enumerate(raw_pattern)
            ]
        else:
            cycles = [
                CyclePattern(position=d, shift_type=st)
                for d, st in sorted(DEFAULT_WEEKLY_PATTERN.items())
            ]
        app.repo.save_cycle_pattern(cycles)

        # 触发后处理
        app.after_save()
        messagebox.showinfo("保存成功", "排班设置已保存。")

    ttk.Button(
        bottom, text="保存设置", command=_on_save,
    ).pack(side=tk.RIGHT)

    # ══════════════════════════════════════════════════════
    # 模式切换时的 UI 刷新
    # ══════════════════════════════════════════════════════
    def _refresh_mode_dependent_ui():
        """根据当前工作模式显示/隐藏相关组件。"""
        current_mode = WorkMode(work_mode_var.get())
        if current_mode == WorkMode.SPECIAL:
            cycle_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 12),
                           before=start_frame)
        else:
            cycle_frame.pack_forget()

        _update_position_combo()
        _refresh_preview()

    # 初始状态
    _refresh_mode_dependent_ui()
