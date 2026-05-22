"""
Prompt 集中管理系统 — v10.0 AI Native 架构

设计原则:
  • 所有 prompt 必须集中管理,禁止散落在 UI 或 Service 代码中
  • 支持模板变量、版本控制、缓存
  • 支持多 provider 格式 (千帆/OpenAI/Anthropic)
"""
import json, re, time
from pathlib import Path
from typing import Optional


class PromptTemplate:
    """单个 Prompt 模板"""

    def __init__(self, name: str, template: str, version: str = "1.0.0",
                 variables: list = None, description: str = "", provider: str = "default"):
        self.name = name
        self.template = template
        self.version = version
        self.variables = variables or re.findall(r'\{(\w+)\}', template)
        self.description = description
        self.provider = provider

    def render(self, **kwargs) -> str:
        return self.template.format(**{k: kwargs.get(k, f"{{{k}}}") for k in self.variables})

    def to_dict(self) -> dict:
        return {"name": self.name, "template": self.template, "version": self.version,
                "variables": self.variables, "description": self.description, "provider": self.provider}


class PromptManager:
    """Prompt 管理器 — 全局单例"""

    def __init__(self):
        self._templates: dict[str, PromptTemplate] = {}
        self._versions: dict[str, list[PromptTemplate]] = {}
        self._cache: dict[str, tuple[float, str]] = {}
        self._cache_ttl = 300

    def register(self, template: PromptTemplate):
        self._templates[template.name] = template
        self._versions.setdefault(template.name, []).append(template)

    def register_many(self, templates: list):
        for t in templates:
            self.register(t)

    def get(self, name: str, use_cache: bool = True, **variables) -> str:
        template = self._templates.get(name)
        if not template:
            raise KeyError(f"Prompt 模板不存在: {name}")
        if not variables:
            return template.template
        cache_key = f"{name}:{template.version}:{json.dumps(variables, sort_keys=True, ensure_ascii=False)}"
        if use_cache:
            entry = self._cache.get(cache_key)
            if entry and time.time() - entry[0] < self._cache_ttl:
                return entry[1]
        rendered = template.render(**variables)
        if use_cache:
            self._cache[cache_key] = (time.time(), rendered)
        return rendered

    def get_template(self, name: str) -> Optional[PromptTemplate]:
        return self._templates.get(name)

    def list_all(self) -> list[str]:
        return list(self._templates.keys())

    def clear_cache(self):
        self._cache.clear()

    def export_all(self) -> dict:
        return {n: t.to_dict() for n, t in self._templates.items()}


# 全局单例
manager = PromptManager()


# ── 内置 Prompt 注册 ──
def _register_builtins():
    manager.register(PromptTemplate(
        name="stock_analysis", version="2.0.0", provider="qianfan",
        description="千帆AI单股分析 — 涨停复盘核心prompt",
        template="{stock_name}({stock_code}) 的最新AI解读，字数不超过200字。\n必须按以下格式输出：\n\n①个股联动题材(必须带6位代码):列出3~6个联动标的，逐个点出逻辑\n②市场主要上涨的核心共识(核心题材、传导逻辑)\n③个股涨停核心原因(包括涨停时间和形态)\n④同逻辑联动标的(带分析，必须带1~5个6位代码)\n⑤其他信息，值得注意的市场信号\n",
    ))
    manager.register(PromptTemplate(
        name="sector_analysis", version="1.0.0", provider="qianfan",
        description="板块分析 — 识别个股所属板块和概念",
        variables=["stock_name", "stock_code", "extra_context"],
        template="请分析股票 {stock_name}({stock_code}) 所属的板块和概念。\n\n额外上下文: {extra_context}\n\n请以JSON格式输出：\n{{\"main_sector\": \"\", \"sub_sectors\": [], \"concepts\": [], \"policy_tags\": [], \"hot_level\": 0, \"reasoning\": \"\"}}",
    ))
    manager.register(PromptTemplate(
        name="tag_clustering", version="1.0.0", provider="qianfan",
        description="标签聚类 — 对标签进行AI推理聚类",
        variables=["tags"],
        template="你是一个金融标签分析专家。请对以下标签进行聚类分析。\n\n标签列表: {tags}\n\n请输出聚类结果，每组包含：聚类名称、包含的标签、聚类逻辑说明。\n输出格式为JSON数组。",
    ))
    manager.register(PromptTemplate(
        name="concept_relation", version="1.0.0", provider="qianfan",
        description="概念关联分析",
        variables=["tag_a", "tag_b"],
        template="在股票市场语境下，标签「{tag_a}」和「{tag_b}」是否属于同一概念或上下游关系？\n请用中文简要回答（≤50字），并给出置信度(0~1)。",
    ))
    manager.register(PromptTemplate(
        name="sentiment_analysis", version="1.0.0", provider="qianfan",
        description="情绪分析",
        variables=["stock_name", "content"],
        template="分析以下文本对股票 {stock_name} 的市场情绪影响：\n\n{content}\n\n请输出JSON：\n{{\"score\": 0.0, \"label\": \"neutral\", \"keywords\": [], \"summary\": \"\"}}\nscore范围 -1.0(极度悲观) ~ 1.0(极度乐观)",
    ))
    manager.register(PromptTemplate(
        name="limit_up_reason", version="1.0.0", provider="qianfan",
        description="涨停原因深度分析",
        variables=["stock_name", "stock_code", "limit_time", "seal_strength", "sector"],
        template="请深度分析 {stock_name}({stock_code}) 的涨停原因：\n\n涨停时间: {limit_time}\n封板强度: {seal_strength}\n所属板块: {sector}\n\n请分析：\n1. 涨停核心驱动因素\n2. 资金性质(游资/机构/混合)\n3. 板块联动效应\n4. 次日预期\n\n字数不超过200字。",
    ))

_register_builtins()
