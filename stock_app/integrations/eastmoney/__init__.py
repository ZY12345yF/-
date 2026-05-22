"""
integrations.eastmoney — 东方财富数据接口

  _http     共用 HTTP 层 (Session + 节流 + 重试)
  sectors   板块榜单 + 板块成份股
  limit_up  涨停板 / 涨幅榜
  market    全市场行情快照

所有函数原本住在 core/api_client.py,Phase 2 拆出。core/api_client.py 现在
是 shim,继续支持 from .core import api_client; api_client.fetch_sectors(...)
"""
from ._http import em_get, set_em_proxy
from .sectors import fetch_sectors, fetch_sector_stocks
from .limit_up import fetch_limit_up_stocks
from .market import fetch_all_market_stocks

__all__ = [
    "em_get", "set_em_proxy",
    "fetch_sectors", "fetch_sector_stocks",
    "fetch_limit_up_stocks",
    "fetch_all_market_stocks",
]
