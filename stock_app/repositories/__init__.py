"""
repositories/ — 数据访问层 (v9.9.8 Phase 2)

按文档 九·Repository 层规范:
    > Repository 只负责: sqlite / json 文件 / HTTP API / 缓存
    > Repository 不允许写业务逻辑
    > Repository 不允许操作 UI

本包暂时与 stock_app/core/* 内的数据访问模块并存,采用 OO 封装。

迁移路径 (渐进式,不破坏现存代码):
  • core/history.py 等模块仍存在,所有现存 `from .core import history` 不破
  • 新业务代码用 `from ..repositories import HistoryRepository`
  • 等所有调用方都迁过来后,core/* 改成 shim 转发到这里
"""
from .history_repository import HistoryRepository, history_repo
from .sector_repository import SectorRepository, sector_repo

__all__ = [
    "HistoryRepository", "history_repo",
    "SectorRepository", "sector_repo",
]
