"""
services/ — 业务逻辑层 (v9.9.8 Phase 2)

按文档 八·服务层规范:
    > Service 负责: 业务规则 / 数据整合 / 副作用编排 / 外部接口协调
    > Service 内不允许写 UI / import tkinter

本包目前包含:
    history_service.py
        BatchRequeryService    — 批量重查行情 (从 history_tab._do_batch_requery 抽出)
        DailyQuotesExporter    — 当日历史 + 行情导出 Excel
        ContentEditService     — 从详情面板文本回写历史 (从 detail_view._do_save_content_to_history 抽出)
        StarredExportService   — 星标导出包装

业务逻辑跟 UI 完全解耦 — 进度反馈通过 callback,UI 弹框由调用方负责。
"""
from .history_service import (
    BatchRequeryService,
    DailyQuotesExporter,
    ContentEditService,
    StarredExportService,
)
from .sector_service import (
    SectorAnalysisService,
    SectorRefreshService,
    SectorStocksSupplyService,
)

__all__ = [
    "BatchRequeryService",
    "DailyQuotesExporter",
    "ContentEditService",
    "StarredExportService",
    "SectorAnalysisService",
    "SectorRefreshService",
    "SectorStocksSupplyService",
]
