"""
HistoryService — 历史 Tab 的业务逻辑层

把 history_tab.py / history/detail_view.py 里混合了 UI 的业务方法
抽出为纯业务函数,UI 部分留给调用方。

收口的业务点 (来源 → 本类):

  history_tab._do_batch_requery        → BatchRequeryService.requery
  history_tab._export_daily_quotes     → DailyQuotesExporter.export
  detail_view._do_save_content_to_history → ContentEditService.save_from_text
  history_tab._export_excel/_html      → StarredExportService.{to_excel, to_html}

设计原则 (文档 八·服务层规范):
  • 不 import tkinter / messagebox / state.ui_queue
  • 副作用通过 callback 通知调用方
  • 异常往外抛,由调用方决定怎么展示
  • 文件 I/O 通过 Repository 进行
  • 外部 API 通过 integrations (现在还在 core/api_client) 进行
"""
from datetime import datetime
import time
import logging

from ..core import api_client, paths
from ..core import history as hist_mod          # repository 内部依然用它
from ..repositories import history_repo
from ..infrastructure.logging import get_logger

log = get_logger(__name__)


# ════════════════════════════════════════════════════════
# 批量重查行情
# ════════════════════════════════════════════════════════
class BatchRequeryService:
    """
    对某一天的全部历史记录批量重新查询当前行情,把"实时行情块"覆盖写回每条
    记录的 content 字段。

    完全跟 UI 解耦:进度反馈走 on_progress(i, total, name) 回调;
    结束统计直接 return,调用方自己决定弹框还是 toast。
    """

    SEP = "─" * 40
    RT_MARKER = "📊 同逻辑联动标的  实时行情(腾讯财经)"
    # 单次查询后 sleep 多少秒,避免被限流
    SLEEP_BETWEEN = 0.3
    SLEEP_AFTER_FAIL = 0.5

    def __init__(self, repo=None):
        self._repo = repo or history_repo

    def requery(self, date_key, records, on_progress=None):
        """
        批量查询行情并写回。

        Args:
            date_key:   '20260513'
            records:    list[dict] (从 repo.load(date_key) 得到的全集)
            on_progress: 可选,签名 on_progress(idx, total, name)
                        在 worker 线程触发,UI 派回主线程是调用方的事

        Returns:
            dict: {'ok': int, 'fail': int, 'skip': int}
        """
        ok = fail = skip = 0
        total = len(records)
        for i, r in enumerate(records, 1):
            name = r.get('name', '')
            if on_progress is not None:
                try:
                    on_progress(i, total, name)
                except Exception:
                    log.exception("on_progress callback failed")

            content = r.get('content', '') or ''
            content = self._strip_existing_rt_block(content)

            codes = self._collect_codes_with_main_first(r, content)
            if not codes:
                skip += 1
                continue

            try:
                data = api_client.fetch_change_pct(codes)
            except Exception:
                log.exception("fetch_change_pct failed")
                data = None
            if not data:
                fail += 1
                time.sleep(self.SLEEP_AFTER_FAIL)
                continue

            rec_main = str(r.get('code', '') or '').zfill(6)
            new_content = content + self._format_rt_block(data, rec_main)
            try:
                self._repo.update_record(date_key, r['id'], content=new_content)
                ok += 1
            except Exception:
                log.exception("update_record failed (%s)", r.get('id'))
                fail += 1
            time.sleep(self.SLEEP_BETWEEN)
        return {'ok': ok, 'fail': fail, 'skip': skip}

    # ── 私有 ──────────────────────────────────────
    def _strip_existing_rt_block(self, content):
        """若 content 已经带过实时行情块,把它砍掉,只保留分析正文。"""
        if self.RT_MARKER not in content:
            return content
        idx = content.rfind("\n\n" + self.SEP)
        if idx == -1:
            p = content.rfind(self.SEP)
            if p > 0:
                idx = content.rfind("\n", 0, p)
        if idx != -1:
            return content[:idx]
        return content

    def _collect_codes_with_main_first(self, record, content):
        """从 content 抽联动股代码,主股放最前。"""
        codes = api_client.extract_linked_codes(content)
        rec_main = str(record.get('code', '') or '').zfill(6)
        if rec_main and rec_main.isdigit() and len(rec_main) == 6:
            if rec_main in codes:
                codes.remove(rec_main)
            codes = [rec_main] + codes
        return codes

    def _format_rt_block(self, data, rec_main):
        """data: {code: info} → 拼成一段附加文本。"""
        lines = ["\n\n" + self.SEP, self.RT_MARKER, self.SEP]
        for code, info in data.items():
            chg = info["change_pct"]
            arrow = "▲" if chg > 0 else ("▼" if chg < 0 else "─")
            sign = "+" if chg > 0 else ""
            prefix = "  ⭐ " if (rec_main and code == rec_main) else "    "
            lines.append("{}{}({})  {}  {}{}%   {}".format(
                prefix, info["name"], code, info["price"],
                arrow, sign + str(chg), info["time"]))
        lines.append(self.SEP)
        return "\n".join(lines)


