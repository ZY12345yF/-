"""
配置文件管理 - 持久化所有用户数据
"""
import json, os
from datetime import datetime
from pathlib import Path

from .paths import PATHS, DIRS, ensure_dirs


# ══════════════════════════════════════════════════
# 厂商 URL 映射
# ══════════════════════════════════════════════════
PROVIDER_URLS = {
    "qianfan":   "https://qianfan.baidubce.com/v2/ai_search/chat/completions",
    "volcano":   "https://ark.cn-beijing.volces.com/api/v3/chat/completions",
    "deepseek":  "https://api.deepseek.com/chat/completions",
    "zhipu":     "https://open.bigmodel.cn/api/paas/v4/chat/completions",
    "moonshot":  "https://api.moonshot.cn/v1/chat/completions",
    "dashscope": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
    "minimax":   "https://api.minimax.chat/v1/text/chatcompletion_v2",
    "siliconflow":"https://api.siliconflow.cn/v1/chat/completions",
    "other":     "",   # 用户自定义
}

# 显示名前缀 → provider key（用于 URL 和 Key 池路由）
PROVIDER_PREFIXES = {
    "🌋 ":  "volcano",
    "🐋 ":  "deepseek",
    "🧪 ":  "zhipu",
    "🌙 ":  "moonshot",
    "☁️ ": "dashscope",
    "🎯 ":  "minimax",
    "⚡ ":  "siliconflow",
}


def get_url_for_model(display_name):
    """根据显示名前缀返回对应厂商 URL，默认千帆。"""
    for prefix, provider in PROVIDER_PREFIXES.items():
        if display_name.startswith(prefix):
            return PROVIDER_URLS.get(provider, "")
    return PROVIDER_URLS["qianfan"]


def key_pool_for_model(display_name):
    """返回该模型应该使用的 Key 池名称: qianfan / volcano / other。"""
    for prefix, provider in PROVIDER_PREFIXES.items():
        if display_name.startswith(prefix):
            if provider == "volcano":
                return "volcano"
            return "other"
    return "qianfan"


