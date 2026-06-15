"""月历网格组件 —— 显示月度排班日历，支持手动覆盖排班"""

from __future__ import annotations

import math
import tkinter as tk
from datetime import date, timedelta
from tkinter import messagebox, ttk
from typing import Any

from config.constants import (
    SHIFT_COLORS,
    SHIFT_NAMES,
    ShiftType,
    WorkMode,
)

# 周几标签（周一~周日）
_WEEKDAY_LABELS = ["一", "二", "三", "四", "五", "六", "日"]


def _get_default_bg() -> str:
    """获取系统默认背景色"""
    try:
        return ttk.Style().lookup("TFrame", "background") or "#f0f0f0"
    except Exception:
        return "#f0f0f0"


def lighten_color(hex_color: str, factor: float = 0.7) -> str:
    """将十六进制颜色与白色混合以减淡。

    Args:
        hex_color: 原始颜色，如 "#FFB74D"
        factor: 混合因子，0=原色, 1=纯白，默认 0.7

    Returns:
        减淡后的十六进制颜色字符串
    """
    hex_color = hex_color.lstrip("#")
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    # 向白色混合：factor 越大越接近白色
    r = int(r + (255 - r) * factor)
    g = int(g + (255 - g) * factor)
    b = int(b + (255 - b) * factor)
    return f"#{r:02x}{g:02x}{b:02x}"


