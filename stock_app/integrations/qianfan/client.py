"""
integrations.qianfan.client — 百度千帆 / 火山方舟豆包 AI 搜索

从 core/api_client.py L415-529 迁入,行为不变。
单元化后,UI 层 (batch_tab / single_tab) 调本模块,不直接调 requests。
"""
import json
import traceback

import requests

from ...core.text_utils import validate_response, clean_symbols
from ..tencent.names import append_realtime_data


def _is_volcano_endpoint(url):
    """识别火山方舟 API(基于 URL)"""
    if not url:
        return False
    return "volces.com" in url or "ark.cn-beijing" in url


def _is_qianfan_endpoint(url):
    """识别百度千帆 API(基于 URL，只有千帆支持联网搜索)"""
    if not url:
        return False
    return "qianfan.baidubce.com" in url or "qianfan.bce" in url


def call_qianfan(stock_name, stock_code, api_key, cfg,
                 on_log=None, category=""):
    """
    调用 AI 搜索 API(同时支持百度千帆 / 火山方舟豆包)
    - category: 涨停类别(如"AI算力+算电协同"),如果传入且开关开启,作为补充上下文加入 prompt
    返回 (result_text, success, sources_list)
    """
    headers = {"Authorization": "Bearer " + api_key,
               "Content-Type":  "application/json"}
    prompt = cfg["prompt_template"].format(
        stock_name=stock_name, stock_code=stock_code)

    # 🔑 类别上下文:只有开关开启时才生效(统一控制 prompt 和结果中的标签行)
    use_category = cfg.get("use_category", True)
    has_category = bool(category and category.strip()) and use_category
    if has_category:
        prompt = ("⚠️ 已知该股票的涨停类别标签为:「{}」,请结合此标签深入分析,"
                  "确保 ②市场主要核心上涨共识 和 ④同逻辑联动标的 紧扣此主线。\n\n".format(
                      category.strip()) + prompt)

    api_url = cfg["api_url"]
    is_volcano = _is_volcano_endpoint(api_url)
    is_qianfan = _is_qianfan_endpoint(api_url)

    if is_qianfan:
        # 百度千帆:带联网搜索
        payload = {
            "messages":      [{"role": "user", "content": prompt}],
            "model":         cfg["model"],
            "search_source": "baidu_search_v2",
            "search_mode":   "auto",
            "stream":        False,
            "max_tokens":    cfg["max_tokens"],
            "temperature":   cfg["temperature"],
        }
    else:
        # 标准 OpenAI 协议（火山方舟 / DeepSeek / 智谱 / Kimi / 阿里 / 硅基流动 等）
        payload = {
            "messages":   [{"role": "user", "content": prompt}],
            "model":      cfg["model"],
            "stream":     False,
            "max_tokens": cfg["max_tokens"],
            "temperature": cfg["temperature"],
        }
        provider_label = "火山方舟" if is_volcano else "第三方厂商"
        if on_log:
            on_log("使用 {} API(标准OpenAI协议)".format(provider_label), "dim")

    sources = []
    try:
        resp = requests.post(api_url, headers=headers,
                             data=json.dumps(payload), timeout=cfg["timeout"])
        if on_log:
            on_log("HTTP {}".format(resp.status_code), "dim")

        if resp.status_code == 429:
            return "❌ 请求过多(429)", False, []
        if resp.status_code != 200:
            return "❌ HTTP {}: {}".format(resp.status_code, resp.text[:200]), False, []

        result = resp.json()
        if "error" in result:
            return "❌ API错误: {}".format(result["error"]), False, []

        # 提取数据源(仅千帆有)
        if is_qianfan:
            si = result.get("search_info", {})
            raw_sources = si.get("search_results", []) or si.get("results", [])
            for s in raw_sources:
                sources.append({
                    "title": s.get("title") or s.get("name") or "未知来源",
                    "url":   s.get("url") or s.get("link") or "",
                })
            if on_log and sources:
                on_log("搜索到 {} 个数据源".format(len(sources)), "purple")

        choices = result.get("choices", [])
        if not choices:
            full = json.dumps(result, ensure_ascii=False)[:400]
            return "❌ 返回无 choices: {}".format(full), False, sources

        content = choices[0]["message"]["content"]
        if on_log:
            on_log("原始字数: {} 字".format(len(content)), "dim")

        # 🔑 关键修复:只有开关开启 + 有 category 时才插入标签行
        category_prefix = ""
        if has_category:
            category_prefix = "【细分标签】:{}\n\n".format(category.strip())

        ok, cleaned = validate_response(content)
        if ok:
            cleaned = category_prefix + cleaned
            cleaned = append_realtime_data(cleaned, on_log=on_log,
                                            main_code=stock_code)
            return cleaned, True, sources

        # 格式异常:清洗符号后追加实时行情
        raw_cleaned = clean_symbols(content)
        raw_cleaned = category_prefix + raw_cleaned
        raw_cleaned = append_realtime_data(raw_cleaned, on_log=on_log,
                                            main_code=stock_code)
        return "⚠️ 格式异常: {}\n\n原始:\n{}".format(cleaned, raw_cleaned), False, sources

    except requests.exceptions.Timeout:
        return "❌ 请求超时", False, []
    except Exception:
        return "❌ 异常: {}".format(traceback.format_exc()[:300]), False, []
