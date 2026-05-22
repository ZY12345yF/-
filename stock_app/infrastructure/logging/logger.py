"""
logger.py — 统一 logger 工厂

用法:
    from stock_app.infrastructure.logging import get_logger
    log = get_logger(__name__)        # 自动按文件域分发
    log.info("watcher started, pid=%d", pid)

行为:
  • get_logger("stock_app.popup.sync") 会路由到 logs/popup.log
  • get_logger("stock_app.core.api_client") 路由到 logs/api.log
  • get_logger("stock_app.core.scheduler") 路由到 logs/scheduler.log
  • 其它走 logs/app.log
  • 同名 logger 复用,不会重复加 handler

日志目录默认是 stock_app 包外层的 logs/ (跟 data/ 同级)。
"""
import logging
import logging.handlers
import os
import sys

# logger name → log filename 路由表
# 按 "stock_app.<域>.<...>" 的第二段域分发
_DOMAIN_TO_FILE = {
    "popup":  "popup.log",
    "tabs":   "ui.log",
    "ui":     "ui.log",
    "core":   "app.log",       # 兜底
    "api":    "api.log",
    "scheduler": "scheduler.log",
    "hexin":  "hexin.log",
    "integrations": "integrations.log",
    "services": "services.log",
    "controllers": "controllers.log",
    "repositories": "repositories.log",
    "infrastructure": "infra.log",
}

_DEFAULT_FILE = "app.log"

# 已配置过的 logger 名缓存,避免重复加 handler
_configured = set()

# 日志目录 — 进程启动时计算一次
_LOG_DIR = None


def _resolve_log_dir():
    """
    日志目录优先级:
      1. 环境变量 STOCK_APP_LOG_DIR
      2. stock_app 包的兄弟目录 logs/  (即 project_root/logs/)
      3. 当前工作目录的 ./logs/
    """
    global _LOG_DIR
    if _LOG_DIR is not None:
        return _LOG_DIR
    env = os.environ.get("STOCK_APP_LOG_DIR")
    if env:
        _LOG_DIR = env
    else:
        # __file__ = .../stock_app/infrastructure/logging/logger.py
        # → project_root = .../
        here = os.path.dirname(os.path.abspath(__file__))
        pkg_root = os.path.dirname(os.path.dirname(os.path.dirname(here)))
        _LOG_DIR = os.path.join(pkg_root, "logs")
    try:
        os.makedirs(_LOG_DIR, exist_ok=True)
    except Exception:
        # 兜底: 退到 /tmp
        _LOG_DIR = "/tmp/stock_app_logs"
        try:
            os.makedirs(_LOG_DIR, exist_ok=True)
        except Exception:
            pass
    return _LOG_DIR


def _route_filename(logger_name):
    """根据 logger 名前缀决定 log 文件名。"""
    parts = logger_name.split(".")
    # parts[0] 一般是 "stock_app"
    if len(parts) >= 2:
        domain = parts[1]
        if domain in _DOMAIN_TO_FILE:
            return _DOMAIN_TO_FILE[domain]
        # 三段名: stock_app.tabs.history → 用第三段 "history" 也找一下
        if len(parts) >= 3:
            sub = parts[2]
            if sub in _DOMAIN_TO_FILE:
                return _DOMAIN_TO_FILE[sub]
    return _DEFAULT_FILE


def get_logger(name):
    """
    返回配置好的 logger。同名 logger 复用,不会重复加 handler。

    Args:
        name: 通常用 __name__,如 "stock_app.popup.sync"
    """
    log = logging.getLogger(name)
    if name in _configured:
        return log

    log.setLevel(logging.DEBUG)
    log.propagate = False  # 不让 root logger 重复打印

    log_dir = _resolve_log_dir()
    filename = _route_filename(name)
    filepath = os.path.join(log_dir, filename)

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)-5s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 文件 handler — 10MB × 5 旋转
    try:
        file_handler = logging.handlers.RotatingFileHandler(
            filepath,
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(fmt)
        log.addHandler(file_handler)
    except Exception:
        # 文件 handler 起不来不致命,继续走 stderr
        pass

    # 控制台 handler — 只输出 WARNING+
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(fmt)
    log.addHandler(console_handler)

    _configured.add(name)
    return log


def configure_root(level="INFO", console_level="WARNING"):
    """
    一次性配置 root logger (可选,通常不用)。
    主要给"我想在子线程异常时 logger.exception()"场景。
    """
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    if not root.handlers:
        h = logging.StreamHandler(sys.stderr)
        h.setLevel(getattr(logging, console_level.upper(), logging.WARNING))
        h.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)-5s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        ))
        root.addHandler(h)
