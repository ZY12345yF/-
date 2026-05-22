"""
AI推理与标签管理模块
- query_ai_relation：AI推理标签间连带逻辑
- query_ai_bulk_clustering：AI批量聚类分析
- rename_tag / merge_tags / delete_tag：标签管理操作
- load_bulk_prompt_template / save_bulk_prompt_template：Prompt模板管理
"""
from .normalize import canonical, load_aliases, save_aliases
from .compute import _TAG_SEP
from .. import history as hist_mod
from .. import api_client


def _rewrite_category_field(old, new, dry_run=False):
    """
    在所有历史记录的 category 字段里，把 token=old 替换为 token=new（或删除）。
    new="" 表示删除该 token。
    返回 (changed_record_count, affected_dates)
    会调用 hist_mod 的更新接口，受其原子写 + 锁保护。
    """
    changed = 0
    dates_touched = []
    for d in hist_mod.list_history_dates():
        records = hist_mod.load_history(d)
        any_change = False
        for r in records:
            cat = r.get("category", "") or ""
            if not cat: continue
            parts = [p for p in _TAG_SEP.split(cat) if p.strip()]
            # 用 canonical 比对，避免大小写/空格差异错过
            new_parts = []
            hit = False
            for p in parts:
                if canonical(p) == old:
                    hit = True
                    if new:
                        new_parts.append(new)
                    # else: 删除 → 不加入
                else:
                    new_parts.append(p)
            if not hit:
                continue
            # 去重保持顺序
            seen, dedup = set(), []
            for p in new_parts:
                key = canonical(p)
                if key and key not in seen:
                    seen.add(key); dedup.append(p)
            new_cat = "+".join(dedup)
            if new_cat != cat:
                if not dry_run:
                    hist_mod.update_record(d, r.get("id"), category=new_cat)
                changed += 1
                any_change = True
        if any_change:
            dates_touched.append(d)
    return changed, dates_touched


def rename_tag(old, new):
    """
    把所有 category 里的 old 改名为 new。同时更新别名表。
    返回受影响记录数。
    """
    old_c = canonical(old)
    new_c = canonical(new)
    if not old_c or not new_c or old_c == new_c:
        return 0
    n, _ = _rewrite_category_field(old_c, new_c, dry_run=False)
    # 把别名表里指向 old 的也跟着改
    aliases = dict(load_aliases())
    aliases[old_c] = new_c
    for k, v in list(aliases.items()):
        if canonical(v) == old_c:
            aliases[k] = new_c
    save_aliases(aliases)
    return n


def merge_tags(sources, target):
    """
    把 sources（list[str]）里的标签全部并入 target。
    返回 (受影响记录数, 各源标签处理结果)
    """
    target_c = canonical(target)
    if not target_c: return 0, {}
    total = 0
    per_src = {}
    aliases = dict(load_aliases())
    for s in sources:
        sc = canonical(s)
        if not sc or sc == target_c:
            per_src[s] = 0
            continue
        n, _ = _rewrite_category_field(sc, target_c, dry_run=False)
        per_src[s] = n
        total += n
        aliases[sc] = target_c
    save_aliases(aliases)
    return total, per_src


def delete_tag(tag):
    """
    从所有 category 中删除该标签 token。返回受影响记录数。
    不动 content 里的文字（那是 AI 写的，删了会破坏原文）。
    """
    c = canonical(tag)
    if not c: return 0
    n, _ = _rewrite_category_field(c, "", dry_run=False)
    return n


# ══════════════════════════════════════════════════
# 调用 AI 推理连带逻辑
# ══════════════════════════════════════════════════
def build_relation_prompt(tag_a, tag_b, co_stock_list, freq_a, freq_b, co_count):
    stocks_str = "、".join(
        "{}({})".format(n, c) for n, c in co_stock_list[:12])
    return ("""请基于以下数据，分析两个 A 股细分标签之间的「连带关系」。

【标签A】：{tag_a}（在本地历史中出现 {freq_a} 次）
【标签B】：{tag_b}（在本地历史中出现 {freq_b} 次）
【两者共同出现】：{co_count} 次
【同时具备这两个标签的代表股票】：{stocks}

请用简洁中文（300字以内）回答：
1. 这两个标签的产业逻辑是什么关系？
2. 一旦标签A行情启动，标签B大概率如何反应？
3. 投资中可以怎么利用这种关联？
4. 风险点是什么？
""").format(tag_a=tag_a, tag_b=tag_b, freq_a=freq_a, freq_b=freq_b,
            co_count=co_count, stocks=stocks_str)


