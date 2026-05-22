"""
技能调度器 — 优先级队列、并发控制、定时触发

支持:
  • 优先级队列 (0=最高优先)
  • 并发度控制 (max_concurrent)
  • 依赖顺序执行
  • 定时/延迟执行
"""
import heapq
import queue
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

from .base import SkillContext, SkillResult
from .executor import SkillExecutor


@dataclass(order=True)
class _SkillJob:
    """调度队列中的技能作业"""
    priority: int
    created_at: float = field(compare=False)
    skill_name: str = field(compare=False)
    ctx: SkillContext = field(compare=False)
    callback: Optional[Callable] = field(compare=False, default=None)


class SkillScheduler:
    """
    技能调度器

    用法:
        scheduler = SkillScheduler(executor)
        scheduler.submit("sector_analysis", ctx, priority=2)
        scheduler.submit_after("news_analysis", ctx, delay_seconds=10)
        scheduler.start()  # 开始消费队列
        scheduler.stop()   # 停止
    """

    def __init__(self, executor: SkillExecutor, max_concurrent: int = 2):
        self.executor = executor
        self.max_concurrent = max_concurrent
        self._queue: list[_SkillJob] = []
        self._lock = threading.Lock()
        self._running = False
        self._worker_thread: Optional[threading.Thread] = None
        self._active_count = 0
        self._active_condition = threading.Condition(self._lock)
        self._delayed: list[tuple[float, _SkillJob]] = []  # (fire_at, job)

    def submit(self, skill_name: str, ctx: SkillContext = None,
               priority: int = 5, callback: Callable = None) -> str:
        """提交技能到调度队列"""
        ctx = ctx or SkillContext()
        ctx.priority = priority
        job = _SkillJob(
            priority=priority,
            created_at=time.time(),
            skill_name=skill_name,
            ctx=ctx,
            callback=callback,
        )
        with self._lock:
            heapq.heappush(self._queue, job)
        return ctx.skill_id

    def submit_after(self, skill_name: str, delay_seconds: float,
                     ctx: SkillContext = None, priority: int = 5,
                     callback: Callable = None) -> str:
        """延迟提交 — delay_seconds 秒后执行"""
        ctx = ctx or SkillContext()
        ctx.priority = priority
        job = _SkillJob(
            priority=priority,
            created_at=time.time(),
            skill_name=skill_name,
            ctx=ctx,
            callback=callback,
        )
        with self._lock:
            self._delayed.append((time.time() + delay_seconds, job))
        return ctx.skill_id

    def submit_chain(self, skill_names: list[str], ctx: SkillContext = None,
                     priority: int = 5, callback: Callable = None) -> str:
        """提交技能链 — 按顺序执行"""
        ctx = ctx or SkillContext()
        ctx.priority = priority

        # 把所有技能打包为一个作业
        for name in skill_names:
            step_ctx = SkillContext(
                input_data=dict(ctx.input_data),
                timeout=ctx.timeout,
                priority=priority,
                chain_id=ctx.skill_id,
            )
            self.submit(name, step_ctx, priority)

        return ctx.skill_id

    def start(self):
        """开始消费队列"""
        if self._running:
            return
        self._running = True
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True, name="skill-scheduler")
        self._worker_thread.start()

    def stop(self, wait: bool = True):
        """停止调度器"""
        self._running = False
        if wait and self._worker_thread:
            self._worker_thread.join(timeout=5)

    def _worker_loop(self):
        """调度主循环"""
        while self._running:
            # 处理延迟任务
            self._promote_delayed()

            # 检查并发度
            with self._lock:
                if self._active_count >= self.max_concurrent:
                    self._active_condition.wait(timeout=0.5)
                    continue

                if not self._queue:
                    # 没有任务,等待
                    self._active_condition.wait(timeout=0.5)
                    continue

                job = heapq.heappop(self._queue)
                self._active_count += 1

            # 在线程池中执行
            def do_job():
                try:
                    result = self.executor.execute(job.skill_name, job.ctx)
                    if job.callback:
                        try:
                            job.callback(result)
                        except Exception:
                            import traceback
                            traceback.print_exc()
                finally:
                    with self._lock:
                        self._active_count -= 1
                        self._active_condition.notify_all()

            self.executor._pool.submit(do_job)

    def _promote_delayed(self):
        """把到期延迟任务移到主队列"""
        now = time.time()
        with self._lock:
            ready = [(t, j) for t, j in self._delayed if t <= now]
            self._delayed = [(t, j) for t, j in self._delayed if t > now]
            for _, job in ready:
                heapq.heappush(self._queue, job)
            if ready:
                self._active_condition.notify_all()

    @property
    def queue_size(self) -> int:
        with self._lock:
            return len(self._queue)

    @property
    def delayed_size(self) -> int:
        with self._lock:
            return len(self._delayed)

    @property
    def active_count(self) -> int:
        with self._lock:
            return self._active_count

    def status(self) -> dict:
        with self._lock:
            return {
                "running": self._running,
                "queue_size": len(self._queue),
                "delayed_size": len(self._delayed),
                "active": self._active_count,
                "max_concurrent": self.max_concurrent,
            }
