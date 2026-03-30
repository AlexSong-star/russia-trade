"""
通用工具函数
"""

import re
import logging
import os
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)

# 飞书配置（从环境变量读取）
FEISHU_APP_ID = os.getenv("FEISHU_APP_ID", "")
FEISHU_APP_SECRET = os.getenv("FEISHU_APP_SECRET", "")
FEISHU_TABLE_ID = os.getenv("FEISHU_TABLE_ID", "tbl4Qdl0yuvtI6dt")  # 测试-客户主表
FEISHU_APP_TOKEN = os.getenv("FEISHU_APP_TOKEN", "UxEmbaiGxaP9RKsQqi3cTW9Dnug")
FEISHU_BASE_URL = "https://open.feishu.cn/open-apis"


def get_feishu_token() -> Optional[str]:
    """获取飞书tenant_access_token"""
    if not FEISHU_APP_ID or not FEISHU_APP_SECRET:
        logger.warning("未配置 FEISHU_APP_ID 或 FEISHU_APP_SECRET")
        return None
    import requests
    url = f"{FEISHU_BASE_URL}/auth/v3/tenant_access_token/internal"
    resp = requests.post(url, json={
        "app_id": FEISHU_APP_ID,
        "app_secret": FEISHU_APP_SECRET
    }, timeout=10)
    if resp.status_code == 200:
        data = resp.json()
        if data.get("code") == 0:
            return data["tenant_access_token"]
    logger.error(f"获取token失败: {resp.text}")
    return None


def write_to_feishu(companies: List[Dict]) -> Dict:
    """
    将公司数据写入飞书多维表格（测试-客户主表）

    Args:
        companies: [{"name": "...", "url": "...", "category": "..."}, ...]

    Returns:
        {"success": bool, "written": int, "errors": []}
    """
    import requests

    token = get_feishu_token()
    if not token:
        return {"success": False, "written": 0, "errors": ["无access_token"]}

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    written = 0
    errors = []

    for i, company in enumerate(companies):
        # 生成客户ID
        prefix = "metaprom"
        seq = str(i + 1).zfill(3)
        customer_id = f"{prefix}-{seq}"

        # 提取公司简称（去掉ООО/ЗАО等）
        short_name = re.sub(
            r'^(ООО|ЗАО|ООО\s+|ПАО|AO|Inc\.?\s*)',
            '', company["name"], flags=re.IGNORECASE
        ).strip()

        # 渠道链接文本
        channel_url = company.get("url", "")

        # 判断客户分类
        cat_lower = (company.get("category", "") + " " + company.get("name", "")).lower()
        if any(kw in cat_lower for kw in ["завод", "комбинат", "производствен", "литейн"]):
            cust_class = "B"
        elif any(kw in cat_lower for kw in ["огнеупор", "валок", "кристаллизатор", "мнлз"]):
            cust_class = "A"
        else:
            cust_class = "C"

        payload = {
            "fields": {
                "客户ID": customer_id,
                "公司名称": short_name,
                "客户分类": cust_class,
                "所在渠道": "metaprom",
                "渠道链接文本": channel_url,
                "官网文本": "",
                "地址": "",
                "规模": "中型",
                "开发状态": "待联系",
            }
        }

        url = f"{FEISHU_BASE_URL}/bitable/v1/apps/{FEISHU_APP_TOKEN}/tables/{FEISHU_TABLE_ID}/records"
        resp = requests.post(url, headers=headers, json=payload, timeout=15)

        if resp.status_code == 200:
            data = resp.json()
            if data.get("code") == 0:
                written += 1
                logger.info(f"[{i+1}] 写入成功: {short_name}")
            else:
                err = f"[{i+1}] API错误 {data.get('code')}: {data.get('msg', '')}"
                errors.append(err)
                logger.warning(err)
        else:
            err = f"[{i+1}] HTTP {resp.status_code}: {resp.text[:100]}"
            errors.append(err)
            logger.warning(err)

    logger.info(f"写入完成: {written}/{len(companies)} 条")
    return {"success": written == len(companies), "written": written, "errors": errors}


def clean_company_name(name: str) -> str:
    """清理公司名称，去除多余字符"""
    if not name:
        return ""
    # 去除首尾空白
    name = name.strip()
    # 去除常见前缀后缀
    name = re.sub(r'^(ООО|ЗАО|ООО\s+)', '', name, flags=re.IGNORECASE)
    return name


def clean_phone(phone: str) -> Optional[str]:
    """清理电话号码"""
    if not phone:
        return None
    # 只保留数字和常见分隔符
    cleaned = re.sub(r'[^\d\+\-\(\)\s]', '', phone)
    return cleaned.strip() if cleaned else None


def clean_email(email: str) -> Optional[str]:
    """清理邮箱地址"""
    if not email:
        return None
    email = email.strip().lower()
    if '@' in email and '.' in email.split('@')[1]:
        return email
    return None


def is_valid_website(url: str) -> bool:
    """检查是否是有效的网站URL"""
    if not url:
        return False
    url = url.strip().lower()
    # 必须是 http 或 https 开头
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    # 检查域名格式
    domain_match = re.match(r'https?://([a-zA-Z0-9\-\.]+\.[a-zA-Z]{2,})', url)
    if domain_match:
        domain = domain_match.group(1)
        # 排除搜索引擎和社交媒体域名
        excluded = ['google', 'yandex', 'bing', 'yahoo', 'facebook', 'instagram',
                    'vk.com', 'linkedin', 'twitter']
        return not any(ex in domain for ex in excluded)
    return False


def extract_domain(url: str) -> Optional[str]:
    """从 URL 提取域名"""
    if not url:
        return None
    match = re.search(r'https?://([^/\s]+)', url)
    return match.group(1) if match else None


def parse_address(address: str) -> dict:
    """
    解析俄罗斯地址
    返回: {city, region, street, building}
    """
    if not address:
        return {}

    parts = address.strip().split(',')
    result = {}

    # 简单解析：假设格式为 "城市, 区域, 街道, 建筑"
    if len(parts) >= 1:
        result['raw'] = address
    if len(parts) >= 2:
        result['city'] = parts[0].strip()
        result['region'] = parts[1].strip()
    if len(parts) >= 3:
        result['street'] = parts[2].strip()

    return result
