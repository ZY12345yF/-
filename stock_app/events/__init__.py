"""
事件系统 — 所有模块间通信统一走 EventBus

设计原则:
  • UI 之间禁止互相 import → 全部走 EventBus
  • Service 内部不允许 emit UI 事件,只 emit 业务事件
  • Controller 是唯一允许把业务事件翻译成 UI 操作的层
  • 所有事件名必须在此注册,禁止散落字符串
"""
from stock_app.app.event_bus import bus, Events, EventBus

# 扩展事件定义 — 新增事件统一在此登记
class DomainEvents:
    """业务域事件 — 不包含 UI 事件"""

    # ── 数据域 ──
    STOCK_DATA_READY    = "stock.data_ready"       # (code, data_dict)
    SECTOR_DATA_READY   = "sector.data_ready"      # (sector_name, data_dict)
    HISTORY_LOADED      = "history.loaded"          # (code, df)
    FAVORITES_CHANGED   = "favorites.changed"       # (action, data)

    # ── AI 技能域 ──
    SKILL_STARTED       = "skill.started"           # (skill_name, context_id)
    SKILL_COMPLETED     = "skill.completed"         # (skill_name, result)
    SKILL_FAILED        = "skill.failed"            # (skill_name, error)
    SKILL_CHAIN_STARTED = "skill.chain_started"     # (chain_id, skills[])
    SKILL_CHAIN_DONE    = "skill.chain_done"        # (chain_id, results[])

    # ── AI 分析域 ──
    AI_ANALYSIS_STARTED = "ai.analysis_started"     # (code, analysis_type)
    AI_ANALYSIS_DONE    = "ai.analysis_done"        # (code, result)
    AI_ANALYSIS_FAILED  = "ai.analysis_failed"      # (code, error)
    AI_BATCH_STARTED    = "ai.batch_started"        # (codes[])
    AI_BATCH_PROGRESS   = "ai.batch_progress"       # (done, total, current_code)
    AI_BATCH_DONE       = "ai.batch_done"           # (results[])

    # ── 概念图谱域 ──
    CONCEPT_UPDATED     = "concept.updated"          # (concept_name, data)
    CONCEPT_LINKED      = "concept.linked"           # (parent, child, weight)
    TAG_PROPAGATED      = "concept.tag_propagated"   # (tag, affected_stocks[])

    # ── 运行时域 ──
    RUNTIME_TOKEN_USED  = "runtime.token_used"       # (provider, tokens, model)
    RUNTIME_RATE_LIMIT  = "runtime.rate_limited"     # (provider, wait_seconds)
    RUNTIME_CIRCUIT_OPEN = "runtime.circuit_open"    # (provider, reason)
    RUNTIME_FALLBACK    = "runtime.fallback"          # (from_provider, to_provider)


# 合并所有事件名到统一命名空间
ALL_EVENTS = set()
for cls in (Events, DomainEvents):
    for attr in dir(cls):
        if not attr.startswith('_') and isinstance(getattr(cls, attr), str):
            ALL_EVENTS.add(getattr(cls, attr))
