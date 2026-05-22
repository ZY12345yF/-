"""
FloatingBall — v9.9.8 悬浮球

原 popup_window.py 里 _create_or_show_ball / _destroy_ball / _on_ball_drag
/ _flash_ball 等 8 个方法 + 4 个 self._ball* 状态。

独立成类后:
  • 自己管自己的状态 (Toplevel / Canvas / 拖动暂存 / 闪烁 after id)
  • 接收回调: on_restore / on_close / on_push_current
  • 持有 theme,不依赖 PopupWindow 本身

接口:
  show()    创建或显示
  hide()    销毁
  flash(times=3)  收到 hexin 切股时闪烁提示
  is_visible() -> bool
"""
import tkinter as tk
from typing import Callable, Optional

from ..core import config as cfg_mod


# 球直径 (px),小一点更隐蔽
BALL_SIZE = 40


class FloatingBall:
    """
    屏幕右上角的圆形悬浮球。
    单击 → on_restore() (展开浮窗)
    右键 → 菜单 (推送当前股 / 关闭)
    拖动 → 自由摆位置
    """

    def __init__(
        self,
        parent_root: tk.Misc,
        theme: dict,
        on_restore: Callable[[], None],
        on_close: Callable[[], None],
        get_current_stock: Callable[[], tuple],  # () -> (code, name)
        on_push_current: Callable[[str, Optional[str]], None],
    ):
        self._parent = parent_root
        self._C = theme
        self._on_restore = on_restore
        self._on_close = on_close
        self._get_current = get_current_stock
        self._on_push_current = on_push_current

        self._ball = None
        self._canvas = None
        self._flash_job = None
        # 拖动暂存
        self._drag = {"x": 0, "y": 0, "start_x": 0, "start_y": 0, "moved": False}

    # ────────────────────────────────────────────
    # 显示 / 隐藏
    # ────────────────────────────────────────────
    def is_visible(self):
        return self._ball is not None

    def show(self):
        """新建或重新显示悬浮球。"""
        if self._ball is not None:
            try:
                self._ball.deiconify()
                self._ball.lift()
            except Exception:
                pass
            return

        C = self._C
        sz = BALL_SIZE

        # 读取保存的位置,没有则用屏幕右上角默认位置
        saved = self._load_ball_pos()
        if saved:
            x, y = saved
        else:
            try:
                sw = self._parent.winfo_screenwidth()
            except Exception:
                sw = 1920
            x = sw - sz - 20
            y = 80

        b = tk.Toplevel(self._parent)
        b.withdraw()
        b.overrideredirect(True)
        b.attributes('-topmost', True)
        # 透明背景: fuchsia 当 transparentcolor (仅 Windows 生效,Linux/Mac 静默回退)
        try:
            b.config(bg='#ff00ff')
            b.attributes('-transparentcolor', '#ff00ff')
        except Exception:
            b.config(bg='#e53935')
        b.geometry("{}x{}+{}+{}".format(sz, sz, x, y))

        cv = tk.Canvas(b, width=sz, height=sz,
                       bg='#ff00ff', highlightthickness=0, bd=0,
                       cursor='hand2')
        cv.pack()

        # 外圈底色（红色）
        pad = 2
        cv.create_oval(pad, pad, sz - pad, sz - pad,
                       fill='#e53935',
                       outline='#cc2b2b',
                       width=1,
                       tags='ball_bg')
        # 上半高光（模拟 3D 凸面感）
        cv.create_arc(pad + 3, pad + 2, sz - pad - 3, sz // 2 + 2,
                      start=0, extent=180,
                      fill='#ff6f6f', outline='', tags='ball_highlight')
        # 柱状图图标（3 根竖条 — 白色在红底上）
        cx, cy = sz // 2, sz // 2
        bar_w = 5
        bar_gap = 3
        bars = [(cx - bar_w - bar_gap, cy + 5, cx - bar_gap, cy - 6),
                (cx + 1, cy + 5, cx + 1 + bar_w, cy - 10),
                (cx + bar_w + bar_gap + 2, cy + 5,
                 cx + bar_w * 2 + bar_gap + 2, cy - 3)]
        for i, (x1, y1, x2, y2) in enumerate(bars):
            cv.create_rectangle(x1, y1, x2, y2,
                                fill='#ffffff', outline='', tags='ball_icon')
        # 右上角白色圆点
        cv.create_oval(sz - pad - 11, pad + 2, sz - pad - 3, pad + 10,
                       fill='#ffffff', outline='', tags='ball_dot1')
        # 左下角小圆点
        cv.create_oval(pad + 4, sz - pad - 10, pad + 10, sz - pad - 4,
                       fill='#cc2b2b', outline='', tags='ball_dot2')

        cv.bind('<Button-1>', self._on_press)
        cv.bind('<B1-Motion>', self._on_motion)
        cv.bind('<ButtonRelease-1>', self._on_release)
        cv.bind('<Button-3>', self._on_right_click)
        cv.bind('<Enter>', lambda e: self._hover(True))
        cv.bind('<Leave>', lambda e: self._hover(False))

        b.deiconify()
        self._ball = b
        self._canvas = cv

    def hide(self):
        """销毁悬浮球。"""
        # 停掉闪烁
        if self._flash_job and self._ball is not None:
            try:
                self._ball.after_cancel(self._flash_job)
            except Exception:
                pass
        self._flash_job = None
        if self._ball is not None:
            try:
                self._ball.destroy()
            except Exception:
                pass
        self._ball = None
        self._canvas = None

    # ────────────────────────────────────────────
    # 闪烁提示 (收到 hexin 切股时)
    # ────────────────────────────────────────────
    def flash(self, times=3):
        if self._ball is None or self._canvas is None:
            return
        # 停掉上一次未完成的闪烁
        if self._flash_job:
            try:
                self._ball.after_cancel(self._flash_job)
            except Exception:
                pass
            self._flash_job = None

        state = {'left': times * 2, 'on': True}

        def _tick():
            if state['left'] <= 0 or self._canvas is None:
                try:
                    if self._canvas:
                        self._canvas.itemconfig('ball_bg', fill='#e53935')
                except Exception:
                    pass
                self._flash_job = None
                return
            try:
                color = '#ffffff' if state['on'] else '#e53935'
                self._canvas.itemconfig('ball_bg', fill=color)
            except Exception:
                self._flash_job = None
                return
            state['on'] = not state['on']
            state['left'] -= 1
            try:
                self._flash_job = self._ball.after(180, _tick)
            except Exception:
                self._flash_job = None

        _tick()

    # ────────────────────────────────────────────
    # 拖动 / 单击区分
    # ────────────────────────────────────────────
    def _on_press(self, e):
        self._drag['x'] = e.x_root - self._ball.winfo_x()
        self._drag['y'] = e.y_root - self._ball.winfo_y()
        self._drag['start_x'] = e.x_root
        self._drag['start_y'] = e.y_root
        self._drag['moved'] = False

    def _on_motion(self, e):
        dx = abs(e.x_root - self._drag['start_x'])
        dy = abs(e.y_root - self._drag['start_y'])
        if dx > 5 or dy > 5:
            self._drag['moved'] = True
        x = e.x_root - self._drag['x']
        y = e.y_root - self._drag['y']
        try:
            self._ball.geometry("+{}+{}".format(x, y))
        except Exception:
            pass

    def _on_release(self, e):
        """没拖动 → 当单击 → 复原。拖动过 → 保存位置。"""
        if self._drag['moved']:
            # 拖动结束,保存位置
            try:
                self._save_ball_pos(self._ball.winfo_x(), self._ball.winfo_y())
            except Exception:
                pass
        else:
            try:
                self._ball.after(10, self._on_restore)
            except Exception:
                self._on_restore()

    # ────────────────────────────────────────────
    # 右键菜单
    # ────────────────────────────────────────────
    def _on_right_click(self, e):
        if self._ball is None:
            return
        C = self._C
        m = tk.Menu(self._ball, tearoff=0,
                    font=('微软雅黑', 9),
                    bg=C['card'], fg=C['text'],
                    activebackground=C['accent'],
                    activeforeground='white')
        m.add_command(label="📂 展开浮窗", command=self._on_restore)
        try:
            code, name = self._get_current()
        except Exception:
            code, name = (None, None)
        if code:
            m.add_command(
                label="📤 推送 {} 到同花顺".format(code),
                command=lambda c=code, n=name: self._on_push_current(c, n))
        m.add_separator()
        m.add_command(label="❌ 关闭浮窗", command=self._on_close)
        try:
            m.tk_popup(e.x_root, e.y_root)
        finally:
            m.grab_release()

    def _hover(self, entered):
        if self._canvas is None:
            return
        try:
            color = '#ff6f6f' if entered else '#e53935'
            self._canvas.itemconfig('ball_bg', fill=color)
        except Exception:
            pass

    # ────────────────────────────────────────────
    # 位置持久化
    # ────────────────────────────────────────────
    def _load_ball_pos(self):
        """从 settings 读取悬浮球位置,返回 (x, y) 或 None。"""
        try:
            s = cfg_mod.load_settings()
            pos = s.get('ball_position')
            if pos and isinstance(pos, (list, tuple)) and len(pos) == 2:
                return int(pos[0]), int(pos[1])
        except Exception:
            pass
        return None

    def _save_ball_pos(self, x, y):
        """保存悬浮球位置到 settings。"""
        try:
            s = cfg_mod.load_settings()
            s['ball_position'] = [x, y]
            cfg_mod.save_settings(s)
        except Exception:
            pass
