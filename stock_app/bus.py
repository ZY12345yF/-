"""
向后兼容 shim — v10.0

bus / Events → stock_app.app.event_bus
state        → stock_app.app.state

旧代码 `from .bus import bus, Events, state` 继续可用。
新代码直接用 `from stock_app.app import bus, Events, state`
"""
from .app.event_bus import bus, Events, EventBus
from .app.state import state, AppState

__all__ = ["bus", "Events", "EventBus", "state", "AppState"]
