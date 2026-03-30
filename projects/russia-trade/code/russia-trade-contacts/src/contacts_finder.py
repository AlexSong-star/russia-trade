"""
Russia Trade Contacts - 俄罗斯客户联系人深挖工具
查找采购负责人：姓名、职位、邮箱、电话

数据源：
1. 公司官网 Контакты 页
2. rusprofile.ru 管理层信息
3. Yandex 搜索
4. Email 格式猜测 + Hunter.io 验证

输出：
- 直接写入飞书多维表格「联系人表」
- 同时返回联系人列表
"""

import asyncio
import json
import logging
import re
import uuid
from pathlib import Path
from typing import Optional, Dict, List
from urllib.parse import urlparse

try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

logger = logging.getLogger(__name__)

# 采购相关职位关键词（俄语）
PROCUREMENT_KEYWORDS = [
    # 采购
    "закупк", "снабжен", "закупщик", "снабженец",
    "закупочная", "поставк", "отдел снабжения",
    # 采购经理/总监
    "директор по закупкам", "руководитель закупок",
    "глава отдела закупок", "начальник отдела закупок",
    "менеджер по закупкам", "ведущий специалист по закупкам",
    "заместитель директора по закупкам",
    # 一般管理
    "коммерческий директор", "финансовый директор",
    "генеральный директор", "исполнительный директор",
    "управляющий директор",
    # 进出口
    "вэд", "внешнеэкономический", "импорт", "экспорт",
    "менеджер вэд", "специалист вэд",
    # 总经理/董事长
    "председатель", "генеральный", "управляющий",
    "首", "генеральный директор",
    # 技术/生产（可能是备选联系人）
    "технический директор", "главный инженер",
    "директор по производству",
]

# 排除关键词（非采购相关）
SKIP_KEYWORDS = [
    "бухгалтер", "юрист", "адвокат", "юристконсульт",
    "секретарь", "ассистент", "кадры", "hr", "hr-менеджер",
    "маркетолог", "pr-менеджер", "пиар", "公关",
    "кадровый", "персонал", "рекрутер",
    "водитель", "охранник", "уборщик",
    "охрана", "безопасность", "охранное",
]

# 俄语姓名常见名字列表（用于识别全名）
RUSSIAN_FIRST_NAMES = [
    "александр", "алексей", "анатолий", "андрей", "аркадий",
    "богдан", "борис", "вадим", "валерий", "василий",
    "виктор", "виталий", "владимир", "владислав", "всеволод",
    "вячеслав", "геннадий", "георгий", "дмитрий", "евгений",
    "егор", "иван", "игорь", "илия", "илья", "иосиф",
    "кирилл", "константин", "лариса", "лев", "леонид",
    "лука", "максим", "михаил", "никита", "николай",
    "олег", "павел", "петр", "сергей", "семен",
    "святослав", "степан", "федор", "юрий", "ярослав",
    # 女性
    "алена", "алеся", "анастасия", "анна", "вера",
    "галина", "дария", "екатерина", "елена", "елизавета",
    "зинаида", "инна", "ирина", "карина", "кристина",
    "лариса", "лидия", "любовь", "людмила", "маргарита",
    "мария", "наталья", "надежда", "ольга", "оксана",
    "светлана", "софия", "татьяна", "юлия", "яна",
]

# 常见俄语邮箱格式
EMAIL_PATTERNS = [
    "{first}.{last}@{domain}",
    "{first_last}@{domain}",
    "{first[0]}{last}@{domain}",
    "{first[0]}.{last}@{domain}",
    "{last}.{first}@{domain}",
    "{last}_{first}@{domain}",
    "{first}_{last}@{domain}",
    "{first}@{domain}",
]


