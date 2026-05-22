"""
SectorRadarMixin — 雷达视图构建 + 事件处理
包含涨停雷达视图、热度榜、右键菜单、龙头分析等。
"""
import tkinter as tk
from tkinter import ttk, messagebox

from ...core import history as hist_mod, sector as sector_core
from ...core import config as cfg_mod, text_utils
from ...bus import bus, Events


class SectorRadarMixin:
    """雷达视图构建与事件处理（Mixin，不写 __init__）"""

    # ─── 雷达视图 ───
    def _build_radar_view(self, parent):
        C = self.C
        top = tk.Frame(parent, bg=C['bg']); top.pack(fill='x', pady=(8, 6))
        tk.Label(top, text="最低涨幅", font=('微软雅黑', 9),
                 bg=C['bg'], fg=C['dim']).pack(side='left', padx=(0, 4))
        self._radar_min_pct = tk.StringVar(value="9.5")
        tk.Entry(top, textvariable=self._radar_min_pct, width=5,
                  font=('微软雅黑', 9)).pack(side='left')
        tk.Label(top, text="%   页数", font=('微软雅黑', 9),
                 bg=C['bg'], fg=C['dim']).pack(side='left', padx=(4, 4))
        self._radar_pages = tk.StringVar(value="5")
        tk.Entry(top, textvariable=self._radar_pages, width=4,
                  font=('微软雅黑', 9)).pack(side='left')
        tk.Label(top, text="(每页100只)", font=('微软雅黑', 8),
                 bg=C['bg'], fg=C['dim']).pack(side='left', padx=(4, 0))

        self._radar_sum_frame = tk.Frame(parent, bg=C['bg'])
        self._radar_sum_frame.pack(fill='x', pady=(0, 8))
        self._radar_sum_vars = {
            'limit_up':  tk.StringVar(value="—"),
            'avg_pct':   tk.StringVar(value="—"),
            'max_pct':   tk.StringVar(value="—"),
            'hot_codes': tk.StringVar(value="—"),
        }
        chip_items = [
            ('🎯 涨停股', 'limit_up'),
            ('📈 平均涨幅', 'avg_pct'),
            ('🚀 最高涨幅', 'max_pct'),
            ('🔥 本地有历史', 'hot_codes'),
        ]
        for label, key in chip_items:
            f = tk.Frame(self._radar_sum_frame, bg=C['card'])
            f.pack(side='left', padx=(0, 8), pady=2, ipadx=8, ipady=4)
            tk.Label(f, text=label, font=('微软雅黑', 8),
                     bg=C['card'], fg=C['dim']).pack(anchor='w')
            tk.Label(f, textvariable=self._radar_sum_vars[key],
                     font=('微软雅黑', 12, 'bold'),
                     bg=C['card'], fg=C['accent']).pack(anchor='w')

        pw = tk.PanedWindow(parent, bg=C['bg'], sashwidth=5,
                             sashrelief='flat', orient='horizontal')
        pw.pack(fill='both', expand=True)
        lf = tk.Frame(pw, bg=C['bg'])
        rf = tk.Frame(pw, bg=C['bg'])
        pw.add(lf, minsize=560)
        pw.add(rf, minsize=280)

        tk.Label(lf, text="涨幅榜（含可能涨停的股票）",
                 font=('微软雅黑', 9, 'bold'),
                 bg=C['bg'], fg=C['accent']).pack(anchor='w', pady=(0, 4))
        cols = ('name', 'code', 'price', 'pct', 'high', 'low')
        self._radar_tree = ttk.Treeview(lf, columns=cols,
                                          show='headings', height=20)
        for col, txt, w in [('name','名称',120),('code','代码',90),
                              ('price','现价',80),('pct','涨幅%',80),
                              ('high','最高',80),('low','最低',80)]:
            self._radar_tree.heading(col, text=txt)
            self._radar_tree.column(col, width=w, minwidth=40,
                                     anchor='center', stretch=True)
        self._radar_tree.pack(side='left', fill='both', expand=True)
        rvsb = ttk.Scrollbar(lf, orient='vertical',
                              command=self._radar_tree.yview)
        self._radar_tree.configure(yscrollcommand=rvsb.set)
        rvsb.pack(side='right', fill='y')
        self._radar_tree.tag_configure('lu', foreground=C['red'])
        self._radar_tree.tag_configure('up', foreground='#ff9a3c')

        self._radar_tree.bind('<<TreeviewSelect>>',
                               lambda e: self._radar_on_row_focus())
        self._radar_tree.bind('<Double-1>',
                               lambda e: self._radar_analyze_selected())
        self._radar_ctx = tk.Menu(self._radar_tree, tearoff=0,
            bg=C['panel'], fg=C['text'],
            activebackground=C['acc_dark'], activeforeground='white',
            font=('微软雅黑', 9))
        self._radar_ctx.add_command(label="🔎  查看股票详情",
            command=self._radar_show_popup_selected)
        self._radar_ctx.add_separator()
        self._radar_ctx.add_command(label="🔍  分析选中（送AI）",
            command=self._radar_analyze_selected)
        self._radar_ctx.add_command(label="⭐  加入自选股",
            command=self._radar_add_to_fav)
        self._radar_tree.bind('<Button-3>', self._radar_show_ctx)
        self._radar_tree.bind('<Button-2>', self._radar_show_ctx)

        tk.Label(rf, text="🔥 今日个股热度 TopN",
                 font=('微软雅黑', 9, 'bold'),
                 bg=C['bg'], fg=C['accent']).pack(anchor='w', pady=(0, 4))
        tk.Label(rf,
                 text="（涨幅榜 ∩ 本地历史）",
                 font=('微软雅黑', 8),
                 bg=C['bg'], fg=C['dim']).pack(anchor='w', pady=(0, 4))

        hot_cols = ('rank', 'name', 'code', 'pct', 'hist')
        self._hot_tree = ttk.Treeview(rf, columns=hot_cols,
                                       show='headings', height=15)
        for col, txt, w in [('rank','#',30),('name','名称',95),
                              ('code','代码',75),('pct','今涨',60),
                              ('hist','历史',50)]:
            self._hot_tree.heading(col, text=txt)
            self._hot_tree.column(col, width=w, minwidth=30,
                                   anchor='center' if col != 'name' else 'w')
        self._hot_tree.pack(fill='both', expand=True)
        self._hot_tree.tag_configure('lu', foreground=C['red'])
        self._hot_tree.bind('<<TreeviewSelect>>',
                             lambda e: self._hot_on_row_focus())
        self._hot_tree.bind('<Double-1>',
                             lambda e: self._hot_open_popup())

    # ─── 雷达 ───
    def _render_radar(self, radar_data):
        for i in self._radar_tree.get_children():
            self._radar_tree.delete(i)
        self._radar_data = radar_data or []
        if not radar_data:
            self._radar_sum_vars['limit_up'].set("—")
            self._radar_sum_vars['avg_pct'].set("—")
            self._radar_sum_vars['max_pct'].set("—")
            self._radar_sum_vars['hot_codes'].set("—")
        else:
            limit_up = sum(1 for s in radar_data
                            if s.get('change_pct', 0) >= 9.7)
            pcts = [s.get('change_pct', 0) for s in radar_data]
            avg = sum(pcts) / max(1, len(pcts))
            mx  = max(pcts) if pcts else 0
            self._radar_sum_vars['limit_up'].set("{} 只".format(limit_up))
            self._radar_sum_vars['avg_pct'].set("+{:.2f}%".format(avg))
            self._radar_sum_vars['max_pct'].set("+{:.2f}%".format(mx))

        hidx = hist_mod.get_code_count_index()
        hit = 0
        hot_candidates = []
        for s in radar_data:
            code = str(s.get('code', '')).zfill(6)
            n_hist = hidx.get(code, 0)
            mark = " 📊" if n_hist > 0 else ""
            tag = 'lu' if s.get('change_pct', 0) >= 9.7 else 'up'
            self._radar_tree.insert('', 'end', values=(
                s.get('name', '') + mark, code,
                "{:.2f}".format(s.get('price', 0)),
                "+{:.2f}%".format(s.get('change_pct', 0)),
                "{:.2f}".format(s.get('high', 0)),
                "{:.2f}".format(s.get('low', 0))), tags=(tag,))
            if n_hist > 0:
                hit += 1
                hot_candidates.append({
                    'name': s.get('name', ''), 'code': code,
                    'pct': s.get('change_pct', 0),
                    'hist': n_hist,
                })
        self._radar_sum_vars['hot_codes'].set("{} 只".format(hit))

        hot_candidates.sort(key=lambda x: (-x['hist'], -x['pct']))
        for i in self._hot_tree.get_children():
            self._hot_tree.delete(i)
        for rank, st in enumerate(hot_candidates[:20], 1):
            tag = 'lu' if st['pct'] >= 9.7 else ''
            self._hot_tree.insert('', 'end', values=(
                rank, st['name'], st['code'],
                "+{:.1f}%".format(st['pct']),
                "{}次".format(st['hist'])), tags=(tag,) if tag else ())

    def _radar_on_row_focus(self):
        sel = self._radar_tree.selection()
        if not sel: return
        v = self._radar_tree.item(sel[0])['values']
        if len(v) >= 2:
            name = str(v[0]).replace(" 📊", "").replace("📊", "").strip()
            self.app.notify_stock_focus(str(v[1]), name)

    def _radar_show_popup_selected(self):
        sel = self._radar_tree.selection()
        if not sel: return
        v = self._radar_tree.item(sel[0])['values']
        if len(v) >= 2:
            name = str(v[0]).replace(" 📊", "").replace("📊", "").strip()
            self.app.show_stock_popup(str(v[1]), name)

    def _radar_show_ctx(self, e):
        try:
            self._radar_tree.identify_row(e.y)
            self._radar_ctx.tk_popup(e.x_root, e.y_root)
        finally:
            self._radar_ctx.grab_release()

    def _radar_analyze_selected(self):
        sel = self._radar_tree.selection()
        if not sel:
            messagebox.showinfo("提示", "请先选中要分析的股票"); return
        try:
            single = self.app.tabs.get('SingleTab')
            if not single: return
            v = self._radar_tree.item(sel[0])['values']
            name = str(v[0]).replace(" 📊", "").replace("📊", "").strip()
            code = str(v[1])
            for i in range(self.app.nb.index('end')):
                txt = self.app.nb.tab(i, 'text') or ""
                if '单股' in txt or 'Single' in txt.lower():
                    self.app.nb.select(i); break
            if hasattr(single, 'name_var'): single.name_var.set(name)
            if hasattr(single, 'code_var'): single.code_var.set(code)
            if hasattr(single, 'trigger_search'): single.trigger_search()
        except Exception:
            pass

    def _radar_add_to_fav(self):
        sel = self._radar_tree.selection()
        added = 0
        for it in sel:
            v = self._radar_tree.item(it)['values']
            if len(v) < 2: continue
            name = str(v[0]).replace(" 📊", "").replace("📊", "").strip()
            code = str(v[1])
            if cfg_mod.add_favorite(name, code, tag="涨停雷达"):
                added += 1
        if added:
            bus.emit(Events.FAVORITES_UPDATED)
        messagebox.showinfo("完成", "已添加 {} 只到自选股".format(added))

    def _hot_on_row_focus(self):
        sel = self._hot_tree.selection()
        if not sel: return
        v = self._hot_tree.item(sel[0])['values']
        if len(v) >= 3:
            self.app.notify_stock_focus(str(v[2]), str(v[1]))

    def _hot_open_popup(self):
        sel = self._hot_tree.selection()
        if not sel: return
        v = self._hot_tree.item(sel[0])['values']
        if len(v) >= 3:
            self.app.show_stock_popup(str(v[2]), str(v[1]))

    # ─── 龙头梯队左键 / 右键 ───
    def _ladder_left_click_follow(self, event):
        """v9.9.6：左键单击 → 通知浮窗刷新（浮窗永远跟随主程序）"""
        text_utils.left_click_follow(event, self._ladder_text, self.app)

    def _ladder_show_ctx(self, event):
        try:
            self._ladder_click_idx = self._ladder_text.index(
                "@{},{}".format(event.x, event.y))
        except Exception:
            self._ladder_click_idx = None
        try:
            self._ladder_ctx.tk_popup(event.x_root, event.y_root)
        finally:
            self._ladder_ctx.grab_release()

    def _ladder_show_stock_popup(self):
        idx = getattr(self, '_ladder_click_idx', None) or self._ladder_text.index('insert')
        try:
            ln = idx.split('.')[0]
            search_text = self._ladder_text.get(
                "{}.0".format(ln), "{}.end".format(ln))
        except Exception:
            search_text = ""
        code, name = text_utils.extract_code_and_name(search_text)
        if not code:
            messagebox.showinfo("提示", "未识别到股票代码"); return
        self.app.show_stock_popup(code, name)

    def _analyze_leaders(self):
        if not self._cur_sector or not self._cur_stocks:
            messagebox.showinfo("提示", "请先选择一个板块"); return
        ladder = sector_core.identify_ladder(self._cur_stocks)
        leaders = ladder.get('leaders', [])[:3]
        if not leaders:
            messagebox.showinfo("提示", "本板块无明显龙头"); return
        single = self.app.tabs.get('SingleTab')
        if not single: return
        for i in range(self.app.nb.index('end')):
            txt = self.app.nb.tab(i, 'text') or ""
            if '单股' in txt or 'Single' in txt.lower():
                self.app.nb.select(i); break
        if hasattr(single, 'name_var'):
            single.name_var.set(leaders[0].get('name', ''))
        if hasattr(single, 'code_var'):
            single.code_var.set(leaders[0].get('code', ''))
        if hasattr(single, 'trigger_search'):
            single.trigger_search()
