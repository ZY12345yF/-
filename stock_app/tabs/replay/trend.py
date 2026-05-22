"""
🔥 热点演化 Mixin
子Tab 3: 概念时间线
"""
import tkinter as tk
from tkinter import ttk

from ...widgets import styled_btn, styled_entry
from ...core import replay
from ...bus import bus, Events, state


class TrendTimelineMixin:
    """热点演化 —— 概念时间线"""

    def _build_trend(self, parent):
        C = self.C
        ctrl = tk.Frame(parent, bg=C['bg']); ctrl.pack(fill='x', pady=(8, 6))
        tk.Label(ctrl, text="概念关键词", font=('微软雅黑', 9),
                 bg=C['bg'], fg=C['dim']).pack(side='left', padx=(0, 4))
        self._trend_kw = tk.StringVar(value="算电协同")
        e = styled_entry(ctrl, self._trend_kw, 18)
        e.pack(side='left', ipady=3)
        e.bind('<Return>', lambda ev: self._show_trend())
        styled_btn(ctrl, "📈 生成时间线", C['accent'],
                   self._show_trend).pack(side='left', padx=4)
        tk.Label(ctrl, text="  💡 如：算电协同、AI算力、玻璃基板",
                 font=('微软雅黑', 8), bg=C['bg'], fg=C['dim']).pack(side='left', padx=8)

        # 时间线显示
        self._trend_text = tk.Text(parent, font=('微软雅黑', 10), wrap='word',
                                    bg=C['card'], fg=C['text'],
                                    relief='flat', padx=14, pady=10,
                                    state='disabled', cursor='arrow')
        vsb = ttk.Scrollbar(parent, orient='vertical',
                             command=self._trend_text.yview)
        self._trend_text.configure(yscrollcommand=vsb.set)
        self._trend_text.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')

        for tag, color in [
            ('h1', C['accent']), ('h2', C['yellow']),
            ('stage_hot', C['red']), ('stage_cool', C['purple']),
            ('stage_mid', C['yellow']), ('stage_dim', C['dim']),
            ('dim', C['dim']),
        ]:
            self._trend_text.tag_config(tag, foreground=color)
        self._trend_text.tag_config('h1bold',
            font=('微软雅黑', 13, 'bold'), foreground=C['accent'])

    def _show_trend(self):
        kw = self._trend_kw.get().strip()
        if not kw:
            return
        T = self._trend_text
        T.config(state='normal')
        T.delete('1.0', 'end')

        def w(text, tag=None):
            if tag: T.insert('end', text, tag)
            else:   T.insert('end', text)

        timeline = replay.build_concept_timeline(kw, days=180)
        w("🔥  「{}」演化时间线\n".format(kw), 'h1bold')
        w("━" * 50 + "\n\n", 'dim')

        if not timeline:
            w("  本地历史记录中未找到该关键词\n", 'dim')
            T.config(state='disabled')
            return

        # 阶段统计
        max_count = max(x["mention_count"] for x in timeline)
        w("📊  共找到 {} 个交易日提及，峰值 {} 只/天\n\n".format(
            len(timeline), max_count), 'h2')

        # 时间线
        for i, node in enumerate(timeline):
            stage = node["stage"]
            # 颜色判定
            if "爆发" in stage or "高潮" in stage:
                stage_tag = 'stage_hot'
            elif "加速" in stage or "延续" in stage:
                stage_tag = 'stage_mid'
            elif "退潮" in stage or "衰退" in stage:
                stage_tag = 'stage_dim'
            else:
                stage_tag = 'stage_cool'

            # 柱状图（用 ▇ 表示热度）
            bar_len = int(node["mention_count"] / max_count * 30)
            bar = "▇" * bar_len

            w("  {}  ".format(node["date_display"]))
            w(stage + "  ", stage_tag)
            w(bar, 'h2')
            w("  {} 只\n".format(node["mention_count"]))

            # 列出当日股票（前5只）
            stocks_str = "、".join(
                "{}({})".format(s['name'], s['code'])
                for s in node["stocks"][:5])
            if len(node["stocks"]) > 5:
                stocks_str += "  +{}".format(len(node["stocks"]) - 5)
            w("      {}\n".format(stocks_str), 'dim')
            w("\n")

        # 判断当前阶段
        if timeline:
            cur_stage = timeline[-1]["stage"]
            w("━" * 50 + "\n", 'dim')
            w("📍 当前阶段判断：", 'h2')
            w(cur_stage + "\n", 'stage_hot' if "高潮" in cur_stage else 'stage_mid')

        T.config(state='disabled')
        # 🆕 v9.9.6：时间线里的股票代码加蓝字下划线 → 推送同花顺
        try:
            from ...widgets import attach_code_links
            attach_code_links(T, self.app, scope='main')
        except Exception:
            import traceback; traceback.print_exc()
