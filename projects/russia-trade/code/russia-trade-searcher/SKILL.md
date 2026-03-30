# russia-trade-searcher

俄罗斯客户搜索工具集。从 B2B 投标网站、黄页、Yandex 搜索潜在客户数据。

## 搜索渠道

| 渠道 | 地址 | 优先级 | 说明 |
|------|------|--------|------|
| **HH.ru 职位搜索** | api.hh.ru | ⭐⭐⭐ | **核心渠道**，通过产品职位找公司，效率最高 |
| B2B投标 | b2b-center.ru | ⭐⭐ | 有实际采购需求，需 Chrome CDP |
| 黄页 | metaprom.ru | ⭐⭐ | 企业目录，规模较大 |
| Yandex | yandex.ru | ⭐ | 补充搜索，CAPTCHA 拦截 |
| VK | api.vk.com | ⭐ | 社群信息，需固定 IP |

## 输出字段（客户主表）

搜索结果写入飞书多维表格时，映射到以下字段：

| 搜索结果字段 | 飞书表格字段 | 说明 |
|------------|-------------|------|
| name | 公司名称 | 公司全名 |
| website | 官网 | 超链接字段 |
| source_channel + source_url | 所在渠道 + 渠道链接 | 渠道名+该平台的原始页面URL |
| address | 地址 | 从metaprom详情页提取 |
| phone | 备注 | 提取到则写入备注 |
| contact | 备注 | 联系人姓名+职位写入备注 |

**注意**：飞书超链接字段创建记录有API限制，"渠道链接"存储为文本类型字段。

## HH.ru 职位搜索（核心方法）

**关键发现**：通过职位文本搜索公司，比按公司名搜索高效 10 倍。

| 方法 | API | 效果 |
|------|-----|------|
| 旧方法（公司名搜索） | `GET /employers?text=Валки` | 找到 **1** 家（名字含关键词） |
| 新方法（职位文本搜索） | `GET /vacancies?text=Валки` | 找到 **44** 家（包括 ЕВРАЗ, Северсталь, ОМК 等） |

```python
from channels.hhru import search_companies

# 同步搜索（推荐）
companies = search_companies([
    "Валки прокатные",       # 轧辊
    "Прокатный стан",        # 轧机
    "Стан горячей прокатки", # 热轧机
])

for c in companies:
    print(f"{c.name} - {c.source_url}")

# 获取雇主详情
from channels.hhru import HHRU_SEARCHER
hhru = HHRU_SEARCHER()
details = hhru.get_employer_details("19989")  # ЕВРАЗ
print(details["website"])

# 获取采购职位
procs = hhru.get_procurement_vacancies("19989")
for p in procs:
    print(f"• {p['name']} - {p['url']}")
```

## 搜索关键词

```python
PRODUCT_KEYWORDS = [
    "Огнеупоры для МНЛЗ",       # 耐火材料+连铸机
    "Валки прокатные",             # 轧辊
    "Кристаллизатор для МНЛЗ",    # 结晶器
    "Поставщик огнеупоров",       # 耐火材料供应商
    "Огнеупорные материалы",      # 耐火材料
    "МНЛЗ запчасти",              # 连铸机配件
]
```

## 使用方式

```python
from src.searcher import RussiaTradeSearcher

searcher = RussiaTradeSearcher()

# 同步搜索单个渠道
results = searcher.search_b2b_center(keywords=["Огнеупоры для МНЛЗ"])

# 输出: [CompanyInfo(name, website, address, source_channel, ...), ...]
for c in results:
    print(f"{c.name} | {c.website}")
```

## 依赖

```
playwright>=1.40.0
beautifulsoup4>=4.12.0
lxml>=4.9.0
requests>=2.31.0
pandas>=2.0.0
aiohttp>=3.9.0
```

安装：
```bash
cd russia-trade-searcher
uv venv && source .venv/bin/activate
uv pip install -r requirements.txt
playwright install chromium
```

## 技术限制（重要）

| 渠道 | 限制 | 应对 |
|------|------|------|
| b2b-center.ru | 人机验证 | 需要代理IP或验证码解决 |
| metaprom.ru | 人机验证 | 需要代理IP或验证码解决 |
| yandex.ru | 搜索CAPTCHA | 需要登录或Anti-Captcha服务 |

俄罗斯主要B2B平台均有反爬，实际使用可能需要：
1. 代理IP池
2. 验证码解决服务（如Anti-Captcha、2Captcha）
3. 降低请求频率

---

*版本：v0.2（客户主表新增渠道链接字段，解决超链接字段写入API限制）*
*更新：2026-03-24*
