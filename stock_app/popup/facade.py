"""
PopupWindow Facade — 向后兼容门面

原 popup_window.py 暴露的全部公开方法在这里全部转发到 PopupController。
旧代码 `from .popup_window import PopupWindow` (现在通过 shim 转到这里)
不需要任何改动。

设计理由 (按文档 三·popup 重构方案):
    > "在不影响现有功能的情况下,将系统从'页面驱动'改造成'驱动业务'"
    > "现有 UI 与功能行为一致,无法替代替代,必须支持渐进式迁移"

每一个原 PopupWindow 的方法 → 这里一行转发到 controller。
原 PopupWindow 直接暴露的属性 (app.py 里 `self._popup._hexin_status_var.set(...)`
这种) → 这里用 @property 转发。
"""
from .controller import PopupController


class PopupWindow:
    """
    浮窗主类的对外门面。结构上等价于:
        PopupWindow → PopupController → {state, view, sync, ball, drag, updater}
    """

    def __init__(self, app):
        self._ctrl = PopupController(app)

    # ════════════════════════════════════════════════
    # 老公开 API — 一行转发,签名保持一致
    # ════════════════════════════════════════════════
    def show(self, code, name=None):
        return self._ctrl.show(code, name)

    def hide(self):
        return self._ctrl.hide()

    def destroy(self):
        return self._ctrl.destroy()

    def notify_main_click(self, code, name=None):
        return self._ctrl.notify_main_click(code, name)

    def push_to_hexin(self, code, name=None):
        return self._ctrl.push_to_hexin(code, name)

    def is_follow_mode(self):
        return self._ctrl.is_follow_mode()

    def follow(self, code, name=None):
        return self._ctrl.follow(code, name)

    def lock_code(self, code, ttl=10.0):
        return self._ctrl.lock_code(code, ttl)

    def restart_hexin_watcher(self):
        return self._ctrl.restart_hexin_watcher()

    def toggle_visibility(self):
        return self._ctrl.toggle_visibility()

    def toggle_minimize(self):
        return self._ctrl.toggle_minimize()

    def undo(self):
        return self._ctrl.undo()

    # ════════════════════════════════════════════════
    # 老属性 — app.py 里 self._popup._hexin_status_var.set(...) 这种直接读
    # ════════════════════════════════════════════════
    @property
    def _hexin_status_var(self):
        """老代码 (app.py / settings_tab 兼容) 直接读这个 StringVar 来更新状态条。"""
        return self._ctrl.view.hexin_status_var

    @property
    def root(self):
        """部分诊断代码会读 popup.root 看是否可见。"""
        return self._ctrl.root

    # ════════════════════════════════════════════════
    # 给新代码用的入口 (老代码不用,新代码可以直接拿 controller 操作)
    # ════════════════════════════════════════════════
    @property
    def controller(self):
        """供 Phase 2 重构期间访问内部结构。"""
        return self._ctrl
