"""
自选股相关方法（Mixin）—— 从 my_sectors_tab.py 拆出
v9.9.7：单一职责拆分，对外接口完全不变
"""
import re
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

from ..base import BaseTab  # noqa: F401  # 仅类型提示用，运行时不严格依赖
from ...widgets import (
    make_card, styled_btn, styled_entry, apply_highlight,
    load_col_widths, save_col_widths,
)
from ...core import (
    config as cfg_mod,
    history as hist_mod,
    api_client, my_sectors,
)
from ...bus import bus, Events, state

# 三种视图常量（与主文件保持同步）
VIEW_FAV  = "favorites"
VIEW_USER = "user_sector"
VIEW_TAG  = "tag_relation"


class FavoritesMixin:
    """所有 _fav_xxx / _build_favorites_view 等自选股相关方法"""

    def _build_favorites_view(self):
        C = self.C
        v = tk.Frame(self._right_container, bg=C['bg'])
        v.pack(fill='both', expand=True)
        self._views[VIEW_FAV] = v

        # 顶部
        hr = tk.Frame(v, bg=C['bg']); hr.pack(fill='x', pady=(0, 6))
        tk.Label(hr, text="📌 自选股", font=('微软雅黑', 12, 'bold'),
                 bg=C['bg'], fg=C['accent']).pack(side='left')
        styled_btn(hr, "🚀 全部分析", C['green'], self._fav_analyze_all).pack(side='right')
        styled_btn(hr, "🔄 刷新", C['idle'], self._render_favorites).pack(side='right', padx=(0, 4))

        # 内嵌添加栏
        ar = tk.Frame(v, bg=C['panel'],
                       highlightbackground=C['border'], highlightthickness=1)
        ar.pack(fill='x', pady=(0, 6))
        ar_in = tk.Frame(ar, bg=C['panel']); ar_in.pack(fill='x', padx=8, pady=6)
        self._fav_name = tk.StringVar()
        self._fav_code = tk.StringVar()
        self._fav_tag  = tk.StringVar()
        for lbl, var, w in [("名称", self._fav_name, 12),
                              ("代码", self._fav_code, 8),
                              ("标签/类别", self._fav_tag, 18)]:
            tk.Label(ar_in, text=lbl, font=('微软雅黑', 8),
                     bg=C['panel'], fg=C['dim']).pack(side='left', padx=(0, 3))
            styled_entry(ar_in, var, w).pack(side='left', padx=(0, 8), ipady=3)
        styled_btn(ar_in, "➕ 添加", C['accent'], self._fav_add).pack(side='left')

        # 双栏：左表 / 右详情
        pw = tk.PanedWindow(v, bg=C['bg'], sashwidth=5,
                             sashrelief='flat', orient='horizontal')
        pw.pack(fill='both', expand=True)
        lf = tk.Frame(pw, bg=C['bg'])
        rf = tk.Frame(pw, bg=C['bg'])
        pw.add(lf, minsize=360)
        pw.add(rf, minsize=400)

        cols = ('name', 'code', 'tag', 'last_date', 'next_day', 'added')
        col_widths = load_col_widths('favorites')
        defaults = {'name': 100, 'code': 75, 'tag': 130,
                    'last_date': 90, 'next_day': 75, 'added': 130}
        titles   = {'name': '名称', 'code': '代码',
                    'tag': '细分标签', 'last_date': '最近分析',
                    'next_day': '次日%', 'added': '添加时间'}
        self._fav_tree = ttk.Treeview(lf, columns=cols, show='headings', height=22)
        for col in cols:
            self._fav_tree.heading(col, text=titles[col])
            self._fav_tree.column(col,
                                   width=col_widths.get(col, defaults[col]),
                                   minwidth=40,
                                   anchor='center' if col != 'name' else 'w',
                                   stretch=True)
        fvsb = ttk.Scrollbar(lf, orient='vertical', command=self._fav_tree.yview)
        self._fav_tree.configure(yscrollcommand=fvsb.set)
        self._fav_tree.pack(side='left', fill='both', expand=True)
        fvsb.pack(side='right', fill='y')

        def _save_w(*_):
            save_col_widths('favorites',
                {c: self._fav_tree.column(c, 'width') for c in cols})
        self._fav_tree.bind('<ButtonRelease-1>', _save_w)

        self._fav_tree.tag_configure('green', foreground=C['red'])
        self._fav_tree.tag_configure('red',   foreground=C['green'])
        self._fav_tree.tag_configure('flat',  foreground=C['dim'])
        self._fav_tree.bind('<<TreeviewSelect>>', lambda e: self._fav_show_detail())
        self._fav_tree.bind('<Delete>',           lambda e: self._fav_remove())
        self._fav_tree.bind('<Double-1>',         lambda e: self._fav_analyze_sel())

        # 右键菜单
        self._fav_ctx = self._build_fav_ctx()
        self._fav_tree.bind('<Button-3>', self._show_fav_ctx)
        self._fav_tree.bind('<Button-2>', self._show_fav_ctx)

        # 详情面板
        rh = tk.Frame(rf, bg=C['panel'],
                       highlightbackground=C['border'], highlightthickness=1)
        rh.pack(fill='x')
        self._fav_title = tk.StringVar(value="📄 详情（点击左侧）")
        tk.Label(rh, textvariable=self._fav_title,
                 font=('微软雅黑', 10, 'bold'),
                 bg=C['panel'], fg=C['accent']).pack(side='left', padx=8, pady=6)
        styled_btn(rh, "✨ 自动高亮", C['acc_dark'],
                   lambda: apply_highlight(self._fav_detail, keep_editable=True),
                   pady=3).pack(side='right', padx=(0, 4), pady=4)

        self._fav_detail = tk.Text(rf, font=('微软雅黑', 10), wrap='word',
                                    bg=C['card'], fg=C['text'],
                                    relief='flat', padx=10, pady=8,
                                    state='disabled', cursor='arrow')
        dvsb = ttk.Scrollbar(rf, orient='vertical', command=self._fav_detail.yview)
        self._fav_detail.configure(yscrollcommand=dvsb.set)
        self._fav_detail.pack(side='left', fill='both', expand=True)
        dvsb.pack(side='right', fill='y')

        for tag, fg, bg in [
            ('accent', C['accent'], ''), ('star_tag', C['star'], ''),
            ('dim', C['dim'], ''), ('policy', C['yellow'], ''),
            ('concept', C['green'], ''), ('money', C['red'], ''),
            ('percent', C['accent'], ''),
            ('category', 'white', C['purple']),
            ('category_kw', '#05070b', C['star']),
            ('h2', C['yellow'], ''),
        ]:
            kw = {'foreground': fg}
            if bg: kw['background'] = bg
            if tag == 'category':
                kw['font'] = ('微软雅黑', 10, 'bold')
            self._fav_detail.tag_config(tag, **kw)

        self._render_favorites()

    def _build_fav_ctx(self):
        C = self.C
        m = tk.Menu(self._fav_tree, tearoff=0,
                     bg=C['panel'], fg=C['text'],
                     activebackground=C['acc_dark'],
                     activeforeground='white',
                     font=('微软雅黑', 9))
        m.add_command(label="🔎  查看股票详情", command=self._fav_show_popup)
        m.add_separator()
        m.add_command(label="🔍  分析选中", command=self._fav_analyze_sel)
        m.add_command(label="🚀  分析全部", command=self._fav_analyze_all)
        m.add_separator()
        m.add_command(label="📋  复制代码", command=lambda: self._fav_copy('code'))
        m.add_command(label="📋  复制 名称+代码", command=lambda: self._fav_copy('name_code'))
        m.add_separator()
        m.add_command(label="🏷️  编辑标签", command=self._fav_edit_tag)
        m.add_command(label="📜  查看完整历史", command=self._fav_view_history)
        m.add_separator()
        m.add_command(label="🗑  删除", command=self._fav_remove)
        return m

    def _fav_show_popup(self):
        sel = self._fav_tree.selection()
        if not sel: return
        data = self._row_data.get(sel[0])
        if data:
            self.app.show_stock_popup(data.get('code',''), data.get('name',''))

    def _show_fav_ctx(self, event):
        iid = self._fav_tree.identify_row(event.y)
        if iid:
            if iid not in self._fav_tree.selection():
                self._fav_tree.selection_set(iid)
            try:
                self._fav_ctx.tk_popup(event.x_root, event.y_root)
            finally:
                self._fav_ctx.grab_release()

    def _render_favorites(self):
        if not hasattr(self, '_fav_tree'):
            return
        for i in self._fav_tree.get_children():
            self._fav_tree.delete(i)
        self._row_data.clear()

        favs = cfg_mod.load_favorites()
        index = self._build_history_index()
        hidx = hist_mod.get_code_count_index()
        for f in favs:
            code = f.get('code', '')
            last = index.get(code)
            last_date = ""
            nd_str = ""
            row_tag = ''
            if last:
                d = last['date']
                last_date = "{}-{}".format(d[4:6], d[6:])
                nd = last.get('next_day')
                if nd and nd.get('change_pct') is not None:
                    pct = nd['change_pct']
                    nd_str = "{:+.1f}%".format(pct)
                    row_tag = 'green' if pct > 0 else ('red' if pct < 0 else 'flat')
            # 🆕 v9.6：有历史则 name 后追加 📊
            mark = " 📊" if hidx.get(str(code).zfill(6), 0) > 0 else ""
            iid = self._fav_tree.insert('', 'end', values=(
                f.get('name','') + mark, f.get('code',''),
                f.get('tag',''), last_date, nd_str, f.get('added_at','')
            ), tags=(row_tag,) if row_tag else ())
            self._row_data[iid] = {**f, 'last_record': last}

    def _build_history_index(self):
        index = {}
        for date_key in hist_mod.list_history_dates():
            for r in hist_mod.load_history(date_key):
                code = r.get('code', '')
                if not code: continue
                if code not in index or date_key > index[code]['date']:
                    index[code] = {**r, 'date': date_key}
        return index

    def _fav_show_detail(self):
        sel = self._fav_tree.selection()
        if not sel: return
        data = self._row_data.get(sel[0])
        if not data: return
        # 🆕 v9.6：通知浮窗（联动模式开启时刷新）
        self.app.notify_stock_focus(data.get('code',''), data.get('name',''))

        T = self._fav_detail
        T.config(state='normal')
        T.delete('1.0', 'end')

        name = data.get('name', ''); code = data.get('code', '')
        tag  = data.get('tag', '')
        self._fav_title.set("📄 {} ({})".format(name, code))

        def w(text, t=None):
            if t: T.insert('end', text, t)
            else: T.insert('end', text)

        w("⭐ {} ({})\n".format(name, code), 'accent')
        if tag:
            w("🏷️ 标签 / 涨停类别: ", 'star_tag')
            w(tag + "\n", 'category')
        w("📅 加入时间: " + data.get('added_at', '未知') + "\n", 'dim')
        w("\n")

        last = data.get('last_record')
        if last:
            d = last['date']
            w("─" * 50 + "\n", 'dim')
            w("📈 最近一次分析  ", 'h2')
            w("({}-{}-{}  {})\n".format(d[:4], d[4:6], d[6:],
                                          last.get('time', '')), 'dim')
            nd = last.get('next_day')
            if nd and nd.get('change_pct') is not None:
                pct = nd['change_pct']
                ct = 'concept' if pct > 0 else 'money'
                w("📊 次日: ", 'star_tag')
                w("{:+.2f}%".format(pct), ct)
                w("  (" + nd.get('date', '') + ")\n", 'dim')
            if last.get('note'):
                w("📝 " + last['note'] + "\n", 'star_tag')
            w("\n")
            content = last.get('content', '')
            if content:
                w(content)
                apply_highlight(T, keep_editable=True)
            else:
                w("（无分析内容）\n", 'dim')
        else:
            w("─" * 50 + "\n", 'dim')
            w("⚠️ 本地历史中暂无该股票的分析记录\n", 'dim')

        T.config(state='disabled')
        # 🆕 v9.9.6：详情里所有 6 位代码加蓝字下划线 → 推送同花顺
        try:
            from ...widgets import attach_code_links
            attach_code_links(T, self.app, main_code=code, scope='main')
        except Exception:
            import traceback; traceback.print_exc()

    def _fav_add(self):
        name = self._fav_name.get().strip()
        code = self._fav_code.get().strip()
        tag  = self._fav_tag.get().strip()
        if not name or not code:
            messagebox.showwarning("提示", "名称和代码不能为空"); return
        code = re.sub(r'\D', '', code).zfill(6)[:6]
        if cfg_mod.add_favorite(name, code, tag):
            self._fav_name.set(""); self._fav_code.set(""); self._fav_tag.set("")
            bus.emit(Events.FAVORITES_UPDATED)
            self._refresh_nav()
        else:
            messagebox.showinfo("已存在", "该代码已在自选股中")

    def _fav_remove(self):
        sel = self._fav_tree.selection()
        if not sel: return
        if not messagebox.askyesno("确认", "删除 {} 只？".format(len(sel))):
            return
        for item in sel:
            data = self._row_data.get(item)
            if data:
                cfg_mod.remove_favorite(data['code'])
        bus.emit(Events.FAVORITES_UPDATED)
        self._refresh_nav()

    def _fav_edit_tag(self):
        sel = self._fav_tree.selection()
        if not sel: return
        data = self._row_data.get(sel[0])
        if not data: return
        new = simpledialog.askstring("编辑标签",
            "为 {} ({}) 设置标签（多个用 + 分隔）：".format(data['name'], data['code']),
            initialvalue=data.get('tag', ''), parent=self.app.root)
        if new is None: return
        cfg_mod.remove_favorite(data['code'])
        cfg_mod.add_favorite(data['name'], data['code'], new.strip())
        bus.emit(Events.FAVORITES_UPDATED)

    def _fav_analyze_sel(self):
        sel = self._fav_tree.selection()
        if not sel: return
        stocks = []
        for item in sel:
            data = self._row_data.get(item)
            if data:
                stocks.append((data['name'], data['code'], data.get('tag','')))
        bus.emit(Events.REQUEST_BATCH_RUN, stocks, "自选股")

    def _fav_analyze_all(self):
        favs = cfg_mod.load_favorites()
        if not favs:
            messagebox.showinfo("提示", "自选股为空"); return
        if not messagebox.askyesno("确认", "分析全部 {} 只？".format(len(favs))):
            return
        stocks = [(f['name'], f['code'], f.get('tag','')) for f in favs]
        bus.emit(Events.REQUEST_BATCH_RUN, stocks, "自选股")

    def _fav_copy(self, kind):
        sel = self._fav_tree.selection()
        if not sel: return
        data = self._row_data.get(sel[0])
        if not data: return
        if kind == 'code':
            s = data['code']
        else:
            s = "{} {}".format(data['name'], data['code'])
        self.app.root.clipboard_clear()
        self.app.root.clipboard_append(s)

    def _fav_view_history(self):
        sel = self._fav_tree.selection()
        if not sel: return
        data = self._row_data.get(sel[0])
        if not data: return
        ht = self.app.tabs.get('HistoryTab')
        if ht:
            try:
                idx = self.app.nb.index(ht.frame)
                self.app.nb.select(idx)
                if hasattr(ht, 'kw_var'):
                    ht.kw_var.set(data['code'])
                    if hasattr(ht, '_search'):
                        ht._search()
            except Exception:
                pass

    # ════════════════════════════════════════════════
    # 视图2: 用户自建板块
    # ════════════════════════════════════════════════