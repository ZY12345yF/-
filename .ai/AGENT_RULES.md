# Agent 协作规则

## 核心原则

本项目是 **AI Native Architecture** — 为多 AI Agent 长期协同维护而设计。

## 协作规则

### 1. 代码修改规则

- **bugfix 允许局部修改** — 错就改,不必为一行 layout 改 6 个文件
- **新功能必须符合架构** — UI无逻辑 / Service化 / Schema化 / EventBus化
- **旧 shim 只保留不扩展** — 不在 shim 上加新逻辑
- **修改后更新 PROJECT_STATE.md** — 记录当前状态

> 历史规则 "禁止小修小补 / 禁止兼容历史屎山" 在重构期 (v9.9.8 → v10) 是有意义的,
> 防止在重构过程中又往旧代码里塞东西。重构完成后,bugfix 走最直接的路径,
> 不再仪式化要求每次改动都重写整个模块。
> 新功能仍然按架构 (Service / Schema / EventBus) 写,这条不变。

### 2. 文件操作规则

- **超过500行必须拆** — 无例外
- **超过800行视为架构错误** — 需彻底重构
- **新功能必须先设计方案** — 在 docs/ 或 .ai/ 写 plan
- **拆分用 Mixin 模式** — 不写 __init__,不改方法签名

### 3. 目录规则

- **skills/** — 所有 AI 能力放这里
- **prompts/** — 所有 Prompt 模板放这里
- **services/** — 所有业务逻辑放这里
- **repositories/** — 所有数据访问放这里
- **schemas/** — 所有数据结构放这里
- **integrations/** — 所有外部 API 放这里

### 4. 依赖规则

```
ui/ → controllers/ → services/ → repositories/
                  → skills/     → integrations/
                  → runtime/

禁止: ui/ ↔ ui/ 直接互相 import
禁止: services/ 直接操作 UI
禁止: integrations/ 直接操作 UI
```

### 5. 命名规则

- 文件名: snake_case
- 类名: PascalCase
- 事件名: `名词.动词_过去式` (如 `stock.data_ready`)
- Skill 名: snake_case (如 `sector_analysis`)

### 6. 验证规则

- 每次修改后运行 `python verify_imports.py`
- pass1 必须零错误
- pass2 错误可接受（环境依赖）
- 新增模块必须加入 verify_imports.py

## Git 规则 (待启用)

```
main        — 稳定版本
develop     — 开发主线
feature/*   — 功能分支
hotfix/*    — 紧急修复
```

禁止直接修改 main。
