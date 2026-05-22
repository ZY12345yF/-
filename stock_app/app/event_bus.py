"""
全局事件总线 — v9.9.8 重构版

相比旧 stock_app/bus.py 的改进:
  • 增加 off() 取消订阅,避免悬挂回调把已销毁的窗体打死
  • 增加 once() 一次性订阅
  • emit() 异常隔离,一个 handler 抛错不影响后续 handler
  • 增加日志钩子,所有 emit 可被路由到 logger.debug
  • 事件名常量集中在 Events 类,新增事件必须在这里登记

向后兼容: stock_app/bus.py 仍然存在,通过 from .app.event_bus import * 转发,
所有现存 `from .bus import bus, Events` 不用改。

设计原则 (按文档 五·原则 1~4):
  • UI 之间禁止互相 import → 全部走 EventBus
  • Service 内部不允许 emit UI 事件,只 emit 业务事件
  • Controller 是唯一允许把"业务事件"翻译成"UI 操作"的层
"""
import threading
from collections import defaultdict


class EventBus:
    """
    线程安全的发布/订阅事件总线。

    用法:
        bus.on(Events.STOCK_CHANGED, callback)
        bus.emit(Events.STOCK_CHANGED, code, name)
        bus.off(Events.STOCK_CHANGED, callback)
    """

    def __init__(self):
        self._subs = defaultdict(list)
        self._lock = threading.Lock()
        # 调试钩子: 设为可调用对象后,所有 emit 都会被记录
        # e.g. bus.set_debug_logger(logger.debug)
        self._debug_logger = None

    # ────────────────────────────────────────────────
    # 订阅
    # ────────────────────────────────────────────────
    def on(self, event_name, callback):
        """
        订阅事件。同一个 callback 重复 on 不去重 (调用方自己保证)。
        返回 callback 本身,方便链式: handler = bus.on(...)
        """
        with self._lock:
            self._subs[event_name].append(callback)
        return callback

    def off(self, event_name, callback):
        """
        取消订阅。callback 必须是 on() 时传入的同一个对象。
        callback 不存在时静默 (避免重复 off 抛错)。
        """
        with self._lock:
            handlers = self._subs.get(event_name)
            if not handlers:
                return
            try:
                handlers.remove(callback)
            except ValueError:
                pass

    def once(self, event_name, callback):
        """订阅一次,触发后自动 off。"""
        def wrapper(*args, **kwargs):
            self.off(event_name, wrapper)
            return callback(*args, **kwargs)
        return self.on(event_name, wrapper)

    def clear(self, event_name=None):
        """清空某事件或全部事件的订阅。主要给测试用。"""
        with self._lock:
            if event_name is None:
                self._subs.clear()
            else:
                self._subs.pop(event_name, None)

    # ────────────────────────────────────────────────
    # 发布
    # ────────────────────────────────────────────────
    def emit(self, event_name, *args, **kwargs):
        """
        发布事件。handler 抛异常不会打断后续 handler。
        在持锁状态下拷贝 handlers 列表,再脱锁回调 — 避免 handler 内部
        再 on/off 时发生死锁或迭代污染。
        """
        with self._lock:
            handlers = list(self._subs.get(event_name, []))
        if self._debug_logger:
            try:
                self._debug_logger(
                    "[bus] %s args=%r kwargs=%r handlers=%d",
                    event_name, args, kwargs, len(handlers),
                )
            except Exception:
                pass
        for h in handlers:
            try:
                h(*args, **kwargs)
            except Exception:
                import traceback
                traceback.print_exc()

    # ────────────────────────────────────────────────
    # 工具
    # ────────────────────────────────────────────────
    def set_debug_logger(self, logger_callable):
        """注册 logger.debug,所有 emit 走它。"""
        self._debug_logger = logger_callable

    def handler_count(self, event_name):
        with self._lock:
            return len(self._subs.get(event_name, []))


# 全局唯一总线
bus = EventBus()


# ════════════════════════════════════════════════════
# 事件名常量 — 集中管理,新增必须在此登记
# 命名规则: 名词.动作 (过去式),snake_case
# ════════════════════════════════════════════════════
class Events:
    # ── 旧事件 (保留,跟原 bus.py 一致,不能动) ──
    API_KEYS_CHANGED   = "api_keys_changed"
    THEME_CHANGED      = "theme_changed"
    PROMPT_CHANGED     = "prompt_changed"
    SETTINGS_CHANGED   = "settings_changed"
    HISTORY_UPDATED    = "history_updated"
    FAVORITES_UPDATED  = "favorites_updated"
    BATCH_STARTED      = "batch_started"
    BATCH_COMPLETED    = "batch_completed"
    REQUEST_BATCH_RUN  = "request_batch_run"

    # ── v9.9.8 新增 (Phase 1) ──
    # Popup 域事件 — 跨页面联动用,内部 popup 不需要走 bus
    POPUP_STOCK_SHOWN     = "popup.stock_shown"      # (code, name)
    POPUP_MINIMIZED       = "popup.minimized"
    POPUP_RESTORED        = "popup.restored"
    POPUP_FOLLOW_CHANGED  = "popup.follow_changed"   # (enabled: bool)

    # 同花顺联动事件
    HEXIN_STOCK_DETECTED  = "hexin.stock_detected"   # (code) — watcher 读到了
    HEXIN_PUSH_OK         = "hexin.push_ok"          # (code, prefix)
    HEXIN_PUSH_FAILED     = "hexin.push_failed"      # (code, reason)
