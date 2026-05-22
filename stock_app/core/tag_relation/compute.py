"""
标签提取与关联度计算模块
- extract_tags_from_content：从记录中提取标签
- build_cooccurrence：构建共现矩阵
- list_all_tags：列出所有标签
- compute_relations：计算关联度评分
- co_stocks：查找共现股票
"""
import re
from collections import defaultdict, Counter

from .normalize import canonical
from .. import history as hist_mod


# ══════════════════════════════════════════════════
# 标签提取（A3：单一数据源 — category 优先，content 仅 fallback）
# ══════════════════════════════════════════════════
_CONTENT_PATTERNS = [
    re.compile(r'【细分标签】\s*[：:]?\s*([^\n]+)'),
    re.compile(r'【涨停逻辑】\s*[：:]?\s*([^\n]+)'),
    re.compile(r'细分标签\s*[：:]?\s*([^\n]+)'),
    re.compile(r'涨停逻辑\s*[：:]?\s*([^\n]+)'),
]
_TAG_SEP = re.compile(r'[+、，,\s/|]+')


def _split_and_canon(s):
    """切分一行文本里的多个标签词，每个走 canonical()"""
    out = set()
    for part in _TAG_SEP.split(s or ""):
        c = canonical(part)
        if c:
            out.add(c)
    return out


def extract_tags_from_content(content, record=None):
    """
    🌟 A3 单一数据源原则：
      record.category 不空 → 只用 category（用户/批量是权威输入）
      record.category 空   → 退而求其次，从 content 的【细分标签】行扫
    所有标签都过 canonical() 规范化 + 走别名表
    """
    # 优先级 1：结构化 category
    if record:
        cat = (record.get("category") or "").strip()
        if cat:
            return _split_and_canon(cat)

    # 优先级 2：fallback —— content 里的【细分标签】行
    tags = set()
    text = content or ""
    for pat in _CONTENT_PATTERNS:
        m = pat.search(text)
        if m:
            tags |= _split_and_canon(m.group(1))
    return tags


# ══════════════════════════════════════════════════
# 全局共现矩阵（A1：可指定回溯天数）
# ══════════════════════════════════════════════════
def build_cooccurrence(days=7, min_freq=1):
    """
    扫描最近 days 天的历史，构建标签频次/共现矩阵/标签→记录索引。
    days=None 或 days<=0 表示扫全部历史。
    """
    tag_freq    = Counter()
    cooccur     = Counter()
    tag_records = defaultdict(list)

    dates = hist_mod.list_history_dates()
    if not dates:
        return {}, {}, {}
    if days is None or days <= 0:
        target_dates = dates
    else:
        target_dates = dates[:int(days)]

    for date_key in target_dates:
        records = hist_mod.load_history(date_key)
        for r in records:
            tags = extract_tags_from_content(r.get('content', ''), record=r)
            if not tags:
                continue
            for t in tags:
                tag_freq[t] += 1
                tag_records[t].append({
                    "date": date_key,
                    "name": r.get('name', ''),
                    "code": r.get('code', ''),
                    "id":   r.get('id', ''),
                })
            tags_list = sorted(tags)
            for i in range(len(tags_list)):
                for j in range(i+1, len(tags_list)):
                    key = (tags_list[i], tags_list[j])
                    cooccur[key] += 1

    filtered_tags = {t for t, c in tag_freq.items() if c >= min_freq}
    tag_freq    = {t: c for t, c in tag_freq.items() if t in filtered_tags}
    cooccur     = {k: v for k, v in cooccur.items()
                    if k[0] in filtered_tags and k[1] in filtered_tags}
    tag_records = {t: r for t, r in tag_records.items() if t in filtered_tags}
    return tag_freq, cooccur, tag_records


# ══════════════════════════════════════════════════
# 标签管理 API（B1）
# ══════════════════════════════════════════════════
def list_all_tags(days=None):
    """
    全局标签清单。返回 [{tag, freq, first_date, last_date, codes_n}, ...]
    days=None / 0 → 全部历史
    """
    dates = hist_mod.list_history_dates()
    if not dates: return []
    if days and days > 0:
        dates = dates[:int(days)]

    freq        = Counter()
    first_date  = {}
    last_date   = {}
    codes_set   = defaultdict(set)
    for d in dates:
        for r in hist_mod.load_history(d):
            tags = extract_tags_from_content(r.get('content', ''), record=r)
            for t in tags:
                freq[t] += 1
                code = r.get('code', '')
                if code: codes_set[t].add(code)
                if t not in first_date or d < first_date[t]:
                    first_date[t] = d
                if t not in last_date  or d > last_date[t]:
                    last_date[t]  = d

    out = []
    for t, f in freq.items():
        out.append({
            "tag":        t,
            "freq":       f,
            "first_date": first_date.get(t, ""),
            "last_date":  last_date.get(t, ""),
            "codes_n":    len(codes_set[t]),
        })
    out.sort(key=lambda x: (-x['freq'], x['tag']))
    return out


# ══════════════════════════════════════════════════
# 关联度评分（Jaccard 系数）
# ══════════════════════════════════════════════════
def compute_relations(target_tag, tag_freq, cooccur, top_n=15):
    if target_tag not in tag_freq:
        return []
    target_freq = tag_freq[target_tag]
    relations = []
    for (a, b), co in cooccur.items():
        if a == target_tag:
            other = b
        elif b == target_tag:
            other = a
        else:
            continue
        other_freq = tag_freq.get(other, 0)
        if other_freq == 0:
            continue
        union = target_freq + other_freq - co
        if union <= 0:
            continue
        jaccard = co / union
        relations.append({
            "tag":           other,
            "cooccur_count": co,
            "score":         round(jaccard, 3),
            "support":       co,
            "self_freq":     target_freq,
            "other_freq":    other_freq,
        })
    relations.sort(key=lambda x: (-x['score'], -x['support']))
    return relations[:top_n]


# ══════════════════════════════════════════════════
# 共现股票
# ══════════════════════════════════════════════════
def co_stocks(tag_a, tag_b, tag_records):
    if tag_a not in tag_records or tag_b not in tag_records:
        return []
    set_a = {(r['name'], r['code']) for r in tag_records[tag_a]}
    set_b = {(r['name'], r['code']) for r in tag_records[tag_b]}
    common = set_a & set_b
    return sorted(common)
