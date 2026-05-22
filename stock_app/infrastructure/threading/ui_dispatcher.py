"""
UIDispatcher — 工作线程 → Tk 主线程的安全派发

Tkinter 的 widget 只能在创建它的线程 (主线程) 操作。从 worker 线程直接
widget.config(...) 会偶发崩溃 (X server 报错 / TclError)。

现在的代码里到处是这种模式:

    def _on_hexin_stock(self, code):           # 这是 worker 线程
        ...
        def _do():
            self._hexin_count_var.set(...)     # 这要在主线程
        try: self.root.after(0, _do)           # ← 派回主线程
        except Exception: pass

把这个 pattern 收口到 UIDispatcher,业务代码可以写:

    self.ui.call_in_ui(self._hexin_count_var.set, "新值")

或者配合 TaskManager:

    task_manager.submit(
        "fetch_quote",
        lambda: api.fetch(code),
        ui_dispatcher=self.ui,
        ui_callback=lambda info: self._render_quote(info),
    )

设计要点:
  • 包装的就是 root.after(0, ...) — 这是 Tk 文档推荐的跨线程方式
  • root 失效后调用静默忽略,避免关闭窗口瞬间的 TclError
  • Phase 2 可以加: 一次性合并 (debounce) / 限流 / 队列长度监控
"""
import traceback


class UIDispatcher:
    """
    持有 Tk root 引用,提供线程安全的"派回主线程"接口。

    一个进程一般一个 root,所以也一般只有一个 UIDispatcher 实例。
    PopupController 等都拿这个实例的引用。
    """

    def __init__(self, tk_root):
        """tk_root: tkinter.Tk 实例 (主窗口)"""
        self._root = tk_root

    def call_in_ui(self, func, *args, **kwargs):
        """
        把 func 调度到主线程执行。立即返回 (非阻塞)。
        func 抛出的异常不会传回 worker — 在主线程内打印 traceback。
        """
        if self._root is None:
            return

        def _wrapped():
            try:
                func(*args, **kwargs)
            except Exception:
                traceback.print_exc()

        try:
            self._root.after(0, _wrapped)
        except Exception:
            # root 已经 destroy / 跨线程 after 偶发失败 — 静默
            pass

    def call_later_ms(self, delay_ms, func, *args, **kwargs):
        """延时 N 毫秒后在主线程执行 (本质是 root.after)。"""
        if self._root is None:
            return None

        def _wrapped():
            try:
                func(*args, **kwargs)
            except Exception:
                traceback.print_exc()

        try:
            return self._root.after(delay_ms, _wrapped)
        except Exception:
            return None
