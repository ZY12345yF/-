"""
PopupRenderMixin — 浮窗渲染方法

从 popup/view.py 拆出,作为 Mixin 注入 PopupView。
所有方法依赖 self._detail / self._C / self._linked_frame 等属性,
这些属性由 PopupView.__init__ / build 负责初始化。
"""
import re
import tkinter as tk

from ..widgets import apply_highlight, attach_code_links


class PopupRenderMixin:
    """渲染相关方法,注入 PopupView。"""

    # ────────────────────────────────────────────
    # 联动股 grid 正则 (类属性)
    # ────────────────────────────────────────────
    # 修法 v10.1: 同时支持全角 （） U+FF08/U+FF09 和半角 () U+0028/U+0029
    # 原因: 千帆返回的内容里两种都存在,半角是模型自己的,全角通常是
    #       中文输入法或人工编辑。只匹配半角会漏掉一半数据。
    _LINK_RE = re.compile(
        r'([\u4e00-\u9fa5A-Z][\u4e00-\u9fa5A-Z0-9·\*]{1,7})'
        r'\s*[(\uff08]\s*(\d{6})\s*[)\uff09]'
    )

    # ════════════════════════════════════════════════
    # 标题 / Follow 按钮
    # ════════════════════════════════════════════════
    def update_title(self, code, name, follow_mode):
        """根据当前股 + follow 状态更新标题栏文字。"""
        suffix = "  📥 跟随同花顺" if follow_mode else ""
        if name or code:
            text = "📊  {} ({}){}".format(name or "", code or "", suffix)
        else:
            text = "📊  股票详情" + suffix
        try:
            self._title_label.config(text=text)
        except Exception:
            pass

    def update_follow_button(self, follow_mode):
        """切 follow 后刷新按钮颜色和文字。"""
        C = self._C
        try:
            if follow_mode:
                self._btn_follow.config(
                    text="● 跟随",
                    bg=C['green'], fg='#ffffff')
            else:
                self._btn_follow.config(
                    text="○ 跟随",
                    bg='#ffffff', fg=C['dim'])
        except Exception:
            pass

    def update_pin_button(self, topmost):
        """切置顶后刷新按钮。"""
        C = self._C
        self._topmost_state = topmost
        try:
            self._btn_pin.config(
                text="📌" if topmost else "📎",
                fg=C['accent'] if topmost else C['dim'])
        except Exception:
            pass

    # ════════════════════════════════════════════════
    # 行情渲染
    # ════════════════════════════════════════════════
    def show_loading_quote(self, code, name):
        """show() 开头: 立即把价格/涨跌清成"加载中"状态。"""
        C = self._C
        try:
            self._name_lbl.config(text=name or "—")
            self._code_lbl.config(text="(" + (code or "") + ")")
            self._price_lbl.config(text="加载中…", fg=C['dim'])
            self._chg_lbl.config(text="", fg=C['dim'])
            self._quote_time_lbl.config(text="")
        except Exception:
            pass

    def render_quote(self, info):
        """info 是 api_client 返回的 dict 或 None。"""
        C = self._C
        if not info:
            try:
                self._price_lbl.config(text="—", fg=C['dim'])
                self._chg_lbl.config(text="无行情", fg=C['dim'])
            except Exception:
                pass
            return
        chg = info.get('change_pct', 0)
        try:
            chg = float(chg)
        except (TypeError, ValueError):
            chg = 0.0
        if chg > 0:
            color = C['red']; sign = "+"; arrow = "▲"
        elif chg < 0:
            color = C['green']; sign = ""; arrow = "▼"
        else:
            color = C['dim']; sign = ""; arrow = "─"
        try:
            self._price_lbl.config(text="{:.2f}".format(info.get('price', 0)),
                                    fg=color)
            self._chg_lbl.config(text="{}  {}{:.2f}%".format(arrow, sign, chg),
                                  fg=color)
            self._quote_time_lbl.config(text=info.get('time', ''))
        except Exception:
            pass

    def update_name_label(self, name):
        """行情拉回来时若发现 name 比浮窗已有的更准,刷新一下。"""
        try:
            self._name_lbl.config(text=name)
        except Exception:
            pass

    # ════════════════════════════════════════════════
    # 日期下拉
    # ════════════════════════════════════════════════
    def populate_date_combo(self, options):
        """options: list[str]。空列表 → 清空。"""
        try:
            self._date_combo['values'] = options
            if options:
                self._date_combo.current(0)
            else:
                self._date_combo.set("")
        except Exception:
            pass

    def current_date_index(self):
        """当前下拉选中的索引,-1 表示无选中。"""
        try:
            return self._date_combo.current()
        except Exception:
            return -1

    # ════════════════════════════════════════════════
    # 分析记录渲染
    # ════════════════════════════════════════════════
    def render_record(self, rec, app, main_code):
        """
        把一条分析记录画到 detail Text。
        app + main_code 是给 attach_code_links 用的 (旧 widgets 模块需要)。
        """
        T = self._detail
        C = self._C
        try:
            T.config(state='normal'); T.delete('1.0', 'end')
        except Exception:
            return

        def w(txt, tg=None):
            if tg:
                T.insert('end', txt, tg)
            else:
                T.insert('end', txt)

        w("📅 {}  {}".format(rec.get('date', ''), rec.get('time', '')), 'dim')
        if rec.get('starred'):
            w("  ⭐ 已加星", 'star')
        if rec.get('success'):
            w("  ✅ 分析成功", 'green')
        else:
            w("  ❌ 分析失败", 'red')
        w("\n")
        cat = rec.get('category', '')
        if cat:
            w("🏷️  细分标签:  ", 'dim')
            w(" {} ".format(cat), 'category')
            w("\n")
        tags = rec.get('tags', [])
        if tags:
            w("📌  自定义标签: ", 'dim')
            w("、".join(tags) + "\n", 'star')
        nd = rec.get('next_day')
        if nd and isinstance(nd, dict):
            pct = nd.get('change_pct')
            if pct is not None:
                try:
                    pct = float(pct)
                except (TypeError, ValueError):
                    pct = 0
                tag = 'up' if pct > 0 else ('down' if pct < 0 else 'flat')
                arrow = '▲' if pct > 0 else ('▼' if pct < 0 else '─')
                sign = '+' if pct > 0 else ''
                w("📈 次日表现 ({}):  ".format(nd.get('date', '')), 'dim')
                w("{} {}{:.2f}%\n".format(arrow, sign, pct), tag)
        note = rec.get('note', '')
        if note:
            w("📝  备注:  ", 'dim')
            w(note + "\n", 'star')
        w("─" * 40 + "\n", 'dim')
        content = rec.get('content', '') or '(无内容)'
        w(content + "\n")
        try:
            apply_highlight(T, keep_editable=True)
        except Exception:
            pass
        try:
            T.config(state='disabled')
        except Exception:
            pass
        # 浮窗内的代码 → scope='popup',点击只推送不刷浮窗
        try:
            attach_code_links(T, app, main_code=main_code, scope='popup')
        except Exception:
            pass
        try:
            T.see('1.0')
        except Exception:
            pass

    def render_no_history(self):
        T = self._detail
        try:
            T.config(state='normal'); T.delete('1.0', 'end')
            T.insert('end', "\n\n  📭  本地暂无该股票的历史分析记录。\n\n", 'dim')
            T.insert('end', "  浮窗会等候你在主程序里分析这只股票后自动刷新。\n\n", 'dim')
            T.config(state='disabled')
        except Exception:
            pass

    # ════════════════════════════════════════════════
    # 联动股 grid
    # ════════════════════════════════════════════════
    def render_linked_grid(self, content, cur_code, on_link_click, on_triple_click=None):
        """
        从 content 抓"名字(代码)"对,去重 + 排除主股 + 最多 6 个,
        排成 2×3 grid。点击代码触发 on_link_click(code, name)。
        三击代码触发 on_triple_click(code, name)。
        """
        # 清掉旧 cell
        try:
            for child in self._linked_frame.winfo_children():
                child.destroy()
        except Exception:
            return
        if not content:
            return
        cur = (cur_code or "").zfill(6)
        seen = {cur} if cur else set()
        items = []
        for name, code in self._LINK_RE.findall(content):
            if code in seen:
                continue
            seen.add(code)
            items.append((name, code))
            if len(items) >= 6:
                break
        if not items:
            return
        C = self._C
        for i, (name, code) in enumerate(items):
            row = i // 2
            col = i % 2
            cell = tk.Frame(self._linked_frame, bg=C['card'])
            cell.grid(row=row, column=col, sticky='w',
                      padx=(0, 18), pady=1)
            tk.Label(cell, text=name,
                     font=('微软雅黑', 9),
                     bg=C['card'], fg=C['text']).pack(side='left')
            link = tk.Label(
                cell, text=" (" + code + ")",
                font=('微软雅黑', 9, 'underline'),
                bg=C['card'], fg=C['accent'],
                cursor='hand2')
            link.pack(side='left')
            # 闭包陷阱: 用默认参数把 code/name 锁住
            def _on_link_press(e, l=link, c=code, n=name):
                l.config(
                    fg=C['accent'], font=('微软雅黑', 11, 'bold underline'))
                l.after(80, lambda: l.config(
                    fg=C['accent'], font=('微软雅黑', 9, 'underline')))
                on_link_click(c, n)
                # 三击检测：通知 Controller 处理
                if on_triple_click:
                    on_triple_click(c, n)

            link.bind('<Button-1>', _on_link_press)
            link.bind('<Enter>',
                      lambda e, l=link: l.config(fg=C['accent']))
            link.bind('<Leave>',
                      lambda e, l=link: l.config(fg=C['accent']))

    # ════════════════════════════════════════════════
    # AI 按钮状态切换 (临时反馈)
    # ════════════════════════════════════════════════
    def flash_ai_button_sent(self):
        """点了 AI 分析 → 临时改文字 → 2s 后恢复。"""
        try:
            self._btn_ai.config(text="  ✅ 已发送到主程序  ")
            self._root.after(
                2000,
                lambda: self._btn_ai.config(text="  📋 立即 AI 分析  "))
        except Exception:
            pass
