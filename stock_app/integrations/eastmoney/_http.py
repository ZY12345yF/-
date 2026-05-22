"""
integrations.eastmoney._http — 东方财富统一 HTTP 层(防封 IP 核心)

- Session 连接复用 + cookie 持久化
- 全局节流(两次请求最小间隔 + 抖动)
- 自动重试 + 退避
- 完整 Chrome 125 指纹
- 可选代理(IP 被封时应急)

本模块从原 core/api_client.py L19-107 整体迁入,行为一字不改。
所有东方财富接口(板块、涨停、全市场)统一调用 _em_get。
"""
import random
import threading
import time

import requests
from requests.adapters import HTTPAdapter
try:
    from urllib3.util.retry import Retry
except ImportError:
    from urllib3.util import Retry


_EM_LOCK = threading.Lock()
_EM_SESSION = None
_EM_LAST_REQ_TS = 0.0
_EM_PROXIES = None  # 由 set_em_proxy 设置

_EM_HEADERS = {
    # 🛡️ 保持与老版本几乎一致的请求形态,避免被东财识别为"另一个客户端"
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/125.0.0.0 Safari/537.36"),
    "Accept": "*/*",
    "Accept-Encoding": "gzip, deflate",   # ⚠️ 不要加 br:环境没装 brotli 会解码失败返回空
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer": "http://quote.eastmoney.com/",
}


def _get_em_session():
    """惰性创建 Session:连接复用 + 自动重试。不预热、不加额外头。"""
    global _EM_SESSION
    with _EM_LOCK:
        if _EM_SESSION is not None:
            return _EM_SESSION
        s = requests.Session()
        retry = Retry(
            total=3,
            backoff_factor=1.5,   # 1.5s, 3s, 6s
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=frozenset(["GET"]),
            respect_retry_after_header=True,
        )
        adapter = HTTPAdapter(max_retries=retry,
                              pool_connections=4, pool_maxsize=4)
        s.mount("https://", adapter)
        s.mount("http://",  adapter)
        s.headers.update(_EM_HEADERS)
        if _EM_PROXIES:
            s.proxies = _EM_PROXIES
        _EM_SESSION = s
        return s


def em_get(url, params=None, timeout=15, min_interval=0.6):
    """
    东财专用 GET:Session 连接复用 + 全局节流 + 自动重试。
    min_interval: 全局两次请求之间最小间隔秒数(带抖动)
    """
    global _EM_LAST_REQ_TS
    sess = _get_em_session()

    # 全局节流(线程安全)
    with _EM_LOCK:
        now = time.time()
        wait = (_EM_LAST_REQ_TS + min_interval) - now
        if wait > 0:
            time.sleep(wait + random.uniform(0, min_interval * 0.3))
        _EM_LAST_REQ_TS = time.time()

    return sess.get(url, params=params, timeout=timeout)


def set_em_proxy(proxy_url):
    """
    IP 被封时应急用。
    proxy_url 形如:
        "http://user:pass@1.2.3.4:8080"
        "socks5://1.2.3.4:1080"
    传 None 表示取消代理(需要 socks 时 pip install requests[socks])
    """
    global _EM_PROXIES, _EM_SESSION
    if proxy_url:
        _EM_PROXIES = {"http": proxy_url, "https": proxy_url}
    else:
        _EM_PROXIES = None
    # 强制重建 session 让代理生效
    with _EM_LOCK:
        _EM_SESSION = None
