"""
integrations.tencent.quote — 腾讯财经实时行情接口

从 core/api_client.py L109-180 迁入,行为不变。
腾讯实时行情比东方财富快、稳,但没有完整盘后数据 — 浮窗/批量重查都用它。
"""
import re
from datetime import datetime

import requests


def _get_market_prefix(code):
    """6位代码 → 带市场前缀的 8 位代码 (e.g. '600519' → 'sh600519')"""
    if code.startswith(("60", "68", "90", "11")):
        return "sh" + code
    elif code.startswith(("00", "30", "39", "12")):
        return "sz" + code
    return code


def fetch_change_pct(codes):
    """
    批量获取涨跌幅
    返回 {code: {"name", "price", "change_pct", "time"}}
    """
    if not codes:
        return {}
    full_codes = [_get_market_prefix(c) for c in codes]
    url = "http://qt.gtimg.cn/q={}".format(",".join(full_codes))
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://gu.qq.com/",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        # 🛡️ gbk 优先,但兜底 utf-8:腾讯偶发返回 utf-8,遇生僻字名时不再变 "?"
        raw = resp.content
        try:
            text = raw.decode("gbk")
        except UnicodeDecodeError:
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                text = raw.decode("gbk", errors="replace")
        text = text.strip()
        result = {}
        for m in re.finditer(r'v_.*?="(.*?)"', text):
            fields = m.group(1).split("~")
            if len(fields) < 4:          # 最低要有名称+代码+现价+昨收
                continue
            try:
                code6 = fields[2]
                name  = fields[1]
                if not code6 or not re.match(r'^\d{6}$', code6):
                    continue
                price   = round(float(fields[3]), 2) if fields[3] else 0.0
                yclose  = float(fields[4]) if len(fields) > 4 and fields[4] else 0.0
                # 优先用字段32(涨跌幅),fallback 用计算值
                if len(fields) > 32 and fields[32]:
                    try:
                        chg_pct = round(float(fields[32]), 2)
                    except ValueError:
                        chg_pct = round((price - yclose) / yclose * 100, 2) if yclose else 0.0
                else:
                    chg_pct = round((price - yclose) / yclose * 100, 2) if yclose else 0.0
                # 更新时间
                raw_t = fields[30] if len(fields) > 30 else ""
                if len(raw_t) == 14 and raw_t.isdigit():
                    upd = "{}-{}-{} {}:{}:{}".format(
                        raw_t[:4], raw_t[4:6], raw_t[6:8],
                        raw_t[8:10], raw_t[10:12], raw_t[12:14])
                else:
                    upd = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                result[code6] = {"name": name, "price": price,
                                 "change_pct": chg_pct, "time": upd}
            except (ValueError, IndexError, ZeroDivisionError):
                continue
        return result
    except Exception:
        return {}
