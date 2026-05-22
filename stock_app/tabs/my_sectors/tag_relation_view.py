"""
标签关联度 - UI 构建 Mixin（_build_tag_relation_view 等视图方法）
v9.9.8：从 tag_relation.py 拆出
"""
import tkinter as tk
from tkinter import ttk

# matplotlib（用于关联度图表）
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
try:
    plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Arial Unicode MS']
    plt.rcParams['axes.unicode_minus'] = False
except Exception:
    pass

from ...widgets import (
    make_card, styled_btn, styled_entry,
    load_col_widths, save_col_widths,
)
from ...core import config as cfg_mod


class TagRelationViewMixin:
    """_build_tag_relation_view / _toggle_bulk_api_panel 等 UI 构建方法"""

    def _build_tag_relation_view(self):
        C = self.C
        v = tk.Frame(self._right_container, bg=C['bg'])
        v.pack(fill='both', expand=True)

        # ── 顶部标题 + 顶部按钮 ──
        hr = tk.Frame(v, bg=C['bg']); hr.pack(fill='x', pady=(0, 6))
        # 左侧装饰条 + 标题
        title_box = tk.Frame(hr, bg=C['bg']); title_box.pack(side='left')
        tk.Frame(title_box, bg=C['accent'], width=4).pack(side='left', fill='y', padx=(0, 8))
        tk.Label(title_box, text="标签关联度分析",
                 font=('微软雅黑', 13, 'bold'),
                 bg=C['bg'], fg=C['text']).pack(side='left', pady=2)
        styled_btn(hr, "\U0001f3f7️ 管理标签", C['purple'],
                   self._tag_open_manager).pack(side='right', padx=(4, 0))
        styled_btn(hr, "\U0001f4dd 聚类提示词", C['accent'],
                   self._edit_bulk_prompt).pack(side='right', padx=(4, 0))
        styled_btn(hr, "\U0001f504 重新扫描", C['idle'],
                   self._tag_rescan).pack(side='right')

        # ── 扫描控制行（含回溯天数）──
        ctrl = tk.Frame(v, bg=C['bg']); ctrl.pack(fill='x', pady=(0, 4))
        tk.Label(ctrl, text="目标标签", font=('微软雅黑', 9),
                 bg=C['bg'], fg=C['dim']).pack(side='left', padx=(0, 4))
        self._tag_var = tk.StringVar()
        self._tag_combo = ttk.Combobox(ctrl, textvariable=self._tag_var,
                                        state='readonly', width=22,
                                        font=('微软雅黑', 9))
        self._tag_combo.pack(side='left', padx=(0, 8))
        self._tag_combo.bind('<<ComboboxSelected>>',
                              lambda e: self._tag_show_relations())

        # 🆕 回溯天数（默认 7）
        tk.Label(ctrl, text="回溯天数", font=('微软雅黑', 9),
                 bg=C['bg'], fg=C['dim']).pack(side='left', padx=(0, 4))
        self._tag_days = tk.StringVar(value="7")
        days_combo = ttk.Combobox(ctrl, textvariable=self._tag_days,
                                  values=["1", "3", "7", "14", "30", "全部"],
                                  state='readonly', width=6,
                                  font=('微软雅黑', 9))
        days_combo.pack(side='left', padx=(0, 8))
        days_combo.bind('<<ComboboxSelected>>', lambda e: self._tag_rescan())

        tk.Label(ctrl, text="最小频次", font=('微软雅黑', 9),
                 bg=C['bg'], fg=C['dim']).pack(side='left', padx=(0, 4))
        self._tag_min_freq = tk.StringVar(value="1")
        styled_entry(ctrl, self._tag_min_freq, 3).pack(side='left', ipady=3)

        self._tag_stat = tk.StringVar(value="点击「重新扫描」开始")
        tk.Label(v, textvariable=self._tag_stat,
                 font=('微软雅黑', 9), bg=C['bg'], fg=C['yellow']).pack(anchor='w', pady=(0, 4))

        # ── 🆕 聚类专属 API 配置区（默认折叠，腾出主区域空间）──
        self._bulk_api_open = tk.BooleanVar(value=False)
        tog_row = tk.Frame(v, bg=C['bg']); tog_row.pack(fill='x', pady=(0, 2))
        self._bulk_api_btn = tk.Button(tog_row,
            text="▶ \U0001f916 聚类专属 API 配置（点击展开）",
            font=('微软雅黑', 9), bg=C['bg'], fg=C['dim'],
            relief='flat', anchor='w', cursor='hand2',
            command=self._toggle_bulk_api_panel)
        self._bulk_api_btn.pack(fill='x')

        self._bulk_api_card = make_card(v, "", pady_top=0)
        # 默认收起
        self._bulk_api_card.pack_forget()

        r1 = tk.Frame(self._bulk_api_card, bg=C['panel']); r1.pack(fill='x', pady=2)
        tk.Label(r1, text="API URL", font=('微软雅黑', 8), bg=C['panel'], fg=C['dim'], width=10, anchor='w').pack(side='left')
        self._bulk_url = tk.StringVar(value=self.app.cfg.get("api_url", ""))
        styled_entry(r1, self._bulk_url).pack(side='left', fill='x', expand=True, ipady=2)

        r2 = tk.Frame(self._bulk_api_card, bg=C['panel']); r2.pack(fill='x', pady=2)
        tk.Label(r2, text="API Key", font=('微软雅黑', 8), bg=C['panel'], fg=C['dim'], width=10, anchor='w').pack(side='left')
        self._bulk_key = tk.StringVar(value=self.app.cfg.get("api_keys", [""])[0] if self.app.cfg.get("api_keys") else "")
        styled_entry(r2, self._bulk_key).pack(side='left', fill='x', expand=True, ipady=2)

        r3 = tk.Frame(self._bulk_api_card, bg=C['panel']); r3.pack(fill='x', pady=2)
        tk.Label(r3, text="Model", font=('微软雅黑', 8), bg=C['panel'], fg=C['dim'], width=10, anchor='w').pack(side='left')
        cur_id = self.app.cfg.get("model", "")
        cur_disp = cfg_mod.model_id_to_display_name(cur_id)
        self._bulk_model_var = tk.StringVar(value=cur_disp)
        model_combo = ttk.Combobox(r3, textvariable=self._bulk_model_var,
                                    values=cfg_mod.MODEL_LIST, font=('微软雅黑', 8), state='readonly')
        model_combo.pack(side='left', fill='x', expand=True, ipady=2)

        btn_r = tk.Frame(self._bulk_api_card, bg=C['panel']); btn_r.pack(fill='x', pady=(6, 0))
        styled_btn(btn_r, "\U0001f30b 火山方舟", C['red'],
                   self._switch_bulk_to_volcano, pady=2).pack(side='left', padx=(0,4))
        styled_btn(btn_r, "\U0001f535 百度千帆", C['accent'],
                   self._switch_bulk_to_qianfan, pady=2).pack(side='left', padx=(0,4))
        styled_btn(btn_r, "\U0001f40b DeepSeek", '#4d6bfe',
                   self._switch_bulk_to_deepseek, pady=2).pack(side='left', padx=(0,4))
        styled_btn(btn_r, "\U0001f9ea 智谱GLM", '#3fc7ff',
                   self._switch_bulk_to_zhipu, pady=2).pack(side='left')

        # ── 聚类执行按钮 ──
        exec_row = tk.Frame(v, bg=C['bg']); exec_row.pack(fill='x', pady=(6, 4))
        styled_btn(exec_row, "\U0001f916 AI 一键聚类（使用专属配置）", C['purple'],
                   self._tag_bulk_analyze, pady=6).pack(fill='x')

        # ── 双栏：左表 / 右图表+详情 ──
        pw = tk.PanedWindow(v, bg=C['bg'], sashwidth=5,
                             sashrelief='flat', orient='horizontal')
        pw.pack(fill='both', expand=True)
        lf = tk.Frame(pw, bg=C['bg'])
        rf = tk.Frame(pw, bg=C['bg'])
        pw.add(lf, minsize=340)
        pw.add(rf, minsize=460)

        # 左表头部加图例
        legend = tk.Frame(lf, bg=C['bg']); legend.pack(fill='x', pady=(0, 2))
        tk.Label(legend, text="\U0001f525 强 ≥0.4", font=('微软雅黑', 8),
                 bg=C['bg'], fg=C['red']).pack(side='left', padx=(2, 8))
        tk.Label(legend, text="⭐ 中 ≥0.2", font=('微软雅黑', 8),
                 bg=C['bg'], fg=C['yellow']).pack(side='left', padx=(0, 8))
        tk.Label(legend, text="\U0001f4a4 弱", font=('微软雅黑', 8),
                 bg=C['bg'], fg=C['dim']).pack(side='left')
        tk.Label(legend, text="(双击关联标签 → 切换目标)", font=('微软雅黑', 8),
                 bg=C['bg'], fg=C['dim']).pack(side='right')

        cols = ('tag', 'score', 'support', 'self', 'other')
        col_widths = load_col_widths('tag_relation')
        defaults = {'tag': 130, 'score': 70, 'support': 70, 'self': 60, 'other': 60}
        self._tag_tree = ttk.Treeview(lf, columns=cols, show='headings', height=18)
        for col, txt in [('tag','关联标签'),('score','关联度'),
                           ('support','共现次数'),('self','本标签'),('other','对方')]:
            self._tag_tree.heading(col, text=txt)
            self._tag_tree.column(col,
                                   width=col_widths.get(col, defaults[col]),
                                   minwidth=40,
                                   anchor='center' if col != 'tag' else 'w',
                                   stretch=True)
        tvsb = ttk.Scrollbar(lf, orient='vertical', command=self._tag_tree.yview)
        self._tag_tree.configure(yscrollcommand=tvsb.set)
        self._tag_tree.pack(side='left', fill='both', expand=True)
        tvsb.pack(side='right', fill='y')

        def _save_w(*_):
            save_col_widths('tag_relation',
                {c: self._tag_tree.column(c, 'width') for c in cols})
        self._tag_tree.bind('<ButtonRelease-1>', _save_w)

        self._tag_tree.tag_configure('high', foreground=C['red'])
        self._tag_tree.tag_configure('mid',  foreground=C['yellow'])
        self._tag_tree.tag_configure('low',  foreground=C['dim'])
        self._tag_tree.bind('<<TreeviewSelect>>', lambda e: self._tag_show_rel_detail())
        # 🆕 B2 双击：切换该标签为新的目标
        self._tag_tree.bind('<Double-Button-1>', lambda e: self._tag_jump_to_selected())

        # 右：详情 + 图表（v9.4：把详情放第一个，让"个股清单"首屏可见）
        self._tag_sub_nb = ttk.Notebook(rf, style='App.TNotebook')
        self._tag_sub_nb.pack(fill='both', expand=True)

        # 详情 Tab 排第一个，默认显示，用户立刻看到本标签下的个股
        f_detail = tk.Frame(self._tag_sub_nb, bg=C['bg'])
        self._tag_sub_nb.add(f_detail, text="  \U0001f4dd 个股 + 详情 + AI推理  ")

        info_bar = tk.Frame(f_detail, bg=C['bg'])
        info_bar.pack(fill='x', pady=(6, 4))
        styled_btn(info_bar, "\U0001f916 推理这对关联", C['purple'],
                   self._tag_ai_pair).pack(side='left', padx=(0, 4))
        styled_btn(info_bar, "\U0001f5d1 清除缓存", C['idle'],
                   self._tag_clear_pair_cache).pack(side='left')
        self._tag_ai_status = tk.StringVar(value="")
        tk.Label(info_bar, textvariable=self._tag_ai_status,
                 font=('微软雅黑', 9), bg=C['bg'], fg=C['yellow']).pack(side='left', padx=8)

        self._tag_detail = tk.Text(f_detail, font=('微软雅黑', 10), wrap='word',
                                    bg=C['card'], fg=C['text'],
                                    relief='flat', padx=10, pady=8,
                                    state='disabled', cursor='arrow')
        tdvsb = ttk.Scrollbar(f_detail, orient='vertical', command=self._tag_detail.yview)
        self._tag_detail.configure(yscrollcommand=tdvsb.set)
        self._tag_detail.pack(side='left', fill='both', expand=True)
        tdvsb.pack(side='right', fill='y')
        for tag, color in [('h1', C['accent']), ('h2', C['yellow']),
                            ('green', C['green']), ('red', C['red']),
                            ('dim', C['dim']), ('purple', C['purple'])]:
            self._tag_detail.tag_config(tag, foreground=color)
        self._tag_detail.tag_config('h1bold',
            font=('微软雅黑', 12, 'bold'), foreground=C['accent'])
        self._tag_detail.tag_config('ai',
            background='#2a1d4d', foreground='white')

        # 🆕 v9.5：标签详情区右键 → 看光标附近的股票详情
        self._tag_detail.bind('<Button-3>', self._tag_detail_show_ctx)
        self._tag_detail.bind('<Button-2>', self._tag_detail_show_ctx)
        # 🆕 v9.6：左键联动
        self._tag_detail.bind('<Button-1>', self._tag_detail_left_click_follow, add='+')
        self._tag_detail_ctx = tk.Menu(self._tag_detail, tearoff=0,
            bg=C['panel'], fg=C['text'],
            activebackground=C['acc_dark'], activeforeground='white',
            font=('微软雅黑', 9))
        self._tag_detail_ctx.add_command(label="\U0001f50e  查看此股详情",
            command=self._tag_detail_show_stock_popup)

        # 关联度图表 Tab（v9.4：调整为第二个，详情优先）
        f_chart = tk.Frame(self._tag_sub_nb, bg=C['bg'])
        self._tag_sub_nb.add(f_chart, text="  \U0001f4ca 关联度图表  ")
        self._tag_fig = Figure(figsize=(6, 4), dpi=90, facecolor=C['bg'])
        self._tag_ax  = self._tag_fig.add_subplot(111)
        self._tag_canvas = FigureCanvasTkAgg(self._tag_fig, master=f_chart)
        self._tag_canvas.get_tk_widget().pack(fill='both', expand=True, padx=8, pady=8)

    # ── 🆕 聚类专属 API 快捷切换 ──
    def _switch_bulk_to_volcano(self):
        self._bulk_url.set(cfg_mod.PROVIDER_URLS["volcano"])
        self._bulk_model_var.set("🌋 doubao-seed-2-0-pro")

    def _switch_bulk_to_qianfan(self):
        self._bulk_url.set(cfg_mod.PROVIDER_URLS["qianfan"])
        self._bulk_model_var.set("🆓 ERNIE-4.5-Turbo-32K")

    def _switch_bulk_to_deepseek(self):
        self._bulk_url.set(cfg_mod.PROVIDER_URLS["deepseek"])
        self._bulk_model_var.set("🐋 DeepSeek-V3.2 (官方)")

    def _switch_bulk_to_zhipu(self):
        self._bulk_url.set(cfg_mod.PROVIDER_URLS["zhipu"])
        self._bulk_model_var.set("🧪 GLM-4-Plus")

    # 🆕 A4：折叠/展开 API 配置面板
    def _toggle_bulk_api_panel(self):
        opened = self._bulk_api_open.get()
        if opened:
            self._bulk_api_card.pack_forget()
            self._bulk_api_btn.config(text="▶ \U0001f916 聚类专属 API 配置（点击展开）")
            self._bulk_api_open.set(False)
        else:
            self._bulk_api_card.pack(fill='x', pady=(2, 4),
                                     after=self._bulk_api_btn.master)
            self._bulk_api_btn.config(text="▼ \U0001f916 聚类专属 API 配置（点击折叠）")
            self._bulk_api_open.set(True)
