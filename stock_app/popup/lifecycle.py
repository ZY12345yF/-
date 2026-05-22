"""
PopupLifecycleMixin — 窗口生命周期

从 popup/controller.py 拆出,作为 Mixin 注入 PopupController。
依赖 self.state / self.view / self.ball / self.sync / self.updater / self.root / self.app,
这些属性由 PopupController.__init__ 初始化。
"""
import traceback
import tkinter as tk

from ..core import history as hist_mod
from ..infrastructure.logging import get_logger

log = get_logger(__name__)


class PopupLifecycleMixin:
    """显示 / 隐藏 / 销毁 / 最小化 / Undo,注入 PopupController。"""

    # ════════════════════════════════════════════════
    # 显示 / 隐藏 / 销毁
    # ════════════════════════════════════════════════
    def show(self, code, name=None):
        """主入口: 浮窗显示一只股票。"""
        if not code:
            return
        code6 = str(code).zfill(6)

        # 当前是悬浮球状态 → 先复原 (否则窗口"开但是空")
        if self.state.minimized:
            self._do_restore()

        # 入回退栈 (undo 自己引起的 show 不要入栈, 重复刷新也不算切换)
        if (not self.state.undoing
                and self.state.cur_code
                and self.state.cur_code != code6):
            self.state.show_history.append(
                (self.state.cur_code, self.state.cur_name))
            if len(self.state.show_history) > 50:
                self.state.show_history.pop(0)

        self.state.cur_code = code6
        self.state.cur_name = name or ""

        try:
            self.root.deiconify()
            self.root.lift()
        except tk.TclError:
            pass

        self.view.update_title(
            self.state.cur_code, self.state.cur_name, self.state.follow_mode)
        self.view.show_loading_quote(code6, name)

        # 历史记录
        try:
            records = hist_mod.find_by_code(code6)
        except Exception:
            log.exception("find_by_code failed for %s", code6)
            records = []
        self.state.records = records

        if records:
            options = [
                "{} {}  {}".format(
                    r.get('date', ''), r.get('time', ''),
                    "⭐" if r.get('starred') else "")
                for r in records
            ]
            self.view.populate_date_combo(options)
            self.view.render_record(records[0], self.app, code6)
            self.view.render_linked_grid(
                records[0].get('content', ''),
                cur_code=code6,
                on_link_click=self.push_linked,
                on_triple_click=self.on_triple_click)
        else:
            self.view.populate_date_combo([])
            self.view.render_no_history()
            self.view.render_linked_grid(
                '', cur_code=code6, on_link_click=self.push_linked,
                on_triple_click=self.on_triple_click)

        # 行情异步
        self.updater.fetch(code6, self._on_quote_ready)

    def hide(self):
        try:
            self.root.withdraw()
        except Exception:
            pass

    def destroy(self):
        try:
            self.sync.stop()
        except Exception:
            pass
        try:
            self.ball.hide()
        except Exception:
            pass
        try:
            self.root.destroy()
        except Exception:
            pass

    def notify_main_click(self, code, name=None):
        """主程序里点了一只股 → 浮窗刷新。"""
        if not code:
            return
        # 悬浮球状态: 不展开,只更新内部当前股 + 闪烁
        if self.state.minimized and self.ball.is_visible():
            code6 = str(code).zfill(6)
            self.state.cur_code = code6
            self.state.cur_name = name or ""
            self.state.needs_refresh_on_restore = True
            try:
                self.ball.flash(times=3)
            except Exception:
                pass
            try:
                self.view.hexin_status_var.set(
                    "📥 已记录 {} ({}) · 点击悬浮球展开".format(
                        name or "?", code6))
            except Exception:
                pass
            return
        self.show(code, name)

    # ════════════════════════════════════════════════
    # 可见性
    # ════════════════════════════════════════════════
    def toggle_visibility(self):
        """F1: 显示/隐藏 (overrideredirect 窗口用 winfo_viewable 判断)。"""
        try:
            if not self.root.winfo_viewable():
                self.root.deiconify()
                try:
                    self.root.lift()
                    self.root.attributes('-topmost', True)
                except Exception:
                    pass
            else:
                self.hide()
        except Exception:
            traceback.print_exc()

    # ════════════════════════════════════════════════
    # 最小化 / 复原 (悬浮球)
    # ════════════════════════════════════════════════
    def toggle_minimize(self):
        try:
            if not self.state.minimized:
                self._do_minimize()
            else:
                self._do_restore()
        except Exception:
            traceback.print_exc()

    def _do_minimize(self):
        try:
            self.state.geo_before_min = self.root.geometry()
        except Exception:
            self.state.geo_before_min = None
        try:
            self.root.withdraw()
        except Exception:
            pass
        self.ball.show()
        self.state.minimized = True
        try:
            self.view.btn_min.config(text=" □ ")
        except Exception:
            pass

    def _do_restore(self):
        self.ball.hide()
        try:
            self.root.deiconify()
            self.root.lift()
            self.root.attributes('-topmost', True)
        except Exception:
            pass
        if self.state.geo_before_min:
            try:
                self.root.geometry(self.state.geo_before_min)
            except Exception:
                pass
            self.state.geo_before_min = None
        self.state.minimized = False
        try:
            self.view.btn_min.config(text=" ─ ")
        except Exception:
            pass
        try:
            self.view.hexin_status_var.set("📐 浮窗已复原")
        except Exception:
            pass
        # 悬浮球期间收到的新数据 → 复原后用最新数据刷一次
        if self.state.needs_refresh_on_restore and self.state.cur_code:
            self.state.needs_refresh_on_restore = False
            try:
                code = self.state.cur_code
                # 临时清空 cur_code 让 show 不当作"重复刷新"跳过
                self.state.cur_code = None
                self.show(code, None)
            except Exception:
                traceback.print_exc()

    def _close_from_ball(self):
        """悬浮球右键菜单 → 关闭浮窗。"""
        self.ball.hide()
        self.state.minimized = False
        try:
            self.root.withdraw()
        except Exception:
            pass

    # ════════════════════════════════════════════════
    # Undo (Ctrl+Z)
    # ════════════════════════════════════════════════
    def undo(self):
        if not self.state.show_history:
            try:
                self.view.hexin_status_var.set("⏪ 无可回退的历史")
            except Exception:
                pass
            return
        prev_code, prev_name = self.state.show_history.pop()
        self.state.undoing = True
        try:
            # 同花顺也跟着回退
            try:
                self.sync.push(prev_code)  # 内部自动 lock_code
            except Exception:
                traceback.print_exc()
            self.show(prev_code, prev_name)
            try:
                self.view.hexin_status_var.set(
                    "⏪ 已回退到 {} ({})".format(prev_name or "?", prev_code))
            except Exception:
                pass
        finally:
            self.state.undoing = False