# ══════════════════════════════════════════════════
# 模型列表
# ══════════════════════════════════════════════════
MODEL_LIST = [
    # ── 🌋 火山方舟（豆包）─────────────────────
    "🌋 doubao-seed-2-0-pro",
    "🌋 doubao-seed-2-0-lite",
    "🌋 doubao-seed-2-0-mini",
    "🌋 doubao-seed-2-0-code",
    "🌋 deepseek-v3-2 (火山)",
    # ── 🔵 百度千帆 ─────────────────────────────
    "🆓 ERNIE-X1-Turbo-32K","🆓 ERNIE-4.5-Turbo-32K","🆓 ERNIE-4.5-Turbo-VL",
    "🆓 DeepSeek-V3.1-250821","🆓 DeepSeek-V3.1-Think-250821","🆓 DeepSeek-R1-250528",
    "🆓 Qwen3-Coder-480B-A35B-Instruct","🆓 Qwen3-235B-A22B-Instruct-2507",
    "🆓 Qwen3-30B-A3B-Instruct-2507","🆓 Qwen3-Coder-30B-A3B-Instruct",
    "ERNIE-5.1","ERNIE-5.0","ERNIE-5.0-Thinking-Preview","ERNIE-5.0-Thinking-Latest","ERNIE-5.0-Thinking-Exp",
    "ERNIE-X1.1","ERNIE-X1.1-Preview","ERNIE-X1-Turbo-32K-Preview",
    "ERNIE-4.5-Turbo-20260402","ERNIE-4.5-Turbo-128K","ERNIE-4.5-Turbo-VL-32K","ERNIE-4.5-0.3B",
    "DeepSeek-V4-Pro","DeepSeek-V4-Flash","DeepSeek-V3.2","DeepSeek-V3.2-Think","DeepSeek-V3",
    "MiniMax-M2.5","GLM-5.1","GLM-5","Kimi-K2.5",
    "DeepSeek-R1-Distill-Qwen-14B","DeepSeek-R1-Distill-Qwen-32B","DeepSeek-OCR",
    "ERNIE-Lite-Pro-128K","ERNIE-Speed-Pro-128K",
    "Qwen3.5-397B-A17B","Qwen3.5-122B-A10B","Qwen3.5-27B","Qwen3.5-35B-A3B",
    "Qwen3-32B","Qwen3-14B","Qwen3-8B","Qwen3-4B","Qwen3-1.7B","Qwen3-0.6B",
    "Qwen3-235B-A22B-Thinking-2507","Qwen3-30B-A3B-Thinking-2507",
    "Qianfan-VL-70B","Qianfan-VL-8B","Qianfan-VL-1.5-Flash",
    "Qianfan-OCR","Qianfan-OCR-Fast","InternVL3-38B",
    # ── 🐋 DeepSeek 官方 ────────────────────────
    "🐋 DeepSeek-V3.2 (官方)","🐋 DeepSeek-V3.2-Thinking (官方)",
    "🐋 DeepSeek-V3.1 (官方)","🐋 DeepSeek-R1 (官方)",
    "🐋 DeepSeek-R1-0528 (官方)",
    # ── 🧪 智谱 GLM ─────────────────────────────
    "🧪 GLM-4-Plus","🧪 GLM-4-Long","🧪 GLM-4-FlashX",
    "🧪 GLM-4-Flash (免费)","🧪 GLM-Z1-Air","🧪 GLM-Z1-Flash (免费)",
    "🧪 GLM-4V-Plus-0111",
    # ── 🌙 月之暗面 Kimi ────────────────────────
    "🌙 Kimi-K2-0711-Preview","🌙 Kimi-K2-Turbo-Preview",
    "🌙 moonshot-v1-128k","🌙 moonshot-v1-32k",
    "🌙 moonshot-v1-8k","🌙 Kimi-VL-A3B-Thinking-250427",
    # ── ☁️ 阿里百炼 DashScope ──────────────────
    "☁️ Qwen3-Max","☁️ Qwen3-Plus","☁️ Qwen3-Turbo",
    "☁️ Qwen-Long (1M)","☁️ QwQ-32B","☁️ Qwen3-VL-235B-A22B-Thinking",
    # ── 🎯 MiniMax ──────────────────────────────
    "🎯 MiniMax-M2.5 (官方)","🎯 MiniMax-Text-01",
    # ── ⚡ 硅基流动 SiliconFlow（多模型代理）────
    "⚡ DeepSeek-V3.2 (硅基)","⚡ DeepSeek-R1 (硅基)",
    "⚡ Qwen3-235B (硅基)","⚡ Qwen3-Coder-480B (硅基)",
    "⚡ GLM-4-9B-Chat (硅基)","⚡ Kimi-K2 (硅基)",
    # ── 🔧 自定义（手动填 URL + Model ID）───────
    "🔧 自定义模型...",
]

