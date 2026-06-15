"""月历网格组件 — 月度排班日历，支持手动覆盖排班"""

from __future__ import annotations

import tkinter as tk
from datetime import date, timedelta
from tkinter import messagebox, ttk
from typing import Any

from config.constants import SHIFT_COLORS, SHIFT_NAMES, ShiftType

_WEEKDAY_LABELS = ["一", "二", "三", "四", "五", "六", "日"]


def lighten_color(hex_color: str, factor: float = 0.7) -> str:
    hex_color = hex_color.lstrip("#")
    r = int(hex_color[0:2], 16); g = int(hex_color[2:4], 16); b = int(hex_color[4:6], 16)
    r = int(r + (255 - r) * factor); g = int(g + (255 - g) * factor); b = int(b + (255 - b) * factor)
    return f"#{r:02x}{g:02x}{b:02x}"


class CalendarGrid(ttk.Frame):
    """月历网格，显示指定月份的排班情况。"""

    def __init__(self, parent: tk.Widget, app: Any,
                 year: int | None = None, month: int | None = None) -> None:
        today = date.today()
        self.year = year if year is not None else today.year
        self.month = month if month is not None else today.month
        self.app = app

        super().__init__(parent)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=0)
        self.rowconfigure(1, weight=0)
        self.rowconfigure(2, weight=1)
        self.rowconfigure(3, weight=0)

        self._build_nav()
        self._build_weekday_headers()
        self._build_grid_frame()
        self._build_legend()
        self._render_cells()

    # ── 导航栏 ──

    def _build_nav(self) -> None:
        d = self.app.design
        nav = tk.Frame(self, bg=d["card_bg"])
        nav.grid(row=0, column=0, sticky="ew", pady=(0, 6))

        self._btn_prev = ttk.Button(nav, text="◀  上个月", command=self._go_prev)
        self._btn_prev.pack(side=tk.LEFT)

        self._lbl_title = tk.Label(nav, font=("Microsoft YaHei UI", 13, "bold"),
                                   fg=d["text_primary"], bg=d["card_bg"])
        self._lbl_title.pack(side=tk.LEFT, expand=True)

        self._btn_next = ttk.Button(nav, text="下个月  ▶", command=self._go_next)
        self._btn_next.pack(side=tk.RIGHT, padx=(0, 4))

        self._btn_today = ttk.Button(nav, text="今天", command=self._go_today)
        self._btn_today.pack(side=tk.RIGHT, padx=(0, 8))

        self._update_title()

    def _update_title(self):
        self._lbl_title.configure(text=f"{self.year}年 {self.month}月")

    def _go_prev(self):
        if self.month == 1:
            self.refresh(self.year - 1, 12)
        else:
            self.refresh(self.year, self.month - 1)

    def _go_next(self):
        if self.month == 12:
            self.refresh(self.year + 1, 1)
        else:
            self.refresh(self.year, self.month + 1)

    def _go_today(self):
        t = date.today()
        self.refresh(t.year, t.month)

    # ── 周标签 ──

    def _build_weekday_headers(self) -> None:
        d = self.app.design
        hf = tk.Frame(self, bg=d["card_bg"])
        hf.grid(row=1, column=0, sticky="ew", pady=(0, 2))
        for i in range(7):
            hf.columnconfigure(i, weight=1)
        for i, label in enumerate(_WEEKDAY_LABELS):
            fg = d["text_muted"] if i >= 5 else d["text_secondary"]
            tk.Label(hf, text=label, font=("Microsoft YaHei UI", 9), fg=fg, bg=d["card_bg"],
                     anchor="center").grid(row=0, column=i, sticky="ew")

    # ── 日期网格 ──

    def _build_grid_frame(self) -> None:
        d = self.app.design
        self._grid_frame = tk.Frame(self, bg=d["card_bg"])
        self._grid_frame.grid(row=2, column=0, sticky="nsew")
        for i in range(7):
            self._grid_frame.columnconfigure(i, weight=1, uniform="cc")
        for i in range(6):
            self._grid_frame.rowconfigure(i, weight=1, uniform="cr")

    # ── 图例 ──

    def _build_legend(self) -> None:
        d = self.app.design
        legend = tk.Frame(self, bg=d["card_bg"])
        legend.grid(row=3, column=0, sticky="ew", pady=(6, 0))

        for col_idx, st in enumerate(ShiftType):
            legend.columnconfigure(col_idx, weight=1)
            color = SHIFT_COLORS.get(st, "#999")
            name = SHIFT_NAMES.get(st, "?")

            item = tk.Frame(legend, bg=d["card_bg"])
            item.grid(row=0, column=col_idx, padx=2)

            swatch = tk.Canvas(item, width=12, height=12, bg=d["card_bg"], highlightthickness=0)
            swatch.pack(side=tk.LEFT, padx=(0, 3))
            swatch.create_oval(1, 1, 11, 11, fill=color, outline="")

            tk.Label(item, text=name, font=("Microsoft YaHei UI", 8),
                     fg=d["text_secondary"], bg=d["card_bg"]).pack(side=tk.LEFT)

        # 节假日标记
        hf = tk.Frame(legend, bg=d["card_bg"])
        hf.grid(row=1, column=0, columnspan=6, sticky="w", pady=(2, 0))
        hc = tk.Canvas(hf, width=12, height=12, bg=d["card_bg"], highlightthickness=0)
        hc.pack(side=tk.LEFT, padx=(0, 3))
        hc.create_oval(1, 1, 11, 11, fill="#fbbf24", outline="")
        tk.Label(hf, text="节假日（金色边框）", font=("Microsoft YaHei UI", 8),
                 fg=d["text_muted"], bg=d["card_bg"]).pack(side=tk.LEFT)

    # ── 渲染日历格子 ──

    def _render_cells(self) -> None:
        d = self.app.design
        for w in self._grid_frame.winfo_children():
            w.destroy()

        today = date.today()
        settings = self._load_settings()
        try:
            cs = date.fromisoformat(settings.cycle_start_date) if settings.cycle_start_date else today
        except ValueError:
            cs = today
        cp = self.app.repo.get_cycle_pattern()

        first_day = date(self.year, self.month, 1)
        if self.month == 12:
            last_day = date(self.year + 1, 1, 1) - timedelta(days=1)
        else:
            last_day = date(self.year, self.month + 1, 1) - timedelta(days=1)

        cal_start = first_day - timedelta(days=first_day.weekday())
        cal_end = last_day + timedelta(days=6 - last_day.weekday())

        schedules = self.app.engine.generate_schedules(
            cal_start, cal_end, settings.work_mode, cs, cp, settings.cycle_reference_index)
        schedule_map: dict[date, Any] = {sd.date: sd for sd in schedules}

        current = cal_start
        for row in range(6):
            for col in range(7):
                if current > cal_end:
                    break

                sd = schedule_map.get(current)
                shift_type = sd.shift_type if sd else ShiftType.REST
                is_holiday = sd.is_holiday if sd else False
                color = SHIFT_COLORS.get(shift_type, "#999999")

                is_current_month = current.month == self.month

                # 直接用颜色作为单元格背景（确保颜色可靠显示）
                if is_current_month:
                    cell_bg = lighten_color(color, 0.3)
                else:
                    cell_bg = "#f8fafc"

                cell = tk.Frame(self._grid_frame, bg=cell_bg, relief="flat", bd=0,
                                highlightthickness=0, highlightbackground=cell_bg)

                # 今天：蓝色边框
                if current == today:
                    cell.configure(highlightthickness=2, highlightbackground=d["accent"])
                # 节假日：金色边框
                elif is_holiday and is_current_month:
                    cell.configure(highlightthickness=2, highlightbackground="#fbbf24")

                cell.grid(row=row, column=col, sticky="nsew", padx=1, pady=1)
                cell.grid_propagate(False)

                # 文字颜色
                txt_fg = _text_fg(cell_bg)
                day_fg = txt_fg if is_current_month else d["text_muted"]

                # 日期数字（左上角）
                day_lbl = tk.Label(cell, text=str(current.day),
                                   bg=cell_bg, fg=day_fg,
                                   font=("Segoe UI", 10, "bold"), anchor="nw")
                day_lbl.place(x=4, y=2)

                # 班次名称（居中）
                if is_current_month:
                    name_lbl = tk.Label(cell, text=SHIFT_NAMES.get(shift_type, ""),
                                        bg=cell_bg, fg=txt_fg,
                                        font=("Microsoft YaHei UI", 8, "bold"))
                    name_lbl.place(relx=0.5, rely=0.65, anchor="center")

                # 点击事件
                def _bind_click(widgets):
                    for w in widgets:
                        try:
                            w.bind("<Button-1>", lambda e, d_=current: self._on_day_click(d_))
                            w.bind("<Enter>", lambda e, f=cell: f.configure(relief="raised"))
                            w.bind("<Leave>", lambda e, f=cell: f.configure(relief="flat"))
                        except Exception:
                            pass

                _bind_click([cell, day_lbl] + list(cell.winfo_children()))

                current += timedelta(days=1)

    def _load_settings(self):
        from config.settings import AppSettings
        try:
            return self.app.repo.load_settings()
        except Exception:
            return AppSettings()

    def _on_day_click(self, clicked_date: date) -> None:
        ShiftOverrideDialog(self, date=clicked_date, app=self.app)
        self.wait_window()
        self.refresh(self.year, self.month)

    def refresh(self, year: int, month: int) -> None:
        self.year = year
        self.month = month
        self._update_title()
        self._render_cells()


