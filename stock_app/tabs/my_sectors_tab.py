"""
🗂️ 我的板块（整合版）
─────────────────────────────────────
左侧导航：
  📌 自选股                  ← 原 自选股 Tab
  ─────────
  📂 半导体（用户自建板块）
  📂 AI算力
  📂 ...
  ─────────
  🕸️ 标签关联度              ← 原 标签关联 Tab

右侧根据选择切换：
  - 自选股：列表 + 详情（含历史分析）
  - 自建板块：股票表 + 行情 + 详情
  - 标签关联度：图表 + AI 推理

主界面顶部统一一个「📥 快速导入栏」：
  粘贴 "半导体：寒武纪 海光信息 600519" → 自动建板块+加股票
"""
import json
import re
import threading
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

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

from .base import BaseTab
from ..widgets import load_col_widths, save_col_widths
from ..widgets import make_card, styled_btn, styled_entry, apply_highlight
from ..core import (config as cfg_mod, history as hist_mod,
                    api_client, my_sectors, tag_relation as tr)
from ..bus import bus, Events, state

# 拆分出去的 Mixin —— 见 my_sectors/ 子目录
from .my_sectors.fav import FavoritesMixin
from .my_sectors.user_sector import UserSectorMixin
from .my_sectors.tag_relation import TagRelationMixin


# 三种视图
VIEW_FAV   = "favorites"
VIEW_USER  = "user_sector"
VIEW_TAG   = "tag_relation"


