#!/usr/bin/env python3
"""
俄罗斯贸易联系人深度挖掘框架 v0.3
集成9大渠道，一次调用全搞定
"""
import re
import json
import time
import uuid
import requests
import urllib.request
import gzip
import urllib.parse
from typing import Optional, Literal
from dataclasses import dataclass, field, asdict
from concurrent.futures import ThreadPoolExecutor, as_completed

# ============================================================
# 数据结构
# ============================================================
@dataclass
class Contact:
    """联系人"""
    name: str = ""
    title: str = ""
    title_cn: str = ""
    department: str = ""
    email: str = ""
    phone: str = ""
    company: str = ""
    source: str = ""
    source_url: str = ""
    linkedin_url: str = ""
    hh_vacancy_id: str = ""
    confidence: float = 0.5
    is_procurement: bool = True
    raw_data: dict = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)

    def to_feishu(self) -> dict:
        """转飞书格式"""
        title_cn = self.title_cn or translate_title(self.title)
        return {
            "姓名": self.name,
            "职位": title_cn,
            "邮箱": self.email,
            "电话": self.phone,
            "深挖方式": self.source,
            "有效性": "有效" if self.confidence >= 0.7 else ("待确认" if self.confidence >= 0.4 else "无效"),
        }


# ============================================================
# 翻译函数
# ============================================================
def translate_title(title: str) -> str:
    """俄语职位 → 中文"""
    if not title:
        return ""
    t = title.lower()
    mapping = {
        "начальник отдела": "部门主管",
        "директор": "总监/总经理",
        "менеджер": "经理",
        "специалист": "专员",
        "заместитель": "副职",
        "генеральный директор": "总经理",
        "закуп": "采购",
        "снабж": "供应/采购",
        "поставщик": "供应商",
        "тендер": "招标",
        "procurement": "采购",
        "sourcing": "采购",
        "supply chain": "供应链",
        "supply": "供应",
    }
    result = title
    for ru, cn in mapping.items():
        if ru in t:
            result = result.replace(ru, cn)
    return result


# ============================================================
# 渠道1: 公司官网
# ============================================================
def mine_website(company_name: str, domain: str) -> list[Contact]:
    """从公司官网联系页面挖邮箱"""
    results = []
    if not domain:
        return results

    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120 Safari/537.36",
        "Accept-Language": "ru-RU,ru;q=0.9",
    })

    pages = [
        "/contacts", "/contact", "/about",
        "/suppliers", "/postavshhikam",
        "/tender", "/zakupki", "/procurement",
    ]

    procurement_kw = ["закуп", "снабж", "поставщик", "тендерн", " снабжен"]

    for path in pages:
        url = domain.rstrip("/") + path
        try:
            r = session.get(url, timeout=8)
            if r.status_code != 200:
                continue

            text = r.text
            clean = re.sub(r'<[^>]+>', ' ', text)
            clean = re.sub(r'\s+', ' ', clean)

            # 找邮箱
            emails = list(set(re.findall(r'[\w.+-]+@[\w.-]+\.[a-zа-я]{2,}', clean)))
            real_emails = [e for e in emails if len(e) < 50]

            # 找采购关键词片段
            for kw in procurement_kw:
                idx = clean.lower().find(kw)
                if idx != -1:
                    snippet = clean[max(0,idx-30):idx+100]
                    # 尝试从中提取邮箱
                    snippet_emails = re.findall(r'[\w.+-]+@[\w.-]+\.[a-zа-я]{2,}', snippet)
                    all_emails = list(set(snippet_emails + real_emails[:3]))
                    if all_emails:
                        c = Contact(
                            name=all_emails[0].split("@")[0] if "@" in all_emails[0] else "",
                            email=all_emails[0],
                            title="官网联系页",
                            source="官网",
                            source_url=url,
                            confidence=0.85,
                            is_procurement=True,
                        )
                        if c.email and c.email not in [r.email for r in results]:
                            results.append(c)
        except Exception:
            pass

    return results


