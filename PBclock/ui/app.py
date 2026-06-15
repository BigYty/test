"""
主窗口 —— 使用 ttkbootstrap 构建原生桌面 UI

现代 SaaS 风格：浅灰底 + 白卡片 + 蓝色强调 + 浅色侧边栏
通过 show_view(name) 切换右侧内容区的视图。
"""

import importlib
import logging
import tkinter as tk

import ttkbootstrap as ttk
from ttkbootstrap.constants import *

logger = logging.getLogger(__name__)

# ── 视图名称常量 ──────────────────────────────────────

VIEW_WORKBENCH = "workbench"
VIEW_SHIFT_CONFIG = "shift_config"
VIEW_SCHEDULE_SETTINGS = "schedule_settings"
VIEW_ALARM_LIST = "alarm_list"
VIEW_SYSTEM_SETTINGS = "system_settings"

_VIEW_MODULES = {
    VIEW_WORKBENCH: "ui.views.dashboard",
    VIEW_SHIFT_CONFIG: "ui.views.shift_config",
    VIEW_SCHEDULE_SETTINGS: "ui.views.schedule_setup",
    VIEW_ALARM_LIST: "ui.views.alarm_list",
    VIEW_SYSTEM_SETTINGS: "ui.views.system_settings",
}

_NAV_ITEMS = [
    (VIEW_WORKBENCH, "📋", "工作台"),
    (VIEW_SHIFT_CONFIG, "⚙️", "班次配置"),
    (VIEW_SCHEDULE_SETTINGS, "📅", "排班设置"),
    (VIEW_ALARM_LIST, "🔔", "闹钟列表"),
    (VIEW_SYSTEM_SETTINGS, "🔧", "系统设置"),
]

# ── 设计令牌（现代 SaaS 风格）──────────────────────────

PAGE_BG = "#f1f5f9"          # 页面底色（冷灰）
SIDEBAR_BG = "#f8fafc"       # 侧边栏底色（微白）
CARD_BG = "#ffffff"          # 卡片白
BORDER = "#e2e8f0"           # 边框浅灰
ACCENT = "#3b82f6"           # 主强调蓝
ACCENT_LIGHT = "#eff6ff"     # 极浅蓝（hover/active 背景）
TEXT_PRIMARY = "#0f172a"     # 主文字（深 slate）
TEXT_SECONDARY = "#64748b"   # 次文字
TEXT_MUTED = "#94a3b8"       # 弱文字
DANGER = "#ef4444"           # 危险/红色
SUCCESS = "#22c55e"          # 成功绿

SIDEBAR_WIDTH = 220


