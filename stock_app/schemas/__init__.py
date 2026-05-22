"""
数据模式定义 — 所有 AI 输出、API 响应、内部数据结构必须 schema 化

设计原则:
  • 所有跨模块数据必须有 schema 约束
  • AI 输出必须经过 schema 验证后才能使用
  • Schema 变更必须向后兼容或显式升级版本
"""
from .ai_result import AIAnalysisResult, ConceptResult, SentimentResult
from .stock import StockSnapshot, StockBasicInfo
