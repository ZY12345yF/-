"""
标签规范化模块
- normalize_tag：统一规范化（全角/半角/空格/尾缀清理）
- canonical：规范化 + 查别名表
- load_aliases / save_aliases：别名表管理
"""
import re, json, threading
from pathlib import Path


# ══════════════════════════════════════════════════
# 规范化（A2）
# ══════════════════════════════════════════════════
# 常见冗余尾缀：在标签末尾出现且去掉后剩余 ≥2 字时移除
_TRIM_SUFFIXES = (
    "产业链", "概念股", "概念", "板块", "题材", "主线", "方向", "标的", "龙头")
# 全角 → 半角的映射（常见的几个）
_FULLWIDTH_MAP = str.maketrans({
    "（": "(", "）": ")", "，": ",", "、": ",", "／": "/", "｜": "|",
    "：": ":", "；": ";", "　": " ",
})


def normalize_tag(s):
    """
    规范化单个标签字符串。返回规范化后的字符串，或 "" 表示该标签应被丢弃。
    规则：
      1. 全角→半角，去前后空白
      2. 去掉括号及其内容： "锂电池(正极)" → "锂电池"
      3. 去掉常见尾缀： "锂电池产业链" → "锂电池"
      4. 长度限制：2 ≤ len ≤ 20
    """
    if not s:
        return ""
    t = str(s).translate(_FULLWIDTH_MAP).strip()
    # 去括号内容（中英文都已经转成半角了）
    t = re.sub(r"\([^)]*\)", "", t).strip()
    # 去末尾常见冗余尾缀，但保留至少 2 字
    for suf in _TRIM_SUFFIXES:
        if t.endswith(suf) and len(t) - len(suf) >= 2:
            t = t[: -len(suf)]
            break
    t = t.strip(" -_,.;:|/+、")
    if not (2 <= len(t) <= 20):
        return ""
    return t


# 标签别名表（C1）：把"锂电"统一为"锂电池"这种映射做成可维护文件
# 路径：data/config/tag_aliases.json，格式 { "锂电": "锂电池", "光伏概念": "光伏" }
_ALIAS_LOCK = threading.Lock()
_ALIAS_CACHE = None
_ALIAS_MTIME = 0


def _alias_path():
    from ..paths import DIRS
    return Path(DIRS["config"]) / "tag_aliases.json"


def load_aliases():
    """读取别名表（带 mtime 缓存）"""
    global _ALIAS_CACHE, _ALIAS_MTIME
    p = _alias_path()
    try:
        mt = p.stat().st_mtime if p.exists() else 0
    except OSError:
        mt = 0
    with _ALIAS_LOCK:
        if _ALIAS_CACHE is not None and mt == _ALIAS_MTIME:
            return _ALIAS_CACHE
        if not p.exists():
            _ALIAS_CACHE, _ALIAS_MTIME = {}, 0
            return {}
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                data = {}
        except Exception:
            data = {}
        _ALIAS_CACHE, _ALIAS_MTIME = data, mt
        return data


def save_aliases(mapping):
    """保存别名表（原子写）"""
    import os, tempfile
    p = _alias_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), prefix=".tmp_", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(mapping, f, ensure_ascii=False, indent=2, sort_keys=True)
        os.replace(tmp, str(p))
    except Exception:
        try: os.unlink(tmp)
        except OSError: pass
        raise
    with _ALIAS_LOCK:
        global _ALIAS_CACHE, _ALIAS_MTIME
        _ALIAS_CACHE = dict(mapping)
        try: _ALIAS_MTIME = p.stat().st_mtime
        except OSError: _ALIAS_MTIME = 0


def canonical(tag):
    """规范化 + 查别名表 → 最终标签名"""
    n = normalize_tag(tag)
    if not n: return ""
    aliases = load_aliases()
    # 一层重定向；如果别名也指向另一个别名，最多再跳一次
    seen = {n}
    cur = n
    for _ in range(2):
        nxt = aliases.get(cur)
        if not nxt or nxt in seen: break
        cur = normalize_tag(nxt) or cur
        seen.add(cur)
    return cur
