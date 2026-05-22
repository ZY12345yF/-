"""
📋 复盘日报 Mixin
子Tab 1: 当日盘面汇总
"""
import tkinter as tk
from tkinter import ttk, messagebox

from ...widgets import styled_btn
from ...core import replay, history as hist_mod, text_utils
from ...bus import bus, Events, state


class DailyReportMixin:
    """复盘日报 —— 当日盘面汇总"""

    def _build_daily(self, parent):
        C = self.C
        # 顶部控制
        ctrl = tk.Frame(parent, bg=C['bg']); ctrl.pack(fill='x', pady=(8, 6))
        tk.Label(ctrl, text="日期", font=('微软雅黑', 9),
                 bg=C['bg'], fg=C['dim']).pack(side='left', padx=(0, 4))
        self._daily_date = tk.StringVar()
        self._daily_combo = ttk.Combobox(ctrl, textvariable=self._daily_date,
                                          state='readonly', width=14,
                                          font=('微软雅黑', 9))
        self._daily_combo.pack(side='left', padx=(0, 8))
        self._daily_combo.bind('<<ComboboxSelected>>',
                                lambda e: self._generate_daily_report())
        styled_btn(ctrl, "📋 生成日报", C['accent'],
                   self._generate_daily_report).pack(side='left', padx=(4, 0))
        styled_btn(ctrl, "🔄 刷新日期", C['idle'],
                   self._refresh_daily_dates).pack(side='right')

        # 报告显示区
        self._daily_text = tk.Text(parent, font=('微软雅黑', 10), wrap='word',
                                    bg=C['card'], fg=C['text'],
                                    relief='flat', padx=14, pady=10,
                                    state='disabled', cursor='arrow')
        vsb = ttk.Scrollbar(parent, orient='vertical',
                             command=self._daily_text.yview)
        self._daily_text.configure(yscrollcommand=vsb.set)
        self._daily_text.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')

        # tag 配色
        for tag, color in [
            ('h1',      C['accent']),  ('h2', C['yellow']),
            ('star',    C['star']),    ('green', C['green']),
            ('red',     C['red']),     ('dim', C['dim']),
            ('hot',     C['red']),     ('cool', C['purple']),
        ]:
            self._daily_text.tag_config(tag, foreground=color)
        self._daily_text.tag_config('bold', font=('微软雅黑', 10, 'bold'))
        self._daily_text.tag_config('h1bold',
            font=('微软雅黑', 12, 'bold'), foreground=C['accent'])

        # 🆕 v9.5：复盘日报右键 → 看光标附近股票详情
        self._daily_text.bind('<Button-3>', self._daily_show_ctx)
        self._daily_text.bind('<Button-2>', self._daily_show_ctx)
        # 🆕 v9.6：左键联动 — 单击文字时识别附近股票并通知浮窗（不阻止默认行为）
        self._daily_text.bind('<Button-1>', self._daily_left_click_follow, add='+')
        self._daily_ctx = tk.Menu(self._daily_text, tearoff=0,
            bg=C['panel'], fg=C['text'],
            activebackground=C['acc_dark'], activeforeground='white',
            font=('微软雅黑', 9))
        self._daily_ctx.add_command(label="🔎  查看此股详情",
            command=self._daily_show_stock_popup)

        self._refresh_daily_dates()

    def _daily_show_ctx(self, event):
        try:
            self._daily_click_idx = self._daily_text.index(
                "@{},{}".format(event.x, event.y))
        except Exception:
            self._daily_click_idx = None
        try:
            self._daily_ctx.tk_popup(event.x_root, event.y_root)
        finally:
            self._daily_ctx.grab_release()

    def _daily_show_stock_popup(self):
        idx = getattr(self, '_daily_click_idx', None) or self._daily_text.index('insert')
        try:
            search_text = self._daily_text.get('sel.first', 'sel.last')
        except tk.TclError:
            search_text = ""
        if not search_text:
            try:
                ln = idx.split('.')[0]
                search_text = self._daily_text.get("{}.0".format(ln), "{}.end".format(ln))
            except Exception:
                search_text = ""
        code, name = text_utils.extract_code_and_name(search_text)
        if not code:
            messagebox.showinfo("提示", "未在光标附近识别到股票代码")
            return
        self.app.show_stock_popup(code, name)

    def _daily_left_click_follow(self, event):
        """v9.9.6：左键单击 → 通知浮窗刷新（浮窗永远跟随，不再需要开关判断）"""
        text_utils.left_click_follow(event, self._daily_text, self.app)

    def _refresh_daily_dates(self):
        dates = hist_mod.list_history_dates()
        display = [d[:4]+'-'+d[4:6]+'-'+d[6:] for d in dates]
        self._daily_combo['values'] = display
        if dates and not self._daily_date.get():
            self._daily_combo.current(0)
            self._generate_daily_report()

    def _generate_daily_report(self):
        d = self._daily_date.get().replace('-', '')
        if not d:
            return
        self._daily_text.config(state='normal')
        self._daily_text.delete('1.0', 'end')

        report = replay.generate_daily_report(d)
        if not report:
            self._daily_text.insert('end', "该日无历史记录")
            self._daily_text.config(state='disabled')
            return

        T = self._daily_text
        def w(text, tag=None):
            if tag: T.insert('end', text, tag)
            else:   T.insert('end', text)

        # ── 标题 ──
        w("📋 复盘日报  ·  {}\n".format(report['date_display']), 'h1bold')
        w("━" * 50 + "\n\n", 'dim')

        # ── 基础数据 ──
        w("📊  当日分析数据\n", 'h2')
        w("─" * 50 + "\n", 'dim')
        w("  · 总分析数：{}  ·  ✅ 成功 {}  ·  ❌ 失败 {}\n".format(
            report['total'], report['ok'], report['fail']))
        w("  · ⭐ 加星：{} 只\n\n".format(report['stars']))

        # ── 主线分析 ──
        if report['top_concepts']:
            w("🎯  强势主线（按提及次数）\n", 'h2')
            w("─" * 50 + "\n", 'dim')
            for i, (concept, cnt) in enumerate(report['top_concepts'][:10], 1):
                tag = 'hot' if i <= 3 else ('cool' if i <= 6 else 'dim')
                w("  {:>2}.  {:<14s}".format(i, concept), tag)
                w("  {:>3} 次提及\n".format(cnt), 'dim')
            w("\n")

        # ── 联动热度 ──
        if report['top_linked']:
            w("🔗  联动热点股票（被提及最多）\n", 'h2')
            w("─" * 50 + "\n", 'dim')
            # 🛡️ v9.4：先本地反查，缺失的批量调东财兜底拉名字
            from ...core import api_client
            codes = [str(c).zfill(6) for c, _ in report['top_linked'][:10]]
            name_lookup = api_client.fetch_stock_names(codes)
            for i, (code, cnt) in enumerate(report['top_linked'][:10], 1):
                code_str = str(code).zfill(6)
                name = name_lookup.get(code_str, "")
                if name:
                    w("  {:>2}.  ".format(i), 'dim')
                    w("{}".format(name), 'h2')
                    w(" ({})".format(code_str), 'dim')
                else:
                    w("  {:>2}.  {}".format(i, code_str), 'dim')
                w("    被提及 {} 次\n".format(cnt), 'dim')
            w("\n")

        # ── 明星股 ──
        if report['star_records']:
            w("⭐  今日加星股票\n", 'h2')
            w("─" * 50 + "\n", 'dim')
            for r in report['star_records']:
                w("  ⭐ {} ({})".format(r['name'], r['code']), 'star')
                if r.get('note'):
                    w("  ·  📝 {}".format(r['note']), 'dim')
                w("\n")
            w("\n")

        # ── 次日表现 ──
        nd = report.get('next_day_summary')
        if nd:
            w("📈  次日表现复盘\n", 'h2')
            w("─" * 50 + "\n", 'dim')
            rate_tag = 'green' if nd['win_rate'] >= 0.5 else 'red'
            w("  · 已追踪：{} 只  ·  胜率 ".format(nd['count']))
            w("{:.0%}".format(nd['win_rate']), rate_tag)
            w("  ·  平均 ")
            avg_tag = 'green' if nd['avg_pct'] > 0 else 'red'
            w("{:+.2f}%\n\n".format(nd['avg_pct']), avg_tag)

            w("  🏆 次日最强（前5）\n", 'green')
            for x in nd['best']:
                w("    · {:<8s}({})".format(x['name'], x['code']))
                w("  {:+.2f}%\n".format(x['pct']), 'green')
            w("\n  📉 次日最弱（前5）\n", 'red')
            for x in nd['worst']:
                w("    · {:<8s}({})".format(x['name'], x['code']))
                w("  {:+.2f}%\n".format(x['pct']), 'red')
            w("\n")
        else:
            w("📈  次日表现复盘\n", 'h2')
            w("─" * 50 + "\n", 'dim')
            w("  · 暂无次日表现数据\n", 'dim')
            w("  · 切到「🌐 次日追踪」Tab 抓取这一天的次日行情\n\n", 'dim')

        w("━" * 50 + "\n", 'dim')
        w("提示：复盘日报基于本地历史数据，不调用任何 AI 接口，秒速生成\n", 'dim')

        T.config(state='disabled')
        # 🆕 v9.9.6：日报里所有 6 位代码渲染成蓝字下划线 → 点击推送同花顺
        try:
            from ...widgets import attach_code_links
            attach_code_links(T, self.app, scope='main')
        except Exception:
            import traceback; traceback.print_exc()
