"""测试联系人查找器"""
import asyncio
import json
import sys
import os
from datetime import datetime
from pathlib import Path

sys.path.insert(0, "src")
from contacts_finder import RussiaTradeContacts

# 测试结果保存目录
RESULTS_DIR = Path(__file__).parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)


def save_results(name: str, data, extra: dict = None):
    """保存测试结果到 JSON 文件"""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = RESULTS_DIR / f"{name}_{ts}.json"

    output = {
        "test_name": name,
        "timestamp": datetime.now().isoformat(),
        "results": data,
    }
    if extra:
        output["extra"] = extra

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"✅ 结果已保存: {filepath}")
    return filepath


# ─────────────────────────────────────────
# 测试用例
# ─────────────────────────────────────────

async def test_email_guessing():
    """测试邮箱格式猜测"""
    finder = RussiaTradeContacts()
    results = await finder._guess_email_patterns("Северсталь", "severstal.ru")
    print(f"Email guesses: {len(results)}")
    for r in results:
        print(f"  {r['email']} | conf={r['confidence']}")
    save_results("email_guess", results, {"company": "Северсталь", "domain": "severstal.ru"})
    return results


async def test_title_translation():
    """测试职位翻译"""
    finder = RussiaTradeContacts()
    titles = [
        "Начальник отдела закупок",
        "Менеджер по закупкам",
        "Директор по закупкам",
        "Генеральный директор",
        "Коммерческий директор",
        "Ведущий специалист по закупкам",
    ]
    results = []
    print("\nTitle translations:")
    for t in titles:
        cn = finder._translate_title(t)
        print(f"  {t} -> {cn}")
        results.append({"original": t, "translated": cn})
    save_results("title_translation", results)
    return results


async def test_transliterate():
    """测试俄语转拉丁"""
    finder = RussiaTradeContacts()
    names = ["Иван", "Петров", "Северсталь", "Новолипецк"]
    results = []
    print("\nTransliteration:")
    for n in names:
        latin = finder._transliterate(n)
        print(f"  {n} -> {latin}")
        results.append({"cyrillic": n, "latin": latin})
    save_results("transliteration", results)
    return results


async def test_email_guess_two_part_name():
    """测试双字名字（名+姓）"""
    finder = RussiaTradeContacts()
    results = await finder._guess_email_patterns(
        "Объединенная металлургическая компания", "omk.ru"
    )
    print(f"\nTwo-part company guesses: {len(results)}")
    for r in results:
        print(f"  {r['email']}")
    save_results("email_guess_two_part", results, {"company": "ОМК", "domain": "omk.ru"})
    return results


async def test_find_contacts_real():
    """真实网站测试"""
    finder = RussiaTradeContacts()
    results = await finder.find_contacts(
        company_name="ТМК",
        website="https://tmk-group.ru",
        domain="tmk.ru",
    )
    print(f"\nReal website (TMK): {len(results)} contacts found")
    for r in results:
        print(f"  [{r.get('source')}] {r.get('name')} | {r.get('title')} | {r.get('email')} | conf={r.get('confidence')}")
    save_results("real_website_tmk", results, {"company": "ТМК", "website": "https://tmk-group.ru"})
    return results


# ─────────────────────────────────────────
# 主入口
# ─────────────────────────────────────────

async def main():
    print("=" * 50)
    print("Russia Trade Contacts - 测试")
    print("=" * 50)

    # 单元测试（不需要网络）
    await test_transliterate()
    await test_title_translation()
    await test_email_guessing()
    await test_email_guess_two_part_name()

    # 集成测试（需要网络）
    await test_find_contacts_real()

    print("\n" + "=" * 50)
    print(f"✅ 全部测试完成！结果保存在: {RESULTS_DIR}/")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
