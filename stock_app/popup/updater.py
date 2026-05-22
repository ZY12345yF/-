"""
QuoteUpdater — 浮窗行情异步刷新

原 popup_window.py 里 _fetch_quote / _refresh_quote。

抽离后:
  • 不依赖 PopupWindow,接收回调 (on_result)
  • 走 TaskManager (Phase 1 暂时还用 threading.Thread,完全等价)
  • 调用方拿到 result 后自己负责更新 UI (派回主线程)

接口:
  fetch(code, on_result)  异步取行情,on_result(info_dict_or_None)
"""
import threading

from ..core import api_client
from ..infrastructure.logging import get_logger

log = get_logger(__name__)


class QuoteUpdater:
    """
    无状态的行情拉取器。每次 fetch 都是一个独立 worker 线程。

    Phase 2 计划:
      • 限流: 同一只股 1s 内连续 fetch 合并成一次
      • 缓存: 行情 5s TTL
      • 走 TaskManager 而非裸 threading.Thread
    """

    def fetch(self, code, on_result):
        """
        异步拉取 code 的行情。

        on_result(info) 会在 worker 线程触发,info 是 api_client 返回的 dict
        或 None (表示无数据)。调用方负责派回主线程更新 UI。
        """
        if not code:
            return
        t = threading.Thread(
            target=self._worker, args=(code, on_result),
            name="quote:" + str(code), daemon=True)
        t.start()

    def _worker(self, code, on_result):
        try:
            data = api_client.fetch_change_pct([code])
        except Exception:
            log.exception("fetch_change_pct failed for %s", code)
            data = {}
        info = data.get(code) or data.get(str(code).zfill(6))
        try:
            on_result(info)
        except Exception:
            log.exception("on_result callback failed for %s", code)
