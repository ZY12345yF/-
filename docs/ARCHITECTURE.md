# 架构文档 — AI Native 量化分析系统 v10.0

## 设计哲学

本项目不是传统 Python 应用，而是 **AI Native Architecture** — 为多 AI Agent 长期协同维护而设计的量化金融操作系统。

### 核心原则

1. **UI层禁止任何业务逻辑** — UI 只负责渲染和事件转发
2. **所有逻辑必须 Service 化** — 业务逻辑在 services/
3. **所有 AI 能力必须 Skill 化** — AI 调用在 skills/
4. **所有数据必须 Repository 化** — 数据访问在 repositories/
5. **所有事件必须 EventBus 化** — 模块通信走 events/
6. **所有输出必须 Schema 化** — 数据结构在 schemas/
7. **所有配置必须集中管理** — 配置在 infrastructure/config/
8. **所有 Prompt 必须集中管理** — Prompt 在 prompts/
9. **所有状态必须 StateManager 化** — 状态在 state/
10. **所有 AI 结果必须可追踪** — 追踪在 runtime/

## 目录结构

```
stock_app/
├── app/               # 应用启动、事件总线、状态
│   ├── event_bus.py   # EventBus 核心实现
│   ├── state.py       # AppState 实现
│   └── bootstrap.py   # App 主类 (~415行)
│
├── core/              # 核心业务逻辑（纯函数，无UI依赖）
│   ├── config.py      # 配置加载
│   ├── history.py     # 历史数据逻辑
│   ├── replay.py      # 复盘逻辑
│   ├── sector.py      # 板块逻辑
│   ├── tag_relation/  # 标签关联度（已拆分）
│   │   ├── normalize.py
│   │   ├── compute.py
│   │   └── ai.py
│   └── ...
│
├── services/          # 业务服务层（协调 repositories + AI）
│   ├── history_service.py
│   └── sector_service.py
│
├── repositories/      # 数据访问层（SQLite / JSON / API）
│   ├── history_repository.py
│   └── sector_repository.py
│
├── controllers/       # 应用控制器（业务事件 → UI操作翻译）
│
├── domain/            # 领域模型
│   ├── models/        # 数据模型
│   └── events/        # 领域事件定义
│
├── integrations/      # 外部API集成
│   ├── eastmoney/     # 东方财富API
│   ├── tencent/       # 腾讯行情API
│   ├── qianfan/       # 千帆/火山AI
│   └── hexin/         # 同花顺桥接
│
├── infrastructure/    # 基础设施
│   ├── threading/     # 线程管理
│   ├── logging/       # 日志系统
│   ├── cache/         # 缓存系统
│   ├── config/        # 配置管理
│   └── database/      # 数据库管理
│
├── ui/                # UI组件（纯视图，无业务逻辑）
│   ├── themes/        # 主题系统
│   ├── shared/        # 共享组件
│   └── windows/       # 窗口组件
│       ├── popup/     # 浮窗组件
│       ├── history/   # 历史窗口
│       ├── sector/    # 板块窗口
│       └── settings/  # 设置窗口
│
├── tabs/              # Tab页面
│   ├── sector/        # 板块分析Tab (拆分中)
│   ├── history/       # 历史Tab (已拆分)
│   │   ├── menus.py
│   │   ├── operations.py
│   │   ├── auto_mode.py
│   │   └── import_subtags.py
│   ├── replay/        # 复盘Tab (已拆分)
│   │   ├── daily.py
│   │   ├── profile.py
│   │   ├── trend.py
│   │   ├── similar.py
│   │   └── track.py
│   └── my_sectors/    # 我的板块Tab
│       ├── tag_relation_view.py
│       ├── tag_relation_scan.py
│       ├── tag_relation_ai.py
│       └── tag_relation_manager.py
│
├── popup/             # 浮窗系统 (已拆分)
│   ├── state.py       # 浮窗状态
│   ├── view.py        # 浮窗视图
│   ├── render.py      # 浮窗渲染
│   ├── controller.py  # 浮窗控制器
│   ├── hexin_ctrl.py  # 同花顺联动
│   ├── lifecycle.py   # 窗口生命周期
│   ├── sync.py        # 同步模块
│   ├── ball.py        # 悬浮球
│   ├── drag.py        # 拖拽
│   ├── updater.py     # 行情更新
│   └── facade.py      # 对外门面
│
├── skills/            # AI技能系统 ⭐ 核心创新
│   ├── base.py        # BaseSkill, SkillContext, SkillResult
│   ├── registry.py    # SkillRegistry 动态注册
│   ├── executor.py    # SkillExecutor 超时/重试/缓存
│   ├── scheduler.py   # SkillScheduler 优先级/并发
│   └── sector/        # 板块分析技能
│       news/          # 新闻分析技能
│       sentiment/     # 情绪分析技能
│       ...
│
├── prompts/           # Prompt集中管理 ⭐
│   └── __init__.py    # PromptManager + 内置模板
│
├── runtime/           # AI运行时系统 ⭐
│   └── __init__.py    # TokenTracker, CircuitBreaker, RateLimiter, ProviderRouter
│
├── state/             # 统一状态管理 ⭐
│   └── __init__.py    # StateManager (App/Market/Skill/Runtime State)
│
├── events/            # 事件定义系统 ⭐
│   └── __init__.py    # DomainEvents + 事件名注册
│
├── schemas/           # 数据Schema系统 ⭐
│   ├── ai_result.py   # AIAnalysisResult 统一输出结构
│   └── stock.py       # StockSnapshot, ConceptNode
│
├── workflows/         # 工作流系统 ⭐
│   └── __init__.py    # WorkflowEngine + BaseWorkflow
│
└── cache/             # 概念图谱系统 ⭐
    └── __init__.py    # ConceptGraph (概念→子概念→个股)
```

## 数据流

```
用户操作 → UI (tabs/) → EventBus (events/)
         → Controller (controllers/) → Service (services/)
         → Repository (repositories/) → 数据库/API
         → Skill (skills/) → AI API (integrations/)
         → Schema 验证 (schemas/)
         → EventBus → UI 刷新
```

## 依赖方向（严格遵守）

```
ui/ → controllers/ → services/ → repositories/ → 数据库
                  → skills/     → integrations/ → AI API
                  → runtime/    → Token/Circuit/RateLimit

禁止: ui/ ↔ ui/ 直接互相 import
禁止: services/ 直接操作 UI
禁止: integrations/ 直接操作 UI
```

## 关键设计决策

| 决策 | 原因 |
|------|------|
| Skill 系统独立于 UI | AI 能力可被命令行/API/定时任务复用 |
| EventBus 单向通知 | 解耦 Tab 间通信，可测试 |
| ConceptGraph 与标签系统并存 | 概念图谱是语义层，标签是数据层 |
| Tkinter 保留 | 桌面端快速迭代，暂不重写为 Web |
| 全局单例 StateManager | 替代分散的全局变量，支持快照/回滚 |
