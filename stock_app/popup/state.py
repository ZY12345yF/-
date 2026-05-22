"""
PopupState — 浮窗运行时状态集中管理

原 popup_window.py 把 12+ 个 `self._xxx` 散在 __init__ 里。重构后:
  • 全部进 PopupState (dataclass)
  • view / controller / sync / ball 都拿同一个 PopupState 引用
  • 状态访问点收口,以后接 Phase 2 的全局 AppState 时一处改完

注意: 这里只放"业务状态" — code / name / 历史栈 / 锁表 / follow 开关...
Tk widget 引用 (self._name_lbl / self._detail / ...) 还留在 PopupView 里,
因为它们的生命周期跟 Tk 窗口绑定,不属于"业务状态"。
"""
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class PopupState:
    # ── 当前看的股 ─────────────────────────────────
    cur_code: Optional[str] = None
    cur_name: Optional[str] = None

    # ── 当前股的分析记录列表 (来自 history) ────────
    records: list = field(default_factory=list)

    # ── 跟随同花顺开关 (是否让浮窗自动跟随同花顺切股) ──
    follow_mode: bool = True

    # ── 同花顺联动状态 (展示用) ────────────────────
    hexin_status: str = "⏳ 同花顺联动: 启动中..."
    hexin_event_count: int = 0

    # ── 自推回声二级防御 ──
    # key: 6位代码字符串, value: 锁定到期时间戳 (time.time() 秒)
    # popup 自己刚推到同花顺的代码,10s 内 watcher 读回来不要刷新浮窗
    popup_locked: dict = field(default_factory=dict)

    # ── Ctrl+Z 回退栈 ──
    # 每个元素 (code, name);最近的在末尾
    show_history: list = field(default_factory=list)
    undoing: bool = False  # 防止 undo 触发的 show 又入栈

    # ── 最小化状态 (悬浮球) ──
    minimized: bool = False
    geo_before_min: Optional[str] = None
    # 在悬浮球期间收到了新数据 → 复原时刷新一次
    needs_refresh_on_restore: bool = False

    # ── 置顶状态 ──
    topmost: bool = True

    # ── 几何约束 ──
    MIN_W: int = 380
    MIN_H: int = 320

    # ── 拖动/缩放暂存 ──
    drag_data:   dict = field(default_factory=lambda: {"x": 0, "y": 0})
    resize_data: dict = field(default_factory=lambda: {
        "x": 0, "y": 0, "w": 0, "h": 0
    })

    # ── 设置快照 (启动时一次性读入) ──
    settings: dict = field(default_factory=dict)
