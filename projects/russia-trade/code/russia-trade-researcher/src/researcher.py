"""
Russia Trade Researcher - 俄罗斯客户背调工具
多数据源深度调研：metaprom / 官网 / VK / rusprofile / 2GIS
"""

import asyncio
import json
import logging
import os
import random
import re
from typing import Optional, Dict, List

try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

try:
    from playwright_stealth import Stealth
    PLAYWRIGHT_STEALTH_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_STEALTH_AVAILABLE = False

logger = logging.getLogger(__name__)

YANDEX_COOKIE_FILE = "/tmp/yandex_cookies.json"
VK_CHROME_DEBUG_URL = "http://127.0.0.1:9222"  # VK已登录的Chrome调试端口


class RussiaTradeResearcher:
    """
    俄罗斯客户背调器
    多数据源调研，公司详情/联系方式/社媒/工商信息全覆盖
    """

    def __init__(self, timeout: int = 20000):
        self.timeout = timeout

    async def research(self, company_name: str,
                      website: Optional[str] = None,
                      metaprom_url: Optional[str] = None) -> Dict:
        """
        背调入口，统一调度所有数据源
        """
        result = {
            # 联系方式
            "phone": None,
            "phones_all": [],
            "email": None,
            "emails_all": [],
            "address": None,
            "address_yandex": None,
            # 公司信息
            "scale": None,
            "products": [],
            "description": None,
            # 社媒
            "social": {},
            # 工商信息
            "inn": None,
            "ogrn": None,
            "legal_form": None,
            # 招标/采购
            "tenders": None,
            "tender_snippet": None,
            # 财务标注
            "finance": None,
            # 设备/产能
            "equipment": None,
            # 置信度
            "confidence": 0.0,
            "sources": [],
            "notes": [],
        }

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)

            try:
                # ① metaprom（俄罗斯B2B平台）
                if metaprom_url:
                    info = await self._research_metaprom(browser, metaprom_url)
                    self._merge(result, info)

                # ② 公司官网
                if website:
                    info = await self._research_website(browser, website)
                    self._merge(result, info)

                # ③ rusprofile 企业数据库
                info = await self._research_rusprofile(browser, company_name)
                self._merge(result, info)

                # ④ VK 公司主页（需已登录的Chrome调试端口）
                info = await self._research_vk(browser, company_name)
                self._merge(result, info)

                # ⑤ b2b-center 招标
                info = await self._research_b2b(browser, company_name)
                if info.get("tenders"):
                    result["tenders"] = info["tenders"]
                    result["sources"].append("b2b-center")

            finally:
                await browser.close()

        # 计算置信度
        CONFIDENCE_FIELDS = [
            'phone', 'email', 'address', 'inn', 'ogrn',
            'scale', 'description', 'social', 'tenders'
        ]
        filled = sum(1 for f in CONFIDENCE_FIELDS if result.get(f))
        result["confidence"] = min(filled / 7, 1.0)

        return result

    # ─────────────────────────────────────────────────────────
    # 数据源 ① metaprom
    # ─────────────────────────────────────────────────────────

    async def _research_metaprom(self, browser, url: str) -> Dict:
        """从 metaprom.ru B2B平台获取公司基础信息"""
        result = {}
        page = await browser.new_page()
        try:
            await page.goto(url, timeout=self.timeout)
            await asyncio.sleep(2)

            body = await page.inner_text('body')
            lines = [l.strip() for l in body.split('\n') if l.strip()]

            for i, line in enumerate(lines):
                line_clean = line.strip()
                if line_clean == 'Адрес' and i + 1 < len(lines):
                    addr = lines[i + 1].strip()
                    # 过滤掉无意义地址
                    if addr and len(addr) > 5 and 'Продукц' not in addr:
                        result['address'] = addr
                if line_clean == 'Телефон' and i + 1 < len(lines):
                    phone_raw = lines[i + 1].strip()
                    result['phone'] = self._normalize_phone(phone_raw)
                if 'Подробное описание' in line_clean:
                    desc = ' '.join(lines[i:i+15])
                    # 去掉前缀词
                    desc = re.sub(r'^[^А-ЯЁa-z]+', '', desc, count=1)
                    result['description'] = desc.strip()[:300]

            if result:
                result['sources'] = ['metaprom']
                logger.info(f"metaprom OK: {url}")

        except Exception as e:
            logger.warning(f"metaprom失败: {e}")
        finally:
            await page.close()

        return result

    # ─────────────────────────────────────────────────────────
    # 数据源 ② 官网
    # ─────────────────────────────────────────────────────────

    async def _research_website(self, browser, url: str) -> Dict:
        """从公司官网获取联系信息"""
        result = {}
        page = await browser.new_page()
        try:
            await page.goto(url, timeout=self.timeout)
            await asyncio.sleep(3)

            body_text = await page.inner_text('body')

            # 地址
            try:
                await page.goto(url.rstrip('/') + '/contacts', timeout=8000)
                await asyncio.sleep(2)
                contact_text = await page.inner_text('body')
                addr_m = re.search(
                    r'(?:адрес|address|г\.?\s)[^\n]{3,100}',
                    contact_text, re.IGNORECASE
                )
                if addr_m:
                    result['address'] = addr_m.group(0).strip()
            except Exception:
                pass

            # 电话（俄语格式）
            phone_m = re.search(
                r'\+7\s?\d{3}\s?\d{3}\s?\d{2}\s?\d{2}',
                body_text
            )
            if phone_m:
                result['phone'] = self._normalize_phone(phone_m.group(0))

            # 邮箱
            email_m = re.search(
                r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}',
                body_text
            )
            if email_m:
                email = email_m.group(0)
                if not any(p in email.lower() for p in ['gmail', 'yandex.', 'mail.ru']):
                    result['email'] = email

            # 主营产品（关键词匹配）
            product_kw = [
                'металл', 'сталь', 'прокат', 'труб', 'лист', 'огнеупор',
                'валк', 'мнлз', 'кристаллизатор', 'сорт', 'профиль'
            ]
            found = [kw for kw in product_kw if kw in body_text.lower()]
            if found:
                result['products'] = found

            if result.get('address') or result.get('phone') or result.get('email'):
                result['sources'] = ['website']
                logger.info(f"官网 OK: {url}")

        except Exception as e:
            logger.warning(f"官网失败: {e}")
        finally:
            await page.close()

        return result

    # ─────────────────────────────────────────────────────────
    # 数据源 ③ VK 公司主页
    # ─────────────────────────────────────────────────────────

    async def _research_vk(self, browser, company_name: str) -> Dict:
        """
        从 VKontakte 获取公司社媒信息
        通过CDP直连到已登录的Chrome实例，精准搜索并提取公司页信息
        """
        result = {}
        try:
            async with async_playwright() as p:
                vk_browser = await p.chromium.connect_over_cdp(VK_CHROME_DEBUG_URL)
                context = vk_browser.contexts[0]
                page = await context.new_page()

                # 用更具体的搜索词（公司名 + 类型关键词）
                search_terms = [
                    company_name,
                    f"{company_name} компания",
                    f"{company_name} завод",
                ]

                found_url = None
                for term in search_terms:
                    q_encoded = term.replace(' ', '%20')
                    await page.goto(
                        f"https://vk.com/search?c%5Bq%5D={q_encoded}&c%5Bsection%5D=communities",
                        timeout=60000,
                        wait_until="domcontentloaded"
                    )
                    await asyncio.sleep(4)

                    text = await page.inner_text('body')

                    # 找社区链接
                    links = await page.query_selector_all('a[href*="/club"], a[href*="/public"]')
                    for link in links[:5]:
                        href = await link.get_attribute('href')
                        if href and '/login' not in href and '/search' not in href:
                            # 检查链接文本是否包含公司名关键词
                            link_text = (await link.inner_text() or '').lower()
                            if any(kw.lower() in link_text for kw in [company_name.split()[0].lower(), 'kzpo', 'завод', 'компания']):
                                found_url = href if href.startswith('http') else f"https://vk.com{href}"
                                break
                    if found_url:
                        break

                if found_url:
                    await page.goto(found_url, timeout=60000)
                    await asyncio.sleep(5)
                    text = await page.inner_text('body')

                    # 提取粉丝/成员数
                    members = re.findall(r'([0-9][0-9,\s]*)\s*(?:участник|подписчик|друзей)', text)
                    if members:
                        result['social'] = {'vk_followers': members[0].strip()}

                    # 提取VK ID
                    id_m = re.search(r'vk\.com/id(\d+)', text)
                    if id_m:
                        result['social'] = result.get('social', {})
                        result['social']['vk_id'] = id_m.group(1)

                    # 提取主页链接
                    vk_link_m = re.search(r'(https://vk\.com/[^<\s]{3,50})', text)
                    if vk_link_m:
                        result['social'] = result.get('social', {})
                        result['social']['vk'] = vk_link_m.group(1)

                    # 提取公开社区描述（避开UI元素）
                    lines = text.split('\n')
                    relevant = []
                    for i, l in enumerate(lines):
                        l_clean = l.strip()
                        # 取包含公司相关信息且长度适中的行
                        if len(l_clean) > 20 and len(l_clean) < 300:
                            if any(kw in l_clean.lower() for kw in
                                   ['завод', 'компания', 'предприятие', 'производство',
                                    'специальн', 'гражданск', 'казан']):
                                relevant.append(l_clean)
                    if relevant:
                        result['description_vk'] = ' '.join(relevant)[:400]

                await vk_browser.close()

        except Exception as e:
            logger.warning(f"VK获取失败: {e}")

        if result:
            result['sources'] = result.get('sources', []) + ['vk']
            logger.info(f"VK OK: {company_name}")

        return result
        """
        从 VKontakte 获取公司社媒信息（需要JS渲染）
        策略：在 rusprofile 搜索结果中找到公司ID → 拼接VK链接
        """
        result = {}
        page = await browser.new_page()
        try:
            # 先在VK搜索公司
            q_encoded = company_name.replace(' ', '%20')
            await page.goto(
                f"https://vk.com/search?c%5Bq%5D={q_encoded}&c%5Bsection%5D=communities",
                timeout=self.timeout,
                wait_until="domcontentloaded"
            )
            await asyncio.sleep(3)

            body_text = await page.inner_text('body')

            # 检查是否需要登录
            if 'Войдите' in body_text and len(body_text) < 5000:
                result['notes'].append("VK需要登录")
                logger.warning("VK需要登录")
                await page.close()
                return result

            # 提取社区链接
            # VK搜索结果的链接格式: href="/club123" 或 href="/public123"
            community_links = re.findall(
                r'href=\"(/[a-z]+[0-9]+)\"[^>]*>\s*<div[^>]*class=\"[^\"]*avatar[^\"]*\"',
                body_text, re.IGNORECASE
            )

            # 也提取普通链接
            all_links = re.findall(r'href=\"(https://vk\.com/[^\"]+)\"', body_text)
            vk_links = [l for l in all_links if 'vk.com' in l and 'login' not in l]

            # 提取粉丝数
            members = re.findall(r'([0-9\s]+)\s*(?:участник|подписчик|друзей)', body_text)
            if members:
                result['social'] = result.get('social', {})
                result['social']['vk_members'] = members[0].strip()

            # 尝试点击第一个结果进入公司主页
            try:
                first_result = page.locator('a[href*="/club"], a[href*="/public"]').first
                if await first_result.count() > 0:
                    href = await first_result.get_attribute('href')
                    if href and '/login' not in href:
                        full_url = href if href.startswith('http') else f"https://vk.com{href}"
                        await page.goto(full_url, timeout=self.timeout)
                        await asyncio.sleep(3)

                        page_text = await page.inner_text('body')
                        # 检查是否是公司页面
                        if 'О компании' in page_text or 'Описание' in page_text:
                            desc_m = re.search(
                                r'О\s?компании\s*[:\-]?\s*([^\n<]{50,500})',
                                page_text
                            )
                            if desc_m:
                                result['description'] = desc_m.group(1).strip()[:300]

                            # 提取关注者/粉丝数
                            followers = re.findall(
                                r'(?:подписчик|участник)[^0-9]{0,20}([0-9,]+)',
                                page_text
                            )
                            if followers:
                                result['social'] = result.get('social', {})
                                result['social']['vk_followers'] = followers[0].strip()

                            # 提取VK主页链接
                            vk_homepage = re.search(
                                r'(https://vk\.com/[^<\s]{3,50})',
                                page_text
                            )
                            if vk_homepage:
                                result['social'] = result.get('social', {})
                                result['social']['vk'] = vk_homepage.group(1)

            except Exception as e:
                logger.warning(f"VK详情页获取失败: {e}")

            if result.get('social') or result.get('description'):
                result['sources'] = result.get('sources', []) + ['vk']
                logger.info(f"VK OK: {company_name}")

        except Exception as e:
            logger.warning(f"VK搜索失败: {e}")
        finally:
            await page.close()

        return result

    # ─────────────────────────────────────────────────────────
    # 数据源 ④ rusprofile 企业工商数据库
    # ─────────────────────────────────────────────────────────

    async def _research_rusprofile(self, browser, company_name: str) -> Dict:
        """
        从 rusprofile.ru 获取企业工商信息
        策略：用Playwright点击搜索结果的第一个公司链接，进入详情页提取数据
        """
        result = {}
        page = await browser.new_page()
        try:
            q_encoded = company_name.replace(' ', '%20')
            await page.goto(
                f"https://www.rusprofile.ru/search?query={q_encoded}&type=ul",
                timeout=self.timeout,
                wait_until="domcontentloaded"
            )
            await asyncio.sleep(3)

            # rusprofile 搜索结果通过 JS 渲染，点击公司名进入详情页
            # 找第一个可点击的公司名元素
            try:
                # rusprofile 的公司名通常在搜索结果里，带有 /id/ 链接
                # 用 Playwright 找第一个指向 /id/ 的链接
                first_link = page.locator('a[href^="/id/"]').first
                if await first_link.count() > 0:
                    href = await first_link.get_attribute('href')
                    if href:
                        detail_url = f"https://www.rusprofile.ru{href}"
                        await page.goto(detail_url, timeout=self.timeout)
                        await asyncio.sleep(3)
            except Exception as e:
                logger.warning(f"rusprofile点击失败: {e}")

            page_text = await page.inner_text('body')

            # 提取ОГРН（13位数字）
            ogrn_m = re.search(r'ОГРН[^\d]*(\d{13})', page_text)
            if ogrn_m:
                result['ogrn'] = ogrn_m.group(1)

            # 提取ИНН（10位数字）
            inn_m = re.search(r'ИНН[^\d]*(\d{10})', page_text)
            if inn_m:
                result['inn'] = inn_m.group(1)

            # 提取公司描述
            desc_m = re.search(
                r'Главное\s+о\s+компании\s+за\s+1\s+минуту\s*([^\n<]{50,600})',
                page_text, re.DOTALL
            )
            if desc_m:
                raw_desc = re.sub(r'\s+', ' ', desc_m.group(1)).strip()
                result['description'] = raw_desc[:300]
                # 从描述中提取城市
                city_m = re.search(
                    r'в\s+(Казани|Москве[и]?|Санкт-Петербург[еу]|[А-ЯЁ][a-яё]{2,}(?:\s+[А-ЯЁ][a-яё]+){0,2})',
                    raw_desc
                )
                if city_m:
                    result['address'] = city_m.group(1).strip()

            # 规模
            if 'микропредприятие' in page_text:
                result['scale'] = 'микропредприятие'
            elif 'малого' in page_text:
                result['scale'] = 'малое предприятие'
            elif 'среднего' in page_text:
                result['scale'] = 'среднее предприятие'

            if result.get('ogrn') or result.get('inn'):
                result['sources'] = ['rusprofile']
                logger.info(f"rusprofile OK: {company_name}")

        except Exception as e:
            logger.warning(f"rusprofile失败: {e}")
        finally:
            await page.close()

        return result

    # ─────────────────────────────────────────────────────────
    # 数据源 ⑤ b2b-center 招标平台
    # ─────────────────────────────────────────────────────────

    async def _research_b2b(self, browser, company_name: str) -> Dict:
        """检查公司招标历史"""
        result = {}
        page = await browser.new_page()
        try:
            q_encoded = company_name.replace(' ', '%20')
            await page.goto(
                f"https://www.b2b-center.ru/?q={q_encoded}",
                timeout=self.timeout,
                wait_until="domcontentloaded"
            )
            await asyncio.sleep(3)

            body = await page.inner_text('body')

            if 'заявк' in body.lower() or 'тендер' in body.lower() or 'предложен' in body.lower():
                result['tenders'] = "有招标记录（见b2b-center）"
                # 提取相关片段
                for kw in ['тендер', 'закуп', 'поставк']:
                    idx = body.lower().find(kw)
                    if idx >= 0:
                        snippet = re.sub(r'\s+', ' ', body[max(0, idx-20):idx+100]).strip()
                        if len(snippet) > 15:
                            result['tender_snippet'] = snippet[:200]
                            break
            else:
                result['tenders'] = "无招标记录"

            logger.info(f"b2b-center查询完成: {company_name}")

        except Exception as e:
            logger.warning(f"b2b-center失败: {e}")
        finally:
            await page.close()

        return result

    # ─────────────────────────────────────────────────────────
    # 工具方法
    # ─────────────────────────────────────────────────────────

    def _normalize_phone(self, phone_str: str) -> str:
        """统一电话格式"""
        # 去掉所有空格和-，保留+和数字
        digits = re.sub(r'[^\d+]', '', phone_str)
        if digits.startswith('8') and len(digits) == 11:
            digits = '+7' + digits[1:]
        return digits

    def _merge(self, target: Dict, source: Dict):
        """将 source 数据合并到 target（不覆盖已有字段）"""
        for k, v in source.items():
            if k in ('sources', 'notes') or v is None:
                continue
            if k == 'phones_all':
                existing = target.get('phones_all', [])
                if isinstance(v, list):
                    target['phones_all'] = list(dict.fromkeys(existing + v))
                elif v:
                    target['phones_all'] = list(dict.fromkeys(existing + [v]))
            elif k == 'emails_all':
                existing = target.get('emails_all', [])
                if isinstance(v, list):
                    target['emails_all'] = list(dict.fromkeys(existing + v))
                elif v:
                    target['emails_all'] = list(dict.fromkeys(existing + [v]))
            elif k == 'social':
                existing = target.get('social', {})
                if isinstance(v, dict):
                    merged = dict(existing)
                    merged.update(v)
                    target['social'] = merged
            elif k == 'products':
                existing = target.get('products', [])
                if isinstance(v, list):
                    target['products'] = list(dict.fromkeys(existing + v))
            elif not target.get(k):
                target[k] = v

        # 合并 sources
        if source.get('sources'):
            target['sources'] = target.get('sources', []) + source['sources']

        # 追加 notes
        if source.get('notes'):
            target['notes'] = target.get('notes', []) + source['notes']

    # ─────────────────────────────────────────────────────────
    # 同步封装
    # ─────────────────────────────────────────────────────────

    def research_sync(self, company_name: str,
                     website: Optional[str] = None,
                     metaprom_url: Optional[str] = None) -> Dict:
        """同步封装"""
        return asyncio.run(self.research(company_name, website, metaprom_url))


if __name__ == "__main__":
    researcher = RussiaTradeResearcher()

    tc = {
        "company_name": "КЗПО",
        "website": "https://kzpo.ru",
        "metaprom_url": "https://metaprom.ru/companies/id55122"
    }

    print(f"\n=== 背调: {tc['company_name']} ===")
    result = researcher.research_sync(**tc)
    for k, v in result.items():
        if v:
            print(f"  {k}: {v}")
    print(f"\n置信度: {result['confidence']:.2f}")
