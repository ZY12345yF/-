"""
历史记录 Tab
- 单条/批量/全天 删除
- ⭐ 星标（行高亮）+ 📝 备注（双击编辑）
- 仅显示星标过滤 + 跨日期搜索
- 🔄 重新识别联动标的行情（一键重查腾讯接口）
- 📝 可编辑详情文本（像 txt 一样自由编辑）
- 💾 保存修改回历史记录
- 右键菜单：复制/剪切/粘贴/全选/手动高亮/清除高亮/微信格式/导出HTML/重新识别/撤销
- 手动高亮：选中文字 → 右键 → 5种颜色
- 字号调节
"""
import json
import threading
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

from .base import BaseTab
from ..widgets import make_card, styled_btn, styled_entry, apply_highlight
from ..core import history as hist_mod, api_client, text_utils, reports
from ..bus import bus, Events
# v9.9.8 Phase 2: 业务逻辑迁到 services/,UI 逻辑留在本 Tab
from ..services import (
    BatchRequeryService,
    DailyQuotesExporter,
    StarredExportService,
)

# 拆分出去的 Mixin —— 见 history/ 子目录
from .history.detail_view import DetailViewMixin
from .history.menus import HistoryMenusMixin
from .history.operations import HistoryOperationsMixin
from .history.auto_mode import AutoModeMixin
from .history.import_subtags import ImportSubtagsMixin


MANUAL_HL_TAGS = [
    ("🟡 黄色",  "hl_yellow", "#ffb627", "#05070b"),
    ("🟢 绿色",  "hl_green",  "#00d68f", "#05070b"),
    ("🔵 蓝色",  "hl_blue",   "#5b8def", "#05070b"),
    ("🟣 紫色",  "hl_purple", "#a78bfa", "#05070b"),
    ("🔴 红色",  "hl_red",    "#ff3b3f", "#05070b"),
    ("🟠 橙色",  "hl_orange", "#ff9a3c", "#05070b"),
]


