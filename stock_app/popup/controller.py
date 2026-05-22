"""
PopupController — 浮窗协调器

按文档 五·原则 3 "Controller 做调度":
    > Controller 负责: UI 事件 → 调服务 → 更新状态 → 通知 View 刷新
    > 它是 UI 和业务之间的隔离层

本类把以下零件拼起来:
    PopupState         运行时状态
    PopupView          Tk widget + 渲染
    HexinSync          同花顺监听 + 自推回声防御
    FloatingBall       悬浮球
    DragResizeHandler  拖动 / 缩放 / 几何记忆
    QuoteUpdater       行情异步刷新
    UIDispatcher       worker → 主线程派发

窗口生命周期方法已移至 PopupLifecycleMixin (.lifecycle)
同花顺联动方法已移至 PopupHexinCtrlMixin (.hexin_ctrl)

行为对齐原 popup_window.py:
    所有公共方法签名一字不差,所有交互细节 (lock / undo / minimize / flash)
    全部保留。原文件 1219 行被拆成 8 个文件,业务逻辑没动一行。
"""
import traceback
import tkinter as tk

from ..core import config as cfg_mod
from ..core.theme import get as theme
from ..infrastructure.threading.ui_dispatcher import UIDispatcher
from ..infrastructure.logging import get_logger
from .state import PopupState
from .view import PopupView
from .sync import HexinSync
from .ball import FloatingBall
from .drag import DragResizeHandler
from .updater import QuoteUpdater
from .hexin_ctrl import PopupHexinCtrlMixin
from .lifecycle import PopupLifecycleMixin

log = get_logger(__name__)


