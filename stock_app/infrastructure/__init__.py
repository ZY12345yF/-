"""
基础设施层 — v9.9.8

不含业务逻辑,只提供"底盘":
    threading/      统一线程调度,所有 worker 必须走 TaskManager
    logging/        统一 logger
    config/         配置加载 (Phase 2 才会启用,现在 core/config.py 还在用)
    database/       SQLite/JSON 持久化 (Phase 2)
    cache/          内存 + 磁盘缓存 (Phase 2)

按文档 六·线程管理统一方案 + 十·日志改造 落地。
"""
