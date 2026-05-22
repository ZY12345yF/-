"""
🎯 复盘中心 Tab
- 📋 复盘日报：当日盘面汇总
- 📁 个股档案：选股查档
- 🔥 热点演化：概念时间线
- 🔍 相似日匹配：找类似行情
- 🌐 次日表现追踪：批量抓取昨日记录的次日表现
"""
import tkinter as tk
from tkinter import ttk

from .base import BaseTab
from .replay.daily import DailyReportMixin
from .replay.profile import StockProfileMixin
from .replay.trend import TrendTimelineMixin
from .replay.similar import SimilarDaysMixin
from .replay.track import NextDayTrackMixin


class ReplayTab(BaseTab, DailyReportMixin, StockProfileMixin,
                TrendTimelineMixin, SimilarDaysMixin, NextDayTrackMixin):
    title = "复盘中心"

    def build(self, parent):
        C = self.C
        body = tk.Frame(parent, bg=C['bg'])
        body.pack(fill='both', expand=True, padx=12, pady=10)

        # 顶部标题
        hr = tk.Frame(body, bg=C['bg']); hr.pack(fill='x', pady=(0, 8))
        tk.Label(hr, text="🎯 复盘中心",
                 font=('微软雅黑', 13, 'bold'),
                 bg=C['bg'], fg=C['text']).pack(side='left')
        tk.Label(hr, text="  ·  复盘工具的灵魂：让历史数据为决策服务",
                 font=('微软雅黑', 9), bg=C['bg'], fg=C['dim']).pack(side='left')

        # 嵌套 Notebook
        sub_style = ttk.Style()
        sub_nb = ttk.Notebook(body, style='App.TNotebook')
        sub_nb.pack(fill='both', expand=True)

        # 5 个子 Tab
        f_daily   = tk.Frame(sub_nb, bg=C['bg'])
        f_profile = tk.Frame(sub_nb, bg=C['bg'])
        f_trend   = tk.Frame(sub_nb, bg=C['bg'])
        f_similar = tk.Frame(sub_nb, bg=C['bg'])
        f_track   = tk.Frame(sub_nb, bg=C['bg'])

        sub_nb.add(f_daily,   text="  📋 复盘日报  ")
        sub_nb.add(f_profile, text="  📁 个股档案  ")
        sub_nb.add(f_trend,   text="  🔥 热点演化  ")
        sub_nb.add(f_similar, text="  🔍 相似日匹配  ")
        sub_nb.add(f_track,   text="  🌐 次日追踪  ")

        self._build_daily(f_daily)
        self._build_profile(f_profile)
        self._build_trend(f_trend)
        self._build_similar(f_similar)
        self._build_track(f_track)
