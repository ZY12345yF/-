"""
integrations.tencent — 腾讯财经接口

  quote   实时行情批量查询 (fetch_change_pct)
  names   代码→名称兜底缓存 + 文本中代码提取 + 行情追加
"""
from .quote import fetch_change_pct
from .names import (fetch_stock_names, extract_linked_codes,
                     append_realtime_data)

__all__ = [
    "fetch_change_pct", "fetch_stock_names",
    "extract_linked_codes", "append_realtime_data",
]
