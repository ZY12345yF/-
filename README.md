# Stock AI Engine v10.0

**AI Native 量化金融操作系统** — 为多 AI Agent 长期协同维护而设计的股票分析平台。

## 项目概览

基于 Python Tkinter 的桌面端股票涨停复盘工具，经过 v10.0 激进式架构重构，从单文件屎山演进为分层模块化的 AI 操作系统。

### 核心能力

- **AI 智能分析** — 千帆/火山/OpenAI/Anthropic 多Provider自动路由，涨停原因、板块识别、情绪分析
- **概念图谱** — 概念→子概念→个股的层次化知识图谱，支持热度传播与时间衰减
- **技能系统** — 所有AI能力封装为可插拔 Skill，支持链式调用、重试、缓存、熔断
- **同花顺联动** — 内存桥接双向同步，代码推送 + 实时跟随
- **数据源整合** — 东方财富涨停/板块/龙虎榜 + 腾讯实时行情
- **标签关联度** — AI驱动的标签共现挖掘与聚类分析

### 架构

```
stock_app/
├── skills/          ⭐ AI技能系统 (BaseSkill/Registry/Executor/Scheduler)
├── prompts/         ⭐ Prompt集中管理 (模板/版本/缓存)
├── runtime/         ⭐ AI运行时 (Token/CircuitBreaker/RateLimiter/Router)
├── state/           ⭐ 统一状态管理 (App/Market/Skill/Runtime)
├── events/          ⭐ 事件驱动系统 (30+事件类型)
├── schemas/         ⭐ 数据Schema (AIAnalysisResult/StockSnapshot)
├── workflows/       ⭐ 工作流引擎 (DAG编排)
├── cache/           ⭐ 概念图谱 (ConceptGraph)
├── repositories/    数据访问层 (SQLite/JSON)
├── services/        业务逻辑层
├── integrations/    东方财富/腾讯/千帆/同花顺
├── core/            核心函数库
├── ui/              UI组件 (纯视图)
├── tabs/            8个功能Tab
└── popup/           浮窗系统
```

### 验证

```
Pass 1 (重构核心) : 75/75 通过 ✅
Pass 2 (顶层启动) :  3/3 通过 ✅
Pass 3 (AST扫描)  :  相对import全部存在 ✅
Pass 4 (API一致)  :  12个公开方法就位 ✅
```

运行验证：`python verify_imports.py`

### 文档

| 文档 | 说明 |
|------|------|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | 总体架构设计 |
| [docs/AI_SKILL_SYSTEM.md](docs/AI_SKILL_SYSTEM.md) | 技能系统 |
| [docs/EVENT_SYSTEM.md](docs/EVENT_SYSTEM.md) | 事件驱动 |
| [docs/STATE_SYSTEM.md](docs/STATE_SYSTEM.md) | 状态管理 |
| [docs/ROADMAP.md](docs/ROADMAP.md) | 路线图 |
| [docs/TECH_DEBT.md](docs/TECH_DEBT.md) | 技术债 |
| [docs/PROJECT_STATE.md](docs/PROJECT_STATE.md) | 当前状态 |

### 启动

```bash
python main.py
```

依赖：Python 3.10+, tkinter, matplotlib, requests, pywin32（同花顺联动需Windows）

### 技术栈

Python · Tkinter · matplotlib · SQLite · 千帆API · OpenAI API · Claude API · 东方财富API · 腾讯行情API

### 分支策略

```
main       — 稳定版本
develop    — 开发主线 (当前)
feature/*  — 功能分支
```

### 当前状态

- 133个Python文件 · 18,784行
- 最大单文件593行 · 仅2个超500行红线
- 架构完成度~80% · 测试覆盖率0%（待补充）

---

*从 v9.9.8 屎山重构为 v10.0 AI操作系统 — 证明任何代码都可以被拯救。*
