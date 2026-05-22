"""
infrastructure.threading — 统一线程调度

按文档 九·Scheduler 架构 + 六·线程管理统一方案:
    > 所有后台任务必须通过 TaskManager.submit()
    > UI 更新必须 ui_dispatcher.call_in_ui(...)
    > 禁止: Thread(target=xxx).start() 散落在业务代码里

本包不替换现有 threading.Thread,而是提供更安全的替代品。
现有代码 (popup / api_client / scheduler) 暂保持原样,新增功能必须走这里。
"""
from .task_manager import TaskManager, task_manager
from .ui_dispatcher import UIDispatcher

__all__ = ["TaskManager", "task_manager", "UIDispatcher"]