# ============================================================
# 渠道2: HH.ru API
# ============================================================
_HH_SESSION = None

def _get_hh_session():
    global _HH_SESSION
    if _HH_SESSION is None:
        _HH_SESSION = requests.Session()
        _HH_SESSION.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120 Safari/537.36",
            "Accept": "application/json",
            "Accept-Language": "ru-RU,ru;q=0.9",
        })
    return _HH_SESSION

def mine_hhru(company_name: str, employer_id: str = None) -> list[Contact]:
    """
    HH.ru API 挖掘
    通过 employer_id 或公司名搜索
    """
    results = []
    session = _get_hh_session()

    # 如果没有 employer_id，先搜索
    if not employer_id:
        try:
            encoded = urllib.parse.quote(company_name)
            r = session.get(f"https://api.hh.ru/employers?text={encoded}&per_page=5", timeout=10)
            if r.status_code == 200:
                employers = r.json().get("items", [])
                if employers:
                    employer_id = str(employers[0]["id"])
        except Exception:
            pass

    if not employer_id:
        return results

    # 获取所有职位
    all_vacs = []
    for page in range(5):
        try:
            r = session.get(
                f"https://api.hh.ru/vacancies?employer_id={employer_id}&per_page=100&page={page}",
                timeout=10
            )
            if r.status_code == 200:
                data = r.json()
                all_vacs.extend(data.get("items", []))
                if page >= data.get("pages", 0) - 1:
                    break
            time.sleep(0.3)
        except Exception:
            break

    procurement_kw = ["закуп", "снабж", "заказчик", "поставщик", "тендер", "снабжен"]

    for vac in all_vacs:
        title = vac.get("name", "")
        sn = vac.get("snippet", {}) or {}
        req = sn.get("requirement", "") or ""
        resp = sn.get("responsibility", "") or ""
        full_text = f"{title} {req} {resp}".lower()

        if any(kw in full_text for kw in procurement_kw):
            vac_id = vac.get("id")
            area = vac.get("area", {}).get("name", "")
            vac_url = vac.get("alternate_url", "")

            # 获取职位详情找HR联系人
            try:
                r2 = session.get(f"https://api.hh.ru/vacancies/{vac_id}", timeout=10)
                if r2.status_code == 200:
                    v_detail = r2.json()
                    contacts = v_detail.get("contacts") or {}
                    name = contacts.get("name", "")
                    email = contacts.get("email", "")
                    phones = [f"{p.get('country','')}{p.get('city','')}{p.get('number','')}"
                              for p in (contacts.get("phones") or [])]
                    dept = v_detail.get("department", {}) or {}

                    if name or email or title:
                        c = Contact(
                            name=name or "",
                            email=email or "",
                            title=title,
                            title_cn=translate_title(title),
                            department=dept.get("name", ""),
                            phone="; ".join(phones) if phones else "",
                            source="HH.ru",
                            source_url=vac_url,
                            hh_vacancy_id=str(vac_id),
                            confidence=0.8 if name else 0.6,
                            is_procurement=True,
                        )
                        results.append(c)
            except Exception:
                pass

            time.sleep(0.3)

    return results


# ============================================================
# 渠道3: VK API
# ============================================================
VK_TOKEN_FILE = "/Users/jarvis/.openclaw/workspace/projects/russia-trade/code/russia-trade-contacts/vk_token.json"

def _get_vk_token() -> Optional[str]:
    try:
        with open(VK_TOKEN_FILE) as f:
            return json.load(f).get("access_token")
    except:
        return None

