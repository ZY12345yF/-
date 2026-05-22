# 技术债清单

## 高优先级

| 项目 | 位置 | 风险 | 建议 |
|------|------|------|------|
| Tkinter 全局依赖 | 所有 tabs/ | 无法测试、无法换UI框架 | 抽取 ViewModel 层 |
| 全局 state 单例 | app/state.py | 测试隔离困难 | 依赖注入替代 |
| 线程管理分散 | 多个 tab | 线程泄漏风险 | 统一到 TaskManager |
| AI 调用散落 | batch_tab, single_tab | Prompt不一致、无重试 | 全部迁移到 Skill 系统 |
| 硬编码 prompt | api_client.py | 改 prompt 要改代码 | 迁移到 prompts/ |
| settings JSON 结构 | core/config.py | 字段散落、无 schema | 统一 SettingsSchema |

## 中优先级

| 项目 | 位置 | 风险 | 建议 |
|------|------|------|------|
| PopupWindow shim | popup_window.py | 26行兼容层 | 所有调用方迁移后删除 |
| bus.py → app/event_bus.py | 已删除 | - | ✅ |
| hexin_bridge 位置 | core/hexin_bridge.py | 逻辑属于 integration | 迁移到 integrations/hexin/ |
| widgets.py 函数过多 | widgets.py (410行) | 职责不清 | 拆分到 ui/shared/ |
| bootstrap.py 职能过重 | app/bootstrap.py (415行) | App 类做太多事 | 抽 KeyboardManager / PopupManager |
| batch_tab.py | tabs/batch_tab.py (538行) | 超500行红线 | 拆分批量操作逻辑 |

## 低优先级

| 项目 | 位置 | 风险 | 建议 |
|------|------|------|------|
| _NullPopup 类 | bootstrap.py | 防御性编程 | 改用 Optional[PopupWindow] |
| 旧注释 `v9.9.x` | 多处 | 信息噪音 | 清理历史版本注释 |
| verify_imports.py | 根目录 | mock 覆盖不全 | 补充新模块检查 |
| Tkinter theme 直接操作 | themes/ | 不支持运行时切换 | CSS-in-Python方案 |
| matplotlib 嵌入 | sector_tab, tag_relation | 启动慢、内存高 | 懒加载 + 后台渲染 |

## 已解决

| 项目 | 解决方案 |
|------|---------|
| ✅ history_tab.py 1070行 | 拆分为4个Mixin |
| ✅ replay_tab.py 732行 | 拆分为5个子Tab |
| ✅ tag_relation.py 952行 | 拆分为4个Mixin |
| ✅ popup view/controller 超500行 | 拆分为 render/hexin_ctrl/lifecycle |
| ✅ 重复 _CODE_RE | 统一到 text_utils.py |
| ✅ 重复 left_click_follow | 提取到 text_utils.py |
| ✅ 未使用 import | 批量清理 |
| ✅ 全局变量分散 | StateManager 统一管理 |
| ✅ Prompt 散落 | PromptManager 集中管理 |
| ✅ AI 调用无追踪 | Runtime 系统 token 统计 |
