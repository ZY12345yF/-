# 当前任务上下文

## 会话目标

将涨停复盘分析工具重构为 **AI Native Architecture** —
可被多个 AI Agent 长期协同维护的量化金融操作系统。

## 当前阶段

**v10.0 架构重构** — 激进式全面重构

### 已完成
- [x] 新架构目录结构
- [x] Skill 技能系统 (BaseSkill/Registry/Executor/Scheduler)
- [x] Prompt 集中管理 (PromptManager + 6内置模板)
- [x] AI Runtime 系统 (Token/Circuit/RateLimit/Router)
- [x] 统一状态管理 (StateManager)
- [x] 事件定义系统 (DomainEvents)
- [x] Schema 系统 (AIAnalysisResult/StockSnapshot/ConceptNode)
- [x] 概念图谱 (ConceptGraph)
- [x] 工作流引擎 (WorkflowEngine)
- [x] 5个超大文件拆分 (history/replay/tag_relation/popup view/popup controller)
- [x] 未使用代码清理 (import/函数/重复逻辑)
- [x] 文档系统 (docs/ 6文件)
- [x] AI协作规则 (.ai/)

### 进行中 (Agent后台)
- [ ] sector_tab.py 拆分 (867行 → 目标≤300)
- [ ] hexin_bridge.py 迁移到 integrations/hexin/
- [ ] core/tag_relation.py 拆分为子模块

### 待做
- [ ] 运行 verify_imports.py 验证
- [ ] 更新 verify_imports.py 加入新模块检查
- [ ] 填充 skills/ 子目录的具体技能
- [ ] 概念图谱数据初始化
- [ ] UI 层 AI 调用迁移到 Skill 系统

## 关键约束

- 不做小修小补
- 不在旧架构上缝合
- 所有新代码必须符合 AI Native 架构
- 保持原有功能不变