def vk_api(method: str, params: dict) -> dict:
    """调用VK API"""
    token = _get_vk_token()
    if not token:
        return {}
    ps = urllib.parse.urlencode(params)
    url = f"https://api.vk.com/method/{method}?{ps}&access_token={token}&v=5.131"
    req = urllib.request.Request(url, headers={"Accept-Encoding": "gzip, deflate", "Accept-Charset": "utf-8"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read()
            if resp.headers.get("Content-Encoding") == "gzip":
                data = gzip.decompress(data)
            return json.loads(data)
    except Exception:
        return {}

def mine_vk(company_name: str, domain: str = None) -> list[Contact]:
    """VK API 挖掘公司成员和采购相关帖子"""
    results = []
    token = _get_vk_token()
    if not token:
        return results

    procurement_kw = ["закуп", "снабж", "закупщик", "снабженец", "поставщик"]

    # 搜索公司群组
    encoded_q = urllib.parse.quote(company_name)
    s = vk_api("groups.search", {"q": company_name, "type": "group", "count": 5})
    groups = s.get("response", {}).get("items", [])

    for g in groups:
        gid = g.get("id")
        gname = g.get("name", "")

        # 获取成员
        try:
            m = vk_api("groups.getMembers", {
                "group_id": gid, "count": 100,
                "fields": "occupation,career,about,contacts"
            })
            profiles = m.get("response", {}).get("profiles", [])
            for u in profiles:
                occ = u.get("occupation") or {}
                career = u.get("career") or []
                occ_text = " ".join([
                    occ.get("name",""), occ.get("position",""), u.get("about","")
                ] + [f"{c.get('company','')} {c.get('position','')}" for c in career[:2]]).lower()

                if any(kw in occ_text for kw in procurement_kw):
                    uid = u.get("id")
                    vk_link = f"vk.com/id{uid}"
                    c = Contact(
                        name=f"{u.get('first_name','')} {u.get('last_name','')}",
                        title=f"{occ.get('name','')} / {occ.get('position','')}",
                        title_cn=translate_title(occ.get("position", "")),
                        source="VK",
                        source_url=f"https://{vk_link}",
                        linkedin_url=f"https://{vk_link}",
                        confidence=0.75,
                        is_procurement=True,
                        raw_data={"vk_id": uid, "group": gname},
                    )
                    results.append(c)
        except Exception:
            pass

        time.sleep(0.3)

    # 搜索采购相关帖子（用newsfeed.search）
    queries = [
        f"{company_name} закупки",
        f"{company_name} поставщик",
        "закупки " + company_name,
    ]
    for q in queries[:2]:
        try:
            ns = vk_api("newsfeed.search", {"q": q, "count": 20, "extended": 1})
            items = ns.get("response", {}).get("items", [])
            profiles = {p["id"]: p for p in ns.get("response", {}).get("profiles", [])}
            groups_d = {g["id"]: g for g in ns.get("response", {}).get("groups", [])}

            for item in items:
                text = item.get("text", "")
                if not text or len(text) < 20:
                    continue
                owner_id = item.get("owner_id", 0)
                from_id = item.get("from_id", 0)

                # 获取发帖人信息
                if owner_id > 0:
                    user = profiles.get(owner_id, {})
                    name = f"{user.get('first_name','')} {user.get('last_name','')}"
                else:
                    ginfo = groups_d.get(abs(owner_id), {})
                    name = ginfo.get("name", "")

                c = Contact(
                    name=name,
                    title="VK帖子作者",
                    source="VK",
                    confidence=0.4,
                    is_procurement=True,
                    raw_data={"post_text": text[:200], "owner_id": owner_id},
                )
                results.append(c)
        except Exception:
            pass

        time.sleep(0.5)

    return results


# ============================================================
# 渠道4: Yandex 搜索
# ============================================================
def mine_yandex(company_name: str) -> list[Contact]:
    """Yandex 商业搜索"""
    results = []
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120 Safari/537.36",
        "Accept-Language": "ru-RU,ru;q=0.9",
    })

    queries = [
        f"{company_name} контакт закупки отдел email",
        f'"{company_name}" +закупки +email',
    ]

    for q in queries[:2]:
        try:
            encoded = urllib.parse.quote(q)
            r = session.get(f"https://yandex.ru/search/?text={encoded}&lr=213", timeout=10)
            if r.status_code != 200:
                continue

            text = r.text
            clean = re.sub(r'<[^>]+>', ' ', text)
            clean = re.sub(r'\s+', ' ', clean)

            emails = list(set(re.findall(r'[\w.+-]+@[\w.-]+\.[a-zа-я]{2,}', clean)))
            real_emails = [e for e in emails if len(e) < 50]

            for kw in ["закупк", "снабжени"]:
                idx = clean.lower().find(kw)
                if idx != -1:
                    snippet = clean[max(0,idx-50):idx+120]
                    snippet_emails = re.findall(r'[\w.+-]+@[\w.-]+\.[a-zа-я]{2,}', snippet)
                    all_e = list(set(snippet_emails + real_emails[:2]))
                    if all_e:
                        c = Contact(
                            email=all_e[0],
                            source="Yandex",
                            confidence=0.5,
                            is_procurement=True,
                        )
                        if c.email not in [r.email for r in results]:
                            results.append(c)
        except Exception:
            pass
        time.sleep(1)

    return results