MODEL_ID_MAP = {
    # ── 🌋 火山方舟 ──────────────────────────────
    "🌋 doubao-seed-2-0-pro":      "doubao-seed-2-0-pro-260215",
    "🌋 doubao-seed-2-0-lite":     "doubao-seed-2-0-lite-260428",
    "🌋 doubao-seed-2-0-mini":     "doubao-seed-2-0-mini-260428",
    "🌋 doubao-seed-2-0-code":     "doubao-seed-2-0-code-preview-260215",
    "🌋 deepseek-v3-2 (火山)":     "deepseek-v3-2-251201",
    # ── 🔵 百度千帆（免费）────────────────────────
    "🆓 ERNIE-X1-Turbo-32K":"ernie-x1-turbo-32k","🆓 ERNIE-4.5-Turbo-32K":"ernie-4.5-turbo-32k",
    "🆓 ERNIE-4.5-Turbo-VL":"ernie-4.5-turbo-vl","🆓 DeepSeek-V3.1-250821":"deepseek-v3.1-250821",
    "🆓 DeepSeek-V3.1-Think-250821":"deepseek-v3.1-think-250821","🆓 DeepSeek-R1-250528":"deepseek-r1-250528",
    "🆓 Qwen3-Coder-480B-A35B-Instruct":"qwen3-coder-480b-a35b-instruct",
    "🆓 Qwen3-235B-A22B-Instruct-2507":"qwen3-235b-a22b-instruct-2507",
    "🆓 Qwen3-30B-A3B-Instruct-2507":"qwen3-30b-a3b-instruct-2507",
    "🆓 Qwen3-Coder-30B-A3B-Instruct":"qwen3-coder-30b-a3b-instruct",
    # ── 🔵 百度千帆（付费）────────────────────────
    "ERNIE-5.1":"ernie-5.1","ERNIE-5.0":"ernie-5.0",
    "ERNIE-5.0-Thinking-Preview":"ernie-5.0-thinking-preview",
    "ERNIE-5.0-Thinking-Latest":"ernie-5.0-thinking-latest",
    "ERNIE-5.0-Thinking-Exp":"ernie-5.0-thinking-exp",
    "ERNIE-X1.1":"ernie-x1.1","ERNIE-X1.1-Preview":"ernie-x1.1-preview",
    "ERNIE-X1-Turbo-32K-Preview":"ernie-x1-turbo-32k-preview",
    "ERNIE-4.5-Turbo-20260402":"ernie-4.5-turbo-20260402",
    "ERNIE-4.5-Turbo-128K":"ernie-4.5-turbo-128k",
    "ERNIE-4.5-Turbo-VL-32K":"ernie-4.5-turbo-vl-32k",
    "ERNIE-4.5-0.3B":"ernie-4.5-0.3b",
    "DeepSeek-V4-Pro":"deepseek-v4-pro","DeepSeek-V4-Flash":"deepseek-v4-flash",
    "DeepSeek-V3.2":"deepseek-v3.2","DeepSeek-V3.2-Think":"deepseek-v3.2-think",
    "DeepSeek-V3":"deepseek-v3","MiniMax-M2.5":"minimax-m2.5",
    "GLM-5.1":"glm-5.1","GLM-5":"glm-5","Kimi-K2.5":"kimi-k2.5",
    "DeepSeek-R1-Distill-Qwen-14B":"deepseek-r1-distill-qwen-14b",
    "DeepSeek-R1-Distill-Qwen-32B":"deepseek-r1-distill-qwen-32b",
    "DeepSeek-OCR":"deepseek-ocr","ERNIE-Lite-Pro-128K":"ernie-lite-pro-128k",
    "ERNIE-Speed-Pro-128K":"ernie-speed-pro-128k",
    "Qwen3.5-397B-A17B":"qwen3.5-397b-a17b","Qwen3.5-122B-A10B":"qwen3.5-122b-a10b",
    "Qwen3.5-27B":"qwen3.5-27b","Qwen3.5-35B-A3B":"qwen3.5-35b-a3b",
    "Qwen3-32B":"qwen3-32b","Qwen3-14B":"qwen3-14b","Qwen3-8B":"qwen3-8b",
    "Qwen3-4B":"qwen3-4b","Qwen3-1.7B":"qwen3-1.7b","Qwen3-0.6B":"qwen3-0.6b",
    "Qwen3-235B-A22B-Thinking-2507":"qwen3-235b-a22b-thinking-2507",
    "Qwen3-30B-A3B-Thinking-2507":"qwen3-30b-a3b-thinking-2507",
    "Qianfan-VL-70B":"qianfan-vl-70b","Qianfan-VL-8B":"qianfan-vl-8b",
    "Qianfan-VL-1.5-Flash":"qianfan-vl-1.5-flash",
    "Qianfan-OCR":"qianfan-ocr","Qianfan-OCR-Fast":"qianfan-ocr-fast",
    "InternVL3-38B":"internvl3-38b",
    # ── 🐋 DeepSeek 官方 ─────────────────────────
    "🐋 DeepSeek-V3.2 (官方)":     "deepseek-chat",
    "🐋 DeepSeek-V3.2-Thinking (官方)": "deepseek-reasoner",
    "🐋 DeepSeek-V3.1 (官方)":     "deepseek-chat",
    "🐋 DeepSeek-R1 (官方)":       "deepseek-reasoner",
    "🐋 DeepSeek-R1-0528 (官方)":  "deepseek-reasoner",
    # ── 🧪 智谱 GLM ──────────────────────────────
    "🧪 GLM-4-Plus":               "glm-4-plus",
    "🧪 GLM-4-Long":               "glm-4-long",
    "🧪 GLM-4-FlashX":             "glm-4-flashx",
    "🧪 GLM-4-Flash (免费)":        "glm-4-flash",
    "🧪 GLM-Z1-Air":               "glm-z1-air",
    "🧪 GLM-Z1-Flash (免费)":       "glm-z1-flash",
    "🧪 GLM-4V-Plus-0111":          "glm-4v-plus-0111",
    # ── 🌙 月之暗面 Kimi ─────────────────────────
    "🌙 Kimi-K2-0711-Preview":     "kimi-k2-0711-preview",
    "🌙 Kimi-K2-Turbo-Preview":    "kimi-k2-turbo-preview",
    "🌙 moonshot-v1-128k":         "moonshot-v1-128k",
    "🌙 moonshot-v1-32k":          "moonshot-v1-32k",
    "🌙 moonshot-v1-8k":           "moonshot-v1-8k",
    "🌙 Kimi-VL-A3B-Thinking-250427":"kimi-vl-a3b-thinking-250427",
    # ── ☁️ 阿里百炼 DashScope ────────────────────
    "☁️ Qwen3-Max":                "qwen-max",
    "☁️ Qwen3-Plus":               "qwen-plus",
    "☁️ Qwen3-Turbo":              "qwen-turbo",
    "☁️ Qwen-Long (1M)":           "qwen-long",
    "☁️ QwQ-32B":                  "qwq-32b",
    "☁️ Qwen3-VL-235B-A22B-Thinking":"qwen3-vl-235b-a22b-thinking",
    # ── 🎯 MiniMax ───────────────────────────────
    "🎯 MiniMax-M2.5 (官方)":      "MiniMax-M2.5",
    "🎯 MiniMax-Text-01":          "abab6.5s-chat",
    # ── ⚡ 硅基流动 SiliconFlow ──────────────────
    "⚡ DeepSeek-V3.2 (硅基)":     "deepseek-ai/DeepSeek-V3.2",
    "⚡ DeepSeek-R1 (硅基)":       "deepseek-ai/DeepSeek-R1",
    "⚡ Qwen3-235B (硅基)":        "Qwen/Qwen3-235B-A22B",
    "⚡ Qwen3-Coder-480B (硅基)":  "Qwen/Qwen3-Coder-480B-A35B-Instruct",
    "⚡ GLM-4-9B-Chat (硅基)":     "THUDM/glm-4-9b-chat",
    "⚡ Kimi-K2 (硅基)":           "moonshotai/Kimi-K2-Instruct",
}

