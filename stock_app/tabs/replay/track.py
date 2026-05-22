"""
🌐 次日追踪 Mixin
子Tab 5: 批量抓取昨日记录的次日表现
"""
import threading
import tkinter as tk
from tkinter import ttk, messagebox

from ...widgets import styled_btn
from ...core import replay, history as hist_mod
from ...bus import bus, Events, state


class NextDayTrackMixin:
    """次日表现追踪 —— 批量抓取昨日记录的次日表现"""

    def _build_track(self, parent):
        C = self.C
        ctrl = tk.Frame(parent, bg=C['bg']); ctrl.pack(fill='x', pady=(8, 6))
        tk.Label(ctrl, text="目标日期", font=('微软雅黑', 9),
                 bg=C['bg'], fg=C['dim']).pack(side='left', padx=(0, 4))
        self._track_date = tk.StringVar()
        self._track_combo = ttk.Combobox(ctrl, textvariable=self._track_date,
                                           state='readonly', width=14,
                                           font=('微软雅黑', 9))
        self._track_combo.pack(side='left', padx=(0, 8))
        styled_btn(ctrl, "🌐 抓取该日所有股票的当前行情", C['purple'],
                   self._track_next_day).pack(side='left', padx=4)
        styled_btn(ctrl, "🔄 刷新", C['idle'],
                   self._refresh_track_dates).pack(side='right')

        info = tk.Frame(parent, bg=C['bg']); info.pack(fill='x', pady=(0, 6))
        tk.Label(info,
                 text="💡 使用场景：\n"
                 "   · 昨天分析了一批股票，今天盘后点这个按钮，会自动抓取所有股票的「次日表现」并写回历史记录。\n"
                 "   · 用于验证 AI 分析的准确度，构建胜率统计。\n"
                 "   · 注意：抓取的是当前实时价格，所以应在【目标日期的下一个交易日盘后】调用。",
                 font=('微软雅黑', 9), bg=C['bg'], fg=C['dim'],
                 justify='left').pack(anchor='w', padx=8)

        self._track_text = tk.Text(parent, font=('Consolas', 9), wrap='word',
                                    bg=C['card'], fg=C['text'],
                                    relief='flat', padx=10, pady=8,
                                    state='disabled', cursor='arrow')
        vsb = ttk.Scrollbar(parent, orient='vertical',
                             command=self._track_text.yview)
        self._track_text.configure(yscrollcommand=vsb.set)
        self._track_text.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')

        for tag, color in [
            ('h1', C['accent']), ('green', C['green']),
            ('red', C['red']), ('dim', C['dim']),
            ('yellow', C['yellow']),
        ]:
            self._track_text.tag_config(tag, foreground=color)

        self._refresh_track_dates()

    def _refresh_track_dates(self):
        dates = hist_mod.list_history_dates()
        display = [d[:4]+'-'+d[4:6]+'-'+d[6:] for d in dates]
        self._track_combo['values'] = display
        if dates and not self._track_date.get():
            self._track_combo.current(0)

    def _track_next_day(self):
        d = self._track_date.get().replace('-', '')
        if not d:
            messagebox.showinfo("提示", "请选择日期")
            return
        if not messagebox.askyesno("确认",
                "将抓取「{}」当日全部记录股票的当前实时价格，作为次日表现写回历史。\n\n"
                "确认继续？".format(self._track_date.get())):
            return

        T = self._track_text
        T.config(state='normal')
        T.delete('1.0', 'end')
        T.insert('end', "🌐 开始批量抓取行情...\n\n", 'h1')
        T.config(state='disabled')

        def _do():
            def on_progress(i, total, name):
                def _upd():
                    T.config(state='normal')
                    # 删除最后一行进度
                    txt = T.get('1.0', 'end-1c')
                    last_nl = txt.rfind("\n📊")
                    if last_nl != -1:
                        T.delete("1.0+{}c".format(last_nl), 'end')
                    T.insert('end', "\n📊 进度: {}/{}  {}".format(i, total, name), 'yellow')
                    T.see('end')
                    T.config(state='disabled')
                state.ui_queue.put(_upd)

            result = replay.batch_update_next_day(d, None, on_progress=on_progress)

            def _done():
                T.config(state='normal')
                T.insert('end', "\n\n" + "━"*50 + "\n", 'dim')
                T.insert('end', "✅ 抓取完成\n\n", 'green')
                T.insert('end', "  · 更新: {} 条\n".format(result['updated']), 'green')
                T.insert('end', "  · 跳过(已有数据): {} 条\n".format(result['skipped']), 'dim')
                T.insert('end', "  · 失败: {} 条\n".format(result['failed']), 'red')
                T.insert('end', "\n💡 切回「📋 复盘日报」可看到次日表现统计\n", 'dim')
                T.config(state='disabled')
                bus.emit(Events.HISTORY_UPDATED)
            state.ui_queue.put(_done)

        threading.Thread(target=_do, daemon=True).start()
