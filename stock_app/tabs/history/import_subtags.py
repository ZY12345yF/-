"""历史记录 Tab — Excel 导入细分标签 Mixin"""
import json
import re as _re
import shutil
import tkinter as tk
from tkinter import messagebox, filedialog

from ...bus import bus, Events


class ImportSubtagsMixin:
    """从 Excel 一键导入细分标签到当日历史记录"""

    # ════════════════════════════════════════════════
    # 🆕 v10.4：从 Excel 一键导入细分标签
    # ════════════════════════════════════════════════
    # 改进点：
    #   - 标签存储：只写 rec['category']，不再往 content 里塞文本
    #   - 冲突处理：用户可选"跳过已有标签"或"覆盖已有标签"
    #   - 向后兼容：旧版 content 里有【细分标签】标记的也识别为"已有标签"
    # ════════════════════════════════════════════════

    # ── 弹窗：选跳过还是覆盖 ─────────────────────────
    TAG_MARKER = "【细分标签】"

    def _ask_import_mode(self):
        """弹对话框让用户选择"跳过已有标签"还是"覆盖已有标签"。返回 True=跳过, False=覆盖。"""
        from ...core.theme import get as theme
        C = theme()
        result = {'skip': True}

        root = self.winfo_toplevel()
        win = tk.Toplevel(root)
        win.title("导入细分标签")
        win.configure(bg=C['panel'], borderwidth=0)
        win.overrideredirect(True)
        win.attributes('-topmost', True)
        # 居中在当前窗口附近
        try:
            rx, ry = root.winfo_rootx(), root.winfo_rooty()
            win.geometry("+{}+{}".format(rx + 200, ry + 200))
        except Exception:
            win.geometry("+300+200")

        def _close(skip):
            result['skip'] = skip
            win.destroy()

        # 标题
        tk.Label(win, text="标签冲突处理", font=('微软雅黑', 12, 'bold'),
                 bg=C['panel'], fg=C['text']).pack(padx=24, pady=(18, 4))

        tk.Label(win, text="已有标签的记录如何处理？",
                 font=('微软雅黑', 9), bg=C['panel'], fg=C['dim']).pack(padx=24, pady=(0, 12))

        btn_frame = tk.Frame(win, bg=C['panel'])
        btn_frame.pack(padx=24, pady=(0, 18))

        btn_skip = tk.Button(
            btn_frame, text="  ⏭ 跳过已有标签  ",
            font=('微软雅黑', 10, 'bold'), bg=C['accent'], fg='white',
            relief='flat', cursor='hand2', padx=16, pady=6,
            command=lambda: _close(True))
        btn_skip.pack(side='left', padx=(0, 10))

        btn_over = tk.Button(
            btn_frame, text="  ✏️ 覆盖已有标签  ",
            font=('微软雅黑', 10, 'bold'), bg=C['yellow'], fg='#111',
            relief='flat', cursor='hand2', padx=16, pady=6,
            command=lambda: _close(False))
        btn_over.pack(side='left')

        # 等待用户操作
        win.grab_set()
        win.wait_window()

        return result.get('skip', True)

    def _record_has_tag(self, rec):
        """判断记录是否已有细分标签（category 字段优先，fallback 检查 content）"""
        if rec.get('category'):
            return True
        # 向后兼容：旧版 content 里嵌入的标签
        content = (rec.get('content') or '')[:200]
        return self.TAG_MARKER in content

    def _extract_tag_from_content(self, rec):
        """从旧版 content 里提取【细分标签】：xxx 的值，返回提取到的标签或空字符串。"""
        content = rec.get('content') or ''
        m = _re.search(r'【细分标签】[：:]\s*(.+?)(?:\n|$)', content)
        if m:
            return m.group(1).strip()
        return ''

    def _import_subtags_from_excel(self):
        """从 Excel 一键导入细分标签到当日历史记录"""
        from pathlib import Path

        # 1. 确认当前选中的日期
        date_key = (self.date_var.get() or "").strip()
        if not date_key:
            messagebox.showwarning(
                "未选日期",
                "请先在左上角的日期下拉框里选一个日期，导入会针对那天的历史记录。")
            return
        # date_combo 显示的日期可能含空格/年月日格式，做下归一化（拿前 8 位数字）
        m = _re.search(r'(\d{8})', date_key)
        if not m:
            # 也支持 2026-05-13 这种
            m = _re.search(r'(\d{4})\D(\d{2})\D(\d{2})', date_key)
            if m:
                date_key = m.group(1) + m.group(2) + m.group(3)
            else:
                messagebox.showerror(
                    "日期格式不对",
                    "无法从 {!r} 中识别 8 位日期。".format(date_key))
                return
        else:
            date_key = m.group(1)

        # 2. 选冲突处理模式（跳过 or 覆盖）
        skip_existing = self._ask_import_mode()

        # 3. 选 Excel 文件
        mode_text = "跳过已有标签" if skip_existing else "覆盖已有标签"
        excel_path = filedialog.askopenfilename(
            title="选择 Excel 文件（G 列 = 细分标签，按股票名称匹配）—— {}".format(mode_text),
            filetypes=[("Excel 文件", "*.xlsx"), ("Excel 旧版", "*.xls"), ("所有文件", "*.*")])
        if not excel_path:
            return

        # 4. 读 Excel
        try:
            import pandas as pd
        except ImportError:
            messagebox.showerror("缺少依赖", "需要 pandas: pip install pandas openpyxl")
            return
        try:
            df = pd.read_excel(excel_path)
        except Exception as e:
            messagebox.showerror("读取失败", "Excel 打不开:\n{}".format(e))
            return

        if '股票名称' not in df.columns:
            messagebox.showerror(
                "格式错误",
                "Excel 中必须包含 '股票名称' 列（当前列：{}）".format(list(df.columns)))
            return
        if df.shape[1] < 7:
            messagebox.showerror(
                "格式错误",
                "Excel 至少要有 7 列（G 列 = 细分标签），当前只有 {} 列".format(df.shape[1]))
            return

        # 5. 定位历史文件
        from ...core.paths import DIRS
        history_file = Path(DIRS["history"]) / "{}.json".format(date_key)
        if not history_file.exists():
            messagebox.showerror(
                "找不到历史文件",
                "{}\n\n请确认 {} 这一天有过分析记录。".format(history_file, date_key))
            return

        # 6. 备份
        try:
            backup = history_file.with_suffix(".json.bak")
            shutil.copy(history_file, backup)
        except Exception as e:
            if not messagebox.askyesno(
                    "备份失败",
                    "无法备份原文件:\n{}\n\n仍要继续吗？".format(e)):
                return

        # 7. 读历史 JSON
        try:
            with open(history_file, 'r', encoding='utf-8') as f:
                records = json.load(f)
        except Exception as e:
            messagebox.showerror("历史文件损坏", str(e))
            return

        # 8. 建立 名称 → 细分标签 映射（G 列 = 第 7 列，索引 6）
        import pandas as _pd
        sub_series = df.iloc[:, 6]
        name_to_sub = {}
        for idx, row in df.iterrows():
            name = str(row['股票名称']).strip()
            sub_val = sub_series.iloc[idx] if hasattr(sub_series, 'iloc') else sub_series[idx]
            sub = str(sub_val).strip() if _pd.notna(sub_val) else ''
            if name and sub and sub.lower() != 'nan':
                name_to_sub[name] = sub

        if not name_to_sub:
            messagebox.showwarning(
                "Excel 里没数据",
                "G 列里一个有效的细分标签都没找到。")
            return

        # 9. 应用到历史记录
        #    只写 category 字段，不改 content
        updated = 0
        skipped_has_tag = 0
        skipped_no_match = 0
        skipped_log = []

        for rec in records:
            name = (rec.get('name', '') or '').strip()
            if name not in name_to_sub:
                skipped_no_match += 1
                continue
            sub = name_to_sub[name]

            # 判断是否已有标签
            if self._record_has_tag(rec):
                if skip_existing:
                    # 跳过模式：已有标签的不改
                    skipped_has_tag += 1
                    continue
                else:
                    # 覆盖模式：更新为新标签
                    rec['category'] = sub
                    updated += 1
                    skipped_log.append("↻ {} → {}".format(name, sub))
                    continue

            # 没有标签：直接写 category
            rec['category'] = sub
            updated += 1
            skipped_log.append("✓ {} → {}".format(name, sub))

        # 10. 写回
        if updated == 0:
            reason = "已有标签（跳过模式）" if skip_existing else "全部覆盖模式下未匹配到新标签"
            messagebox.showinfo(
                "没有需要更新的记录",
                "Excel 里有 {} 个名字 → 标签映射，但：\n\n"
                "  · {} 条 {}（跳过）\n"
                "  · {} 条名称对不上（跳过）\n"
                "  · 0 条新增\n\n"
                "已备份到 {}".format(
                    len(name_to_sub), skipped_has_tag, reason,
                    skipped_no_match,
                    backup.name if 'backup' in locals() else '(未备份)'))
            return

        try:
            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump(records, f, ensure_ascii=False, indent=2)
        except Exception as e:
            messagebox.showerror("写入失败", str(e))
            return

        # 11. 完成提示 + 刷新当前 Tab
        messagebox.showinfo(
            "导入完成",
            "✅ 成功更新 {} 条记录（{}模式）\n"
            "⚠ 跳过 {} 条（已有标签）\n"
            "ℹ 跳过 {} 条（Excel 中没有匹配名）\n\n"
            "已备份到 {}\n\n"
            "页面将自动刷新。".format(
                updated, "跳过" if skip_existing else "覆盖",
                skipped_has_tag, skipped_no_match,
                backup.name if 'backup' in locals() else '(未备份)'))
        # 触发历史更新事件，让本 Tab + 其它 Tab 都刷新
        try:
            bus.emit(Events.HISTORY_UPDATED)
        except Exception:
            pass
        try:
            self._load_day()
        except Exception:
            pass
