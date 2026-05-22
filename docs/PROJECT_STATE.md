# 项目当前状态

> 自动生成于 2026-05-21

## 规模

- 总 Python 文件: ~80+
- 总代码行数: ~16,000
- 最大文件: sector_tab.py (867行 → 拆分中)
- 文件数 >500行: 5 (拆分中)
- 文件数 300-500行: 12

## 架构完成度

| 系统 | 状态 | 完成度 |
|------|------|--------|
| EventBus | ✅ 生产就绪 | 100% |
| StateManager | ✅ 生产就绪 | 100% |
| Skill 系统 | ✅ 框架就绪 | 80% (需填充具体技能) |
| Prompt 管理 | ✅ 框架就绪 | 80% (需迁移旧prompt) |
| Runtime 系统 | ✅ 框架就绪 | 85% |
| Schema 系统 | ✅ 框架就绪 | 70% (需补充更多schema) |
| 概念图谱 | ✅ 框架就绪 | 60% (需灌入数据) |
| 工作流引擎 | ✅ 框架就绪 | 70% (需实现具体工作流) |
| Repository 层 | ⚠️  部分完成 | 40% (history/sector有,其余缺) |
| Service 层 | ⚠️  部分完成 | 40% |
| UI 去耦合 | ⚠️  进行中 | 50% |

## 模块列表

### 新增模块 (v10.0)

| 模块 | 路径 | 行数 |
|------|------|------|
| Skill 基类 | skills/base.py | 150 |
| Skill 注册表 | skills/registry.py | 90 |
| Skill 执行器 | skills/executor.py | 190 |
| Skill 调度器 | skills/scheduler.py | 160 |
| Prompt 管理器 | prompts/__init__.py | 95 |
| Runtime 系统 | runtime/__init__.py | 130 |
| State 管理器 | state/__init__.py | 388 |
| 事件定义 | events/__init__.py | 60 |
| Schema 系统 | schemas/ | 110 |
| 工作流引擎 | workflows/__init__.py | 120 |
| 概念图谱 | cache/__init__.py | 160 |

### 已拆分模块

| 原始文件 | 原来行数 | 拆分后主文件 | 子模块 |
|---------|---------|------------|--------|
| history_tab.py | 1070 | 301行 | 4个Mixin (236+250+149+190) |
| replay_tab.py | 732 | 59行 | 5个子Tab |
| tag_relation.py (UI) | 952 | 54行 | 4个Mixin |
| popup/view.py | 616 | 371行 | render.py (270) |
| popup/controller.py | 555 | 232行 | hexin_ctrl.py (134) + lifecycle.py (225) |

### 已删除模块

- `stock_app/bus.py` — 向后兼容 shim (功能在 app/event_bus.py)
- `stock_app/integrations/{eastmoney,qianfan,tencent}/` — 错误的目录名
- `HANDOVER.md` / `MIGRATION.md` — 临时交接文档
- `__pycache__/` — 所有 (25个)

## 风险模块

1. **sector_tab.py (867行)** — 正在拆分中，是当前最大风险
2. **bootstrap.py (415行)** — App 主类职责过多
3. **api_client.py** — 旧AI调用逻辑，需迁移到 Skill 系统
4. **settings_tab.py (432行)** — 超红线

## 下一步

1. 完成3个Agent的拆分任务
2. 运行 `python verify_imports.py` 验证
3. 实现具体 Skill（sector/news/sentiment）
4. 概念图谱数据初始化
5. UI 层 AI 调用迁移到 Skill 系统

---

## 修复记录

### 2026-05-22 · 联动股网格部分股不显示(全角括号 bug)

**症状**: 有些股能看到联动股 2×3 网格(如浙江世宝),有些看不到(如曙光股份)。

**根因**: `popup/render.py` 的 `_LINK_RE` 正则只匹配半角 `()`,不匹配全角 `（）`。千帆 AI 返回的内容里两种括号都存在——半角通常是模型本身,全角是中文输入法或人工编辑残留。曙光股份的内容用了全角,所以一只都识别不出来。

**修法**: 一处正则字符类调整,加入 U+FF08 和 U+FF09。

```python
# 之前
r'...[((]...[))]'   # 只有半角

# 现在
r'...[(\uff08]...[)\uff09]'   # 半角 + 全角
```

**影响面**: 改 1 个文件 1 行正则,符合放宽后的 bugfix 规则。

### 2026-05-22 · 联动股网格 layout 高度问题

**症状**: 浮窗顶部"股票名 价格 涨跌"右侧的联动股 2×3 网格区域完全空白。

**根因**: `popup/view.py` line1 容器的高度由 `_name_lbl` (16pt bold, ~28px) 决定。`_linked_frame` 默认随父容器收缩,而 grid 2 行需要 ~46px,被裁掉。

**修法**: `_linked_frame` 加 `height=46` + `pack_propagate(False)`,占住地盘不被压扁。

**影响面**: 改 1 个文件 (view.py),不动 service / controller / schema / event,view.py 372 → 378 行(仍在 500 限额内)。
