"""
run_batch_crawl.py - 批量爬取metaprom 9个分类，写入飞书表格
用法: python run_batch_crawl.py
"""

import asyncio
import logging
import sys
import os
from pathlib import Path

# 添加src到路径
sys.path.insert(0, str(Path(__file__).parent))

from playwright.async_api import async_playwright

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)

# 9个目标分类
CATEGORIES = [
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

END_USER_KW = [
    "завод", "комбинат", "предприяти", "производствен",
    "литейн", "прокатн", "сталелитейн", "чугунолитейн",
    "ферросплав", "электрометаллург", "непрерывн", "мнлз",
    "трубопрокатн", "сортопрокатн", "листопрокатн",
    "энергомаш", "тяжмаш", "уралмаш",
]
TRADER_KW = [
    "торг", "трейд", "тд ", "тд,", "тд.", "скупк",
    "металлоторг", "металл-торг", "опт", "склад", "база",
    "дистрибьют", "поставщик", "снабжен", "сервис",
    "клининг", "транспорт", "логистик", "экспедиц",
    "интер", "онлайн", "маркет", "портал",
]
PRODUCT_KW = [
    "огнеупор", "огнеупорн", "футеровк",
    "валок", "валк", "прокатн валок",
    "кристаллизатор", "мнлз", "непрерывнолит",
    "сталь", "металл", "прокат", "литьё", "отливк",
    "чугун", "ферросплав", "сорт", "лист", "труб",
]


def is_end_user(name: str) -> bool:
    name_lower = name.lower()
    if any(kw in name_lower for kw in TRADER_KW):
        return False
    return any(kw in name_lower for kw in END_USER_KW)


def is_target_product(name: str) -> bool:
    return any(kw in name.lower() for kw in PRODUCT_KW)


async def crawl_category(browser, slug: str, cat_name: str) -> list:
    """串行爬取单个分类"""
    companies = []
    page = await browser.new_page()

    try:
        url = f"https://www.metaprom.ru/companies/{slug}/"
        await page.goto(url, timeout=30000)
        await asyncio.sleep(5)

        links = await page.query_selector_all("a")
        seen = set()

        for link in links:
            href = await link.get_attribute("href")
            text = (await link.inner_text()).strip()

            if not (href and "/companies/id" in href and text and len(text) > 4):
                continue
            if text in seen:
                continue
            if any(s in href for s in ["/offers/", "/products/", "/news/"]):
                continue

            seen.add(text)

            if href.startswith("http"):
                full_url = href
            elif href.startswith("/"):
                full_url = "https://www.metaprom.ru" + href
            else:
                full_url = "https://www.metaprom.ru/" + href

            companies.append({
                "name": text,
                "url": full_url,
                "category": cat_name,
                "slug": slug,
            })

        logger.info(f"[{cat_name}] → {len(companies)} 家公司")

    except Exception as e:
        logger.error(f"[{cat_name}] 失败: {e}")
    finally:
        await page.close()

    return companies


async def main():
    logger.info("=" * 50)
    logger.info("开始批量爬取 metaprom 9个分类")
    logger.info("=" * 50)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        try:
            all_companies = []
            for slug, cat_name in CATEGORIES:
                companies = await crawl_category(browser, slug, cat_name)
                all_companies.extend(companies)
                logger.info(f"  已累计: {len(all_companies)} 家公司")
                await asyncio.sleep(1)  # 礼貌性延迟

            logger.info(f"\n合计提取: {len(all_companies)} 家公司")

        finally:
            await browser.close()

    # 去重
    seen_names = set()
    unique = []
    for c in all_companies:
        norm = " ".join(c["name"].split()).lower()
        if norm not in seen_names:
            seen_names.add(norm)
            unique.append(c)
    all_companies = unique
    logger.info(f"去重后: {len(all_companies)} 家公司")

    # 过滤
    target = [c for c in all_companies if is_end_user(c["name"])]
    related = [c for c in all_companies if is_target_product(c["name"])]
    target_related = [c for c in target if is_target_product(c["name"])]

    logger.info(f"\n--- 过滤结果 ---")
    logger.info(f"终端用户(завод/комбинат): {len(target)} 家")
    logger.info(f"含目标产品关键词: {len(related)} 家")
    logger.info(f"终端用户+目标产品(最高优先): {len(target_related)} 家")

    # 分批写入飞书
    logger.info(f"\n准备写入飞书...")
    batch = target_related[:30]  # 先写最高优先的30条
    logger.info(f"本次写入: {len(batch)} 条")

    for c in batch:
        logger.info(f"  [{c['category']}] {c['name']}")

        # 保存结果到本地JSON（供后续导入飞书）
    output_path = Path(__file__).parent / "crawl_results.json"
    import json
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "all": all_companies,
            "target": target,
            "target_related": target_related,
        }, f, ensure_ascii=False, indent=2)
    logger.info(f"结果已保存: {output_path}")

    # 打印高优先级目标
    if target_related:
        logger.info(f"\n高优先级目标 ({len(target_related)} 家):")
        for c in target_related[:20]:
            logger.info(f"  [{c['category']}] {c['name']}")
            logger.info(f"    {c['url']}")

    logger.info("\n完成！")


if __name__ == "__main__":
    asyncio.run(main())
