# AI 技能系统文档

## 概述

Skill 系统是本架构的核心创新。所有 AI 能力被封装为独立的 **技能(Skill)**，支持动态注册、热插拔、异步执行、技能链、缓存、重试、熔断。

## 核心组件

### BaseSkill（技能基类）

```python
from stock_app.skills.base import BaseSkill, SkillContext, SkillResult

class MySkill(BaseSkill):
    name = "my_analysis"
    description = "我的分析技能"
    category = "sector"
    version = "1.0.0"
    cache_ttl = 300  # 缓存5分钟

    def execute(self, ctx: SkillContext) -> SkillResult:
        # 实现 AI 调用逻辑
        result = call_ai(ctx.input_data)
        return SkillResult(success=True, data=result)
```

### SkillContext（执行上下文）

| 字段 | 类型 | 说明 |
|------|------|------|
| input_data | dict | 输入数据 |
| timeout | int | 超时秒数 (默认60) |
| priority | int | 优先级 0-9 (0最高) |
| retry_count | int | 重试次数 |
| chain_id | str | 技能链 ID |
| depends_on | list | 前置技能 |

### SkillResult（执行结果）

| 字段 | 类型 | 说明 |
|------|------|------|
| success | bool | 是否成功 |
| data | dict | 输出数据 |
| error | str | 错误信息 |
| tokens_used | int | Token 消耗 |
| latency_ms | int | 耗时(毫秒) |
| model_used | str | 使用的模型 |
| provider | str | AI提供商 |
| cached | bool | 是否来自缓存 |

### SkillRegistry（注册表）

- `register(skill)` — 注册技能
- `unregister(name)` — 卸载技能（热插拔）
- `get(name)` — 获取技能实例
- `list_all()` / `list_by_category(cat)` — 发现技能
- `check_dependencies(name)` — 依赖检查

### SkillExecutor（执行器）

- `execute(name, ctx)` — 同步执行（含超时/重试/缓存）
- `execute_async(name, ctx)` — 异步执行
- `execute_chain(names, ctx)` — 技能链执行

### SkillScheduler（调度器）

- `submit(name, ctx, priority)` — 提交到优先级队列
- `submit_after(name, delay, ctx)` — 延迟执行
- `submit_chain(names, ctx)` — 提交技能链
- `start()` / `stop()` — 启停调度器
- `status()` — 队列状态

## 技能类别规划

| 类别 | 目录 | 描述 |
|------|------|------|
| sector | skills/sector/ | 板块识别、概念分析 |
| news | skills/news/ | 新闻解读、事件分析 |
| policy | skills/policy/ | 政策解读、行业影响 |
| sentiment | skills/sentiment/ | 情绪分析、市场心理 |
| finance | skills/finance/ | 财报分析、估值 |
| dragon_tiger | skills/dragon_tiger/ | 龙虎榜分析 |
| hot_money | skills/hot_money/ | 游资跟踪 |
| announcement | skills/announcement/ | 公告解读 |
| clustering | skills/clustering/ | AI聚类、标签发现 |

## 使用示例

```python
from stock_app.skills import registry, executor, scheduler
from stock_app.skills.base import SkillContext

# 单个技能
ctx = SkillContext(input_data={"code": "000001", "name": "平安银行"})
result = executor.execute("sector_analysis", ctx)

# 技能链
results = executor.execute_chain(
    ["sector_analysis", "sentiment_analysis", "limit_up_reason"],
    ctx
)

# 异步调度
scheduler.start()
scheduler.submit("news_analysis", ctx, priority=3)
```

## AI Provider 路由

系统自动处理 Provider 切换：

1. 默认: 千帆(支持搜索) → 火山(不支持搜索) → OpenAI → Anthropic → 本地
2. 熔断: 连续失败5次 → 自动切换下一个 Provider
3. 限流: 滑动窗口控制每分钟请求数
4. 并发: max_concurrent 限制同时请求数
