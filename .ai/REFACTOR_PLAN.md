# 重构执行计划

## 阶段1: 架构基础 (✅ 已完成)

- [x] 创建新目录结构 (skills/prompts/runtime/state/events/schemas/workflows/cache)
- [x] 构建 Skill 系统 (BaseSkill/Registry/Executor/Scheduler)
- [x] 构建 Prompt 系统 (PromptManager + 模板)
- [x] 构建 Runtime 系统 (Token/Circuit/RateLimit/Router)
- [x] 构建 State 系统 (App/Market/Skill/Runtime)
- [x] 构建 Event 系统 (DomainEvents + 30+事件)
- [x] 构建 Schema 系统 (AIAnalysisResult/StockSnapshot/ConceptNode)
- [x] 构建 Workflow 系统 (WorkflowEngine)
- [x] 构建概念图谱 (ConceptGraph)
- [x] 创建文档系统 (docs/ 6文件)
- [x] 创建 AI 协作系统 (.ai/ 5文件)

## 阶段2: 代码清理 (✅ 已完成)

- [x] 删除 bus.py shim
- [x] 删除错误目录 {eastmoney,qianfan,tencent}
- [x] 删除 HANDOVER.md / MIGRATION.md
- [x] 清理所有 __pycache__
- [x] 删除未使用 import (5个文件)
- [x] 提取公共函数到 text_utils.py
- [x] 统一 _CODE_RE 定义
- [x] 删除未使用函数 (hexin_bridge.py)

## 阶段3: 文件拆分 (🔄 进行中)

- [x] history_tab.py (1070→301) — 4个Mixin
- [x] replay_tab.py (732→59) — 5个子Tab
- [x] tag_relation.py UI (952→54) — 4个Mixin
- [x] popup/view.py (616→371) — render.py
- [x] popup/controller.py (555→232) — hexin_ctrl + lifecycle
- [ ] sector_tab.py (867→目标300) — 拆分中
- [ ] hexin_bridge.py (595) — 迁移到 integrations/hexin/ 中
- [ ] core/tag_relation.py (559) — 拆分为子模块 中

## 阶段4: 验证 (⏳ 待做)

- [ ] 更新 verify_imports.py — 加入新模块路径
- [ ] 运行 python verify_imports.py — Pass 1必须零错误
- [ ] 检查所有 import 链路

## 阶段5: 技能实现 (⏳ 未来)

- [ ] skills/sector/ — 板块分析技能
- [ ] skills/news/ — 新闻分析技能
- [ ] skills/sentiment/ — 情绪分析技能
- [ ] skills/policy/ — 政策分析技能
- [ ] 注册所有技能到 registry

## 阶段6: 迁移 (⏳ 未来)

- [ ] batch_tab.py AI调用 → skills
- [ ] single_tab.py AI调用 → skills
- [ ] api_client.py 旧逻辑 → services + skills
- [ ] 所有 prompt 从代码移到 prompts/templates/*.md
