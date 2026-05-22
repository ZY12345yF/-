"""
stock_app.app — 应用编排层

按 v9.9.8 架构方案二·目录结构,这里放:
    bootstrap.py    应用入口 (原 stock_app/app.py)
    event_bus.py    全局事件总线
    state.py        全局应用状态
    scheduler.py    (后续) 定时任务调度器,目前还在 core/

不放业务逻辑,只做"启动 + 拼装 + 跨模块通讯"。

App 类用 lazy __getattr__,这样:
    from stock_app.app import bus, Events, state    # 轻量
    from stock_app.app import App                   # 触发 bootstrap 加载
"""
# 轻量 (不依赖 tk / core / requests):
from .event_bus import bus, Events, EventBus  # noqa: F401
from .state import state, AppState  # noqa: F401

__all__ = ["App", "bus", "Events", "EventBus", "state", "AppState"]


def __getattr__(name):
    if name == "App":
        from .bootstrap import App as _App
        return _App
    raise AttributeError(
        "module {!r} has no attribute {!r}".format(__name__, name))
