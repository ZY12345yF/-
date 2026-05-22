"""
SectorService — 板块 Tab 的业务逻辑层

把 sector_tab.py 里业务密集的方法抽出为纯业务函数:

  sector_tab._refresh (125 行,流程编排)
      → SectorRefreshService.refresh
  sector_tab._render_sector_detail 中的"取强度+梯队+历史"3 行
      → SectorAnalysisService.analyze
  sector_tab._save_partial_on_close
      → SectorRefreshService.save_partial  (薄包装)

设计原则跟 history_service 一致:
  • Service 不 import tkinter / messagebox
  • 进度反馈走 on_status(msg) / on_progress(done, total) callback
  • UI 派回主线程是 Tab 的事 (state.ui_queue.put)
  • 异常往外抛或通过状态消息传递
"""
import time

from ..core import sector as sector_core
from ..repositories import sector_repo
from ..infrastructure.logging import get_logger

log = get_logger(__name__)


# ════════════════════════════════════════════════════════
# 1. 板块强度评分 + 梯队识别 + 历史查询 (组合)
# ════════════════════════════════════════════════════════
class SectorAnalysisService:
    """
    用户在板块榜上选中一只板块后,Tab 要展示三块内容:
      ① 强度评分 + breakdown 卡片
      ② 龙头梯队 (从板块成份股识别)
      ③ 历史表现 (最近 180 天该板块出现过几次)

    本 Service 把这 3 个计算合一,返回结构化结果。
    """

    def __init__(self, repo=None):
        self._repo = repo or sector_repo

    def analyze(self, sector, stocks, history_days=180):
        """
        Args:
            sector:  dict 来自板块榜单的一行
            stocks:  list[dict] 该板块的成份股
            history_days: 历史回溯天数

        Returns:
            dict {
                'score':       int 0-100,
                'breakdown':   dict 评分 breakdown,
                'ladder':      list[dict] 梯队,
                'history':     list[dict] 历史表现,
                'total_stocks': int,
            }
        """
        score, breakdown = sector_core.calc_sector_strength(sector, stocks)
        ladder = sector_core.identify_ladder(stocks)
        history = self._repo.search_in_history(
            sector['name'], days=history_days)
        return {
            'score':       score,
            'breakdown':   breakdown,
            'ladder':      ladder,
            'history':     history,
            'total_stocks': len(stocks),
        }


