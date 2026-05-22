"""
概念图谱系统 — v10.0 AI Native 架构

概念 → 子概念 → 个股 的层次化知识图谱
支持: 概念继承 · 标签传播 · 动态权重 · 热度衰减 · AI聚类
"""
import json, threading, time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CNode:
    name: str
    weight: float = 1.0
    base_weight: float = 1.0
    decay: float = 0.05
    parent: Optional[str] = None
    children: list = field(default_factory=list)
    stocks: list = field(default_factory=list)
    aliases: list = field(default_factory=list)
    tags: list = field(default_factory=list)
    news_count: int = 0
    updated: float = field(default_factory=time.time)

    @property
    def age_days(self) -> float: return (time.time() - self.updated) / 86400

    @property
    def eff_weight(self) -> float:
        w = self.weight * (1 - self.decay) ** self.age_days
        return max(w, self.base_weight * 0.05)

    def to_dict(self) -> dict:
        return {"name": self.name, "weight": round(self.eff_weight, 4),
                "parent": self.parent, "children": self.children,
                "stocks": self.stocks, "aliases": self.aliases,
                "news_count": self.news_count, "age_days": round(self.age_days, 2)}


class ConceptGraph:
    """概念图谱 — 全局单例"""

    def __init__(self):
        self._lock = threading.RLock()
        self._nodes: dict[str, CNode] = {}
        self._stock_idx: dict[str, set] = defaultdict(set)
        self._tag_idx: dict[str, set] = defaultdict(set)

    # ── CRUD ──
    def add(self, name: str, parent: str = None, weight: float = 1.0,
            stocks: list = None, aliases: list = None, tags: list = None,
            decay: float = 0.05) -> CNode:
        with self._lock:
            if name in self._nodes:
                n = self._nodes[name]; n.weight = max(n.weight, weight)
            else:
                n = CNode(name=name, weight=weight, base_weight=weight, parent=parent, decay=decay)
                self._nodes[name] = n
            if parent:
                n.parent = parent
                pn = self._nodes.get(parent)
                if pn and name not in pn.children: pn.children.append(name)
            if stocks:
                for c in stocks: self._stock_idx[c].add(name)
                n.stocks = list(set(n.stocks + stocks))
            if aliases: n.aliases = list(set(n.aliases + aliases))
            if tags:
                for t in tags: self._tag_idx[t].add(name)
                n.tags = list(set(n.tags + tags))
            n.updated = time.time()
            return n

    def get(self, name: str) -> Optional[CNode]: return self._nodes.get(name)

    def remove(self, name: str):
        with self._lock:
            n = self._nodes.pop(name, None)
            if not n: return
            for c in n.stocks: self._stock_idx[c].discard(name)
            for t in n.tags: self._tag_idx[t].discard(name)
            for child in list(n.children): self.remove(child)

    def list_roots(self) -> list[str]:
        return [n for n, node in self._nodes.items() if not node.parent]

    def children(self, name: str) -> list[str]:
        n = self.get(name); return list(n.children) if n else []

    def ancestors(self, name: str) -> list[str]:
        result, cur = [], name
        while cur:
            n = self.get(cur)
            if n and n.parent: result.append(n.parent); cur = n.parent
            else: break
        return result

    def descendants(self, name: str) -> list[str]:
        n = self.get(name)
        if not n: return []
        result = []
        for c in n.children: result.append(c); result.extend(self.descendants(c))
        return result

    # ── 关系 ──
    def link(self, parent: str, child: str, weight: float = 0.5):
        pn, cn = self.get(parent), self.get(child)
        if pn and cn:
            cn.parent = parent
            if child not in pn.children: pn.children.append(child)
            cn.weight = max(cn.weight, pn.weight * weight)
            cn.updated = time.time()

    # ── 传播 ──
    def propagate(self, name: str, hot: float):
        n = self.get(name)
        if not n: return
        with self._lock:
            n.weight += hot; n.updated = time.time()
            for i, a in enumerate(self.ancestors(name)):
                an = self.get(a)
                if an: an.weight += hot * (0.5 ** (i + 1)); an.updated = time.time()
            for d in self.descendants(name):
                dn = self.get(d)
                if dn: dn.weight += hot * 0.3; dn.updated = time.time()

    # ── 查询 ──
    def stocks_for(self, name: str, deep: bool = True) -> list[str]:
        s = set(self.get(name).stocks if self.get(name) else [])
        if deep:
            for d in self.descendants(name):
                dn = self.get(d)
                if dn: s.update(dn.stocks)
        return list(s)

    def concepts_for_stock(self, code: str) -> list[str]:
        return list(self._stock_idx.get(code, set()))

    def search(self, kw: str) -> list[str]:
        kw = kw.lower(); results = []
        for name, n in self._nodes.items():
            if kw in name.lower(): results.append(name)
            elif any(kw in a.lower() for a in n.aliases): results.append(name)
        return results

    def hot(self, top_n: int = 20) -> list[dict]:
        return [n.to_dict() for n in sorted(self._nodes.values(),
                key=lambda n: n.eff_weight, reverse=True)[:top_n]]

    def tree(self, name: str = None, depth: int = 3) -> dict:
        roots = [self.get(name)] if name else [self.get(r) for r in self.list_roots()]
        def _t(n, d):
            if not n or d <= 0: return {}
            return {"name": n.name, "weight": round(n.eff_weight, 4),
                    "stocks": len(n.stocks), "news": n.news_count,
                    "children": {c: _t(self.get(c), d-1) for c in n.children}}
        if name: return _t(self.get(name), depth)
        return {r: _t(self.get(r), depth) for r in self.list_roots() if self.get(r)}

    # ── 持久化 ──
    def dump(self, path: str):
        data = {n: {"weight": nd.weight, "base_weight": nd.base_weight,
                     "parent": nd.parent, "children": nd.children,
                     "stocks": nd.stocks, "aliases": nd.aliases,
                     "tags": nd.tags, "news_count": nd.news_count,
                     "updated": nd.updated}
                for n, nd in self._nodes.items()}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load(self, path: str):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for name, d in data.items():
            self.add(name=name, parent=d.get("parent"), weight=d.get("weight", 1.0),
                     stocks=d.get("stocks", []), aliases=d.get("aliases", []),
                     tags=d.get("tags", []))
            n = self._nodes[name]
            n.base_weight = d.get("base_weight", 1.0)
            n.updated = d.get("updated", time.time())
            n.news_count = d.get("news_count", 0)

    def stats(self) -> dict:
        return {"total": len(self._nodes), "roots": len(self.list_roots()),
                "stock_links": sum(len(n.stocks) for n in self._nodes.values())}


graph = ConceptGraph()
