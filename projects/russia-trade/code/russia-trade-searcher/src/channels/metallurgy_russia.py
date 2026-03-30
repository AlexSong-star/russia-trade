"""
Metallurgy Russia 展会参展商搜索器 (metallurgy-russia.ru)
俄罗斯最大的冶金/铸造行业展会"Металлургия.Россия, Литмаш.Россия"参展商目录

展会信息（2025年）：
- URL: https://metallurgy-russia.ru
- 参展商列表: https://metallurgy-russia.ru/ru/exhibition/16/participants
- 展商详情: https://metallurgy-russia.ru/ru/exhibition/16/{exhibitor_id}
- 约 280 家参展商，全部在一页展示

数据字段：
- 公司名称（H1标签）
- 地址（Адрес字段）
- 电话（Мобильный телефон / Телефон字段）
- 网站（Веб сайт字段）

无需登录，完全HTTP可访问
"""

import asyncio
import logging
import re
import urllib.parse
import urllib.request
from typing import List, Set

try:
    from ..models import CompanyInfo
except ImportError:
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from models import CompanyInfo

logger = logging.getLogger(__name__)

BASE_URL = "https://metallurgy-russia.ru"
PARTICIPANTS_URL = "https://metallurgy-russia.ru/ru/exhibition/16/participants"


class MetallurgyRussiaSearcher:
    """
    Metallurgy Russia 展会参展商搜索器
    通过爬取参展商目录，找到所有冶金/铸造相关企业
    """

    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120 Safari/537.36",
            "Accept": "application/json, text/html, */*",
            "Accept-Language": "ru-RU,ru;q=0.9",
            "Referer": BASE_URL,
        }

    async def search(self, keywords: List[str] = None) -> List[CompanyInfo]:
        """
        爬取 metallurgy-russia.ru 全部参展商

        Args:
            keywords: 保留参数（暂不使用，展会参展商已是筛选后的目标客户）

        Returns:
            参展商公司信息列表
        """
        exhibitor_ids = await self._get_all_exhibitor_ids()
        if not exhibitor_ids:
            logger.warning("[MetallurgyRussia] 未找到参展商")
            return []

        logger.info(f"[MetallurgyRussia] 找到 {len(exhibitor_ids)} 家参展商，开始采集详情...")

        # 并发抓详情（限制并发数避免被封）
        semaphore = asyncio.Semaphore(5)
        tasks = [self._scrape_exhibitor(semaphore, eid) for eid in exhibitor_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        companies = []
        for r in results:
            if isinstance(r, Exception):
                continue
            if r:
                companies.append(r)

        logger.info(f"[MetallurgyRussia] 采集完成，共 {len(companies)} 家")
        return companies

    async def _get_all_exhibitor_ids(self) -> List[str]:
        """获取参展商 ID 列表"""
        loop = asyncio.get_event_loop()
        ids = await loop.run_in_executor(None, self._fetch_exhibitor_ids)
        return ids

    def _fetch_exhibitor_ids(self) -> List[str]:
        """HTTP获取参展商ID列表"""
        req = urllib.request.Request(PARTICIPANTS_URL, headers=self.headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8")

        # 提取 /ru/exhibition/16/{id} 格式的链接
        ids = re.findall(r'href="/ru/exhibition/16/(\d+)"', html)
        seen: Set[str] = set()
        unique_ids = []
        for eid in ids:
            if eid not in seen:
                seen.add(eid)
                unique_ids.append(eid)

        logger.info(f"[MetallurgyRussia] 列表页提取到 {len(unique_ids)} 个参展商ID")
        return unique_ids

    async def _scrape_exhibitor(self, semaphore, exhibitor_id: str) -> CompanyInfo:
        """并发抓取单个参展商详情"""
        async with semaphore:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, self._fetch_exhibitor, exhibitor_id)

    def _fetch_exhibitor(self, exhibitor_id: str) -> CompanyInfo:
        """HTTP抓取单个参展商详情页"""
        url = f"{BASE_URL}/ru/exhibition/16/{exhibitor_id}"
        try:
            req = urllib.request.Request(url, headers=self.headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                html = resp.read().decode("utf-8")
        except Exception as e:
            logger.warning(f"[MetallurgyRussia] 抓取 {exhibitor_id} 失败: {e}")
            return None

        # 公司名称：从 H1 提取
        name_match = re.search(r"<h1[^>]*>([^<]+)</h1>", html)
        name = name_match.group(1).strip() if name_match else ""
        if not name or len(name) < 2:
            # Fallback: 从页面标题提取 "NAME - Список участников 2025"
            title_match = re.search(r"<title>([^<]+)</title>", html)
            if title_match:
                name = title_match.group(1).split(" - Список")[0].strip()

        if not name:
            return None

        # 地址
        address = ""
        addr_match = re.search(r"<dt>Адрес:</dt>\s*<dd>([^<]+)</dd>", html)
        if addr_match:
            address = addr_match.group(1).strip()

        # 电话（优先手机，再固定电话）
        phone = ""
        phone_match = re.search(r"<dt>Мобильный телефон:</dt>\s*<dd>([^<]+)</dd>", html)
        if not phone_match:
            phone_match = re.search(r"<dt>Телефон:</dt>\s*<dd>([^<]+)</dd>", html)
        if phone_match:
            phone = phone_match.group(1).strip()
            # 规范化：去除多余空格
            phone = re.sub(r"\s+", " ", phone)

        # 网站
        website = ""
        site_match = re.search(r"<dt>Веб сайт:</dt>\s*<dd>\s*<a[^>]+href='([^']+)'", html)
        if not site_match:
            site_match = re.search(r"<dt>Веб сайт:</dt>\s*<dd>\s*<a[^>]+href=\"([^\"]+)\"", html)
        if site_match:
            website = site_match.group(1).strip()

        return CompanyInfo(
            name=name,
            website=website,
            address=address,
            phone=phone,
            source_channel="metallurgy-russia.ru",
            source_url=url,
            extra={"exhibitor_id": exhibitor_id},
        )

    def search_sync(self, keywords: List[str] = None) -> List[CompanyInfo]:
        """同步封装"""
        return asyncio.run(self.search(keywords))
