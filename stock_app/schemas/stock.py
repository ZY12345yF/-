"""
股票数据 Schema — 统一的内外数据交换格式
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class StockBasicInfo:
    """股票基础信息"""
    code: str = ""
    name: str = ""
    market: str = ""          # sh / sz / bj
    industry: str = ""
    sector: str = ""
    list_date: str = ""


@dataclass
class StockSnapshot:
    """股票实时快照"""
    code: str = ""
    name: str = ""
    price: float = 0.0
    change_pct: float = 0.0      # 涨跌幅 %
    volume: float = 0.0          # 成交量(手)
    amount: float = 0.0          # 成交额(万元)
    turnover: float = 0.0        # 换手率 %
    high: float = 0.0
    low: float = 0.0
    open: float = 0.0
    pre_close: float = 0.0
    limit_up: float = 0.0        # 涨停价
    limit_down: float = 0.0      # 跌停价
    limit_up_times: int = 0      # 连板数
    first_limit_up_time: str = ""  # 首次涨停时间
    sector_tags: list = field(default_factory=list)
    fetched_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class ConceptNode:
    """概念图谱节点"""
    name: str = ""
    weight: float = 1.0          # 当前热度权重
    parent: Optional[str] = None
    children: list = field(default_factory=list)
    stocks: list = field(default_factory=list)  # 关联股票代码
    aliases: list = field(default_factory=list)  # 别名
    decay_rate: float = 0.05     # 热度衰减率(每日)
    last_updated: str = field(default_factory=lambda: datetime.now().isoformat())
