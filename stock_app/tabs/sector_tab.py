"""
📊 板块分析 Tab（v9.7 重写）
- 主 Tab：[📊 板块分析] + [📡 涨停雷达] 两个子 Tab
- 顶部日期下拉：选「今日（实时）」走 API，选历史日期走快照
- 「刷新」按钮：拉实时 → 预先拉全部板块成份股 → 整体保存为今日快照
- 选历史日期时点刷新 → 弹确认对话框
- 龙头梯队 Text：单击带代码的行通知浮窗（联动模式开启时刷新）

v9.9.8 拆分：Mixin 拆分到 sector/ 目录
- SectorDataMixin   : 数据刷新、快照管理
- SectorDetailMixin : 板块视图构建、详情渲染
- SectorRadarMixin  : 雷达视图构建、事件处理
"""
import tkinter as tk
from tkinter import ttk

from .base import BaseTab
from .sector.sector_data import SectorDataMixin
from .sector.sector_detail import SectorDetailMixin
from .sector.sector_radar import SectorRadarMixin
from ..widgets import make_card, styled_btn
from ..core import (api_client, sector as sector_core,
                     config as cfg_mod,
                     history as hist_mod,
                     sector_snapshot as snap_mod,
                     text_utils)
from ..bus import bus, Events, state
# v9.9.8 Phase 2: 业务逻辑迁到 services/,数据访问迁到 repositories/
from ..services import (
    SectorAnalysisService,
    SectorRefreshService,
    SectorStocksSupplyService,
)
from ..repositories import sector_repo


STATUS_COLORS = {
    "一字板":     "#ff3838",
    "涨停":       "#ff3b3f",
    "炸板":       "#ff9a3c",
    "冲高回落":   "#ffb627",
    "强势":       "#00d68f",
    "上涨":       "#5b8def",
    "下跌":       "#5d6477",
    "跌停":       "#00d9ff",
}


class SectorTab(SectorDataMixin, SectorDetailMixin, SectorRadarMixin, BaseTab):
    title = "板块分析"

    def __init__(self, app):
        super().__init__(app)
        self._sectors = []
        self._cur_sector = None
        self._cur_stocks = []
        self._stocks_by_sector = {}
        self._select_seq = 0
        self._radar_data = []
        self._cur_date_key = None
        self._available_dates = []

    def build(self, parent):
        C = self.C
        body = tk.Frame(parent, bg=C['bg'])
        body.pack(fill='both', expand=True, padx=12, pady=10)

        # 顶部
        hr = tk.Frame(body, bg=C['bg']); hr.pack(fill='x', pady=(0, 8))
        title_box = tk.Frame(hr, bg=C['bg']); title_box.pack(side='left')
        tk.Frame(title_box, bg=C['accent'], width=4).pack(side='left', fill='y', padx=(0, 8))
        tk.Label(title_box, text="板块 & 雷达分析",
                 font=('微软雅黑', 13, 'bold'),
                 bg=C['bg'], fg=C['text']).pack(side='left', pady=2)

        tk.Label(hr, text="  📅 日期", font=('微软雅黑', 9),
                 bg=C['bg'], fg=C['dim']).pack(side='left', padx=(18, 4))
        self._date_var = tk.StringVar(value="今日（实时）")
        self._date_combo = ttk.Combobox(hr, textvariable=self._date_var,
                                         state='readonly', width=18,
                                         font=('微软雅黑', 9))
        self._date_combo.pack(side='left')
        self._date_combo.bind('<<ComboboxSelected>>',
                               lambda e: self._on_date_change())

        self._sector_type = tk.StringVar(value="concept")
        type_frame = tk.Frame(hr, bg=C['bg'])
        type_frame.pack(side='left', padx=(14, 0))
        for val, lbl in [("concept", "💡 概念"), ("industry", "🏭 行业")]:
            tk.Radiobutton(type_frame, text=lbl, variable=self._sector_type,
                           value=val, font=('微软雅黑', 9),
                           bg=C['bg'], fg=C['text'],
                           selectcolor=C['card'], activebackground=C['bg'],
                           command=self._on_type_change).pack(side='left', padx=(0, 6))

        styled_btn(hr, "🔄 刷新（拉实时并保存今日快照）", C['accent'],
                   self._refresh).pack(side='right', padx=(6, 0))
        styled_btn(hr, "🚀 分析当前板块龙头", C['green'],
                   self._analyze_leaders).pack(side='right', padx=(0, 6))

        self._status_var = tk.StringVar(value="未刷新，请点击「刷新」")
        tk.Label(body, textvariable=self._status_var,
                 font=('微软雅黑', 9), bg=C['bg'], fg=C['yellow']).pack(anchor='w', pady=(0, 6))

        self._sub_nb = ttk.Notebook(body, style='App.TNotebook')
        self._sub_nb.pack(fill='both', expand=True)

        self._sector_frame = tk.Frame(self._sub_nb, bg=C['bg'])
        self._sub_nb.add(self._sector_frame, text="  📊 板块分析  ")
        self._build_sector_view(self._sector_frame)

        self._radar_frame = tk.Frame(self._sub_nb, bg=C['bg'])
        self._sub_nb.add(self._radar_frame, text="  📡 涨停雷达  ")
        self._build_radar_view(self._radar_frame)

        self.app.root.after(100, self._auto_load_today_or_latest)
