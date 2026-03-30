# Russia Trade Contacts - 设计文档

## 目标
深挖俄罗斯公司联系人：采购负责人姓名、职位、邮箱、电话。

## 核心定位
**阶段一工具**：以公司官网 + 公开数据源为主，人工研判为核心。

---

## 数据源优先级

| 优先级 | 数据源 | 说明 |
|--------|--------|------|
| P0 | 公司官网「Контакты」页 | 最佳来源，往往直接列采购负责人 |
| P0 | rusprofile.ru | 有时会显示管理层名单 |
| P1 | Yandex 搜索 | 搜索" компания {公司名} закупки директор / снабженец" |
| P1 | Email 格式猜测 | 常见俄语邮箱格式生成 + Hunter.io 验证 |
| P2 | HH.ru | 某些公司员工的职位信息 |
| P2 | LinkedIn | 部分俄罗斯大公司有 LinkedIn 页面 |

---

## 联系人字段

```python
{
    "name": "Иван Петров",           # 姓名
    "name_ru": "Иван Петров",         # 俄语姓名
    "name_cn": None,                  # 中文音译（可选）
    "title": "Начальник отдела закупок",  # 职位
    "title_cn": "采购部长",            # 职位中文
    "department": "Отдел снабжения", # 部门
    "email": "i.petrov@severstal.com",
    "email_verify": True,             # 是否经过验证
    "email_source": "hunter",         # 来源（website/rusprofile/hunter/pattern）
    "phone": "+7 800 100-00-00",     # 电话（直接）
    "phone_internal": " доб. 1234",    # 分机
    "telegram": None,
    "whatsapp": None,
    "vk": None,                       # VK号
    "notes": "曾出现在2024年招标评审中",
    "confidence": 0.85,               # 置信度
    "source": "website",
    "source_url": "https://company.ru/contacts",
}
```

---

## 技术方案

### 文件结构
```
contacts/
├── src/
│   ├── __init__.py
│   └── contacts_finder.py     # 主类 RussiaTradeContacts
├── SKILL.md
├── requirements.txt
└── tests/
    └── test_contacts.py
```

### 依赖
- playwright + playwright-stealth（浏览器自动化）
- beautifulsoup4 + lxml（网页解析）
- httpx（轻量 HTTP，Hunter.io 等 API）
- deep-translator（俄语职位翻译）

### 俄语职位识别关键词

```python
PROCUREMENT_KEYWORDS = [
    # 采购相关
    "закупк", "снабжен", "закупщик", "снабженец",
    "закупочная", "поставк", "отдел снабжения",
    # 采购总监/经理
    "директор по закупкам", "руководитель закупок",
    "глава отдела закупок", "начальник отдела закупок",
    "менеджер по закупкам", "ведущий специалист по закупкам",
    # 一般经理
    "коммерческий директор", "финансовый директор",
    "генеральный директор", "исполнительный директор",
    # 进出口
    "вэд", "внешнеэкономический", "импорт", "экспорт",
    # 董事长/总经理
    "председатель", "генеральный", "управляющий",
]

SKIP_KEYWORDS = [
    "бухгалтер", "юрист", "адвокат", "юристконсульт",
    "секретарь", "assistant", "ассистент", "кадры", "HR",
    "маркетолог", "PR", "PR-менеджер",
]
```

---

## 邮箱格式策略

### 俄语邮箱常见格式（按优先级）
```python
EMAIL_PATTERNS = [
    # 格式 => 示例
    "{first}.{last}@{domain}",        # ivan.petrov@company.ru
    "{first[0]}{last}@{domain}",       # ipetrov@company.ru
    "{first[0]}.{last}@{domain}",      # i.petrov@company.ru
    "{last}.{first}@{domain}",         # petrov.ivan@company.ru
    "{first}_{last}@{domain}",         # ivan_petrov@company.ru
    "{first}@{domain}",                # ivan@company.ru
]
```

### Hunter.io 验证
- 免费 API：100次/月
- 验证邮箱格式是否真实存在

### 验证方法
1. 发验证邮件（不可行，太耗时）
2. Hunter.io API 验证（可用）
3. SMTP 验证（不可行，易被封）

---

## 输出格式

### find_contacts(公司名, 官网) -> List[Dict]
返回联系人列表，按置信度降序排列。

### enrich_company_contacts(company: Dict) -> Dict
在已有的公司信息 dict 上新增 contacts 字段。

---

## 已知限制

1. **俄罗斯公司联系人信息极少公开** — 大多数公司官网只留 info@ 或总机电话，不留个人邮箱
2. **个人邮箱极少在网页公开** — 实际能找到的联系人信息非常有限，需要人工研判
3. **Hunter.io 俄罗斯数据覆盖率低** — 可能只有 20-30% 的公司能验证到邮箱
4. **采购负责人变动频繁** — 信息可能过时

---

*版本：v0.1*
*更新时间：2026-03-26*
