"""
VK 搜索器 (vk.com)
通过 VK API 搜索产品相关公司/群组/供应商
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import json
import logging
from typing import List, Optional

from models import CompanyInfo

logger = logging.getLogger(__name__)

VK_TOKEN_FILE = "/Users/jarvis/.openclaw/workspace/projects/russia-trade/code/russia-trade-contacts/vk_token.json"


def _get_vk_token() -> Optional[str]:
    """读取 VK access_token"""
    try:
        with open(VK_TOKEN_FILE) as f:
            return json.load(f).get("access_token")
    except Exception:
        return None


def _vk_api(method: str, params: dict) -> dict:
    """调用 VK API"""
    token = _get_vk_token()
    if not token:
        logger.warning("VK token 未找到，跳过 VK 搜索")
        return {}
    import urllib.request
    import urllib.parse
    ps = urllib.parse.urlencode(params)
    url = f"https://api.vk.com/method/{method}?{ps}&access_token={token}&v=5.131"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            return json.loads(resp.read())
    except Exception as e:
        logger.warning(f"VK API {method} 失败: {e}")
        return {}


def search_vk_companies(keywords: List[str]) -> List[CompanyInfo]:
    """
    通过 VK 搜索产品相关公司/群组
    
    搜索策略：
    1. groups.search — 搜产品/厂商相关的公开群组/公众页面
    2. 过滤掉非俄罗斯、非厂商的群组
    
    返回: List[CompanyInfo]
    """
    results = []
    seen = set()
    
    for kw in keywords:
        # 搜索相关群组
        s = _vk_api("groups.search", {"q": kw, "type": "group", "count": 10})
        items = s.get("response", {}).get("items", [])
        
        for item in items:
            gid = item.get("id")
            name = item.get("name", "")
            screen_name = item.get("screen_name", "")
            is_closed = item.get("is_closed", 1)
            # is_closed: 0=开放, 1=封闭, 2=私有
            if is_closed == 1:
                continue  # 跳过封闭群组
            
            # 去重（同一公司不同关键词）
            key = screen_name or str(gid)
            if key in seen:
                continue
            seen.add(key)
            
            # 提取域名
            website = f"https://vk.com/{screen_name}" if screen_name else None
            
            # 获取成员数，判断规模
            ginfo = _vk_api("groups.getById", {"group_id": gid, "fields": "members_count,description,site"})
            resp_items = ginfo.get("response", [])
            if resp_items:
                g = resp_items[0]
                members = g.get("members_count", 0)
                desc = g.get("description", "")
                site = g.get("site", "")
                
                # 过滤：成员太少不是正经厂商
                if members and members < 50:
                    continue
                
                results.append(CompanyInfo(
                    name=name,
                    website=site or website,
                    address="",
                    phone="",
                    source_channel="VK",
                    source_url=website,
                    description=desc[:300] if desc else "",
                ))
        
        # 同时搜索公司（type=page）
        sp = _vk_api("groups.search", {"q": kw, "type": "page", "count": 5})
        sp_items = sp.get("response", {}).get("items", [])
        for item in sp_items:
            screen_name = item.get("screen_name", "")
            name = item.get("name", "")
            key = screen_name or name
            if key in seen:
                continue
            seen.add(key)
            results.append(CompanyInfo(
                name=name,
                website=f"https://vk.com/{screen_name}" if screen_name else None,
                address="",
                phone="",
                source_channel="VK",
                source_url=f"https://vk.com/{screen_name}" if screen_name else None,
            ))

    logger.info(f"VK 搜索 [{keywords}] → 找到 {len(results)} 个公司/群组")
    return results


# 快速测试
if __name__ == "__main__":
    companies = search_vk_companies(["Валки прокатные", "Прокатный стан"])
    for c in companies[:10]:
        print(f"  [{c.source_channel}] {c.name} | {c.website} | 成员: {c.description[:50]}")