# ============================================================
# 渠道5: tenderguru.ru 招标平台
# ============================================================
def mine_tenderguru(company_name: str) -> list[Contact]:
    """tenderguru.ru 俄罗斯招标平台"""
    results = []
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120 Safari/537.36",
        "Accept-Language": "ru-RU,ru;q=0.9",
    })

    try:
        encoded = urllib.parse.quote(company_name)
        r = session.get(f"https://tenderguru.ru/search/?q={encoded}", timeout=10)
        if r.status_code == 200:
            emails = list(set(re.findall(r'[\w.+-]+@[\w.-]+\.[a-zа-я]{2,}', r.text)))
            real_emails = [e for e in emails if "tenderguru" in e.lower() or len(e) < 40]
            for email in real_emails[:3]:
                c = Contact(
                    email=email,
                    source="tenderguru",
                    confidence=0.6,
                    is_procurement=True,
                )
                results.append(c)
    except Exception:
        pass

    return results


# ============================================================
# 渠道6: LinkedIn (Chrome CDP)
# ============================================================
def mine_linkedin(company_name: str, domain: str = None) -> list[Contact]:
    """
    LinkedIn Chrome CDP 挖掘
    通过 Playwright 连接已登录的 Chrome，获取采购相关人员信息
    """
    results = []
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return results

    try:
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")

            li_page = None
            for ctx in browser.contexts:
                for page in ctx.pages:
                    if "linkedin.com/feed" in page.url:
                        li_page = page
                        break
                if li_page:
                    break

            if not li_page:
                browser.close()
                return results

            search_page = li_page.context.new_page()

            # 搜索词
            searches = [
                f"site:linkedin.com \"{company_name}\" procurement",
                f"site:linkedin.com \"{company_name}\" закупки",
                f"site:linkedin.com \"{domain or company_name}\" supply chain",
            ]

            for sq in searches[:2]:
                try:
                    encoded = urllib.parse.quote(sq)
                    search_url = f"https://www.linkedin.com/search/results/people/?keywords={encoded}"
                    search_page.goto(search_url, timeout=20000)
                    search_page.wait_for_load_state("domcontentloaded", timeout=15000)
                    search_page.wait_for_timeout(4000)

                    text = search_page.inner_text("body")
                    lines = text.split("\n")

                    # 解析人员列表
                    i = 0
                    while i < len(lines) - 2:
                        line = lines[i].strip()
                        # 英文名字模式
                        if re.match(r'^[A-Z][a-z]+(\s+[A-Z][a-z]+){1,2}$', line):
                            name = line
                            title = ""
                            company = ""

                            # 看后面几行找职位和公司
                            for j in range(i+1, min(i+6, len(lines))):
                                l = lines[j].strip()
                                if not l:
                                    continue
                                l_lower = l.lower()
                                if any(kw in l_lower for kw in ["procurement", "sourcing", "supply chain", "закуп", "снабж", "supply"]):
                                    if not title:
                                        title = l
                                if company_name.lower() in l_lower or (domain and domain.split(".")[0].lower() in l_lower):
                                    company = l
                                    break

                            if title or company:
                                # 尝试获取 profile URL
                                profile_url = search_page.evaluate(f"""
                                    () => {{
                                        const links = Array.from(document.querySelectorAll('a'));
                                        for (let link of links) {{
                                            const txt = link.innerText || '';
                                            if (txt.includes('{name.replace("'", "\\\\'")}')) {{
                                                const href = link.href || '';
                                                if (href.includes('/in/')) {{
                                                    return href.split('?')[0];
                                                }}
                                            }}
                                        }}
                                        return '';
                                    }}
                                """)

                                c = Contact(
                                    name=name,
                                    title=title,
                                    title_cn=translate_title(title),
                                    company=company,
                                    source="LinkedIn",
                                    source_url=profile_url if profile_url else "",
                                    linkedin_url=profile_url if profile_url else "",
                                    confidence=0.7,
                                    is_procurement=bool(title),
                                )
                                results.append(c)
                        i += 1

                    time.sleep(3)

                except Exception:
                    pass

            search_page.close()
            browser.close()

    except Exception:
        pass

    return results


