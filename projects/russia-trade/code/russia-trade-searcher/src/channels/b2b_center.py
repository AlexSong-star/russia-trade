"""
B2B Center 搜索器 (b2b-center.ru)
俄罗斯最大的B2B投标平台，有实际采购需求
优先级最高

注意：b2b-center.ru 有较强的反爬机制，可能需要验证码或IP验证
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


class B2BCenterSearcher:
    """B2B Center (b2b-center.ru) 搜索器"""

    BASE_URL = "https://www.b2b-center.ru"

    async def search(self, keywords: List[str]) -> List[CompanyInfo]:
        """
        搜索 B2B Center

        Args:
            keywords: 俄语关键词列表

        Returns:
            公司信息列表
        """
        if not PLAYWRIGHT_AVAILABLE:
            logger.error("playwright 未安装，请运行: pip install playwright && playwright install chromium")
            return []

        all_results = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=['--disable-blink-features=AutomationControlled']
            )
            try:
                for keyword in keywords:
                    logger.info(f"B2B Center 搜索: {keyword}")
                    results = await self._search_keyword(browser, keyword)
                    all_results.extend(results)
                    logger.info(f"关键词 '{keyword}' 获取 {len(results)} 条结果")
                    await asyncio.sleep(1)
            finally:
                await browser.close()

        return all_results

    async def _search_keyword(self, browser, keyword: str) -> List[CompanyInfo]:
        """搜索单个关键词"""
        search_url = f"{self.BASE_URL}/?q={quote(keyword)}"

        page = await browser.new_page()
        results = []

        try:
            await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2)

            # 检测是否被拦截
            if await self._is_blocked(page):
                logger.warning("B2B Center 返回了人机验证页面，跳过此关键词")
                return []

            # 尝试等待搜索结果
            try:
                await page.wait_for_selector(
                    ".company-list__item, .b2b-company-card, table.requests",
                    timeout=10000
                )
            except Exception:
                pass

            # 提取公司信息
            companies = await page.query_selector_all(
                ".company-item, .company-card, .b2b-company, tr.company, article.company"
            )

            for company_elem in companies[:20]:
                try:
                    company = await self._parse_company_element(company_elem)
                    if company and company.name:
                        results.append(company)
                except Exception as e:
                    logger.debug(f"解析公司元素失败: {e}")
                    continue

        except Exception as e:
            logger.error(f"搜索页面加载失败: {e}")

        finally:
            await page.close()

        return results

    async def _is_blocked(self, page) -> bool:
        """检测是否被反爬拦截"""
        try:
            title = await page.title()
            url = page.url
            content = await page.content()

            # 检测验证码/拦截页面特征
            blocked_indicators = [
                "капча", "captcha", "robot", "access denied",
                "проверка", "пожалуйста подождите", "проверка безопасности"
            ]
            content_lower = content.lower()

            if any(ind in content_lower for ind in blocked_indicators):
                return True
            if "b2b-center" not in url and len(content) < 5000:
                return True

            return False
        except Exception:
            return False

    async def _parse_company_element(self, elem) -> Optional[CompanyInfo]:
        """从页面元素解析公司信息"""
        try:
            # 公司名称
            name_elem = await elem.query_selector(
                "a.company-name, .company__name a, .title a, h3 a, a[href*='/company/']"
            )
            name = await name_elem.inner_text() if name_elem else None
            if not name:
                name_elem = await elem.query_selector("a")
                name = await name_elem.inner_text() if name_elem else None
            name = name.strip() if name else None

            if not name:
                return None

            # 官网
            website_elem = await elem.query_selector(
                "a.website, a[href*='://']:not([href*='b2b-center'])"
            )
            website = None
            if website_elem:
                href = await website_elem.get_attribute("href")
                if href and "://" in href and "b2b-center" not in href:
                    website = href

            # 地址
            address_elem = await elem.query_selector(
                ".address, .company__address, .location"
            )
            address = await address_elem.inner_text() if address_elem else None
            if address:
                address = address.strip()

            # 电话
            phone_elem = await elem.query_selector(".phone, .tel, [href*='tel:']")
            phone = await phone_elem.inner_text() if phone_elem else None
            if phone:
                phone = re.sub(r'\s+', ' ', phone.strip())

            # 邮箱
            email_elem = await elem.query_selector(".email, [href*='mailto:']")
            email = None
            if email_elem:
                href = await email_elem.get_attribute("href")
                if href and href.startswith("mailto:"):
                    email = href.replace("mailto:", "")
                else:
                    email = await email_elem.inner_text()
            if email:
                email = email.strip()

            return CompanyInfo(
                name=name,
                website=website,
                address=address,
                phone=phone,
                email=email,
                source_channel="b2b-center",
                products=[keyword for keyword in []]
            )
        except Exception as e:
            logger.debug(f"解析公司元素详情失败: {e}")
            return None

    async def search_tenders(self, keywords: List[str]) -> List[dict]:
        """搜索招标信息"""
        if not PLAYWRIGHT_AVAILABLE:
            return []

        all_tenders = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                for keyword in keywords:
                    tenders = await self._search_tenders_keyword(browser, keyword)
                    all_tenders.extend(tenders)
                    await asyncio.sleep(1)
            finally:
                await browser.close()

        return all_tenders

    async def _search_tenders_keyword(self, browser, keyword: str) -> List[dict]:
        """搜索单个关键词的招标信息"""
        search_url = f"{self.BASE_URL}/market/requests/?q={quote(keyword)}"

        page = await browser.new_page()
        tenders = []

        try:
            await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2)

            tender_rows = await page.query_selector_all(
                "table.requests tr, .tender-item, .request-item"
            )

            for row in tender_rows[:15]:
                try:
                    title_elem = await row.query_selector(".title a, .request__title a, h3 a")
                    title = await title_elem.inner_text() if title_elem else None

                    company_elem = await row.query_selector(".company-name, .supplier, .request__company")
                    company = await company_elem.inner_text() if company_elem else None

                    deadline_elem = await row.query_selector(".deadline, .date, .request__date")
                    deadline = await deadline_elem.inner_text() if deadline_elem else None

                    url_elem = await row.query_selector("a[href*='/request/']")
                    url = await url_elem.get_attribute("href") if url_elem else None
                    if url and not url.startswith("http"):
                        url = f"{self.BASE_URL}{url}"

                    if title:
                        tenders.append({
                            "title": title.strip(),
                            "company": company.strip() if company else None,
                            "deadline": deadline.strip() if deadline else None,
                            "url": url,
                            "keyword": keyword
                        })
                except Exception:
                    continue

        except Exception as e:
            logger.error(f"招标搜索失败: {e}")
        finally:
            await page.close()

        return tenders