# ════════════════════════════════════════════════════════
# 当日历史 + 行情 导出
# ════════════════════════════════════════════════════════
class DailyQuotesExporter:
    """
    导出某一天所有记录 + 当前行情到 Excel。

    与 UI 解耦 — 不弹框,返回 (path, n_records, n_codes) 或抛异常。
    """

    def __init__(self, repo=None):
        self._repo = repo or history_repo

    def export(self, date_key):
        """
        Args:
            date_key: '20260513'

        Returns:
            tuple: (file_path: pathlib.Path, n_records: int, n_codes: int)

        Raises:
            ValueError: 当日无记录 / 无有效代码 / 行情查询全失败
            其它: 文件写入异常往外抛
        """
        records = self._repo.load(date_key)
        if not records:
            raise ValueError("当日无历史记录")

        codes = sorted({
            r.get('code', '') for r in records
            if r.get('code') and r['code'] != '000000'
        })
        if not codes:
            raise ValueError("未找到有效的股票代码")

        data = api_client.fetch_change_pct(codes)
        if not data:
            raise ValueError("行情查询失败")

        import pandas as pd
        rows = []
        for r in records:
            code = r.get('code', '')
            name = r.get('name', '')
            if code == '000000' or not code:
                continue
            q = data.get(code, {})
            rows.append({
                "股票代码": code,
                "股票名称": q.get('name', name),
                "分析状态": "✅成功" if r.get('success') else "❌失败",
                "分析时间": r.get('time', ''),
                "备注":     r.get('note', ''),
                "细分标签": r.get('category', ''),
                "现价":     q.get('price', ''),
                "涨跌幅%":  q.get('change_pct', ''),
                "行情时间": q.get('time', ''),
            })

        df = pd.DataFrame(rows)
        df = df.sort_values(by="涨跌幅%", ascending=False,
                            na_position='last').reset_index(drop=True)

        fn = paths.DIRS["output"] / "历史行情_{}_{}.xlsx".format(
            date_key, datetime.now().strftime("%H%M%S"))
        df.to_excel(fn, index=False)
        log.info("daily quotes exported: %s (%d rows)", fn, len(rows))
        return (fn, len(rows), len(codes))


# ════════════════════════════════════════════════════════
# 详情面板文本 → 回写历史记录
# ════════════════════════════════════════════════════════
class ContentEditService:
    """
    把用户在详情面板里编辑的纯文本回写到历史记录的 content 字段。

    需要剥掉前面的"元信息头" (时间/名称/备注行/标签行/次日表现行)。
    """

    def __init__(self, repo=None):
        self._repo = repo or history_repo

    def parse_content_from_panel_text(self, full_text):
        """
        从详情面板的完整文本里提取出"分析正文"。
        UI 渲染时会在最前面加几行元信息,这里反向剥离。
        """
        lines = full_text.splitlines(keepends=True)
        content_start = 0
        for i, line in enumerate(lines):
            if i == 0:
                continue   # 跳过时间/名称头行
            stripped = line.strip()
            if (stripped.startswith('📝 备注:')
                or stripped.startswith('🏷️ 标签:')
                or stripped.startswith('📈 次日表现')
                or stripped == ''):
                continue
            content_start = i
            break
        return ''.join(lines[content_start:]).strip()

    def save_from_text(self, date_key, record_id, full_text):
        """
        Args:
            full_text: 从 Text widget 拿到的完整内容 (含元信息头)

        Returns:
            (saved_content: str, success: bool)
            返回写入的纯正文本,调用方需要拿它去同步内存缓存。
        """
        if not date_key or not record_id:
            return ("", False)
        content = self.parse_content_from_panel_text(full_text)
        try:
            self._repo.update_record(date_key, record_id, content=content)
            return (content, True)
        except Exception:
            log.exception("update_record failed (%s/%s)", date_key, record_id)
            return (content, False)


# ════════════════════════════════════════════════════════
# 星标导出包装
# ════════════════════════════════════════════════════════
class StarredExportService:
    """
    Repository 已经实现了 export_starred_to_excel/html,这里只是给个
    Service 入口,语义对齐:Service 是"业务",Repository 是"数据"。

    Service 层加点儿东西:
      • 统一日志
      • 异常路径明确
      • 将来要做"导出前过滤" / "按分组导出" 等就在这里
    """

    def __init__(self, repo=None):
        self._repo = repo or history_repo

    def to_excel(self):
        """返回路径或 None (无星标)。"""
        path = self._repo.export_starred_to_excel()
        if path:
            log.info("starred exported to excel: %s", path)
        return path

    def to_html(self):
        """返回路径或 None (无星标)。"""
        path = self._repo.export_starred_to_html()
        if path:
            log.info("starred exported to html: %s", path)
        return path
