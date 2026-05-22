"""
stock_app.popup — 浮窗子包 (v9.9.8 重构)

原 stock_app/popup_window.py (1219 行) 拆为本子包:

    state.py        PopupState               业务运行时状态 (集中)
    view.py         PopupView                Tk UI 构建 (渲染方法在 render.py)
    render.py       PopupRenderMixin         渲染方法 Mixin → PopupView
    controller.py   PopupController          用户行为协调 / 模块拼装 (核心)
    hexin_ctrl.py   PopupHexinCtrlMixin      同花顺联动 Mixin → PopupController
    lifecycle.py    PopupLifecycleMixin      窗口生命周期 Mixin → PopupController
    sync.py         HexinSync                同花顺监听 + 自推回声防御
    ball.py         FloatingBall             悬浮球
    drag.py         DragResizeHandler        拖动 / 缩放 / 几何持久化
    updater.py      QuoteUpdater             行情异步刷新
    facade.py       PopupWindow              向后兼容门面 (老代码入口)

外部代码应继续使用:
    from stock_app.popup_window import PopupWindow

它现在是个 shim, 内部转到这里来。新代码也可以直接:
    from stock_app.popup import PopupWindow

层次依赖 (允许的方向, 严禁反向):
    facade  ──→  controller (含 hexin_ctrl + lifecycle Mixin)
                       │
                       ├──→  view (含 render Mixin)
                       ├──→  sync / ball / drag / updater / state
                       │
                       └──→  state  (controller 协调时改 state)

view / sync / ball / drag / updater / state / render / hexin_ctrl / lifecycle 之间
不互相 import。
"""
from .facade import PopupWindow

__all__ = ["PopupWindow"]
