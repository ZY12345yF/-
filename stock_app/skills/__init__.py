"""
AI 技能系统 — v10.0 AI Native 架构核心

设计原则:
  • 所有 AI 能力必须 skill 化 — 禁止在 UI 层直接调 AI
  • 技能支持动态注册、热插拔、异步执行、技能链
  • 每个技能有独立的 context、result、cache、retry
  • 技能的输入/输出必须 schema 化

架构:
  BaseSkill      → 技能基类,定义 execute() 接口
  SkillContext    → 技能执行上下文 (输入、超时、优先级)
  SkillResult     → 技能执行结果 (输出、token、耗时)
  SkillRegistry   → 技能注册表 (动态注册、发现)
  SkillExecutor   → 技能执行器 (超时、重试、fallback)
  SkillScheduler  → 技能调度器 (优先级队列、并发控制)
"""
from .base import BaseSkill, SkillContext, SkillResult, SkillStatus
from .registry import SkillRegistry
from .executor import SkillExecutor
from .scheduler import SkillScheduler

# 全局实例
registry = SkillRegistry()
executor = SkillExecutor(registry)
scheduler = SkillScheduler(executor)
