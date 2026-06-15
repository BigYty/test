# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

排班闹钟 — Windows 11 原生桌面应用（tkinter + ttkbootstrap）。用户自定义班次循环，系统按排班发送 Windows 原生通知。支持中国法定节假日自动同步。

## 常用命令

```powershell
# 启动应用
cd shift-alarm && python main.py

# 打包 exe
cd shift-alarm && pyinstaller shift_alarm.spec --noconfirm

# 测试节假日爬取（删缓存重爬）
python -c "
import os; os.remove(os.path.expanduser('~/AppData/Local/ShiftAlarm/shift_alarm.db'))
from db.repository import Repository; from core.holiday_service import HolidayService
r=Repository(); r.init_tables(); r.seed_defaults()
HolidayService(r).refresh_year(2026)
print('OK')
"

# 安装依赖
pip install -r shift-alarm/requirements.txt
```

## 架构

```
┌─────────────────────────────────────────┐
│          tkinter 原生窗口                │
│  ui/app.py (MainApp)                    │
│  ├─ 侧边栏导航 (5个视图)                 │
│  └─ 内容区 (动态加载 ui/views/*.py)      │
└──────────────┬──────────────────────────┘
               │ 直接调用 (无 HTTP 层)
┌──────────────▼──────────────────────────┐
│  core/shift_engine.py    排班循环计算     │
│  core/alarm_scheduler.py APScheduler调度 │
│  core/holiday_service.py 节假日爬取      │
│  db/repository.py        SQLite 访问层   │
└──────────────┬──────────────────────────┘
               │
    ┌──────────┴──────────┐
    ▼                     ▼
  SQLite          winotify (Windows 通知)
  (~/AppData/     pystray (系统托盘)
  Local/ShiftAlarm/)
```

`main.py` 入口流程：初始化 DB → ShiftEngine → AlarmScheduler → MainApp → pystray 托盘 → tkinter 主循环

## 核心模块

### `ui/app.py` — 主窗口 (MainApp)
- 继承 `ttk.Window`（ttkbootstrap `cosmo` 主题），1100x750
- 左侧 200px 深色侧边栏 + 右侧内容区 `self.content_frame`
- 通过 `self.repo`, `self.engine`, `self.scheduler` 属性暴露后端服务给各视图
- `show_view(name)` — 用 `importlib` 动态加载 `ui.views.*` 模块，调用 `build(parent_frame, self)`
- `after_save()` — 保存后触发 `reschedule_callback` + 刷新当前视图
- 窗口关闭 → `self.withdraw()` 隐藏到托盘，不退出

### `ui/tray.py` — 系统托盘
- 用 pystray + Pillow 动态绘制时钟图标
- 右键菜单：打开主界面 / 退出；双击显示窗口
- `create_tray(root_app, on_open, on_quit)` 工厂函数

### `ui/views/dashboard.py` — 工作台视图
- 今日/明日班次卡片（ttk.LabelFrame，左边框彩色条）+ 月历组件 CalendarGrid
- 当前工作模式指示 + "刷新节假日"按钮

### `ui/views/shift_config.py` — 班次配置视图
- 6 个班次卡片 2x3 网格，每卡片含：开始/结束时间 Entry、☑次日复选框、提前提醒 Spinbox
- 休息（类型4）跳过时间控件。"保存所有班次"→ `repo.update_shift()` → `after_save()`

### `ui/views/schedule_setup.py` — 排班设置视图
- 工作模式 Radiobutton（正常/特殊）+ CycleBuilder 组件 + 起始日期/位置选择 + 14天预览表

### `ui/views/alarm_list.py` — 闹钟列表（ttk.Treeview）
- 三列：时间 | 班次（彩色tag）| 状态，30秒自动刷新，通过 `<Destroy>` 绑定取消定时器

### `ui/views/system_settings.py` — 系统设置（ttk.Notebook 双标签页）
- 闹钟设置：延迟 Spinbox + 音量 Scale；节假日管理：年份 + 刷新按钮

### `ui/widgets/calendar_grid.py` — 月历组件 CalendarGrid(ttk.Frame)
- 7列网格，每个日期显示数字+班次简称，彩色背景（`lighten_color` 减淡）
- 今天蓝色边框，节假日金色边框，点击弹出覆盖对话框

### `ui/widgets/cycle_builder.py` — 循环构建器 CycleBuilder(ttk.Frame)
- 上部6个彩色按钮（点击添加），中部已选序列（点击移除），下部清空按钮

### `core/shift_engine.py` — 排班引擎（不变）
- `get_shift_for_date()` → `(ShiftType, is_holiday_override)`
- NORMAL：周循环 → 节假日覆盖 REST → 调休上班日恢复白班
- SPECIAL：`(start_index + days) % cycle_len` 循环

### `core/alarm_scheduler.py` — 闹钟调度（不变）
- APScheduler `DateTrigger`（非 CronTrigger），凌晨 2:00 重算未来 14 天
- 闹钟时间 = 班次开始 - 提醒分钟，不可跨到前一日
- 触发 → `winotify` Windows toast

### `core/holiday_service.py` — 节假日（不变）
- 爬取 `holidays-calendar.net/calendar_zh_cn/china_zh_cn.html`
- 正则匹配「放假」「上班」提取日期范围，`_closest_holiday_before()` 就近匹配名称
- 缓存到 `holiday_cache` 表 + 内存 `_memory_cache`

### `config/constants.py` — 班次定义（不变）
- 6 种 `ShiftType` 枚举 + `SHIFT_NAMES`, `SHIFT_COLORS`, `DEFAULT_SHIFT_TIMES`
- 时间用**当日分钟数** (0-2879)，≥1440 即跨日，`time_utils.py` 转换显示
- `NORMAL_MODE_SHIFTS` = {白班, 值班, 休息}

### `db/repository.py` — 数据访问层（不变）
- 6 张表：`settings`, `shift_config`, `cycle_pattern`, `schedule`, `alarm_log`, `holiday_cache`
- `AppSettings` JSON 序列化存 `settings` 键值表

## 关键设计决策

1. **tkinter + ttkbootstrap** 而非 PyQt/Web：Python 3.13 内置 tkinter 保证兼容，ttkbootstrap 提供 Win11 现代主题
2. **无 HTTP 层**：视图直接调用 `app.repo`/`app.engine`，去除 FastAPI 中间层
3. **视图动态加载**：`importlib.import_module` 按需加载视图模块，`build(parent, app)` 统一接口
4. **APScheduler DateTrigger**：排班每天不同，凌晨重算而非 CronTrigger
5. **分钟数存储**：时间用相对分钟 (0-2879)，≥1440 即跨日
6. **PyInstaller 单文件 exe**：`shift_alarm.spec` → `dist/ShiftAlarm.exe` (~41MB)
7. **`after_save()` 统一钩子**：任何保存操作后触发 `reschedule_callback` + 视图刷新