def _text_fg(hex_color: str) -> str:
    hex_color = hex_color.lstrip("#")
    r = int(hex_color[0:2], 16); g = int(hex_color[2:4], 16); b = int(hex_color[4:6], 16)
    return "#ffffff" if (0.299 * r + 0.587 * g + 0.114 * b) < 150 else "#000000"


class ShiftOverrideDialog(tk.Toplevel):
    """手动覆盖排班的对话框"""

    def __init__(self, parent: tk.Widget, date_obj: date, app: Any) -> None:
        super().__init__(parent)
        self.date = date_obj
        self.app = app
        self.result: ShiftType | None = None

        self.title(f"覆盖排班 — {date_obj.isoformat()}")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self._build_ui()
        self._center_on_parent(parent)

    def _build_ui(self) -> None:
        d = self.app.design
        main = tk.Frame(self, bg=d["card_bg"])
        main.pack(fill="both", expand=True, padx=20, pady=16)

        tk.Label(main, text=f"为 {self.date.isoformat()} 选择班次：",
                 font=("Microsoft YaHei UI", 11, "bold"),
                 fg=d["text_primary"], bg=d["card_bg"]).pack(anchor="w", pady=(0, 12))

        self._radio_var = tk.IntVar(value=-1)
        rf = tk.Frame(main, bg=d["card_bg"])
        rf.pack(fill="x", pady=(0, 16))

        for st in ShiftType:
            color = SHIFT_COLORS.get(st, "#999")
            name = SHIFT_NAMES.get(st, "")

            row = tk.Frame(rf, bg=d["card_bg"])
            row.pack(fill="x", pady=1)

            dot = tk.Canvas(row, width=14, height=14, bg=d["card_bg"], highlightthickness=0)
            dot.pack(side="left", padx=(0, 8))
            dot.create_oval(1, 1, 13, 13, fill=color, outline="")

            ttk.Radiobutton(row, text=name, variable=self._radio_var, value=st.value).pack(side="left")

        bf = tk.Frame(main, bg=d["card_bg"])
        bf.pack(fill="x")
        ttk.Button(bf, text="取消", command=self.destroy).pack(side="right", padx=(6, 0))
        ttk.Button(bf, text="确认覆盖", command=self._confirm).pack(side="right")

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

        from db.models import ScheduleDay
        try:
            self.app.repo.save_schedule(ScheduleDay(date=self.date, shift_type=st, is_override=True))
            self.app.after_save()
        except Exception as e:
            messagebox.showerror("保存失败", str(e), parent=self)
            return

        self.result = st
        self.destroy()

    def _center_on_parent(self, parent: tk.Widget) -> None:
        self.update_idletasks()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        px, py = parent.winfo_rootx(), parent.winfo_rooty()
        w, h = self.winfo_width(), self.winfo_height()
        self.geometry(f"+{px + (pw - w) // 2}+{py + (ph - h) // 2}")
