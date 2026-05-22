"""
标签关联度 - 标签管理对话框 Mixin
v9.9.8：从 tag_relation.py 拆出
"""
import threading
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

from ...widgets import styled_btn
from ...core import my_sectors, tag_relation as tr, text_utils
from ...bus import state

# 三种视图常量（与主文件保持同步）
VIEW_FAV  = "favorites"
VIEW_USER = "user_sector"
VIEW_TAG  = "tag_relation"


class TagRelationManagerMixin:
    """_tag_open_manager / _tag_detail_show_ctx 等标签管理与交互方法"""

    # ════════════════════════════════════════════════
    # 🆕 v9.5：标签详情区右键 → 看光标附近股票详情
    # ════════════════════════════════════════════════
    def _tag_detail_show_ctx(self, event):
        try:
            self._tag_detail_click_idx = self._tag_detail.index(
                "@{},{}".format(event.x, event.y))
        except Exception:
            self._tag_detail_click_idx = None
        try:
            self._tag_detail_ctx.tk_popup(event.x_root, event.y_root)
        finally:
            self._tag_detail_ctx.grab_release()

    def _tag_detail_show_stock_popup(self):
        idx = getattr(self, '_tag_detail_click_idx', None) or self._tag_detail.index('insert')
        # 优先用选中文本
        try:
            search_text = self._tag_detail.get('sel.first', 'sel.last')
        except tk.TclError:
            search_text = ""
        if not search_text:
            try:
                line_no = idx.split('.')[0]
                search_text = self._tag_detail.get("{}.0".format(line_no),
                                                    "{}.end".format(line_no))
            except Exception:
                search_text = ""
        code, name = text_utils.extract_code_and_name(search_text)
        if not code:
            messagebox.showinfo("提示", "未在光标附近识别到股票代码")
            return
        self.app.show_stock_popup(code, name)

    def _tag_detail_left_click_follow(self, event):
        """v9.6：左键单击 → 通知浮窗刷新（v9.9.6 起浮窗永远跟随，无需判断开关）"""
        text_utils.left_click_follow(event, self._tag_detail, self.app)

    # ════════════════════════════════════════════════
    # 🆕 B1：标签管理对话框
    # ════════════════════════════════════════════════
    def _tag_open_manager(self):
        """列出所有标签，支持重命名/合并/删除/查看别名表"""
        C = self.C
        dlg = tk.Toplevel(self.app.root)
        dlg.title("🏷️  标签管理")
        dlg.geometry("760x560")
        dlg.configure(bg=C['bg'])
        dlg.transient(self.app.root)

        # 顶部提示
        tk.Label(dlg, text="🏷️  标签管理",
                 font=('微软雅黑', 12, 'bold'),
                 bg=C['bg'], fg=C['accent']).pack(pady=(10, 2))
        hint = ("· 重命名: 选中 1 个标签，改名后所有历史 category 同步\n"
                "· 合并:   选中 2+ 个标签，输入目标名，全部并入目标\n"
                "· 删除:   选中 N 个标签，从所有 category 中移除（不动 AI 文本）")
        tk.Label(dlg, text=hint, font=('微软雅黑', 9),
                 bg=C['bg'], fg=C['dim'], justify='left').pack(pady=(0, 8))

        # 表格
        wrap = tk.Frame(dlg, bg=C['bg']); wrap.pack(fill='both', expand=True, padx=14)
        cols = ('tag', 'freq', 'codes_n', 'first', 'last')
        tree = ttk.Treeview(wrap, columns=cols, show='headings', height=18,
                             selectmode='extended')
        for col, txt, w_ in [('tag','标签',180),('freq','频次',60),
                              ('codes_n','涉及股票数',90),
                              ('first','首次',88),('last','最近',88)]:
            tree.heading(col, text=txt)
            tree.column(col, width=w_, minwidth=40,
                         anchor='center' if col != 'tag' else 'w',
                         stretch=True)
        sb = ttk.Scrollbar(wrap, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        tree.pack(side='left', fill='both', expand=True)
        sb.pack(side='right', fill='y')

        # 状态条
        status = tk.StringVar(value="加载中...")
        tk.Label(dlg, textvariable=status, font=('微软雅黑', 9),
                 bg=C['bg'], fg=C['yellow']).pack(anchor='w', padx=14, pady=(4, 2))

        # 数据加载
        def _reload():
            tree.delete(*tree.get_children())
            status.set("⏳ 扫描所有历史...")
            def _do():
                rows = tr.list_all_tags(days=0)
                def _upd():
                    for r in rows:
                        tree.insert('', 'end', values=(
                            r['tag'], r['freq'], r['codes_n'],
                            r['first_date'], r['last_date']))
                    status.set("✅ 共 {} 个标签".format(len(rows)))
                state.ui_queue.put(_upd)
            threading.Thread(target=_do, daemon=True).start()

        _reload()

        def _selected_tags():
            return [tree.item(iid)['values'][0] for iid in tree.selection()]

        # 操作按钮区
        def _do_rename():
            tags = _selected_tags()
            if len(tags) != 1:
                messagebox.showinfo("提示", "请选择 1 个标签进行重命名", parent=dlg); return
            old = tags[0]
            new = simpledialog.askstring("重命名",
                "把【{}】改为：".format(old),
                initialvalue=old, parent=dlg)
            if not new or new.strip() == old: return
            new = new.strip()
            def _do():
                n = tr.rename_tag(old, new)
                state.ui_queue.put(lambda: (
                    messagebox.showinfo("完成",
                        "已把 {} 条历史记录中的【{}】改为【{}】\n（同时写入了别名表）".format(n, old, new),
                        parent=dlg),
                    _reload()))
            threading.Thread(target=_do, daemon=True).start()

        def _do_merge():
            tags = _selected_tags()
            if len(tags) < 2:
                messagebox.showinfo("提示", "请至少选择 2 个标签进行合并", parent=dlg); return
            target = simpledialog.askstring("合并",
                "把下列 {} 个标签合并为：\n\n  {}".format(
                    len(tags), "、".join(tags[:8]) + ("..." if len(tags) > 8 else "")),
                initialvalue=tags[0], parent=dlg)
            if not target or not target.strip(): return
            target = target.strip()
            sources = [t for t in tags if t != target]
            if not sources: return
            def _do():
                n, per = tr.merge_tags(sources, target)
                detail = "\n".join("  · {} → {} 条".format(s, c) for s, c in per.items())
                state.ui_queue.put(lambda: (
                    messagebox.showinfo("完成",
                        "已合并 {} 个标签到【{}】，共影响 {} 条历史记录:\n\n{}".format(
                            len(sources), target, n, detail),
                        parent=dlg),
                    _reload()))
            threading.Thread(target=_do, daemon=True).start()

        def _do_delete():
            tags = _selected_tags()
            if not tags:
                messagebox.showinfo("提示", "请选择要删除的标签", parent=dlg); return
            if not messagebox.askyesno("确认",
                "确定要从所有历史 category 中删除以下 {} 个标签吗？\n\n{}\n\n"
                "（AI 生成的文本不会被改动）".format(
                    len(tags), "、".join(tags[:10]) + ("..." if len(tags) > 10 else "")),
                parent=dlg): return
            def _do():
                total = 0
                for t in tags:
                    total += tr.delete_tag(t)
                state.ui_queue.put(lambda: (
                    messagebox.showinfo("完成",
                        "已从 {} 条历史记录中移除 {} 个标签".format(total, len(tags)),
                        parent=dlg),
                    _reload()))
            threading.Thread(target=_do, daemon=True).start()

        def _do_view_aliases():
            aliases = tr.load_aliases()
            if not aliases:
                messagebox.showinfo("别名表", "暂无别名映射", parent=dlg); return
            lines = ["  · {} → {}".format(k, v) for k, v in sorted(aliases.items())]
            msg = "当前别名表（共 {} 条）：\n\n{}".format(
                len(aliases), "\n".join(lines[:50]))
            if len(aliases) > 50: msg += "\n\n...（仅显示前 50 条）"
            messagebox.showinfo("别名表", msg, parent=dlg)

        bb = tk.Frame(dlg, bg=C['bg']); bb.pack(fill='x', padx=14, pady=(0, 12))
        styled_btn(bb, "✏️ 重命名", C['accent'],     _do_rename, pady=6).pack(side='left', padx=(0, 4))
        styled_btn(bb, "🔀 合并",   C['purple'],     _do_merge,  pady=6).pack(side='left', padx=(0, 4))
        styled_btn(bb, "🗑 删除",   C['red'],        _do_delete, pady=6).pack(side='left', padx=(0, 4))
        styled_btn(bb, "🔗 查看别名表", C['idle'],   _do_view_aliases, pady=6).pack(side='left')
        styled_btn(bb, "🔄 刷新",   C['idle'],       lambda: _reload(), pady=6).pack(side='right')

        def _on_close():
            # 关闭时若有改动，刷新主关联视图
            dlg.destroy()
            try:
                self._tag_rescan()
            except Exception:
                pass
        dlg.protocol("WM_DELETE_WINDOW", _on_close)

    # ════════════════════════════════════════════════
    # 全局：新建/重命名/删除板块
    # ════════════════════════════════════════════════
    def _create_sector_dialog(self):
        name = simpledialog.askstring("新建板块",
            "请输入板块名（如：半导体）", parent=self.app.root)
        if not name: return
        ok, msg = my_sectors.create_sector(name.strip())
        if not ok:
            messagebox.showwarning("失败", msg); return
        self._refresh_nav()
        for i in range(self._nav.size()):
            if name.strip() in self._nav.get(i) and "📂" in self._nav.get(i):
                self._nav.selection_clear(0, 'end')
                self._nav.selection_set(i)
                self._cur_view = VIEW_USER
                self._cur_sector_name = name.strip()
                for w in self._right_container.winfo_children():
                    w.destroy()
                self._build_user_sector_view()
                break

    def _rename_sector(self):
        if self._cur_view != VIEW_USER or not self._cur_sector_name:
            messagebox.showinfo("提示", "请先选中一个自建板块"); return
        new = simpledialog.askstring("重命名",
            "新名称：", initialvalue=self._cur_sector_name, parent=self.app.root)
        if not new: return
        ok, msg = my_sectors.rename_sector(self._cur_sector_name, new.strip())
        if not ok:
            messagebox.showwarning("失败", msg); return
        self._cur_sector_name = new.strip()
        self._refresh_nav()
        self._render_user_sector()

    def _delete_sector(self):
        if self._cur_view != VIEW_USER or not self._cur_sector_name:
            messagebox.showinfo("提示", "请先选中一个自建板块"); return
        if not messagebox.askyesno("确认",
                "删除板块「{}」？".format(self._cur_sector_name)):
            return
        my_sectors.delete_sector(self._cur_sector_name)
        self._cur_sector_name = None
        for w in self._right_container.winfo_children():
            w.destroy()
        self._refresh_nav()

    def _analyze_current(self):
        """快捷键 Ctrl+Enter 触发，按当前视图执行相应分析"""
        if self._cur_view == VIEW_FAV:
            self._fav_analyze_sel()
        elif self._cur_view == VIEW_USER:
            self._analyze_user_sector()
