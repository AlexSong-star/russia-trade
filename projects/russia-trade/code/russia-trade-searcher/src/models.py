"""
共享数据模型
"""

from dataclasses import dataclass, asdict
from typing import Optional, List, Dict


@dataclass
class CompanyInfo:
    """公司基本信息"""
    name: str                          # 公司名称
    website: Optional[str] = None      # 官网
    address: Optional[str] = None      # 地址
    source_channel: Optional[str] = None  # 来源渠道
    source_url: Optional[str] = None  # 来源页面URL
    products: Optional[List[str]] = None  # 主营产品
    phone: Optional[str] = None        # 电话
    email: Optional[str] = None       # 邮箱
    extra: Optional[Dict] = None      # 其他信息

    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v is not None}