# ════════════════════════════════════════════════════════
# 2. 板块刷新 — 长流程,增量保存
# ════════════════════════════════════════════════════════
class SectorRefreshService:
    """
    板块刷新流程:
      ① 拉板块榜单                  → 早渲染
      ② 逐个板块拉成份股            → 每 BATCH 个增量保存
      ③ 拉涨停 / 涨幅榜             → 雷达数据
      ④ 终保存快照
    全程通过 callback 反馈状态,UI 派回主线程的事留给调用方。

    与原 _refresh() 行为一致:增量保存、失败板块剔除、雷达参数透传。
    """

    BATCH_SAVE_EVERY = 10  # 每拉 10 个板块增量保存一次

    def __init__(self, repo=None):
        self._repo = repo or sector_repo

    def refresh(self, sector_type, radar_min_pct, radar_pages,
                on_status=None,
                on_sectors_loaded=None,
                on_partial_progress=None):
        """
        完整刷新流程,在 worker 线程里调用 (本方法是阻塞的)。

        Args:
            sector_type:   'industry' / 'concept'
            radar_min_pct: float
            radar_pages:   int
            on_status(msg: str):           状态文字变化
            on_sectors_loaded(sectors):    板块榜单拉到后立即触发,允许早渲染
            on_partial_progress(stocks_by_sector, done, total, failed):
                                           每次增量保存后触发,允许 Tab 同步内存

        Returns:
            dict {
                'sectors':           list,
                'stocks_by_sector':  dict {code: list[stock]},
                'radar':             list,
                'failed_codes':      list[str],
                'date_key':          str,
                'saved_ok':          bool,
                'save_error':        str or None,
            }
            如果拉板块榜单失败,返回 {'error': ...}。
        """
        def _status(msg):
            if on_status:
                try: on_status(msg)
                except Exception: log.exception("on_status callback failed")

        # ── 1. 板块榜单 ─────────────────────────────
        _status("⏳ 正在拉取板块榜单...")
        sectors = self._repo.fetch_sectors(sector_type, top_n=200)
        if isinstance(sectors, dict) and 'error' in sectors:
            return {'error': sectors['error']}

        today = self._repo.today_key()
        if on_sectors_loaded:
            try: on_sectors_loaded(sectors, today)
            except Exception: log.exception("on_sectors_loaded failed")

        _status("⏳ 板块榜单 {} 个已加载,正在拉成份股...".format(len(sectors)))

        # ── 2. 增量拉成份股 ─────────────────────────
        stocks_by_sector = {}
        failed_codes = []
        total = len(sectors)
        for i, s in enumerate(sectors):
            code = s.get('code', '')
            stocks = self._repo.fetch_sector_stocks(code, top_n=200)
            if isinstance(stocks, list) and stocks:
                stocks_by_sector[code] = stocks
            else:
                # 失败板块剔除(行为跟原版 Q3 选 1 一致)
                failed_codes.append(s.get('name', code))

            if (i + 1) % self.BATCH_SAVE_EVERY == 0 or i == total - 1:
                msg = "⏳ 已拉 {}/{} 个板块(成功 {},失败 {})".format(
                    i + 1, total, len(stocks_by_sector), len(failed_codes))
                _status(msg)
                # 增量保存
                partial_payload = {
                    "type":            sector_type,
                    "sectors":         sectors,
                    "stocks_by_sector": dict(stocks_by_sector),
                    "radar":           [],
                    "radar_params":    {"min_pct": radar_min_pct,
                                         "pages":   radar_pages},
                    "progress":        {"done":   i + 1,
                                          "total":  total,
                                          "failed": list(failed_codes)},
                }
                try:
                    self._repo.save_snapshot(partial_payload, today)
                except Exception:
                    log.exception("partial save_snapshot failed")
                if on_partial_progress:
                    try:
                        on_partial_progress(
                            dict(stocks_by_sector),
                            i + 1, total, list(failed_codes))
                    except Exception:
                        log.exception("on_partial_progress failed")

        # ── 3. 涨停 / 涨幅榜 (雷达) ─────────────────
        _status(
            "⏳ 成份股全部拉完({} 成功 / {} 失败),正在拉涨幅榜...".format(
                len(stocks_by_sector), len(failed_codes)))
        radar = self._repo.fetch_limit_up_stocks(
            min_pct=radar_min_pct, max_pages=radar_pages)
        if isinstance(radar, dict) and 'error' in radar:
            radar = []

        # ── 4. 终保存 ─────────────────────────────
        payload = {
            "type":            sector_type,
            "sectors":         sectors,
            "stocks_by_sector": stocks_by_sector,
            "radar":           radar,
            "radar_params":    {"min_pct": radar_min_pct,
                                 "pages":   radar_pages},
            "progress":        {"done":   total,
                                  "total":  total,
                                  "failed": failed_codes},
        }
        saved_ok = True
        save_error = None
        try:
            self._repo.save_snapshot(payload, today)
        except Exception as e:
            saved_ok = False
            save_error = str(e)
            log.exception("final save_snapshot failed")

        return {
            'sectors':           sectors,
            'stocks_by_sector':  stocks_by_sector,
            'radar':             radar,
            'failed_codes':      failed_codes,
            'date_key':          today,
            'saved_ok':          saved_ok,
            'save_error':        save_error,
        }

    def save_partial(self, payload, date_key=None):
        """
        主程序关闭时的兜底保存。Tab 在 _save_partial_on_close 调用。
        薄包装 — 失败静默,不抛出 (关闭流程不能因此卡住)。
        """
        try:
            self._repo.save_snapshot(payload,
                date_key or self._repo.today_key())
            return True
        except Exception:
            log.exception("save_partial failed")
            return False


# ════════════════════════════════════════════════════════
# 3. 按需补拉成份股 (Tab 选中一个板块但内存没数据时)
# ════════════════════════════════════════════════════════
class SectorStocksSupplyService:
    """
    用户点了一个板块,内存没成份股 (e.g. 从历史快照加载、增量保存进行中
    时点了未完成的板块) → 临时去拉一次。

    跟 SectorRefreshService 不同的是:
      • 这是单板块、即时、不保存
      • 用于点击后填充,不影响整体快照
    """

    def __init__(self, repo=None):
        self._repo = repo or sector_repo

    def supply(self, sector_code):
        """
        Args:
            sector_code: 板块代码
        Returns:
            list[dict] 成份股,或 [] (失败)
        """
        stocks = self._repo.fetch_sector_stocks(sector_code, top_n=200)
        return stocks if isinstance(stocks, list) else []
