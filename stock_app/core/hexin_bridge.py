"""
hexin_bridge 向后兼容 shim
═══════════════════════════════════════════════════════════════════
v9.9.8 迁移：主逻辑已迁至 stock_app/integrations/hexin/bridge.py
这里保留为向后兼容转发层，所有 import stock_app.core.hexin_bridge
的代码无需修改即可正常工作。
═══════════════════════════════════════════════════════════════════
"""
from ..integrations.hexin.bridge import *
