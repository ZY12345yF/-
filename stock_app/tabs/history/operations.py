"""历史记录 Tab — 星标/备注/删除/标签/导出操作 Mixin"""
import threading
import tkinter as tk
from tkinter import messagebox, simpledialog

from ...core import history as hist_mod, reports
from ...bus import bus, Events, state
from ...services import (
    StarredExportService,
    DailyQuotesExporter,
)


class HistoryOperationsMixin:
    """星标 / 备注 / 删除 / 清除 / 搜索 / 标签 / 自选 / 导出"""

    # ════════════════════════════════════════════
    # 星标 / 备注 / 删除
    # ════════════════════════════════════════════
    def _toggle_star(self):
        recs = self._get_sel()
        if not recs:
            messagebox.showinfo("提示", "请先选中记录")
            return
        for dk, r, _ in recs:
            hist_mod.toggle_star(dk, r.get('id'))
        self._reload_list()

    def _edit_note_dialog(self):
        recs = self._get_sel()
        if not recs: return
        dk, r, _ = recs[0]
        new = simpledialog.askstring(
            "编辑备注",
            "为 {} ({}) 添加备注：".format(r.get('name',''), r.get('code','')),
            initialvalue=r.get('note',''), parent=self.app.root)
        if new is None: return
        hist_mod.set_note(dk, r.get('id'), new.strip())
        self._reload_list()

    def _delete_selected(self):
        recs = self._get_sel()
        if not recs: return
        if not messagebox.askyesno("确认删除",
                "确认删除选中的 {} 条记录？".format(len(recs))):
            return
        by_date = {}
        for dk, r, _ in recs:
            by_date.setdefault(dk, []).append(r.get('id'))
        for dk, ids in by_date.items():
            hist_mod.delete_records(dk, ids)
        self.detail.delete('1.0', 'end')
        self._cur_date_key = self._cur_record_id = None
        self._dirty = False
        self._save_btn.config(state='disabled')
        self._reload_list()

    def _clear_day(self):
        d = self._get_date_key()
        if not d: return
        if not messagebox.askyesno("确认清空",
                "将清空 {} 当天所有记录？".format(d)):
            return
        hist_mod.clear_day(d)
        self.detail.delete('1.0', 'end')
        self._refresh_dates()

    def _reload_list(self):
        if self.kw_var.get().strip():
            self._search()
        else:
            self._load_day()

    def _search(self):
        kw = self.kw_var.get().strip()
        if not kw:
            self._load_day(); return
        for i in self.tree.get_children():
            self.tree.delete(i)
        self._row_data.clear()   # 清空旧的行数据缓存
        only_star = self.only_star.get()
        for r in hist_mod.search_history(kw)[:300]:
            if only_star and not r.get('starred'): continue
            d    = r.get('date','')
            star = '⭐' if r.get('starred') else ''
            ok   = '✅' if r.get('success') else '❌'
            note = r.get('note','')[:20]
            tags = ('starred',) if r.get('starred') else ()
            iid  = self.tree.insert('', 'end',
                                     values=(star,
                                             "{} {}".format(d[4:6]+'-'+d[6:], r.get('time','')),
                                             r.get('name',''), r.get('code',''), ok, note),
                                     tags=tags)
            self._row_data[iid] = r    # 用字典缓存完整数据

    # ════════════════════════════════════════════
    # 编辑标签（多选）
    # ════════════════════════════════════════════
    def _edit_tags_dialog(self):
        from ...core.replay import PRESET_TAGS
        recs = self._get_sel()
        if not recs:
            messagebox.showinfo("提示", "请先选中一条记录")
            return
        date_key, r, _ = recs[0]
        cur_tags = set(r.get('tags', []) or [])

        # 构建对话框
        dlg = tk.Toplevel(self.app.root)
        dlg.title("🏷️ 编辑标签")
        dlg.geometry("360x460")
        dlg.configure(bg=self.C['bg'])
        dlg.transient(self.app.root)
        dlg.resizable(False, False)

        tk.Label(dlg,
                 text="为 {} ({}) 选择标签".format(r.get('name',''), r.get('code','')),
                 font=('微软雅黑', 10, 'bold'),
                 bg=self.C['bg'], fg=self.C['text']).pack(pady=(16, 4))
        tk.Label(dlg, text="可多选，关闭对话框自动保存",
                 font=('微软雅黑', 8), bg=self.C['bg'], fg=self.C['dim']).pack(pady=(0, 12))

        # 标签复选框
        check_frame = tk.Frame(dlg, bg=self.C['bg'])
        check_frame.pack(fill='both', expand=True, padx=24)

        var_dict = {}
        for lbl, val in PRESET_TAGS:
            v = tk.BooleanVar(value=(val in cur_tags))
            var_dict[val] = v
            cb = tk.Checkbutton(check_frame, text=lbl,
                                 variable=v, font=('微软雅黑', 10),
                                 bg=self.C['bg'], fg=self.C['text'],
                                 selectcolor=self.C['card'],
                                 activebackground=self.C['bg'],
                                 anchor='w', padx=8)
            cb.pack(fill='x', pady=1)

        def _on_close():
            new_tags = [val for val, v in var_dict.items() if v.get()]
            hist_mod.update_record(date_key, r.get('id'), tags=new_tags)
            # 同步缓存
            self._sync_row_data_cache(r.get('id'), tags=new_tags)
            dlg.destroy()
            # 如果是当前显示的记录，刷新详情
            if self._cur_record_id == r.get('id'):
                self._show_detail()

        from ...widgets import styled_btn
        styled_btn(dlg, "💾 保存并关闭", self.C['green'],
                   _on_close, pady=8).pack(pady=12, fill='x', padx=24)
        dlg.protocol("WM_DELETE_WINDOW", _on_close)

    # ════════════════════════════════════════════
    # 从历史记录加入自选股
    # ════════════════════════════════════════════
    def _add_to_favorites(self):
        from ...core import config as cfg_mod
        recs = self._get_sel()
        if not recs:
            messagebox.showinfo("提示", "请先选中一条或多条记录")
            return
        added, dup = 0, 0
        for _, r, _ in recs:
            name = r.get("name", "").strip()
            code = r.get("code", "").strip()
            if not name or not code or code == "000000":
                continue
            if cfg_mod.add_favorite(name, code, tag="历史记录"):
                added += 1
            else:
                dup += 1
        bus.emit(Events.FAVORITES_UPDATED)
        if added:
            messagebox.showinfo("完成",
                "已加入自选股 {} 只{}".format(
                    added, "，{} 只已存在跳过".format(dup) if dup else ""))
        elif dup:
            messagebox.showinfo("提示", "选中的股票已全部在自选股中了")
        else:
            messagebox.showinfo("提示", "没有找到有效的股票代码（代码为000000的记录无法添加）")

    # ════════════════════════════════════════════
    # 导出星标
    # ════════════════════════════════════════════
    def _export_excel(self):
        # v9.9.8 Phase 2: 业务走 StarredExportService
        try:
            path = StarredExportService().to_excel()
            messagebox.showinfo("导出成功", path) if path else messagebox.showinfo("提示", "没有星标记录")
        except Exception as e:
            messagebox.showerror("失败", str(e))

    def _export_html(self):
        # v9.9.8 Phase 2: 业务走 StarredExportService
        try:
            path = StarredExportService().to_html()
            messagebox.showinfo("导出成功", path) if path else messagebox.showinfo("提示", "没有星标记录")
        except Exception as e:
            messagebox.showerror("失败", str(e))

    # ════════════════════════════════════════════════
    # 导出当日历史股票的实时行情
    # ════════════════════════════════════════════════
    def _export_daily_quotes(self):
        """
        v9.9.8 Phase 2: 业务下沉到 DailyQuotesExporter,
        本方法只剩 UI: 进度 toast + 错误弹框。
        """
        d = self._get_date_key()
        if not d:
            messagebox.showinfo("提示", "请先在左上角选择日期")
            return

        # 预检 — Service 会再次检查,但提前给用户更好的反馈
        records = hist_mod.load_history(d)
        if not records:
            messagebox.showinfo("提示", "当日无历史记录")
            return
        codes = list(set(r.get('code', '') for r in records
                         if r.get('code') and r['code'] != '000000'))
        if not codes:
            messagebox.showinfo("提示", "未找到有效的股票代码")
            return
        self._show_inline_toast(
            "⏳ 正在查询 {} 只股票行情...".format(len(codes)), "info")

        def _do():
            try:
                fn, n_rows, n_codes = DailyQuotesExporter().export(d)
            except ValueError as e:
                # Service 抛出的业务异常 — 用 toast 展示
                state.ui_queue.put(
                    lambda msg=str(e): self._show_inline_toast(
                        "❌ " + msg, "fail"))
                return
            except Exception as e:
                state.ui_queue.put(
                    lambda msg=str(e): self._show_inline_toast(
                        "❌ 保存失败: " + msg, "fail"))
                return
            state.ui_queue.put(lambda: (
                self._show_inline_toast(
                    "✅ 已导出: {}".format(fn.name), "ok"),
                messagebox.showinfo("导出成功",
                                    "已保存至:\n{}".format(str(fn)))
            ))

        threading.Thread(target=_do, daemon=True).start()
