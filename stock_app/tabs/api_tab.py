"""
API 管理 Tab
- 修改 API URL / 模型 / Keys
- 🆕 模型与URL强联动
- 🆕 Keys 池分离：百度千帆与火山方舟独立管理，随模型精准切换
"""
import tkinter as tk
from tkinter import ttk, messagebox

from .base import BaseTab
from ..widgets import make_card, styled_btn, styled_entry
from ..core import config as cfg_mod
from ..bus import bus, Events


class ApiTab(BaseTab):
    title = "API管理"

    def __init__(self, app):
        super().__init__(app)
        self._qianfan_keys = []
        self._volcano_keys = []
        self._other_keys = []           # 第三方厂商（DeepSeek/智谱/Kimi/阿里等）
        self._current_key_type = "qianfan"  # 状态锁：qianfan / volcano / other

    def build(self, parent):
        C = self.C
        body = tk.Frame(parent, bg=C['bg'])
        body.pack(fill='both', expand=True, padx=16, pady=12)

        tk.Label(body, text="🔑 API 全局管理", font=('微软雅黑', 12, 'bold'),
                 bg=C['bg'], fg=C['text']).pack(anchor='w', pady=(0, 8))
        tk.Label(body, text="切换模型时，URL和Key列表会自动联动切换，保存后全局生效",
                 font=('微软雅黑', 9), bg=C['bg'], fg=C['dim']).pack(anchor='w', pady=(0, 12))

        # ── 接口配置 ──────────────────────────
        rc = make_card(body, "🌐  接口与模型配置（强联动）", pady_top=0)

        # URL
        row_url = tk.Frame(rc, bg=C['panel'])
        row_url.pack(fill='x', pady=3)
        tk.Label(row_url, text="API URL", font=('微软雅黑', 9),
                 bg=C['panel'], fg=C['dim'], width=14, anchor='w').pack(side='left')
        self.url_var = tk.StringVar(value=self.app.cfg.get("api_url", ""))
        styled_entry(row_url, self.url_var).pack(side='left', fill='x', expand=True,
                                                  padx=(4, 0), ipady=4)

        # Model（下拉）
        row_model = tk.Frame(rc, bg=C['panel'])
        row_model.pack(fill='x', pady=3)
        tk.Label(row_model, text="模型 Model", font=('微软雅黑', 9),
                 bg=C['panel'], fg=C['dim'], width=14, anchor='w').pack(side='left')

        cur_id = self.app.cfg.get("model", "")
        cur_disp = cfg_mod.model_id_to_display_name(cur_id)
        self.model_var = tk.StringVar(value=cur_disp)

        style = ttk.Style()
        style.configure("Dark.TCombobox",
                        fieldbackground=C['card'], background=C['card'],
                        foreground=C['text'], arrowcolor=C['accent'],
                        borderwidth=0)
        self.model_combo = ttk.Combobox(row_model, textvariable=self.model_var,
                                        values=cfg_mod.MODEL_LIST,
                                        style="Dark.TCombobox",
                                        font=('微软雅黑', 9), state='readonly')
        self.model_combo.pack(side='left', fill='x', expand=True, padx=(4, 0), ipady=4)

        self.model_id_label = tk.Label(rc, text="ID: " + cur_id,
                                        font=('Consolas', 8),
                                        bg=C['panel'], fg=C['dim'])
        self.model_id_label.pack(anchor='w', padx=(150, 0), pady=(2, 0))

        # 核心：模型选择联动逻辑 (URL + Keys)
        def _on_model_change(e=None):
            disp = self.model_var.get()
            new_id = cfg_mod.display_name_to_model_id(disp)
            self.model_id_label.config(text="ID: " + new_id)

            # 1. 先保存当前文本框 Keys 到内存
            self._save_current_keys_to_memory()

            # 2. 根据模型前缀决定 URL 和 Key 池
            # 🔧 自定义模型：不自动切 URL，让用户自己填
            if not disp.startswith("🔧"):
                target_url = cfg_mod.get_url_for_model(disp)
                if target_url:
                    self.url_var.set(target_url)
            target_pool = cfg_mod.key_pool_for_model(disp)

            # 3. 加载新池子的 Keys 到文本框
            self._current_key_type = target_pool
            self._load_keys_to_ui()

        self.model_combo.bind("<<ComboboxSelected>>", _on_model_change)

        # 一键切换 API 厂商
        switch_row = tk.Frame(rc, bg=C['panel'])
        switch_row.pack(fill='x', pady=(8, 0))
        tk.Label(switch_row, text="快捷切换：", font=('微软雅黑', 8),
                 bg=C['panel'], fg=C['dim'], width=14, anchor='w').pack(side='left')
        styled_btn(switch_row, "🔵 百度千帆", C['accent'],
                   self._switch_to_qianfan, pady=2).pack(side='left', padx=(4, 4))
        styled_btn(switch_row, "🌋 火山方舟", C['red'],
                   self._switch_to_volcano, pady=2).pack(side='left', padx=(0, 4))
        styled_btn(switch_row, "🐋 DeepSeek", '#4d6bfe',
                   self._switch_to_deepseek, pady=2).pack(side='left', padx=(0, 4))
        styled_btn(switch_row, "🧪 智谱GLM", '#3fc7ff',
                   self._switch_to_zhipu, pady=2).pack(side='left', padx=(0, 4))
        styled_btn(switch_row, "🌙 Kimi", '#6355a8',
                   self._switch_to_moonshot, pady=2).pack(side='left', padx=(0, 4))
        styled_btn(switch_row, "☁️ 阿里百炼", '#ff6a00',
                   self._switch_to_dashscope, pady=2).pack(side='left', padx=(0, 4))

        # ── 🆕 Key 列表区域 (带动态大标题) ──────────────────────────
        kc = make_card(body, "🔑  当前编辑：", pady_top=8)
        
        # 动态大标题：明确告知用户现在编辑的是哪家
        self._key_type_hint = tk.StringVar(value="🔵 百度千帆 API Keys")
        tk.Label(kc, textvariable=self._key_type_hint, 
                 font=('微软雅黑', 11, 'bold'), 
                 bg=C['panel'], fg=C['accent']).pack(anchor='w', pady=(0, 6))

        self.keys_text = tk.Text(kc, font=('Consolas', 9),
                                 bg=C['card'], fg=C['text'],
                                 insertbackground='white', relief='flat',
                                 height=10)
        self.keys_text.pack(fill='x', pady=(0, 6))

        tk.Label(kc, text="💡 此列表随上方模型自动切换，请确保 Key 与模型匹配",
                 font=('微软雅黑', 8), bg=C['panel'], fg=C['dim']).pack(anchor='w')

        # ── 操作按钮 ──────────────────────────
        btn_row = tk.Frame(body, bg=C['bg'])
        btn_row.pack(fill='x', pady=(12, 0))
        styled_btn(btn_row, "💾  保存所有配置", C['green'],
                   self._save, pady=8).pack(side='left')
        self.save_status = tk.StringVar(value="")
        tk.Label(btn_row, textvariable=self.save_status,
                 font=('微软雅黑', 9), bg=C['bg'], fg=C['green']).pack(side='left', padx=12)

        # 初始化加载 Keys 到内存和文本框
        self._init_keys()

    def _init_keys(self):
        """初始化读取分离的 Keys"""
        self._qianfan_keys = self.app.cfg.get("qianfan_api_keys", [])
        self._volcano_keys = self.app.cfg.get("volcano_api_keys", [])
        self._other_keys = self.app.cfg.get("other_api_keys", [])

        # 兼容旧版本
        if not self._qianfan_keys and not self._volcano_keys and not self._other_keys:
            self._qianfan_keys = self.app.cfg.get("api_keys", [])

        # 根据当前模型决定显示哪组 Keys
        self._current_key_type = cfg_mod.key_pool_for_model(self.model_var.get())
        self._load_keys_to_ui()

    def _save_current_keys_to_memory(self):
        """将当前文本框的 Keys 暂存到内存对应的列表"""
        raw_keys = self.keys_text.get("1.0", "end").strip().splitlines()
        current_keys = [k.strip() for k in raw_keys if k.strip()]

        if self._current_key_type == "volcano":
            self._volcano_keys = current_keys
        elif self._current_key_type == "other":
            self._other_keys = current_keys
        else:
            self._qianfan_keys = current_keys

    def _load_keys_to_ui(self):
        """将内存中的 Keys 填入文本框，并更新大标题"""
        if self._current_key_type == "volcano":
            keys_list = self._volcano_keys
            self._key_type_hint.set("🌋 火山方舟 API Keys")
        elif self._current_key_type == "other":
            keys_list = self._other_keys
            self._key_type_hint.set("🌐 第三方厂商 API Keys")
        else:
            keys_list = self._qianfan_keys
            self._key_type_hint.set("🔵 百度千帆 API Keys")
            
        self.keys_text.config(state='normal')
        self.keys_text.delete('1.0', 'end')
        self.keys_text.insert('1.0', "\n".join(keys_list))

    def _save(self):
        # 1. 暂存当前文本框的 Keys
        self._save_current_keys_to_memory()

        # 2. 收集新值
        new_url   = self.url_var.get().strip()
        disp = self.model_var.get().strip()
        new_model = cfg_mod.display_name_to_model_id(disp)

        # 3. 写回配置（三个 Key 池全部保存）
        self.app.cfg["api_url"]  = new_url
        self.app.cfg["model"]    = new_model
        self.app.cfg["qianfan_api_keys"] = self._qianfan_keys
        self.app.cfg["volcano_api_keys"] = self._volcano_keys
        self.app.cfg["other_api_keys"]   = self._other_keys

        # 全局 api_keys 根据当前选中的模型动态赋值
        pool = cfg_mod.key_pool_for_model(disp)
        if pool == "volcano":
            self.app.cfg["api_keys"] = self._volcano_keys
        elif pool == "other":
            self.app.cfg["api_keys"] = self._other_keys
        else:
            self.app.cfg["api_keys"] = self._qianfan_keys

        cfg_mod.save_config(self.app.cfg)

        # 触发事件 → 所有Tab自动刷新
        bus.emit(Events.API_KEYS_CHANGED, self.app.cfg["api_keys"])

        qf_cnt = len(self._qianfan_keys)
        volc_cnt = len(self._volcano_keys)
        oth_cnt = len(self._other_keys)
        pool_label = {"volcano": "火山", "other": "第三方", "qianfan": "千帆"}.get(pool, pool)
        self.save_status.set("✅ 已保存 (千帆:{} 火山:{} 其他:{}, 激活:{})".format(
            qf_cnt, volc_cnt, oth_cnt, pool_label))
        self.frame.after(4000, lambda: self.save_status.set(""))

    # ════════════════════════════════════════════
    # 厂商一键切换
    # ════════════════════════════════════════════
    def _switch_to_qianfan(self):
        self._save_current_keys_to_memory()
        self.url_var.set(cfg_mod.PROVIDER_URLS["qianfan"])
        self.model_var.set("🆓 ERNIE-4.5-Turbo-32K")
        self.model_id_label.config(text="ID: " + cfg_mod.display_name_to_model_id(self.model_var.get()))
        self._current_key_type = "qianfan"
        self._load_keys_to_ui()

    def _switch_to_volcano(self):
        self._save_current_keys_to_memory()
        self.url_var.set(cfg_mod.PROVIDER_URLS["volcano"])
        self.model_var.set("🌋 doubao-seed-2-0-pro")
        self.model_id_label.config(text="ID: " + cfg_mod.display_name_to_model_id(self.model_var.get()))
        self._current_key_type = "volcano"
        self._load_keys_to_ui()

    def _switch_to_deepseek(self):
        self._save_current_keys_to_memory()
        self.url_var.set(cfg_mod.PROVIDER_URLS["deepseek"])
        self.model_var.set("🐋 DeepSeek-V3.2 (官方)")
        self.model_id_label.config(text="ID: " + cfg_mod.display_name_to_model_id(self.model_var.get()))
        self._current_key_type = "other"
        self._load_keys_to_ui()

    def _switch_to_zhipu(self):
        self._save_current_keys_to_memory()
        self.url_var.set(cfg_mod.PROVIDER_URLS["zhipu"])
        self.model_var.set("🧪 GLM-4-Plus")
        self.model_id_label.config(text="ID: " + cfg_mod.display_name_to_model_id(self.model_var.get()))
        self._current_key_type = "other"
        self._load_keys_to_ui()

    def _switch_to_moonshot(self):
        self._save_current_keys_to_memory()
        self.url_var.set(cfg_mod.PROVIDER_URLS["moonshot"])
        self.model_var.set("🌙 moonshot-v1-128k")
        self.model_id_label.config(text="ID: " + cfg_mod.display_name_to_model_id(self.model_var.get()))
        self._current_key_type = "other"
        self._load_keys_to_ui()

    def _switch_to_dashscope(self):
        self._save_current_keys_to_memory()
        self.url_var.set(cfg_mod.PROVIDER_URLS["dashscope"])
        self.model_var.set("☁️ Qwen3-Plus")
        self.model_id_label.config(text="ID: " + cfg_mod.display_name_to_model_id(self.model_var.get()))
        self._current_key_type = "other"
        self._load_keys_to_ui()