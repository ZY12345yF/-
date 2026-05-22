"""
全局应用状态 — v9.9.8 重构版

按文档 五·原则 4 "状态集中管理":
    > 当前项目最大问题之一: 状态分散
    > self.current_code / self.selected_code / global_code / share_code
    > 最终谁是真实状态没人知道。必须集中。

本文件先把原 bus.py 里的 AppState 拆出来,并预留新字段位置。
当前 popup_window.py 里的 _cur_code / _cur_name / _follow_mode 等
仍由 PopupState (popup/state.py) 局部管理,等 Phase 2 再迁过来。

向后兼容: stock_app/bus.py 仍然 re-export `state` 单例,所有现存
`from .bus import state` 不用改。
"""
import queue
import threading


class AppState:
    """
    全局共享运行时状态。

    分类:
        threading 控制   — save_lock / shutdown / paused
        UI 跨线程队列    — log_queue / ui_queue
        批量分析运行态   — running / failed_stocks / last_batch_df / ...
        当前选中输入文件 — input_file

    Phase 2 计划加入 (现在还在各 Tab 自己持有):
        current_stock      — 全局"当前看的股票" (code, name)
        selected_sector    — 当前选中板块
        replay_state       — 复盘运行态
    """

    def __init__(self):
        # 应用级 lock 和事件
        self.save_lock = threading.Lock()
        self.shutdown  = threading.Event()
        self.paused    = threading.Event()

        # UI 队列: 工作线程 → 主线程
        # 配合 stock_app/app.py 里 _poll_queues() 80ms 拉取
        self.log_queue = queue.Queue()
        self.ui_queue  = queue.Queue()

        # 运行时状态 (批量分析)
        self.running        = False
        self.failed_stocks  = []
        self.last_batch_df  = None
        self.last_output    = None

        # 当前选中的输入文件
        self.input_file     = None


# 全局唯一状态单例
state = AppState()
