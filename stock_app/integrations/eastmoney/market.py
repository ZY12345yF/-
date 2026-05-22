"""
integrations.eastmoney.market — 东方财富全市场行情快照

从 core/api_client.py L663-730 迁入,行为不变。
"""
import time
from ._http import em_get


def fetch_all_market_stocks(on_progress=None):
    """
    分页拉取全市场 A 股行情(含北交所)。

    ⚠️ 历史教训:旧版本用 pz=6000 单次请求触发了东财 WAF 黑名单。
       现改为 pz=200 分页 + em_get 全局节流(默认 0.8s 间隔)。
    返回 [{"code","name","price","change_pct","high","low","prev_close"}, ...]
    """
    url = "http://push2.eastmoney.com/api/qt/clist/get"
    fs = ("m:0+t:6+f:!2,m:0+t:13+f:!2,m:0+t:80+f:!2,m:0+t:7+f:!2,"
          "m:1+t:2+f:!2,m:1+t:23+f:!2,m:1+t:3+f:!2,m:0+t:81+f:!2")

    PAGE_SIZE = 200          # 不要超过 200
    MAX_PAGES = 30           # 30*200 = 6000 上限
    all_stocks = []
    seen = set()

    try:
        for page in range(1, MAX_PAGES + 1):
            params = {
                "pn": page, "pz": PAGE_SIZE, "po": 1, "np": 1,
                "fltt": 2, "invt": 2, "fid": "f3",
                "fs": fs,
                "fields": "f12,f14,f2,f3,f15,f16,f18",
                "_": int(time.time() * 1000),
            }
            if on_progress:
                on_progress(page, MAX_PAGES)

            resp  = em_get(url, params=params, timeout=20, min_interval=0.8)
            body  = resp.json().get("data", {}) or {}
            items = body.get("diff", []) or []
            if not items:
                break

            for it in items:
                try:
                    code = str(it.get("f12", "")).zfill(6)
                    if not code or code in seen:
                        continue
                    # 过滤退市股、停牌无数据等
                    name = it.get("f14", "")
                    if not name or code.startswith(("9", "2")):
                        continue
                    price = float(it.get("f2", 0))
                    if price <= 0:
                        continue
                    seen.add(code)
                    all_stocks.append({
                        "code":        code,
                        "name":        name,
                        "price":       price,
                        "change_pct":  float(it.get("f3", 0)),
                        "high":        float(it.get("f15", 0)),
                        "low":         float(it.get("f16", 0)),
                        "prev_close":  float(it.get("f18", 0)),
                    })
                except (TypeError, ValueError):
                    continue

            # 不足一页 → 已到末尾
            if len(items) < PAGE_SIZE:
                break

        return all_stocks
    except Exception as e:
        return {"error": str(e)}
