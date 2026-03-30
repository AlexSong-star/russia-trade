"""
metaprom 批量爬虫 - 9个分类全量爬取
"""

import asyncio
import re
from typing import List, Dict, Optional
from urllib.parse import urljoin
from playwright.async_api import async_playwright
import logging

logger = logging.getLogger(__name__)


# 9个目标分类
TARGET_CATEGORIES = [
    ("metalloprokat", "黑色金属/钢材"),
    ("pipes", "钢管"),
    ("stainless", "不锈钢"),
    ("non-ferrous", "有色金属"),
    ("metallurgy", "冶金/钢铁"),
    ("metal-equipment", "冶金设备"),
    ("foundry", "铸造"),
    ("cranes", "起重设备"),
    ("power", "电力设备"),
]

# 终端用户关键词（优先保留）
END_USER_KW = [
    "завод", "комбинат", "предприяти", "производствен",
    "литейн", "прокатн", "сталелитейн", "чугунолитейн",
    "ферросплав", "электрометаллург", "непрерывн", "мнлз",
    "трубопрокатн", "сортопрокатн", "листопрокатн",
    "энергомаш", "тяжмаш", "уралмаш",
]

# 无关/贸易商关键词（排除）
TRADER_KW = [
    "торг", "трейд", "тд ", "тд,", "тд.", "скупк",
    "металлоторг", "металл-торг", "опт", "склад", "база",
    "дистрибьют", "поставщик", "снабжен", "сервис",
    "клининг", "транспорт", "логистик", "экспедиц",
    "интер", "онлайн", "маркет", "портал",
]

# 目标产品关键词（耐火材料/轧辊/结晶器）
PRODUCT_KW = [
    "огнеупор", "огнеупорн", "футеровк",
    "валок", "валк", "прокатн валок", "рабоч валок",
    "кристаллизатор", "мнлз", "непрерывнолит",
    "сталь", "металл", "прокат", "литьё", "отливк",
    "чугун", "ферросплав", "сорт", "лист", "труб",
]


def is_end_user(name: str) -> bool:
    """判断是否疑似终端用户（工厂/生产商）"""
    name_lower = name.lower()
    if any(kw in name_lower for kw in TRADER_KW):
        return False
    return any(kw in name_lower for kw in END_USER_KW)


def is_target_product(name: str, desc: str = "") -> bool:
    """判断是否目标产品相关"""
    text = (name + " " + desc).lower()
    return any(kw in text for kw in PRODUCT_KW)


def parse_company_url(href: str) -> Optional[str]:
    """标准化公司URL"""
    if not href:
        return None
    if href.startswith("http"):
        return href
    if href.startswith("/"):
        return "https://www.metaprom.ru" + href
    return "https://www.metaprom.ru/" + href


async def crawl_category(browser, slug: str, cat_name: str) -> List[Dict]:
    """爬取单个分类页"""
    companies = []
    page = await browser.new_page()

    try:
        url = f"https://www.metaprom.ru/companies/{slug}/"
        await page.goto(url, timeout=30000)
        await asyncio.sleep(5)  # 等待JS渲染

        # 提取所有公司链接
        links = await page.query_selector_all("a")
        seen = set()

        for link in links:
            href = await link.get_attribute("href")
            text = (await link.inner_text()).strip()

            # 过滤：公司链接 + 非空名称 + 去重
            if not (href and "/companies/id" in href and text and len(text) > 4):
                continue
            if text in seen:
                continue
            if any(skip in href for skip in ["/offers/", "/products/", "/news/"]):
                continue

            seen.add(text)
            company_url = parse_company_url(href)
            if not company_url:
                continue

            companies.append({
                "name": text,
                "url": company_url,
                "category": cat_name,
                "category_slug": slug,
            })

        logger.info(f"分类 [{cat_name}] 提取到 {len(companies)} 家公司")
    except Exception as e:
        logger.error(f"分类 [{cat_name}] 爬取失败: {e}")
    finally:
        await page.close()

    return companies


async def crawl_all_categories() -> List[Dict]:
    """并发爬取所有9个分类"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        try:
            # 并发爬取9个分类
            tasks = [
                crawl_category(browser, slug, name)
                for slug, name in TARGET_CATEGORIES
            ]
            results = await asyncio.gather(*tasks)

            # 合并结果
            all_companies = []
            for companies in results:
                all_companies.extend(companies)

            logger.info(f"总计提取到 {len(all_companies)} 家公司")
            return all_companies

        finally:
            await browser.close()


def filter_companies(companies: List[Dict]) -> tuple[List[Dict], List[Dict]]:
    """
    过滤公司
    Returns:
        (target_companies, other_companies)  # 高相关 vs 其他
    """
    target = []
    other = []

    for c in companies:
        name = c["name"]

        if not is_end_user(name):
            other.append(c)
            continue

        if is_target_product(name):
            target.append(c)
        else:
            other.append(c)

    return target, other


def deduplicate_by_name(companies: List[Dict]) -> List[Dict]:
    """按公司名去重"""
    seen = set()
    result = []
    for c in companies:
        # 标准化名称（去掉多余空格、大写）
        norm_name = " ".join(c["name"].split()).lower()
        if norm_name not in seen:
            seen.add(norm_name)
            result.append(c)
    return result


async def run_batch_crawl() -> tuple[List[Dict], List[Dict]]:
    """
    批量爬取+过滤主流程
    Returns:
        (target_companies, all_valid_companies)
    """
    # 1. 爬取所有分类
    all_companies = await crawl_all_categories()

    # 2. 去重
    all_companies = deduplicate_by_name(all_companies)
    logger.info(f"去重后剩余 {len(all_companies)} 家公司")

    # 3. 过滤
    target, other = filter_companies(all_companies)
    logger.info(f"高相关(终端用户+目标产品): {len(target)} 家")
    logger.info(f"其他终端用户(不含目标产品): {len(other)} 家")

    return target, all_companies


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

    print("开始批量爬取 metaprom 9个分类...")
    target, all_cos = asyncio.run(run_batch_crawl())

    print(f"\n高相关目标客户: {len(target)} 家")
    for c in target[:10]:
        print(f"  🏭 [{c['category']}] {c['name']}")

    print(f"\n其他终端用户: {len(all_cos) - len(target)} 家")
