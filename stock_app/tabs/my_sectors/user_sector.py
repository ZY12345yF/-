"""
自定义板块相关方法（Mixin）—— 从 my_sectors_tab.py 拆出
v9.9.7：单一职责拆分，对外接口完全不变
"""
import threading
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

from ...widgets import (
    make_card, styled_btn, styled_entry, apply_highlight,
    load_col_widths, save_col_widths,
)
from ...core import (
    config as cfg_mod,
    history as hist_mod,
    api_client, my_sectors,
)
from ...bus import bus, Events, state


class UserSectorMixin:
    """所有 _user_xxx / _build_user_sector_view 等自定义板块相关方法"""

    def _build_user_sector_view(self):
        C = self.C
        v = tk.Frame(self._right_container, bg=C['bg'])
        v.pack(fill='both', expand=True)

        # 顶部
        hr = tk.Frame(v, bg=C['bg']); hr.pack(fill='x', pady=(0, 6))
        self._sector_title_var = tk.StringVar(value="📂 " + (self._cur_sector_name or ""))
        tk.Label(hr, textvariable=self._sector_title_var,
                 font=('微软雅黑', 12, 'bold'),
                 bg=C['bg'], fg=C['accent']).pack(side='left')

        self._auto_refresh_var = tk.BooleanVar(value=False)
        tk.Checkbutton(hr, text="🔁 自动刷新(30s)",
                       variable=self._auto_refresh_var,
                       font=('微软雅黑', 9),
                       bg=C['bg'], fg=C['yellow'],
                       selectcolor=C['card'],
                       activebackground=C['bg'],
                       command=self._toggle_auto_refresh).pack(side='right', padx=(0, 6))
        styled_btn(hr, "🔄 刷新行情", C['accent'],
                   self._refresh_user_quotes).pack(side='right', padx=(4, 0))
        styled_btn(hr, "🚀 分析整个板块", C['green'],
                   self._analyze_user_sector).pack(side='right', padx=(4, 0))

        # 统计卡
        self._stat_frame = tk.Frame(v, bg=C['bg'])
        self._stat_frame.pack(fill='x', pady=(0, 6))

        # 工具栏
        tb = tk.Frame(v, bg=C['panel'],
                      highlightbackground=C['border'], highlightthickness=1)
        tb.pack(fill='x', pady=(0, 4))
        tk.Label(tb, text="📋 股票列表",
                 font=('微软雅黑', 9, 'bold'),
                 bg=C['panel'], fg=C['accent']).pack(side='left', padx=8, pady=5)
        styled_btn(tb, "➕ 添加", C['accent'],
                   self._user_add_stock_dialog).pack(side='right', padx=4, pady=4)
        styled_btn(tb, "🗑 删除选中", C['red'],
                   self._user_remove_selected).pack(side='right', padx=(0, 4), pady=4)

        # 双栏：左股票表 / 右详情
        pw = tk.PanedWindow(v, bg=C['bg'], sashwidth=5,
                             sashrelief='flat', orient='horizontal')
        pw.pack(fill='both', expand=True)
        lf = tk.Frame(pw, bg=C['bg'])
        rf = tk.Frame(pw, bg=C['bg'])
        pw.add(lf, minsize=420)
        pw.add(rf, minsize=380)

        cols = ('name', 'code', 'price', 'pct', 'last_date', 'next_day')
        col_widths = load_col_widths('user_sector')
        defaults = {'name': 110, 'code': 80, 'price': 70, 'pct': 80,
                    'last_date': 80, 'next_day': 70}
        titles = {'name': '名称', 'code': '代码', 'price': '现价',
                  'pct': '涨跌幅', 'last_date': '最近分析', 'next_day': '次日%'}
        self._user_tree = ttk.Treeview(lf, columns=cols, show='headings', height=22)
        for col in cols:
            self._user_tree.heading(col, text=titles[col])
            self._user_tree.column(col,
                                    width=col_widths.get(col, defaults[col]),
                                    minwidth=40,
                                    anchor='center' if col != 'name' else 'w',
                                    stretch=True)
        uvsb = ttk.Scrollbar(lf, orient='vertical', command=self._user_tree.yview)
        self._user_tree.configure(yscrollcommand=uvsb.set)
        self._user_tree.pack(side='left', fill='both', expand=True)
        uvsb.pack(side='right', fill='y')

        def _save_w(*_):
            save_col_widths('user_sector',
                {c: self._user_tree.column(c, 'width') for c in cols})
        self._user_tree.bind('<ButtonRelease-1>', _save_w)

        self._user_tree.tag_configure('lu', foreground=C['red'], background=C['acc_dark'])
        self._user_tree.tag_configure('up_strong', foreground=C['red'])
        self._user_tree.tag_configure('up',   foreground='#ff9a3c')
        self._user_tree.tag_configure('down', foreground=C['green'])
        self._user_tree.tag_configure('flat', foreground=C['dim'])
        self._user_tree.bind('<<TreeviewSelect>>',
                              lambda e: self._user_show_detail())

        # 右键菜单
        m = tk.Menu(self._user_tree, tearoff=0,
                     bg=C['panel'], fg=C['text'],
                     activebackground=C['acc_dark'],
                     activeforeground='white',
                     font=('微软雅黑', 9))
        m.add_command(label="🔎  查看股票详情",
                       command=self._user_show_popup)
        m.add_separator()
        m.add_command(label="🔍  单股分析（送AI）",
                       command=self._user_analyze_single)
        m.add_command(label="📋  复制代码",
                       command=lambda: self._user_copy('code'))
        m.add_command(label="📋  复制名称+代码",
                       command=lambda: self._user_copy('name_code'))
        m.add_separator()
        m.add_command(label="⭐  加入自选股",
                       command=self._user_add_to_fav)
        m.add_separator()
        m.add_command(label="🗑  从板块删除",
                       command=self._user_remove_selected)
        self._user_ctx = m
        def _show(event):
            iid = self._user_tree.identify_row(event.y)
            if iid:
                if iid not in self._user_tree.selection():
                    self._user_tree.selection_set(iid)
                try:
                    m.tk_popup(event.x_root, event.y_root)
                finally:
                    m.grab_release()
        self._user_tree.bind('<Button-3>', _show)
        self._user_tree.bind('<Button-2>', _show)

        # 右侧详情
        rh = tk.Frame(rf, bg=C['panel'],
                       highlightbackground=C['border'], highlightthickness=1)
        rh.pack(fill='x')
        self._user_detail_title = tk.StringVar(value="📄 详情（点击左侧）")
        tk.Label(rh, textvariable=self._user_detail_title,
                 font=('微软雅黑', 10, 'bold'),
                 bg=C['panel'], fg=C['accent']).pack(side='left', padx=8, pady=6)
        styled_btn(rh, "✨ 自动高亮", C['acc_dark'],
                   lambda: apply_highlight(self._user_detail, keep_editable=True),
                   pady=3).pack(side='right', padx=(0, 4), pady=4)

        self._user_detail = tk.Text(rf, font=('微软雅黑', 10), wrap='word',
                                     bg=C['card'], fg=C['text'],
                                     relief='flat', padx=10, pady=8,
                                     state='disabled', cursor='arrow')
        udvsb = ttk.Scrollbar(rf, orient='vertical', command=self._user_detail.yview)
        self._user_detail.configure(yscrollcommand=udvsb.set)
        self._user_detail.pack(side='left', fill='both', expand=True)
        udvsb.pack(side='right', fill='y')
        for tag, fg, bg in [
            ('accent', C['accent'], ''), ('star_tag', C['star'], ''),
            ('dim', C['dim'], ''), ('policy', C['yellow'], ''),
            ('concept', C['green'], ''), ('money', C['red'], ''),
            ('percent', C['accent'], ''),
            ('category', 'white', C['purple']),
            ('category_kw', '#05070b', C['star']),
            ('h2', C['yellow'], ''),
        ]:
            kw = {'foreground': fg}
            if bg: kw['background'] = bg
            if tag == 'category':
                kw['font'] = ('微软雅黑', 10, 'bold')
            self._user_detail.tag_config(tag, **kw)

        self._render_user_sector()

    def _render_user_sector(self):
        if not hasattr(self, '_user_tree') or not self._cur_sector_name:
            return
        sector = my_sectors.get_sector(self._cur_sector_name)
        if not sector:
            return
        self._sector_title_var.set("📂 " + self._cur_sector_name)

        # 统计卡
        for w in self._stat_frame.winfo_children():
            w.destroy()
        stats = my_sectors.get_sector_stats(self._cur_sector_name)
        if stats:
            self._render_stat_card(stats, sector)

        # 表
        for i in self._user_tree.get_children():
            self._user_tree.delete(i)
        self._row_data.clear()

        quotes = sector.get('quotes', {})
        index = self._build_history_index()
        hidx = hist_mod.get_code_count_index()    # 🆕 v9.6
        stocks = list(sector['stocks'])
        if quotes:
            stocks.sort(key=lambda s: -quotes.get(s['code'], {}).get('change_pct', -999))

        for s in stocks:
            code = s.get('code', '')
            q = quotes.get(code, {})
            name = s.get('name') or q.get('name', '')
            price = q.get('price', '')
            chg = q.get('change_pct')
            pct_str = "--" if chg is None else "{:+.2f}%".format(chg)
            tag = 'flat'
            if chg is not None:
                if chg >= 9.7: tag = 'lu'
                elif chg >= 3: tag = 'up_strong'
                elif chg > 0:  tag = 'up'
                elif chg < 0:  tag = 'down'

            last = index.get(code)
            last_date = ""
            nd_str = ""
            if last:
                d = last['date']
                last_date = "{}-{}".format(d[4:6], d[6:])
                nd = last.get('next_day')
                if nd and nd.get('change_pct') is not None:
                    nd_str = "{:+.1f}%".format(nd['change_pct'])

            # 🆕 v9.6：有历史则 name 后追加 📊
            disp_name = name + (" 📊" if hidx.get(str(code).zfill(6), 0) > 0 else "")
            iid = self._user_tree.insert('', 'end',
                values=(disp_name, code, price, pct_str, last_date, nd_str),
                tags=(tag,))
            self._row_data[iid] = {'name': name, 'code': code,
                                    'last_record': last,
                                    'tag': self._cur_sector_name}

    def _render_stat_card(self, stats, sector):
        C = self.C
        row = tk.Frame(self._stat_frame, bg=C['bg'])
        row.pack(fill='x')
        refresh_str = "上次刷新: " + (sector.get('last_refresh', '未刷新'))
        tk.Label(row,
                 text="共 {} 只  ·  {}".format(stats['total'], refresh_str),
                 font=('微软雅黑', 9),
                 bg=C['bg'], fg=C['dim']).pack(anchor='w', padx=4, pady=(0, 4))

        row2 = tk.Frame(self._stat_frame, bg=C['bg'])
        row2.pack(fill='x')
        items = [
            ('🎯 涨停', "{} 只".format(stats['limit_up']), C['red']),
            ('📈 上涨', "{} 只".format(stats['up']),       C['red']),
            ('📉 下跌', "{} 只".format(stats['down']),     C['green']),
            ('📊 平均', "{:+.2f}%".format(stats['avg_pct']),
                       C['red'] if stats['avg_pct'] > 0 else C['green']),
        ]
        for lbl, val, color in items:
            cell = tk.Frame(row2, bg=C['panel'],
                             highlightbackground=C['border'], highlightthickness=1)
            cell.pack(side='left', fill='both', expand=True, padx=2)
            tk.Label(cell, text=lbl, font=('微软雅黑', 8),
                     bg=C['panel'], fg=C['dim']).pack(pady=(4, 0))
            tk.Label(cell, text=val, font=('微软雅黑', 12, 'bold'),
                     bg=C['panel'], fg=color).pack(pady=(0, 4))

    def _user_show_detail(self):
        sel = self._user_tree.selection()
        if not sel: return
        data = self._row_data.get(sel[0])
        if not data: return
        # 🆕 v9.6：通知浮窗（联动模式开启时刷新）
        self.app.notify_stock_focus(data.get('code',''), data.get('name',''))

        T = self._user_detail
        T.config(state='normal')
        T.delete('1.0', 'end')

        name = data.get('name', ''); code = data.get('code', '')
        self._user_detail_title.set("📄 {} ({})".format(name, code))

        def w(text, t=None):
            if t: T.insert('end', text, t)
            else: T.insert('end', text)

        w("📂 {} · {} ({})\n".format(self._cur_sector_name, name, code), 'accent')
        w("\n")

        last = data.get('last_record')
        if last:
            d = last['date']
            w("─" * 50 + "\n", 'dim')
            w("📈 最近一次分析  ", 'h2')
            w("({}-{}-{}  {})\n".format(d[:4], d[4:6], d[6:],
                                          last.get('time', '')), 'dim')
            nd = last.get('next_day')
            if nd and nd.get('change_pct') is not None:
                pct = nd['change_pct']
                ct = 'concept' if pct > 0 else 'money'
                w("📊 次日: ", 'star_tag')
                w("{:+.2f}%".format(pct), ct)
                w("\n")
            w("\n")
            content = last.get('content', '')
            if content:
                w(content)
                apply_highlight(T, keep_editable=True)
        else:
            w("─" * 50 + "\n", 'dim')
            w("⚠️ 该股票暂无历史分析记录\n", 'dim')
            w("💡 提示：右键 → 单股分析 开始分析\n", 'dim')

        T.config(state='disabled')
        # 🆕 v9.9.6：详情里所有 6 位代码加蓝字下划线 → 推送同花顺
        try:
            from ...widgets import attach_code_links
            attach_code_links(T, self.app, main_code=code, scope='main')
        except Exception:
            import traceback; traceback.print_exc()

    def _refresh_user_quotes(self):
        if not self._cur_sector_name: return
        def _do():
            my_sectors.refresh_quotes(self._cur_sector_name)
            state.ui_queue.put(self._render_user_sector)
        threading.Thread(target=_do, daemon=True).start()

    def _toggle_auto_refresh(self):
        self._auto_refresh_on = self._auto_refresh_var.get()
        if self._auto_refresh_on:
            self._schedule_next_refresh()
        else:
            if self._auto_refresh_id:
                try:
                    self.app.root.after_cancel(self._auto_refresh_id)
                except Exception:
                    pass
                self._auto_refresh_id = None

    def _schedule_next_refresh(self):
        if not self._auto_refresh_on or not self._cur_sector_name:
            return
        threading.Thread(target=lambda: (
            my_sectors.refresh_quotes(self._cur_sector_name),
            state.ui_queue.put(self._render_user_sector)
        ), daemon=True).start()
        self._auto_refresh_id = self.app.root.after(
            30000, self._schedule_next_refresh)

    def _user_add_stock_dialog(self):
        if not self._cur_sector_name: return
        s = simpledialog.askstring("添加股票",
            "输入名称+代码（如：寒武纪 688256）：", parent=self.app.root)
        if not s: return
        name_lookup = cfg_mod.get_name_lookup()
        parsed = my_sectors.parse_import_text(s, name_lookup=name_lookup)
        if not parsed:
            messagebox.showinfo("失败", "未识别到代码"); return
        my_sectors.add_stocks(self._cur_sector_name, parsed)
        self._refresh_user_quotes()
        self._refresh_nav()

    def _user_remove_selected(self):
        sel = self._user_tree.selection()
        if not sel or not self._cur_sector_name: return
        codes = [self._row_data.get(iid, {}).get('code', '')
                 for iid in sel]
        codes = [c for c in codes if c]
        if not codes: return
        if not messagebox.askyesno("确认",
                "从「{}」删除 {} 只？".format(self._cur_sector_name, len(codes))):
            return
        my_sectors.remove_stocks(self._cur_sector_name, codes)
        self._render_user_sector()
        self._refresh_nav()

    def _analyze_user_sector(self):
        if not self._cur_sector_name: return
        sector = my_sectors.get_sector(self._cur_sector_name)
        if not sector or not sector['stocks']:
            messagebox.showinfo("提示", "板块为空"); return
        stocks = [(s['name'] or s['code'], s['code'], self._cur_sector_name)
                  for s in sector['stocks']]
        if not messagebox.askyesno("确认",
                "分析「{}」板块的 {} 只股票？".format(
                    self._cur_sector_name, len(stocks))):
            return
        bus.emit(Events.REQUEST_BATCH_RUN, stocks, "板块·" + self._cur_sector_name)

    def _user_analyze_single(self):
        sel = self._user_tree.selection()
        if not sel: return
        data = self._row_data.get(sel[0])
        if not data: return
        single = self.app.tabs.get('SingleTab')
        if single:
            try:
                idx = self.app.nb.index(single.frame)
                self.app.nb.select(idx)
                single.name_var.set(data['name'])
                single.code_var.set(data['code'])
            except Exception:
                pass

    def _user_copy(self, kind):
        sel = self._user_tree.selection()
        if not sel: return
        data = self._row_data.get(sel[0])
        if not data: return
        if kind == 'code':
            s = data['code']
        else:
            s = "{} {}".format(data['name'], data['code'])
        self.app.root.clipboard_clear()
        self.app.root.clipboard_append(s)

    def _user_add_to_fav(self):
        sel = self._user_tree.selection()
        if not sel: return
        added = 0
        for iid in sel:
            data = self._row_data.get(iid)
            if data and cfg_mod.add_favorite(data['name'], data['code'],
                                             tag=self._cur_sector_name or ""):
                added += 1
        bus.emit(Events.FAVORITES_UPDATED)
        self._refresh_nav()

    def _user_show_popup(self):
        """🆕 v9.5：在浮窗打开股票详情"""
        sel = self._user_tree.selection()
        if not sel: return
        data = self._row_data.get(sel[0])
        if data:
            self.app.show_stock_popup(data.get('code',''), data.get('name',''))

    # ════════════════════════════════════════════════
    # 视图3: 标签关联度 (v9.2：天数控制 + API 收纳 + 标签管理 + 双击跳转)
    # ════════════════════════════════════════════════