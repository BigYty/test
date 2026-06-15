"""中国法定节假日查询服务 —— 从 holidays-calendar.net 爬取数据"""

from datetime import date, timedelta
from typing import Optional
import logging
import re

import requests

from db.repository import Repository
from db.models import HolidayCache

logger = logging.getLogger(__name__)

CALENDAR_URL = "https://holidays-calendar.net/calendar_zh_cn/china_zh_cn.html"

# 假日名称列表（按页面出现顺序）
HOLIDAY_NAMES_ORDERED = ["元旦", "春节", "清明节", "劳动节", "端午节", "中秋节", "国庆节"]


class HolidayService:
    """节假日服务 —— 数据源: holidays-calendar.net"""

    def __init__(self, repo: Repository):
        self.repo = repo
        self._memory_cache: dict[str, HolidayCache] = {}

    def is_holiday(self, d: date) -> bool:
        cache = self._get_cached(d)
        if cache:
            return cache.is_holiday and not cache.is_workday
        return self._is_weekend(d)

    def is_workday(self, d: date) -> bool:
        cache = self._get_cached(d)
        if cache:
            return cache.is_workday
        return False

    def get_holiday_name(self, d: date) -> str:
        cache = self._get_cached(d)
        if cache and cache.is_holiday:
            return cache.name
        return ""

    def _get_cached(self, d: date) -> Optional[HolidayCache]:
        key = d.isoformat()
        if key in self._memory_cache:
            return self._memory_cache[key]
        db_cache = self.repo.get_holiday(d)
        if db_cache:
            self._memory_cache[key] = db_cache
            return db_cache
        return None

    def refresh_year(self, year: int):
        """从 holidays-calendar.net 爬取整年节假日数据"""
        try:
            logger.info(f"正在爬取 {year} 年节假日...")
            resp = requests.get(CALENDAR_URL, timeout=15, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            resp.encoding = "utf-8"
            html = resp.text
        except Exception as e:
            logger.warning(f"爬取失败: {e}")
            return

        holiday_set, workday_set, holiday_names = self._parse_page(html, year)

        if not holiday_set:
            logger.warning(f"未能解析 {year} 年节假日")
            return

        cache_list = []
        current = date(year, 1, 1)
        end = date(year, 12, 31)
        while current <= end:
            is_hol = current in holiday_set
            is_wd = current in workday_set
            name = holiday_names.get(current, "")
            cache_list.append(HolidayCache(
                date=current, year=year,
                is_holiday=is_hol,
                is_workday=is_wd,
                name=name,
            ))
            current += timedelta(days=1)

        self.repo.save_holidays(cache_list)
        for hc in cache_list:
            self._memory_cache[hc.date.isoformat()] = hc
        logger.info(
            f"已刷新 {year} 年: {len(holiday_set)}天假期, "
            f"{len(workday_set)}天补班"
        )

    def _parse_page(
        self, html: str, year: int,
    ) -> tuple[set[date], set[date], dict[date, str]]:
        """解析页面"""
        holiday_set: set[date] = set()
        workday_set: set[date] = set()
        holiday_names: dict[date, str] = {}

        # 提取纯文本
        text = re.sub(r'<[^>]+>', ' ', html)
        text = re.sub(r'&nbsp;|&ensp;|&emsp;| | ', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()

        # 找到「中国节日 YYYY」区块
        year_str = str(year)
        title_match = re.search(rf"中国节日\s*{year_str}", text)
        if not title_match:
            logger.warning(f"未找到 中国节日 {year}")
            return holiday_set, workday_set, holiday_names

        start_pos = title_match.start()
        next_title = re.search(r"中国节日\s*\d{4}", text[start_pos + 10:])
        if next_title:
            block = text[start_pos:start_pos + 10 + next_title.start()]
        else:
            block = text[start_pos:]

        # ── 策略：找所有「放假」日期范围 + 所有「上班」日期，就近匹配假日名称 ──

        # 1. 找所有假期日期范围（带"放假"关键词的）
        # 完整跨月: X月X日至X月X日...放假
        for m in re.finditer(
            r'(\d{1,2})\s*月\s*(\d{1,2})\s*日[^0-9]{0,30}?[至\-–]\s*'
            r'(\d{1,2})\s*月\s*(\d{1,2})\s*日[^。]{0,80}?放[假休]',
            block
        ):
            m1, d1 = int(m.group(1)), int(m.group(2))
            m2, d2 = int(m.group(3)), int(m.group(4))
            hname = self._closest_holiday_before(block, m.start())
            self._fill_range(year, m1, d1, m2, d2, hname, holiday_set, holiday_names)

        # 同月简写: X月X日至X日...放假
        for m in re.finditer(
            r'(\d{1,2})\s*月\s*(\d{1,2})\s*日[^0-9]{0,20}?至\s*(\d{1,2})\s*日[^。]{0,80}?放[假休]',
            block
        ):
            month, d1, d2 = int(m.group(1)), int(m.group(2)), int(m.group(3))
            hname = self._closest_holiday_before(block, m.start())
            self._fill_range(year, month, d1, month, d2, hname, holiday_set, holiday_names)

        # 2. 找所有补班日期
        for m in re.finditer(r'上班', block):
            pos = m.start()
            # 取「上班」之前的文本（最多150字符）
            before = block[max(0, pos - 150):pos]
            # 找这之前的所有日期
            dates_before = re.findall(r'(\d{1,2})\s*月\s*(\d{1,2})\s*日', before)
            for m_str, d_str in dates_before[-5:]:
                try:
                    dt = date(year, int(m_str), int(d_str))
                    if self._is_valid_date(dt) and dt not in holiday_set:
                        workday_set.add(dt)
                        logger.debug(f"  补班: {dt}")
                except ValueError:
                    pass

        return holiday_set, workday_set, holiday_names

    def _closest_holiday_before(self, text: str, pos: int) -> str:
        """找到 pos 之前最近的假日名称（限制在200字符内）"""
        best_name = ""
        best_dist = 200  # 最多往前找200字符
        for hname in HOLIDAY_NAMES_ORDERED:
            before = text[:pos]
            idx = before.rfind(hname)
            if idx >= 0:
                dist = pos - idx
                if dist < best_dist:
                    best_dist = dist
                    best_name = hname
        return best_name

    def _fill_range(
        self, year: int, m1: int, d1: int, m2: int, d2: int,
        name: str, holiday_set: set[date], holiday_names: dict[date, str],
    ):
        """填充日期范围"""
        try:
            start = date(year, m1, d1)
            end = date(year, m2, d2)
            if not self._is_valid_date(start) or not self._is_valid_date(end):
                return
            cur = start
            while cur <= end:
                holiday_set.add(cur)
                if name and cur not in holiday_names:
                    holiday_names[cur] = name
                cur += timedelta(days=1)
            logger.debug(f"  假期: {start}~{end} ({name})")
        except ValueError:
            pass

    @staticmethod
    def _is_valid_date(d: date) -> bool:
        return date(2000, 1, 1) <= d <= date(2099, 12, 31)

    @staticmethod
    def _is_weekend(d: date) -> bool:
        return d.weekday() >= 5
