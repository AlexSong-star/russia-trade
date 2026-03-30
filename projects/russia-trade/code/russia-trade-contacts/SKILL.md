# Russia Trade Contacts - 俄罗斯客户联系人深挖 Skill v0.3

从多渠道深度挖掘俄罗斯公司采购负责人，自动写入飞书多维表格。

## 使用方式

```python
import sys
sys.path.insert(0, "code/russia-trade-contacts/src")
from contacts_miner import ContactsMiner

miner = ContactsMiner()

# 挖掘 TMK
contacts = miner.mine(
    company_name="Трубная Металлургическая Компания",
    domain="tmk-group.ru",
    hh_employer_id="6131",
)

# 挖掘并直接写入飞书
miner.mine_to_feishu(
    company_name="Северсталь",
    domain="severstal.com",
    hh_employer_id="",
    bitable_info={
        "app_token": "UxEmbaiGxaP9RKsQqi3cTW9Dnug",
        "table_id": "tblUmoyljEJDOeuP",
        "customer_id": "客户UUID",
    },
)
```

## 9大渠道

| 渠道 | 方法 | 依赖 | 状态 |
|------|------|------|------|
| 公司官网 | requests | - | ✅ |
| HH.ru | requests API | - | ✅ |
| Yandex搜索 | requests | VPN | ✅ |
| tenderguru.ru | requests | VPN | ✅ |
| LinkedIn | Playwright CDP | Chrome已登录 | ✅ |
| VK API | urllib | VPN（IP绑定） | ⚠️ 需固定IP |
| RusProfile | Playwright | VPN | ✅ |
| 2GIS | Playwright | VPN | ✅ |
| Telegram | Playwright | VPN | 待测 |

**⚠️ VK token 是 IP 绑定的** — VPN 切换服务器节点后 token 失效。需要固定 IP 的 VPN 或服务端 OAuth。

**✅ LinkedIn** — 通过 Chrome CDP 连接，无需重新登录，自动搜索 TMK 采购人。

## 输出格式

```python
[
    {
        "name": "Иван Петров",           # 俄语姓名
        "email": "i.petrov@company.ru",  # 邮箱
        "title": "Начальник отдела закупок",  # 俄语职位
        "title_cn": "采购部长",           # 中文职位
        "phone": "+7 (495) 123-45-67",  # 电话
        "source": "HH.ru",               # 来源渠道
        "source_url": "...",             # 来源链接
        "confidence": 0.85,              # 置信度
        "is_procurement": True,          # 是否采购相关
    }
]
```

## 飞书字段映射

| 飞书字段 | 来源 |
|----------|------|
| 姓名 | name |
| 职位 | title_cn（自动翻译） |
| 邮箱 | email |
| 电话 | phone |
| 深挖方式 | source（H H.ru / VK / LinkedIn / 官网 等） |
| 有效性 | 置信度≥0.7=有效，≥0.4=待确认 |

## 飞书多维表格选项更新

深挖方式字段需要追加以下选项（在飞书UI手动添加）：
- HH.ru
- VK
- RusProfile
- tenderguru
- Telegram

## 安装

```bash
cd code/russia-trade-contacts
uv venv .venv --python python3
source .venv/bin/activate
uv pip install requests
playwright install chromium
```

## VK Token 维护

Token 路径: `code/russia-trade-contacts/vk_token.json`

Token 通过 Chrome CDP 提取（需 Chrome 已登录 VK）：
```bash
# 方法：Chrome 打开 vk.com 登录后，运行：
python3 -c "
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:9222')
    for ctx in browser.contexts:
        for page in ctx.pages:
            if 'vk.com/feed' in page.url:
                token = page.evaluate(\"localStorage.getItem('vk_web_token')\")
                print(token)
"
```

## HH.ru employer ID 快速查

```bash
curl -s "https://api.hh.ru/employers?text=公司名&per_page=5" | python3 -c "import sys,json; [print(f'{e[\"id\"]} {e[\"name\"]}') for e in json.load(sys.stdin)['items']]"
```

## 已知限制

- **VK token IP绑定**：VPN 切换节点后 token 失效，需重新提取
- **HH.ru 不返回公开联系人**：API 只返回职位信息，不返回 HR 邮箱（需付费订阅）
- **LinkedIn 免费版**：看不到邮箱，需 Sales Navigator（$100/月）
- **公司官网**：俄罗斯公司极少公开个人邮箱，通常只有部门邮箱

## 版本

- v0.3：9大渠道整合，VK token IP绑定警告，LinkedIn CDP
- v0.2：写入飞书多维表格
- v0.1：多数据源框架

*更新：2026-03-26*
