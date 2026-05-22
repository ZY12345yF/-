"""
integrations.eastmoney.sectors — 东方财富板块接口

从 core/api_client.py L532-657 整体迁入,函数体一字不改。
"""
import time

from ._http import em_get


def fetch_sectors(sector_type="concept", top_n=200):
    """
    拉取板块列表(行业/概念)
    - sector_type: "concept" 概念板块 / "industry" 行业板块
    - top_n: 最多返回多少个板块(按涨幅降序)
    返回 [{"code","name","change_pct","price_change","turnover","amount",
           "main_inflow","leader_name","leader_pct"}, ...]
    """
    # m:90+t:2 概念板块;m:90+t:3 行业板块
    fs = "m:90+t:3" if sector_type == "industry" else "m:90+t:2"
    url = "http://push2.eastmoney.com/api/qt/clist/get"
    params = {
        "pn": 1, "pz": top_n, "po": 1, "np": 1,
        "fltt": 2, "invt": 2, "fid": "f3",
        "fs": fs,
        "fields": "f12,f14,f2,f3,f4,f5,f6,f7,f62,f128,f136",
        "_": int(time.time() * 1000),
    }
    try:
        resp = em_get(url, params=params, timeout=15, min_interval=0.6)
        body = resp.json().get("data", {}) or {}
        items = body.get("diff", []) or []
        result = []
        for it in items:
            try:
                result.append({
                    "code":         str(it.get("f12", "")),
                    "name":         it.get("f14", ""),
                    "price":        float(it.get("f2", 0)),
                    "change_pct":   float(it.get("f3", 0)),
                    "price_change": float(it.get("f4", 0)),
                    "turnover":     float(it.get("f5", 0)),      # 成交量(手)
                    "amount":       float(it.get("f6", 0)),      # 成交额(元)
                    "amplitude":    float(it.get("f7", 0)),      # 振幅
                    "main_inflow":  float(it.get("f62", 0)),     # 主力净流入(元)
                    "leader_name":  it.get("f128", ""),
                    "leader_pct":   float(it.get("f136", 0)),
                })
            except (TypeError, ValueError):
                continue
        return result
    except Exception as e:
        return {"error": str(e)}


def fetch_sector_stocks(sector_code, top_n=200):
    """
    拉取某板块下的所有成份股
    - sector_code: 板块代码(如 'BK0428')
    返回 [{"code","name","price","change_pct","amount","turnover_rate","main_inflow","status"}, ...]
    其中 status: '一字板' / '涨停' / '炸板' / '冲高回落' / '正常' 等
    """
    url = "http://push2.eastmoney.com/api/qt/clist/get"
    params = {
        "pn": 1, "pz": top_n, "po": 1, "np": 1,
        "fltt": 2, "invt": 2, "fid": "f3",
        "fs": "b:{}".format(sector_code),
        "fields": "f12,f14,f2,f3,f4,f5,f6,f8,f15,f16,f17,f18,f62",
        "_": int(time.time() * 1000),
    }
    try:
        resp  = em_get(url, params=params, timeout=15, min_interval=0.6)
        body  = resp.json().get("data", {}) or {}
        items = body.get("diff", []) or []
        result = []
        for it in items:
            try:
                code  = str(it.get("f12", "")).zfill(6)
                name  = it.get("f14", "")
                price = float(it.get("f2", 0))
                chg   = float(it.get("f3", 0))
                high  = float(it.get("f15", 0))
                low   = float(it.get("f16", 0))
                opn   = float(it.get("f17", 0))
                prev  = float(it.get("f18", 0))
                tr_rate = float(it.get("f8", 0))    # 换手率
                amount  = float(it.get("f6", 0))
                main_in = float(it.get("f62", 0))

                # 判断状态:
                #   - 一字板: 开 = 高 = 低 = 现价 = 涨停价
                #   - 涨停:   现价 = 高 ≈ 涨停(涨幅约 9.8-10%)
                #   - 炸板:   日内最高 ≈ 涨停 but 现价 < 涨停
                #   - 冲高回落: 高 - 现 > 3%
                limit_up_pct = 9.8 if code.startswith(("6","00")) else 19.8 if code.startswith("30") else 9.8
                # 创业板/科创板 20%,其他 10%
                if code.startswith(("30","68")):
                    limit_up_pct = 19.8
                high_pct = ((high - prev) / prev * 100) if prev else 0

                if chg >= limit_up_pct and abs(price - high) < 0.01 and abs(opn - high) < 0.01 and abs(low - high) < 0.01:
                    status = "一字板"
                elif chg >= limit_up_pct and abs(price - high) < 0.01:
                    status = "涨停"
                elif high_pct >= limit_up_pct and chg < limit_up_pct - 1:
                    status = "炸板"
                elif high_pct - chg >= 3:
                    status = "冲高回落"
                elif chg >= 5:
                    status = "强势"
                elif chg >= 0:
                    status = "上涨"
                elif chg <= -limit_up_pct:
                    status = "跌停"
                else:
                    status = "下跌"

                result.append({
                    "code":          code,
                    "name":          name,
                    "price":         price,
                    "change_pct":    chg,
                    "high_pct":      round(high_pct, 2),
                    "amount":        amount,
                    "turnover_rate": tr_rate,
                    "main_inflow":   main_in,
                    "status":        status,
                })
            except (TypeError, ValueError):
                continue
        return result
    except Exception as e:
        return {"error": str(e)}
