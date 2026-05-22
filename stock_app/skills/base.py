"""
技能基类定义 — BaseSkill, SkillContext, SkillResult

所有 AI 技能必须继承 BaseSkill。
"""
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional


class SkillStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


@dataclass
class SkillContext:
    """
    技能执行上下文 — 不可变输入

    skill_id:     唯一标识,自动生成
    input_data:   输入数据 (dict / schema)
    timeout:      超时秒数,默认 60
    priority:     优先级,0=最高 9=最低
    retry_count:  最大重试次数
    chain_id:     技能链 ID (可选)
    depends_on:   依赖的前置技能 ID 列表
    metadata:     扩展元数据
    """
    input_data: dict = field(default_factory=dict)
    timeout: int = 60
    priority: int = 5
    retry_count: int = 2
    chain_id: str = ""
    depends_on: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    skill_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    created_at: float = field(default_factory=time.time)

    def is_expired(self) -> bool:
        return (time.time() - self.created_at) > self.timeout


@dataclass
class SkillResult:
    """
    技能执行结果 — 结构化输出

    success:      是否成功
    data:         输出数据 (dict / schema)
    error:        错误信息
    tokens_used:  Token 消耗
    latency_ms:   耗时(毫秒)
    model_used:   使用的模型
    provider:     AI 提供商
    skill_id:     关联的技能 ID
    retry_count:  实际重试次数
    cached:       是否来自缓存
    """
    success: bool = True
    data: dict = field(default_factory=dict)
    error: str = ""
    tokens_used: int = 0
    latency_ms: int = 0
    model_used: str = ""
    provider: str = ""
    skill_id: str = ""
    retry_count: int = 0
    cached: bool = False

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "tokens_used": self.tokens_used,
            "latency_ms": self.latency_ms,
            "model_used": self.model_used,
            "provider": self.provider,
            "skill_id": self.skill_id,
            "retry_count": self.retry_count,
            "cached": self.cached,
        }


class BaseSkill(ABC):
    """
    AI 技能基类

    所有技能必须:
      1. 继承此类
      2. 实现 execute()
      3. 设置 name / description / category
      4. 定义 input_schema / output_schema (可选,用于验证)

    用法:
        class SectorAnalysisSkill(BaseSkill):
            name = "sector_analysis"
            description = "板块分析:识别股票所属板块和概念"
            category = "sector"

            def execute(self, ctx: SkillContext) -> SkillResult:
                ...
    """

    name: str = ""
    description: str = ""
    category: str = ""
    version: str = "1.0.0"

    # schema 定义 (子类覆盖)
    input_schema: dict = None   # JSON Schema
    output_schema: dict = None

    # 运行时配置
    default_timeout: int = 60
    default_priority: int = 5
    max_retries: int = 2
    cache_ttl: int = 300        # 缓存有效期(秒), 0=不缓存

    # 依赖
    depends_on: list = []       # 依赖的其他 skill name 列表

    def __init__(self):
        self._cache: dict[str, tuple[float, SkillResult]] = {}

    @abstractmethod
    def execute(self, ctx: SkillContext) -> SkillResult:
        """执行技能 — 子类必须实现"""
        ...

    def validate_input(self, ctx: SkillContext) -> bool:
        """验证输入 — 子类可覆盖"""
        if self.input_schema is None:
            return True
        # 简单验证: 检查必需字段
        for key, spec in self.input_schema.get("properties", {}).items():
            if spec.get("required") and key not in ctx.input_data:
                return False
        return True

    def validate_output(self, result: SkillResult) -> bool:
        """验证输出 — 子类可覆盖"""
        return True

    def on_before_execute(self, ctx: SkillContext):
        """执行前钩子 — 日志/监控"""
        pass

    def on_after_execute(self, ctx: SkillContext, result: SkillResult):
        """执行后钩子 — 日志/缓存"""
        pass

    def on_error(self, ctx: SkillContext, error: Exception):
        """异常钩子 — 日志/报警"""
        pass

    def get_cache_key(self, ctx: SkillContext) -> str:
        """生成缓存 key"""
        import json
        raw = json.dumps(ctx.input_data, sort_keys=True, ensure_ascii=False, default=str)
        return f"{self.name}:{raw}"

    def get_from_cache(self, ctx: SkillContext) -> Optional[SkillResult]:
        """从缓存读取结果"""
        if self.cache_ttl <= 0:
            return None
        key = self.get_cache_key(ctx)
        entry = self._cache.get(key)
        if entry:
            ts, result = entry
            if time.time() - ts < self.cache_ttl:
                result.cached = True
                return result
            del self._cache[key]
        return None

    def set_cache(self, ctx: SkillContext, result: SkillResult):
        """缓存结果"""
        if self.cache_ttl <= 0:
            return
        key = self.get_cache_key(ctx)
        self._cache[key] = (time.time(), result)

    def __repr__(self):
        return f"<{self.__class__.__name__}(name={self.name}, v={self.version})>"
