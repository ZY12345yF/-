"""
SectorDetailMixin — 板块视图构建 + 详情渲染
包含板块榜单、龙头梯队、历史回看等子视图。
"""
import threading
import tkinter as tk
from tkinter import ttk

from ...services import SectorAnalysisService, SectorStocksSupplyService
from ...bus import state


class SectorDetailMixin:
    """板块视图构建与详情渲染（Mixin，不写 __init__）"""

    # ─── 板块视图 ───
    def _build_sector_view(self, parent):
        C = self.C
        pw = tk.PanedWindow(parent, bg=C['bg'], sashwidth=5,
                             sashrelief='flat', orient='horizontal')
        pw.pack(fill='both', expand=True)
        left  = tk.Frame(pw, bg=C['bg'])
        right = tk.Frame(pw, bg=C['bg'])
        pw.add(left, minsize=420)
        pw.add(right, minsize=520)

        tk.Label(left, text="板块榜单（按涨幅排序）",
                 font=('微软雅黑', 9, 'bold'),
                 bg=C['bg'], fg=C['accent']).pack(anchor='w', pady=(0, 4))

        cols = ('name', 'pct', 'inflow', 'leader')
        self._sector_tree = ttk.Treeview(left, columns=cols,
                                          show='headings', height=22)
        for col, txt, w in [('name', '板块', 150), ('pct', '涨幅', 70),
                              ('inflow', '主力流入', 90), ('leader', '领涨股', 110)]:
            self._sector_tree.heading(col, text=txt)
            self._sector_tree.column(col, width=w,
                                      anchor='center' if col != 'name' else 'w')
        vsb = ttk.Scrollbar(left, orient='vertical',
                             command=self._sector_tree.yview)
        self._sector_tree.configure(yscrollcommand=vsb.set)
        self._sector_tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')
        self._sector_tree.tag_configure('up_strong', foreground=C['red'])
        self._sector_tree.tag_configure('up',        foreground='#ff9a3c')
        self._sector_tree.tag_configure('down',      foreground=C['green'])
        self._sector_tree.bind('<<TreeviewSelect>>',
                                lambda e: self._on_sector_select())

        head = tk.Frame(right, bg=C['panel'],
                        highlightbackground=C['border'], highlightthickness=1)
        head.pack(fill='x')
        self._sect_title = tk.StringVar(value="选中一个板块查看详情")
        tk.Label(head, textvariable=self._sect_title,
                 font=('微软雅黑', 11, 'bold'),
                 bg=C['panel'], fg=C['accent']).pack(side='left', padx=10, pady=8)
        self._score_var = tk.StringVar(value="")
        tk.Label(head, textvariable=self._score_var,
                 font=('微软雅黑', 14, 'bold'),
                 bg=C['panel'], fg=C['yellow']).pack(side='right', padx=10, pady=8)

        self._breakdown_frame = tk.Frame(right, bg=C['bg'])
        self._breakdown_frame.pack(fill='x', pady=(4, 6))

        sub_nb = ttk.Notebook(right, style='App.TNotebook')
        sub_nb.pack(fill='both', expand=True)

        ladder_frame = tk.Frame(sub_nb, bg=C['bg'])
        sub_nb.add(ladder_frame, text="  🏆 龙头梯队  ")
        self._ladder_text = tk.Text(ladder_frame,
                                     font=('微软雅黑', 10), wrap='word',
                                     bg=C['card'], fg=C['text'],
                                     relief='flat', padx=10, pady=8,
                                     state='disabled', cursor='arrow')
        lvsb = ttk.Scrollbar(ladder_frame, orient='vertical',
                              command=self._ladder_text.yview)
        self._ladder_text.configure(yscrollcommand=lvsb.set)
        self._ladder_text.pack(side='left', fill='both', expand=True)
        lvsb.pack(side='right', fill='y')

        for tag, color in [('rank1', '#ffd700'), ('rank2', '#c0c0c0'),
                            ('rank3', '#cd7f32'), ('lu', C['red']),
                            ('broken', '#ff9a3c'), ('fading', C['yellow']),
                            ('follow', C['green']), ('section', C['accent']),
                            ('dim', C['dim'])]:
            self._ladder_text.tag_config(tag, foreground=color)
        self._ladder_text.tag_config('bold', font=('微软雅黑', 10, 'bold'))

        self._ladder_text.bind('<Button-1>',
                                self._ladder_left_click_follow, add='+')
        self._ladder_text.bind('<Button-3>', self._ladder_show_ctx)
        self._ladder_text.bind('<Button-2>', self._ladder_show_ctx)
        self._ladder_ctx = tk.Menu(self._ladder_text, tearoff=0,
            bg=C['panel'], fg=C['text'],
            activebackground=C['acc_dark'], activeforeground='white',
            font=('微软雅黑', 9))
        self._ladder_ctx.add_command(label="🔎  查看此股详情",
            command=self._ladder_show_stock_popup)

        history_frame = tk.Frame(sub_nb, bg=C['bg'])
        sub_nb.add(history_frame, text="  📅 历史回看  ")
        tk.Label(history_frame,
                 text="本地历史记录中该板块出现的所有日期",
                 font=('微软雅黑', 9), bg=C['bg'], fg=C['dim']).pack(anchor='w', pady=(6, 4))
        h_cols = ('date', 'count', 'stocks')
        self._hist_tree = ttk.Treeview(history_frame, columns=h_cols,
                                        show='headings', height=18)
        for col, txt, w in [('date', '日期', 100), ('count', '出现次数', 80),
                              ('stocks', '涉及股票', 350)]:
            self._hist_tree.heading(col, text=txt)
            self._hist_tree.column(col, width=w,
                                    anchor='center' if col != 'stocks' else 'w')
        h_vsb = ttk.Scrollbar(history_frame, orient='vertical',
                               command=self._hist_tree.yview)
        self._hist_tree.configure(yscrollcommand=h_vsb.set)
        self._hist_tree.pack(side='left', fill='both', expand=True)
        h_vsb.pack(side='right', fill='y')

    # ─── 板块榜单 / 板块详情 ───
    def _render_sectors(self, sectors, sector_type):
        for i in self._sector_tree.get_children():
            self._sector_tree.delete(i)
        self._sectors = sectors
        for s in sectors:
            pct = s.get('change_pct', 0)
            inflow_yi = s.get('main_inflow', 0) / 1e8
            leader_text = "{} ({:+.1f}%)".format(
                s.get('leader_name', ''), s.get('leader_pct', 0)) \
                if s.get('leader_name') else ""
            if pct >= 3:   tag = 'up_strong'
            elif pct > 0:  tag = 'up'
            else:          tag = 'down'
            self._sector_tree.insert('', 'end', values=(
                s.get('name', ''),
                "{:+.2f}%".format(pct),
                "{:+.2f}亿".format(inflow_yi),
                leader_text), tags=(tag,))

    def _on_sector_select(self):
        sel = self._sector_tree.selection()
        if not sel: return
        idx = self._sector_tree.index(sel[0])
        if idx >= len(self._sectors): return
        sector = self._sectors[idx]
        self._cur_sector = sector
        self._sect_title.set("📂 {}  ({:+.2f}%)".format(
            sector['name'], sector.get('change_pct', 0)))
        self._clear_breakdown(); self._clear_ladder(); self._clear_history_tree()

        self._select_seq += 1
        my_seq = self._select_seq
        code = sector.get('code', '')
        stocks = self._stocks_by_sector.get(code, [])
        if not stocks:
            # v9.9.8 Phase 2: 按需补拉走 SectorStocksSupplyService
            def _supply():
                fetched = SectorStocksSupplyService().supply(code)
                if fetched:
                    self._stocks_by_sector[code] = fetched
                    def _r():
                        if my_seq != self._select_seq: return
                        self._render_sector_detail(sector, fetched)
                    state.ui_queue.put(_r)
            threading.Thread(target=_supply, daemon=True).start()
            return
        self._render_sector_detail(sector, stocks)

    def _render_sector_detail(self, sector, stocks):
        """
        v9.9.8 Phase 2: 三个业务计算 (强度评分 + 梯队识别 + 历史查询)
        下沉到 SectorAnalysisService;本方法只负责渲染。
        """
        self._cur_stocks = stocks
        result = SectorAnalysisService().analyze(sector, stocks)
        self._render_score(
            result['score'], result['breakdown'], result['total_stocks'])
        self._render_ladder(result['ladder'], sector)
        self._render_history(result['history'])

    def _clear_breakdown(self):
        for w in self._breakdown_frame.winfo_children(): w.destroy()
        self._score_var.set("")

    def _render_score(self, score, breakdown, total_stocks):
        C = self.C
        for w in self._breakdown_frame.winfo_children(): w.destroy()
        if score >= 70: color = C['red']
        elif score >= 50: color = '#ff9a3c'
        elif score >= 30: color = C['yellow']
        else: color = C['dim']
        self._score_var.set("强度 {}/100".format(score))

        chips = [
            ("📈 涨停股", "{} 只".format(breakdown.get('limit_up', 0))),
            ("📊 涨幅",   "板块涨幅 {:+.2f}%".format(breakdown.get('sector_pct', 0))),
            ("🔥 涨家数比", "涨家数 {}".format(breakdown.get('up_ratio', '0/0'))),
            ("💰 主力净入", "主力净流入 {:+.2f} 亿".format(breakdown.get('inflow_yi', 0))),
        ]
        row = tk.Frame(self._breakdown_frame, bg=C['bg'])
        row.pack(fill='x', padx=4)
        for label, value in chips:
            chip = tk.Frame(row, bg=C['card'])
            chip.pack(side='left', padx=(0, 8), ipadx=6, ipady=3)
            tk.Label(chip, text=label, font=('微软雅黑', 8),
                     bg=C['card'], fg=C['dim']).pack(anchor='w')
            tk.Label(chip, text=value, font=('微软雅黑', 10, 'bold'),
                     bg=C['card'], fg=color).pack(anchor='w')

    def _clear_ladder(self):
        self._ladder_text.config(state='normal')
        self._ladder_text.delete('1.0', 'end')
        self._ladder_text.config(state='disabled')

    def _render_ladder(self, ladder, sector):
        C = self.C
        T = self._ladder_text
        T.config(state='normal'); T.delete('1.0', 'end')
        def w(text, tag=None):
            if tag: T.insert('end', text, tag)
            else:   T.insert('end', text)

        if not ladder:
            w("\n暂无梯队数据。", 'dim')
            T.config(state='disabled'); return

        w("\n📈 板块概况\n", 'section')
        w("成交额: {:.1f} 亿".format(ladder.get('total_volume', 0) / 1e8), 'dim')
        w("  ·  主力净流入: {:+.2f} 亿".format(
            sector.get('main_inflow', 0) / 1e8), 'dim')
        w("  ·  振幅: {:.2f}%\n\n".format(ladder.get('amplitude', 0)), 'dim')

        groups = [
            ("🔴 冲高回落（日内高位回落）", ladder.get('fading', []), 'fading'),
            ("🟡 炸板（涨停打开未封回）",  ladder.get('broken', []), 'broken'),
            ("🟢 强势龙头（按市值/涨幅）", ladder.get('leaders', []), 'rank1'),
            ("🔵 跟风梯队（次新）",        ladder.get('followers', []), 'follow'),
        ]
        for title, items, color_tag in groups:
            if not items: continue
            w(title + "  ", color_tag); w("{} 只\n".format(len(items)), 'dim')
            for i, st in enumerate(items[:15], 1):
                code = st.get('code', '')
                name = st.get('name', '')
                pct  = st.get('change_pct', 0)
                price= st.get('price', 0)
                high = st.get('high', 0)
                prev = st.get('prev_close', price)
                prefix = "龙{}".format(i) if title.startswith("🟢") else "·"
                w("  {} {}  ".format(prefix, name))
                w("({}) ".format(code), 'dim')
                w("现 {:+.2f}% / 高 {:+.2f}%\n".format(
                    pct,
                    100 * (high - prev) / max(1, prev)),
                  color_tag)
            w("\n")

        w("📊 板块结构: ", 'section')
        cnt = ladder.get('counts', {})
        parts = []
        for label, key in [('涨停','limit_up'),('补涨','followers'),
                            ('炸板','broken'),('冲高回落','fading'),
                            ('其他上涨','up'),('下跌','down')]:
            parts.append("{} {}".format(label, cnt.get(key, 0)))
        w("  ·  ".join(parts), 'dim')

        T.config(state='disabled')
        # 🆕 v9.9.6：龙头梯队里所有股票代码加蓝字下划线 → 推送同花顺
        try:
            from ...widgets import attach_code_links
            attach_code_links(T, self.app, scope='main')
        except Exception:
            import traceback; traceback.print_exc()

    def _clear_history_tree(self):
        for i in self._hist_tree.get_children():
            self._hist_tree.delete(i)

    def _render_history(self, history_data):
        for i in self._hist_tree.get_children():
            self._hist_tree.delete(i)
        if not history_data:
            self._hist_tree.insert('', 'end',
                values=("(无)", 0, "本地历史中未找到该板块"))
            return
        for entry in history_data:
            self._hist_tree.insert('', 'end', values=(
                entry['date'], entry['count'],
                "、".join(entry['stocks'][:5]) +
                ("..." if len(entry['stocks']) > 5 else "")))