class CalendarGrid(ttk.Frame):
    """月历网格，显示指定月份的排班情况。

    使用方式::

        cal = CalendarGrid(parent, app, year=2026, month=6)
        cal.pack(fill="both", expand=True)
        cal.refresh(2026, 7)  # 切换到 7 月
    """

    def __init__(
        self,
        parent: tk.Widget,
        app: Any,
        year: int | None = None,
        month: int | None = None,
    ) -> None:
        today = date.today()
        self.year = year if year is not None else today.year
        self.month = month if month is not None else today.month
        self.app = app

        super().__init__(parent)

        # 申明网格行/列权重，使日历格子能均匀撑开
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=0)   # 导航栏
        self.rowconfigure(1, weight=0)   # 周标签
        self.rowconfigure(2, weight=1)   # 日期网格
        self.rowconfigure(3, weight=0)   # 图例

        self._build_nav()
        self._build_weekday_headers()
        self._build_grid_frame()
        self._build_legend()
        self._render_cells()

    # ─── 导航栏 ────────────────────────────────────────

    def _build_nav(self) -> None:
        nav = ttk.Frame(self)
        nav.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        nav.columnconfigure(2, weight=1)

        self._btn_prev = ttk.Button(nav, text="← 月", command=self._go_prev_month)
        self._btn_prev.grid(row=0, column=0, padx=2)

        self._lbl_title = ttk.Label(nav, font=("TkDefaultFont", 12, "bold"))
        self._lbl_title.grid(row=0, column=2)

        self._btn_next = ttk.Button(nav, text="月 →", command=self._go_next_month)
        self._btn_next.grid(row=0, column=3, padx=2)

        self._btn_today = ttk.Button(nav, text="今天", command=self._go_today)
        self._btn_today.grid(row=0, column=4, padx=(8, 2))

        self._update_title()

    def _update_title(self) -> None:
        self._lbl_title.configure(text=f"{self.year}年 {self.month}月")

    def _go_prev_month(self) -> None:
        if self.month == 1:
            self.refresh(self.year - 1, 12)
        else:
            self.refresh(self.year, self.month - 1)

    def _go_next_month(self) -> None:
        if self.month == 12:
            self.refresh(self.year + 1, 1)
        else:
            self.refresh(self.year, self.month + 1)

    def _go_today(self) -> None:
        today = date.today()
        self.refresh(today.year, today.month)

    # ─── 周标签 ────────────────────────────────────────

    def _build_weekday_headers(self) -> None:
        header_frame = ttk.Frame(self)
        header_frame.grid(row=1, column=0, sticky="ew", pady=(0, 4))
        for i in range(7):
            header_frame.columnconfigure(i, weight=1)

        weekend_color = "#999999"
        for i, label in enumerate(_WEEKDAY_LABELS):
            fg = weekend_color if i >= 5 else None
            lbl = ttk.Label(header_frame, text=label, anchor="center", font=("TkDefaultFont", 9))
            if fg:
                lbl.configure(foreground=fg)
            lbl.grid(row=0, column=i, sticky="ew")

    # ─── 日期网格容器 ─────────────────────────────────

    def _build_grid_frame(self) -> None:
        """构建标准 tk Frame 承载彩色格子（ttk Frame 不直接支持背景色）"""
        self._grid_frame = tk.Frame(self, bg=self._default_bg())
        self._grid_frame.grid(row=2, column=0, sticky="nsew")
        for i in range(7):
            self._grid_frame.columnconfigure(i, weight=1, uniform="calcol")
        for i in range(6):
            self._grid_frame.rowconfigure(i, weight=1, uniform="calrow")

    # ─── 图例 ──────────────────────────────────────────

    def _build_legend(self) -> None:
        legend = ttk.Frame(self)
        legend.grid(row=3, column=0, sticky="ew", pady=(8, 0))

        items = [
            (ShiftType.DAY_SHIFT, SHIFT_NAMES[ShiftType.DAY_SHIFT]),
            (ShiftType.NIGHT_SHIFT, SHIFT_NAMES[ShiftType.NIGHT_SHIFT]),
            (ShiftType.MORNING_SHIFT, SHIFT_NAMES[ShiftType.MORNING_SHIFT]),
            (ShiftType.REST, SHIFT_NAMES[ShiftType.REST]),
            (ShiftType.NIGHT_SHIFT_B, SHIFT_NAMES[ShiftType.NIGHT_SHIFT_B]),
            (ShiftType.ON_DUTY, SHIFT_NAMES[ShiftType.ON_DUTY]),
        ]

        for col_idx, (st, name) in enumerate(items):
            legend.columnconfigure(col_idx, weight=1)
            color = SHIFT_COLORS.get(st, "#999")
            item_frame = ttk.Frame(legend)
            item_frame.grid(row=0, column=col_idx, padx=2)

            swatch = tk.Frame(item_frame, width=14, height=14, bg=color, relief="solid", bd=1)
            swatch.pack(side="left", padx=(0, 3))

            lbl = ttk.Label(item_frame, text=name, font=("TkDefaultFont", 8))
            lbl.pack(side="left")

        # 节假日标记（第 2 行）
        holiday_frame = ttk.Frame(legend)
        holiday_frame.grid(row=1, column=0, columnspan=6, sticky="w", pady=(4, 0))
        holiday_swatch = tk.Frame(holiday_frame, width=14, height=14, bg="#FFD700", relief="solid", bd=1)
        holiday_swatch.pack(side="left", padx=(0, 3))
        ttk.Label(holiday_frame, text="节假日（金色边框）", font=("TkDefaultFont", 8)).pack(side="left")

    # ─── 渲染日历格子 ──────────────────────────────────

    def _render_cells(self) -> None:
        """清空并重新绘制所有日期格子"""
        for w in self._grid_frame.winfo_children():
            w.destroy()

        today = date.today()

        # 加载设置
        settings = self._load_settings()

        try:
            cycle_start = date.fromisoformat(settings.cycle_start_date) if settings.cycle_start_date else today
        except ValueError:
            cycle_start = today

        cycle_pattern = self.app.repo.get_cycle_pattern()

        # 计算日历范围（含前后填充）
        first_day = date(self.year, self.month, 1)
        if self.month == 12:
            last_day = date(self.year + 1, 1, 1) - timedelta(days=1)
        else:
            last_day = date(self.year, self.month + 1, 1) - timedelta(days=1)

        cal_start = first_day - timedelta(days=first_day.weekday())      # 周一
        cal_end = last_day + timedelta(days=6 - last_day.weekday())       # 周日

        # 生成排班数据
        schedules = self.app.engine.generate_schedules(
            cal_start, cal_end,
            settings.work_mode,
            cycle_start,
            cycle_pattern,
            settings.cycle_reference_index,
        )
        schedule_map: dict[date, Any] = {sd.date: sd for sd in schedules}

        default_bg = self._default_bg()
        current = cal_start
        row = 0
        while current <= cal_end and row < 6:
            for col in range(7):
                if current > cal_end:
                    break

                sd = schedule_map.get(current)
                if sd:
                    shift_type = sd.shift_type
                    is_holiday = sd.is_holiday
                else:
                    shift_type = ShiftType.REST
                    is_holiday = False

                color = SHIFT_COLORS.get(shift_type, "#999999")
                cell_bg = lighten_color(color, 0.65)       # 浅色背景

                # 非本月日期再减淡一层
                if current.month != self.month:
                    cell_bg = lighten_color(cell_bg, 0.45)

                # 文字颜色
                text_alpha = 1.0 if current.month == self.month else 0.4
                text_fg = self._text_color_for_bg(cell_bg, text_alpha)

                # 创建单元格
                cell = tk.Frame(
                    self._grid_frame,
                    bg=cell_bg,
                    relief="flat",
                    bd=0,
                    highlightthickness=0,
                    highlightbackground=default_bg,
                )

                # 今天蓝色边框
                if current == today:
                    cell.configure(highlightthickness=2, highlightbackground="#2196F3", highlightcolor="#2196F3")
                # 节假日金色边框（不与今天边框冲突时叠加）
                elif is_holiday:
                    cell.configure(highlightthickness=2, highlightbackground="#FFD700", highlightcolor="#FFD700")

                cell.grid(row=row, column=col, sticky="nsew", padx=1, pady=1)
                cell.grid_propagate(False)

                # 日期数字
                date_lbl = tk.Label(
                    cell, text=str(current.day),
                    bg=cell_bg, fg=text_fg,
                    font=("TkDefaultFont", 10, "bold"),
                    anchor="nw",
                )
                date_lbl.pack(anchor="nw", padx=3, pady=(2, 0))

                # 班次名称
                shift_name = SHIFT_NAMES.get(shift_type, "")
                shift_lbl = tk.Label(
                    cell, text=shift_name,
                    bg=cell_bg, fg=text_fg,
                    font=("TkDefaultFont", 8),
                    anchor="center",
                )
                shift_lbl.pack(anchor="center", expand=True)

                # 绑定点击事件
                bind_targets = [cell, date_lbl, shift_lbl]
                for target in bind_targets:
                    target.bind("<Button-1>", lambda e, d=current: self._on_day_click(d))
                    # 悬停效果
                    target.bind("<Enter>", lambda e, f=cell: f.configure(relief="raised"))
                    target.bind("<Leave>", lambda e, f=cell: f.configure(relief="flat"))

                current += timedelta(days=1)
            row += 1

    # ─── 设置加载 ──────────────────────────────────────

    def _load_settings(self):
        """加载应用设置（安全调用，兼容设置尚未初始化的情况）"""
        from config.settings import AppSettings
        try:
            return self.app.repo.load_settings()
        except Exception:
            return AppSettings()

    # ─── 点击日期 → 覆盖排班 ────────────────────────────

    def _on_day_click(self, clicked_date: date) -> None:
        """弹出对话框允许用户覆盖指定日期的排班"""
        dialog = ShiftOverrideDialog(
            self,
            date=clicked_date,
            app=self.app,
        )
        self.wait_window(dialog)
        # 对话框关闭后刷新日历
        self.refresh(self.year, self.month)

    # ─── 公共方法 ──────────────────────────────────────

    def refresh(self, year: int, month: int) -> None:
        """重新加载指定年月的排班数据并刷新显示"""
        self.year = year
        self.month = month
        self._update_title()
        self._render_cells()

    # ─── 辅助 ──────────────────────────────────────────

    def _default_bg(self) -> str:
        """获取默认背景色（跟随系统主题）"""
        return _get_default_bg()

    def _text_color_for_bg(self, bg_hex: str, alpha: float = 1.0) -> str:
        """根据背景色亮度返回合适的文字颜色（黑/白/淡灰）"""
        bg_hex = bg_hex.lstrip("#")
        r = int(bg_hex[0:2], 16)
        g = int(bg_hex[2:4], 16)
        b = int(bg_hex[4:6], 16)
        luminance = 0.299 * r + 0.587 * g + 0.114 * b
        if alpha < 1.0:
            # 混入默认背景色以模拟透明度
            def_bg = _get_default_bg().lstrip("#")
            dr = int(def_bg[0:2], 16)
            dg = int(def_bg[2:4], 16)
            db = int(def_bg[4:6], 16)
            r2 = int(r * alpha + dr * (1 - alpha))
            g2 = int(g * alpha + dg * (1 - alpha))
            b2 = int(b * alpha + db * (1 - alpha))
            return f"#{r2:02x}{g2:02x}{b2:02x}"
        return "#000000" if luminance > 150 else "#ffffff"


