"""
🔍 相似日匹配 Mixin
子Tab 4: 找类似行情
"""
import tkinter as tk
from tkinter import ttk, messagebox

from ...widgets import styled_btn
from ...core import replay, history as hist_mod
from ...bus import bus, Events, state


class SimilarDaysMixin:
    """相似日匹配 —— 找类似行情"""

    def _build_similar(self, parent):
        C = self.C
        ctrl = tk.Frame(parent, bg=C['bg']); ctrl.pack(fill='x', pady=(8, 6))
        tk.Label(ctrl, text="比较日期", font=('微软雅黑', 9),
                 bg=C['bg'], fg=C['dim']).pack(side='left', padx=(0, 4))
        self._sim_date = tk.StringVar()
        self._sim_combo = ttk.Combobox(ctrl, textvariable=self._sim_date,
                                         state='readonly', width=14,
                                         font=('微软雅黑', 9))
        self._sim_combo.pack(side='left', padx=(0, 8))
        styled_btn(ctrl, "🔍 查找相似日", C['accent'],
                   self._show_similar).pack(side='left', padx=4)
        styled_btn(ctrl, "🔄 刷新", C['idle'],
                   self._refresh_sim_dates).pack(side='right')

        self._sim_text = tk.Text(parent, font=('微软雅黑', 10), wrap='word',
                                  bg=C['card'], fg=C['text'],
                                  relief='flat', padx=14, pady=10,
                                  state='disabled', cursor='arrow')
        vsb = ttk.Scrollbar(parent, orient='vertical',
                             command=self._sim_text.yview)
        self._sim_text.configure(yscrollcommand=vsb.set)
        self._sim_text.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')

        for tag, color in [
            ('h1', C['accent']), ('h2', C['yellow']),
            ('high', C['red']), ('mid', C['yellow']),
            ('low', C['dim']), ('dim', C['dim']),
        ]:
            self._sim_text.tag_config(tag, foreground=color)
        self._sim_text.tag_config('h1bold',
            font=('微软雅黑', 13, 'bold'), foreground=C['accent'])

        self._refresh_sim_dates()

    def _refresh_sim_dates(self):
        dates = hist_mod.list_history_dates()
        display = [d[:4]+'-'+d[4:6]+'-'+d[6:] for d in dates]
        self._sim_combo['values'] = display
        if dates and not self._sim_date.get():
            self._sim_combo.current(0)

    def _show_similar(self):
        d = self._sim_date.get().replace('-', '')
        if not d:
            messagebox.showinfo("提示", "请选择日期")
            return
        T = self._sim_text
        T.config(state='normal')
        T.delete('1.0', 'end')

        def w(text, tag=None):
            if tag: T.insert('end', text, tag)
            else:   T.insert('end', text)

        results = replay.find_similar_days(d, top_n=10)
        w("🔍  与 {} 最相似的历史日\n".format(self._sim_date.get()), 'h1bold')
        w("━" * 50 + "\n\n", 'dim')

        if not results:
            w("  无其他历史日可比较\n", 'dim')
            T.config(state='disabled')
            return

        for i, r in enumerate(results, 1):
            sim = r["similarity"]
            sim_tag = 'high' if sim >= 60 else ('mid' if sim >= 30 else 'low')
            w("  {:>2}.  {}\n".format(i, r["date_display"]), 'h2')
            w("       相似度: ")
            w("{}%".format(sim), sim_tag)
            w("    规模: {} 只\n".format(r["total_count"]))
            w("       主线: " + " · ".join(r["main_concepts"]), 'dim')
            w("\n\n")

        T.config(state='disabled')
