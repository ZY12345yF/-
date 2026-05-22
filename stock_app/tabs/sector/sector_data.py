"""
SectorDataMixin — 板块数据刷新、快照管理
提供日期下拉、快照加载/保存、实时刷新等功能。
"""
import threading
from tkinter import messagebox

from ...core import sector_snapshot as snap_mod
from ...services import SectorRefreshService
from ...repositories import sector_repo
from ...bus import state


def _now():
    from datetime import datetime
    return datetime.now().strftime("%H:%M:%S")


class SectorDataMixin:
    """板块数据刷新与快照管理（Mixin，不写 __init__）"""

    # ─── 启动加载 ───
    def _auto_load_today_or_latest(self):
        self._refresh_date_dropdown()
        today = snap_mod.today_key()
        if snap_mod.load_snapshot(today) is not None:
            self._cur_date_key = today
            self._date_var.set("今日（实时）")
            self._load_snapshot_into_ui(today)
            self._status_var.set("📁 已加载今日快照（{}）".format(_now()))
            return
        dates = snap_mod.list_dates()
        if dates:
            d = dates[0]
            self._cur_date_key = d
            self._date_var.set("{} (历史)".format(snap_mod.format_date_label(d)))
            self._load_snapshot_into_ui(d)
            self._status_var.set(
                "📁 已加载 {} 的快照 · 点 🔄 刷新可拉取今日实时数据".format(
                    snap_mod.format_date_label(d)))
        else:
            self._status_var.set("未刷新，请点击「🔄 刷新」获取板块和雷达数据")

    def _refresh_date_dropdown(self):
        dates = snap_mod.list_dates()
        today = snap_mod.today_key()
        opts = ["今日（实时）"]
        for d in dates:
            if d == today:
                continue
            opts.append("{} (历史)".format(snap_mod.format_date_label(d)))
        self._available_dates = dates
        self._date_combo['values'] = opts

    def _on_date_change(self):
        text = self._date_var.get()
        today = snap_mod.today_key()
        if text == "今日（实时）":
            self._cur_date_key = today
            if snap_mod.load_snapshot(today) is not None:
                self._load_snapshot_into_ui(today)
                self._status_var.set("📁 已加载今日快照")
            else:
                self._status_var.set("今日尚未刷新，请点击「🔄 刷新」")
            return
        for d in self._available_dates:
            if snap_mod.format_date_label(d) in text:
                self._cur_date_key = d
                self._load_snapshot_into_ui(d)
                self._status_var.set("📁 历史快照: {}".format(
                    snap_mod.format_date_label(d)))
                break

    def _on_type_change(self):
        today = snap_mod.today_key()
        if self._cur_date_key == today or self._cur_date_key is None:
            self._refresh()
        else:
            # 历史快照里类型固定 → 强制还原回快照里的类型
            snap = snap_mod.load_snapshot(self._cur_date_key)
            if snap:
                self._sector_type.set(snap.get('type', 'concept'))
                self._load_snapshot_into_ui(self._cur_date_key)

    # ─── 刷新（拉实时 + 全板块预拉 + 保存） ───
    def _refresh(self):
        """
        v9.9.8 Phase 2: 业务流程迁到 SectorRefreshService;
        本方法只剩 UI 部分(确认对话框 + 清表 + 状态更新)。
        """
        today = snap_mod.today_key()
        if self._cur_date_key and self._cur_date_key != today:
            if not messagebox.askyesno(
                "确认刷新",
                "当前正在查看历史快照({})。\n\n"
                "刷新会拉取实时数据并保存为今日({})快照,不会覆盖该历史日期。\n\n"
                "是否继续?".format(
                    snap_mod.format_date_label(self._cur_date_key),
                    snap_mod.format_date_label(today))):
                return

        sector_type = self._sector_type.get()
        radar_min_pct = self._safe_float(self._radar_min_pct.get(), 9.5)
        radar_pages   = max(1, min(10, self._safe_int(self._radar_pages.get(), 5)))

        self._status_var.set("⏳ 正在拉取板块榜单...")
        for i in self._sector_tree.get_children(): self._sector_tree.delete(i)
        for i in self._radar_tree.get_children():  self._radar_tree.delete(i)
        for i in self._hot_tree.get_children():    self._hot_tree.delete(i)
        self._clear_breakdown(); self._clear_ladder(); self._clear_history_tree()

        # ── 三个 callback,UI 派回主线程 (在 worker 线程里被调用) ──
        def _on_status(msg):
            state.ui_queue.put(lambda m=msg: self._status_var.set(m))

        def _on_sectors_loaded(sectors, today_key):
            # v9.8 早渲染: 板块榜单一拉到立刻显示,不等成份股
            def _early_render():
                self._render_sectors(sectors, sector_type)
                self._cur_date_key = today_key
                self._date_var.set("今日(实时)")
            state.ui_queue.put(_early_render)

        def _on_partial_progress(stocks_by_sector, done, total, failed):
            # 增量保存时同步内存(让选板块能立刻看到数据)
            self._stocks_by_sector = stocks_by_sector

        def _do():
            result = SectorRefreshService().refresh(
                sector_type=sector_type,
                radar_min_pct=radar_min_pct,
                radar_pages=radar_pages,
                on_status=_on_status,
                on_sectors_loaded=_on_sectors_loaded,
                on_partial_progress=_on_partial_progress,
            )
            if 'error' in result:
                state.ui_queue.put(lambda e=result['error']:
                    self._status_var.set("❌ 拉取板块失败: " + e))
                return

            if not result['saved_ok']:
                state.ui_queue.put(lambda m=result.get('save_error', ''):
                    self._status_var.set("⚠️ 保存快照失败: " + m))

            def _render():
                self._refresh_date_dropdown()
                self._stocks_by_sector = result['stocks_by_sector']
                self._render_radar(result['radar'])
                if result['saved_ok']:
                    tail = ""
                    failed = result['failed_codes']
                    if failed:
                        tail = " · 失败 {} 个:{}".format(
                            len(failed),
                            "、".join(failed[:3]) +
                            ("..." if len(failed) > 3 else ""))
                    self._status_var.set(
                        "✅ {} · 已保存今日快照({}){}".format(
                            "概念" if sector_type == "concept" else "行业",
                            _now(), tail))
            state.ui_queue.put(_render)

        threading.Thread(target=_do, daemon=True).start()

    # ════════════════════════════════════════════════
    # 🆕 v9.8：主程序关闭时的兜底保存
    # ════════════════════════════════════════════════
    def _save_partial_on_close(self):
        """
        App._on_close 调用:把当前内存里的成份股 + 板块再存一次。
        v9.9.8 Phase 2: 写盘走 SectorRefreshService.save_partial。
        """
        try:
            if not self._sectors or not self._stocks_by_sector:
                return
            today = snap_mod.today_key()
            existing = sector_repo.load_snapshot(today) or {}
            # 仅在本次拉取数据 >= 既有数据时才覆盖
            existing_count = len(existing.get('stocks_by_sector', {}))
            new_count = len(self._stocks_by_sector)
            if new_count < existing_count:
                # 已有快照比内存数据更全,不动它
                return
            payload = {
                "type":   self._sector_type.get(),
                "sectors": self._sectors,
                "stocks_by_sector": self._stocks_by_sector,
                "radar":  self._radar_data,
                "radar_params": existing.get("radar_params", {}),
            }
            SectorRefreshService().save_partial(payload, today)
        except Exception:
            import traceback; traceback.print_exc()

    def _load_snapshot_into_ui(self, date_key):
        snap = snap_mod.load_snapshot(date_key)
        if not snap: return
        saved_type = snap.get('type', 'concept')
        if saved_type != self._sector_type.get():
            self._sector_type.set(saved_type)
        sectors = snap.get('sectors', [])
        self._stocks_by_sector = snap.get('stocks_by_sector', {}) or {}
        self._render_sectors(sectors, saved_type)
        self._render_radar(snap.get('radar', []))

    @staticmethod
    def _safe_int(s, dft):
        try: return int(s)
        except: return dft

    @staticmethod
    def _safe_float(s, dft):
        try: return float(s)
        except: return dft
