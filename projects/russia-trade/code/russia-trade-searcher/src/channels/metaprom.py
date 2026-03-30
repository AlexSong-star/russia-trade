"""
Metaprom 搜索器 (metaprom.ru)
俄罗斯工业B2B黄页，企业目录型
公司链接格式：/companies/id<数字>
"""

import asyncio
import logging
import re
from typing import List, Optional, Set
from urllib.parse import urljoin

try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

from models import CompanyInfo

logger = logging.getLogger(__name__)


# 与钢铁/冶金相关的供应商分类
RELEVANT_CATEGORIES = [
    "equipment-manufacturing",   # 设备制造
    "metal-construction",        # 金属结构
    "details",                  # 机械零件
    "metal-equipment",          # 冶金设备
    "stanki",                  # 机床
    "pumps-equipment",          # 泵设备
    "valves",                  # 阀门
    "electro",                  # 电气设备
    "crush",                    # 粉碎设备
    "welding-equipment",        # 焊接设备
    "rawmaterials",             # 原材料
    "metalloprokat",           # 黑色金属
    "stainless",               # 不锈钢
    "pipes",                   # 管道
]

SEARCH_KEYWORDS = [
    "огнеупоры",             # 耐火材料
    "МНЛЗ",                  # 连铸机
    "прокатные валки",       # 轧辊
    "металлургическое",      # 冶金
]


class MetapromSearcher:
    """Metaprom (metaprom.ru) 搜索器"""

    BASE_URL = "https://www.metaprom.ru"
    COMPANIES_URL = "https://www.metaprom.ru/companies"

    async def search(self, keywords: List[str]) -> List[CompanyInfo]:
        """
        搜索 Metaprom 公司目录

        Args:
            keywords: 俄语关键词列表

        Returns:
            公司信息列表
        """
        if not PLAYWRIGHT_AVAILABLE:
            logger.error("playwright 未安装")
            return []

        all_results = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                for keyword in keywords:
                    logger.info(f"Metaprom 搜索关键词: {keyword}")
                    results = await self._search_by_keyword(browser, keyword)
                    all_results.extend(results)
                    logger.info(f"关键词 '{keyword}' 获取 {len(results)} 条结果")
                    await asyncio.sleep(1)
            finally:
                await browser.close()

        return all_results

    async def _search_by_keyword(self, browser, keyword: str) -> List[CompanyInfo]:
        """通过关键词搜索公司"""
        page = await browser.new_page()
        results = []

        try:
            # 先加载主页
            await page.goto(self.BASE_URL, timeout=30000)
            await asyncio.sleep(3)

            # 找到搜索框并输入
            input_el = await page.query_selector('input.search__input')
            if input_el:
                await input_el.click()
                await asyncio.sleep(0.5)
                await input_el.fill(keyword)
                await asyncio.sleep(1)
                # 按回车触发搜索（避免按钮跳转到注册页）
                await page.keyboard.press("Enter")
                # 等待搜索结果加载
                await asyncio.sleep(4)

                results = await self._extract_companies_from_page(page)

        except Exception as e:
            logger.error(f"关键词搜索失败: {e}")
        finally:
            await page.close()

        return results

    async def scrape_all_categories(self, max_per_category: int = 30) -> List[CompanyInfo]:
        """
        爬取所有相关分类目录下的公司

        Args:
            max_per_category: 每个分类最多爬取公司数

        Returns:
            公司信息列表
        """
        if not PLAYWRIGHT_AVAILABLE:
            logger.error("playwright 未安装")
            return []

        all_results = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                for category in RELEVANT_CATEGORIES:
                    url = f"{self.COMPANIES_URL}/{category}/"
                    logger.info(f"爬取分类: {category}")
                    try:
                        companies = await self._scrape_category(browser, url, max_per_category)
                        all_results.extend(companies)
                        logger.info(f"分类 {category} 获取 {len(companies)} 条结果")
                    except Exception as e:
                        logger.error(f"分类 {category} 爬取失败: {e}")
                    await asyncio.sleep(1)
            finally:
                await browser.close()

        return all_results

    async def _scrape_category(self, browser, url: str, max_companies: int) -> List[CompanyInfo]:
        """爬取单个分类目录"""
        page = await browser.new_page()
        results = []

        try:
            await page.goto(url, timeout=30000)
            await asyncio.sleep(3)

            # 提取公司
            companies = await self._extract_companies_from_page(page, max_companies)
            results.extend(companies)

            # 翻页（最多翻3页）
            for _ in range(3):
                next_btn = await page.query_selector(
                    'a.next, a[rel="next"], .pagination a:has-text("→"), '
                    'a.pagination__next, a[href*="page="]'
                )
                if not next_btn:
                    break

                await next_btn.click()
                await asyncio.sleep(2)

                more = await self._extract_companies_from_page(page, max_companies - len(results))
                results.extend(more)

                if len(results) >= max_companies:
                    break

        except Exception as e:
            logger.error(f"分类页面加载失败: {e}")
        finally:
            await page.close()

        return results[:max_companies]

    async def _extract_companies_from_page(self, page, max_count: int = 50) -> List[CompanyInfo]:
        """从页面提取公司信息"""
        results = []

        # 通过 /companies/id<数字> URL 模式提取公司
        company_links = await page.query_selector_all('a[href*="/companies/id"]')
        seen_ids: Set[str] = set()

        for link in company_links:
            try:
                href = await link.get_attribute('href')
                if not href or href in seen_ids:
                    continue

                # 提取公司 ID
                match = re.search(r'/companies/id(\d+)', href)
                if not match:
                    continue

                company_id = match.group(1)
                if company_id in seen_ids:
                    continue
                seen_ids.add(company_id)

                name = await link.inner_text()
                name = name.strip()
                if not name or len(name) < 3:
                    continue

                results.append(CompanyInfo(
                    name=name,
                    website=urljoin(self.BASE_URL, href),
                    source_channel="metaprom",
                    extra={"company_id": company_id}
                ))

                if len(results) >= max_count:
                    break

            except Exception:
                continue

        logger.info(f"从页面提取到 {len(results)} 家公司")
        return results

    async def enrich_company(self, browser, company_url: str) -> Optional[CompanyInfo]:
        """
        访问公司详情页，补充地址、电话、邮箱等信息

        Args:
            browser: Playwright browser 实例
            company_url: 公司页面URL

        Returns:
            补充了详细信息的 CompanyInfo
        """
        page = await browser.new_page()
        try:
            await page.goto(company_url, timeout=30000)
            await asyncio.sleep(2)

            # 提取详情
            body = await page.inner_text('body')

            # 地址
            address = None
            addr_match = re.search(r'(?:адрес|address|location)[:\s]+([^\n]{5,100})', body, re.IGNORECASE)
            if addr_match:
                address = addr_match.group(1).strip()

            # 电话
            phone = None
            phone_match = re.search(
                r'(?:\+7|8|тел[:\s]?|phone[:\s]?)[\s]*([+\d\s\-\(\)]{7,20})',
                body, re.IGNORECASE
            )
            if phone_match:
                phone = phone_match.group(1).strip()

            # 邮箱
            email = None
            email_match = re.search(r'[\w\.\-]+@[\w\.\-]+\.\w+', body)
            if email_match:
                email = email_match.group(0).lower()

            return CompanyInfo(
                name="",
                address=address,
                phone=phone,
                email=email,
                source_channel="metaprom"
            )

        except Exception as e:
            logger.error(f"访问公司详情页失败: {e}")
            return None
        finally:
            await page.close()
