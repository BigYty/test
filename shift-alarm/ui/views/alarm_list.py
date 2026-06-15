"""闹钟列表视图"""

from __future__ import annotations

from datetime import datetime
import tkinter as tk
from tkinter import ttk

from config.constants import ShiftType, SHIFT_NAMES, SHIFT_COLORS


# 闹钟状态文本映射
STATUS_TEXT: dict[int, str] = {
    0: "待触发",
    1: "已触发",
    2: "已关闭",
    3: "已延迟",
}


def build(parent: ttk.Frame, app):
    """构建闹钟列表视图

    Args:
        parent: 父 Frame (ttk.Frame)
        app: MainApp 实例，提供 app.scheduler, app.repo 等
    """
    # ── 顶部标题栏 ────────────────────────────────
    title_frame = ttk.Frame(parent)
    title_frame.pack(fill="x", padx=12, pady=(12, 8))

    title_label = ttk.Label(
        title_frame,
        text="闹钟列表",
        font=("", 14, "bold"),
    )
    title_label.pack(side="left")

    refresh_btn = ttk.Button(
        title_frame,
        text="手动刷新",
        command=lambda: _refresh_alarms(),
    )
    refresh_btn.pack(side="right")

    # ── Treeview 闹钟列表 ─────────────────────────
    columns = ("time", "shift", "status")
    tree = ttk.Treeview(
        parent,
        columns=columns,
        show="headings",
        selectmode="none",
    )
    tree.heading("time", text="触发时间")
    tree.heading("shift", text="班次")
    tree.heading("status", text="状态")

    tree.column("time", width=140, anchor="center")
    tree.column("shift", width=120, anchor="center")
    tree.column("status", width=80, anchor="center")

    # 为每个班次类型配置 tag 颜色
    for st, color in SHIFT_COLORS.items():
        tag_name = f"shift_{st.value}"
        tree.tag_configure(tag_name, background=color)

    tree.pack(fill="both", expand=True, padx=12, pady=(0, 4))

    # ── 空状态提示 ────────────────────────────────
    empty_label = ttk.Label(
        parent,
        text="暂无即将触发的闹钟",
        font=("", 11),
        foreground="gray",
    )

    # ── 底部状态栏 ────────────────────────────────
    status_frame = ttk.Frame(parent)
    status_frame.pack(fill="x", padx=12, pady=(0, 8))

    status_text = tk.StringVar(value="")

    status_label = ttk.Label(
        status_frame,
        textvariable=status_text,
        font=("", 9),
        foreground="gray",
    )
    status_label.pack(side="left")

    # ── 自动刷新调度 ──────────────────────────────
    _auto_refresh_id: list[int | None] = [None]

    def _refresh_alarms():
        """从调度器获取数据并刷新列表"""
        if not hasattr(app, "scheduler") or app.scheduler is None:
            status_text.set("调度器不可用")
            return

        try:
            alarms = app.scheduler.get_upcoming_alarms(limit=30)
        except Exception as e:
            status_text.set(f"获取闹钟失败: {e}")
            return

        # 清除现有数据
        for item in tree.get_children():
            tree.delete(item)

        if not alarms:
            tree.pack_forget()
            empty_label.pack(fill="both", expand=True, padx=12, pady=50)
            status_text.set(f"更新时间: {datetime.now().strftime('%H:%M:%S')}")
        else:
            empty_label.pack_forget()
            tree.pack(fill="both", expand=True, padx=12, pady=(0, 4))

            for alarm in alarms:
                # 解析 alarm_time ISO 字符串
                try:
                    alarm_dt = datetime.fromisoformat(alarm["alarm_time"])
                    time_str = alarm_dt.strftime("%m/%d %H:%M")
                except (ValueError, KeyError):
                    time_str = alarm.get("alarm_time", "未知")

                # 班次信息
                shift_type_val = alarm.get("shift_type", 0)
                try:
                    st = ShiftType(shift_type_val)
                    shift_name = SHIFT_NAMES.get(st, alarm.get("shift_name", "未知"))
                except ValueError:
                    shift_name = alarm.get("shift_name", "未知")
                    st = None

                # 状态
                alarm_status = alarm.get("status", 0)
                status_display = STATUS_TEXT.get(alarm_status, f"状态{alarm_status}")

                # 确定 tag
                tag = f"shift_{shift_type_val}" if st else ""

                tree.insert(
                    "",
                    "end",
                    values=(time_str, shift_name, status_display),
                    tags=(tag,),
                )

            status_text.set(
                f"共 {len(alarms)} 条闹钟 | 更新时间: {datetime.now().strftime('%H:%M:%S')}"
            )

    def _schedule_auto_refresh():
        """执行一次刷新并安排下一次"""
        _refresh_alarms()

        # 检查 parent 是否仍然存在（视图可能已销毁）
        try:
            if parent.winfo_exists():
                _auto_refresh_id[0] = parent.after(30000, _schedule_auto_refresh)
        except Exception:
            pass

    def _on_destroy(*_):
        """视图销毁时取消自动刷新"""
        if _auto_refresh_id[0] is not None:
            try:
                parent.after_cancel(_auto_refresh_id[0])
            except Exception:
                pass
            _auto_refresh_id[0] = None

    # 绑定销毁事件以清理定时器
    parent.bind("<Destroy>", _on_destroy)

    # 初始加载：立即刷新一次，30秒后开始周期刷新
    _refresh_alarms()
    _auto_refresh_id[0] = parent.after(30000, _schedule_auto_refresh)
