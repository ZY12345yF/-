"""
诊断脚本 — 不要直接跑 main.py 闪退看不到错误时用这个

它会:
  1. 检查 Python 版本
  2. 一步步 import stock_app 的各个子模块
  3. 每步出错就把完整 Traceback 写到 diagnose.log
  4. 跑完打开 diagnose.log 给你看

用法:
    cd 到项目目录
    python diagnose.py
然后会自动用记事本打开 diagnose.log。把这个文件发给我即可。
"""
import sys
import os
import traceback
import io


# 输出同时写到 stdout 和文件
class TeeOutput:
    def __init__(self, *streams):
        self.streams = streams
    def write(self, s):
        for st in self.streams:
            try:
                st.write(s)
                st.flush()
            except Exception:
                pass
    def flush(self):
        for st in self.streams:
            try: st.flush()
            except Exception: pass


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    log_path = os.path.join(here, "diagnose.log")

    # 用 UTF-8 写日志,避免中文编码出错
    log_file = io.open(log_path, "w", encoding="utf-8")
    sys.stdout = TeeOutput(sys.__stdout__, log_file)
    sys.stderr = TeeOutput(sys.__stderr__, log_file)

    print("=" * 70)
    print("诊断脚本运行 -- diagnose.log")
    print("=" * 70)

    # ─── 1. 基础环境 ───
    print("\n[1] Python 环境")
    print("    版本:", sys.version)
    print("    路径:", sys.executable)
    print("    工作目录:", os.getcwd())
    print("    脚本目录:", here)
    print("    sys.path[0]:", sys.path[0] if sys.path else "(空)")

    # 确保能 import stock_app
    if here not in sys.path:
        sys.path.insert(0, here)

    # ─── 2. 检查关键文件存在性 ───
    print("\n[2] 关键文件检查")
    key_files = [
        "stock_app/__init__.py",
        "stock_app/app/__init__.py",
        "stock_app/app/bootstrap.py",
        "stock_app/app/event_bus.py",
        "stock_app/app/state.py",
        "stock_app/bus.py",
        "stock_app/popup_window.py",
        "stock_app/popup/__init__.py",
        "stock_app/popup/controller.py",
        "stock_app/popup/view.py",
        "stock_app/popup/facade.py",
        "stock_app/core/__init__.py",
        "stock_app/tabs/__init__.py",
        "stock_app/widgets.py",
        # 不能存在的文件
        "stock_app/app.py",     # 必须已删除
    ]
    for f in key_files:
        full = os.path.join(here, f)
        exists = os.path.isfile(full)
        flag = "✓" if exists else "✗"
        note = ""
        if f == "stock_app/app.py" and exists:
            note = "  ← 严重! 这个文件必须删除, 否则会屏蔽 app/ 子包"
        size = ""
        if exists:
            try: size = " ({} bytes)".format(os.path.getsize(full))
            except: pass
        print("    {} {}{}{}".format(flag, f, size, note))

    # ─── 3. 一步一步 import ───
    print("\n[3] 模块 import 逐步检查")
    steps = [
        # 最基础的,不依赖外部
        ("stock_app",                        "顶层包 (lazy)"),
        ("stock_app.app.event_bus",          "EventBus"),
        ("stock_app.app.state",              "AppState"),
        ("stock_app.bus",                    "bus shim"),
        ("stock_app.infrastructure",                  "infrastructure 占位"),
        ("stock_app.infrastructure.threading",        "threading 子包"),
        ("stock_app.infrastructure.threading.task_manager",  "TaskManager"),
        ("stock_app.infrastructure.threading.ui_dispatcher", "UIDispatcher"),
        ("stock_app.infrastructure.logging",          "logging 子包"),
        ("stock_app.infrastructure.logging.logger",   "logger"),
        # popup 子包
        ("stock_app.popup.state",            "PopupState"),
        # 下面这些会拉 tkinter — 在没装 tkinter 的环境下会失败,但 Windows 下应该都过
        ("stock_app.popup.ball",             "FloatingBall (需 tkinter)"),
        ("stock_app.popup.drag",             "DragResize (需 tkinter)"),
        ("stock_app.popup.view",             "PopupView (需 tkinter)"),
        ("stock_app.popup.sync",             "HexinSync"),
        ("stock_app.popup.updater",          "QuoteUpdater"),
        ("stock_app.popup.controller",       "PopupController"),
        ("stock_app.popup.facade",           "PopupWindow facade"),
        ("stock_app.popup",                  "popup 包"),
        ("stock_app.popup_window",           "popup_window shim"),
        # core
        ("stock_app.core",                   "core 子包 (拉所有 core)"),
        ("stock_app.core.config",            "core.config"),
        ("stock_app.core.theme",             "core.theme"),
        ("stock_app.core.api_client",        "core.api_client (需 requests)"),
        ("stock_app.core.hexin_bridge",      "core.hexin_bridge (需 win32/pywin32)"),
        # widgets
        ("stock_app.widgets",                "widgets"),
        # tabs
        ("stock_app.tabs",                   "tabs (会拉所有 Tab → matplotlib 等)"),
        # bootstrap (压轴,加载到这一步就接近能跑了)
        ("stock_app.app.bootstrap",          "App 类"),
    ]

    first_failure = None
    for mod, desc in steps:
        try:
            __import__(mod)
            print("    ✓ {:50s} {}".format(mod, desc))
        except Exception as e:
            print("    ✗ {:50s} {}".format(mod, desc))
            print("       错误: {}: {}".format(type(e).__name__, e))
            if first_failure is None:
                first_failure = (mod, e)

    if first_failure:
        mod, e = first_failure
        print("\n[3.1] 第一个失败模块 {} 的完整 Traceback:".format(mod))
        print("-" * 70)
        # 重新 import 触发再抛一次,带 traceback
        # 注意有些已经 partially import 了,要从 sys.modules 删掉
        for cached in list(sys.modules):
            if cached.startswith(mod.split(".")[0]):
                # 别清掉成功的依赖,只清失败的
                pass
        try:
            # 不真删除已成功的,只为失败模块单独再 try 一次
            sys.modules.pop(mod, None)
            __import__(mod)
        except Exception:
            traceback.print_exc()
        print("-" * 70)

    # ─── 4. 尝试创建 App (不运行 mainloop) ───
    if not first_failure:
        print("\n[4] 尝试构造 App() 实例 (不进入 mainloop)")
        try:
            from stock_app import App
            print("    ✓ from stock_app import App  → 成功")
            print("    现在尝试 App() 构造...")
            # 不能真跑 mainloop, 但可以构造看是否爆炸
            # 由于 App.__init__ 会创建 Tk 主窗口,这一步在无显示环境会失败
            # 但 Windows 上有显示,应该能过
            print("    (跳过实际构造,避免弹窗)")
            print("    要测试请直接跑: python main.py")
        except Exception:
            print("    ✗ App import 失败")
            traceback.print_exc()

    # ─── 5. 收尾 ───
    print("\n" + "=" * 70)
    print("诊断完成。日志已写到:")
    print("    " + log_path)
    print("=" * 70)
    log_file.close()

    # 自动打开 diagnose.log
    try:
        if sys.platform.startswith("win"):
            os.startfile(log_path)
        elif sys.platform == "darwin":
            os.system('open "{}"'.format(log_path))
        else:
            print("(请手动打开 diagnose.log)")
    except Exception:
        pass

    # Windows 下让窗口停住
    if sys.platform.startswith("win"):
        try:
            input("\n按 Enter 退出...")
        except Exception:
            pass


if __name__ == "__main__":
    main()
