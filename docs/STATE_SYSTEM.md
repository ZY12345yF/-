# 状态管理系统文档

## 概述

替代全局变量分散管理，统一为 StateManager 单例。支持快照、回滚、变更通知。

## StateManager

```python
from stock_app.state import manager

# 应用状态
manager.app.running = True
manager.app.shutdown  # → bool
manager.app.current_theme = "dark"

# 市场状态
manager.market.set_current_stock("000001", "平安银行")
manager.market.cache_stock("000001", snapshot_dict)

# 技能状态
manager.skill.skill_started("skill_001", ctx)
manager.skill.skill_completed("skill_001", result)

# 运行时状态
manager.runtime.record_usage("qianfan", 1500)
manager.runtime.get_usage_report()
```

## 子系统

### AppState

| 字段 | 说明 |
|------|------|
| running | 批量分析是否运行中 |
| shutdown | 应用关闭信号 |
| paused | 暂停标志 |
| input_file | 当前输入文件路径 |
| current_theme | 主题名 |
| log_queue | 日志队列(跨线程) |
| ui_queue | UI操作队列(跨线程) |

### MarketState

| 字段 | 说明 |
|------|------|
| current_stock_code | 当前聚焦股票 |
| current_stock_name | 当前聚焦股票名 |
| selected_sector | 当前选中板块 |
| _stock_cache | 股票快照缓存 |
| _sector_stocks | 板块成份股缓存 |

### SkillState

| 字段 | 说明 |
|------|------|
| active_skills | 正在执行的技能 |
| completed_count | 完成计数 |
| failed_count | 失败计数 |
| total_tokens | 累计Token |
| _results | 技能结果存储 |

### RuntimeState

| 字段 | 说明 |
|------|------|
| provider | 当前活跃Provider |
| total_tokens | 累计Token |
| total_requests | 累计请求数 |
| circuit_open | 熔断器状态 |
| consecutive_failures | 连续失败计数 |
| fallback_active | 降级激活中 |

## 变更监听

```python
# 监听特定字段变化
unbind = manager.app.watch("running", lambda key, old, new: print(f"{key}: {old} → {new}"))

# 监听所有变化
manager.app.watch("*", lambda key, old, new: print(f"changed: {key}"))

# 取消监听
unbind()
```

## 快照与持久化

```python
# 创建快照
snap = manager.app.snapshot()

# 导出到文件
manager.dump_to_file("state_snapshot.json")

# 回滚
manager.app.rollback(steps=1)
```
