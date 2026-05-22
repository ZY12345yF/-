"""
SectorRepository — 板块数据访问

包装两个底层模块:
  • core.sector_snapshot  — 板块快照 CRUD (纯数据访问)
  • core.sector           — 板块"历史搜索 / Top 概念抽取" (跨数据源查询,
                            性质属于 Repository 而非 Service)
  • core.api_client       — 板块榜单 / 成份股 / 涨停涨幅榜 (远程 API,
                            性质属于 Repository → 将来迁到
                            integrations/eastmoney/)

切勿放进本 Repository 的:
  • 板块强度评分计算   → 业务规则,归 Service
  • 龙头梯队识别       → 业务规则,归 Service
  • 增量保存的流程编排 → 业务流程,归 Service

跟 history_repository 的设计完全一致 — Repository 是 stateless 的,
方法体只做"调底层 + 透传"。
"""
from ..core import sector as sector_core
from ..core import sector_snapshot as snap_mod
from ..core import api_client


class SectorRepository:
    """板块数据访问对象。所有底层调用都在这里收口。"""

    # ── 快照 CRUD (本地 json 文件) ────────────────────
    def list_snapshot_dates(self):
        """返回所有已有快照的日期 key 列表 ['20260513', ...] 新→旧"""
        return snap_mod.list_dates()

    def today_key(self):
        """今日的 date key,e.g. '20260513'"""
        return snap_mod.today_key()

    def format_date_label(self, date_key):
        """date_key → '今日（实时）' / '昨日 20260512' 等显示标签。"""
        return snap_mod.format_date_label(date_key)

    def load_snapshot(self, date_key):
        """加载指定日期快照,返回 payload dict 或 None。"""
        return snap_mod.load_snapshot(date_key)

    def save_snapshot(self, payload, date_key=None):
        """保存快照。date_key=None 则用 today_key()。"""
        return snap_mod.save_snapshot(payload, date_key)

    def delete_snapshot(self, date_key):
        return snap_mod.delete_snapshot(date_key)

    # ── 历史查询 (跨快照搜索 + history.json 搜索) ─────
    def search_in_history(self, sector_name, days=180):
        """
        在最近 N 天里搜索某板块的"历史表现"。
        返回 list[dict]:每个元素是某天该板块的简略快照数据。
        """
        return sector_core.search_sector_in_history(sector_name, days=days)

    def extract_top_concepts(self, date_key, top_n=15):
        """从某天的快照中抽出涨幅 Top N 概念板块。"""
        return sector_core.extract_top_concepts(date_key, top_n=top_n)

    # ── 远程 API (东方财富) ────────────────────────────
    # 将来这部分会迁到 integrations/eastmoney/,Repository 改为转发
    def fetch_sectors(self, sector_type, top_n=200):
        """
        拉取板块榜单。
        Args:
            sector_type: 'industry' 或 'concept'
            top_n:       拉前 N 个 (按涨幅排序)
        Returns:
            list[dict] 板块榜单 or {'error': str}
        """
        return api_client.fetch_sectors(sector_type, top_n=top_n)

    def fetch_sector_stocks(self, sector_code, top_n=200):
        """拉取某板块成份股。返回 list[dict] 或 {'error': str}。"""
        return api_client.fetch_sector_stocks(sector_code, top_n=top_n)

    def fetch_limit_up_stocks(self, min_pct=9.5, max_pages=5):
        """
        拉取涨停 / 涨幅榜单 (雷达用)。
        Returns: list[dict] 或 {'error': str}
        """
        return api_client.fetch_limit_up_stocks(
            min_pct=min_pct, max_pages=max_pages)


# 全局单例
sector_repo = SectorRepository()
