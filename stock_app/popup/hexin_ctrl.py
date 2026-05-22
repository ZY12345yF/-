"""
PopupHexinCtrlMixin — 同花顺联动控制

从 popup/controller.py 拆出,作为 Mixin 注入 PopupController。
依赖 self.state / self.sync / self._ui / self.view,
这些属性由 PopupController.__init__ 初始化。
"""
import threading
import traceback

from ..widgets import check_triple_click


class PopupHexinCtrlMixin:
    """同花顺推送 + 监听回调,注入 PopupController。"""

    # ════════════════════════════════════════════════
    # 推送同花顺
    # ════════════════════════════════════════════════
    def push_current_code(self):
        """点摘要区代码 → 推送同花顺 (不刷新浮窗)。"""
        if not self.state.cur_code:
            return
        code = self.state.cur_code

        def _worker():
            ok, reason = self.sync.push(code)
            self._ui.call_in_ui(
                self._update_push_status, ok, reason, code)

        threading.Thread(target=_worker, daemon=True).start()

    def push_linked(self, code, name):
        """点联动股代码 → 推送同花顺,浮窗不变。"""
        if not code:
            return

        def _worker():
            ok, reason = self.sync.push(code)
            self._ui.call_in_ui(
                self._update_push_status, ok, reason, code)

        threading.Thread(target=_worker, daemon=True).start()
        # 立即给反馈,推送结果回来再 update 一次
        try:
            self.view.hexin_status_var.set(
                "📤 正在推送联动股 {} ({})...".format(name or "?", code))
        except Exception:
            pass

    def push_to_hexin(self, code, name=None):
        """老 API: 显式推送 (同步)。"""
        try:
            ok, reason = self.sync.push(str(code or "").zfill(6))
            self._update_push_status(ok, reason, code)
        except Exception:
            traceback.print_exc()

    def lock_code(self, code, ttl=10.0):
        """v9.9.6.2: 标记 code 是浮窗自己推的,watcher 读到不刷新。"""
        self.sync.lock_code(code, ttl)

    def on_triple_click(self, code, name):
        """🆕 三击蓝字代码 → 浏览器搜索该股票。"""
        check_triple_click(code, name)

    def restart_hexin_watcher(self):
        """设置变更后用新参数重启同花顺监听。"""
        self.sync.restart(
            on_stock=self._on_hexin_stock,
            on_status=self._on_hexin_status,
            get_follow_mode=lambda: self.state.follow_mode,
        )
        self.state.hexin_status = "🔄 同花顺监听已重启"
        try:
            self.view.hexin_status_var.set(self.state.hexin_status)
        except Exception:
            pass

    def _update_push_status(self, ok, reason, code):
        if ok:
            msg = "📤 已推送 {} 到同花顺 (前缀 {})".format(code, reason)
        else:
            msg = "❌ 推送失败: " + str(reason)
        self.state.hexin_status = msg
        try:
            self.view.hexin_status_var.set(msg)
        except Exception:
            pass

    # ════════════════════════════════════════════════
    # 同花顺监听回调 (worker 线程触发,要派回主线程)
    # ════════════════════════════════════════════════
    def _on_hexin_stock(self, code):
        """
        watcher 读到同花顺切了股 → 调度回主线程处理。
        二级防御: 自推 lock 命中就跳过。
        """
        if self.sync.is_locked(code):
            def _silent():
                try:
                    self.view.hexin_status_var.set(
                        "🔁 跳过自推回声 (popup-lock, code={})".format(code))
                except Exception:
                    pass
            self._ui.call_in_ui(_silent)
            return

        def _do():
            self.state.hexin_event_count += 1
            # 悬浮球状态: 不展开,只更新内部当前股 + 闪烁
            if self.state.minimized and self.ball.is_visible():
                self.state.cur_code = str(code).zfill(6)
                try:
                    self.view.hexin_count_var.set(
                        "✅ 切换 {} 次 · 最近 {}".format(
                            self.state.hexin_event_count, code))
                except Exception:
                    pass
                try:
                    self.ball.flash(times=3)
                except Exception:
                    pass
                self.state.needs_refresh_on_restore = True
                return
            # 正常模式: 刷新浮窗
            try:
                self.view.hexin_count_var.set(
                    "✅ 切换 {} 次 · 最近 {}".format(
                        self.state.hexin_event_count, code))
            except Exception:
                pass
            self.show(code, None)

        self._ui.call_in_ui(_do)

    def _on_hexin_status(self, msg):
        self.state.hexin_status = msg
        self._ui.call_in_ui(
            lambda: self.view.hexin_status_var.set(msg))
