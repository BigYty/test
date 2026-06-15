"""循环顺序构建器 —— 可复用的排班循环编辑组件"""

import tkinter as tk
from tkinter import ttk

from config.constants import ShiftType, SHIFT_NAMES, SHIFT_COLORS


# ── 辅助：将 HEX 颜色转淡色用于背景 ──────────────────────
def _lighten(hex_color: str, factor: float = 0.35) -> str:
    """将 HEX 颜色转为浅色版本（用于标签背景）"""
    hex_color = hex_color.lstrip("#")
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    r = int(r + (255 - r) * factor)
    g = int(g + (255 - g) * factor)
    b = int(b + (255 - b) * factor)
    return f"#{r:02x}{g:02x}{b:02x}"


# 预计算的淡色背景缓存
_LIGHT_COLORS: dict[str, str] = {}


def _get_light_color(hex_color: str) -> str:
    if hex_color not in _LIGHT_COLORS:
        _LIGHT_COLORS[hex_color] = _lighten(hex_color)
    return _LIGHT_COLORS[hex_color]


class CycleBuilder(ttk.Frame):
    """循环顺序构建器组件。

    上部：6 个彩色班次按钮，点击添加到循环末尾
    中部：循环序列显示区，显示已选班次的有序列表，点击可移除
    下部：清空按钮

    使用方式：
        builder = CycleBuilder(parent, app)
        builder.pack(fill=tk.BOTH, expand=True)
        pattern = builder.get_pattern()   # → list[int]
        builder.set_pattern([1, 2, 3])    # 加载已有循环
    """

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self._pattern: list[int] = []  # shift_type 有序列表

        self._build_ui()

    # ── 公共 API ────────────────────────────────────────

    def get_pattern(self) -> list[int]:
        """返回当前循环顺序（shift_type 列表）"""
        return list(self._pattern)

    def set_pattern(self, patterns: list):
        """从已有数据加载循环顺序。接受 shift_type 的 int 列表或 CyclePattern 对象列表。"""
        self._pattern = []
        for item in patterns:
            if hasattr(item, "shift_type"):
                self._pattern.append(int(item.shift_type))
            else:
                self._pattern.append(int(item))
        self._refresh_sequence()

    # ── UI 构建 ─────────────────────────────────────────

    def _build_ui(self):
        # ── 上部：6 个班次按钮 ──
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(btn_frame, text="点击添加班次到循环末尾：").pack(
            anchor=tk.W, pady=(0, 4)
        )

        btns_row = ttk.Frame(btn_frame)
        btns_row.pack(fill=tk.X)

        for st in ShiftType:
            color = SHIFT_COLORS.get(st, "#CCCCCC")
            name = SHIFT_NAMES.get(st, "未知")
            b = tk.Button(
                btns_row,
                text=name,
                bg=color,
                fg="white" if st != ShiftType.REST else "black",
                activebackground=color,
                relief=tk.RAISED,
                width=8,
                command=lambda s=st: self._add_shift(s),
            )
            b.pack(side=tk.LEFT, padx=2, pady=2)

        # ── 中部：循环序列显示区 ──
        ttk.Label(self, text="当前循环顺序：").pack(anchor=tk.W, pady=(8, 4))

        # 用 Canvas + 内嵌 Frame 实现可滚动（当序列很长时）
        seq_container = ttk.Frame(self, relief=tk.SUNKEN, borderwidth=1)
        seq_container.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

        self._seq_canvas = tk.Canvas(seq_container, height=80, highlightthickness=0)
        self._seq_scrollbar = ttk.Scrollbar(
            seq_container, orient=tk.VERTICAL, command=self._seq_canvas.yview
        )
        self._seq_inner = ttk.Frame(self._seq_canvas)

        self._seq_inner.bind(
            "<Configure>",
            lambda e: self._seq_canvas.configure(
                scrollregion=self._seq_canvas.bbox("all")
            ),
        )
        self._seq_canvas.create_window((0, 0), window=self._seq_inner, anchor=tk.NW)
        self._seq_canvas.configure(yscrollcommand=self._seq_scrollbar.set)

        self._seq_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        # 滚动条按需显示
        self._seq_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self._seq_scrollbar.pack_forget()  # 初始隐藏

        # 空状态提示
        self._empty_label = ttk.Label(
            self._seq_inner,
            text="（空）点击上方按钮添加班次",
            foreground="gray",
        )
        self._empty_label.pack(padx=8, pady=12)

        # ── 下部：清空按钮 ──
        bottom_frame = ttk.Frame(self)
        bottom_frame.pack(fill=tk.X)

        self._clear_btn = ttk.Button(
            bottom_frame, text="清空循环", command=self._clear_pattern
        )
        self._clear_btn.pack(side=tk.LEFT)

        self._count_label = ttk.Label(
            bottom_frame, text="共 0 个班次", foreground="gray"
        )
        self._count_label.pack(side=tk.RIGHT)

    # ── 内部操作 ────────────────────────────────────────

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
        """刷新序列显示区"""
        # 清除现有内容
        for w in self._seq_inner.winfo_children():
            w.destroy()
        self._empty_label = None

        if not self._pattern:
            # 空状态
            self._empty_label = ttk.Label(
                self._seq_inner,
                text="（空）点击上方按钮添加班次",
                foreground="gray",
            )
            self._empty_label.pack(padx=8, pady=12)
            self._seq_scrollbar.pack_forget()
        else:
            # 显示序列
            self._seq_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            row_frame = ttk.Frame(self._seq_inner)
            row_frame.pack(fill=tk.X, padx=4, pady=4)

            for idx, shift_val in enumerate(self._pattern):
                st = ShiftType(shift_val)
                color = SHIFT_COLORS.get(st, "#CCCCCC")
                name = SHIFT_NAMES.get(st, "未知")
                bg = _get_light_color(color)

                # 每个标签：彩色背景 + 序号 + 名称，点击移除
                tag_frame = tk.Frame(
                    row_frame,
                    bg=bg,
                    relief=tk.RAISED,
                    borderwidth=1,
                    cursor="hand2",
                )
                tag_frame.pack(side=tk.LEFT, padx=3, pady=3)

                # 序号小标签
                idx_lbl = tk.Label(
                    tag_frame,
                    text=f"#{idx + 1}",
                    bg=bg,
                    fg="#666666",
                    font=("", 8),
                )
                idx_lbl.pack(side=tk.LEFT, padx=(4, 1))

                name_lbl = tk.Label(
                    tag_frame,
                    text=name,
                    bg=bg,
                    fg="#333333",
                    font=("", 9, "bold"),
                )
                name_lbl.pack(side=tk.LEFT, padx=(1, 2))

                # 删除小叉号
                del_lbl = tk.Label(
                    tag_frame,
                    text=" x",
                    bg=bg,
                    fg="#999999",
                    font=("", 9),
                    cursor="hand2",
                )
                del_lbl.pack(side=tk.LEFT, padx=(0, 4))

                # 绑定点击事件（整个标签区域）
                for w in (tag_frame, idx_lbl, name_lbl, del_lbl):
                    w.bind("<Button-1>", lambda e, i=idx: self._remove_shift(i))
                    w.bind(
                        "<Enter>",
                        lambda e, f=tag_frame: f.configure(relief=tk.SUNKEN),
                    )
                    w.bind(
                        "<Leave>",
                        lambda e, f=tag_frame: f.configure(relief=tk.RAISED),
                    )

            # 更新 Canvas 滚动区域
            self._seq_inner.update_idletasks()
            self._seq_canvas.configure(scrollregion=self._seq_canvas.bbox("all"))

        # 更新计数
        self._count_label.configure(text=f"共 {len(self._pattern)} 个班次")
