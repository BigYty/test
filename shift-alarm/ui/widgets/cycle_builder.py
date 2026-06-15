"""循环顺序构建器 — 可复用的排班循环编辑组件"""

import tkinter as tk
from tkinter import ttk

from config.constants import ShiftType, SHIFT_NAMES, SHIFT_COLORS


def _text_fg(hex_color: str) -> str:
    hex_color = hex_color.lstrip("#")
    r = int(hex_color[0:2], 16); g = int(hex_color[2:4], 16); b = int(hex_color[4:6], 16)
    return "#ffffff" if (0.299 * r + 0.587 * g + 0.114 * b) < 150 else "#000000"


class CycleBuilder(ttk.Frame):
    """循环顺序构建器组件。

    上部：6 个彩色班次按钮，点击添加到循环末尾
    中部：循环序列显示区
    下部：清空按钮
    """

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self._pattern: list[int] = []
        self._build_ui()

    def get_pattern(self) -> list[int]:
        return list(self._pattern)

    def set_pattern(self, patterns: list):
        self._pattern = []
        for item in patterns:
            self._pattern.append(int(item.shift_type) if hasattr(item, "shift_type") else int(item))
        self._refresh_sequence()

    def _build_ui(self):
        d = self.app.design

        # ── 按钮区 ──
        btn_section = ttk.Frame(self)
        btn_section.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(btn_section, text="点击添加班次到循环末尾：",
                  font=("Microsoft YaHei UI", 10)).pack(anchor="w", pady=(0, 6))

        btns_row = tk.Frame(btn_section, bg=d["card_bg"])
        btns_row.pack(fill=tk.X)

        for st in ShiftType:
            color = SHIFT_COLORS.get(st, "#ccc")
            name = SHIFT_NAMES.get(st, "未知")
            fg = _text_fg(color)

            # 直接用 Label 模拟按钮 —— 比 Frame+Label 更可靠地显示背景色
            btn = tk.Label(
                btns_row, text=name, bg=color, fg=fg,
                font=("Microsoft YaHei UI", 9, "bold"),
                width=7, cursor="hand2",
                relief=tk.RAISED, borderwidth=2,
            )
            btn.pack(side=tk.LEFT, padx=2, pady=2)

            btn.bind("<Button-1>", lambda e, s=st: self._add_shift(s))
            btn.bind("<Enter>", lambda e, b=btn: b.configure(relief=tk.SUNKEN))
            btn.bind("<Leave>", lambda e, b=btn: b.configure(relief=tk.RAISED))

        # ── 序列显示区 ──
        ttk.Label(self, text="当前循环顺序：",
                  font=("Microsoft YaHei UI", 10)).pack(anchor="w", pady=(8, 4))

        seq_container = tk.Frame(self, bg=d["card_bg"], highlightthickness=1, highlightbackground=d["border"])
        seq_container.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

        self._seq_canvas = tk.Canvas(seq_container, height=70, bg=d["card_bg"], highlightthickness=0)
        self._seq_scroll = ttk.Scrollbar(seq_container, orient="vertical", command=self._seq_canvas.yview)
        self._seq_inner = tk.Frame(self._seq_canvas, bg=d["card_bg"])

        self._seq_inner.bind("<Configure>",
                             lambda e: self._seq_canvas.configure(scrollregion=self._seq_canvas.bbox("all")))
        self._seq_canvas.create_window((0, 0), window=self._seq_inner, anchor="nw")
        self._seq_canvas.configure(yscrollcommand=self._seq_scroll.set)

        self._seq_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._seq_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self._seq_scroll.pack_forget()

        self._empty_lbl = tk.Label(self._seq_inner, text="（空）点击上方按钮添加班次",
                                   fg=d["text_muted"], bg=d["card_bg"],
                                   font=("Microsoft YaHei UI", 10))
        self._empty_lbl.pack(padx=12, pady=16)

        # ── 底部：清空 + 计数 ──
        bottom = ttk.Frame(self)
        bottom.pack(fill=tk.X)
        ttk.Button(bottom, text="清空循环", command=self._clear_pattern).pack(side=tk.LEFT)
        self._count_lbl = ttk.Label(bottom, text="共 0 个班次", foreground="gray")
        self._count_lbl.pack(side=tk.RIGHT)

    def _add_shift(self, shift_type: ShiftType):
        self._pattern.append(int(shift_type))
        self._refresh_sequence()

    def _remove_shift(self, index: int):
        if 0 <= index < len(self._pattern):
            del self._pattern[index]
            self._refresh_sequence()

    def _clear_pattern(self):
        self._pattern.clear()
        self._refresh_sequence()

    def _refresh_sequence(self):
        d = self.app.design

        for w in self._seq_inner.winfo_children():
            w.destroy()

        if not self._pattern:
            self._empty_lbl = tk.Label(self._seq_inner, text="（空）点击上方按钮添加班次",
                                       fg=d["text_muted"], bg=d["card_bg"],
                                       font=("Microsoft YaHei UI", 10))
            self._empty_lbl.pack(padx=12, pady=16)
            self._seq_scroll.pack_forget()
        else:
            self._seq_scroll.pack(side=tk.RIGHT, fill=tk.Y)
            row = tk.Frame(self._seq_inner, bg=d["card_bg"])
            row.pack(fill=tk.X, padx=6, pady=6)

            for idx, sv in enumerate(self._pattern):
                st = ShiftType(sv)
                color = SHIFT_COLORS.get(st, "#ccc")
                name = SHIFT_NAMES.get(st, "未知")

                tag = tk.Frame(row, bg=color, cursor="hand2", relief="flat", bd=0)
                tag.pack(side=tk.LEFT, padx=3, pady=2)

                inner = tk.Frame(tag, bg=color)
                inner.pack(padx=8, pady=4)

                tk.Label(inner, text=f"#{idx+1}", bg=color, fg=_text_fg(color),
                         font=("Segoe UI", 7)).pack(side=tk.LEFT, padx=(0, 4))
                tk.Label(inner, text=name, bg=color, fg=_text_fg(color),
                         font=("Microsoft YaHei UI", 9, "bold")).pack(side=tk.LEFT)
                tk.Label(inner, text=" x", bg=color, fg=_text_fg(color),
                         font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT, padx=(4, 0))

                for wd in (tag, inner) + tuple(inner.winfo_children()):
                    wd.bind("<Button-1>", lambda e, i=idx: self._remove_shift(i))
                    wd.bind("<Enter>", lambda e, f=tag: f.configure(relief="raised", bd=1))
                    wd.bind("<Leave>", lambda e, f=tag: f.configure(relief="flat", bd=0))

            self._seq_inner.update_idletasks()
            self._seq_canvas.configure(scrollregion=self._seq_canvas.bbox("all"))

        self._count_lbl.configure(text=f"共 {len(self._pattern)} 个班次")
