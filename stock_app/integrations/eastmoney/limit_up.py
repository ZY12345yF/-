"""
integrations.eastmoney.limit_up — 东方财富涨停板 / 涨幅榜

从 core/api_client.py L358-413 迁入,行为不变。
"""
import time
from ._http import em_get


def fetch_limit_up_stocks(min_pct=9.5, max_pages=5):
    """
    分页拉取涨停/接近涨停股票列表
    - min_pct:   最低涨幅过滤,默认 9.5%
    - max_pages: 最多页数,每页 100 条(默认5页=最多500条)
    """
    PAGE_SIZE = 100
    url = "http://push2.eastmoney.com/api/qt/clist/get"
    base_params = {
        "pz": PAGE_SIZE, "po": 1, "np": 1,
        "fltt": 2, "invt": 2, "fid": "f3",
        "fs": ("m:0+t:6+f:!2,m:0+t:13+f:!2,m:0+t:80+f:!2,"
               "m:1+t:2+f:!2,m:1+t:23+f:!2,m:0+t:7+f:!2,m:1+t:3+f:!2"),
        "fields": "f12,f14,f2,f3,f4,f5,f15,f16,f17,f18",
    }
    result = []
    seen   = set()
    try:
        for page in range(1, max_pages + 1):
            params = dict(base_params)
            params["pn"] = page
            params["_"]  = int(time.time() * 1000)
            resp  = em_get(url, params=params, timeout=15, min_interval=0.6)
            body  = resp.json().get("data", {}) or {}
            items = body.get("diff", [])
            if not items:
                break
            for it in items:
                try:
                    chg = float(it.get("f3", 0))
                    if chg < min_pct:
                        return result   # 按涨幅降序,低于阈值后面也不用抓了
                    code = str(it.get("f12", "")).zfill(6)
                    if code in seen:
                        continue
                    seen.add(code)
                    result.append({
                        "code":       code,
                        "name":       it.get("f14", ""),
                        "price":      float(it.get("f2", 0)),
                        "change_pct": chg,
                        "open":       float(it.get("f17", 0)),
                        "high":       float(it.get("f15", 0)),
                        "low":        float(it.get("f16", 0)),
                    })
                except (TypeError, ValueError):
                    continue
            if len(items) < PAGE_SIZE:
                break
        return result
    except Exception as e:
        return {"error": str(e)}