class HistoryTab(BaseTab, DetailViewMixin, HistoryMenusMixin,
                 HistoryOperationsMixin, AutoModeMixin, ImportSubtagsMixin):
    title = "历史记录"

    def __init__(self, app):
        super().__init__(app)
        self._cur_date_key  = None
        self._cur_record_id = None
        self._cur_record_code = None    # 🆕 v9.3：当前记录的股票代码（联动行情主股标识用）
        self._dirty         = False
        self._row_data = {}
        # 自动保存相关
        self._auto_save_id    = None
        self._auto_save_delay = 1500
        self._loading         = False
        # 🔑 内容快照：用于精确判断是否需要保存（不依赖 <<Modified>> 事件）
        # 中文 IME 输入下 <<Modified>> 经常漏触发，靠快照对比最可靠
        self._original_content = ""
        # 自动批量识别模式
        self._auto_mode_on     = False
        self._auto_mode_id     = None       # after() 句柄
        self._auto_mode_minutes = 5         # 默认每 5 分钟一次

    def build(self, parent):
        C = self.C
        body = tk.Frame(parent, bg=C['bg'])
        body.pack(fill='both', expand=True, padx=16, pady=12)

        # ── 顶部 ──────────────────────────────────────────
        hr = tk.Frame(body, bg=C['bg']); hr.pack(fill='x', pady=(0, 8))
        tk.Label(hr, text="📜 历史记录", font=('微软雅黑', 12, 'bold'),
                 bg=C['bg'], fg=C['text']).pack(side='left')
        # 一键批量重识别按钮（最显眼位置）
        styled_btn(hr, "🔄 一键重识别当日全部", C['purple'],
                   self._batch_requery_all).pack(side='left', padx=(20, 0))
        # 🆕 v9.9.8：从 Excel 导入细分标签（G 列），按当前选中日期匹配
        styled_btn(hr, "📥 导入细分标签", C['accent'],
                   self._import_subtags_from_excel).pack(side='left', padx=(8, 0))

        # 自动模式开关
        self._auto_mode_var = tk.BooleanVar(value=False)
        self._auto_chk = tk.Checkbutton(hr, text="🔁 自动模式",
                                          variable=self._auto_mode_var,
                                          font=('微软雅黑', 9, 'bold'),
                                          bg=C['bg'], fg=C['yellow'],
                                          activebackground=C['bg'],
                                          activeforeground=C['yellow'],
                                          selectcolor=C['card'],
                                          command=self._toggle_auto_mode)
        self._auto_chk.pack(side='left', padx=(8, 0))

        tk.Label(hr, text="间隔(分钟)", font=('微软雅黑', 8),
                 bg=C['bg'], fg=C['dim']).pack(side='left', padx=(8, 2))
        self._auto_interval_var = tk.StringVar(value=str(self._auto_mode_minutes))
        styled_entry(hr, self._auto_interval_var, 4).pack(side='left', ipady=2)

        self._auto_status_var = tk.StringVar(value="")
        tk.Label(hr, textvariable=self._auto_status_var,
                 font=('微软雅黑', 8), bg=C['bg'],
                 fg=C['green']).pack(side='left', padx=(8, 0))
        styled_btn(hr, "📈 导出当日行情Excel", C['purple'],
                   self._export_daily_quotes).pack(side='right', padx=(4, 0))
        styled_btn(hr, "📊 导出星标Excel", C['green'],
                   self._export_excel).pack(side='right', padx=(4, 0))
        styled_btn(hr, "📄 导出星标HTML", C['accent'],
                   self._export_html).pack(side='right', padx=(4, 0))

        # ── 搜索/过滤行 ──────────────────────────────────
        sr = tk.Frame(body, bg=C['bg']); sr.pack(fill='x', pady=(0, 8))
        tk.Label(sr, text="日期", font=('微软雅黑', 9),
                 bg=C['bg'], fg=C['dim']).pack(side='left', padx=(0, 4))
        self.date_var = tk.StringVar()
        self.date_combo = ttk.Combobox(sr, textvariable=self.date_var,
                                        state='readonly', width=14,
                                        font=('微软雅黑', 9))
        self.date_combo.pack(side='left', padx=(0, 12))
        self.date_combo.bind('<<ComboboxSelected>>', lambda e: self._load_day())

        tk.Label(sr, text="搜索", font=('微软雅黑', 9),
                 bg=C['bg'], fg=C['dim']).pack(side='left', padx=(0, 4))
        self.kw_var = tk.StringVar()
        kw_e = styled_entry(sr, self.kw_var, 20)
        kw_e.pack(side='left', ipady=3)
        kw_e.bind('<Return>', lambda e: self._search())
        styled_btn(sr, "🔍", C['accent'], self._search).pack(side='left', padx=(2, 0))
        styled_btn(sr, "重置", C['idle'],
                   lambda: [self.kw_var.set(""), self._load_day()]).pack(side='left', padx=(2, 12))
        self.only_star = tk.BooleanVar(value=False)
        tk.Checkbutton(sr, text="⭐ 仅显示星标",
                       variable=self.only_star, font=('微软雅黑', 9),
                       bg=C['bg'], fg=C['text'], selectcolor=C['card'],
                       activebackground=C['bg'],
                       command=self._load_day).pack(side='left')
        styled_btn(sr, "刷新", C['idle'], self._refresh_dates).pack(side='right')

        # ── 双栏布局 ─────────────────────────────────────
        pw = tk.PanedWindow(body, bg=C['bg'], sashwidth=5,
                            sashrelief='flat', orient='horizontal')
        pw.pack(fill='both', expand=True)
        left  = tk.Frame(pw, bg=C['bg'])
        right = tk.Frame(pw, bg=C['bg'])
        pw.add(left,  minsize=360)
        pw.add(right, minsize=440)

        # ── 左侧列表 ─────────────────────────────────────
        cols = ('star','time','name','code','status','note')
        # 加载持久化列宽
        from ..widgets import load_col_widths, save_col_widths
        col_widths = load_col_widths('history')
        defaults = {'star':40,'time':80,'name':100,'code':80,'status':50,'note':110}
        self.tree = ttk.Treeview(left, columns=cols, show='headings', height=20)
        for col, txt, w in [('star','⭐',40),('time','时间',80),('name','名称',100),
                              ('code','代码',80),('status','状态',50),('note','备注',110)]:
            self.tree.heading(col, text=txt)
            self.tree.column(col,
                              width=col_widths.get(col, defaults[col]),
                              minwidth=30,
                              anchor='center' if col!='note' else 'w',
                              stretch=True)
        vsb = ttk.Scrollbar(left, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')
        self.tree.tag_configure('starred', background=C['acc_dark'], foreground='white')
        self.tree.bind('<<TreeviewSelect>>', lambda e: self._show_detail())
        self.tree.bind('<Delete>',           lambda e: self._delete_selected())
        self.tree.bind('<Double-1>',         lambda e: self._edit_note_dialog())

        # 列宽拖动后保存
        def _save_widths(*_):
            widths = {c: self.tree.column(c, 'width') for c in cols}
            save_col_widths('history', widths)
        self.tree.bind('<ButtonRelease-1>', _save_widths, add='+')

        # 右键菜单（在Treeview上）
        self._build_tree_context_menu()

        lb = tk.Frame(left, bg=C['bg']); lb.pack(fill='x', pady=(4, 0))
        styled_btn(lb, "⭐ 星标",    C['yellow'], self._toggle_star).pack(side='left', padx=(0, 3))
        styled_btn(lb, "📝 备注",    C['accent'],  self._edit_note_dialog).pack(side='left', padx=(0, 3))
        styled_btn(lb, "🗑 删除",    C['red'],     self._delete_selected).pack(side='left', padx=(0, 3))
        styled_btn(lb, "🧹 清空当日",C['idle'],   self._clear_day).pack(side='left', padx=(0, 3))
        styled_btn(lb, "🏷️ 标签",   C['purple'], self._edit_tags_dialog).pack(side='left', padx=(0, 3))
        styled_btn(lb, "➕ 加入自选",C['green'],  self._add_to_favorites).pack(side='left')
        tk.Label(left, text="💡 单击=查看  双击=改备注  Del=删除",
                 font=('微软雅黑', 7), bg=C['bg'], fg=C['dim']).pack(anchor='w', pady=(2, 0))

        # ── 右侧工具栏 ──────────────────────────────────
        rh = tk.Frame(right, bg=C['panel'],
                      highlightbackground=C['border'], highlightthickness=1)
        rh.pack(fill='x')
        tk.Label(rh, text="📄 详情（可直接编辑）",
                 font=('微软雅黑', 9, 'bold'),
                 bg=C['panel'], fg=C['accent']).pack(side='left', padx=8, pady=5)

        self._save_btn = tk.Button(rh, text="💾 保存",
                                    font=('微软雅黑', 8), pady=3, padx=6,
                                    bg=C['green'], fg='white', relief='flat',
                                    cursor='hand2', state='disabled',
                                    command=self._save_edit)
        self._save_btn.pack(side='right', padx=4, pady=4)

        # Inline Toast 提示标签（取代弹窗）
        self._toast_var = tk.StringVar(value="")
        self._toast_lbl = tk.Label(rh, textvariable=self._toast_var,
                                    font=('微软雅黑', 9, 'bold'),
                                    bg=C['panel'], fg=C['green'])
        self._toast_lbl.pack(side='right', padx=8, pady=4)

        tk.Button(rh, text="🔄 重新识别行情",
                  font=('微软雅黑', 8), pady=3, padx=6,
                  bg=C['purple'], fg='white', relief='flat', cursor='hand2',
                  command=self._requery_realtime).pack(side='right', padx=(0, 4), pady=4)

        tk.Button(rh, text="✨ 自动高亮",
                  font=('微软雅黑', 8), pady=3, padx=6,
                  bg=C['acc_dark'], fg='white', relief='flat', cursor='hand2',
                  command=lambda: apply_highlight(self.detail, keep_editable=True)).pack(side='right', padx=(0, 4), pady=4)

        # 字号
        tk.Label(rh, text="字", font=('微软雅黑', 8),
                 bg=C['panel'], fg=C['dim']).pack(side='right', padx=(0, 1), pady=4)
        self._fsize = tk.IntVar(value=10)
        tk.Button(rh, text="▲", font=('Arial', 7), width=2,
                  bg=C['border'], fg=C['text'], relief='flat', cursor='hand2',
                  command=self._font_up).pack(side='right', pady=4)
        tk.Label(rh, textvariable=self._fsize, font=('微软雅黑', 8),
                 bg=C['panel'], fg=C['yellow'], width=2).pack(side='right', pady=4)
        tk.Button(rh, text="▼", font=('Arial', 7), width=2,
                  bg=C['border'], fg=C['text'], relief='flat', cursor='hand2',
                  command=self._font_down).pack(side='right', padx=(4, 0), pady=4)

        # ── 右侧可编辑文本框 ──────────────────────────
        txt_frame = tk.Frame(right, bg=C['bg'])
        txt_frame.pack(fill='both', expand=True)

        self.detail = tk.Text(txt_frame,
                              font=('微软雅黑', 10), wrap='word',
                              bg=C['card'], fg=C['text'],
                              insertbackground=C['accent'],
                              selectbackground=C['acc_dark'],
                              selectforeground='white',
                              relief='flat', undo=True, maxundo=50,
                              padx=8, pady=6)
        d_vsb = ttk.Scrollbar(txt_frame, orient='vertical',
                               command=self.detail.yview)
        self.detail.configure(yscrollcommand=d_vsb.set)
        self.detail.pack(side='left', fill='both', expand=True)
        d_vsb.pack(side='right', fill='y')

        # 颜色 tag
        for tag, fg, bg in [
            ('accent',   C['accent'],  ''),
            ('star_tag', C['star'],    ''),
            ('dim',      C['dim'],     ''),
            ('policy',   C['yellow'],  ''),
            ('concept',  C['green'],   ''),
            ('money',    C['red'],     ''),
            ('percent',  C['accent'],  ''),
            ('category', 'white',       C['purple']),
            ('category_kw', '#05070b',  C['star']),
            # 🆕 v9.3 联动行情行级染色：A 股习惯红涨绿跌
            ('up',       C['red'],     ''),
            ('down',     C['green'],   ''),
            ('flat',     C['dim'],     ''),
            # 🆕 v9.3 主股票标识：当前记录对应的股票，加深背景突出
            ('main_stock', C['star'],  '#3a2f1a'),
        ]:
            kw = {'foreground': fg}
            if bg: kw['background'] = bg
            # category 加粗
            if tag == 'category':
                kw['font'] = ('微软雅黑', 10, 'bold')
            # 主股票也加粗
            if tag == 'main_stock':
                kw['font'] = ('微软雅黑', 10, 'bold')
            self.detail.tag_config(tag, **kw)

        for _, tag, bg, fg in MANUAL_HL_TAGS:
            self.detail.tag_config(tag, background=bg, foreground=fg)

        self.detail.bind('<<Modified>>', self._on_modified)
        # 🔑 兜底：用 KeyRelease 检测编辑（IME 中文输入下 <<Modified>> 不可靠）
        self.detail.bind('<KeyRelease>', self._on_key_release)

        # 右键菜单
        self._ctx = self._build_context_menu()
        self.detail.bind('<Button-3>', self._show_ctx)
        self.detail.bind('<Button-2>', self._show_ctx)  # macOS
        # 🆕 v9.6：左键联动 — 单击文字时识别附近股票通知浮窗（不阻止默认）
        self.detail.bind('<Button-1>', self._detail_left_click_follow, add='+')

        self._refresh_dates()
        bus.on(Events.HISTORY_UPDATED,
               lambda *a: self.app.root.after(100, self._refresh_dates))
