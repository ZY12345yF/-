"""
AI 分析结果 Schema — 统一的 AI 输出结构

所有 AI 分析（新闻、公告、涨停原因、情绪等）的输出必须符合此 Schema。
Controller 层负责把原始 AI 文本解析到此结构，UI 层只消费此结构。
"""
from dataclasses import dataclass, field, asdict
from typing import Optional
from datetime import datetime


@dataclass
class ConceptResult:
    """概念/板块识别结果"""
    name: str = ""
    weight: float = 0.0          # 0.0 ~ 1.0 关联强度
    confidence: float = 0.0       # AI 置信度
    reasoning: str = ""           # AI 推理链


@dataclass
class SentimentResult:
    """情绪分析结果"""
    score: float = 0.0            # -1.0 ~ 1.0, 负=悲观 正=乐观
    label: str = "neutral"        # positive / negative / neutral / mixed
    keywords: list = field(default_factory=list)
    summary: str = ""


@dataclass
class AIAnalysisResult:
    """
    统一的 AI 分析输出结构

    输入: 新闻/公告/涨停原因 等文本
    输出: 此结构
    """
    # ── 基础信息 ──
    stock_code: str = ""
    stock_name: str = ""
    analysis_type: str = ""        # news / announcement / limit_up / policy / sentiment
    generated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    # ── 核心分析 ──
    main_sector: str = ""          # 主板块
    sub_sectors: list = field(default_factory=list)
    concepts: list = field(default_factory=list)  # List[ConceptResult]
    policy_tags: list = field(default_factory=list)

    # ── 市场研判 ──
    emotion_score: float = 0.0     # 情绪分数 -1.0 ~ 1.0
    market_stage: str = ""         # 市场阶段: 启动/发酵/高潮/分歧/退潮
    capital_style: list = field(default_factory=list)  # 资金风格
    hot_level: int = 0             # 热度等级 0~10

    # ── AI 元信息 ──
    reasoning_chain: list = field(default_factory=list)
    confidence: float = 0.0        # 0.0 ~ 1.0
    model_used: str = ""
    provider: str = ""             # qianfan / openai / anthropic / local
    tokens_used: int = 0
    latency_ms: int = 0

    # ── 来源追溯 ──
    source_urls: list = field(default_factory=list)
    raw_prompt: str = ""
    raw_response: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    def is_reliable(self, threshold: float = 0.6) -> bool:
        return self.confidence >= threshold

    def summary(self) -> str:
        """生成可读摘要"""
        parts = []
        if self.main_sector:
            parts.append(f"主板块: {self.main_sector}")
        if self.sub_sectors:
            parts.append(f"子板块: {', '.join(self.sub_sectors[:3])}")
        if self.emotion_score != 0:
            emo = "乐观" if self.emotion_score > 0 else "悲观" if self.emotion_score < 0 else "中性"
            parts.append(f"情绪: {emo}({self.emotion_score:+.2f})")
        if self.market_stage:
            parts.append(f"阶段: {self.market_stage}")
        parts.append(f"热度: {'★' * self.hot_level}{'☆' * (10 - self.hot_level)}")
        return " | ".join(parts)


@dataclass
class BatchAnalysisResult:
    """批量分析结果"""
    total: int = 0
    completed: int = 0
    failed: int = 0
    results: list = field(default_factory=list)  # List[AIAnalysisResult]
    errors: list = field(default_factory=list)
    started_at: str = ""
    completed_at: str = ""
    total_tokens: int = 0
    total_cost_estimate: float = 0.0
