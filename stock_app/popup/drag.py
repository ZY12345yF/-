"""
DragResizeHandler — 浮窗拖动 + 缩放 + 几何持久化

原 popup_window.py 里 _drag_start / _drag_motion / _drag_end / _resize_*
/ _save_geometry / _title_context_menu / _show_size_dialog / _reset_size。

抽离后:
  • 拖动 / 缩放本身是纯交互,不耦合业务
  • 几何存盘读 settings (cfg_mod),独立保存到 popup_geometry
  • 设置对话框 (自定义大小) 也在这里,因为它直接操作 geometry
"""
import tkinter as tk

from ..core import config as cfg_mod
from .state import PopupState


class DragResizeHandler:
    """
    持有: window (Toplevel), state (PopupState, 用其 drag_data / resize_data
    / MIN_W / MIN_H / minimized 标志)。
    """

    def __init__(self, window: tk.Toplevel, state: PopupState, theme: dict):
        self._win = window
        self._state = state
        self._C = theme

    # ────────────────────────────────────────────
    # 拖动 (标题栏)
    # ────────────────────────────────────────────
    def bind_title_drag(self, widget):
        """让 widget 成为拖动把手 (整窗跟随)。"""
        widget.bind('<Button-1>', self._drag_start)
        widget.bind('<B1-Motion>', self._drag_motion)
        widget.bind('<ButtonRelease-1>', self._drag_end)

    def _drag_start(self, e):
        self._state.drag_data['x'] = e.x_root - self._win.winfo_x()
        self._state.drag_data['y'] = e.y_root - self._win.winfo_y()

    def _drag_motion(self, e):
        x = e.x_root - self._state.drag_data['x']
        y = e.y_root - self._state.drag_data['y']
        try:
            self._win.geometry("+{}+{}".format(x, y))
        except Exception:
            pass

    def _drag_end(self, _e):
        self.save_geometry()

    # ────────────────────────────────────────────
    # 缩放 (右下角手柄)
    # ────────────────────────────────────────────
    def bind_resize_grip(self, widget):
        """让 widget 成为右下角缩放把手。"""
        widget.bind('<Button-1>', self._resize_start)
        widget.bind('<B1-Motion>', self._resize_motion)
        widget.bind('<ButtonRelease-1>', self._resize_end)

    def _resize_start(self, e):
        self._state.resize_data['x'] = e.x_root
        self._state.resize_data['y'] = e.y_root
        self._state.resize_data['w'] = self._win.winfo_width()
        self._state.resize_data['h'] = self._win.winfo_height()

    def _resize_motion(self, e):
        dx = e.x_root - self._state.resize_data['x']
        dy = e.y_root - self._state.resize_data['y']
        new_w = max(self._state.MIN_W, self._state.resize_data['w'] + dx)
        new_h = max(self._state.MIN_H, self._state.resize_data['h'] + dy)
        x = self._win.winfo_x()
        y = self._win.winfo_y()
        try:
            self._win.geometry("{}x{}+{}+{}".format(new_w, new_h, x, y))
        except Exception:
            pass

    def _resize_end(self, _e):
        self.save_geometry()

    # ────────────────────────────────────────────
    # 几何持久化
    # ────────────────────────────────────────────
    def save_geometry(self):
        """把当前 geometry 写到 settings.json。最小化状态不存。"""
        if self._state.minimized:
            return
        try:
            geo = self._win.geometry()
            s = cfg_mod.load_settings()
            s["popup_geometry"] = geo
            cfg_mod.save_settings(s)
        except Exception:
            pass

    # ────────────────────────────────────────────
    # 自定义大小对话框 (标题栏右键)
    # ────────────────────────────────────────────
    def show_size_dialog(self):
        """弹出"设置浮窗大小"小对话框。"""
        C = self._C
        win = self._win
        dialog = tk.Toplevel(win)
        dialog.title("自定义浮窗大小")
        dialog.geometry("300x160+{}+{}".format(
            win.winfo_x() + 80, win.winfo_y() + 120))
        dialog.resizable(False, False)
        dialog.configure(bg=C['card'])
        dialog.attributes('-topmost', True)
        dialog.transient(win)

        cur_w = win.winfo_width()
        cur_h = win.winfo_height()

        frame = tk.Frame(dialog, bg=C['card'])
        frame.pack(fill='both', expand=True, padx=16, pady=12)
        tk.Label(frame, text="宽度:", font=('微软雅黑', 10),
                 bg=C['card'], fg=C['text']).grid(
                     row=0, column=0, sticky='e', pady=8)
        w_var = tk.StringVar(value=str(cur_w))
        w_entry = tk.Entry(frame, textvariable=w_var, width=8,
                           font=('微软雅黑', 11),
                           bg=C['bg'], fg=C['text'],
                           insertbackground=C['text'],
                           relief='solid', bd=1, justify='center')
        w_entry.grid(row=0, column=1, padx=(8, 20), pady=8)
        w_entry.select_range(0, 'end')
        w_entry.focus_set()
        tk.Label(frame, text="高度:", font=('微软雅黑', 10),
                 bg=C['card'], fg=C['text']).grid(
                     row=0, column=2, sticky='e', pady=8)
        h_var = tk.StringVar(value=str(cur_h))
        h_entry = tk.Entry(frame, textvariable=h_var, width=8,
                           font=('微软雅黑', 11),
                           bg=C['bg'], fg=C['text'],
                           insertbackground=C['text'],
                           relief='solid', bd=1, justify='center')
        h_entry.grid(row=0, column=3, padx=(8, 0), pady=8)

        def apply_size():
            try:
                nw = max(self._state.MIN_W, int(w_var.get()))
                nh = max(self._state.MIN_H, int(h_var.get()))
            except ValueError:
                dialog.destroy()
                return
            x = win.winfo_x()
            y = win.winfo_y()
            win.geometry("{}x{}+{}+{}".format(nw, nh, x, y))
            self.save_geometry()
            dialog.destroy()

        btn_frame = tk.Frame(frame, bg=C['card'])
        btn_frame.grid(row=1, column=0, columnspan=4, pady=(16, 0))
        btn_ok = tk.Label(btn_frame, text="  确定  ",
                          font=('微软雅黑', 10, 'bold'),
                          bg=C['accent'], fg='white',
                          cursor='hand2', padx=14, pady=4)
        btn_ok.pack(side='left', padx=4)
        btn_ok.bind('<Button-1>', lambda e: apply_size())
        btn_cancel = tk.Label(btn_frame, text="  取消  ",
                              font=('微软雅黑', 10),
                              bg=C['dim'], fg='white',
                              cursor='hand2', padx=14, pady=4)
        btn_cancel.pack(side='left', padx=4)
        btn_cancel.bind('<Button-1>', lambda e: dialog.destroy())
        dialog.bind('<Return>', lambda e: apply_size())
        dialog.bind('<Escape>', lambda e: dialog.destroy())

    def reset_to_default_size(self):
        """重置到 600×700,保持当前左上角位置。"""
        x = self._win.winfo_x()
        y = self._win.winfo_y()
        try:
            self._win.geometry("600x700+{}+{}".format(x, y))
            self.save_geometry()
        except Exception:
            pass

    def show_title_context_menu(self, e):
        """标题栏右键菜单。"""
        C = self._C
        menu = tk.Menu(self._win, tearoff=0,
                       font=('微软雅黑', 10),
                       bg=C['card'], fg=C['text'],
                       activebackground=C['accent'],
                       activeforeground='white')
        menu.add_command(label="📐 自定义窗口大小...",
                         command=self.show_size_dialog)
        menu.add_command(label="🔄 重置为默认大小 (600×700)",
                         command=self.reset_to_default_size)
        try:
            menu.tk_popup(e.x_root, e.y_root)
        finally:
            menu.grab_release()
