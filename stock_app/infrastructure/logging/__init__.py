"""
infrastructure.logging — 统一日志

文档 十·日志改造:
    > 当前项目规模已经不能用 print
    > 必须统一 logger.info() / warning() / error()
    > 并按域拆分: app.log / api.log / scheduler.log

策略 (Phase 1, 最小可用):
  • get_logger(name) 返回带文件 handler 的 logger
  • 默认输出到 stock_app/../logs/{domain}.log,RotatingFileHandler 10MB × 5
  • 控制台 handler 走 stderr,只输出 WARNING 以上

策略 (Phase 2 待办):
  • Color formatter
  • 全局异常捕获 hook (替代到处 traceback.print_exc())
  • 在 print() 桥接器,把旧 print 自动转发到 logger.info

向后兼容: 旧代码 print(...) / traceback.print_exc() 可继续用,本模块只是
提供新的更好的方式。
"""
from .logger import get_logger, configure_root

__all__ = ["get_logger", "configure_root"]
