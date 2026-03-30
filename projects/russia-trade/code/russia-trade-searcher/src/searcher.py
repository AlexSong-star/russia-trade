"""
Russia Trade Searcher - 俄罗斯客户搜索工具集
支持 B2B投标(b2b-center.ru)、黄页(metaprom.ru)、Yandex 三个渠道
"""

import asyncio
import logging
from typing import List, Dict, Optional

from .models import CompanyInfo
from .channels.b2b_center import B2BCenterSearcher
from .channels.metaprom import MetapromSearcher
from .channels.yandex import YandexSearcher

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RussiaTradeSearcher:
    """
    俄罗斯客户搜索器
    并行从三个渠道搜索客户信息
    """

    # 搜索关键词组合
    PRODUCT_KEYWORDS = [
        "Огнеупоры для МНЛЗ",       # 耐火材料+连铸机
        "Валки прокатные",            # 轧辊
        "Кристаллизатор для МНЛЗ",   # 结晶器
        "Поставщик огнеупоров",       # 耐火材料供应商
        "Огнеупорные материалы",     # 耐火材料
        "МНЛЗ запчасти",             # 连铸机配件
    ]

    def __init__(self):
        self.b2b = B2BCenterSearcher()
        self.metaprom = MetapromSearcher()
        self.yandex = YandexSearcher()

    async def search_channel(self, channel: str, keywords: List[str]) -> List[CompanyInfo]:
        """
        从单个渠道搜索

        Args:
            channel: 渠道标识 ("b2b_center", "metaprom", "yandex")
            keywords: 关键词列表

        Returns:
            公司信息列表
        """
        logger.info(f"开始搜索渠道: {channel}, 关键词数: {len(keywords)}")

        try:
            if channel == "b2b_center":
                return await self.b2b.search(keywords)
            elif channel == "metaprom":
                return await self.metaprom.search(keywords)
            elif channel == "yandex":
                return await self.yandex.search(keywords)
            else:
                logger.warning(f"未知渠道: {channel}")
                return []
        except Exception as e:
            logger.error(f"渠道 {channel} 搜索失败: {e}")
            return []

    async def search_all(self, keywords: Optional[List[str]] = None,
                         channels: Optional[List[str]] = None) -> List[CompanyInfo]:
        """
        并行从所有渠道搜索

        Args:
            keywords: 关键词列表，默认使用 PRODUCT_KEYWORDS
            channels: 要搜索的渠道列表，默认 ["b2b_center", "metaprom", "yandex"]

        Returns:
            所有渠道搜索结果（去重后）
        """
        if keywords is None:
            keywords = self.PRODUCT_KEYWORDS
        if channels is None:
            channels = ["b2b_center", "metaprom", "yandex"]

        logger.info(f"开始全面搜索，渠道: {channels}, 关键词: {keywords}")

        tasks = [self.search_channel(ch, keywords) for ch in channels]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_companies = []
        for i, res in enumerate(results):
            if isinstance(res, Exception):
                logger.error(f"渠道 {channels[i]} 异常: {res}")
                continue
            all_companies.extend(res)
            logger.info(f"渠道 {channels[i]} 获取 {len(res)} 条结果")

        unique = self._deduplicate(all_companies)
        logger.info(f"去重后共 {len(unique)} 家客户")

        return unique

    def _deduplicate(self, companies: List[CompanyInfo]) -> List[CompanyInfo]:
        """按公司名称去重"""
        seen = set()
        unique = []
        for c in companies:
            name = c.name.strip().lower()
            if name and name not in seen:
                seen.add(name)
                unique.append(c)
        return unique

    def search_b2b_center(self, keywords: Optional[List[str]] = None) -> List[CompanyInfo]:
        """同步接口：只搜索 B2B Center"""
        if keywords is None:
            keywords = self.PRODUCT_KEYWORDS
        return asyncio.run(self.b2b.search(keywords))

    def search_metaprom(self, keywords: Optional[List[str]] = None) -> List[CompanyInfo]:
        """同步接口：只搜索 Metaprom"""
        if keywords is None:
            keywords = self.PRODUCT_KEYWORDS
        return asyncio.run(self.metaprom.search(keywords))

    def search_yandex(self, keywords: Optional[List[str]] = None) -> List[CompanyInfo]:
        """同步接口：只搜索 Yandex"""
        if keywords is None:
            keywords = self.PRODUCT_KEYWORDS
        return asyncio.run(self.yandex.search(keywords))


if __name__ == "__main__":
    import json

    # 测试
    searcher = RussiaTradeSearcher()

    print("测试 B2B Center 搜索（同步接口）...")
    results = searcher.search_b2b_center(keywords=["Огнеупоры для МНЛЗ"])
    print(f"B2B Center 获取到 {len(results)} 条结果")
    for c in results[:3]:
        print(f"  - {c.name} | {c.website} | {c.source_channel}")

    print("\n测试 Metaprom 搜索（同步接口）...")
    results = searcher.search_metaprom(keywords=["Валки прокатные"])
    print(f"Metaprom 获取到 {len(results)} 条结果")
    for c in results[:3]:
        print(f"  - {c.name} | {c.website} | {c.source_channel}")
