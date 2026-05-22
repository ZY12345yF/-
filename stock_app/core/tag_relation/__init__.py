"""
细分标签关联度分析
- 极简提取模式：只提取【细分标签】和【涨停逻辑】，拒绝宽泛概念污染
- 基于历史记录提取标签，挖掘关联关系
- 输出：共现矩阵、关联度评分、共现股票、连带逻辑推理

v9.2 改进：
- normalize_tag：统一规范化（全角/半角/空格/尾缀清理）
- 单一数据源：以 record.category 为权威，content 仅 fallback
- build_cooccurrence 支持指定回溯天数
- 别名表 aliases.json：把"锂电"→"锂电池"这种映射做成可维护
- 标签管理：list / rename / merge / delete 全套 API
"""
from .normalize import normalize_tag, canonical, load_aliases, save_aliases
from .compute import extract_tags_from_content, build_cooccurrence, list_all_tags, compute_relations, co_stocks
from .ai import query_ai_relation, query_ai_bulk_clustering, rename_tag, merge_tags, delete_tag, load_bulk_prompt_template, save_bulk_prompt_template

__all__ = [
    "normalize_tag", "canonical", "load_aliases", "save_aliases",
    "extract_tags_from_content", "build_cooccurrence", "list_all_tags",
    "compute_relations", "co_stocks",
    "query_ai_relation", "query_ai_bulk_clustering",
    "rename_tag", "merge_tags", "delete_tag",
    "load_bulk_prompt_template", "save_bulk_prompt_template",
]
