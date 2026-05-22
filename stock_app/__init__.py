"""
涨停复盘分析工具 — 模块化版本

v9.9.8 架构调整 (Phase 1 止血):
  • App 类移到 stock_app.app.bootstrap
  • 顶层访问 stock_app.App 采用 PEP 562 lazy import —
    导入子模块 (e.g. stock_app.popup) 时不再触发 App 加载,
    可以独立 import / 测试。
"""
__version__ = "2.0"


def __getattr__(name):
    # 旧代码: from stock_app import App   仍然工作,但只在真访问 App 时
    # 才连锁加载 bootstrap → core → api_client → requests。
    if name == "App":
        from .app.bootstrap import App as _App
        return _App
    raise AttributeError(
        "module {!r} has no attribute {!r}".format(__name__, name))
