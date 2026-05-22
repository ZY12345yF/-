"""
📁 个股档案 Mixin
子Tab 2: 选股查档
"""
import re
import threading
import tkinter as tk
from tkinter import ttk, messagebox

from ...widgets import styled_btn, styled_entry
from ...core import replay
from ...bus import bus, Events, state


class StockProfileMixin:
    """个股档案 —— 选股查档"""

    def _build_profile(self, parent):
        C = self.C
        ctrl = tk.Frame(parent, bg=C['bg']); ctrl.pack(fill='x', pady=(8, 6))
        tk.Label(ctrl, text="股票代码", font=('微软雅黑', 9),
                 bg=C['bg'], fg=C['dim']).pack(side='left', padx=(0, 4))
        self._prof_code_var = tk.StringVar()
        e = styled_entry(ctrl, self._prof_code_var, 12)
        e.pack(side='left', ipady=3)
        e.bind('<Return>', lambda ev: self._show_profile())
        styled_btn(ctrl, "🔍 查询档案", C['accent'],
                   self._show_profile).pack(side='left', padx=4)

        tk.Label(ctrl, text="  💡 输入6位代码（如600519）",
                 font=('微软雅黑', 8), bg=C['bg'], fg=C['dim']).pack(side='left', padx=8)

        self._prof_text = tk.Text(parent, font=('微软雅黑', 10), wrap='word',
                                   bg=C['card'], fg=C['text'],
                                   relief='flat', padx=14, pady=10,
                                   state='disabled', cursor='arrow')
        vsb = ttk.Scrollbar(parent, orient='vertical',
                             command=self._prof_text.yview)
        self._prof_text.configure(yscrollcommand=vsb.set)
        self._prof_text.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')

        for tag, color in [
            ('h1', C['accent']), ('h2', C['yellow']),
            ('green', C['green']), ('red', C['red']),
            ('dim', C['dim']), ('star', C['star']),
        ]:
            self._prof_text.tag_config(tag, foreground=color)
        self._prof_text.tag_config('bold', font=('微软雅黑', 10, 'bold'))
        self._prof_text.tag_config('h1bold',
            font=('微软雅黑', 13, 'bold'), foreground=C['accent'])

    def _show_profile(self):
        code = self._prof_code_var.get().strip()
        if not code:
            messagebox.showinfo("提示", "请输入股票代码")
            return
        code = re.sub(r'\D', '', code).zfill(6)[:6]

        T = self._prof_text
        T.config(state='normal')
        T.delete('1.0', 'end')
        T.insert('end', "📁 查询中...请稍候\n")
        T.config(state='disabled')

        def _do():
            profile = replay.build_stock_profile(code)
            def _render():
                T.config(state='normal')
                T.delete('1.0', 'end')

                def w(text, tag=None):
                    if tag: T.insert('end', text, tag)
                    else:   T.insert('end', text)

                # 标题
                name = profile.get("name", "") or "未知"
                w("📁  {}（{}）档案\n".format(name, code), 'h1bold')
                w("━" * 50 + "\n", 'dim')

                if profile["total_analyses"] == 0:
                    w("\n  本地历史中未找到该股票的分析记录\n", 'dim')
                    w("  请先在「单股搜索」或「批量分析」中分析该股票\n", 'dim')
                    T.config(state='disabled')
                    return

                # 实时行情
                from ...core import api_client
                try:
                    realtime = api_client.fetch_change_pct([code])
                    if realtime and code in realtime:
                        info = realtime[code]
                        w("\n📊 当前行情\n", 'h2')
                        w("─" * 50 + "\n", 'dim')
                        chg = info["change_pct"]
                        chg_tag = 'green' if chg > 0 else ('red' if chg < 0 else 'dim')
                        arrow = "▲" if chg > 0 else ("▼" if chg < 0 else "─")
                        w("  价格: {}".format(info["price"]))
                        w("    {} {:+.2f}%\n".format(arrow, chg), chg_tag)
                        w("  时间: {}\n".format(info["time"]), 'dim')
                except Exception:
                    pass

                # 历次分析
                w("\n📅 历次分析 ({} 次)\n".format(profile["total_analyses"]), 'h2')
                w("─" * 50 + "\n", 'dim')
                for r in profile["records"]:
                    d = r["date"]
                    date_str = "{}-{}-{}".format(d[:4], d[4:6], d[6:])
                    star = "⭐" if r.get("starred") else "  "
                    ok   = "✅" if r.get("success") else "❌"
                    w("  {}  {} {}  {} {}".format(
                        star, ok, date_str, r.get("time", ""),
                        replay.extract_main_logic(r.get("content", ""))[:50]
                    ), None)
                    # 次日表现
                    nd = r.get("next_day")
                    if nd and nd.get("change_pct") is not None:
                        pct = nd["change_pct"]
                        pct_tag = 'green' if pct > 0 else 'red'
                        w("\n      → 次日 ", 'dim')
                        w("{:+.2f}%".format(pct), pct_tag)
                        w("\n")
                    else:
                        w("\n")
                    if r.get("note"):
                        w("      📝 {}\n".format(r["note"]), 'star')
                w("\n")

                # 次日胜率统计
                stats = profile["next_day_stats"]
                if stats["count"] > 0:
                    w("🎯 历次涨停后次日表现\n", 'h2')
                    w("─" * 50 + "\n", 'dim')
                    win_tag = 'green' if stats["win_rate"] >= 0.5 else 'red'
                    w("  胜率: ")
                    w("{:.0%} ".format(stats["win_rate"]), win_tag)
                    w("({} 胜 / {} 总)".format(stats["win"], stats["count"]))
                    avg_tag = 'green' if stats["avg_pct"] > 0 else 'red'
                    w("    平均涨幅: ")
                    w("{:+.2f}%\n\n".format(stats["avg_pct"]), avg_tag)

                # 反复出现的逻辑
                if profile["logic_counter"]:
                    w("🔁 反复出现的逻辑/概念\n", 'h2')
                    w("─" * 50 + "\n", 'dim')
                    for concept, cnt in profile["logic_counter"]:
                        w("  · {:<14s}".format(concept))
                        w("  出现 {} 次\n".format(cnt), 'dim')
                    w("\n")

                # 经常联动
                if profile["linked_stocks"]:
                    w("🔗 经常联动的股票\n", 'h2')
                    w("─" * 50 + "\n", 'dim')
                    for code2, cnt in profile["linked_stocks"]:
                        w("  · {}  ".format(code2))
                        w("  共同出现 {} 次\n".format(cnt), 'dim')

                T.config(state='disabled')
                # 🆕 v9.9.6：档案里所有 6 位代码渲染成蓝字下划线 → 推送同花顺
                try:
                    from ...widgets import attach_code_links
                    attach_code_links(T, self.app, main_code=code, scope='main')
                except Exception:
                    import traceback; traceback.print_exc()
            state.ui_queue.put(_render)

        threading.Thread(target=_do, daemon=True).start()
