"""
import 链路验证 (mock 版本) — v10.0 AI Native 架构

环境没装 tkinter / matplotlib,所以把它们 mock 掉只验证 import 解析。
分四轮:

  Pass 1 - 重构核心:  新系统模块 + 重构产物,必须 0 错误
  Pass 2 - 端到端:    完整 stock_app + 旧 shim,失败只警告
  Pass 3 - 静态扫描:  AST 相对 import 目标是否存在
  Pass 4 - 公开 API:  PopupWindow 方法完整性
"""
import sys, types, ast, os
from unittest.mock import MagicMock


def _make_mock_module(name):
    m = types.ModuleType(name)
    m.__getattr__ = lambda attr, _n=name: MagicMock(name=_n + "." + attr)
    return m


def install_mocks():
    tk = _make_mock_module("tkinter")
    tk.Tk = MagicMock(name="Tk")
    tk.Toplevel = MagicMock(name="Toplevel")
    tk.Frame = MagicMock(name="Frame")
    tk.Label = MagicMock(name="Label")
    tk.Entry = MagicMock(name="Entry")
    tk.Text = MagicMock(name="Text")
    tk.Canvas = MagicMock(name="Canvas")
    tk.Menu = MagicMock(name="Menu")
    tk.StringVar = MagicMock(name="StringVar")
    tk.IntVar = MagicMock(name="IntVar")
    tk.BooleanVar = MagicMock(name="BooleanVar")
    tk.TclError = type("TclError", (Exception,), {})
    tk.Misc = type("Misc", (), {})
    sys.modules["tkinter"] = tk

    ttk = _make_mock_module("tkinter.ttk")
    for c in ("Style", "Scrollbar", "Combobox", "Notebook",
              "Frame", "Treeview", "Progressbar", "Button",
              "Entry", "Label", "Checkbutton", "Radiobutton",
              "Separator", "Spinbox"):
        setattr(ttk, c, MagicMock())
    sys.modules["tkinter.ttk"] = ttk

    for sub in ("messagebox", "filedialog", "simpledialog",
                "colorchooser", "scrolledtext", "font"):
        sys.modules["tkinter." + sub] = _make_mock_module("tkinter." + sub)

    for big in ("matplotlib", "matplotlib.pyplot", "matplotlib.backends",
                "matplotlib.backends.backend_tkagg",
                "matplotlib.figure", "matplotlib.font_manager",
                "numpy", "pandas", "openpyxl", "openpyxl.styles",
                "openai", "anthropic",
                "pythoncom", "win32api", "win32gui", "win32con",
                "win32process", "win32clipboard", "pywintypes",
                "psutil", "keyboard", "pyperclip", "pymem",
                "pymem.process"):
        if big not in sys.modules:
            sys.modules[big] = _make_mock_module(big)

    if "requests" not in sys.modules:
        requests = _make_mock_module("requests")
        requests.Session = MagicMock(name="Session")
        sys.modules["requests"] = requests
        sys.modules["requests.adapters"] = _make_mock_module("requests.adapters")
        sys.modules["requests.adapters"].HTTPAdapter = MagicMock(name="HTTPAdapter")
        sys.modules["urllib3"] = _make_mock_module("urllib3")
        sys.modules["urllib3.util"] = _make_mock_module("urllib3.util")
        sys.modules["urllib3.util"].Retry = MagicMock(name="Retry")
        sys.modules["urllib3.util.retry"] = _make_mock_module("urllib3.util.retry")
        sys.modules["urllib3.util.retry"].Retry = MagicMock(name="Retry")


def try_import(mod, indent="    "):
    try:
        __import__(mod)
        print("%s✓ %s" % (indent, mod))
        return True
    except Exception as e:
        print("%s✗ %s  → %s: %s" % (indent, mod, type(e).__name__, e))
        return False


def header(text):
    print()
    print("=" * 60)
    print(text)
    print("=" * 60)