class MySectorsTab(BaseTab, FavoritesMixin, UserSectorMixin, TagRelationMixin):
    title = "我的板块"

    def __init__(self, app):
        super().__init__(app)
        self._cur_view = None    # VIEW_FAV / VIEW_USER / VIEW_TAG
        self._cur_sector_name = None
        self._row_data = {}      # iid -> dict（自选股/板块共用）
        self._auto_refresh_id = None
        self._auto_refresh_on = False
        # 标签关联度
        self._tag_freq = {}
        self._cooccur  = {}
        self._tag_records = {}
        self._cur_tag  = None
        self._cur_rels = []
        self._cur_other_tag = None

    def build(self, parent):
        C = self.C
        body = tk.Frame(parent, bg=C['bg'])
        body.pack(fill='both', expand=True, padx=10, pady=8)

        # ═══════════ 顶部：快速导入栏 ═══════════
        top = tk.Frame(body, bg=C['panel'],
                        highlightbackground=C['border'], highlightthickness=1)
        top.pack(fill='x', pady=(0, 6))
        ti = tk.Frame(top, bg=C['panel']); ti.pack(fill='x', padx=8, pady=6)
        tk.Label(ti, text="📥 快速导入", font=('微软雅黑', 9, 'bold'),
                 bg=C['panel'], fg=C['accent']).pack(side='left', padx=(0, 6))

        self._quick_var = tk.StringVar()
        quick_entry = tk.Entry(ti, textvariable=self._quick_var,
                                font=('微软雅黑', 10),
                                bg=C['card'], fg=C['text'],
                                insertbackground='white', relief='flat')
        quick_entry.pack(side='left', fill='x', expand=True, ipady=4)
        quick_entry.bind('<Return>', lambda e: self._quick_import())

        styled_btn(ti, "➕ 导入", C['green'],
                   self._quick_import).pack(side='left', padx=(6, 0))

        tk.Label(top,
                 text="💡 格式：「板块名：股票1 股票2 代码1 ...」  例：半导体：寒武纪 海光信息 600519",
                 font=('微软雅黑', 8), bg=C['panel'], fg=C['dim']).pack(anchor='w', padx=10, pady=(0, 4))

        # ═══════════ 主体：左导航 / 右内容 ═══════════
        pw = tk.PanedWindow(body, bg=C['bg'], sashwidth=5,
                             sashrelief='flat', orient='horizontal')
        pw.pack(fill='both', expand=True)
        left  = tk.Frame(pw, bg=C['bg'])
        right = tk.Frame(pw, bg=C['bg'])
        pw.add(left,  minsize=200)
        pw.add(right, minsize=620)

        # ─── 左：导航 ───
        tk.Label(left, text="🗂️ 我的导航",
                 font=('微软雅黑', 9, 'bold'),
                 bg=C['bg'], fg=C['accent']).pack(anchor='w', pady=(0, 4))

        self._nav = tk.Listbox(left,
                                font=('微软雅黑', 10),
                                bg=C['card'], fg=C['text'],
                                selectbackground=C['acc_dark'],
                                selectforeground='white',
                                relief='flat', highlightthickness=0,
                                activestyle='none')
        nvsb = ttk.Scrollbar(left, orient='vertical', command=self._nav.yview)
        self._nav.configure(yscrollcommand=nvsb.set)
        self._nav.pack(side='left', fill='both', expand=True)
        nvsb.pack(side='right', fill='y')
        self._nav.bind('<<ListboxSelect>>', lambda e: self._on_nav_select())

        # 左下按钮
        lb = tk.Frame(left, bg=C['bg']); lb.pack(fill='x', pady=(4, 0))
        styled_btn(lb, "➕ 新建板块", C['green'],
                   self._create_sector_dialog).pack(side='left', padx=(0, 3))
        styled_btn(lb, "✏️ 重命名", C['accent'],
                   self._rename_sector).pack(side='left', padx=(0, 3))
        styled_btn(lb, "🗑 删除", C['red'],
                   self._delete_sector).pack(side='left')
        tk.Label(left, text="💡 Ctrl+N 新建  Ctrl+Enter 分析",
                 font=('微软雅黑', 7), bg=C['bg'], fg=C['dim']).pack(anchor='w', pady=(2, 0))

        # ─── 右：三种视图共用容器（动态切换） ───
        self._right_container = tk.Frame(right, bg=C['bg'])
        self._right_container.pack(fill='both', expand=True)

        # 预先构建三个视图（懒加载）
        self._views = {}

        # 初始化
        self._refresh_nav()
        # 默认选中第一项（自选股）
        if self._nav.size() > 0:
            self._nav.selection_set(0)
            self._on_nav_select()

        # 事件
        bus.on(Events.FAVORITES_UPDATED,
               lambda *a: self.app.root.after(100, self._on_event_update))
        bus.on(Events.HISTORY_UPDATED,
               lambda *a: self.app.root.after(100, self._on_event_update))

        # 快捷键
        self._bind_shortcuts()

    def _on_event_update(self):
        """事件触发时，根据当前视图刷新"""
        if self._cur_view == VIEW_FAV:
            self._render_favorites()
        elif self._cur_view == VIEW_USER:
            self._render_user_sector()

    def _bind_shortcuts(self):
        root = self.app.root
        root.bind('<Control-n>', lambda e: self._maybe(self._create_sector_dialog))
        root.bind('<Control-N>', lambda e: self._maybe(self._create_sector_dialog))
        root.bind('<Control-Return>', lambda e: self._maybe(self._analyze_current))

    def _maybe(self, fn):
        try:
            if self.app.nb.select() == str(self.frame):
                fn()
        except Exception:
            pass

    # ════════════════════════════════════════════════
    # 导航
    # ════════════════════════════════════════════════
    def _refresh_nav(self):
        cur_sel = self._nav.curselection()
        cur_text = self._nav.get(cur_sel[0]) if cur_sel else ""

        self._nav.delete(0, 'end')
        # 1. 自选股
        favs = cfg_mod.load_favorites()
        self._nav.insert('end', "📌 自选股 ({})".format(len(favs)))
        # 2. 分隔
        self._nav.insert('end', "─" * 22)
        # 3. 自建板块
        for name in my_sectors.list_sectors():
            sector = my_sectors.get_sector(name)
            n = len(sector['stocks']) if sector else 0
            self._nav.insert('end', "  📂 {}  ({})".format(name, n))
        # 4. 分隔
        self._nav.insert('end', "─" * 22)
        # 5. 标签关联度
        self._nav.insert('end', "🕸️ 标签关联度")

        # 恢复选中
        for i in range(self._nav.size()):
            if self._nav.get(i) == cur_text:
                self._nav.selection_set(i)
                return
        if self._nav.size() > 0:
            self._nav.selection_set(0)

    def _on_nav_select(self):
        sel = self._nav.curselection()
        if not sel: return
        text = self._nav.get(sel[0])

        if text.startswith("─"):
            # 分隔行，跳过
            return

        # 清空右侧
        for w in self._right_container.winfo_children():
            w.destroy()

        if text.startswith("📌 自选股"):
            self._cur_view = VIEW_FAV
            self._cur_sector_name = None
            self._build_favorites_view()
        elif text.startswith("🕸️"):
            self._cur_view = VIEW_TAG
            self._cur_sector_name = None
            self._build_tag_relation_view()
        elif "📂" in text:
            # 提取板块名
            name = text.strip().lstrip("📂 ").strip()
            # 去掉末尾的 (N)
            name = re.sub(r'\s*\(\d+\)\s*$', '', name).strip()
            self._cur_view = VIEW_USER
            self._cur_sector_name = name
            self._build_user_sector_view()

    # ════════════════════════════════════════════════
    # 快速导入
    # ════════════════════════════════════════════════
    def _quick_import(self):
        text = self._quick_var.get().strip()
        if not text:
            return

        name_lookup = cfg_mod.get_name_lookup()
        parsed = my_sectors.parse_smart(text, name_lookup=name_lookup)
        sector_name = parsed.get('sector_name')
        stocks = parsed.get('stocks', [])

        if not sector_name:
            # 没有板块名 → 默认放到当前板块
            if self._cur_view == VIEW_USER and self._cur_sector_name:
                sector_name = self._cur_sector_name
            else:
                messagebox.showinfo("提示",
                    "请按格式输入：板块名：股票1 股票2 ...\n"
                    "例如：半导体：寒武纪 海光信息 600519\n\n"
                    "或先选中一个板块再粘贴股票")
                return

        if not stocks:
            messagebox.showinfo("提示",
                "未识别到任何股票代码。\n\n"
                "若使用中文名导入，请确保该名称已在历史记录中出现过。\n"
                "或使用6位代码导入（如 688256）。")
            return

        # 板块不存在则创建
        if not my_sectors.get_sector(sector_name):
            ok, msg = my_sectors.create_sector(sector_name)
            if not ok:
                messagebox.showwarning("失败", msg); return

        # 加入股票
        ok, msg, added = my_sectors.add_stocks(sector_name, stocks)

        # 清空输入框
        self._quick_var.set("")
        self._refresh_nav()

        # 切换到该板块
        for i in range(self._nav.size()):
            line = self._nav.get(i)
            if sector_name in line and "📂" in line:
                self._nav.selection_clear(0, 'end')
                self._nav.selection_set(i)
                self._cur_view = VIEW_USER
                self._cur_sector_name = sector_name
                for w in self._right_container.winfo_children():
                    w.destroy()
                self._build_user_sector_view()
                break

        # 后台异步刷新行情
        threading.Thread(target=lambda: (
            my_sectors.refresh_quotes(sector_name),
            state.ui_queue.put(self._render_user_sector)
        ), daemon=True).start()

        # 提示用户结果
        not_found = []
        if added < len(stocks):
            # 比较代码 vs 想加入的总数
            existing_codes = {s['code'] for s in my_sectors.get_sector(sector_name)['stocks']}
            for s in stocks:
                if s['code'] not in existing_codes:
                    not_found.append("{}({})".format(s.get('name','?'), s['code']))

        # 简短的临时提示（不弹窗，免打扰）
        msg = "✅ 导入「{}」：识别 {} 只，新增 {} 只".format(
            sector_name, len(stocks), added)
        bus.emit(Events.FAVORITES_UPDATED)

    # ════════════════════════════════════════════════
    # 视图1: 自选股
    # ════════════════════════════════════════════════