"""
技能执行器 — 超时控制、重试、fallback、token 统计

核心功能:
  • 单技能执行 + 超时控制
  • 技能链执行 (按依赖顺序)
  • 自动重试 (可配置次数和退避策略)
  • 缓存命中检查
  • Token 统计上报
  • 异常隔离
"""
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from typing import Callable, Optional

from .base import BaseSkill, SkillContext, SkillResult, SkillStatus
from .registry import SkillRegistry


class SkillExecutor:
    """
    技能执行器

    用法:
        executor = SkillExecutor(registry)
        ctx = SkillContext(input_data={"code": "000001"}, timeout=30)
        result = executor.execute("sector_analysis", ctx)
    """

    def __init__(self, registry: SkillRegistry, max_workers: int = 4):
        self.registry = registry
        self._pool = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="skill-")
        self._running: dict[str, SkillContext] = {}
        self._lock = threading.Lock()

        # 钩子
        self.on_skill_start: Optional[Callable] = None
        self.on_skill_done: Optional[Callable] = None
        self.on_skill_fail: Optional[Callable] = None
        self.on_token_used: Optional[Callable] = None

    def execute(self, skill_name: str, ctx: SkillContext = None) -> SkillResult:
        """
        执行单个技能 (同步,带超时控制)

        流程:
          1. 查注册表 → 2. 检查缓存 → 3. 验证输入 → 4. 执行 → 5. 缓存 → 6. 上报
        """
        ctx = ctx or SkillContext()
        skill = self.registry.get(skill_name)
        if not skill:
            return SkillResult(success=False, error=f"技能未注册: {skill_name}")

        # 缓存命中
        cached = skill.get_from_cache(ctx)
        if cached:
            return cached

        # 输入验证
        if not skill.validate_input(ctx):
            return SkillResult(success=False, error=f"输入验证失败: {skill_name}")

        ctx.skill_id = ctx.skill_id or skill_name

        # 执行 (带重试)
        result = self._execute_with_retry(skill, ctx)

        # 输出验证
        if result.success and not skill.validate_output(result):
            result = SkillResult(success=False, error="输出验证失败")

        # 缓存
        if result.success:
            skill.set_cache(ctx, result)

        # 上报 token
        if result.tokens_used and self.on_token_used:
            try:
                self.on_token_used(skill_name, result.tokens_used, result.provider)
            except Exception:
                pass

        return result

    def execute_async(self, skill_name: str, ctx: SkillContext = None) -> SkillResult:
        """异步执行技能 (非阻塞, 返回时可能未完成)"""
        ctx = ctx or SkillContext()
        ctx.skill_id = ctx.skill_id or skill_name

        with self._lock:
            self._running[ctx.skill_id] = ctx

        future = self._pool.submit(self._execute_async_wrapper, skill_name, ctx)
        future.add_done_callback(lambda f: self._on_async_done(ctx.skill_id, f))
        return SkillResult(success=True, data={"async": True, "skill_id": ctx.skill_id})

    def execute_chain(self, skill_names: list[str], ctx: SkillContext = None) -> list[SkillResult]:
        """
        执行技能链 — 按顺序执行,前一个的输出作为后一个的输入

        返回每个技能的结果列表。
        任一技能失败则停止后续执行。
        """
        ctx = ctx or SkillContext()
        results = []
        accumulated_data = dict(ctx.input_data)

        for name in skill_names:
            step_ctx = SkillContext(
                input_data=accumulated_data,
                timeout=ctx.timeout,
                priority=ctx.priority,
                chain_id=ctx.chain_id or ctx.skill_id,
            )
            result = self.execute(name, step_ctx)
            results.append(result)
            if not result.success:
                break
            # 累加输出到下一个输入
            accumulated_data.update(result.data)

        return results

    def _execute_with_retry(self, skill: BaseSkill, ctx: SkillContext) -> SkillResult:
        """执行 + 超时 + 重试"""
        last_error = ""
        max_retries = min(skill.max_retries, ctx.retry_count)

        for attempt in range(max_retries + 1):
            try:
                # 超时控制
                future = self._pool.submit(self._execute_one, skill, ctx)
                result = future.result(timeout=ctx.timeout)
                result.retry_count = attempt
                result.skill_id = ctx.skill_id
                return result

            except FutureTimeoutError:
                last_error = f"超时 ({ctx.timeout}s)"
                if attempt < max_retries:
                    time.sleep(1 * (attempt + 1))  # 退避
                continue
            except Exception as e:
                last_error = str(e)
                traceback.print_exc()
                if attempt < max_retries:
                    time.sleep(2 ** attempt)  # 指数退避
                continue

        return SkillResult(
            success=False,
            error=f"重试 {max_retries} 次后仍失败: {last_error}",
            skill_id=ctx.skill_id,
            retry_count=max_retries,
        )

    def _execute_one(self, skill: BaseSkill, ctx: SkillContext) -> SkillResult:
        """单次执行"""
        skill.on_before_execute(ctx)
        if self.on_skill_start:
            try:
                self.on_skill_start(skill.name, ctx)
            except Exception:
                pass

        t0 = time.time()
        try:
            result = skill.execute(ctx)
            result.latency_ms = int((time.time() - t0) * 1000)
            result.skill_id = ctx.skill_id
            result.model_used = result.model_used or skill.name
            result.provider = result.provider or "unknown"
            skill.on_after_execute(ctx, result)
            if self.on_skill_done:
                self.on_skill_done(skill.name, result)
        except Exception as e:
            result = SkillResult(
                success=False,
                error=f"{type(e).__name__}: {e}",
                latency_ms=int((time.time() - t0) * 1000),
                skill_id=ctx.skill_id,
            )
            skill.on_error(ctx, e)
            if self.on_skill_fail:
                self.on_skill_fail(skill.name, result)

        return result

    def _execute_async_wrapper(self, skill_name: str, ctx: SkillContext) -> SkillResult:
        return self.execute(skill_name, ctx)

    def _on_async_done(self, skill_id: str, future):
        with self._lock:
            self._running.pop(skill_id, None)

    def cancel(self, skill_id: str) -> bool:
        """取消正在执行的技能 (尽力)"""
        with self._lock:
            if skill_id in self._running:
                del self._running[skill_id]
                return True
        return False

    def running_count(self) -> int:
        with self._lock:
            return len(self._running)

    def shutdown(self):
        self._pool.shutdown(wait=False)
