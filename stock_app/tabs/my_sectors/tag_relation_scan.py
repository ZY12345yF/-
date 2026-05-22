"""
标签关联度 - 扫描与图表 Mixin
v9.9.8：从 tag_relation.py 拆出
"""
import threading

from ...core import tag_relation as tr
from ...bus import state


class TagRelationScanMixin:
    """_tag_rescan / _tag_show_relations / _tag_draw_chart 等扫描与图表方法"""

    # ── 扫描与图表逻辑 ──
    def _tag_rescan(self):
        try:
            mf = int(self._tag_min_freq.get())
        except Exception:
            mf = 1
        # 🆕 读回溯天数：可选 "1/3/7/14/30/全部"
        d_raw = (self._tag_days.get() if hasattr(self, '_tag_days') else '7').strip()
        if d_raw in ("", "全部", "all", "0"):
            days = 0   # 全部历史
        else:
            try: days = int(d_raw)
            except Exception: days = 7
        self._tag_stat.set("⏳ 扫描中...（{}）".format(
            "全部历史" if days == 0 else "近 {} 天".format(days)))
        def _do():
            tf, co, rec = tr.build_cooccurrence(days=days, min_freq=mf)
            def _upd():
                self._tag_freq = tf; self._cooccur = co; self._tag_records = rec
                if not tf:
                    self._tag_stat.set("⚠️ 未找到标签（请确保历史中有【细分标签】或概念关键词）")
                    self._tag_combo['values'] = []
                    return
                tags_sorted = sorted(tf.items(), key=lambda x: -x[1])
                self._tag_combo['values'] = [
                    "{} ({}次)".format(t, c) for t, c in tags_sorted]
                self._tag_stat.set("✅ 扫描完成：{} 个标签，{} 对共现（{}）".format(
                    len(tf), len(co),
                    "全部历史" if days == 0 else "近 {} 天".format(days)))
                if self._tag_combo['values'] and not self._tag_var.get():
                    self._tag_combo.current(0)
                    self._tag_show_relations()
            state.ui_queue.put(_upd)
        threading.Thread(target=_do, daemon=True).start()

    # 🆕 B2：双击关联标签 → 切换该标签为新目标
    def _tag_jump_to_selected(self):
        sel = self._tag_tree.selection()
        if not sel: return
        idx = self._tag_tree.index(sel[0])
        if idx >= len(self._cur_rels): return
        new_tag = self._cur_rels[idx]['tag']
        freq = self._tag_freq.get(new_tag, 0)
        target_label = "{} ({}次)".format(new_tag, freq)
        # 在 combobox 候选里找
        for i, v in enumerate(self._tag_combo['values']):
            if v == target_label:
                self._tag_combo.current(i)
                break
        else:
            # 不在候选里（频次为 0），直接 set
            self._tag_var.set(target_label)
        self._tag_show_relations()

    def _tag_get_cur(self):
        v = self._tag_var.get()
        if not v: return None
        return v.split(" (")[0]

    def _tag_show_relations(self):
        tag = self._tag_get_cur()
        if not tag: return
        self._cur_tag = tag
        rels = tr.compute_relations(tag, self._tag_freq, self._cooccur, top_n=20)
        self._cur_rels = rels
        for i in self._tag_tree.get_children():
            self._tag_tree.delete(i)
        for r in rels:
            score = r['score']
            tg = 'high' if score >= 0.4 else ('mid' if score >= 0.2 else 'low')
            self._tag_tree.insert('', 'end', values=(
                r['tag'], "{:.3f}".format(score), r['support'],
                r['self_freq'], r['other_freq']), tags=(tg,))
        self._tag_draw_chart(tag, rels[:12])
        self._tag_render_overview(tag, rels)
        # 🆕 v9.4：自动切到"详情 Tab"，让概览中的个股清单直接可见
        try:
            self._tag_sub_nb.select(0)
        except Exception:
            pass

    def _tag_draw_chart(self, target, rels):
        C = self.C
        self._tag_ax.clear()
        if not rels:
            self._tag_ax.text(0.5, 0.5, "无关联数据",
                              transform=self._tag_ax.transAxes,
                              ha='center', va='center', color=C['dim'])
            self._tag_canvas.draw(); return
        labels = [r['tag'] for r in rels][::-1]
        scores = [r['score'] for r in rels][::-1]
        sups   = [r['support'] for r in rels][::-1]
        colors = [C['red'] if s >= 0.4 else (C['yellow'] if s >= 0.2 else C['accent'])
                  for s in scores]
        self._tag_fig.patch.set_facecolor(C['bg'])
        self._tag_ax.set_facecolor(C['card'])
        bars = self._tag_ax.barh(labels, scores, color=colors, edgecolor='none')
        for bar, sup in zip(bars, sups):
            self._tag_ax.text(bar.get_width() + 0.005,
                              bar.get_y() + bar.get_height()/2,
                              " {} 次".format(sup),
                              va='center', fontsize=8, color=C['text'])
        self._tag_ax.set_xlabel("Jaccard 关联度", color=C['dim'], fontsize=9)
        self._tag_ax.set_title("「{}」 关联标签 Top {}".format(target, len(rels)),
                                color=C['text'], fontsize=11, pad=10)
        self._tag_ax.tick_params(colors=C['text'])
        for spine in self._tag_ax.spines.values():
            spine.set_color(C['border'])
        self._tag_ax.grid(axis='x', alpha=0.2, color=C['border'])
        self._tag_fig.tight_layout()
        self._tag_canvas.draw()

    def _tag_render_overview(self, tag, rels):
        T = self._tag_detail
        T.config(state='normal'); T.delete('1.0', 'end')
        def w(text, tg=None):
            if tg: T.insert('end', text, tg)
            else:  T.insert('end', text)

        # ─── 标题区（加大间距 + 三栏汇总）───
        freq = self._tag_freq.get(tag, 0)
        recs = self._tag_records.get(tag, [])
        codes_set = {(r.get('name',''), r.get('code','')) for r in recs}
        codes_set.discard(('',''))

        w("\n  🕸️  ", 'h1bold')
        w("{}\n".format(tag), 'h1bold')
        w("    频次 ", 'dim'); w("{}".format(freq), 'h2')
        w("    涉及个股 ", 'dim'); w("{}".format(len(codes_set)), 'h2')
        w("    关联标签 ", 'dim'); w("{}\n".format(len(rels)), 'h2')
        w("  " + "━" * 48 + "\n\n", 'dim')

        # ─── 🆕 本标签下的个股清单（需求 3）───
        w("  💎  本标签下的个股 ", 'h2')
        w("({} 只)\n".format(len(codes_set)), 'dim')
        if codes_set:
            # 按代码 + 最近日期排序
            by_code = {}
            for r in recs:
                key = (r.get('name',''), r.get('code',''))
                if key == ('',''): continue
                d = r.get('date','')
                if key not in by_code or d > by_code[key]:
                    by_code[key] = d
            sorted_stocks = sorted(by_code.items(),
                                   key=lambda x: (-len(x[1]), x[0][1]))
            line_items = []
            for (name, code), last_date in sorted_stocks[:30]:
                short_d = last_date[4:8] if len(last_date) >= 8 else last_date
                line_items.append("{}({})·{}".format(name, code, short_d))
            # 每行 2 项
            for i in range(0, len(line_items), 2):
                row = "    ".join(line_items[i:i+2])
                w("    {}\n".format(row), 'concept')
            if len(sorted_stocks) > 30:
                w("    ……还有 {} 只\n".format(len(sorted_stocks) - 30), 'dim')
        else:
            w("    （无个股数据）\n", 'dim')
        w("\n")

        # ─── Top 关联标签（带 emoji 强度徽章）───
        w("  📊  Top 关联标签\n", 'h2')
        for i, r in enumerate(rels[:12], 1):
            stag = 'red' if r['score'] >= 0.4 else ('purple' if r['score'] >= 0.2 else 'dim')
            badge = "🔥" if r['score'] >= 0.4 else ("⭐" if r['score'] >= 0.2 else "💤")
            w("    {} {:>2}. ".format(badge, i), 'dim')
            w("{:<14s}".format(r['tag']))
            w("  Jaccard ", 'dim')
            w("{:.3f}".format(r['score']), stag)
            w("  共现 {} 次\n".format(r['support']), 'dim')

        w("\n  💡 点击左侧 → 看产业逻辑 · 双击 → 跳转到该标签\n", 'dim')
        T.config(state='disabled')

    def _tag_show_rel_detail(self):
        sel = self._tag_tree.selection()
        if not sel or not self._cur_tag: return
        idx = self._tag_tree.index(sel[0])
        if idx >= len(self._cur_rels): return
        rel = self._cur_rels[idx]
        self._cur_other_tag = rel['tag']

        T = self._tag_detail
        T.config(state='normal'); T.delete('1.0', 'end')
        def w(text, tg=None):
            if tg: T.insert('end', text, tg)
            else:  T.insert('end', text)

        w("\n  🔗  ", 'h1bold')
        w("{}".format(self._cur_tag), 'h1bold')
        w("  ⇄  ", 'dim')
        w("{}\n".format(rel['tag']), 'h1bold')
        w("  " + "━" * 48 + "\n\n", 'dim')

        # ── 关联度 chip ──
        stag = 'red' if rel['score'] >= 0.4 else ('purple' if rel['score'] >= 0.2 else 'dim')
        label = ("🔥 强关联" if rel['score'] >= 0.4 else
                 ("⭐ 中等" if rel['score'] >= 0.2 else "💤 弱"))
        w("    Jaccard 关联度  ", 'dim')
        w("{:.3f}".format(rel['score']), stag)
        w("    ", 'dim')
        w(label + "\n", stag)
        w("    共现 ", 'dim'); w("{}".format(rel['support']), 'h2')
        w("    {} 单独 ".format(self._cur_tag), 'dim'); w("{}".format(rel['self_freq']), 'h2')
        w("    {} 单独 ".format(rel['tag']), 'dim'); w("{}\n\n".format(rel['other_freq']), 'h2')

        # ── 共现股票 ──
        co = tr.co_stocks(self._cur_tag, rel['tag'], self._tag_records)
        if co:
            w("  💎  同时具备这两个标签的股票 ", 'h2')
            w("({} 只)\n".format(len(co)), 'dim')
            line_items = ["{}({})".format(n, c) for n, c in co[:24]]
            for i in range(0, len(line_items), 2):
                row = "    ".join(line_items[i:i+2])
                w("    {}\n".format(row), 'concept')
            if len(co) > 24:
                w("    ……还有 {} 只\n".format(len(co) - 24), 'dim')
            w("\n")

        # ── AI 推理 ──
        cache = self._load_pair_cache()
        key = self._pair_key(self._cur_tag, rel['tag'])
        if key in cache:
            w("  🤖  AI 推理（缓存）\n", 'h2')
            w(cache[key]['analysis'] + "\n", 'ai')
            w("\n  生成时间: " + cache[key].get('time', ''), 'dim')
        else:
            w("  🤖  暂无 AI 推理，点击上方「🤖 推理这对关联」按钮生成\n", 'dim')

        T.config(state='disabled')
