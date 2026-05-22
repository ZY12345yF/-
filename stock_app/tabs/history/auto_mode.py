"""历史记录 Tab — 自动模式 / 批量重识别 / Inline Toast Mixin"""
import threading
import tkinter as tk
from tkinter import messagebox

from ...core import history as hist_mod
from ...services import BatchRequeryService


class AutoModeMixin:
    """自动批量识别模式 + 一键批量重识别 + 行内提示"""

    # ════════════════════════════════════════════
    # 自动模式：定时批量识别行情
    # ════════════════════════════════════════════
    def _toggle_auto_mode(self):
        """开关自动模式"""
        if self._auto_mode_var.get():
            # 解析间隔
            try:
                m = int(self._auto_interval_var.get())
                if m < 1: m = 1
                self._auto_mode_minutes = m
            except Exception:
                self._auto_mode_minutes = 5
                self._auto_interval_var.set("5")
            self._auto_mode_on = True
            self._auto_status_var.set("✅ 已启用 · 每{}分钟自动批量识别".format(self._auto_mode_minutes))
            # 立刻执行一次
            self._schedule_next_auto_run(initial=True)
        else:
            self._auto_mode_on = False
            self._auto_status_var.set("已关闭")
            if self._auto_mode_id:
                try:
                    self.app.root.after_cancel(self._auto_mode_id)
                except Exception:
                    pass
                self._auto_mode_id = None
            self.app.root.after(3000, lambda: self._auto_status_var.set(""))

    def _schedule_next_auto_run(self, initial=False):
        """安排下一次自动批量识别"""
        if not self._auto_mode_on:
            return
        # initial=True 时延迟 3 秒（避免开关刚打开立刻触发），否则按间隔
        delay_ms = 3000 if initial else self._auto_mode_minutes * 60 * 1000
        self._auto_mode_id = self.app.root.after(delay_ms, self._auto_run_batch)

    def _auto_run_batch(self):
        """自动模式触发的批量识别（无确认弹窗）"""
        if not self._auto_mode_on:
            return
        d = self._get_date_key()
        if not d:
            self._schedule_next_auto_run()
            return
        records = hist_mod.load_history(d)
        if not records:
            self._auto_status_var.set("⚠️ 当日无记录，等待下一次")
            self._schedule_next_auto_run()
            return
        # 在后台执行，完成后自动调度下一次
        import threading
        def _worker():
            self._do_batch_requery(d, records, silent=True)
            self.app.root.after(0, lambda: (
                self._auto_status_var.set("✅ 已完成第 {} 轮 · 下一轮 {} 分钟后".format(
                    getattr(self, "_auto_round", 0) + 1, self._auto_mode_minutes)),
                setattr(self, "_auto_round", getattr(self, "_auto_round", 0) + 1)
            ))
            self.app.root.after(0, self._schedule_next_auto_run)
        threading.Thread(target=_worker, daemon=True).start()
        self._auto_status_var.set("🔄 第 {} 轮识别中...".format(
            getattr(self, "_auto_round", 0) + 1))

    # ════════════════════════════════════════════
    # Inline Toast 提示（取代弹窗）
    # ════════════════════════════════════════════
    def _show_inline_toast(self, msg, kind="ok"):
        """在详情面板顶部显示一行短暂提示，3 秒后自动消失"""
        C = self.C
        color = {"ok": C['green'], "fail": C['red'], "info": C['accent']}.get(kind, C['green'])
        self._toast_lbl.config(fg=color)
        self._toast_var.set(msg)
        # 取消旧定时器
        if hasattr(self, "_toast_after_id") and self._toast_after_id:
            try:
                self.app.root.after_cancel(self._toast_after_id)
            except Exception:
                pass
        self._toast_after_id = self.app.root.after(
            3500, lambda: self._toast_var.set(""))

    # ════════════════════════════════════════════
    # 一键批量重识别当日全部记录
    # ════════════════════════════════════════════
    def _batch_requery_all(self):
        d = self._get_date_key()
        if not d:
            messagebox.showinfo("提示", "请先在左上角选择日期")
            return
        records = hist_mod.load_history(d)
        if not records:
            messagebox.showinfo("提示", "当日无历史记录")
            return
        if not messagebox.askyesno("确认",
            "将对 {} 当日全部 {} 条记录批量重新识别联动行情。\n\n"
            "预计耗时约 {} 秒（每条记录查询一次腾讯接口）。\n\n"
            "完成后自动保存到历史文件。确定继续？".format(
                d, len(records), len(records) * 1)):
            return

        # 后台线程跑，避免UI卡死
        import threading, time
        threading.Thread(
            target=lambda: self._do_batch_requery(d, records),
            daemon=True).start()

    def _do_batch_requery(self, date_key, records, silent=False):
        """
        v9.9.8 Phase 2: 业务逻辑迁到 BatchRequeryService;
        本方法是"UI 外壳"——只负责进度 toast 和最终弹框。

        注: 本方法依然在 worker 线程里跑 (来自 _batch_requery_all 的 Thread),
        因此对 UI 的更新都走 self.app.root.after(0, ...)。
        """
        # 进度回调: 由 Service 在 worker 线程内调用,这里再 after(0) 派回主线程
        def _on_progress(i, total, name):
            self.app.root.after(0,
                lambda i=i, n=name, t=total: self._show_inline_toast(
                    "🔄 批量识别中 ({}/{})  {}".format(i, t, n), "info"))

        stats = BatchRequeryService().requery(
            date_key, records, on_progress=_on_progress)
        ok, fail, skip = stats['ok'], stats['fail'], stats['skip']

        # 完成 — 切回主线程显示
        def _done():
            self._show_inline_toast(
                "✅ 批量完成：成功 {} / 失败 {} / 跳过 {}".format(ok, fail, skip), "ok")
            self._load_day()
            if not silent:
                messagebox.showinfo("批量识别完成",
                    "✅ 成功更新: {} 条\n"
                    "❌ 行情查询失败: {} 条\n"
                    "⏭️ 跳过(无代码): {} 条".format(ok, fail, skip))
        self.app.root.after(0, _done)
