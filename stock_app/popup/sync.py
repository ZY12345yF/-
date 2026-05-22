"""
HexinSync — 同花顺联动 + 自推回声防御

原 popup_window.py 里这几块:
  • _start_hexin_watcher() 模块级函数
  • lock_code() / _is_locked() — 二级防御锁表
  • _on_hexin_stock() — watcher 回调
  • _on_hexin_status() — 状态条回调
  • restart_hexin_watcher() — 设置变了重启

全部收口到本类。对外接口:
  start(on_stock, on_status, get_follow_mode)   — 启动监听
  stop()                                        — 停止监听
  restart(on_stock, on_status, get_follow_mode) — 用新设置重启
  lock_code(code, ttl=10)                       — 自推前先 lock,防回声
  is_locked(code) -> bool                       — 检查锁
  push(code) -> (ok, reason)                    — 显式推送一只股票
  is_running() -> bool

外部传进来的回调签名:
  on_stock(code)   — 同花顺切到新股时调用 (在 watcher 线程)
  on_status(msg)   — watcher 状态变化时调用
  get_follow_mode() -> bool — watcher 检查是否启用跟随
"""
import time

from ..core import config as cfg_mod
from ..core import hexin_bridge as hexin
from ..infrastructure.logging import get_logger

log = get_logger(__name__)


class HexinSync:
    def __init__(self):
        self._watcher = None
        # 自推回声锁: code → 过期时间戳
        self._locked = {}

    # ────────────────────────────────────────────
    # 生命周期
    # ────────────────────────────────────────────
    def start(self, on_stock, on_status, get_follow_mode):
        """
        启动同花顺监听。如果设置里关了监听就不启动。
        on_stock / on_status 会在 watcher 内部线程触发,调用方需要自己派回主线程。
        """
        try:
            s = cfg_mod.load_settings()
        except Exception:
            s = {}
        if not s.get("hexin_watcher_enabled", True):
            try:
                on_status("⏸️ 设置中已关闭监听")
            except Exception:
                pass
            log.info("hexin watcher disabled in settings")
            return None
        try:
            w = hexin.HexinReadWatcher(
                on_change=on_stock,
                on_status=on_status,
                enabled_fn=get_follow_mode,
                settings=s,
            )
            w.start()
            self._watcher = w
            log.info("hexin watcher started")
            return w
        except Exception:
            log.exception("hexin watcher start failed")
            return None

    def stop(self):
        if self._watcher is not None:
            try:
                self._watcher.stop()
                log.info("hexin watcher stopped")
            except Exception:
                log.exception("hexin watcher stop failed")
        self._watcher = None

    def restart(self, on_stock, on_status, get_follow_mode):
        """用最新设置重启 watcher。"""
        self.stop()
        return self.start(on_stock, on_status, get_follow_mode)

    def is_running(self):
        return self._watcher is not None

    # ────────────────────────────────────────────
    # 自推回声防御
    # ────────────────────────────────────────────
    def lock_code(self, code, ttl=10.0):
        """
        浮窗自己刚把 code 推到同花顺前调用本方法。
        ttl 秒内 watcher 读到这个 code 不要触发刷新 (避免 A→A 死循环)。

        和 hexin_bridge 内部的 push_silencer 是双保险 — 因为同花顺切股可能
        慢于全局 silencer 的 3s 默认。
        """
        if not code:
            return
        try:
            self._locked[str(code).zfill(6)] = time.time() + float(ttl)
        except Exception:
            pass

    def is_locked(self, code):
        """这个 code 现在是否处于自推回声窗口。过期自动清。"""
        if not code:
            return False
        code6 = str(code).zfill(6)
        exp = self._locked.get(code6)
        if exp is None:
            return False
        if time.time() > exp:
            self._locked.pop(code6, None)
            return False
        return True

    def clear_lock(self, code=None):
        """清单只 code 的锁,或全部锁。"""
        if code is None:
            self._locked.clear()
        else:
            self._locked.pop(str(code).zfill(6), None)

    # ────────────────────────────────────────────
    # 推送
    # ────────────────────────────────────────────
    def push(self, code):
        """
        同步推送 code 到同花顺。返回 (ok: bool, reason: str)。
        调用前会自动 lock_code,所以不需要外部再 lock。
        """
        code6 = str(code or "").zfill(6)
        if not code6 or code6 == "000000":
            return (False, "空代码")
        self.lock_code(code6)
        try:
            ok, reason = hexin.push_code_to_hexin(code6)
            if ok:
                log.info("hexin push ok: %s (%s)", code6, reason)
            else:
                log.warning("hexin push failed: %s (%s)", code6, reason)
            return (ok, reason)
        except Exception as e:
            log.exception("hexin push exception")
            return (False, str(e))
