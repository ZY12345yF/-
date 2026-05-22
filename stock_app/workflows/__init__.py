"""
工作流系统 — v10.0 AI Native 架构

支持: 技能编排 · 条件触发 · 定时任务 · DAG 流程 · 并发执行
"""
import threading, time, traceback
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional


class WFStatus(Enum):
    IDLE = "idle"; RUNNING = "running"; COMPLETED = "completed"; FAILED = "failed"; CANCELLED = "cancelled"


@dataclass
class Step:
    """工作流步骤"""
    name: str
    skill_name: str
    depends_on: list = field(default_factory=list)
    condition: Optional[Callable[[], bool]] = None
    timeout: int = 60
    retry: int = 1


@dataclass
class WFResult:
    workflow: str = ""
    status: WFStatus = WFStatus.IDLE
    steps: dict = field(default_factory=dict)
    started: float = 0.0; finished: float = 0.0
    total_tokens: int = 0; error: str = ""

    @property
    def success(self) -> bool: return self.status == WFStatus.COMPLETED
    @property
    def duration(self) -> float: return self.finished - self.started if self.finished else 0


class BaseWorkflow(ABC):
    name: str = ""; description: str = ""

    def __init__(self):
        self.status = WFStatus.IDLE
        self._steps: list[Step] = []
        self._step_map: dict[str, Step] = {}
        self._results: dict[str, Any] = {}

    @abstractmethod
    def define_steps(self) -> list[Step]: ...

    def add_step(self, s: Step):
        self._steps.append(s); self._step_map[s.name] = s

    def validate(self) -> list[str]:
        issues = []; names = set()
        for s in self._steps:
            if s.name in names: issues.append(f"重复: {s.name}")
            names.add(s.name)
            for d in s.depends_on:
                if d not in [x.name for x in self._steps]: issues.append(f"{s.name} 依赖未知: {d}")
        return issues


class WorkflowEngine:
    """工作流引擎 — 注册/调度/执行"""

    def __init__(self, skill_executor=None):
        self._wfs: dict[str, BaseWorkflow] = {}
        self._lock = threading.Lock()
        if skill_executor:
            self.skill_exec = skill_executor
        else:
            from stock_app.skills import executor; self.skill_exec = executor
        self.on_start: Optional[Callable] = None
        self.on_done: Optional[Callable] = None
        self.on_fail: Optional[Callable] = None

    def register(self, wf: BaseWorkflow):
        with self._lock:
            self._wfs[wf.name] = wf
            wf._steps = wf.define_steps()
            for s in wf._steps: wf._step_map[s.name] = s

    def get(self, name: str) -> Optional[BaseWorkflow]:
        return self._wfs.get(name)

    def list_all(self) -> list[str]: return list(self._wfs.keys())

    def run(self, name: str, input_data: dict = None) -> WFResult:
        wf = self.get(name)
        if not wf: return WFResult(workflow=name, status=WFStatus.FAILED, error=f"未注册: {name}")

        wf.status = WFStatus.RUNNING
        result = WFResult(workflow=name, status=WFStatus.RUNNING, started=time.time())
        if self.on_start:
            try: self.on_start(name, input_data)
            except: pass

        data = dict(input_data or {})
        try:
            issues = wf.validate()
            if issues: raise ValueError("; ".join(issues))
            done = set()
            while len(done) < len(wf._steps):
                ready = next((s for s in wf._steps if s.name not in done and all(d in done for d in s.depends_on)), None)
                if not ready: raise RuntimeError(f"死锁: {[s.name for s in wf._steps if s.name not in done]}")
                if ready.condition and not ready.condition(): continue

                from stock_app.skills.base import SkillContext
                ctx = SkillContext(input_data=data, timeout=ready.timeout, retry_count=ready.retry)
                sr = self.skill_exec.execute(ready.skill_name, ctx)
                result.steps[ready.name] = {"success": sr.success, "error": sr.error,
                                              "tokens": sr.tokens_used, "data": sr.data}
                result.total_tokens += sr.tokens_used
                if sr.success:
                    done.add(ready.name); data.update(sr.data or {})
                else:
                    raise RuntimeError(f"步骤 {ready.name} 失败: {sr.error}")
            result.status = WFStatus.COMPLETED
        except Exception as e:
            result.status = WFStatus.FAILED; result.error = str(e)
            traceback.print_exc()
            wf.status = WFStatus.FAILED
            if self.on_fail:
                try: self.on_fail(name, str(e))
                except: pass
        result.finished = time.time(); wf.status = result.status
        if result.success and self.on_done:
            try: self.on_done(name, result)
            except: pass
        return result

    def run_async(self, name: str, input_data: dict = None, cb: Callable = None):
        def r():
            res = self.run(name, input_data)
            if cb:
                try: cb(res)
                except: traceback.print_exc()
        t = threading.Thread(target=r, daemon=True, name=f"wf-{name}"); t.start(); return t


engine = WorkflowEngine()
