"""中国法定节假日查询服务"""

from datetime import date, timedelta
from typing import Optional
import logging

from db.repository import Repository
from db.models import HolidayCache

logger = logging.getLogger(__name__)


class HolidayService:
    """节假日服务 —— 主数据源 chinese_calendar 库 + timor.tech API 降级"""

    def __init__(self, repo: Repository):
        self.repo = repo
        self._memory_cache: dict[str, HolidayCache] = {}

    def is_holiday(self, d: date) -> bool:
        """判断是否为法定节假日"""
        cache = self._get_cached(d)
        if cache:
            return cache.is_holiday and not cache.is_workday
        return self._is_weekend(d)

    def is_workday(self, d: date) -> bool:
        """判断是否为调休上班日（原本周末但需要上班）"""
        cache = self._get_cached(d)
        if cache:
            return cache.is_workday
        return False

    def get_holiday_name(self, d: date) -> str:
        """获取节假日名称"""
        cache = self._get_cached(d)
        if cache and cache.is_holiday:
            return cache.name
        return ""

    def _get_cached(self, d: date) -> Optional[HolidayCache]:
        """从内存缓存或数据库获取"""
        key = d.isoformat()
        if key in self._memory_cache:
            return self._memory_cache[key]

        db_cache = self.repo.get_holiday(d)
        if db_cache:
            self._memory_cache[key] = db_cache
            return db_cache

        # 未缓存，尝试从数据源查询
        result = self._query_holiday(d)
        if result:
            self._memory_cache[key] = result
            self.repo.save_holidays([result])
            return result

        return None

    def _query_holiday(self, d: date) -> Optional[HolidayCache]:
        """查询单个日期是否为节假日"""
        # 1. 尝试 chinese_calendar 库
        try:
            from chinese_calendar import is_holiday, is_workday, get_holiday_detail
            holiday = is_holiday(d)
            workday = is_workday(d)
            name = ""
            if holiday:
                detail = get_holiday_detail(d)
                if detail:
                    name = str(detail) if detail else ""
            return HolidayCache(
                date=d, year=d.year,
                is_holiday=holiday and not workday,
                is_workday=workday,
                name=name,
            )
        except Exception as e:
            logger.debug(f"chinese_calendar 查询失败: {e}")

        # 2. 降级：判断周末
        return HolidayCache(
            date=d, year=d.year,
            is_holiday=self._is_weekend(d),
            is_workday=False,
            name="周末" if self._is_weekend(d) else "",
        )

    def refresh_year(self, year: int):
        """刷新整年节假日数据"""
        try:
            from chinese_calendar import get_holidays, get_workdays
            holidays = get_holidays(year)
            workdays = get_workdays(year)

            cache_list = []
            # 遍历全年每一天
            current = date(year, 1, 1)
            end = date(year, 12, 31)
            holiday_set = set(holidays) if holidays else set()
            workday_set = set(workdays) if workdays else set()

            while current <= end:
                is_hol = current in holiday_set
                is_wd = current in workday_set
                cache_list.append(HolidayCache(
                    date=current, year=year,
                    is_holiday=is_hol,
                    is_workday=is_wd,
                    name="",
                ))
                current += timedelta(days=1)

            self.repo.save_holidays(cache_list)
            # 刷新内存缓存
            for hc in cache_list:
                self._memory_cache[hc.date.isoformat()] = hc
            logger.info(f"已刷新 {year} 年节假日数据，共 {len(cache_list)} 天")
        except Exception as e:
            logger.warning(f"刷新节假日数据失败: {e}")

    @staticmethod
    def _is_weekend(d: date) -> bool:
        """是否为周末"""
        return d.weekday() >= 5  # 5=周六, 6=周日