class ShiftOverrideDialog(tk.Toplevel):
    """手动覆盖排班的对话框"""

    def __init__(self, parent: tk.Widget, date: date, app: Any) -> None:
        super().__init__(parent)
        self.date = date
        self.app = app
        self.result: ShiftType | None = None

        self.title(f"覆盖排班 — {date.isoformat()}")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self._build_ui()
        self._center_on_parent(parent)

    def _build_ui(self) -> None:
        main = ttk.Frame(self, padding=16)
        main.pack(fill="both", expand=True)

        ttk.Label(main, text=f"为 {self.date.isoformat()} 选择班次：",
                  font=("TkDefaultFont", 10, "bold")).pack(anchor="w", pady=(0, 12))

        self._radio_var = tk.IntVar(value=-1)
        radio_frame = ttk.Frame(main)
        radio_frame.pack(fill="x", pady=(0, 16))

        for st in ShiftType:
            color = SHIFT_COLORS.get(st, "#999")
            name = SHIFT_NAMES.get(st, "")

            row_frame = tk.Frame(radio_frame, bg=self._default_bg())
            row_frame.pack(fill="x", pady=1)

            swatch = tk.Frame(row_frame, width=16, height=16, bg=color, relief="solid", bd=1)
            swatch.pack(side="left", padx=(0, 8))

            ttk.Radiobutton(
                row_frame,
                text=name,
                variable=self._radio_var,
                value=st.value,
            ).pack(side="left")

        btn_frame = ttk.Frame(main)
        btn_frame.pack(fill="x")
        ttk.Button(btn_frame, text="取消", command=self.destroy).pack(side="right", padx=(4, 0))
        ttk.Button(btn_frame, text="确认覆盖", bootstyle="primary", command=self._confirm).pack(side="right")

    def _confirm(self) -> None:
        val = self._radio_var.get()
        if val < 0:
            messagebox.showwarning("未选择", "请先选择一个班次类型。", parent=self)
            return

        try:
            st = ShiftType(val)
        except ValueError:
            messagebox.showerror("错误", f"无效的班次类型: {val}", parent=self)
            return

        sd = ScheduleDay(date=self.date, shift_type=st, is_override=True)
        try:
            self.app.repo.save_schedule(sd)
            self.app.after_save()
        except Exception as e:
            messagebox.showerror("保存失败", str(e), parent=self)
            return

        self.result = st
        self.destroy()

    def _center_on_parent(self, parent: tk.Widget) -> None:
        self.update_idletasks()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()
        w = self.winfo_width()
        h = self.winfo_height()
        x = px + (pw - w) // 2
        y = py + (ph - h) // 2
        self.geometry(f"+{x}+{y}")

    def _default_bg(self) -> str:
        return _get_default_bg()


# 延迟导入避免循环依赖（模块底部）
from db.models import ScheduleDay
