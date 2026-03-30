"""
HH.ru 搜索器 - 通过职位搜索找公司
核心方法：通过产品相关职位搜索公司，比按公司名搜索高效 10 倍
例如：搜"Валки прокатные"职位 → 找到所有轧辊相关工厂
"""
import logging
import re
import time
from typing import List

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

try:
    from ..models import CompanyInfo
except Exception:
    import sys as _sys
    _sys.path.insert(0, "/Users/jarvis/.openclaw/workspace/projects/russia-trade/code/russia-trade-searcher/src")
    from models import CompanyInfo

logger = logging.getLogger(__name__)


class HHRU_SEARCHER:
    """
    HH.ru 搜索器 - 通过职位文本找公司

    传统方法: employers?text=关键词 → 只能找到名字含关键词的公司
    正确方法: vacancies?text=关键词 → 找到所有发布相关职位的公司（包括工厂）

    效果对比:
    - "Валки прокатные" employer搜索: 1 家
    - "Валки прокатные" vacancy搜索: 60+ 家（包括 ЕВРАЗ, Северсталь, ОМК 等大厂）
    """

    BASE_URL = "https://api.hh.ru"

    def __init__(self):
        if not REQUESTS_AVAILABLE:
            logger.error("requests 未安装")
            self.session = None
            return

        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120 Safari/537.36",
            "Accept": "application/json",
            "Accept-Language": "ru-RU,ru;q=0.9",
        })

    async def search(self, keywords: List[str]) -> List[CompanyInfo]:
        """
        通过职位关键词搜索公司

        Args:
            keywords: 产品/职位相关关键词列表

        Returns:
            公司信息列表
        """
        if not REQUESTS_AVAILABLE:
            return []

        results = []
        for keyword in keywords:
            logger.info(f"HH.ru 职位搜索: {keyword}")
            companies = await self._search_keyword(keyword)
            results.extend(companies)
            logger.info(f"关键词 '{keyword}' → {len(companies)} 家公司")
            await asyncio.sleep(0.5)

        # 去重
        seen = set()
        unique = []
        for c in results:
            if c.name not in seen:
                seen.add(c.name)
                unique.append(c)
        return unique

    async def _search_keyword(self, keyword: str) -> List[CompanyInfo]:
        """搜索单个关键词，返回公司列表"""
        import asyncio, urllib.parse

        companies = {}
        encoded = urllib.parse.quote(keyword)
        url = f"{self.BASE_URL}/vacancies?text={encoded}&area=113&per_page=50"

        try:
            r = self.session.get(url, timeout=15)
            if r.status_code != 200:
                return []
            data = r.json()
            items = data.get("items", [])

            for vac in items:
                emp = vac.get("employer") or {}
                eid = str(emp.get("id", ""))
                if not eid or eid == "0":
                    continue
                if eid in companies:
                    continue

                # 提取公司信息
                name = emp.get("name", "")
                if not name:
                    continue

                company_info = CompanyInfo(
                    name=name,
                    source_channel="HH.ru",
                    source_url=emp.get("alternate_url", "") or f"https://hh.ru/employer/{eid}",
                    extra={
                        "hh_id": eid,
                        "vacancy_title": vac.get("name", ""),
                        "vacancy_url": vac.get("alternate_url", ""),
                        "area": vac.get("area", {}).get("name", ""),
                        "salary": vac.get("salary"),
                    }
                )
                companies[eid] = company_info

        except Exception as e:
            logger.error(f"HH.ru 搜索失败: {e}")

        return list(companies.values())

    def search_sync(self, keywords: List[str]) -> List[CompanyInfo]:
        """同步版本（供直接调用）"""
        if not REQUESTS_AVAILABLE:
            return []

        results = []
        for keyword in keywords:
            logger.info(f"HH.ru 职位搜索: {keyword}")
            companies = self._search_keyword_sync(keyword)
            results.extend(companies)
            logger.info(f"关键词 '{keyword}' → {len(companies)} 家公司")

        seen = set()
        unique = []
        for c in results:
            if c.name not in seen:
                seen.add(c.name)
                unique.append(c)
        return unique

    def _search_keyword_sync(self, keyword: str) -> List[CompanyInfo]:
        """同步搜索单个关键词"""
        import urllib.parse

        companies = {}
        encoded = urllib.parse.quote(keyword)
        url = f"{self.BASE_URL}/vacancies?text={encoded}&area=113&per_page=50"

        try:
            r = self.session.get(url, timeout=15)
            if r.status_code != 200:
                return []
            data = r.json()
            items = data.get("items", [])

            for vac in items:
                emp = vac.get("employer") or {}
                eid = str(emp.get("id", ""))
                if not eid or eid == "0":
                    continue
                if eid in companies:
                    continue

                name = emp.get("name", "")
                if not name:
                    continue

                company_info = CompanyInfo(
                    name=name,
                    source_channel="HH.ru",
                    source_url=emp.get("alternate_url", "") or f"https://hh.ru/employer/{eid}",
                    extra={
                        "hh_id": eid,
                        "vacancy_title": vac.get("name", ""),
                        "vacancy_url": vac.get("alternate_url", ""),
                        "area": vac.get("area", {}).get("name", ""),
                    }
                )
                companies[eid] = company_info
            time.sleep(0.3)

        except Exception as e:
            logger.error(f"HH.ru 搜索失败: {e}")

        return list(companies.values())

    def get_employer_details(self, hh_id: str) -> dict:
        """获取雇主详细信息（官网、描述、规模）"""
        try:
            r = self.session.get(f"{self.BASE_URL}/employers/{hh_id}", timeout=10)
            if r.status_code == 200:
                emp = r.json()
                return {
                    "name": emp.get("name", ""),
                    "website": emp.get("website", ""),
                    "description": re.sub(r'<[^>]+>', '', emp.get("description", ""))[:300],
                    "industry": emp.get("industry", ""),
                    "area": emp.get("area", {}).get("name", ""),
                    "staff_count": emp.get("staff_count", ""),
                }
        except Exception as e:
            logger.error(f"HH.ru 雇主详情失败: {e}")
        return {}

    def get_procurement_vacancies(self, hh_id: str) -> List[dict]:
        """获取某公司的采购相关职位"""
        try:
            r = self.session.get(
                f"{self.BASE_URL}/vacancies",
                params={"employer_id": hh_id, "per_page": 50},
                timeout=10
            )
            if r.status_code == 200:
                vacs = r.json().get("items", [])
                proc_kw = ["закуп", "снабж", "заказчик", "поставщик", "тендер"]
                return [
                    {"name": v["name"], "url": v.get("alternate_url", "")}
                    for v in vacs
                    if any(k in v.get("name", "").lower() for k in proc_kw)
                ]
        except Exception as e:
            logger.error(f"HH.ru 采购职位查询失败: {e}")
        return []


# 方便直接调用的实例
_hhru = None

def search_companies(keywords: List[str]) -> List[CompanyInfo]:
    """一行调用 HH.ru 搜索"""
    global _hhru
    if _hhru is None:
        _hhru = HHRU_SEARCHER()
    return _hhru.search_sync(keywords)
