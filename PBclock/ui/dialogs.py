"""弹窗工具"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from datetime import date

from config.constants import ShiftType, SHIFT_NAMES
from db.models import ScheduleDay


def show_info(parent: tk.Widget, title: str, message: str):
    """显示信息弹窗"""
    messagebox.showinfo(title, message, parent=parent)


def show_warning(parent: tk.Widget, title: str, message: str):
    """显示警告弹窗"""
    messagebox.showwarning(title, message, parent=parent)


def show_error(parent: tk.Widget, title: str, message: str):
    """显示错误弹窗"""
    messagebox.showerror(title, message, parent=parent)


def show_confirm(parent: tk.Widget, title: str, message: str) -> bool:
    """确认弹窗，返回 True/False"""
    return messagebox.askyesno(title, message, parent=parent)


def show_shift_override_dialog(parent: tk.Widget, app, date_str: str, current_shift: ShiftType | int) -> bool:
    """排班覆盖弹窗：选择新班次 → 调用 app.repo.save_schedule() → 返回是否成功

    Args:
        parent: 父窗口
        app: MainApp 实例 (提供 app.repo, app.after_save, app.refresh_current_view)
        date_str: 日期字符串 YYYY-MM-DD
        current_shift: 当前班次 (ShiftType 或 int)

    Returns:
        是否保存成功
    """
    # 规范化 current_shift 为 ShiftType
    if isinstance(current_shift, int):
        try:
            current_shift = ShiftType(current_shift)
        except ValueError:
            current_shift = ShiftType.REST

    # 创建对话框
    dialog = tk.Toplevel(parent)
    dialog.title("排班覆盖")
    dialog.geometry("320x380")
    dialog.resizable(False, False)
    dialog.transient(parent)
    dialog.grab_set()

    # 居中
    dialog.update_idletasks()
    pw = parent.winfo_width()
    ph = parent.winfo_height()
    px = parent.winfo_rootx()
    py = parent.winfo_rooty()
    dw = dialog.winfo_width()
    dh = dialog.winfo_height()
    x = px + (pw - dw) // 2
    y = py + (ph - dh) // 2
    dialog.geometry(f"+{x}+{y}")

    result = {"confirmed": False, "shift_type": None}

    # 标题
    header = ttk.Label(
        dialog,
        text=f"覆盖排班 — {date_str}",
        font=("", 12, "bold"),
    )
    header.pack(pady=(12, 4))

    current_name = SHIFT_NAMES.get(current_shift, "未知")
    info_label = ttk.Label(
        dialog,
        text=f"当前班次: {current_name}",
    )
    info_label.pack(pady=(0, 8))

    # 分隔线
    ttk.Separator(dialog, orient="horizontal").pack(fill="x", padx=16, pady=4)

    select_label = ttk.Label(dialog, text="选择新班次:")
    select_label.pack(pady=(8, 4))

    # 班次选择列表
    list_frame = ttk.Frame(dialog)
    list_frame.pack(fill="both", expand=True, padx=16, pady=(0, 8))

    shift_var = tk.IntVar(value=current_shift.value)

    for st in ShiftType:
        st_name = SHIFT_NAMES.get(st, st.name)
        rb = ttk.Radiobutton(
            list_frame,
            text=st_name,
            variable=shift_var,
            value=st.value,
        )
        rb.pack(anchor="w", pady=1)

    # 按钮
    btn_frame = ttk.Frame(dialog)
    btn_frame.pack(fill="x", padx=16, pady=(0, 12))

    def on_confirm():
        result["confirmed"] = True
        result["shift_type"] = shift_var.get()
        dialog.destroy()

    def on_cancel():
        dialog.destroy()

    cancel_btn = ttk.Button(btn_frame, text="取消", command=on_cancel)
    cancel_btn.pack(side="right", padx=(4, 0))

    confirm_btn = ttk.Button(btn_frame, text="确认覆盖", command=on_confirm)
    confirm_btn.pack(side="right")

    dialog.wait_window()

    if not result["confirmed"]:
        return False

    new_shift_type = ShiftType(result["shift_type"])

    # 如果没变化，就不保存
    if new_shift_type == current_shift:
        return False

    # 保存排班覆盖
    try:
        schedule = ScheduleDay(
            date=date.fromisoformat(date_str),
            shift_type=new_shift_type,
            is_holiday=False,
            is_override=True,
            note="手动覆盖",
        )
        app.repo.save_schedule(schedule)
        app.after_save()
        app.refresh_current_view()
        show_info(parent, "成功", f"已覆盖 {date_str} 为 {SHIFT_NAMES[new_shift_type]}")
        return True
    except Exception as e:
        show_error(parent, "保存失败", str(e))
        return False
