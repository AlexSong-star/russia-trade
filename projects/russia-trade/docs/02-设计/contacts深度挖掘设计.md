# 联系人深度挖掘 - 技术方案 v0.2

## 目标

找到俄罗斯公司**真实的采购负责人**（姓名、职位、邮箱、电话），而非总机 info@。

---

## 现实情况

俄罗斯公司官网 90%+ 只留总机电话和 info@，不公开采购负责人联系方式。
必须通过**多渠道交叉验证**才能找到真人。

---

## 数据源优先级（从高到低）

### 🔴 P0 - 必须攻克的渠道

#### 1. VKontakte (vk.com)

**为什么重要：** 俄罗斯最大社媒，B2B 场景下采购经理会在 VK 发采购需求、关注供应商。

**实现方案：**

```
方案A：VK 官方 API（推荐）
- 用强哥的 VK 账号授权（手机号登录）
- 搜索公司名称 + "закуп"（采购）关键词
- 找到发帖/评论的采购负责人
- VK API: groups.search, board.getComments, market.get

方案B：VK 爬虫（备用）
- 用 Playwright 保持登录态
- 搜索 "компания {公司} закупки"
- 从搜索结果中提取人名+帖子内容

依赖：vk-api (已安装), Playwright (已有)
```

**VK API 关键端点：**
```python
# 搜索公司
vk.groups.search(q="ПТК Инжиниринг", type="groups")

# 获取公司详情（可能显示联系方式）
vk.groups.getById(group_id=id, fields="contacts,description")

# 搜索采购相关帖子
vk.board.getComments(group_id=id, topic_id=采购topic)

# 市场/采购帖子
vk.market.get(group_id=id)
```

**VK 关键词：**
```
закупк, закупщик, снабженец, отдел снабжения
закупочная деятельность, закупки для бизнеса
```

---

#### 2. HH.ru（类似俄罗斯 LinkedIn）

**为什么重要：** 俄罗斯最大招聘网站，采购经理找工作时会暴露公司+职位信息。

**数据可获取：**
- 公司员工列表（姓名、职位）
- 某些 HR 会留联系方式
- 历史招聘职位（可推断采购规模）

**实现方案：**
```python
# Playwright 自动化
# 1. 搜索公司员工: https://hh.ru/employer/{company_id}/staff
# 2. 搜索职位包含 "закуп"
# 3. 提取员工姓名+职位
```

---

### 🟡 P1 - 辅助渠道

#### 3. Yandex + 企业数据库交叉

```
组合搜索：
- "{公司名}" "закупк" "директор" "email"
- "{公司名}" "снабжен" "email"
- ИНН "{inn}" + Yandex Maps（找地址，再找同一地址的其他公司）

数据源：
- Yandex Maps（企业地址标注）
- 2GIS（更详细的企业数据，API 需要申请）
- RusProfile（已有 INN/ОГРН，可查管理层）
```

#### 4. 俄罗斯工商名录

```
propartner.ru - B2B平台，有供应商名录
isgp.ru - 企业信息
checko.ru - 企业信息（含高管名字）
```

#### 5. 招标数据交叉

```
b2b-center.ru, zakupki.gov.ru
如果公司有招标历史 → 说明有采购部门 → 有采购负责人
```

---

### 🟢 P2 - 锦上添花

#### 6. 企业官网深度爬取

不只爬「Контакты」页，还要爬：
- 「О компании」页面（管理团队介绍）
- 新闻稿（提到采购负责人）
- 供应商招募页面
- 招聘页（采购职位）

#### 7. Email 格式深度猜测

如果知道采购负责人的俄语名字（从VK/HH获取），结合常见邮箱格式：
```
{first_name[0]}.{last_name}@{domain}  # i.petrov@company.ru
{last_name}@{domain}                   # petrov@company.ru
```

然后用 SMTP 验证或 Hunter.io 验证。

---

## 技术实现路径

### 阶段一：VK + HH.ru（2个最强渠道）