def display_name_to_model_id(display_name):
    return MODEL_ID_MAP.get(display_name, display_name)

def model_id_to_display_name(model_id):
    for k, v in MODEL_ID_MAP.items():
        if v == model_id:
            return k
    return model_id


# ══════════════════════════════════════════════════
# 默认配置
# ══════════════════════════════════════════════════
DEFAULT_CONFIG = {
    "api_keys": [],               # 全局实际使用的 Keys (运行时由下方三组映射)
    "qianfan_api_keys": [],       # 百度千帆专属 Keys
    "volcano_api_keys": [],       # 火山方舟专属 Keys
    "other_api_keys": [],         # 第三方厂商 Keys（DeepSeek/智谱/Kimi/阿里/MiniMax/硅基流动等）
    "api_url":       "https://qianfan.baidubce.com/v2/ai_search/chat/completions",
    "model":         "ernie-4.5-turbo-128k",
    "timeout":       120,
    "max_tokens":    2500,
    "temperature":   0.2,
    "request_delay": 2,
    "output_prefix": "涨停分析结果",
    "tag_relation_api_settings": {   # 🆕 标签关联度专属API配置
        "url": "",
        "key": "",
        "model_disp": ""
    },
    "prompt_template": (
        "你是一个专业的股票分析师，严格按照以下固定格式分析{stock_name}({stock_code})的上涨原因：\n\n"
        "【核心信息总结】\n"
        "{stock_name}({stock_code})\n"
        "① 【核心业务】：清晰说明公司主营业务、具体业务后面标注出营收占比，核心产品与主要应用场景\n"
        "② 【市场主要核心上涨共识】：提炼全平台论坛讨论度最高的核心上涨观点【核心传播来源类型】\n"
        "③ 【市场次要上涨共识】：提炼全平台论坛次高热度的辅助上涨观点【核心传播来源类型】\n"
        "④ 【同逻辑联动标的】：提炼与个股同主线、同核心上涨驱动逻辑的A股核心关联标的，【关联原因汇总】\n"
        "⑤ 同逻辑标的板块事件共识：提炼近3个月内对板块产生直接催化的交易级事件\n\n"
        "严格要求：\n"
        "- 必须严格按照上述5个模块顺序输出，一字不得修改\n"
        "- 每个模块标题必须完全匹配，使用中文括号【】\n"
        "- 文字控制在1200-1800字之间\n"
        "- 内容必须专业、准确，基于最新市场信息\n"
        "- 只输出分析内容，不要任何其他说明、问候语或结束语\n"
        "- 如果信息不足，请基于公开信息合理分析，不要编造数据"
    ),
}

