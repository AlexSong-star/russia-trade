# russia-trade-researcher

俄罗斯客户背调 Skill。从多渠道深度调研公司信息，补全客户主表字段。

## 功能

根据客户名称/官网，深度调研并填写：
- **联系方式**：电话、邮箱、地址
- **工商信息**：ИНН、ОГРН、法律形式、规模
- **公司描述**：主营产品、经营范围
- **社媒**：VK 等社交账号
- **招标**：b2b-center 招标历史
- **财务标注**：是否有财务信息

## 数据源

| 渠道 | 用途 | 状态 |
|------|------|------|
| metaprom.ru | B2B平台，公司详情页 | ✅ |
| 公司官网 | 地址、电话、邮箱、产品 | ✅ |
| rusprofile.ru | 工商信息（ИНН、ОГРН、规模） | ✅ |
| b2b-center.ru | 招标历史查询 | ✅ |
| VK | 社媒账号 | ⚠️ 需登录 |
| Yandex | 电话/社媒/地址标注 | ⚠️ IP限制 |
| 2GIS | 企业数据库 | ⏳ 待接入 |

## 使用方式

```python
from src.researcher import RussiaTradeResearcher

researcher = RussiaTradeResearcher()

# 背调单家公司
result = researcher.research(
    company_name="ПТК Инжиниринг",
    website="https://ptking.ru/",
    metaprom_url="https://metaprom.ru/companies/id676434"
)

# 批量背调（从飞书表格读取待背调的客户）
results = researcher.research_all_from_table()
```

## 输出

返回 dict，包含背调结果：

```python
{
    # 联系方式
    "phone": "+79031234567",
    "phones_all": ["+79031234567", "+74951234567"],
    "email": "info@company.ru",
    "emails_all": [...],
    "address": "г. Казань, ул. Беломорская 69А",
    # 工商信息
    "inn": "1661041463",
    "ogrn": "1141690058400",
    "legal_form": "ООО",
    "scale": "микропредприятие",
    # 公司信息
    "description": "Производство стальных труб и профилей...",
    "products": ["стальные трубы", "профили"],
    # 社媒
    "social": {"vk": "vk.com/company123", "instagram": "..."},
    # 招标
    "tenders": "有招标记录",
    "tender_snippet": "...",
    # 置信度
    "confidence": 0.86,
    "sources": ["metaprom", "website", "rusprofile", "b2b-center"],
}
```

## 依赖

```
playwright>=1.40.0
playwright-stealth>=2.0.0
beautifulsoup4>=4.12.0
lxml>=4.9.0
```

## 已知限制

- **Yandex**：当前 IP 已被反爬标记，需接 SERP API（Zenserp）或使用代理 IP
- **VK**：匿名用户无法查看公司详情，需登录

*版本：v0.2*
*更新：2026-03-25*
