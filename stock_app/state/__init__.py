"""
统一状态管理器 — v10.0 AI Native 架构

设计原则:
  • 禁止全局变量,所有状态必须通过 StateManager 访问
  • 状态变更自动通知订阅者
  • 支持快照/回滚
  • 支持持久化关键状态
  • 线程安全

状态分类:
  AppState      — 应用级状态 (running, shutdown, queues)
  MarketState   — 市场数据状态 (当前股票、板块数据)
  SkillState    — 技能执行状态
  RuntimeState  — AI运行时状态 (token、provider、限流)
  TaskState     — 任务执行状态
"""
import json
import threading
import time
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Callable, Optional


# ════════════════════════════════════════════════════
# 状态基类
# ════════════════════════════════════════════════════
class StateSnapshot:
    """状态快照 — 可序列化的状态副本"""

    def __init__(self, data: dict, timestamp: float = None):
        self.data = data
        self.timestamp = timestamp or time.time()

    def to_json(self) -> str:
        return json.dumps(self.data, ensure_ascii=False, default=str)

    def age_seconds(self) -> float:
        return time.time() - self.timestamp


class ObservableState:
    """可观察状态 — 变更时通知订阅者"""

    def __init__(self):
        self._lock = threading.RLock()
        self._watchers: dict[str, list[Callable]] = defaultdict(list)
        self._snapshots: list[StateSnapshot] = []
        self._max_snapshots = 30

    def watch(self, key: str, callback: Callable[[str, Any, Any], None]) -> Callable:
        """监听某个 key 的变化。callback(key, old_val, new_val)。返回取消函数。"""
        with self._lock:
            self._watchers[key].append(callback)
        def unbind():
            with self._lock:
                try:
                    self._watchers[key].remove(callback)
                except ValueError:
                    pass
        return unbind

    def _notify(self, key: str, old_val: Any, new_val: Any):
        with self._lock:
            watchers = list(self._watchers.get(key, []))
            watchers.extend(self._watchers.get("*", []))
        for cb in watchers:
            try:
                cb(key, old_val, new_val)
            except Exception:
                import traceback
                traceback.print_exc()

    def snapshot(self) -> StateSnapshot:
        """创建当前状态快照"""
        with self._lock:
            data = self._collect_snapshot_data()
            snap = StateSnapshot(data)
            self._snapshots.append(snap)
            if len(self._snapshots) > self._max_snapshots:
                self._snapshots = self._snapshots[-self._max_snapshots:]
            return snap

    def _collect_snapshot_data(self) -> dict:
        raise NotImplementedError

    def rollback(self, steps: int = 1) -> bool:
        with self._lock:
            if len(self._snapshots) < steps:
                return False
            self._snapshots = self._snapshots[:-steps]
            return True


# ════════════════════════════════════════════════════
# 应用状态
# ════════════════════════════════════════════════════
@dataclass
class AppStateData:
    running: bool = False
    shutdown: bool = False
    paused: bool = False
    input_file: Optional[str] = None
    last_batch_df: Any = None
    failed_stocks: list = field(default_factory=list)
    current_theme: str = "dark"
    active_tab: int = 0


class AppStateManager(ObservableState):
    """应用全局状态"""

    def __init__(self):
        super().__init__()
        self._data = AppStateData()
        self.log_queue = __import__('queue').Queue()
        self.ui_queue = __import__('queue').Queue()
        self.save_lock = threading.Lock()

    # ── 属性访问 ──
    @property
    def running(self) -> bool:
        return self._data.running

    @running.setter
    def running(self, v: bool):
        old = self._data.running
        self._data.running = v
        self._notify("running", old, v)

    @property
    def shutdown(self) -> bool:
        return self._data.shutdown

    @shutdown.setter
    def shutdown(self, v: bool):
        old = self._data.shutdown
        self._data.shutdown = v
        self._notify("shutdown", old, v)

    @property
    def paused(self) -> bool:
        return self._data.paused

    @paused.setter
    def paused(self, v: bool):
        old = self._data.paused
        self._data.paused = v
        self._notify("paused", old, v)

    @property
    def current_theme(self) -> str:
        return self._data.current_theme

    @current_theme.setter
    def current_theme(self, v: str):
        old = self._data.current_theme
        self._data.current_theme = v
        self._notify("current_theme", old, v)

    def _collect_snapshot_data(self) -> dict:
        return asdict(self._data)

    def set_shutdown(self):
        self.shutdown = True

    def is_shutdown(self) -> bool:
        return self._data.shutdown


# ════════════════════════════════════════════════════
# 市场状态
# ════════════════════════════════════════════════════
@dataclass
class MarketStateData:
    current_stock_code: str = ""
    current_stock_name: str = ""
    selected_sector: str = ""
    market_trend: str = ""          # bull / bear / sideways
    limit_up_count: int = 0
    market_sentiment: float = 0.0   # 市场情绪指数


