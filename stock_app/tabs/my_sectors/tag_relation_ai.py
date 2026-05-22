"""
标签关联度 - AI 推理与聚类 Mixin
v9.9.8：从 tag_relation.py 拆出
"""
import json
import threading
import tkinter as tk
from tkinter import messagebox

from ...widgets import styled_btn
from ...core import config as cfg_mod, tag_relation as tr
from ...bus import state


class TagRelationAIMixin:
    """_tag_ai_pair / _tag_bulk_analyze / _edit_bulk_prompt 等 AI 方法"""

    # ── AI pair cache ──
    def _pair_cache_path(self):
        from ...core.paths import DIRS
        from pathlib import Path
        return Path(DIRS["config"]) / "tag_relation_ai_cache.json"

    def _load_pair_cache(self):
        p = self._pair_cache_path()
        if not p.exists(): return {}
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _save_pair_cache(self, cache):
        p = self._pair_cache_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")

    def _pair_key(self, a, b):
        return "||".join(sorted([a, b]))

    def _tag_ai_pair(self):
        if not self._cur_tag or not self._cur_other_tag:
            messagebox.showinfo("提示", "请先选中一个关联标签"); return
        a, b = self._cur_tag, self._cur_other_tag
        cache = self._load_pair_cache()
        key = self._pair_key(a, b)
        if key in cache:
            if not messagebox.askyesno("已有缓存", "重新生成？"):
                return

        # 🆕 读取专属配置
        bulk_url = self._bulk_url.get().strip()
        bulk_key = self._bulk_key.get().strip()
        bulk_model = cfg_mod.display_name_to_model_id(self._bulk_model_var.get().strip())
        if not bulk_key:
            messagebox.showwarning("无 Key", "请在上方填写聚类专用 API Key"); return
        bulk_cfg = {"api_url": bulk_url, "model": bulk_model, "timeout": 60}

        co = tr.co_stocks(a, b, self._tag_records)
        co_count = self._cooccur.get(tuple(sorted([a, b])), 0)
        freq_a = self._tag_freq.get(a, 0)
        freq_b = self._tag_freq.get(b, 0)
        self._tag_ai_status.set("🤖 推理中...")

        def _do():
            result, ok = tr.query_ai_relation(
                a, b, co, freq_a, freq_b, co_count, bulk_key, bulk_cfg)  # 🆕 使用专属配置
            from datetime import datetime
            if ok:
                cache[key] = {
                    "tag_a": a, "tag_b": b, "analysis": result,
                    "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "co_count": co_count,
                }
                self._save_pair_cache(cache)
            def _done():
                self._tag_ai_status.set("✅ 完成" if ok else "❌ 失败")
                self.app.root.after(3000, lambda: self._tag_ai_status.set(""))
                self._tag_show_rel_detail()
            state.ui_queue.put(_done)
        threading.Thread(target=_do, daemon=True).start()

    def _tag_clear_pair_cache(self):
        if not self._cur_tag or not self._cur_other_tag: return
        cache = self._load_pair_cache()
        key = self._pair_key(self._cur_tag, self._cur_other_tag)
        if key in cache:
            del cache[key]
            self._save_pair_cache(cache)
            self._tag_show_rel_detail()

    # ════════════════════════════════════════════════
    # 🆕 批量 AI 聚类（使用专属配置和提示词）
    # ════════════════════════════════════════════════
    def _edit_bulk_prompt(self):
        """编辑批量分析的提示词"""
        C = self.C
        dlg = tk.Toplevel(self.app.root)
        dlg.title("📝 编辑 AI 聚类专属提示词")
        dlg.geometry("760x560")
        dlg.configure(bg=C['bg'])
        dlg.transient(self.app.root)

        tk.Label(dlg, text="自定义批量聚类提示词",
                 font=('微软雅黑', 11, 'bold'),
                 bg=C['bg'], fg=C['accent']).pack(pady=(12, 4))
        tk.Label(dlg,
                 text="提示词中必须包含 {tag_list} 和 {cooccur_list} 占位符，系统会自动替换为扫描数据",
                 font=('微软雅黑', 9), bg=C['bg'], fg=C['yellow']).pack()

        text = tk.Text(dlg, font=('Consolas', 10), wrap='word',
                        bg=C['card'], fg=C['text'], insertbackground='white',
                        relief='flat', padx=8, pady=6, height=20, undo=True)
        text.pack(fill='both', expand=True, padx=24, pady=8)

        cur = tr.load_bulk_prompt_template()
        text.insert('1.0', cur)

        bb = tk.Frame(dlg, bg=C['bg']); bb.pack(fill='x', padx=24, pady=(0, 12))
        def _save():
            t = text.get('1.0', 'end-1c').strip()
            tr.save_bulk_prompt_template(t)
            messagebox.showinfo("已保存", "提示词已保存", parent=dlg)
            dlg.destroy()
        def _reset():
            if messagebox.askyesno("确认", "恢复为默认提示词？", parent=dlg):
                text.delete('1.0', 'end')
                text.insert('1.0', tr.DEFAULT_BULK_PROMPT)
        styled_btn(bb, "💾 保存并关闭", C['green'], _save, pady=8).pack(side='right', padx=(4, 0))
        styled_btn(bb, "↩️ 恢复默认", C['idle'], _reset, pady=8).pack(side='right')

    def _tag_bulk_analyze(self):
        if not self._tag_freq:
            messagebox.showinfo("提示", "请先点「重新扫描」"); return

        # 🆕 读取聚类专属 API 配置
        bulk_url = self._bulk_url.get().strip()
        bulk_key = self._bulk_key.get().strip()
        bulk_model_disp = self._bulk_model_var.get().strip()
        bulk_model = cfg_mod.display_name_to_model_id(bulk_model_disp)

        # 🌟 需求2：保存专属配置到全局设置
        self.app.cfg["tag_relation_api_settings"] = {
            "url": bulk_url, "key": bulk_key, "model_disp": bulk_model_disp
        }
        cfg_mod.save_config(self.app.cfg)

        if not bulk_key:
            messagebox.showwarning("无 Key", "请在上方填写聚类专用 API Key"); return

        bulk_cfg = {
            "api_url": bulk_url,
            "model": bulk_model,
            "timeout": 180,
            "max_tokens": 3000
        }

        if not messagebox.askyesno("确认",
                "将使用专属配置发送 AI 聚类请求：\n\n"
                "🌐 URL: {}\n"
                "🤖 Model: {}\n"
                "🔑 Key: {}...\n\n"
                "继续？".format(bulk_url[:50], self._bulk_model_var.get(), bulk_key[:15])):
            return

        prompt_template = tr.load_bulk_prompt_template()

        T = self._tag_detail
        T.config(state='normal'); T.delete('1.0', 'end')
        T.insert('end', "🤖 AI 批量聚类中...\n", 'h1')
        T.config(state='disabled')
        self._tag_ai_status.set("🤖 分析中（耗时较长）...")

        def _do():
            result, ok = tr.query_ai_bulk_clustering(
                self._tag_freq, self._cooccur, bulk_key,  # 🆕 使用专属 Key
                bulk_cfg,                                   # 🆕 使用专属 Cfg
                custom_prompt=prompt_template)

            from datetime import datetime
            try:
                from ...core.paths import DIRS
                from pathlib import Path
                p = Path(DIRS["config"]) / "tag_relation_bulk_result.txt"
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(
                    "生成时间: {}\nModel: {}\n\n{}".format(
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        self._bulk_model_var.get(), result),
                    encoding="utf-8")
            except Exception:
                pass

            def _done():
                T.config(state='normal')
                T.delete('1.0', 'end')
                T.insert('end', "🤖  AI 批量聚类结果\n", 'h1')
                T.insert('end', "━" * 50 + "\n\n", 'dim')
                T.insert('end', result if ok else "❌ 分析失败: " + result)
                T.insert('end', "\n\n" + "━" * 50 + "\n", 'dim')
                T.insert('end', "✅ 结果已保存到 data/config/tag_relation_bulk_result.txt\n", 'dim')
                T.config(state='disabled')
                self._tag_ai_status.set("✅ 完成" if ok else "❌ 失败")
                self.app.root.after(5000, lambda: self._tag_ai_status.set(""))
            state.ui_queue.put(_done)
        threading.Thread(target=_do, daemon=True).start()
