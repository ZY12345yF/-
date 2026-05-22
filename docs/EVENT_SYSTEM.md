# 事件驱动架构文档

## 概述

所有模块间通信统一走 EventBus，禁止直接互相 import。

## EventBus API

```python
from stock_app.events import bus, Events, DomainEvents

# 订阅
bus.on(Events.STOCK_CHANGED, handler)
bus.once(DomainEvents.SKILL_COMPLETED, handler)

# 发布
bus.emit(Events.HISTORY_UPDATED, code, data)

# 取消
bus.off(Events.STOCK_CHANGED, handler)

# 调试
bus.set_debug_logger(logger.debug)
```

## 事件分类

### UI 事件 (Events)

| 事件 | 触发时机 | 参数 |
|------|---------|------|
| API_KEYS_CHANGED | API密钥变更 | - |
| THEME_CHANGED | 主题切换 | - |
| SETTINGS_CHANGED | 设置变更 | - |
| HISTORY_UPDATED | 历史记录更新 | (code, data) |
| FAVORITES_UPDATED | 收藏变更 | - |
| BATCH_STARTED | 批量开始 | - |
| BATCH_COMPLETED | 批量完成 | - |
| POPUP_STOCK_SHOWN | 浮窗显示股票 | (code, name) |
| HEXIN_STOCK_DETECTED | 同花顺检测到股票 | (code) |

### 业务域事件 (DomainEvents)

| 事件 | 触发时机 | 参数 |
|------|---------|------|
| STOCK_DATA_READY | 股票数据就绪 | (code, data) |
| SECTOR_DATA_READY | 板块数据就绪 | (sector, data) |
| SKILL_STARTED | 技能开始 | (skill_name, ctx_id) |
| SKILL_COMPLETED | 技能完成 | (skill_name, result) |
| SKILL_FAILED | 技能失败 | (skill_name, error) |
| AI_ANALYSIS_STARTED | AI分析开始 | (code, type) |
| AI_ANALYSIS_DONE | AI分析完成 | (code, result) |
| AI_BATCH_PROGRESS | 批量进度 | (done, total, code) |
| CONCEPT_UPDATED | 概念更新 | (concept, data) |
| RUNTIME_TOKEN_USED | Token使用 | (provider, tokens) |
| RUNTIME_CIRCUIT_OPEN | 熔断打开 | (provider, reason) |
| RUNTIME_FALLBACK | Provider降级 | (from, to) |

## 设计规则

1. **UI 之间禁止直接 import** → 全部走 EventBus
2. **Service 只 emit 业务事件** → 不 emit UI 事件
3. **Controller 翻译业务→UI** → 唯一允许跨层翻译的层
4. **事件名必须注册** → 新增事件在 Events/DomainEvents 中登记
5. **异常隔离** → handler 抛错不影响后续 handler
6. **线程安全** → emit/on/off 都持锁

## 典型流程

```
用户点击分析按钮
  → UI emit REQUEST_BATCH_RUN
  → Controller 收到,调用 Service
  → Service emit AI_BATCH_STARTED
  → Skill 执行,emit SKILL_STARTED / SKILL_COMPLETED
  → Service emit AI_BATCH_PROGRESS / AI_BATCH_DONE
  → Controller 翻译成 UI 事件
  → UI 收到,刷新显示
```
