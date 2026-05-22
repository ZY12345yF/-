"""
AI Runtime 系统 — v10.0 AI Native 架构

Token统计 · Provider路由 · 熔断 · 限流 · Fallback · 上下文压缩
"""
import threading, time
from collections import defaultdict
from typing import Callable, Optional


PROVIDER_CFG = {
    "qianfan":   {"max_qpm": 60, "max_conc": 3, "cost_per_1k": 0.004, "search": True},
    "volcano":   {"max_qpm": 30, "max_conc": 2, "cost_per_1k": 0.001, "search": False},
    "openai":    {"max_qpm": 60, "max_conc": 3, "cost_per_1k": 0.002, "search": False},
    "anthropic": {"max_qpm": 50, "max_conc": 2, "cost_per_1k": 0.003, "search": False},
    "local":     {"max_qpm": 9999, "max_conc": 1, "cost_per_1k": 0.0, "search": False},
}


class TokenTracker:
    """Token 用量追踪"""

    def __init__(self):
        self._lock = threading.Lock()
        self._records: list[dict] = []
        self._totals: dict[str, dict] = defaultdict(lambda: {"tokens": 0, "requests": 0, "cost": 0.0})

    def record(self, provider: str, tokens: int, model: str = "", req_type: str = ""):
        cost_per_1k = PROVIDER_CFG.get(provider, {}).get("cost_per_1k", 0)
        cost = tokens / 1000.0 * cost_per_1k
        with self._lock:
            self._records.append({"ts": time.time(), "provider": provider, "model": model,
                                  "tokens": tokens, "type": req_type})
            if len(self._records) > 500:
                self._records = self._records[-250:]
            t = self._totals[provider]
            t["tokens"] += tokens; t["requests"] += 1; t["cost"] += cost

    def get_summary(self) -> dict:
        with self._lock:
            return {"total_tokens": sum(s["tokens"] for s in self._totals.values()),
                    "total_requests": sum(s["requests"] for s in self._totals.values()),
                    "total_cost": round(sum(s["cost"] for s in self._totals.values()), 6),
                    "by_provider": {p: dict(s) for p, s in self._totals.items()}}

    def get_recent_tokens(self, minutes: int = 1) -> dict[str, int]:
        cutoff = time.time() - minutes * 60
        with self._lock:
            counts = defaultdict(int)
            for r in self._records:
                if r["ts"] >= cutoff:
                    counts[r["provider"]] += r["tokens"]
            return dict(counts)


class CircuitBreaker:
    """熔断器 — 连续失败 N 次后自动切换 provider"""

    def __init__(self, threshold: int = 5, recovery: float = 30.0):
        self.threshold = threshold
        self.recovery = recovery
        self._lock = threading.Lock()
        self._failures: dict[str, int] = defaultdict(int)
        self._state: dict[str, str] = defaultdict(lambda: "closed")
        self._opened_at: dict[str, float] = {}

    def is_open(self, provider: str) -> bool:
        with self._lock:
            state = self._state[provider]
            if state == "closed":
                return False
            if state == "open":
                if time.time() - self._opened_at.get(provider, 0) >= self.recovery:
                    self._state[provider] = "half_open"
                    return False
                return True
            return False  # half_open

    def record_success(self, provider: str):
        with self._lock:
            self._failures[provider] = 0
            self._state[provider] = "closed"

    def record_failure(self, provider: str):
        with self._lock:
            self._failures[provider] += 1
            if self._failures[provider] >= self.threshold:
                self._state[provider] = "open"
                self._opened_at[provider] = time.time()


class RateLimiter:
    """滑动窗口限流"""

    def __init__(self, window: float = 60.0):
        self._lock = threading.Lock()
        self._windows: dict[str, list[float]] = defaultdict(list)
        self._window = window

    def check(self, provider: str) -> tuple[bool, float]:
        max_qpm = PROVIDER_CFG.get(provider, {}).get("max_qpm", 60)
        now = time.time()
        cutoff = now - self._window
        with self._lock:
            w = [t for t in self._windows[provider] if t > cutoff]
            self._windows[provider] = w
            if len(w) < max_qpm:
                w.append(now)
                return True, 0.0
            wait = min(w) - cutoff + 0.1
            return False, max(wait, 0.1)


class ProviderRouter:
    """Provider 路由器 — 熔断/限流的自动降级"""

    _CHAIN = ["qianfan", "volcano", "openai", "anthropic", "local"]

    def __init__(self, cb: CircuitBreaker, rl: RateLimiter):
        self.cb = cb; self.rl = rl

    def route(self, preferred: str = None, require_search: bool = False) -> Optional[str]:
        candidates = [preferred] + [p for p in self._CHAIN if p != preferred] if preferred else list(self._CHAIN)
        for p in candidates:
            if self.cb.is_open(p):
                continue
            if require_search and not PROVIDER_CFG.get(p, {}).get("search", False):
                continue
            ok, _ = self.rl.check(p)
            if ok:
                return p
        return None


class ContextCompressor:
    """上下文压缩"""

    @staticmethod
    def estimate_tokens(text: str) -> int:
        cn = sum(1 for c in text if '一' <= c <= '鿿')
        return int(cn / 1.5 + (len(text) - cn) / 4)

    @classmethod
    def compress(cls, text: str, max_tokens: int = 8000) -> str:
        if cls.estimate_tokens(text) <= max_tokens:
            return text
        ratio = max_tokens / max(cls.estimate_tokens(text), 1)
        half = int(len(text) * ratio * 0.5)
        return text[:half] + f"\n\n... [已压缩] ...\n\n" + text[-half:]


class AIRuntime:
    """AI 运行时管理器 — 全局单例"""

    def __init__(self):
        self.tracker = TokenTracker()
        self.cb = CircuitBreaker()
        self.rl = RateLimiter()
        self.router = ProviderRouter(self.cb, self.rl)
        self.compressor = ContextCompressor()
        self._conc: dict[str, int] = defaultdict(int)
        self._lock = threading.Lock()
        self.on_circuit_open: Optional[Callable] = None
        self.on_fallback: Optional[Callable] = None

    def before_request(self, provider: str = None, require_search: bool = False) -> Optional[str]:
        actual = self.router.route(provider, require_search)
        if not actual:
            return None
        with self._lock:
            maxc = PROVIDER_CFG.get(actual, {}).get("max_conc", 2)
            if self._conc[actual] >= maxc:
                for fb in [p for p in self.router._CHAIN if p != actual]:
                    if not self.cb.is_open(fb) and self._conc[fb] < PROVIDER_CFG.get(fb, {}).get("max_conc", 2):
                        if self.on_fallback: self.on_fallback(provider, fb)
                        actual = fb; break
            self._conc[actual] += 1
        return actual

    def after_request(self, provider: str):
        with self._lock:
            self._conc[provider] = max(0, self._conc[provider] - 1)

    def record_usage(self, provider: str, tokens: int, model: str = "", req_type: str = ""):
        self.tracker.record(provider, tokens, model, req_type)
        self.cb.record_success(provider)

    def record_failure(self, provider: str, reason: str = ""):
        self.cb.record_failure(provider)
        if self.cb.is_open(provider) and self.on_circuit_open:
            self.on_circuit_open(provider, reason)

    def get_report(self) -> dict:
        return self.tracker.get_summary()

    def get_status(self) -> dict:
        return {"usage": self.tracker.get_summary(),
                "circuits": {p: self.cb._state[p] for p in PROVIDER_CFG},
                "concurrent": dict(self._conc)}


runtime = AIRuntime()
