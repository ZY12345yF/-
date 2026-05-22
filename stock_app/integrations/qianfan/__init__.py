"""
integrations.qianfan — 千帆 / 火山方舟 / 第三方厂商 AI 搜索
"""
from .client import call_qianfan, _is_volcano_endpoint, _is_qianfan_endpoint

__all__ = ["call_qianfan", "_is_volcano_endpoint", "_is_qianfan_endpoint"]