# ============================================================
# 主类：联系人挖掘器
# ============================================================
class ContactsMiner:
    """
    俄罗斯贸易联系人挖掘器
    支持9大渠道，按公司名/官网/INN自动挖掘
    """

    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120 Safari/537.36",
            "Accept-Language": "ru-RU,ru;q=0.9",
            "Accept-Encoding": "gzip, deflate",
        })

    def mine(
        self,
        company_name: str,
        domain: str = None,
        hh_employer_id: str = None,
        vk_group_id: str = None,
        include_linkedin: bool = True,
    ) -> list[Contact]:
        """
        深度挖掘入口

        Args:
            company_name: 公司名称（俄语/英语）
            domain: 官网域名（如 tmk-group.ru）
            hh_employer_id: HH.ru雇主ID（可选，自动搜索）
            vk_group_id: VK群组ID（可选，自动搜索）
            include_linkedin: 是否启用LinkedIn（需要Chrome已登录）
        """
        print(f"\n{'='*60}")
        print(f"🔍 深度挖掘: {company_name}")
        print(f"{'='*60}")

        all_contacts = []

        # 并发执行各渠道（LinkedIn单独执行因为需要特殊处理）
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {}

            if domain:
                f = executor.submit(mine_website, company_name, domain)
                futures["官网"] = f

            if hh_employer_id or company_name:
                f = executor.submit(mine_hhru, company_name, hh_employer_id)
                futures["HH.ru"] = f

            if company_name:
                f = executor.submit(mine_vk, company_name, domain)
                futures["VK"] = f

            if company_name:
                f = executor.submit(mine_yandex, company_name)
                futures["Yandex"] = f

            if company_name:
                f = executor.submit(mine_tenderguru, company_name)
                futures["tenderguru"] = f

            for name, future in futures.items():
                try:
                    contacts = future.result(timeout=30)
                    if contacts:
                        print(f"\n[{name}] 找到 {len(contacts)} 个联系人")
                        all_contacts.extend(contacts)
                    else:
                        print(f"\n[{name}] 无结果")
                except Exception as e:
                    print(f"\n[{name}] 错误: {e}")

        # LinkedIn 单独执行（需要Playwright且可能较慢）
        if include_linkedin:
            print("\n[LinkedIn] 搜索中（需要Chrome已登录LinkedIn）...")
            try:
                li_contacts = mine_linkedin(company_name, domain)
                if li_contacts:
                    print(f"[LinkedIn] 找到 {len(li_contacts)} 个联系人")
                    all_contacts.extend(li_contacts)
                else:
                    print("[LinkedIn] 无结果（可能未登录）")
            except Exception as e:
                print(f"[LinkedIn] 错误: {e}")

        # 去重
        unique = {}
        for c in all_contacts:
            key = f"{c.name.lower().strip()}|{c.email.lower().strip()}"
            if key not in unique or c.confidence > unique[key].confidence:
                unique[key] = c

        final = list(unique.values())

        print(f"\n{'='*60}")
        print(f"📋 汇总")
        print(f"{'='*60}")
        print(f"去重后: {len(final)} 个联系人")
        for c in final:
            marker = "🌟" if c.is_procurement else "  "
            print(f"  {marker} {c.name} | {c.title[:30] if c.title else ''} | {c.email}")

        return final

    def mine_to_feishu(
        self,
        company_name: str,
        domain: str = None,
        hh_employer_id: str = None,
        bitable_info: dict = None,
    ) -> list[Contact]:
        """挖掘并写入飞书"""
        contacts = self.mine(
            company_name=company_name,
            domain=domain,
            hh_employer_id=hh_employer_id,
        )

        if not bitable_info:
            return contacts

        # 写入飞书
        written = 0
        for c in contacts:
            try:
                write_contact_to_feishu(c, bitable_info)
                written += 1
                print(f"  ✅ 已写入: {c.name} | {c.email}")
            except Exception as e:
                print(f"  ❌ 写入失败: {c.name} | {e}")

        print(f"\n共写入 {written}/{len(contacts)} 个联系人到飞书")
        return contacts


