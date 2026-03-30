# russia-trade-searcher

俄罗斯客户搜索工具集

## 概述

从三个渠道搜索俄罗斯钢铁/冶金行业潜在客户：
- **B2B投标** (b2b-center.ru) ⭐⭐⭐ 有实际采购需求
- **黄页** (metaprom.ru) ⭐⭐ 企业目录
- **Yandex搜索** (yandex.ru) ⭐ 补充搜索

## 安装

```bash
cd russia-trade-searcher
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
playwright install chromium
```

## 使用

```python
from src.searcher import RussiaTradeSearcher

searcher = RussiaTradeSearcher()

# 搜索所有渠道
results = searcher.search_b2b_center(keywords=["Огнеупоры для МНЛЗ"])

# 打印结果
for c in results:
    print(f"{c.name} | {c.website} | {c.source_channel}")
```

## 输出格式

```python
CompanyInfo(
    name="公司名称",
    website="官网URL",
    address="地址",
    phone="电话",
    email="邮箱",
    source_channel="b2b-center|metaprom|yandex",
    source_url="来源页面URL",
    products=["主营产品关键词"]
)
```

## 技术限制

| 渠道 | 限制 |
|------|------|
| b2b-center.ru | 可能触发人机验证 |
| metaprom.ru | 可能触发人机验证 |
| yandex.ru | 搜索触发CAPTCHA，需要登录或验证码解决 |

**注意**：俄罗斯主要B2B平台均有较强反爬机制，实际使用中可能需要：
1. 使用代理IP
2. 接入验证码解决服务（如Anti-Captcha）
3. 使用真实浏览器环境

## 文件结构

```
russia-trade-searcher/
├── SKILL.md
├── README.md
├── requirements.txt
└── src/
    ├── __init__.py
    ├── models.py          # 数据模型
    ├── searcher.py        # 主搜索器
    ├── utils.py           # 工具函数
    └── channels/
        ├── __init__.py
        ├── b2b_center.py  # B2B Center
        ├── metaprom.py     # Metaprom
        └── yandex.py       # Yandex
```
