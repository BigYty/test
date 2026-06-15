# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

排班闹钟 — Windows 11 桌面应用。用户自定义班次循环，系统按排班在指定时间发送 Windows 原生通知提醒。支持中国法定节假日自动同步。

## 常用命令

```powershell
# 启动应用（浏览器自动打开 http://127.0.0.1:8765）
cd shift-alarm && python main.py

# 仅启动 Web 服务（不启动托盘/闹钟，方便调试前端）
python -c "from web.server import create_app; import uvicorn; uvicorn.run(create_app(), host='127.0.0.1', port=8765)"

# 测试节假日爬取（删除旧缓存后重爬）
python -c "
import os; os.remove(os.path.expanduser('~/AppData/Local/ShiftAlarm/shift_alarm.db'))
from db.repository import Repository; from core.holiday_service import HolidayService
r=Repository(); r.init_tables(); r.seed_defaults()
HolidayService(r).refresh_year(2026)
print('OK')
"

# 安装/更新依赖
pip install -r shift-alarm/requirements.txt
```

## 架构

```
浏览器 (localhost:8765)
    │  HTTP REST + 静态文件
    ▼
FastAPI (web/server.py, web/api_routes.py)
    │
    ├── core/shift_engine.py    ← 排班循环计算
    ├── core/alarm_scheduler.py ← APScheduler 闹钟调度
    ├── core/holiday_service.py ← 节假日爬取
    └── db/repository.py        ← SQLite 数据访问层
            │
            ▼
        SQLite (~/AppData/Local/ShiftAlarm/shift_alarm.db)

main.py 统一入口：起 Web 线程 + APScheduler + pystray 托盘 + winotify 通知
```

## 核心模块

### `core/shift_engine.py` — 排班引擎
- `get_shift_for_date(target_date, ...)` → `(ShiftType, is_holiday_override)`
- NORMAL 模式：按 `DEFAULT_WEEKLY_PATTERN` 周循环 → 节假日覆盖为 REST → 调休上班日恢复
- SPECIAL 模式：`(start_index + days_from_start) % cycle_length` 循环
- `generate_schedules(start, end)` 批量生成并写库

### `core/alarm_scheduler.py` — 闹钟调度
- 基于 APScheduler `BackgroundScheduler`，使用 `DateTrigger`（非 CronTrigger，因每天排班不同）
- 凌晨 2:00 自动重算未来 14 天闹钟
- 闹钟时间计算在 `core/time_utils.py`：`班次开始 - 提前提醒分钟数`，不可跨到前一日
- 触发回调 → `winotify` 发送 Windows 原生 toast

### `core/holiday_service.py` — 节假日
- **数据源**：`https://holidays-calendar.net/calendar_zh_cn/china_zh_cn.html`
- 页面格式为纯文本段落，通过正则匹配「放假」「上班」关键词提取日期范围
- `_closest_holiday_before()` 将日期范围就近匹配到假日名称
- 结果缓存到 `holiday_cache` 表 + 内存 `_memory_cache`
- 函数签名 `is_holiday(d)`, `is_workday(d)`, `get_holiday_name(d)`

### `db/repository.py` — 数据访问层（单例）
- 5 张表：`settings`, `shift_config`, `cycle_pattern`, `schedule`, `alarm_log`, `holiday_cache`
- `seed_defaults()` 仅在表为空时填充 6 种班次默认值
- `AppSettings` 序列化为 JSON 存 `settings` 键值表

### `config/constants.py` — 班次定义
- 6 种班次：`ShiftType` 枚举 + `SHIFT_NAMES`, `SHIFT_COLORS`, `DEFAULT_SHIFT_TIMES`
- 时间用**当日分钟数** (0-2879) 表示，≥1440 即跨日，通过 `core/time_utils.py` 转换显示
- `NORMAL_MODE_SHIFTS` = {白班, 值班, 休息}，`SPECIAL_MODE_SHIFTS` = 全部 6 种

### 前端（SPA，无框架）
- `web/static/index.html` — 5 个页面（section 切换）
- `web/static/js/app.js` — 全局状态 `STATE`、API 封装、页面导航、工作台渲染
- `web/static/js/config.js` — 班次配置、**点选式循环构建器**（点击按钮添加到序列，点击序列位移除）、排班设置、闹钟列表
- `web/static/js/calendar.js` — 月历渲染（lightenColor 生成渐变背景）

## 关键设计决策

1. **Web UI + 后台进程** 而非 PyQt：Python 3.13 兼容性好，UI 开发快，浏览器即界面
2. **APScheduler DateTrigger** 而非 CronTrigger：排班每天可能不同，每天凌晨重算所有闹钟
3. **分钟数存储** 而非 datetime：班次起止时间用相对分钟 (0-2879)，支持跨日（≥1440）
4. **节假日只在查询时判断**：`is_holiday()` 无缓存则按周末兜底，避免误判
5. **前端无框架**：纯原生 JS + CSS Grid/Flexbox，零依赖，加载极快
6. **数据存储**：`~/AppData/Local/ShiftAlarm/` 下 SQLite + 日志文件