# ============================================================
# 飞书写入
# ============================================================
def write_contact_to_feishu(contact: Contact, bitable_info: dict) -> None:
    """将联系人写入飞书多维表格"""
    import subprocess

    app_token = bitable_info["app_token"]
    table_id = bitable_info["table_id"]
    customer_id = bitable_info.get("customer_id", "")

    # 获取用户 access_token
    cmd = [
        "python3", "-c",
        f"""
import subprocess
result = subprocess.run(
    ['security', 'find-generic-password', '-a', 'openclaw-feishu-uat', '-w'],
    capture_output=True, text=True
)
print(result.stdout.strip())
"""
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    uat = result.stdout.strip()
    if not uat:
        raise RuntimeError("无法获取飞书 access_token")

    # 构建记录
    feishu_data = contact.to_feishu()
    feishu_data["联系人ID"] = str(uuid.uuid4())
    if customer_id:
        feishu_data["客户ID"] = customer_id

    # 转换为飞书字段格式
    fields = {}
    field_mapping = {
        "联系人ID": "联系人ID",
        "客户ID": "客户ID",
        "姓名": "姓名",
        "职位": "职位",
        "邮箱": "邮箱",
        "电话": "电话",
        "深挖方式": "深挖方式",
        "有效性": "有效性",
    }
    for k, v in feishu_data.items():
        if k in field_mapping and v:
            fields[field_mapping[k]] = v

    # 写入
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records"
    payload = {"fields": fields}

    import json as json_lib
    cmd2 = [
        "curl", "-s", "-X", "POST",
        "-H", f"Authorization: Bearer {uat}",
        "-H", "Content-Type: application/json",
        "-d", json_lib.dumps(payload),
        url,
        "-k"
    ]
    r = subprocess.run(cmd2, capture_output=True, text=True)
    resp = json_lib.loads(r.stdout)
    if resp.get("code") != 0 and "duplicate" not in str(resp.get("msg", "")):
        raise RuntimeError(f"飞书写入失败: {resp.get('msg')}")


# ============================================================
# 便捷入口
# ============================================================
def mine_company(
    company_name: str,
    domain: str = None,
    hh_employer_id: str = None,
    bitable_info: dict = None,
) -> list[Contact]:
    """一行调用挖掘"""
    miner = ContactsMiner()
    return miner.mine_to_feishu(
        company_name=company_name,
        domain=domain,
        hh_employer_id=hh_employer_id,
        bitable_info=bitable_info,
    )
