# 项目路线图

## 已完成 (v10.0)

- [x] 模块化重构：所有超大文件拆分到 ≤500行
- [x] Skill 技能系统：BaseSkill / Registry / Executor / Scheduler
- [x] Prompt 集中管理：PromptManager + 6个内置模板
- [x] AI Runtime 系统：TokenTracker / CircuitBreaker / RateLimiter / ProviderRouter
- [x] 统一状态管理：StateManager (App/Market/Skill/Runtime)
- [x] 事件定义系统：DomainEvents + 30+ 事件类型
- [x] Schema 系统：AIAnalysisResult / StockSnapshot / ConceptNode
- [x] 概念图谱：ConceptGraph (概念→子概念→个股)
- [x] 工作流引擎：WorkflowEngine + DAG执行
- [x] 代码清理：删除未使用import、重复逻辑、废弃函数
- [x] 历史Tab拆分：menus / operations / auto_mode / import_subtags
- [x] 复盘Tab拆分：daily / profile / trend / similar / track
- [x] 标签关联拆分：view / scan / ai / manager
- [x] 浮窗系统拆分：render / hexin_ctrl / lifecycle

## 进行中

- [ ] 板块分析Tab拆分 (Agent处理中)
- [ ] 同花顺桥接迁移到 integrations/hexin/ (Agent处理中)
- [ ] 标签关联核心逻辑拆分 (Agent处理中)

## 下一阶段 (v10.1)

- [ ] 实战技能实现：为 skills/sector/ news/ sentiment/ 等目录填充具体技能
- [ ] 概念图谱初始化：灌入 A股概念数据（从东方财富API爬取）
- [ ] 工作流实现：MorningWorkflow / AfterMarketWorkflow
- [ ] UI 去耦合：将 Tab 中的 AI 调用全部迁移到 Skill 系统
- [ ] Prompt 文件化：将 prompts/__init__.py 中的模板迁移到 .md 文件
- [ ] Web 化探索：FastAPI + React 替代 Tkinter方案评估
- [ ] 测试体系：pytest + mock skill 的单元测试
- [ ] 本地模型支持：Ollama / vLLM 集成

## 远期愿景 (v11.0+)

- [ ] 多Agent协作：多个AI Agent并行分析不同维度
- [ ] 实时行情推送：WebSocket替代轮询
- [ ] 因子回测引擎：基于概念图谱的量化因子
- [ ] 知识图谱可视化：D3.js / ECharts 交互式概念图
- [ ] Auto-GPT 自主分析：AI自主选题→分析→报告→推送