class MainApp(ttk.Window):
    """排班闹钟主窗口

    通过属性暴露后端服务和设计令牌给各视图：
    - self.repo / self.engine / self.scheduler
    - self.design — 设计令牌 dict
    """

    def __init__(self, repo, engine, scheduler, reschedule_callback):
        super().__init__(themename="cosmo", size=(1100, 750), title="排班闹钟")

        self.repo = repo
        self.engine = engine
        self.scheduler = scheduler
        self.reschedule_callback = reschedule_callback

        self.design = {
            "page_bg": PAGE_BG, "sidebar_bg": SIDEBAR_BG,
            "card_bg": CARD_BG, "border": BORDER,
            "accent": ACCENT, "accent_light": ACCENT_LIGHT,
            "text_primary": TEXT_PRIMARY, "text_secondary": TEXT_SECONDARY,
            "text_muted": TEXT_MUTED, "danger": DANGER, "success": SUCCESS,
        }

        self._current_view_name: str | None = None
        self._nav_buttons: dict[str, dict] = {}

        self.minsize(900, 600)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_layout()
        self.show_view(VIEW_WORKBENCH)

    # ── 布局 ───────────────────────────────────────────

    def _build_layout(self):
        main = ttk.Frame(self)
        main.pack(fill=BOTH, expand=True)

        # 左右分栏
        sidebar_frame = ttk.Frame(main, width=SIDEBAR_WIDTH)
        sidebar_frame.pack(side=LEFT, fill=Y)
        sidebar_frame.pack_propagate(False)

        content_frame = ttk.Frame(main)
        content_frame.pack(side=LEFT, fill=BOTH, expand=True)

        self._build_sidebar(sidebar_frame)
        self._build_content(content_frame)

    def _build_sidebar(self, parent: ttk.Frame):
        """浅色侧边栏 — 现代极简风格"""
        sidebar = tk.Frame(parent, bg=SIDEBAR_BG)

        # 右侧分隔线
        sep = tk.Frame(parent, bg=BORDER, width=1)
        sep.pack(side=RIGHT, fill=Y)

        sidebar.pack(fill=BOTH, expand=True)

        # ── Logo 区 ──
        logo_frame = tk.Frame(sidebar, bg=SIDEBAR_BG)
        logo_frame.pack(fill=X, padx=16, pady=(20, 6))

        # 应用名
        tk.Label(
            logo_frame, text="排班闹钟",
            font=("Microsoft YaHei UI", 15, "bold"),
            fg=TEXT_PRIMARY, bg=SIDEBAR_BG,
        ).pack(anchor="w")

        tk.Label(
            logo_frame, text="PBclock v3",
            font=("Segoe UI", 8),
            fg=TEXT_MUTED, bg=SIDEBAR_BG,
        ).pack(anchor="w")

        # 分隔
        tk.Frame(sidebar, bg=BORDER, height=1).pack(fill=X, padx=12, pady=(12, 8))

        # ── 导航 ──
        nav_frame = tk.Frame(sidebar, bg=SIDEBAR_BG)
        nav_frame.pack(fill=BOTH, expand=True, padx=8)

        for view_name, icon, label in _NAV_ITEMS:
            btn_data = self._create_nav_item(nav_frame, view_name, icon, label)
            self._nav_buttons[view_name] = btn_data

        # ── 底部 ──
        bottom = tk.Frame(sidebar, bg=SIDEBAR_BG)
        bottom.pack(fill=X, padx=16, pady=(8, 16))

        tk.Label(
            bottom, text="Windows 11 · Desktop",
            font=("Segoe UI", 7), fg=TEXT_MUTED, bg=SIDEBAR_BG,
        ).pack(anchor="w")
        tk.Label(
            bottom, text="by: BigYty",
            font=("Segoe UI", 7, "italic"), fg=TEXT_MUTED, bg=SIDEBAR_BG,
        ).pack(anchor="w")

    def _create_nav_item(self, parent, view_name, icon, label):
        """创建导航项 — 圆角矩形，hover/active 切换蓝色背景"""
        # 外层容器保持统一间距
        wrapper = tk.Frame(parent, bg=SIDEBAR_BG)
        wrapper.pack(fill=X)

        # 可点击的标签区域
        btn = tk.Frame(wrapper, bg=SIDEBAR_BG, cursor="hand2")
        btn.pack(fill=X, padx=4, pady=1)

        icon_lbl = tk.Label(
            btn, text=icon,
            bg=SIDEBAR_BG, fg=TEXT_SECONDARY,
            font=("Segoe UI", 12),
        )
        icon_lbl.pack(side=LEFT, padx=(12, 8), pady=7)

        text_lbl = tk.Label(
            btn, text=label,
            bg=SIDEBAR_BG, fg=TEXT_PRIMARY,
            font=("Microsoft YaHei UI", 10),
            anchor="w",
        )
        text_lbl.pack(side=LEFT, pady=7)

        # 右侧圆点指示器（默认隐藏）
        dot = tk.Canvas(btn, width=6, height=6, bg=SIDEBAR_BG, highlightthickness=0)
        dot.pack(side=RIGHT, padx=(0, 12), pady=7)
        dot.pack_forget()

        all_widgets = [btn, icon_lbl, text_lbl]

        def on_click(e, v=view_name):
            self.show_view(v)

        def on_enter(e, b=btn, i=icon_lbl, t=text_lbl, d=dot):
            if self._nav_buttons.get(self._current_view_name, {}).get("btn") != b:
                b.configure(bg=ACCENT_LIGHT)
                for c in [i, t]:
                    c.configure(bg=ACCENT_LIGHT)
                i.configure(fg=ACCENT)
                t.configure(fg=ACCENT)

        def on_leave(e, b=btn, i=icon_lbl, t=text_lbl, d=dot):
            is_active = self._nav_buttons.get(self._current_view_name, {}).get("btn") == b
            if not is_active:
                b.configure(bg=SIDEBAR_BG)
                for c in [i, t]:
                    c.configure(bg=SIDEBAR_BG)
                i.configure(fg=TEXT_SECONDARY)
                t.configure(fg=TEXT_PRIMARY)

        for w in all_widgets:
            w.bind("<Button-1>", on_click)
            w.bind("<Enter>", on_enter)
            w.bind("<Leave>", on_leave)

        return {"wrapper": wrapper, "btn": btn, "icon": icon_lbl, "text": text_lbl, "dot": dot}

    def _build_content(self, parent: ttk.Frame):
        """右侧内容区"""
        self.content_frame = ttk.Frame(parent)
        self.content_frame.pack(fill=BOTH, expand=True)

    # ── 视图导航 ──────────────────────────────────────

    def show_view(self, name: str):
        self._current_view_name = name

        for widget in self.content_frame.winfo_children():
            widget.destroy()

        module_path = _VIEW_MODULES.get(name)
        if module_path:
            try:
                mod = importlib.import_module(module_path)
                mod.build(self.content_frame, self)
            except ImportError:
                self._show_placeholder(name)
            except Exception:
                logger.exception("视图 %s 构建失败", name)
                self._show_placeholder(name)

        self._update_nav_active(name)

    def refresh_current_view(self):
        if self._current_view_name:
            self.show_view(self._current_view_name)

    def after_save(self):
        if self.reschedule_callback:
            self.reschedule_callback()
        self.refresh_current_view()

    # ── 导航激活态 ────────────────────────────────────

    def _update_nav_active(self, active_name: str):
        for name, data in self._nav_buttons.items():
            btn = data["btn"]
            icon = data["icon"]
            text = data["text"]
            dot = data["dot"]

            is_active = (name == active_name)
            # 先重置所有子控件 bg
            bg = ACCENT_LIGHT if is_active else SIDEBAR_BG
            for w in [btn, icon, text]:
                w.configure(bg=bg)
            icon.configure(fg=ACCENT if is_active else TEXT_SECONDARY)
            text.configure(fg=ACCENT if is_active else TEXT_PRIMARY)
            # 圆点指示器
            if is_active:
                dot.pack(side=RIGHT, padx=(0, 12), pady=7)
                dot.configure(bg=ACCENT_LIGHT)
                dot.delete("all")
                dot.create_oval(0, 0, 6, 6, fill=ACCENT, outline="")
            else:
                dot.pack_forget()

    def _show_placeholder(self, name: str):
        f = ttk.Frame(self.content_frame)
        f.pack(expand=True)
        ttk.Label(f, text=f"视图「{name}」尚未实现",
                  font=("Microsoft YaHei UI", 14), bootstyle="secondary").pack(pady=20)

    # ── 窗口行为 ──────────────────────────────────────

    def show_window(self):
        self.deiconify()
        self.lift()
        self.focus_force()

    def _on_close(self):
        self.withdraw()

    def quit_app(self):
        if self.scheduler:
            try:
                self.scheduler.shutdown()
            except Exception:
                logger.exception("关闭调度器时出错")
        self.destroy()