DEFAULT_SETTINGS = {
    "theme":      "dark",
    "font_size":  10,
    "highlight":  True,
    "schedule":   None,
}


# ══════════════════════════════════════════════════
# JSON 读写工具
# ══════════════════════════════════════════════════
def _load_json(path, default):
    if not Path(path).exists():
        return default() if callable(default) else dict(default)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(default, dict):
            merged = dict(default)
            merged.update(data)
            # 🆕 兼容旧版本：如果没有分离的 Keys，把旧的 api_keys 迁移给千帆
            if "qianfan_api_keys" not in data and "api_keys" in data:
                merged["qianfan_api_keys"] = data["api_keys"]
            return merged
        return data
    except Exception:
        return default() if callable(default) else dict(default)

def _save_json(path, data):
    ensure_dirs()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ══════════════════════════════════════════════════
# 配置接口
# ══════════════════════════════════════════════════
def load_config():
    return _load_json(PATHS["config"], DEFAULT_CONFIG)

def save_config(cfg):
    _save_json(PATHS["config"], cfg)

def load_settings():
    return _load_json(PATHS["settings"], DEFAULT_SETTINGS)

def save_settings(s):
    _save_json(PATHS["settings"], s)


# ══════════════════════════════════════════════════
# 自选股
# ══════════════════════════════════════════════════
def load_favorites():
    return _load_json(PATHS["favorites"], list)

def save_favorites(favs):
    _save_json(PATHS["favorites"], favs)

def add_favorite(name, code, tag=""):
    favs = load_favorites()
    if any(f["code"] == code for f in favs):
        return False
    favs.append({"name": name, "code": code, "tag": tag,
                 "added_at": datetime.now().strftime("%Y-%m-%d %H:%M")})
    save_favorites(favs)
    return True

def remove_favorite(code):
    favs = load_favorites()
    favs = [f for f in favs if f["code"] != code]
    save_favorites(favs)


# ══════════════════════════════════════════════════
# 股票名称字典
# ══════════════════════════════════════════════════
def load_stock_dict():
    return _load_json(PATHS["stock_dict"], dict)

def save_stock_dict(d):
    _save_json(PATHS["stock_dict"], d)

def learn_stocks(name_code_pairs):
    d = load_stock_dict()
    changed = False
    for name, code in name_code_pairs:
        if name and code and d.get(name) != code:
            d[name] = code
            changed = True
    if changed:
        save_stock_dict(d)
    return len(d)

def search_stocks(keyword, limit=8):
    if not keyword:
        return []
    d = load_stock_dict()
    keyword = keyword.lower()
    matches = []
    for name, code in d.items():
        if keyword in name.lower() or keyword in code:
            matches.append((name, code))
            if len(matches) >= limit:
                break
    return matches


def get_name_lookup():
    """名称→代码反查表，用于从文本中识别股票名"""
    return load_stock_dict()


def get_code_to_name_lookup():
    """代码→名称反查表，用于从代码查回中文名（联动股、复盘热点等场景）"""
    d = load_stock_dict()
    out = {}
    for name, code in d.items():
        if name and code:
            # 保留首次出现的（同代码不同名极少见，但有就用第一个）
            out.setdefault(str(code).zfill(6), name)
    return out