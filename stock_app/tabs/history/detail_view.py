"""
历史 Tab 的详情视图相关方法（Mixin）—— 从 history_tab.py 拆出
v9.9.7：单一职责拆分，对外接口完全不变
"""
import threading
import tkinter as tk
from tkinter import ttk, messagebox

from ...widgets import make_card, styled_btn, styled_entry, apply_highlight
from ...core import history as hist_mod, api_client, text_utils, reports
from ...bus import bus, Events, state
# v9.9.8 Phase 2: 业务逻辑迁到 services/
from ...services import ContentEditService

# 手动高亮 tag（与主文件保持同步）
MANUAL_HL_TAGS = [
    ("🟡 黄色",  "hl_yellow", "#ffb627", "#05070b"),
    ("🟢 绿色",  "hl_green",  "#00d68f", "#05070b"),
    ("🔵 蓝色",  "hl_blue",   "#5b8def", "#05070b"),
    ("🟣 紫色",  "hl_purple", "#a78bfa", "#05070b"),
    ("🔴 红色",  "hl_red",    "#ff3b3f", "#05070b"),
    ("🟠 橙色",  "hl_orange", "#ff9a3c", "#05070b"),
]


class DetailViewMixin:
    """详情区相关方法"""

    def _detail_left_click_follow(self, event):
        """v9.9.6：左键单击 → 通知浮窗刷新（浮窗永远跟随）"""
        text_utils.left_click_follow(event, self.detail, self.app)

    # ════════════════════════════════════════════
    # 手动高亮
    # ════════════════════════════════════════════
    def _hl_apply(self, tag):
        try:
            s = self.detail.index('sel.first')
            e = self.detail.index('sel.last')
        except tk.TclError:
            messagebox.showinfo("提示", "请先用鼠标选中要高亮的文字")
            return
        self.detail.tag_add(tag, s, e)

    def _hl_clear_sel(self):
        try:
            s = self.detail.index('sel.first')
            e = self.detail.index('sel.last')
        except tk.TclError:
            messagebox.showinfo("提示", "请先选中文字")
            return
        for _, tag, _, _ in MANUAL_HL_TAGS:
            self.detail.tag_remove(tag, s, e)
        for t in ('policy','concept','money','percent'):
            self.detail.tag_remove(t, s, e)

    def _hl_clear_all(self):
        for _, tag, _, _ in MANUAL_HL_TAGS:
            self.detail.tag_remove(tag, '1.0', 'end')
        for t in ('policy','concept','money','percent','category','category_kw'):
            self.detail.tag_remove(t, '1.0', 'end')

    # ════════════════════════════════════════════
    # 字号
    # ════════════════════════════════════════════
    def _font_up(self):
        v = self._fsize.get()
        if v < 24:
            self._fsize.set(v+1)
            self.detail.config(font=('微软雅黑', v+1))

    def _font_down(self):
        v = self._fsize.get()
        if v > 6:
            self._fsize.set(v-1)
            self.detail.config(font=('微软雅黑', v-1))

    # ════════════════════════════════════════════
    # 日期/列表
    # ════════════════════════════════════════════
    def _refresh_dates(self):
        dates = hist_mod.list_history_dates()
        display = [d[:4]+'-'+d[4:6]+'-'+d[6:] for d in dates]
        self.date_combo['values'] = display
        if dates and not self.date_var.get():
            self.date_combo.current(0)
        if self.date_var.get():
            self._load_day()

    def _get_date_key(self):
        return self.date_var.get().replace('-', '')

    def _load_day(self):
        d = self._get_date_key()
        if not d: return
        for i in self.tree.get_children():
            self.tree.delete(i)
        self._row_data.clear()   # 清空旧的行数据缓存
        only_star = self.only_star.get()
        for r in hist_mod.load_history(d):
            if only_star and not r.get('starred'): continue
            self._insert_row(r, d)

    def _insert_row(self, r, date_key):
        star = '⭐' if r.get('starred') else ''
        ok   = '✅' if r.get('success') else '❌'
        note = r.get('note','')[:20]
        tags = ('starred',) if r.get('starred') else ()
        iid  = self.tree.insert('', 'end',
                                 values=(star, r.get('time',''),
                                         r.get('name',''), r.get('code',''),
                                         ok, note), tags=tags)
        # 用 Python 字典缓存完整数据，不再依赖 tree.set 隐藏列
        self._row_data[iid] = {**r, 'date': date_key}

    def _get_sel(self):
        result = []
        for item in self.tree.selection():
            d = self._row_data.get(item)
            if d:
                result.append((d['date'], d, item))
        return result

    # ════════════════════════════════════════════
    # 详情显示 + 编辑 + 保存
    # ════════════════════════════════════════════
    def _show_detail(self):
        # 🔑 切换前：用快照对比检查内容是否有变化（不依赖 <<Modified>> 事件）
        # 这样即使中文 IME 输入下 <<Modified>> 漏触发，也能可靠保存
        if self._cur_record_id:
            current = self.detail.get('1.0', 'end-1c')
            if current and current != self._original_content:
                self._do_save_content_to_history()
        self._dirty = False
        # 取消已调度的自动保存
        if self._auto_save_id:
            try:
                self.app.root.after_cancel(self._auto_save_id)
            except Exception:
                pass
            self._auto_save_id = None

        recs = self._get_sel()
        if not recs: return
        _, r, _ = recs[0]
        self._cur_date_key  = r['date']
        self._cur_record_id = r.get('id')
        # 🆕 v9.3 记录"主股票"代码：用于在联动行情中标识
        self._cur_record_code = str(r.get('code', '')).zfill(6)
        # 🆕 v9.6 通知浮窗（联动模式开启时刷新）
        self.app.notify_stock_focus(r.get('code',''), r.get('name',''))

        # 屏蔽加载期间的 modified 事件
        self._loading = True
        try:
            self.detail.edit_reset()
            self.detail.delete('1.0', 'end')

            star = "⭐  " if r.get('starred') else ""
            head = "{}{}  {}({})  {}\n".format(
                star, r.get('time',''),
                r.get('name',''), r.get('code',''),
                '✅成功' if r.get('success') else '❌失败')
            self.detail.insert('end', head, 'accent')
            if r.get('note'):
                self.detail.insert('end', "📝 备注: " + r['note'] + "\n", 'star_tag')

            # 🆕 标签显示
            tags_list = r.get('tags', []) or []
            if tags_list:
                from ...core.replay import PRESET_TAGS
                tag_map = {v: lbl for lbl, v in PRESET_TAGS}
                tag_display = "  ".join(tag_map.get(t, t) for t in tags_list)
                self.detail.insert('end', "🏷️ 标签: " + tag_display + "\n", 'star_tag')

            # 🆕 次日表现
            nd = r.get('next_day')
            if nd and nd.get('change_pct') is not None:
                pct = nd['change_pct']
                arrow = "▲" if pct > 0 else ("▼" if pct < 0 else "─")
                sign  = "+" if pct > 0 else ""
                line = "📈 次日表现 ({}): {}  {}{}%\n".format(
                    nd.get('date',''), arrow, sign, pct)
                self.detail.insert('end', line,
                                   'concept' if pct > 0 else 'money')

            self.detail.insert('end', "\n" + r.get('content', ''))
            apply_highlight(self.detail, keep_editable=True)
            # 🆕 v9.4：识别"📊 同逻辑联动标的"区段并染色
            self._apply_quote_coloring(self.detail,
                main_code=self._cur_record_code or "")
            # 🆕 v9.9.6：把所有 6 位代码渲染为蓝字下划线 → 点击推送同花顺
            try:
                from ...widgets import attach_code_links
                attach_code_links(self.detail, self.app,
                                   main_code=self._cur_record_code or "", scope='main')
            except Exception:
                import traceback; traceback.print_exc()

            self.detail.edit_modified(False)
            self._dirty = False
            self._save_btn.config(state='disabled', text="💾 保存")
            self.detail.see('1.0')
            # 🔑 关键：记录加载后的内容快照，作为后续对比基准
            self._original_content = self.detail.get('1.0', 'end-1c')
        finally:
            self._loading = False

    def _on_modified(self, e):
        # _show_detail 加载内容时会触发，不算用户修改
        if self._loading:
            try:
                self.detail.edit_modified(False)
            except Exception:
                pass
            return
        if not self.detail.edit_modified():
            return
        # 🔑 立刻把 modified flag 重置回 False，这样下一次按键还会触发本事件
        # 否则 Tkinter 只在 False→True 时触发一次，连续打字将不再触发！
        try:
            self.detail.edit_modified(False)
        except Exception:
            pass

        if not self._dirty:
            self._dirty = True
            self._save_btn.config(state='normal', text="💾 保存中...")
        # 防抖自动保存：每次编辑后重置定时器
        self._schedule_auto_save()

    def _on_key_release(self, e):
        """KeyRelease 兜底：用快照对比直接判断有无变化"""
        if self._loading:
            return
        # 忽略修饰键和导航键
        if e.keysym in ('Control_L','Control_R','Shift_L','Shift_R','Alt_L','Alt_R',
                         'Left','Right','Up','Down','Home','End','Prior','Next'):
            return
        current = self.detail.get('1.0', 'end-1c')
        if current != self._original_content:
            if not self._dirty:
                self._dirty = True
                self._save_btn.config(state='normal', text="💾 保存中...")
            self._schedule_auto_save()

    def _schedule_auto_save(self):
        """每次编辑后调度自动保存（防抖：1.5秒内无新编辑才真正保存）"""
        if self._auto_save_id:
            try:
                self.app.root.after_cancel(self._auto_save_id)
            except Exception:
                pass
        self._auto_save_id = self.app.root.after(
            self._auto_save_delay, self._auto_save_now)

    def _auto_save_now(self):
        """实际执行自动保存"""
        self._auto_save_id = None
        if not self._cur_record_id:
            return
        # 用快照对比判断是否真的需要保存
        current = self.detail.get('1.0', 'end-1c')
        if current == self._original_content:
            return  # 没变化，不保存
        if self._do_save_content_to_history():
            self._dirty = False
            self._original_content = current  # 更新快照
            self.detail.edit_modified(False)
            self._save_btn.config(text="✅ 已自动保存", state='disabled')
            self.app.root.after(2000,
                lambda: self._save_btn.config(text="💾 保存"))

    def _do_save_content_to_history(self):
        """
        把当前详情面板内容（去掉元信息头）写回历史记录。

        v9.9.8 Phase 2: 业务逻辑迁到 ContentEditService.save_from_text;
        本方法只负责读 widget + 同步内存缓存。
        """
        if not self._cur_date_key or not self._cur_record_id:
            return False
        full = self.detail.get('1.0', 'end-1c')
        saved_content, ok = ContentEditService().save_from_text(
            self._cur_date_key, self._cur_record_id, full)
        if not ok:
            return False
        # 🔑 关键修复 (保留): 同步更新内存中的 _row_data 缓存
        # 否则切换回来时会用旧的缓存数据覆盖文件中的新内容(导致编辑"丢失")
        self._sync_row_data_cache(self._cur_record_id, content=saved_content)
        return True

    def _sync_row_data_cache(self, record_id, **fields):
        """更新内存中 _row_data 缓存的指定记录字段"""
        for iid, data in self._row_data.items():
            if data.get('id') == record_id:
                data.update(fields)
                break

    def _save_edit(self):
        if not self._do_save_content_to_history():
            return
        self._dirty = False
        self.detail.edit_modified(False)
        self._save_btn.config(text="✅ 已保存", state='disabled')
        self.app.root.after(2000,
            lambda: self._save_btn.config(text="💾 保存"))

    # ════════════════════════════════════════════
    # 🆕 v9.4：联动行情区段染色（统一处理单条/批量重识别两条路径）
    # ════════════════════════════════════════════
    def _apply_quote_coloring(self, widget, main_code=""):
        """
        扫描 widget 全文，找到「📊 同逻辑联动标的  实时行情」区段，
        对该区段内每一行整行染色：
          - 涨 → up（红）
          - 跌 → down（绿）
          - 平 → flat（暗）
          - 主股票 → 整行额外加 main_stock 背景（覆盖 fg 但能看清）
        """
        RT_MARKER = "📊 同逻辑联动标的"
        text = widget.get('1.0', 'end-1c')
        idx = text.find(RT_MARKER)
        if idx == -1:
            return
        # 找到 marker 所在行的行号
        start_offset = idx
        # 计算行号 + 列号：tkinter 用 "{line}.{col}" 索引
        # 行号 = 该 offset 之前换行数 + 1
        line_no = text.count("\n", 0, start_offset) + 1

        # 先清掉已有的 up/down/flat/main_stock tag（避免重复叠加）
        for t in ('up', 'down', 'flat', 'main_stock'):
            widget.tag_remove(t, '1.0', 'end')

        main6 = str(main_code or "").zfill(6) if main_code else ""

        # 从 marker 行开始扫到文末，逐行识别：
        #   匹配 ▲/▼/─ + 涨跌幅 → up/down/flat
        #   含 "小结" 且含 "上涨/下跌" → dim
        # 其他行（空行/分隔线/标题）跳过。
        # 注：行情区段固定在 marker 之后，且通常是 content 的末尾，扫到 EOF 安全。
        import re as _re
        cur_line = line_no + 1  # 跳过 marker 行本身
        total_lines = int(widget.index('end-1c').split('.')[0])
        while cur_line <= total_lines:
            line_start = "{}.0".format(cur_line)
            line_end   = "{}.end".format(cur_line)
            row_text = widget.get(line_start, line_end)
            stripped = row_text.strip()
            if not stripped:
                cur_line += 1
                continue
            # 小结行 → dim
            if "小结" in stripped and ("上涨" in stripped or "下跌" in stripped):
                widget.tag_add('dim', line_start, line_end)
                cur_line += 1
                continue
            # 行情行：含 ▲/▼/─ 后跟百分比
            m_pct = _re.search(r'([▲▼─])\s*([+\-]?\d+(?:\.\d+)?)\s*%', row_text)
            if not m_pct:
                cur_line += 1
                continue
            try:
                pct = float(m_pct.group(2))
            except ValueError:
                pct = 0.0
            if pct > 0:
                color_tag = 'up'
            elif pct < 0:
                color_tag = 'down'
            else:
                color_tag = 'flat'
            widget.tag_add(color_tag, line_start, line_end)
            # 主股票判断
            if main6:
                m_code = _re.search(r'[（(](\d{6})[)）]', row_text)
                if m_code and m_code.group(1) == main6:
                    widget.tag_add('main_stock', line_start, line_end)
            cur_line += 1

    # ════════════════════════════════════════════
    # 重新识别联动标的行情
    # ════════════════════════════════════════════
    def _requery_realtime(self):
        content = self.detail.get('1.0', 'end-1c')
        if not content.strip():
            messagebox.showinfo("提示", "请先选择一条记录")
            return

        SEP       = "─" * 40
        RT_MARKER = "📊 同逻辑联动标的  实时行情（腾讯财经）"

        # 移除旧的实时行情块
        if RT_MARKER in content:
            idx = content.find("\n\n" + SEP)
            if idx == -1:
                idx = content.rfind(SEP)
                if idx != -1:
                    idx = content.rfind("\n", 0, idx)
            if idx != -1:
                self.detail.delete("1.0+{}c".format(idx), 'end')
                content = content[:idx]

        # 提取联动标的代码
        codes = api_client.extract_linked_codes(content)
        # 🆕 v9.9.6：把当前主股票也加进去（放在最前面），让"本股票"也参与
        # 行情展示和 ⭐ 标记
        main_code = (self._cur_record_code or "").zfill(6) if self._cur_record_code else ""
        if main_code and main_code.isdigit() and len(main_code) == 6:
            if main_code in codes:
                codes.remove(main_code)
            codes = [main_code] + codes
        if not codes:
            self._show_inline_toast(
                "⚠️ 未在④段落找到6位股票代码（AI可能只给了名称没给代码）", "fail")
            return

        # 追加"查询中"提示
        self.detail.insert('end', "\n\n🔄 正在查询 {} 只联动标的行情，请稍候...".format(len(codes)))
        self.detail.see('end')

        def _do():
            data = api_client.fetch_change_pct(codes)

            def _update():
                # 删掉"查询中"提示
                txt = self.detail.get('1.0', 'end-1c')
                p   = txt.rfind("\n\n🔄")
                if p != -1:
                    self.detail.delete("1.0+{}c".format(p), 'end')

                if not data:
                    self._show_inline_toast(
                        "❌ 行情查询失败（非交易时段或网络问题）", "fail")
                    return

                lines_head = ["\n\n" + SEP, RT_MARKER, SEP, ""]
                # 先插入静态文本头（保留 plain 样式）
                self.detail.insert('end', "\n".join(lines_head) + "\n")
                main_code = (self._cur_record_code or "").zfill(6) if self._cur_record_code else ""
                up_n = down_n = 0
                for code, info in data.items():
                    chg = info.get("change_pct", 0)
                    try: chg = float(chg)
                    except (TypeError, ValueError): chg = 0.0
                    is_main = (str(code).zfill(6) == main_code) and main_code
                    if chg > 0:
                        arrow, sign = "▲", "+"; up_n += 1
                    elif chg < 0:
                        arrow, sign = "▼", "";  down_n += 1
                    else:
                        arrow, sign = "─", ""
                    prefix = "  ⭐ " if is_main else "    "
                    # 整行一次性插入，颜色由 _apply_quote_coloring 统一处理
                    self.detail.insert('end',
                        "{}{}（{}）  {}  {}{}{}%    {}\n".format(
                            prefix, info.get("name",""), code,
                            info.get("price",""), arrow, sign, chg,
                            info.get("time","")))
                # 底部汇总条
                if up_n or down_n:
                    self.detail.insert('end', SEP + "\n")
                    self.detail.insert('end',
                        "  小结：上涨 {}  ·  下跌 {}  ·  共 {}\n".format(
                            up_n, down_n, len(data)))
                self.detail.insert('end', SEP + "\n")

                # 🆕 v9.4：统一染色（涨红跌绿 + 主股突出）
                self._apply_quote_coloring(self.detail, main_code=main_code)
                # 🆕 v9.9.6：新追加的行情区里也加蓝字下划线链接
                try:
                    from ...widgets import attach_code_links
                    attach_code_links(self.detail, self.app,
                                       main_code=main_code, scope='main')
                except Exception:
                    import traceback; traceback.print_exc()
                self.detail.see('end')

                # 🔑 自动保存：把更新后的内容写回历史记录文件
                if self._cur_date_key and self._cur_record_id:
                    self._do_save_content_to_history()
                    self.detail.edit_modified(False)
                    self._dirty = False
                    self._save_btn.config(state='disabled')

                self._show_inline_toast(
                    "✅ 已识别 {} 只联动代码，{} 只成功获取行情，已自动保存".format(
                        len(codes), len(data)))

            self.app.root.after(0, _update)

        threading.Thread(target=_do, daemon=True).start()

    # ════════════════════════════════════════════
    # 右键菜单功能
    # ════════════════════════════════════════════
