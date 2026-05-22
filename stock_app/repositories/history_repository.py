"""
HistoryRepository — 历史记录的数据访问对象

封装 stock_app/core/history.py 的全部函数为 OO 接口。

设计原则 (文档 九·Repository 规范):
  • Repository 只做数据访问 — 读写 sqlite/json 文件 / 维护索引缓存
  • 不做业务逻辑 (那是 Service 的事)
  • 不操作 UI (没有 tkinter / messagebox)
  • 线程安全 — 由底层 core/history.py 的 _HIST_LOCK 保证

为什么不直接搬运代码:
  • core/history.py 被 history_tab / popup / my_sectors / batch_tab / radar_tab
    五个 Tab 直接调用 (from ..core import history as hist_mod)
  • 暴力搬运会破坏所有调用方
  • OO 包装是更稳的渐进式路径 — core/history.py 保持不动,
    它和 HistoryRepository 共用同一份磁盘数据,行为完全一致

方法表 ≡ core/history.py 模块函数表,签名不变:

    读:
      list_dates() / load(date_key) / search(keyword) / find_by_code(code)
      list_all_starred()

    索引:
      get_code_count_index(force=False) / has_history(code)
      history_marker(code, fmt='emoji')

    写:
      save(name, code, content, success=True, category="") -> record_id
      delete_record(date_key, record_id)
      delete_records(date_key, record_ids)
      clear_day(date_key) / clear_all()
      update_record(date_key, record_id, **kwargs)
      toggle_star(date_key, record_id) -> 新的 starred 状态
      set_note(date_key, record_id, note)

    导出 (会被 Service 调用,但导出本身只产生文件,无 UI 弹框):
      export_starred_to_excel() -> path 或 None
      export_starred_to_html() -> path 或 None
"""
from .. import core


class HistoryRepository:
    """
    历史记录数据访问对象。

    本类是 stateless — 实例没有任何字段,所有调用都直接路由到底层 core.history。
    所以单例 (history_repo) 跟创建 new 实例完全等价。
    """

    # ── 读 ────────────────────────────────────────
    def list_dates(self):
        """返回所有有数据的日期字符串列表 ['20260513', ...] 新→旧"""
        return core.history.list_history_dates()

    def load(self, date_key):
        """返回某一天的全部记录 list[dict]。"""
        return core.history.load_history(date_key)

    def search(self, keyword):
        """跨日期全文搜索 (name/code/content/note),返回 list[dict] 每条带 date 字段。"""
        return core.history.search_history(keyword)

    def find_by_code(self, code):
        """精确按代码查所有历史,按 date+time 倒序。"""
        return core.history.find_by_code(code)

    def list_all_starred(self):
        """所有加星的记录,跨日期。"""
        return core.history.list_all_starred()

    # ── 索引 ──────────────────────────────────────
    def get_code_count_index(self, force=False):
        """{code: 历史条数} 索引。带 mtime 缓存,文件未变化时直接复用。"""
        return core.history.get_code_count_index(force=force)

    def has_history(self, code):
        """code 是否有历史记录。"""
        return core.history.has_history(code)

    def history_marker(self, code, fmt='emoji'):
        """返回 '📊' 或 '📊3' 标记串,无历史返回 ''。"""
        return core.history.history_marker(code, fmt=fmt)

    # ── 写 ────────────────────────────────────────
    def save(self, name, code, content, success=True, category=""):
        """新增一条记录,返回 record_id。"""
        return core.history.save_history(
            name, code, content, success=success, category=category)

    def delete_record(self, date_key, record_id):
        return core.history.delete_record(date_key, record_id)

    def delete_records(self, date_key, record_ids):
        return core.history.delete_records(date_key, record_ids)

    def clear_day(self, date_key):
        return core.history.clear_day(date_key)

    def clear_all(self):
        return core.history.clear_all()

    def update_record(self, date_key, record_id, **kwargs):
        """更新一条记录的若干字段。"""
        return core.history.update_record(date_key, record_id, **kwargs)

    def toggle_star(self, date_key, record_id):
        """翻转 starred,返回翻转后的状态。"""
        return core.history.toggle_star(date_key, record_id)

    def set_note(self, date_key, record_id, note):
        return core.history.set_note(date_key, record_id, note)

    # ── 导出 (产生文件) ────────────────────────────
    # 注意: 这是"基础导出",Service 层会在此之上做"导出 + 通知 + 错误处理"组合
    def export_starred_to_excel(self):
        """导出所有星标到 Excel,返回路径或 None (无数据)。"""
        return core.history.export_starred_to_excel()

    def export_starred_to_html(self):
        """导出所有星标到 HTML,返回路径或 None。"""
        return core.history.export_starred_to_html()


# 全局单例 — 业务代码通过这个调用
history_repo = HistoryRepository()