def query_ai_relation(tag_a, tag_b, co_stock_list, freq_a, freq_b, co_count,
                      api_key, cfg):
    prompt = build_relation_prompt(tag_a, tag_b, co_stock_list,
                                   freq_a, freq_b, co_count)
    import requests, json, traceback
    headers = {"Authorization": "Bearer " + api_key,
               "Content-Type":  "application/json"}
    is_qianfan = api_client._is_qianfan_endpoint(cfg["api_url"])
    payload = {
        "messages":   [{"role": "user", "content": prompt}],
        "model":      cfg["model"],
        "stream":     False,
        "max_tokens": 800,
        "temperature": 0.3,
    }
    if is_qianfan:
        payload["search_source"] = "baidu_search_v2"
        payload["search_mode"]   = "auto"
    try:
        resp = requests.post(cfg["api_url"], headers=headers,
                             data=json.dumps(payload),
                             timeout=cfg.get("timeout", 60))
        if resp.status_code != 200:
            return "❌ HTTP {}: {}".format(resp.status_code, resp.text[:200]), False
        data = resp.json()
        choices = data.get("choices", [])
        if not choices:
            return "❌ 无返回内容", False
        return choices[0]["message"]["content"], True
    except Exception:
        return "❌ 异常: {}".format(traceback.format_exc()[:300]), False


# ══════════════════════════════════════════════════
# 批量分析（自定义 Prompt）
# ══════════════════════════════════════════════════
DEFAULT_BULK_PROMPT = """以下为 A 股涨停细分标签数据，请提取并解读这些词语的信息，并划分关联度。
关联度大于 50% 的标签需要你放在同一个细分主线下。

【标签清单及出现频次】
{tag_list}

【两两共现 Top 20】
{cooccur_list}

请按以下格式输出（用中文）：

## 🎯 主线划分
主线1：某某主线
  - 标签A、标签B、标签C（关联度 75%）
  - 产业逻辑：...

## 🔗 跨主线连带

## ⚠️ 注意事项

请直接输出，不要客套话。
"""


def collect_bulk_data(tag_freq, cooccur, top_tags=40, top_pairs=20):
    tags_sorted = sorted(tag_freq.items(), key=lambda x: -x[1])[:top_tags]
    tag_list_str = "\n".join(
        "  · {} ({} 次)".format(t, c) for t, c in tags_sorted)
    pairs_sorted = sorted(cooccur.items(), key=lambda x: -x[1])[:top_pairs]
    pairs_str = "\n".join(
        "  · {} ⇄ {} （共现 {} 次）".format(a, b, c)
        for (a, b), c in pairs_sorted)
    return tag_list_str, pairs_str


def query_ai_bulk_clustering(tag_freq, cooccur, api_key, cfg,
                              custom_prompt=None):
    tag_list_str, cooccur_str = collect_bulk_data(tag_freq, cooccur)
    template = custom_prompt or DEFAULT_BULK_PROMPT
    try:
        prompt = template.format(
            tag_list=tag_list_str, cooccur_list=cooccur_str)
    except KeyError:
        prompt = template + "\n\n" + tag_list_str + "\n\n" + cooccur_str

    import requests, json, traceback
    headers = {"Authorization": "Bearer " + api_key,
               "Content-Type":  "application/json"}
    is_qianfan = api_client._is_qianfan_endpoint(cfg["api_url"])
    payload = {
        "messages":   [{"role": "user", "content": prompt}],
        "model":      cfg["model"],
        "stream":     False,
        "max_tokens": 3000,
        "temperature": 0.3,
    }
    if is_qianfan:
        payload["search_source"] = "baidu_search_v2"
        payload["search_mode"]   = "auto"
    try:
        resp = requests.post(cfg["api_url"], headers=headers,
                             data=json.dumps(payload),
                             timeout=cfg.get("timeout", 120))
        if resp.status_code != 200:
            return "❌ HTTP {}: {}".format(resp.status_code, resp.text[:200]), False
        data = resp.json()
        choices = data.get("choices", [])
        if not choices:
            return "❌ 无返回内容", False
        return choices[0]["message"]["content"], True
    except Exception:
        return "❌ 异常: {}".format(traceback.format_exc()[:300]), False


def load_bulk_prompt_template():
    from ..paths import DIRS
    from pathlib import Path
    p = Path(DIRS["config"]) / "tag_relation_bulk_prompt.txt"
    if p.exists():
        return p.read_text(encoding="utf-8")
    return DEFAULT_BULK_PROMPT


def save_bulk_prompt_template(text):
    from ..paths import DIRS
    from pathlib import Path
    p = Path(DIRS["config"]) / "tag_relation_bulk_prompt.txt"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text or DEFAULT_BULK_PROMPT, encoding="utf-8")