#### VK 登录授权

强哥如果有 VK 账号，提供手机号，我帮生成 access_token，后续可以：
1. 搜索公司主页
2. 查看帖子/评论里的采购负责人
3. 获取联系人信息（如果有公开）

#### HH.ru 自动化

用 Playwright（已安装）：
1. 搜索 `{公司名} сотрудники`
2. 过滤「закуп」相关职位
3. 提取人名+职位+头像

---

## 输出格式升级

```python
{
    "name": "Иван Петров",
    "title": "Начальник отдела закупок",
    "title_cn": "采购部长",
    "email": "i.petrov@company.ru",
    "phone": "+7 (495) 123-45-67",
    "source": "vk",                    # 来源
    "source_url": "https://vk.com/id123456",
    "confidence": 0.85,
    "notes": "在VK发帖询问МНЛЗ配件，显示职位为采购部长",
    "vk_id": "id123456",
    "is_verified": True,              # 是否经过多渠道验证
    "other_sources": ["hh.ru", "website"]
}
```

---

## 优先级排序

| 渠道 | 难度 | 预期效果 | 优先级 |
|------|------|---------|--------|
| VK 帖子搜索 | 中（有账号即可） | 高 | P0 |
| HH.ru 员工搜索 | 中（需解析） | 高 | P0 |
| 官网新闻稿爬取 | 低 | 中 | P1 |
| Yandex 多关键词搜索 | 低 | 中 | P1 |
| Email 格式 + Hunter 验证 | 低 | 低 | P2 |
| 招标数据交叉 | 中 | 中 | P2 |

---

## 实施现状 (2026-03-26)

### ✅ VK API 已集成
- Token 已获取，有效期长
- Token 路径: `code/russia-trade-contacts/vk_token.json`
- VK Token 调用方式: `curl -s --compressed "https://api.vk.com/method/{method}?access_token={TOKEN}&v=5.131"`
- ⚠️ VPN 隧道不稳定，API 调用偶发失败，需重试机制
- **已知 TMK VK ID**: 26319834 (tmkgroupru, 3万成员)

### ✅ HH.ru 已验证可访问
- TMK 雇主 ID: **959179**
- URL: https://hh.ru/employer/959179
- 反爬保护 (ddos-guard)，需用 Playwright 绕过
- 需要 HH.ru 账号登录才能抓取完整员工数据

### ✅ TMK 采购专用邮箱发现！
- **tmk_pokupka@tmk-group.ru** — 供应商询价专用邮箱！可直接发开发信
- tmk@tmk-group.com — 公共邮箱
- pr@tmk-group.com — PR 邮箱
- tmk_pokupka 是"采购"俄语拼音，值得一试

### 供应商招募页
- TMK 官网: https://tmk-group.ru
- 供应商门户: 需进一步研究 tmk-group.ru/suppliers 或类似路径
- 其他俄罗斯大公司供应商门户: b2b-center.ru, tenderguru.ru

---

## 实施现状 (2026-03-26)

### VK API 集成状态
- Token: ✅ 已获取并保存
- Token 路径: `code/russia-trade-contacts/vk_token.json`
- ⚠️ VPN 隧道不稳定，需重试机制

### TMK 联系信息（实测）
| 渠道 | 联系方式 | 备注 |
|------|---------|------|
| 采购询价邮箱 | tmk_pokupka@tmk-group.ru | 最佳优先发开发信 |
| 公共邮箱 | tmk@tmk-group.com | 通常转发到采购 |
| 总机电话 | +7 (495) 775-76-00 | 总部莫斯科 |
| HH.ru | hh.ru/employer/959179 | HR 发布采购职位 |
| VK | tmkgroupru | 官方帖子有采购需求 |

### HH.ru 雇主ID（按公司名）
手动搜索确认：
- ТМК TMK: **959179**
- Северсталь: 待查
- НЛМК: 待查

---

*版本：v0.3*
*更新：2026-03-26*
