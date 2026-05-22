"""历史记录 Tab — 右键菜单 Mixin"""
import tkinter as tk
from tkinter import messagebox

from ...widgets import apply_highlight
from ...core import text_utils, reports
from ...bus import bus, Events

# 手动高亮 tag（与主文件保持同步）
MANUAL_HL_TAGS = [
    ("🟡 黄色",  "hl_yellow", "#ffb627", "#05070b"),
    ("🟢 绿色",  "hl_green",  "#00d68f", "#05070b"),
    ("🔵 蓝色",  "hl_blue",   "#5b8def", "#05070b"),
    ("🟣 紫色",  "hl_purple", "#a78bfa", "#05070b"),
    ("🔴 红色",  "hl_red",    "#ff3b3f", "#05070b"),
    ("🟠 橙色",  "hl_orange", "#ff9a3c", "#05070b"),
]


class HistoryMenusMixin:
    """所有右键菜单相关方法"""

    def _build_context_menu(self):
        C = self.C
        ctx = tk.Menu(self.detail, tearoff=0,
                       bg=C['panel'], fg=C['text'],
                       activebackground=C['acc_dark'],
                       activeforeground='white',
                       font=('微软雅黑', 9))

        # 🆕 v9.5：浮窗查看（基于右键位置自动识别）
        ctx.add_command(label="🔎  查看此股详情",
                         command=self._ctx_show_stock_popup)
        ctx.add_separator()

        ctx.add_command(label="📋  复制       Ctrl+C",
                         command=lambda: self.detail.event_generate('<<Copy>>'))
        ctx.add_command(label="✂️  剪切       Ctrl+X",
                         command=lambda: self.detail.event_generate('<<Cut>>'))
        ctx.add_command(label="📌  粘贴       Ctrl+V",
                         command=lambda: self.detail.event_generate('<<Paste>>'))
        ctx.add_command(label="⬛  全选       Ctrl+A",
                         command=lambda: self.detail.tag_add('sel','1.0','end'))
        ctx.add_separator()

        # 手动高亮子菜单
        hl = tk.Menu(ctx, tearoff=0,
                      bg=C['panel'], fg=C['text'],
                      activebackground=C['acc_dark'],
                      activeforeground='white',
                      font=('微软雅黑', 9))
        for label, tag, bg, fg in MANUAL_HL_TAGS:
            hl.add_command(label=label,
                           command=lambda t=tag: self._hl_apply(t))
        hl.add_separator()
        hl.add_command(label="🚫  清除选中高亮",
                        command=self._hl_clear_sel)
        ctx.add_cascade(label="🎨  高亮选中文字", menu=hl)
        ctx.add_command(label="✨  自动关键词高亮",
                         command=lambda: apply_highlight(self.detail, keep_editable=True))
        ctx.add_command(label="🚫  清除全部高亮",
                         command=self._hl_clear_all)
        ctx.add_separator()
        ctx.add_command(label="💬  转微信格式并复制",
                         command=self._ctx_wechat)
        ctx.add_command(label="📄  导出此条为HTML",
                         command=self._ctx_export_html)
        ctx.add_separator()
        ctx.add_command(label="🔄  重新识别联动行情",
                         command=self._requery_realtime)
        ctx.add_command(label="💾  保存当前修改",
                         command=self._save_edit)
        ctx.add_separator()
        ctx.add_command(label="↩️  撤销       Ctrl+Z",
                         command=lambda: self.detail.event_generate('<<Undo>>'))
        ctx.add_command(label="↪️  重做       Ctrl+Y",
                         command=lambda: self.detail.edit_redo())
        return ctx

    def _show_ctx(self, event):
        # 🆕 v9.5：记录右键点击位置，用于"查看此股详情"识别附近的代码/股名
        try:
            self._ctx_click_index = self.detail.index(
                "@{},{}".format(event.x, event.y))
        except Exception:
            self._ctx_click_index = None
        try:
            self._ctx.tk_popup(event.x_root, event.y_root)
        finally:
            self._ctx.grab_release()

    def _ctx_show_stock_popup(self):
        """
        从右键位置附近识别股票，弹浮窗。识别规则（按优先级）：
          1. 若用户先选中了文本（sel），优先用选中文本
          2. 当前行匹配 6 位代码（含括号也行）→ 用代码
          3. 当前行匹配本地 stock_dict 里的股票名 → 用名字反查代码
          4. 都失败 → 退而求其次用当前记录本身的 code/name
        """
        import re
        text_at_cursor = ""
        # 1. 用选中文本
        try:
            text_at_cursor = self.detail.get('sel.first', 'sel.last')
        except tk.TclError:
            text_at_cursor = ""

        # 2. 当前行整行
        line_text = ""
        idx = getattr(self, '_ctx_click_index', None) or self.detail.index('insert')
        try:
            line_no = idx.split('.')[0]
            line_text = self.detail.get("{}.0".format(line_no), "{}.end".format(line_no))
        except Exception:
            pass

        target_code = ""
        target_name = ""

        search_text = text_at_cursor or line_text
        # 优先匹配 6 位代码（带括号或裸数字）
        m = re.search(r'[（(](\d{6})[)）]', search_text)
        if not m:
            m = re.search(r'(?<![.\d])(\d{6})(?![.\d])', search_text)
        if m:
            target_code = m.group(1)
            # 同行向前找 2-6 字的中文名（最靠近 ( 的那段）
            before = search_text[:m.start()]
            mname = re.search(r'([一-龥A-Z][一-龥A-Z0-9·\*]{1,7})\s*$',
                              before.rstrip())
            if mname: target_name = mname.group(1)

        # 还没拿到 → 用当前记录的 code/name 兜底
        if not target_code:
            target_code = self._cur_record_code or ""
            recs = self._get_sel()
            if recs:
                _, r, _ = recs[0]
                target_name = r.get('name', '')

        if not target_code:
            messagebox.showinfo("提示", "未能从光标附近识别到股票代码，请选中带 6 位代码的文字后再试")
            return
        self.app.show_stock_popup(target_code, target_name)

    def _ctx_wechat(self):
        content = self.detail.get('1.0', 'end-1c')
        recs = self._get_sel()
        name = recs[0][1].get('name','?') if recs else '?'
        code = recs[0][1].get('code','?') if recs else '?'
        wx = text_utils.to_wechat_format(name, code, content)
        self.app.root.clipboard_clear()
        self.app.root.clipboard_append(wx)
        messagebox.showinfo("已复制", "微信格式已复制到剪贴板")

    def _ctx_export_html(self):
        content = self.detail.get('1.0', 'end-1c')
        recs = self._get_sel()
        if not recs:
            messagebox.showinfo("提示", "请先选中左侧列表中的记录")
            return
        _, r, _ = recs[0]
        try:
            fn = reports.export_html_report([{
                "name":    r.get("name",""),
                "code":    r.get("code",""),
                "content": content,
                "success": True,
            }], title="{} 分析报告".format(r.get("name","")))
            messagebox.showinfo("导出成功", fn)
        except Exception as e:
            messagebox.showerror("失败", str(e))

    def _build_tree_context_menu(self):
        C = self.C
        m = tk.Menu(self.tree, tearoff=0,
                     bg=C['panel'], fg=C['text'],
                     activebackground=C['acc_dark'],
                     activeforeground='white',
                     font=('微软雅黑', 9))
        m.add_command(label="🔎  查看股票详情",    command=self._tree_show_popup)
        m.add_separator()
        m.add_command(label="⭐  切换星标",        command=self._toggle_star)
        m.add_command(label="📝  编辑备注",        command=self._edit_note_dialog)
        m.add_command(label="🏷️  编辑标签",        command=self._edit_tags_dialog)
        m.add_separator()
        m.add_command(label="➕  加入自选股",      command=self._add_to_favorites)
        m.add_command(label="📋  复制代码",        command=self._tree_copy_code)
        m.add_command(label="📋  复制 名称+代码",  command=self._tree_copy_name_code)
        m.add_separator()
        m.add_command(label="🔄  重新分析（送AI）", command=self._tree_reanalyze)
        m.add_separator()
        m.add_command(label="🗑  删除记录",        command=self._delete_selected)
        self._tree_ctx = m
        self.tree.bind('<Button-3>', self._show_tree_ctx)
        self.tree.bind('<Button-2>', self._show_tree_ctx)

    def _tree_show_popup(self):
        """🆕 v9.5：在浮窗打开股票详情"""
        recs = self._get_sel()
        if not recs: return
        _, r, _ = recs[0]
        self.app.show_stock_popup(r.get('code',''), r.get('name',''))

    def _show_tree_ctx(self, event):
        iid = self.tree.identify_row(event.y)
        if iid:
            if iid not in self.tree.selection():
                self.tree.selection_set(iid)
            try:
                self._tree_ctx.tk_popup(event.x_root, event.y_root)
            finally:
                self._tree_ctx.grab_release()

    def _tree_copy_code(self):
        recs = self._get_sel()
        if not recs: return
        _, r, _ = recs[0]
        self.app.root.clipboard_clear()
        self.app.root.clipboard_append(r.get('code', ''))

    def _tree_copy_name_code(self):
        recs = self._get_sel()
        if not recs: return
        _, r, _ = recs[0]
        self.app.root.clipboard_clear()
        self.app.root.clipboard_append("{} {}".format(r.get('name', ''), r.get('code', '')))

    def _tree_reanalyze(self):
        recs = self._get_sel()
        if not recs: return
        stocks = []
        for _, r, _ in recs:
            stocks.append((r.get('name', ''), r.get('code', ''), ''))
        bus.emit(Events.REQUEST_BATCH_RUN, stocks, "历史重分析")