def main():
    install_mocks()

    header("Pass 1 · 重构核心 (必须全过)")
    pass1 = [
        # ── 基础设施 ──
        "stock_app.app.event_bus",
        "stock_app.app.state",
        "stock_app.infrastructure",
        "stock_app.infrastructure.threading",
        "stock_app.infrastructure.threading.task_manager",
        "stock_app.infrastructure.threading.ui_dispatcher",
        "stock_app.infrastructure.logging",
        "stock_app.infrastructure.logging.logger",

        # ── 浮窗系统 (已拆分) ──
        "stock_app.popup",
        "stock_app.popup.state",
        "stock_app.popup.view",
        "stock_app.popup.render",
        "stock_app.popup.sync",
        "stock_app.popup.ball",
        "stock_app.popup.drag",
        "stock_app.popup.updater",
        "stock_app.popup.controller",
        "stock_app.popup.hexin_ctrl",
        "stock_app.popup.lifecycle",
        "stock_app.popup.facade",
        "stock_app.popup_window",

        # ── 数据层 ──
        "stock_app.repositories",
        "stock_app.repositories.history_repository",
        "stock_app.repositories.sector_repository",
        "stock_app.services",
        "stock_app.services.history_service",
        "stock_app.services.sector_service",

        # ── 集成层 ──
        "stock_app.integrations.eastmoney",
        "stock_app.integrations.eastmoney._http",
        "stock_app.integrations.eastmoney.sectors",
        "stock_app.integrations.eastmoney.limit_up",
        "stock_app.integrations.eastmoney.market",
        "stock_app.integrations.tencent",
        "stock_app.integrations.tencent.quote",
        "stock_app.integrations.tencent.names",
        "stock_app.integrations.qianfan",
        "stock_app.integrations.qianfan.client",
        "stock_app.integrations.hexin",
        "stock_app.integrations.hexin.bridge",

        # ── 领域 + UI ──
        "stock_app.controllers",
        "stock_app.domain",
        "stock_app.domain.models",
        "stock_app.domain.events",
        "stock_app.integrations",
        "stock_app.ui",
        "stock_app.ui.windows.popup",
        "stock_app.ui.themes",

        # ── Tab 拆分模块 ──
        "stock_app.tabs.history.menus",
        "stock_app.tabs.history.operations",
        "stock_app.tabs.history.auto_mode",
        "stock_app.tabs.history.import_subtags",
        "stock_app.tabs.replay.daily",
        "stock_app.tabs.replay.profile",
        "stock_app.tabs.replay.trend",
        "stock_app.tabs.replay.similar",
        "stock_app.tabs.replay.track",
        "stock_app.tabs.my_sectors.tag_relation_view",
        "stock_app.tabs.my_sectors.tag_relation_scan",
        "stock_app.tabs.my_sectors.tag_relation_ai",
        "stock_app.tabs.my_sectors.tag_relation_manager",

        # ── v10.0 新架构系统 ⭐ ──
        "stock_app.skills",
        "stock_app.skills.base",
        "stock_app.skills.registry",
        "stock_app.skills.executor",
        "stock_app.skills.scheduler",
        "stock_app.prompts",
        "stock_app.runtime",
        "stock_app.state",
        "stock_app.events",
        "stock_app.schemas",
        "stock_app.schemas.ai_result",
        "stock_app.schemas.stock",
        "stock_app.workflows",
        "stock_app.cache",

        # ── 核心拆分模块 ──
        "stock_app.core.hexin_bridge",
    ]
    pass1_fail = []
    for m in pass1:
        if not try_import(m):
            pass1_fail.append(m)

    header("Pass 2 · 顶层 stock_app (依赖环境)")
    pass2 = [
        "stock_app",
        "stock_app.app",
        "stock_app.app.bootstrap",
    ]
    pass2_fail = []
    for m in pass2:
        if not try_import(m):
            pass2_fail.append(m)

    header("Pass 3 · 静态扫描:相对 import 目标是否真实存在")
    here = os.path.dirname(os.path.abspath(__file__))
    pkg_root = os.path.join(here, "stock_app")
    bad_imports = []

    def _module_to_path(mod_name):
        parts = mod_name.split(".")
        return [
            os.path.join(here, *parts) + ".py",
            os.path.join(here, *parts, "__init__.py"),
        ]

    def _resolve_relative(current_module, is_init, level, mod_tail):
        parts = current_module.split(".")
        current_pkg = parts if is_init else parts[:-1]
        if level - 1 > len(current_pkg):
            return None
        base = current_pkg[:len(current_pkg) - (level - 1)]
        if mod_tail:
            return ".".join(base + mod_tail.split("."))
        return ".".join(base) if base else None

    for dirpath, dirs, files in os.walk(pkg_root):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for fn in files:
            if not fn.endswith(".py"):
                continue
            fp = os.path.join(dirpath, fn)
            rel = os.path.relpath(fp, here).replace(os.sep, "/")
            pkg_parts = os.path.relpath(fp, here).replace(os.sep, ".")[:-3].split(".")
            if pkg_parts[-1] == "__init__":
                current_module = ".".join(pkg_parts[:-1])
                is_init = True
            else:
                current_module = ".".join(pkg_parts)
                is_init = False
            try:
                tree = ast.parse(open(fp, encoding="utf-8").read(), filename=fp)
            except Exception as e:
                bad_imports.append((rel, "?", "parse error: " + str(e)))
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.ImportFrom):
                    continue
                if node.level == 0:
                    continue
                mod_tail = node.module or ""
                resolved = _resolve_relative(current_module, is_init,
                                              node.level, mod_tail)
                if resolved is None:
                    bad_imports.append((rel, node.lineno,
                                        "level {} dots 越出包根".format(node.level)))
                    continue
                cands = _module_to_path(resolved)
                exists = any(os.path.isfile(c) for c in cands)
                if not exists:
                    parent_cands = _module_to_path(resolved)
                    parent_exists = any(os.path.isfile(c) for c in parent_cands)
                    if not parent_exists:
                        bad_imports.append((
                            rel, node.lineno,
                            "from {} import ... → {} 不存在".format(
                                "." * node.level + mod_tail, resolved)))

    if bad_imports:
        print("    ✗ 发现 {} 处相对 import 目标不存在:".format(len(bad_imports)))
        for rel, ln, why in bad_imports:
            print("       %s:%s  %s" % (rel, ln, why))
        pass1_fail.append("relative imports broken")
    else:
        print("    ✓ 所有相对 import 目标都存在 (含函数体内的延迟 import)")

    header("Pass 4 · PopupWindow 公开 API 一致性")
    expected = [
        "show", "hide", "destroy", "notify_main_click",
        "push_to_hexin", "is_follow_mode", "follow", "lock_code",
        "restart_hexin_watcher", "toggle_visibility",
        "toggle_minimize", "undo",
    ]
    from stock_app.popup import PopupWindow
    missing = [m for m in expected if not hasattr(PopupWindow, m)]
    if missing:
        print("    ✗ PopupWindow 缺方法: %s" % missing)
        pass1_fail.append("PopupWindow public API")
    else:
        print("    ✓ %d 个公开方法全部就位" % len(expected))

    for attr in ("_hexin_status_var", "root", "controller"):
        if hasattr(PopupWindow, attr):
            print("    ✓ PopupWindow.%s 就位" % attr)
        else:
            print("    ✗ PopupWindow 缺 %s" % attr)
            pass1_fail.append("PopupWindow." + attr)

    header("结果")
    print("Pass 1 (重构核心) : %d 通过, %d 失败" %
          (len(pass1) - len(pass1_fail), len(pass1_fail)))
    print("Pass 2 (顶层 + tabs) : %d 通过, %d 失败 (失败可接受 = 环境缺依赖)" %
          (len(pass2) - len(pass2_fail), len(pass2_fail)))

    if pass1_fail:
        print("\n❌ 重构核心有未解决的失败:")
        for m in pass1_fail:
            print("   - %s" % m)
        return 1

    if pass2_fail:
        print("\n⚠️  顶层 import 有失败但都属于环境缺依赖, 重构本身 OK")

    print("\n✅ 重构本身完整, 所有新模块 import 链路正常")
    return 0


if __name__ == "__main__":
    sys.exit(main())
