"""
TaskManager — 统一后台任务调度

替代散落各处的 `threading.Thread(target=xxx, daemon=True).start()`。

设计目标:
  • 所有后台 worker 在这里登记 → 关闭程序时能干净收尾,不留僵尸
  • daemon=True 默认,主程序结束就自动收
  • 异常隔离: worker 抛出来不会把整个程序打死
  • 可选 callback: worker 跑完后回主线程触发 (需要 UIDispatcher 配合)
  • 给 worker 一个 name 方便日志定位

兼容性: 旧代码继续用 threading.Thread 不影响。新增功能优先用 task_manager.submit。

用法:
    from stock_app.infrastructure.threading import task_manager

    # 简单 fire-and-forget
    task_manager.submit("fetch_quote", lambda: api.fetch(...))

    # 带回主线程的 callback
    task_manager.submit(
        "fetch_quote",
        lambda: api.fetch(code),
        ui_dispatcher=app_ui_dispatcher,
        ui_callback=lambda result: label.config(text=result),
    )

注意: 本类是 Phase 1 的最小实现。Phase 2 可以加:
  • 工作线程池 (限流,避免开几百个 Thread)
  • 任务优先级
  • 取消机制
  • 进度回调
"""
import threading
import traceback
import uuid


class _Task:
    """单个任务句柄,内部用。"""

    __slots__ = ("id", "name", "thread", "_done")

    def __init__(self, tid, name):
        self.id = tid
        self.name = name
        self.thread = None
        self._done = threading.Event()

    def is_alive(self):
        return self.thread is not None and self.thread.is_alive()

    def wait(self, timeout=None):
        return self._done.wait(timeout=timeout)


class TaskManager:
    """
    线程安全的任务调度器。所有 submit 进来的任务都登记在 _tasks 里。

    线程数无上限 (Phase 1 简化,够当前规模用)。Phase 2 改成 ThreadPoolExecutor。
    """

    def __init__(self):
        self._tasks = {}
        self._lock = threading.Lock()
        self._shutdown = False

    def submit(
        self,
        name,
        func,
        *args,
        ui_dispatcher=None,
        ui_callback=None,
        on_error=None,
        **kwargs,
    ):
        """
        提交一个后台任务。

        Args:
            name: 任务名,用于日志 (e.g. "fetch_quote_600519")
            func: 实际执行的函数,在 worker 线程跑
            *args, **kwargs: 传给 func 的参数
            ui_dispatcher: 可选,UIDispatcher 实例,用于把 callback 派到主线程
            ui_callback: 可选,func 跑完后用 func 返回值调用 (主线程)
            on_error: 可选,func 抛异常时调用,签名 on_error(exc)

        Returns:
            _Task 句柄,可 .wait() / .is_alive()
        """
        if self._shutdown:
            return None
        tid = uuid.uuid4().hex[:8]
        task = _Task(tid, name)

        def _run():
            try:
                result = func(*args, **kwargs)
                if ui_callback is not None:
                    if ui_dispatcher is not None:
                        ui_dispatcher.call_in_ui(ui_callback, result)
                    else:
                        # 没 dispatcher 就在 worker 线程里直接调
                        # (Tkinter 跨线程不安全,所以推荐总是传 dispatcher)
                        try:
                            ui_callback(result)
                        except Exception:
                            traceback.print_exc()
            except Exception as e:
                if on_error is not None:
                    try:
                        if ui_dispatcher is not None:
                            ui_dispatcher.call_in_ui(on_error, e)
                        else:
                            on_error(e)
                    except Exception:
                        traceback.print_exc()
                else:
                    traceback.print_exc()
            finally:
                task._done.set()
                with self._lock:
                    self._tasks.pop(tid, None)

        t = threading.Thread(target=_run, name="task:" + name, daemon=True)
        task.thread = t
        with self._lock:
            self._tasks[tid] = task
        t.start()
        return task

    def active_count(self):
        with self._lock:
            return sum(1 for t in self._tasks.values() if t.is_alive())

    def active_names(self):
        with self._lock:
            return [t.name for t in self._tasks.values() if t.is_alive()]

    def shutdown(self, wait_timeout=3.0):
        """
        通知 TaskManager 不再接新任务,等存活线程退出 (最多 wait_timeout 秒)。
        daemon 线程不退也无所谓,主程序会随进程结束。
        """
        self._shutdown = True
        if wait_timeout is None or wait_timeout <= 0:
            return
        with self._lock:
            tasks = list(self._tasks.values())
        deadline_per = wait_timeout / max(1, len(tasks))
        for t in tasks:
            t.wait(timeout=deadline_per)


# 全局唯一 TaskManager
task_manager = TaskManager()
