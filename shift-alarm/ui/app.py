"""
主窗口 —— 使用 ttkbootstrap 构建原生桌面 UI

左侧边栏（200px） + 右侧内容区布局。
通过 show_view(name) 切换右侧内容区的视图。
"""

import importlib
import logging

import ttkbootstrap as ttk
from ttkbootstrap.constants import *

logger = logging.getLogger(__name__)

# ── 视图名称常量 ──────────────────────────────────────

VIEW_WORKBENCH = "workbench"
VIEW_SHIFT_CONFIG = "shift_config"
VIEW_SCHEDULE_SETTINGS = "schedule_settings"
VIEW_ALARM_LIST = "alarm_list"
VIEW_SYSTEM_SETTINGS = "system_settings"

# 视图名 → 模块路径 映射
_VIEW_MODULES = {
    VIEW_WORKBENCH: "ui.views.dashboard",
    VIEW_SHIFT_CONFIG: "ui.views.shift_config",
    VIEW_SCHEDULE_SETTINGS: "ui.views.schedule_setup",
    VIEW_ALARM_LIST: "ui.views.alarm_list",
    VIEW_SYSTEM_SETTINGS: "ui.views.system_settings",
}

# 导航按钮标签
_NAV_LABELS = [
    (VIEW_WORKBENCH, "📋  工作台"),
    (VIEW_SHIFT_CONFIG, "⚙️  班次配置"),
    (VIEW_SCHEDULE_SETTINGS, "📅  排班设置"),
    (VIEW_ALARM_LIST, "🔔  闹钟列表"),
    (VIEW_SYSTEM_SETTINGS, "🔧  系统设置"),
]


class MainApp(ttk.Window):
    """排班闹钟主窗口

    接收所有后端服务实例，通过属性暴露给各视图：
    - self.repo       — Repository 实例
    - self.engine     — ShiftEngine 实例
    - self.scheduler  — AlarmScheduler 实例
    """

    def __init__(self, repo, engine, scheduler, reschedule_callback):
        super().__init__(themename="cosmo", size=(1100, 750), title="排班闹钟")

        # 后端服务
        self.repo = repo
        self.engine = engine
        self.scheduler = scheduler
        self.reschedule_callback = reschedule_callback

        # 内部状态
        self._current_view_name: str | None = None
        self._nav_buttons: dict[str, ttk.Button] = {}

        # 窗口配置
        self.minsize(900, 600)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # 构建布局
        self._build_layout()

        # 默认显示工作台
        self.show_view(VIEW_WORKBENCH)

    # ── 布局 ───────────────────────────────────────────

    def _build_layout(self):
        """主布局：左侧边栏 + 右侧内容区"""
        main_container = ttk.Frame(self)
        main_container.pack(fill=BOTH, expand=True)

        self._build_sidebar(main_container)
        self._build_content_area(main_container)

    def _build_sidebar(self, parent: ttk.Frame):
        """构建左侧 200px 导航栏"""
        sidebar = ttk.Frame(parent, width=200, bootstyle="dark")
        sidebar.pack(side=LEFT, fill=Y)
        sidebar.pack_propagate(False)

        # 应用标题
        title_frame = ttk.Frame(sidebar, bootstyle="dark")
        title_frame.pack(fill=X, pady=(20, 30))
        ttk.Label(
            title_frame,
            text="⏰ 排班闹钟",
            font=("Microsoft YaHei UI", 16, "bold"),
            bootstyle="inverse-dark",
        ).pack(padx=15)

        # 导航按钮
        for view_name, label_text in _NAV_LABELS:
            btn = ttk.Button(
                sidebar,
                text=label_text,
                bootstyle="dark-outline",
                command=lambda v=view_name: self.show_view(v),
            )
            btn.pack(fill=X, padx=10, pady=3)
            self._nav_buttons[view_name] = btn

    def _build_content_area(self, parent: ttk.Frame):
        """构建右侧内容区"""
        self.content_frame = ttk.Frame(parent)
        self.content_frame.pack(side=LEFT, fill=BOTH, expand=True)

    # ── 视图导航 ──────────────────────────────────────

    def show_view(self, name: str):
        """切换到指定视图"""
        self._current_view_name = name

        # 清除内容区所有子控件
        for widget in self.content_frame.winfo_children():
            widget.destroy()

        # 动态导入视图模块并调用 build()
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
        """重新渲染当前视图"""
        if self._current_view_name:
            self.show_view(self._current_view_name)

    def after_save(self):
        """保存后触发重调度并刷新当前视图"""
        if self.reschedule_callback:
            self.reschedule_callback()
        self.refresh_current_view()

    # ── 窗口行为 ──────────────────────────────────────

    def show_window(self):
        """显示并前置主窗口（供托盘回调使用）"""
        self.deiconify()
        self.lift()
        self.focus_force()

    def _on_close(self):
        """窗口关闭按钮 → 隐藏到托盘"""
        self.withdraw()

    def quit_app(self):
        """完全退出应用"""
        if self.scheduler:
            try:
                self.scheduler.shutdown()
            except Exception:
                logger.exception("关闭调度器时出错")
        self.destroy()

    # ── 内部辅助 ──────────────────────────────────────

    def _update_nav_active(self, active_name: str):
        """更新导航按钮激活态样式"""
        for name, btn in self._nav_buttons.items():
            if name == active_name:
                btn.configure(bootstyle="primary")
            else:
                btn.configure(bootstyle="dark-outline")

    def _show_placeholder(self, name: str):
        """视图模块不存在时的占位提示"""
        placeholder = ttk.Frame(self.content_frame)
        placeholder.pack(expand=True)
        ttk.Label(
            placeholder,
            text=f"视图「{name}」尚未实现",
            font=("Microsoft YaHei UI", 14),
            bootstyle="secondary",
        ).pack(pady=20)
        ttk.Label(
            placeholder,
            text="请完成对应视图模块的 build() 函数",
            font=("Microsoft YaHei UI", 10),
            bootstyle="secondary",
        ).pack()