class MarketStateManager(ObservableState):
    """市场数据状态 — 当前关注的股票、板块等"""

    def __init__(self):
        super().__init__()
        self._data = MarketStateData()
        self._stock_cache: dict[str, dict] = {}  # code → snapshot
        self._sector_stocks: dict[str, list] = {}  # sector → [codes]

    @property
    def current_stock_code(self) -> str:
        return self._data.current_stock_code

    @current_stock_code.setter
    def current_stock_code(self, v: str):
        old = self._data.current_stock_code
        self._data.current_stock_code = v
        self._notify("current_stock_code", old, v)

    @property
    def current_stock_name(self) -> str:
        return self._data.current_stock_name

    @current_stock_name.setter
    def current_stock_name(self, v: str):
        old = self._data.current_stock_name
        self._data.current_stock_name = v
        self._notify("current_stock_name", old, v)

    def set_current_stock(self, code: str, name: str = ""):
        self.current_stock_code = code
        self.current_stock_name = name

    def cache_stock(self, code: str, data: dict):
        self._stock_cache[code] = data

    def get_cached_stock(self, code: str) -> Optional[dict]:
        return self._stock_cache.get(code)

    def cache_sector_stocks(self, sector: str, stocks: list):
        self._sector_stocks[sector] = stocks

    def _collect_snapshot_data(self) -> dict:
        return asdict(self._data)


# ════════════════════════════════════════════════════
# 技能状态
# ════════════════════════════════════════════════════
@dataclass
class SkillStateData:
    active_skills: dict = field(default_factory=dict)   # skill_id → SkillContext
    completed_count: int = 0
    failed_count: int = 0
    total_tokens: int = 0
    last_skill_chain_id: str = ""


class SkillStateManager(ObservableState):
    """技能执行状态"""

    def __init__(self):
        super().__init__()
        self._data = SkillStateData()
        self._results: dict[str, Any] = {}  # skill_id → SkillResult

    def skill_started(self, skill_id: str, context: Any):
        self._data.active_skills[skill_id] = context
        self._notify("skill_started", None, skill_id)

    def skill_completed(self, skill_id: str, result: Any):
        self._data.active_skills.pop(skill_id, None)
        self._data.completed_count += 1
        self._data.total_tokens += getattr(result, 'tokens_used', 0)
        self._results[skill_id] = result
        self._notify("skill_completed", skill_id, result)

    def skill_failed(self, skill_id: str, error: str):
        self._data.active_skills.pop(skill_id, None)
        self._data.failed_count += 1
        self._notify("skill_failed", skill_id, error)

    def get_result(self, skill_id: str) -> Any:
        return self._results.get(skill_id)

    def _collect_snapshot_data(self) -> dict:
        return asdict(self._data)


# ════════════════════════════════════════════════════
# 运行时状态
# ════════════════════════════════════════════════════
@dataclass
class RuntimeStateData:
    provider: str = "qianfan"       # qianfan / openai / anthropic / local
    model: str = ""
    total_tokens: int = 0
    total_requests: int = 0
    total_cost_estimate: float = 0.0
    rate_limited_until: float = 0.0
    circuit_open: bool = False
    consecutive_failures: int = 0
    fallback_active: bool = False
    active_provider: str = ""


class RuntimeStateManager(ObservableState):
    """AI 运行时状态 — token、provider、熔断、限流"""

    def __init__(self):
        super().__init__()
        self._data = RuntimeStateData()
        self._provider_usage: dict[str, dict] = defaultdict(lambda: {
            "tokens": 0, "requests": 0, "failures": 0, "cost": 0.0
        })

    @property
    def provider(self) -> str:
        return self._data.provider

    @provider.setter
    def provider(self, v: str):
        old = self._data.provider
        self._data.provider = v
        self._notify("provider", old, v)

    def record_usage(self, provider: str, tokens: int, model: str = ""):
        self._data.total_tokens += tokens
        self._data.total_requests += 1
        self._data.model = model or self._data.model
        usage = self._provider_usage[provider]
        usage["tokens"] += tokens
        usage["requests"] += 1
        self._notify("token_used", None, {"provider": provider, "tokens": tokens})

    def record_failure(self, provider: str):
        self._data.consecutive_failures += 1
        self._provider_usage[provider]["failures"] += 1
        self._notify("provider_failure", provider, self._data.consecutive_failures)

    def record_success(self, provider: str):
        self._data.consecutive_failures = 0

    def set_rate_limited(self, until: float):
        self._data.rate_limited_until = until
        self._notify("rate_limited", None, until)

    def set_circuit_open(self, v: bool, reason: str = ""):
        self._data.circuit_open = v
        self._notify("circuit_open", not v, v)

    def get_usage_report(self) -> dict:
        return {
            "total_tokens": self._data.total_tokens,
            "total_requests": self._data.total_requests,
            "by_provider": dict(self._provider_usage),
        }

    def _collect_snapshot_data(self) -> dict:
        return asdict(self._data)


# ════════════════════════════════════════════════════
# 统一状态管理器
# ════════════════════════════════════════════════════
class StateManager:
    """
    统一状态管理器 — 所有模块通过此单例访问状态

    用法:
        from stock_app.state import manager

        manager.app.running = True
        manager.market.set_current_stock("000001", "平安银行")
        manager.skill.skill_started("skill_001", ctx)
    """

    def __init__(self):
        self.app = AppStateManager()
        self.market = MarketStateManager()
        self.skill = SkillStateManager()
        self.runtime = RuntimeStateManager()

    def snapshot_all(self) -> dict:
        return {
            "app": self.app.snapshot().data,
            "market": self.market.snapshot().data,
            "skill": self.skill.snapshot().data,
            "runtime": self.runtime.snapshot().data,
        }

    def dump_to_file(self, path: str):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.snapshot_all(), f, ensure_ascii=False, indent=2, default=str)

    def reset(self):
        """重置所有状态（测试用）"""
        self.__init__()


# 全局单例
manager = StateManager()
