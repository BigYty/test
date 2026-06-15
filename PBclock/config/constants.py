"""班次类型、工作模式等常量定义"""

from enum import IntEnum


class ShiftType(IntEnum):
    """班次类型枚举"""
    DAY_SHIFT = 1       # 白班
    NIGHT_SHIFT = 2     # 夜班(A)
    MORNING_SHIFT = 3   # 早班
    REST = 4            # 休息
    NIGHT_SHIFT_B = 5   # 夜班(B) —— 第二个夜班，用户可独立配置
    ON_DUTY = 6         # 值班


class WorkMode(IntEnum):
    """工作模式"""
    NORMAL = 1   # 正常工作表
    SPECIAL = 2  # 特殊工种


# 班次中文名称
SHIFT_NAMES: dict[ShiftType, str] = {
    ShiftType.DAY_SHIFT:     "白班",
    ShiftType.NIGHT_SHIFT:   "夜班(A)",
    ShiftType.MORNING_SHIFT: "早班",
    ShiftType.REST:          "休息",
    ShiftType.NIGHT_SHIFT_B: "夜班(B)",
    ShiftType.ON_DUTY:       "值班",
}

# 班次显示颜色 (HEX)
SHIFT_COLORS: dict[ShiftType, str] = {
    ShiftType.DAY_SHIFT:     "#FFB74D",  # 橙色
    ShiftType.NIGHT_SHIFT:   "#5C6BC0",  # 靛蓝
    ShiftType.MORNING_SHIFT: "#66BB6A",  # 绿色
    ShiftType.REST:          "#BDBDBD",  # 灰色
    ShiftType.NIGHT_SHIFT_B: "#4527A0",  # 深紫
    ShiftType.ON_DUTY:       "#EF5350",  # 红色
}

# 默认班次时间 (start_minutes, end_minutes)，相对于当日 00:00
# end_minutes 可超过 1440 (24h)，表示跨日
DEFAULT_SHIFT_TIMES: dict[ShiftType, tuple[int, int]] = {
    ShiftType.DAY_SHIFT:     (8 * 60,  20 * 60),            # 08:00-20:00
    ShiftType.NIGHT_SHIFT:   (20 * 60, 24 * 60 + 8 * 60),   # 20:00-次日08:00
    ShiftType.MORNING_SHIFT: (6 * 60,  14 * 60),            # 06:00-14:00
    ShiftType.REST:          (0,       0),                   # 全天休息
    ShiftType.NIGHT_SHIFT_B: (20 * 60, 24 * 60 + 8 * 60),   # 20:00-次日08:00
    ShiftType.ON_DUTY:       (8 * 60,  17 * 60),            # 08:00-17:00
}

# 默认提前提醒分钟数
DEFAULT_REMINDER_MINUTES = 30

# 正常工作表可用班次
NORMAL_MODE_SHIFTS = {ShiftType.DAY_SHIFT, ShiftType.ON_DUTY, ShiftType.REST}

# 特殊工种可用班次（全部6种）
SPECIAL_MODE_SHIFTS = set(ShiftType)

# 正常工作表默认周循环
DEFAULT_WEEKLY_PATTERN: dict[int, ShiftType] = {
    0: ShiftType.DAY_SHIFT,   # 周一 → 白班
    1: ShiftType.DAY_SHIFT,   # 周二 → 白班
    2: ShiftType.DAY_SHIFT,   # 周三 → 白班
    3: ShiftType.DAY_SHIFT,   # 周四 → 白班
    4: ShiftType.DAY_SHIFT,   # 周五 → 白班
    5: ShiftType.ON_DUTY,     # 周六 → 值班
    6: ShiftType.REST,        # 周日 → 休息
}
