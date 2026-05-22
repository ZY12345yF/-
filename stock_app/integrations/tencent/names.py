"""
integrations.tencent.names — 股票代码 → 名称兜底反查 (含磁盘缓存)
                              + 文本中代码提取 + 行情追加

从 core/api_client.py L182-356 迁入,行为不变。
归这里是因为它依赖 tencent.quote.fetch_change_pct。

优先级:
  本地 stock_dict (config.get_code_to_name_lookup) → 磁盘缓存 → 腾讯接口

extract_linked_codes / append_realtime_data 跟"名称查询"耦合在一起,
所以放同文件。
"""
import json
import os
import re
import tempfile
import threading

from .quote import fetch_change_pct


# ════════════════════════════════════════════════════
# 名称磁盘缓存
# ════════════════════════════════════════════════════
_NAME_CACHE = None
_NAME_CACHE_LOCK = threading.Lock()


def _name_cache_path():
    # 延迟 import 避免循环
    from ...core.paths import DIRS
    return DIRS["config"] / "code_name_cache.json"


def _load_name_cache():
    global _NAME_CACHE
    with _NAME_CACHE_LOCK:
        if _NAME_CACHE is not None:
            return _NAME_CACHE
        p = _name_cache_path()
        if not p.exists():
            _NAME_CACHE = {}
            return _NAME_CACHE
        try:
            _NAME_CACHE = json.loads(p.read_text(encoding="utf-8"))
            if not isinstance(_NAME_CACHE, dict):
                _NAME_CACHE = {}
        except Exception:
            _NAME_CACHE = {}
        return _NAME_CACHE


def _save_name_cache():
    p = _name_cache_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd, tmp = tempfile.mkstemp(dir=str(p.parent), prefix=".tmp_", suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(_NAME_CACHE or {}, f, ensure_ascii=False, indent=2)
        os.replace(tmp, str(p))
    except Exception:
        pass


def fetch_stock_names(codes, use_cache=True, refresh_missing=True):
    """
    批量查股票代码 → 名称的映射。
    优先级:磁盘缓存 > stock_dict > 腾讯接口实时拉取。
    返回 {code6: name},查不到的 code 不在返回字典里。
    """
    if not codes:
        return {}
    codes6 = [str(c).zfill(6) for c in codes if c]
    out = {}

    # 1. stock_dict (用户自己学习过的)
    try:
        from ...core import config as cfg_mod
        local = cfg_mod.get_code_to_name_lookup()
        for c in codes6:
            if c in local:
                out[c] = local[c]
    except Exception:
        pass

    # 2. 磁盘缓存
    if use_cache:
        cache = _load_name_cache()
        for c in codes6:
            if c not in out and c in cache:
                out[c] = cache[c]

    # 3. 兜底:腾讯接口实时拉
    missing = [c for c in codes6 if c not in out]
    if refresh_missing and missing:
        try:
            data = fetch_change_pct(missing)
            cache = _load_name_cache()
            changed = False
            for c in missing:
                if c in data and data[c].get("name"):
                    out[c] = data[c]["name"]
                    cache[c] = data[c]["name"]
                    changed = True
            if changed:
                _save_name_cache()
        except Exception:
            pass

    return out


# ════════════════════════════════════════════════════
# 文本中提取联动标的代码
# ════════════════════════════════════════════════════
def extract_linked_codes(text):
    """
    从分析文本中提取联动标的股票代码
    策略:先定位 ④ 段落,找不到则全文搜
    关键修复:lookahead 中 ⑤ 必须是独立符号,不能匹配列表序号 "5."
    """
    chunk = ""

    # 找 ④/4 开头的联动标的段落,到 ⑤(全角圆圈数字)或 "⑤" / 段落结束为止
    # 注意:不要用 [5] 作为停止符,会把 "5. xxx" 列表项也截掉
    patterns = [
        # ④ 和关键词之间允许任意字符(含换行)
        r'[④]\s*[^④⑤\n]{0,30}同逻辑联动标的[^】\n]*[】]?(.*?)(?=⑤|同逻辑标的板块事件|\Z)',
        r'同逻辑联动标的[^】\n]*[】]?(.*?)(?=⑤|同逻辑标的板块事件|\Z)',
        r'联动标的[^】\n]*[】]?(.*?)(?=⑤|板块事件|\Z)',
    ]
    for pat in patterns:
        m = re.search(pat, text, re.DOTALL)
        if m and len(m.group(1).strip()) > 10:
            chunk = m.group(1)
            break

    src = chunk if len(chunk) > 30 else text

    # 优先匹配括号格式  (000001) / (000001)
    codes_paren = re.findall(r'[((](\d{6})[))]', src)
    # 再匹配裸数字(不被小数点或更多数字包围)
    codes_bare  = re.findall(r'(?<![.\d])(\d{6})(?![.\d])', src)

    all_codes = codes_paren + [c for c in codes_bare if c not in codes_paren]

    # 🛡️ 白名单:A 股代码合法前缀(沪深京三市)
    #   60/68/90/11  → 沪市主板/科创板/B股/可转债
    #   00/30/12/39  → 深市主板/创业板/可转债/指数
    #   83/87/43/82  → 北交所/新三板精选层
    # 之前用 BAD_STARTS 黑名单堵不完,邮编 / 电话尾号 / 订单号都会误匹配
    VALID_PREFIXES = ("60", "68", "00", "30", "11", "12",
                      "83", "87", "43", "82")
    seen, valid = set(), []
    for c in all_codes:
        if c in seen:
            continue
        if not any(c.startswith(p) for p in VALID_PREFIXES):
            continue
        # 额外排除全 0 / 明显异常
        if c == "000000" or c.startswith("0000"):
            continue
        seen.add(c)
        valid.append(c)
    return valid[:12]


def append_realtime_data(text, on_log=None, main_code=None):
    """
    在分析结果末尾追加联动标的实时行情
    🆕 v9.9.6:main_code 不为空时把当前主股票也加进去(放在列表最前面),
              以便在详情里显示行情时能用 ⭐ 标记主股。
    """
    codes = extract_linked_codes(text)
    # 主股加到最前面(去重)
    main6 = str(main_code or "").zfill(6) if main_code else ""
    if main6 and main6.isdigit() and len(main6) == 6:
        if main6 in codes:
            codes.remove(main6)
        codes = [main6] + codes
    if not codes:
        return text
    if on_log:
        on_log("查询联动标的实时行情: {}".format(codes), "purple")
    data = fetch_change_pct(codes)
    if not data:
        return text
    lines = ["\n\n" + "─" * 40]
    lines.append("📊 同逻辑联动标的  实时行情(腾讯财经)")
    lines.append("─" * 40)
    for code, info in data.items():
        chg = info["change_pct"]
        arrow = "▲" if chg > 0 else ("▼" if chg < 0 else "─")
        sign  = "+" if chg > 0 else ""
        # 🆕 v9.9.6:主股票前面加 ⭐ 标识,跟 history_tab _requery_realtime 的视觉一致
        prefix = "  ⭐ " if (main6 and code == main6) else "    "
        lines.append("{}{}({})  {}  {}{}%   {}".format(
            prefix, info["name"], code, info["price"],
            arrow, sign + str(chg), info["time"]))
    lines.append("─" * 40)
    return text + "\n".join(lines)