class RussiaTradeContacts:
    """
    俄罗斯客户联系人查找器
    查找公司采购负责人（姓名、职位、邮箱、电话）
    """

    def __init__(self, timeout: int = 20000, headless: bool = True):
        self.timeout = timeout
        self.headless = headless
        self._browser = None
        self._context = None

    # ─────────────────────────────────────────
    # 公开 API
    # ─────────────────────────────────────────

    async def find_contacts(
        self,
        company_name: str,
        website: Optional[str] = None,
        inn: Optional[str] = None,
        domain: Optional[str] = None,
        bitable_info: Optional[Dict] = None,
    ) -> List[Dict]:
        """
        查找公司联系人入口

        Args:
            company_name: 公司名称（俄语）
            website: 公司官网
            inn: INN（税号，可选）
            domain: 邮箱域名（如 severstal.ru）
            bitable_info: 飞书多维表格信息（可选）
                {
                    "app_token": "xxx",
                    "table_id": "tblxxx",
                    "customer_id": "uuid"   # 关联的客户ID
                }
                若传入此参数，联系人自动写入飞书联系人表

        Returns:
            联系人列表，按置信度降序
        """
        results = []
        seen_emails = set()

        # 1. 官网联系人页
        if website:
            contacts = await self._find_on_website(website, company_name)
            for c in contacts:
                if c["email"] and c["email"] not in seen_emails:
                    seen_emails.add(c["email"])
                    results.append(c)
                elif not c["email"]:
                    results.append(c)

        # 2. rusprofile.ru
        if inn:
            contacts = await self._find_on_rusprofile(inn, company_name)
            for c in contacts:
                if c.get("email") and c["email"] not in seen_emails:
                    seen_emails.add(c["email"])
                    results.append(c)
                elif not c.get("email"):
                    results.append(c)

        # 3. Yandex 搜索
        contacts = await self._search_on_yandex(company_name, domain)
        for c in contacts:
            if c.get("email") and c["email"] not in seen_emails:
                seen_emails.add(c["email"])
                results.append(c)
            elif not c.get("email"):
                results.append(c)

        # 4. Email 格式猜测（当有域名但无邮箱时）
        if domain and not any(r.get("email") for r in results):
            guessed = await self._guess_email_patterns(company_name, domain)
            results.extend(guessed)

        # 去重 & 排序
        results = self._deduplicate(results)
        results.sort(key=lambda x: x.get("confidence", 0), reverse=True)

        # 写入飞书多维表格
        if bitable_info and results:
            await self._save_to_bitable(results, bitable_info)

        return results

    def find_contacts_sync(
        self,
        company_name: str,
        website: Optional[str] = None,
        inn: Optional[str] = None,
        domain: Optional[str] = None,
        bitable_info: Optional[Dict] = None,
    ) -> List[Dict]:
        """同步封装"""
        return asyncio.get_event_loop().run_until_complete(
            self.find_contacts(company_name, website, inn, domain, bitable_info)
        )

    # ─────────────────────────────────────────
    # 写入飞书多维表格
    # ─────────────────────────────────────────

    async def _save_to_bitable(
        self,
        contacts: List[Dict],
        bitable_info: Dict,
    ):
        """
        将联系人批量写入飞书多维表格「联系人表」

        字段映射：
        - 联系人ID: UUID
        - 客户ID: 关联的客户UUID
        - 姓名: name
        - 职位: title_cn
        - 邮箱: email
        - 电话: phone
        - 深挖方式: source（官网/rusprofile/yandex/pattern）
        - 有效性: 根据confidence判断（≥0.7=有效，<0.7=待确认）

        依赖：httpx, app_id + app_secret（通过环境变量或 bitable_info 传入）
        """
        import os
        import asyncio

        try:
            import httpx
        except ImportError:
            logger.warning("httpx not installed, contacts will not be written to Bitable")
            logger.info("Install with: uv pip install httpx")
            self._save_to_json(contacts, bitable_info)
            return

        app_token = bitable_info.get("app_token")
        table_id = bitable_info.get("table_id")
        customer_id = bitable_info.get("customer_id")
        app_id = bitable_info.get("app_id") or os.getenv("FEISHU_APP_ID")
        app_secret = bitable_info.get("app_secret") or os.getenv("FEISHU_APP_SECRET")

        if not app_id or not app_secret:
            logger.warning("Missing Feishu app credentials (app_id/app_secret)")
            logger.info("Set FEISHU_APP_ID and FEISHU_APP_SECRET env vars, or pass in bitable_info")
            self._save_to_json(contacts, bitable_info)
            return

        if not app_token or not table_id:
            logger.warning("Missing app_token or table_id in bitable_info")
            self._save_to_json(contacts, bitable_info)
            return

        # 获取 tenant access token
        try:
            token_data = await self._get_tenant_token(app_id, app_secret)
            tenant_token = token_data.get("tenant_access_token")
            if not tenant_token:
                raise ValueError("No tenant_access_token in response")
        except Exception as e:
            logger.warning(f"Failed to get Feishu tenant token: {e}")
            self._save_to_json(contacts, bitable_info)
            return

        headers = {
            "Authorization": f"Bearer {tenant_token}",
            "Content-Type": "application/json",
        }

        # 批量写入（飞书支持批量创建）
        records = []
        for c in contacts:
            contact_id = str(uuid.uuid4())
            confidence = c.get("confidence", 0)

            # 有效性
            if confidence >= 0.7:
                validity = "有效"
            elif confidence >= 0.4:
                validity = "待确认"
            else:
                validity = "无效"

            # 深挖方式
            source = c.get("source", "unknown")
            method_label = {
                "website": "官网",
                "rusprofile": "Rusprofile",
                "yandex": "Yandex搜索",
                "pattern": "Email格式猜测",
            }.get(source, source)

            fields = {
                "联系人ID": {"text": contact_id},
                "客户ID": {"text": customer_id or ""},
                "姓名": {"text": c.get("name") or ""},
                "职位": {"text": (c.get("title_cn") or c.get("title") or "")[:100]},
                "邮箱": {"text": c.get("email") or ""},
                "电话": {"text": c.get("phone") or ""},
                "深挖方式": {"text": method_label},
                "有效性": {"text": validity},
            }
            records.append({"fields": fields})

        if not records:
            return

        # 批量创建记录
        url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_create"
        payload = {"records": records}

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(url, headers=headers, json=payload)
                resp_data = resp.json()

                if resp.status_code == 200 and resp_data.get("code") == 0:
                    written = len(resp_data.get("data", {}).get("records", []))
                    logger.info(f"[Bitable] ✅ 成功写入 {written}/{len(contacts)} 条联系人到 {app_token}/{table_id}")
                else:
                    logger.warning(f"[Bitable] ❌ 写入失败: {resp_data.get('msg')} (code={resp_data.get('code')})")
                    # fallback: 保存到 JSON
                    self._save_to_json(contacts, bitable_info)
        except Exception as e:
            logger.warning(f"[Bitable] API调用异常: {e}")
            self._save_to_json(contacts, bitable_info)

    async def _get_tenant_token(self, app_id: str, app_secret: str) -> Dict:
        """获取 Feishu tenant access token"""
        import httpx
        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        payload = {"app_id": app_id, "app_secret": app_secret}
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=payload)
            return resp.json()

    def _save_to_json(self, contacts: List[Dict], bitable_info: Dict):
        """
        Bitable 写入失败时，保存到本地 JSON 文件作为备份
        文件名: contacts_{customer_id}_{timestamp}.json
        """
        import os
        from datetime import datetime

        backup_dir = Path(__file__).parent.parent / "results"
        backup_dir.mkdir(exist_ok=True)

        customer_id = bitable_info.get("customer_id", "unknown")
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = backup_dir / f"contacts_{customer_id}_{ts}.json"

        output = {
            "customer_id": customer_id,
            "timestamp": datetime.now().isoformat(),
            "target_bitable": {
                "app_token": bitable_info.get("app_token"),
                "table_id": bitable_info.get("table_id"),
            },
            "contacts": contacts,
            "note": "Bitable写入失败时的本地备份，请手动导入飞书表格",
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        logger.info(f"[Backup] 联系人已保存到本地: {filepath}")


    # ─────────────────────────────────────────
    # 数据源 1: 公司官网
    # ─────────────────────────────────────────

    async def _find_on_website(self, website: str, company_name: str) -> List[Dict]:
        """从公司官网找联系人"""
        if not PLAYWRIGHT_AVAILABLE:
            logger.warning("Playwright not available, skipping website search")
            return []

        contacts = []
        parsed = urlparse(website)
        base_url = f"{parsed.scheme}://{parsed.netloc}"

        # 常见联系人页路径
        contact_paths = [
            "/contacts",
            "/contact",
            "/контакты",
            "/о-компании/контакты",
            "/about/contacts",
            "/en/contacts",
        ]

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            )

            for path in contact_paths:
                url = base_url + path
                try:
                    page = await context.new_page()
                    await page.goto(url, timeout=10000)
                    await page.wait_for_load_state("domcontentloaded")

                    # 提取联系人信息
                    text = await page.content()
                    page_contacts = self._extract_contacts_from_text(text, company_name)

                    # 从页面源码提取邮箱
                    html = await page.content()
                    emails = self._extract_emails_from_html(html)
                    for email in emails:
                        if self._is_procurement_related_email(email, company_name):
                            # 找关联的姓名
                            name = self._find_name_near_email(html, email)
                            title = self._find_title_near_text(text, name) if name else None
                            page_contacts.append({
                                "name": name or self._email_to_name(email),
                                "email": email,
                                "title": title,
                                "title_cn": self._translate_title(title) if title else None,
                                "source": "website",
                                "source_url": url,
                                "confidence": 0.75 if name else 0.5,
                            })

                    if page_contacts:
                        logger.info(f"[Website] Found {len(page_contacts)} contacts on {url}")
                        await page.close()
                        await browser.close()
                        return page_contacts

                    await page.close()
                except Exception as e:
                    logger.debug(f"[Website] Failed to fetch {url}: {e}")
                    continue

            await browser.close()

        return contacts

    # ─────────────────────────────────────────
    # 数据源 2: rusprofile.ru
    # ─────────────────────────────────────────

    async def _find_on_rusprofile(self, inn: str, company_name: str) -> List[Dict]:
        """从 rusprofile.ru 找管理层信息"""
        if not PLAYWRIGHT_AVAILABLE:
            return []

        contacts = []
        url = f"https://rusprofile.ru/inn/{inn}"

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=self.headless)
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
                )
                page = await context.new_page()
                await page.goto(url, timeout=15000)
                await page.wait_for_load_state("domcontentloaded")

                html = await page.content()

                # 提取管理者信息（通常在右侧栏）
                # rusprofile 的组织结构页面
                management_url = f"https://rusprofile.ru/management/{inn}"
                await page.goto(management_url, timeout=15000)
                await page.wait_for_load_state("domcontentloaded")
                mgmt_html = await page.content()

                # 解析管理者
                contacts = self._parse_rusprofile_management(mgmt_html, company_name)

                await browser.close()
        except Exception as e:
            logger.debug(f"[Rusprofile] Failed: {e}")

        return contacts

    async def _search_on_yandex(
        self,
        company_name: str,
        domain: Optional[str] = None,
    ) -> List[Dict]:
        """用 Yandex 搜索联系人"""
        if not PLAYWRIGHT_AVAILABLE:
            return []

        contacts = []
        queries = [
            f'"{company_name}" закупки директор email',
            f'"{company_name}" снабженец email',
            f'"{company_name}" отдел закупок email',
            f'"{company_name}" контакты закупки',
        ]

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=self.headless)
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
                )

                for query in queries[:2]:  # 限制搜索次数
                    try:
                        page = await context.new_page()
                        # Yandex 搜索
                        search_url = f"https://yandex.ru/search/?text={query}"
                        await page.goto(search_url, timeout=15000)
                        await page.wait_for_load_state("domcontentloaded")

                        html = await page.content()
                        # 从搜索结果提取邮箱
                        emails = self._extract_emails_from_html(html)
                        for email in emails:
                            if email.endswith(domain) if domain else True:
                                name = self._email_to_name(email)
                                contacts.append({
                                    "name": name,
                                    "email": email,
                                    "title": None,
                                    "title_cn": None,
                                    "source": "yandex",
                                    "source_url": search_url,
                                    "confidence": 0.55,
                                })

                        await page.close()
                    except Exception as e:
                        logger.debug(f"[Yandex] Query failed: {e}")
                        continue

                await browser.close()
        except Exception as e:
            logger.debug(f"[Yandex] Failed: {e}")

        return contacts

    # ─────────────────────────────────────────
    # Email 格式猜测 + Hunter.io 验证
    # ─────────────────────────────────────────

    def _transliterate(self, name: str) -> str:
        """俄语名字转拉丁字母"""
        cyrillic_to_latin = {
            "а": "a", "б": "b", "в": "v", "г": "g", "д": "d",
            "е": "e", "ё": "e", "ж": "zh", "з": "z", "и": "i",
            "й": "y", "к": "k", "л": "l", "м": "m", "н": "n",
            "о": "o", "п": "p", "р": "r", "с": "s", "т": "t",
            "у": "u", "ф": "f", "х": "kh", "ц": "ts", "ч": "ch",
            "ш": "sh", "щ": "shch", "ъ": "", "ы": "y", "ь": "",
            "э": "e", "ю": "yu", "я": "ya",
        }
        result = []
        for c in name.lower():
            result.append(cyrillic_to_latin.get(c, c))
        return "".join(result)

    async def _guess_email_patterns(
        self,
        company_name: str,
        domain: str,
    ) -> List[Dict]:
        """
        猜测可能的邮箱格式
        当知道域名但找不到邮箱时使用
        """
        contacts = []

        # 从公司名提取可能的俄语姓名
        name_parts = re.findall(r'[А-Яа-яЁё]+', company_name)
        if len(name_parts) >= 2:
            last_ru = name_parts[0].lower()
            first_ru = name_parts[1].lower()
        elif len(name_parts) == 1:
            last_ru = name_parts[0].lower()
            first_ru = "ivan"
        else:
            return []

        # 俄语转拉丁字母
        first = self._transliterate(first_ru)
        last = self._transliterate(last_ru)
        first_last = first + last

        patterns = EMAIL_PATTERNS
        for pattern in patterns:
            try:
                email = pattern.format(
                    first=first,
                    last=last,
                    first_last=first_last,
                    domain=domain,
                )
                # 优先验证 info@ / contact@ 等通用邮箱
                generic_patterns = [
                    f"info@{domain}",
                    f"contact@{domain}",
                    f"zakupki@{domain}",  # 采购专用
                    f"snabschik@{domain}",
                ]
                if email in generic_patterns or "{" in email:
                    continue

                contacts.append({
                    "name": None,
                    "email": email,
                    "title": None,
                    "title_cn": None,
                    "source": "pattern",
                    "source_url": None,
                    "confidence": 0.3,  # 猜测的，置信度低
                    "notes": "Email格式猜测，需人工确认",
                })
            except Exception:
                continue

        return contacts[:3]  # 最多返回3个猜测

    # ─────────────────────────────────────────
    # 解析器
    # ─────────────────────────────────────────

    def _extract_contacts_from_text(self, text: str, company_name: str) -> List[Dict]:
        """从页面文本提取联系人"""
        contacts = []

        # 提取邮箱
        emails = re.findall(r'[\w.+-]+@[\w-]+\.[\w.-]+', text)
        emails = [e.lower() for e in emails if self._is_valid_email(e)]

        # 提取俄语全名（2-3个单词，首字母大写）
        names = re.findall(r'[А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+)?', text)

        # 提取电话号码
        phones = re.findall(
            r'\+7\s?[\d]{3}\s?[\d]{3}\s?[\d]{2}\s?[\d]{2}|'
            r'8\s?[\d]{3}\s?[\d]{3}\s?[\d]{2}\s?[\d]{2}|'
            r'[\d\-\(\)\s]{10,}',
            text
        )

        # 为每个邮箱找关联的姓名和职位
        for email in set(emails):
            name = self._find_name_near_email(text, email)
            title = self._find_title_near_text(text, name) if name else None

            # 判断是否是采购相关
            is_procurement = False
            if title:
                title_lower = title.lower()
                for kw in PROCUREMENT_KEYWORDS:
                    if kw in title_lower:
                        is_procurement = True
                        break
                for kw in SKIP_KEYWORDS:
                    if kw in title_lower:
                        is_procurement = False
                        break

            contacts.append({
                "name": name or self._email_to_name(email),
                "email": email,
                "title": title,
                "title_cn": self._translate_title(title) if title else None,
                "department": self._extract_department(text, name) if name else None,
                "phone": self._find_phone_near_text(text, name or email),
                "source": "website",
                "source_url": None,
                "confidence": 0.85 if (name and is_procurement) else 0.6 if name else 0.4,
                "is_procurement": is_procurement,
            })

        return contacts

    def _extract_emails_from_html(self, html: str) -> List[str]:
        """从 HTML 提取邮箱"""
        emails = re.findall(r'[\w.+-]+@[\w-]+\.[\w.-]+', html)
        return [e.lower() for e in emails if self._is_valid_email(e)]

    def _find_name_near_email(self, text: str, email: str) -> Optional[str]:
        """在邮箱附近找关联的姓名"""
        # 找邮箱前后的文本（50个字符内）
        idx = text.lower().find(email.lower())
        if idx == -1:
            return None

        segment = text[max(0, idx-100):idx+100]

        # 找俄语全名（2-3个词，首字母大写）
        names = re.findall(r'[А-ЯЁ][а-яё]{2,15}\s+[А-ЯЁ][а-яё]{2,15}(?:\s+[А-ЯЁ][а-яё]{2,15})?', segment)
        if names:
            return names[0]

        # 尝试在段落中找
        return None

    def _find_title_near_text(self, text: str, name: Optional[str]) -> Optional[str]:
        """在姓名附近找职位"""
        if not name:
            return None

        idx = text.find(name)
        if idx == -1:
            return None

        segment = text[max(0, idx-200):idx+200]

        # 俄语职位常见模式
        title_patterns = [
            r'[А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+\s+—?\s*([А-ЯЁа-яё\s,-]+?)(?:\n|,|$)',
            r'([А-ЯЁ][а-яё\s-]{5,30}директор[а-яё]*)',
            r'([А-ЯЁ][а-яё\s-]{5,30}начальник[а-яё]*)',
            r'([А-ЯЁ][а-яё\s-]{5,30}менеджер[а-яё]*)',
            r'([А-ЯЁ][а-яё\s-]{5,30}специалист[а-яё]*)',
            r'([А-ЯЁ][а-яё\s-]{5,30}закуп[а-яё]*)',
        ]

        for pattern in title_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                title = match.group(1).strip()
                if len(title) > 5:
                    return title[:50]

        return None

    def _find_phone_near_text(self, text: str, keyword: str) -> Optional[str]:
        """在关键词附近找电话号码"""
        if not keyword:
            return None

        idx = text.find(keyword)
        if idx == -1:
            return None

        segment = text[max(0, idx-50):idx+200]

        # 俄罗斯电话格式
        phones = re.findall(
            r'\+7\s?[\d]{3}\s?[\d]{3}\s?[\d]{2}\s?[\d]{2}|'
            r'8\s?[\d]{3}\s?[\d]{3}\s?[\d]{2}\s?[\d]{2}|'
            r'\(?\d{3}\)?[\s-]?\d{3}[\s-]?\d{2}[\s-]?\d{2}',
            segment
        )

        if phones:
            return phones[0].strip()

        return None

    def _extract_department(self, text: str, name: Optional[str]) -> Optional[str]:
        """提取部门"""
        if not name:
            return None

        dept_keywords = [
            "отдел закупок", "отдел снабжения", "закупочный отдел",
            "коммерческий отдел", "отдел продаж", "производственный отдел",
            "технический отдел", "бухгалтерия", "юридический отдел",
        ]

        text_lower = text.lower()
        for dept in dept_keywords:
            if dept in text_lower:
                # 确认部门和姓名在同一区域
                idx = text_lower.find(dept)
                if name in text[max(0,idx-300):idx+300]:
                    return dept

        return None

    def _parse_rusprofile_management(self, html: str, company_name: str) -> List[Dict]:
        """解析 rusprofile 管理层信息"""
        contacts = []

        # rusprofile 的人物卡片通常包含姓名和职位
        # 使用正则提取
        person_blocks = re.findall(
            r'<div[^>]*class="[^"]*(?:person|management|director)[^"]*"[^>]*>(.*?)</div>',
            html, re.IGNORECASE | re.DOTALL
        )

        for block in person_blocks:
            name_match = re.search(r'[А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+', block)
            title_match = re.search(r'(?:должность|position)[^>]*>([^<]+)<', block, re.IGNORECASE)
            email_match = re.search(r'[\w.+-]+@[\w-]+\.[\w.-]+', block)

            if name_match and title_match:
                title = title_match.group(1).strip()
                name = name_match.group(0).strip()

                is_procurement = any(kw in title.lower() for kw in PROCUREMENT_KEYWORDS)

                if not any(kw in title.lower() for kw in SKIP_KEYWORDS):
                    contacts.append({
                        "name": name,
                        "email": email_match.group(0).lower() if email_match else None,
                        "title": title,
                        "title_cn": self._translate_title(title),
                        "source": "rusprofile",
                        "source_url": "https://rusprofile.ru",
                        "confidence": 0.8 if is_procurement else 0.5,
                        "is_procurement": is_procurement,
                    })

        return contacts

    def _deduplicate(self, contacts: List[Dict]) -> List[Dict]:
        """去重"""
        seen = set()
        result = []
        for c in contacts:
            key = (c.get("email") or c.get("name") or "").lower()
            if key and key not in seen:
                seen.add(key)
                result.append(c)
            elif not key:
                result.append(c)
        return result

    # ─────────────────────────────────────────
    # 工具函数
    # ─────────────────────────────────────────

    def _is_valid_email(self, email: str) -> bool:
        """简单验证邮箱格式"""
        if not email or len(email) < 5:
            return False
        if not re.match(r'^[\w.+-]+@[\w-]+\.[\w.-]+$', email):
            return False
        # 排除明显非人用邮箱
        skip_domains = ["yandex.ru/trash", "spam", "example"]
        if any(d in email.lower() for d in skip_domains):
            return False
        return True

    def _is_procurement_related_email(self, email: str, company_name: str) -> bool:
        """判断邮箱是否与采购相关（通过用户名判断）"""
        username = email.split("@")[0].lower()
        procurement_usernames = ["zakup", "snabschik", "zap", "procurement", " снабж"]
        return any(pu in username for pu in procurement_usernames)

    def _email_to_name(self, email: str) -> str:
        """将邮箱转换为俄语姓名格式"""
        username = email.split("@")[0].lower()
        # 移除常见分隔符
        username = username.replace(".", " ").replace("_", " ")
        parts = username.split()
        if len(parts) >= 2:
            return parts[0].capitalize() + " " + parts[1].capitalize()
        return username.capitalize()

    def _translate_title(self, title: Optional[str]) -> Optional[str]:
        """简单翻译俄语职位为中文"""
        if not title:
            return None
        title_lower = title.lower()

        mapping = {
            "директор по закупкам": "采购总监",
            "директор закупок": "采购总监",
            "директор": "总监",
            "руководитель закупок": "采购负责人",
            "начальник отдела закупок": "采购部长",
            "начальник отдела снабжения": "采购部长",
            "начальник": "部长",
            "менеджер по закупкам": "采购经理",
            "менеджер закупок": "采购经理",
            "менеджер": "经理",
            "специалист по закупкам": "采购专员",
            "специалист": "专员",
            "закупщик": "采购员",
            "снабженец": "采购员",
            "коммерческий директор": "商务总监",
            "генеральный директор": "总经理",
            "технический директор": "技术总监",
            "главный инженер": "总工程师",
            "заместитель директора": "副总监",
            "вэд": "进出口经理",
        }

        for ru, cn in mapping.items():
            if ru in title_lower:
                return cn

        return "其他"

    def _normalize_phone(self, phone: str) -> str:
        """标准化俄罗斯电话格式"""
        digits = re.sub(r'\D', '', phone)
        if digits.startswith('8') and len(digits) == 11:
            digits = '7' + digits[1:]
        if not digits.startswith('7'):
            return phone
        if len(digits) == 11:
            return f"+7 ({digits[1:4]}) {digits[4:7]}-{digits[7:9]}-{digits[9:11]}"
        return phone