class PopupController(PopupHexinCtrlMixin, PopupLifecycleMixin):
    """
    浮窗主控。app.py 通过 facade (PopupWindow) 间接持有它。
    同花顺联动 → PopupHexinCtrlMixin
    窗口生命周期 → PopupLifecycleMixin
    """

    def __init__(self, app):
        self.app = app
        self.theme = theme()
        self.state = PopupState()

        # ── 设置快照 ──────────────────────────────
        try:
            self.state.settings = cfg_mod.load_settings()
        except Exception:
            self.state.settings = {}
        legacy_follow = self.state.settings.get("popup_follow_mode")
        self.state.follow_mode = bool(self.state.settings.get(
            "popup_follow_hexin",
            True if legacy_follow is None else legacy_follow))
        self.state.hexin_status = "⏳ 同花顺联动: 启动中..."

        # ── 创建 Toplevel ────────────────────────
        self.root = tk.Toplevel(app.root)
        self.root.withdraw()
        self.root.title("📊 股票浮窗")

        # ── View ─────────────────────────────────
        initial_geo = self.state.settings.get(
            "popup_geometry", "600x700+200+120")
        self.view = PopupView(
            root=self.root,
            theme=self.theme,
            initial_geometry=initial_geo,
            initial_follow_mode=self.state.follow_mode,
            min_w=self.state.MIN_W,
            min_h=self.state.MIN_H,
            callbacks={
                'on_hide':                self.hide,
                'on_toggle_minimize':     self.toggle_minimize,
                'on_toggle_follow':       self.toggle_follow,
                'on_toggle_topmost':      self.toggle_topmost,
                'on_push_current_code':   self.push_current_code,
                'on_request_ai_analyze':  self.request_ai_analyze,
                'on_date_change':         self.on_date_change,
                'on_refresh_quote':       self.refresh_quote,
                'on_restore_status_text': self._restore_status_text,
                'on_triple_click':        self.on_triple_click,
            },
        )

        # ── UI 派发 ──────────────────────────────
        self._ui = UIDispatcher(self.root)

        # ── 拖动 / 缩放 ───────────────────────────
        self.drag = DragResizeHandler(self.root, self.state, self.theme)
        self.drag.bind_title_drag(self.view.title_bar)
        self.drag.bind_title_drag(self.view.title_label)
        # 标题栏右键 → 几何菜单
        self.view.title_bar.bind('<Button-3>', self.drag.show_title_context_menu)
        self.view.title_label.bind('<Button-3>', self.drag.show_title_context_menu)
        self.drag.bind_resize_grip(self.view.grip)

        # ── 悬浮球 ────────────────────────────────
        self.ball = FloatingBall(
            parent_root=app.root,
            theme=self.theme,
            on_restore=self._do_restore,
            on_close=self._close_from_ball,
            get_current_stock=lambda: (self.state.cur_code, self.state.cur_name),
            on_push_current=self.push_to_hexin,
        )

        # ── 行情更新器 ────────────────────────────
        self.updater = QuoteUpdater()

        # ── 同花顺联动 ────────────────────────────
        self.sync = HexinSync()
        self.sync.start(
            on_stock=self._on_hexin_stock,
            on_status=self._on_hexin_status,
            get_follow_mode=lambda: self.state.follow_mode,
        )

        # ── 窗口关闭走 hide,而不是销毁 ──────────────
        try:
            self.root.protocol("WM_DELETE_WINDOW", self.hide)
        except Exception:
            pass

        # ── 立即显示 ──────────────────────────────
        self.root.deiconify()
        self.root.update()

    # ════════════════════════════════════════════════
    # Follow 开关
    # ════════════════════════════════════════════════
    def toggle_follow(self):
        self.state.follow_mode = not self.state.follow_mode
        self.view.update_follow_button(self.state.follow_mode)
        # 写回 settings
        try:
            s = cfg_mod.load_settings()
            s["popup_follow_hexin"] = self.state.follow_mode
            # 清掉老 key
            s.pop("popup_follow_mode", None)
            s.pop("popup_push_hexin", None)
            s.pop("popup_main_link", None)
            cfg_mod.save_settings(s)
        except Exception:
            traceback.print_exc()
        self.view.update_title(
            self.state.cur_code, self.state.cur_name, self.state.follow_mode)
        if self.state.follow_mode:
            self.state.hexin_status = "✅ 已启用 📥 跟随同花顺 (同花顺 → 浮窗)"
        else:
            self.state.hexin_status = "⏸️ 跟随已关闭 (手动模式)"
        try:
            self.view.hexin_status_var.set(self.state.hexin_status)
        except Exception:
            pass

    def is_follow_mode(self):
        return self.state.follow_mode

    # ════════════════════════════════════════════════
    # 置顶开关
    # ════════════════════════════════════════════════
    def toggle_topmost(self):
        self.state.topmost = not self.state.topmost
        try:
            self.root.attributes('-topmost', self.state.topmost)
        except Exception:
            pass
        self.view.update_pin_button(self.state.topmost)
        if self.state.topmost:
            self.view.hexin_status_var.set("📌 已置顶")
        else:
            self.view.hexin_status_var.set("📎 已取消置顶")

    def follow(self, code, name=None):
        """老 API: 等价 notify_main_click。"""
        self.notify_main_click(code, name)

    # ════════════════════════════════════════════════
    # 行情
    # ════════════════════════════════════════════════
    def refresh_quote(self):
        if not self.state.cur_code:
            return
        self.updater.fetch(self.state.cur_code, self._on_quote_ready)

    def _on_quote_ready(self, info):
        """worker 线程: updater 拿到行情后回调。派回主线程渲染。"""
        if info and not self.state.cur_name:
            self.state.cur_name = info.get('name', '')

        def _ui():
            self.view.render_quote(info)
            if self.state.cur_name:
                self.view.update_name_label(self.state.cur_name)
                self.view.update_title(
                    self.state.cur_code,
                    self.state.cur_name,
                    self.state.follow_mode)

        self._ui.call_in_ui(_ui)

    # ════════════════════════════════════════════════
    # 日期切换
    # ════════════════════════════════════════════════
    def on_date_change(self):
        idx = self.view.current_date_index()
        if idx < 0 or idx >= len(self.state.records):
            return
        rec = self.state.records[idx]
        self.view.render_record(rec, self.app, self.state.cur_code)
        self.view.render_linked_grid(
            rec.get('content', ''),
            cur_code=self.state.cur_code,
            on_link_click=self.push_linked,
            on_triple_click=self.on_triple_click)

    # ════════════════════════════════════════════════
    # AI 分析
    # ════════════════════════════════════════════════
    def request_ai_analyze(self):
        if not self.state.cur_code:
            return
        code = self.state.cur_code
        name = self.state.cur_name or ""
        self.view.flash_ai_button_sent()
        try:
            self.app.root.after(
                0,
                lambda: self.app._do_ai_analyze_from_popup(code, name))
        except Exception:
            traceback.print_exc()

    # ════════════════════════════════════════════════
    # 内部: hover follow 按钮抬起 → 恢复状态条文字
    # ════════════════════════════════════════════════
    def _restore_status_text(self):
        try:
            self.view.hexin_status_var.set(self.state.hexin_status)
        except Exception:
            pass
