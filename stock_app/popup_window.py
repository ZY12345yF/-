"""
popup_window.py — 向后兼容 shim (v9.9.8 重构)

原 1219 行的 PopupWindow 已经按"View / Controller / Service"分层拆解到
stock_app.popup 子包,内部由 PopupController 串接 6 个模块:

    popup/
    ├── state.py        PopupState
    ├── view.py         PopupView (Tk UI)
    ├── controller.py   PopupController
    ├── sync.py         HexinSync (同花顺)
    ├── ball.py         FloatingBall (悬浮球)
    ├── drag.py         DragResizeHandler
    ├── updater.py      QuoteUpdater (行情)
    └── facade.py       PopupWindow (兼容门面)

本文件只是 import 转发,保证 `from .popup_window import PopupWindow`
继续可用。app.py / settings_tab.py / widgets.py 内部对 popup 的引用都不
需要改 (它们通过 app.show_stock_popup / app._popup 间接访问)。

迁移完成后,新代码请直接 from .popup import PopupWindow。
未来某天确认全部内部代码都已切到新路径,可以删除本文件。
"""
from .popup import PopupWindow  # noqa: F401

__all__ = ["PopupWindow"]
