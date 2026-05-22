# 代码风格

## Python 风格

- 变量/函数: snake_case
- 类: PascalCase
- 常量: UPPER_SNAKE_CASE
- 私有: _leading_underscore

## 文件组织

- 每文件 ≤ 500行 (红线)
- 每函数 ≤ 50行 (推荐)
- 每类 ≤ 10个方法 (推荐, Mixin 除外)

## Import 规则

```python
# 标准库
import os, json, threading

# 第三方
import tkinter as tk

# 项目内 — 使用相对导入
from ..core import config
from .base import BaseTab
```

## 注释规则

- **禁止冗余注释** — 不解释 WHAT,只解释 WHY
- 不写多行 docstring — 类/函数名已有信息
- 不写 `# 🔑 关键修复` 等表情注释 — 用 git commit message 记录
- 遗留版本号注释 (`v9.9.x`) — 逐步清理

## Mixin 规则

```python
class MyMixin:
    """不写 __init__, 属性由主类 build() 创建"""

    def some_method(self):
        # self.xxx 通过 MRO 自动解析
        self.treeview.insert(...)
```

## 架构红线

- ❌ UI 层不能有 AI 调用
- ❌ UI 层不能有数据库操作
- ❌ Service 层不能操作 UI
- ❌ 模块间不能直接 import (走 EventBus)
- ❌ Prompt 不能硬编码在代码中
- ❌ 状态不能存全局变量
