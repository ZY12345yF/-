"""
PopupView — 浮窗 UI 构建

原 popup_window.py 里:
  _build_window()          — 700+ 行,所有 widget 构造
  _render_record(rec)      — 把分析记录画到 Text (已移至 .render)
  _render_no_history()     (已移至 .render)
  _render_linked_grid()    — 顶部联动股 2×3 grid (已移至 .render)
  _update_title()          (已移至 .render)

抽离规则 (按文档 五·原则 1):
  • View 不做业务: 没有 if 业务条件, 没有 fetch, 没有 settings 读写
  • View 接收 callbacks (controller 注入),不引用 controller 本身
  • View 暴露 widget 引用给 controller (self.name_lbl / self.detail / ...)
    这是 Tkinter 的现实约束 — 后期换到 PyQt 时这些命名也直接复用

注意:
  • View 不持有 PopupState 引用,所有需要的状态由 controller 在调用方法时传入
  • 这样保证 view 的接口是显式的,看 method 签名就知道它需要什么数据
"""
import tkinter as tk
from tkinter import ttk

from .render import PopupRenderMixin


class PopupView(PopupRenderMixin):
    """
    所有 Tk widget 都在这里创建,渲染逻辑由 PopupRenderMixin 提供。

    构造时只接 root + theme + 一组回调 (controller 注入)。
    callbacks 的命名跟 controller 方法对齐,看名字就知道点哪个键调哪个。
    """

    def __init__(
        self,
        root: tk.Toplevel,
        theme: dict,
        initial_geometry: str,
        callbacks: dict,
        initial_follow_mode: bool = True,
        min_w: int = 380,
        min_h: int = 320,
    ):
        """
        Args:
            root: PopupController 创建的 Toplevel
            theme: stock_app.core.theme.get() 返回的色板
            initial_geometry: 上次保存的 geometry
            callbacks: dict, 见 _required_callbacks
            initial_follow_mode: 启动时的 follow 开关
            min_w/min_h: 最小尺寸
        """
        self._root = root
        self._C = theme
        self._cb = callbacks  # controller 注入的所有回调
        self._follow_mode_init = initial_follow_mode
        self._min_w = min_w
        self._min_h = min_h
        self._initial_geo = initial_geometry
        self._topmost_state = True

        # 所有 widget 句柄,controller 渲染时直接访问
        # 命名风格: leading underscore 表示"只该被 controller 和 view 自己用"
        self._title_label = None
        self._btn_min = None
        self._btn_follow = None
        self._btn_ai = None
        self._name_lbl = None
        self._code_lbl = None
        self._price_lbl = None
        self._chg_lbl = None
        self._quote_time_lbl = None
        self._linked_frame = None
        self._detail = None
        self._date_combo = None
        self._date_var = None
        self._grip = None
        self._title_bar = None
        self._summary_frame = None
        self._detail_wrap = None
        self._bottom_frame = None
        self._status_bar = None
        self._hexin_status_var = None
        self._hexin_count_var = None

        self.build()
        self._start_keep_topmost()

    # ════════════════════════════════════════════════
    # 公开属性 (controller 渲染时访问)
    # ════════════════════════════════════════════════
    @property
    def hexin_status_var(self):
        return self._hexin_status_var

    @property
    def hexin_count_var(self):
        return self._hexin_count_var

    @property
    def title_label(self):
        return self._title_label

    @property
    def title_bar(self):
        return self._title_bar

    @property
    def btn_min(self):
        return self._btn_min

    @property
    def btn_follow(self):
        return self._btn_follow

    @property
    def btn_ai(self):
        return self._btn_ai

    @property
    def grip(self):
        """右下角缩放手柄。controller 拿去绑给 DragResizeHandler。"""
        return self._grip

    @property
    def detail_text(self):
        """detail Text widget。极少数情况下 controller 需要直接访问。"""
        return self._detail

    # ════════════════════════════════════════════════
    # 构建
    # ════════════════════════════════════════════════
    def build(self):
        """构建整个浮窗 UI。只调用一次。"""
        C = self._C
        w = self._root
        w.geometry(self._initial_geo)
        w.minsize(self._min_w, self._min_h)
        w.configure(bg=C['bg'])
        w.overrideredirect(True)
        w.attributes('-topmost', True)

        self._build_title_bar()
        self._build_summary()
        self._build_detail()
        self._build_bottom_bar()
        self._build_status_bar()
        self._build_resize_grip()

    def _start_keep_topmost(self):
        """每 2s 重申一次 topmost,防止被其它窗口压住。取消置顶时不强制。"""
        w = self._root

        def _tick():
            try:
                if self._topmost_state:
                    w.attributes('-topmost', True)
                w.after(2000, _tick)
            except tk.TclError:
                pass

        w.after(2000, _tick)

    def _build_title_bar(self):
        C = self._C
        w = self._root
        _bar_bg = '#ffffff'
        _bar_fg = C['bg']

        title_bar = tk.Frame(w, bg=_bar_bg, height=32)
        title_bar.pack(fill='x', side='top')
        title_bar.pack_propagate(False)
        self._title_bar = title_bar

        self._title_label = tk.Label(
            title_bar, text="📊  股票详情",
            font=('微软雅黑', 10, 'bold'),
            bg=_bar_bg, fg=_bar_fg)
        self._title_label.pack(side='left', padx=10)

        # ✕ 关闭
        btn_close = tk.Label(title_bar, text=" ✕ ",
                             font=('微软雅黑', 11, 'bold'),
                             bg=_bar_bg, fg=_bar_fg,
                             cursor='hand2', padx=8)
        btn_close.pack(side='right')
        btn_close.bind('<Button-1>', lambda e: self._cb['on_hide']())
        btn_close.bind('<Enter>', lambda e: btn_close.config(bg=C['red'], fg='white'))
        btn_close.bind('<Leave>', lambda e: btn_close.config(bg=_bar_bg, fg=_bar_fg))

        # ─ 最小化
        self._btn_min = tk.Label(title_bar, text=" ─ ",
                                 font=('微软雅黑', 11, 'bold'),
                                 bg=_bar_bg, fg=_bar_fg,
                                 cursor='hand2', padx=8)
        self._btn_min.pack(side='right')
        self._btn_min.bind('<Button-1>', lambda e: self._cb['on_toggle_minimize']())
        self._btn_min.bind('<Enter>',
                           lambda e: self._btn_min.config(bg=C['card']))
        self._btn_min.bind('<Leave>',
                           lambda e: self._btn_min.config(bg=_bar_bg))

        # 分隔线
        tk.Frame(title_bar, bg=C['border'], width=1).pack(
            side='right', fill='y', padx=4, pady=7)

        # 📌 置顶/取消置顶
        self._btn_pin = tk.Label(
            title_bar, text="📌",
            font=('微软雅黑', 10),
            bg=_bar_bg, fg=_bar_fg,
            cursor='hand2', padx=6)
        self._btn_pin.pack(side='right')
        self._btn_pin.bind('<Button-1>', lambda e: self._cb['on_toggle_topmost']())
        self._btn_pin.bind('<Enter>',
                           lambda e: self._btn_pin.config(bg=C['card']))
        self._btn_pin.bind('<Leave>',
                           lambda e: self._btn_pin.config(bg=_bar_bg))
        pin_tip = "置顶: 浮窗始终在最前面"
        self._btn_pin.bind('<Enter>',
                           lambda e: self._hexin_status_var.set(pin_tip), add='+')
        self._btn_pin.bind('<Leave>',
                           lambda e: self._cb['on_restore_status_text'](), add='+')

        # ● 跟随同花顺 (pill 样式 - 激活时绿底白字)
        if self._follow_mode_init:
            _follow_bg, _follow_fg = C['green'], '#ffffff'
            _follow_text = "● 跟随"
        else:
            _follow_bg, _follow_fg = _bar_bg, C['dim']
            _follow_text = "○ 跟随"
        self._btn_follow = tk.Label(
            title_bar, text=_follow_text,
            font=('微软雅黑', 9, 'bold'),
            bg=_follow_bg, fg=_follow_fg,
            cursor='hand2', padx=6, pady=1)
        self._btn_follow.pack(side='right')
        self._btn_follow.bind('<Button-1>', lambda e: self._cb['on_toggle_follow']())

        def _follow_enter(e):
            self._hexin_status_var.set(
                "跟随同花顺: 在同花顺里切股票时,浮窗自动跟着切")

        def _follow_leave(e):
            self._cb['on_restore_status_text']()

        self._btn_follow.bind('<Enter>', _follow_enter)
        self._btn_follow.bind('<Leave>', _follow_leave)

        self._btn_follow.bind('<Enter>', _follow_enter)
        self._btn_follow.bind('<Leave>', _follow_leave)

    def _build_summary(self):
        C = self._C
        w = self._root

        # v9.9.6.5: 顶级容器外存,最小化时 pack_forget 用
        self._summary_frame = tk.Frame(w, bg=C['card'])
        self._summary_frame.pack(fill='x', side='top', padx=8, pady=(8, 0))
        inner = tk.Frame(self._summary_frame, bg=C['card'])
        inner.pack(fill='x', padx=12, pady=10)

        # 第一行: 股票名 + 代码 + 联动股网格 + AI 按钮
        line1 = tk.Frame(inner, bg=C['card']); line1.pack(fill='x')
        self._name_lbl = tk.Label(
            line1, text="—",
            font=('微软雅黑', 16, 'bold'),
            bg=C['card'], fg=C['text'])
        self._name_lbl.pack(side='left')

        # 代码 = 蓝字下划线,点击推送
        self._code_lbl = tk.Label(
            line1, text="",
            font=('微软雅黑', 11, 'underline'),
            bg=C['card'], fg=C['accent'],
            cursor='hand2')
        self._code_lbl.pack(side='left', padx=(8, 0), pady=(6, 0))
        def _on_code_press(e):
            self._code_lbl.config(
                fg=C['accent'], font=('微软雅黑', 13, 'bold underline'))
            self._code_lbl.after(80, lambda: self._code_lbl.config(
                fg=C['accent'], font=('微软雅黑', 11, 'underline')))
            self._cb['on_push_current_code']()
            # 三击检测：通知 Controller 处理
            code = self._code_lbl.cget('text')
            if code:
                name = self._name_lbl.cget('text')
                self._cb['on_triple_click'](code, name)

        self._code_lbl.bind('<Button-1>', _on_code_press)
        self._code_lbl.bind('<Enter>',
                             lambda e: self._code_lbl.config(fg=C['accent']))
        self._code_lbl.bind('<Leave>',
                             lambda e: self._code_lbl.config(fg=C['accent']))

        # AI 分析按钮 (先 pack right 让 grid 占满中间)
        self._btn_ai = tk.Label(
            line1, text="  📋 立即 AI 分析  ",
            font=('微软雅黑', 9, 'bold'),
            bg=C['purple'], fg='white',
            cursor='hand2', padx=8, pady=4)
        self._btn_ai.pack(side='right', pady=(4, 0))
        self._btn_ai.bind('<Button-1>',
                           lambda e: self._cb['on_request_ai_analyze']())

        # 联动股 grid 占中间
        # 修法 v10.x: 固定 46px 高 + 关 propagate
        # 原因: line1 的高度由 _name_lbl (16pt bold ~28px) 决定,
        #       _linked_frame 默认会随父容器收缩,grid 2 行 (~46px) 会被裁。
        #       强制 height=46 + pack_propagate(False) 让它占住地盘,
        #       第一行 grid 出来后不会再缩。
        self._linked_frame = tk.Frame(line1, bg=C['card'], height=46)
        self._linked_frame.pack(side='left', expand=True, fill='both',
                                 padx=(20, 12))
        self._linked_frame.pack_propagate(False)

        # 第二行: 价格 + 涨跌
        line2 = tk.Frame(inner, bg=C['card']); line2.pack(fill='x', pady=(6, 0))
        self._price_lbl = tk.Label(
            line2, text="—",
            font=('微软雅黑', 22, 'bold'),
            bg=C['card'], fg=C['text'])
        self._price_lbl.pack(side='left')
        self._chg_lbl = tk.Label(
            line2, text="",
            font=('微软雅黑', 13, 'bold'),
            bg=C['card'], fg=C['dim'])
        self._chg_lbl.pack(side='left', padx=(14, 0), pady=(8, 0))
        self._quote_time_lbl = tk.Label(
            line2, text="",
            font=('微软雅黑', 9),
            bg=C['card'], fg=C['dim'])
        self._quote_time_lbl.pack(side='right', pady=(10, 0))

    def _build_detail(self):
        C = self._C
        w = self._root

        self._detail_wrap = tk.Frame(w, bg=C['bg'])
        self._detail_wrap.pack(fill='both', expand=True, padx=8, pady=8)
        self._detail = tk.Text(
            self._detail_wrap, font=('微软雅黑', 10), wrap='word',
            bg=C['card'], fg=C['text'],
            relief='flat', padx=12, pady=10,
            state='disabled', cursor='arrow')
        d_vsb = ttk.Scrollbar(self._detail_wrap, orient='vertical',
                              command=self._detail.yview)
        self._detail.configure(yscrollcommand=d_vsb.set)
        self._detail.pack(side='left', fill='both', expand=True)
        d_vsb.pack(side='right', fill='y')

        # tag 样式
        for tag, fg, bg in [
            ('h1', C['accent'], ''), ('h2', C['yellow'], ''),
            ('dim', C['dim'], ''), ('green', C['green'], ''),
            ('red', C['red'], ''),  ('star', C['star'], ''),
            ('star_tag', C['star'], ''), ('accent', C['accent'], ''),
            ('policy', C['yellow'], ''), ('concept', C['green'], ''),
            ('money', C['red'], ''), ('percent', C['accent'], ''),
            ('category', 'white', C['purple']),
            ('category_kw', '#05070b', C['star']),
            ('up', C['red'], ''), ('down', C['green'], ''),
            ('flat', C['dim'], ''),
        ]:
            kw = {'foreground': fg}
            if bg:
                kw['background'] = bg
            if tag in ('category', 'category_kw'):
                kw['font'] = ('微软雅黑', 10, 'bold')
            self._detail.tag_config(tag, **kw)
        self._detail.tag_config(
            'h1bold',
            font=('微软雅黑', 12, 'bold'), foreground=C['accent'])

    def _build_bottom_bar(self):
        C = self._C
        w = self._root

        self._bottom_frame = tk.Frame(w, bg=C['bg'], height=36)
        self._bottom_frame.pack(fill='x', side='bottom')
        self._bottom_frame.pack_propagate(False)
        tk.Label(self._bottom_frame, text="📅 日期:", font=('微软雅黑', 9),
                 bg=C['bg'], fg=C['dim']).pack(side='left', padx=(10, 2))
        self._date_var = tk.StringVar()
        self._date_combo = ttk.Combobox(
            self._bottom_frame, textvariable=self._date_var,
            state='readonly', width=22,
            font=('微软雅黑', 9))
        self._date_combo.pack(side='left', padx=(0, 8))
        self._date_combo.bind(
            '<<ComboboxSelected>>',
            lambda e: self._cb['on_date_change']())

        refresh_btn = tk.Label(
            self._bottom_frame, text="🔄 刷新行情",
            font=('微软雅黑', 9), bg=C['bg'],
            fg=C['accent'], cursor='hand2', padx=8)
        refresh_btn.pack(side='left')
        refresh_btn.bind('<Button-1>',
                          lambda e: self._cb['on_refresh_quote']())

    def _build_status_bar(self):
        C = self._C
        w = self._root

        self._status_bar = tk.Frame(w, bg=C['panel'], height=22)
        self._status_bar.pack(fill='x', side='bottom')
        self._status_bar.pack_propagate(False)
        self._hexin_status_var = tk.StringVar(value="⏳ 同花顺联动: 启动中...")
        tk.Label(self._status_bar, textvariable=self._hexin_status_var,
                 font=('微软雅黑', 8), bg=C['panel'],
                 fg=C['dim']).pack(side='left', padx=8)
        self._hexin_count_var = tk.StringVar(value="切换 0 次")
        tk.Label(self._status_bar, textvariable=self._hexin_count_var,
                 font=('微软雅黑', 8), bg=C['panel'],
                 fg=C['accent']).pack(side='right', padx=8)

    def _build_resize_grip(self):
        C = self._C
        w = self._root

        self._grip = tk.Label(
            w, text="◢", font=('微软雅黑', 9),
            bg=C['bg'], fg=C['dim'], cursor='bottom_right_corner')
        self._grip.place(relx=1.0, rely=1.0, anchor='se')
