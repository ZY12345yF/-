"""
core/api_client.py — 向后兼容 shim (v9.9.8 Phase 2)

原 729 行已按职责拆分到 integrations/:

    integrations/eastmoney/
      _http.py        — Session + 节流 + 重试 (em_get, set_em_proxy)
      sectors.py      — fetch_sectors, fetch_sector_stocks
      limit_up.py     — fetch_limit_up_stocks
      market.py       — fetch_all_market_stocks

    integrations/tencent/
      quote.py        — fetch_change_pct
      names.py        — fetch_stock_names, extract_linked_codes, append_realtime_data

    integrations/qianfan/
      client.py       — call_qianfan, _is_volcano_endpoint

本文件保留是为了让现存 `from ..core import api_client` 和
`api_client.fetch_sectors(...)` 等所有调用方零改动。

未来确认所有 import 都已切到 integrations 后,可以删除本 shim。
"""
# 东方财富
from ..integrations.eastmoney._http import (
    em_get as _em_get,         # 模块级私有名也透传(以防有人直接调)
    set_em_proxy,
)
# 也暴露公共版本
from ..integrations.eastmoney import (
    fetch_sectors, fetch_sector_stocks,
    fetch_limit_up_stocks,
    fetch_all_market_stocks,
)
# 腾讯
from ..integrations.tencent import (
    fetch_change_pct, fetch_stock_names,
    extract_linked_codes, append_realtime_data,
)
from ..integrations.tencent.quote import _get_market_prefix
from ..integrations.tencent.names import (
    _name_cache_path, _load_name_cache, _save_name_cache,
)
# 千帆
from ..integrations.qianfan.client import call_qianfan, _is_volcano_endpoint, _is_qianfan_endpoint

__all__ = [
    # 东方财富
    "set_em_proxy",
    "fetch_sectors", "fetch_sector_stocks",
    "fetch_limit_up_stocks",
    "fetch_all_market_stocks",
    # 腾讯
    "fetch_change_pct", "fetch_stock_names",
    "extract_linked_codes", "append_realtime_data",
    # 千帆
    "call_qianfan",
]
