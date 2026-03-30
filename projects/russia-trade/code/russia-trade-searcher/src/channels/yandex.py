"""
Yandex 搜索器 (yandex.ru)
俄罗斯搜索引擎，配合 Playwright 自动化搜索
"""

import asyncio
import logging
import re
from typing import List, Optional
from urllib.parse import quote

try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

from ..models import CompanyInfo

logger = logging.getLogger(__name__)


class YandexSearcher:
    """Yandex 搜索器 - 使用 Playwright 自动化"""

    BASE_URL = "https://yandex.ru"

    async def search(self, keywords: List[str]) -> List[CompanyInfo]:
        """
        搜索 Yandex

        Args:
            keywords: 俄语关键词列表

        Returns:
            公司信息列表
        """
        all_results = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                for keyword in keywords:
                    logger.info(f"Yandex 搜索: {keyword}")
                    results = await self._search_keyword(browser, keyword)
                    all_results.extend(results)
                    logger.info(f"关键词 '{keyword}' 获取 {len(results)} 条结果")
                    await asyncio.sleep(2)
            finally:
                await browser.close()

        return all_results

    async def _search_keyword(self, browser, keyword: str) -> List[CompanyInfo]:
        """搜索单个关键词"""
        search_url = f"{self.BASE_URL}/search/?text={quote(keyword)}&lr=105"

        page = await browser.new_page()
        results = []

        try:
            await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3)

            try:
                await page.wait_for_selector(".serp-items, .serp-item, .OrganicTitle", timeout=10000)
            except Exception:
                pass

            organic_items = await page.query_selector_all(".OrganicTitle, .serp-item .OrganicTitle, .b-serp-item")

            for item in organic_items[:15]:
                try:
                    company = await self._parse_organic_result(item, keyword)
                    if company and company.name:
                        results.append(company)
                except Exception as e:
                    logger.debug(f"解析搜索结果失败: {e}")
                    continue

            try:
                kp = await page.query_selector(".KnowledgePanel, .b-knowledge-panel")
                if kp:
                    company_name_elem = await kp.query_selector(".EntityName, .c-entity__title")
                    if company_name_elem:
                        name = await company_name_elem.inner_text()
                        results.append(CompanyInfo(
                            name=name.strip(),
                            source_channel="yandex",
                            products=[keyword]
                        ))
            except Exception:
                pass

        except Exception as e:
            logger.error(f"Yandex 页面加载失败: {e}")
        finally:
            await page.close()

        return results

    async def _parse_organic_result(self, item, keyword: str) -> Optional[CompanyInfo]:
        """解析 Yandex 有机搜索结果"""
        try:
            title_elem = await item.query_selector("a, .Link, .OrganicTitle")
            if not title_elem:
                return None

            title = await title_elem.inner_text()
            href = await title_elem.get_attribute("href")

            if not title or not href or "yandex" in href:
                return None

            name = title.strip()

            return CompanyInfo(
                name=name,
                website=href if href.startswith("http") else None,
                source_channel="yandex",
                source_url=href,
                products=[keyword]
            )
        except Exception as e:
            logger.debug(f"解析有机结果失败: {e}")
            return None

    async def search_maps(self, keywords: List[str]) -> List[CompanyInfo]:
        """搜索 Yandex Maps"""
        all_results = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                for keyword in keywords:
                    logger.info(f"Yandex Maps 搜索: {keyword}")
                    results = await self._search_maps_keyword(browser, keyword)
                    all_results.extend(results)
                    await asyncio.sleep(2)
            finally:
                await browser.close()

        return all_results

    async def _search_maps_keyword(self, browser, keyword: str) -> List[CompanyInfo]:
        """在 Yandex Maps 上搜索"""
        maps_url = f"https://yandex.ru/maps/?text={quote(keyword)}&ll=37.617644,55.755819&z=10"

        page = await browser.new_page()
        results = []

        try:
            await page.goto(maps_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3)

            try:
                await page.wait_for_selector(".card-feature, .business-card, .map-card", timeout=10000)
            except Exception:
                pass

            cards = await page.query_selector_all(".card-feature, .business-card")

            for card in cards[:10]:
                try:
                    name_elem = await card.query_selector(".card-feature__title, .business-card__title, .title")
                    name = await name_elem.inner_text() if name_elem else None

                    addr_elem = await card.query_selector(".address, .card-feature__address")
                    address = await addr_elem.inner_text() if addr_elem else None

                    phone_elem = await card.query_selector(".phone, .card-feature__phone")
                    phone = await phone_elem.inner_text() if phone_elem else None

                    if name:
                        results.append(CompanyInfo(
                            name=name.strip(),
                            address=address.strip() if address else None,
                            phone=phone.strip() if phone else None,
                            source_channel="yandex_maps",
                            products=[keyword]
                        ))
                except Exception:
                    continue

        except Exception as e:
            logger.error(f"Yandex Maps 加载失败: {e}")
        finally:
            await page.close()

        return results
