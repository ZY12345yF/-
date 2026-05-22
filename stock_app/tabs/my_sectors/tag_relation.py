"""
标签关联度相关方法（Mixin 聚合）—— 从 my_sectors_tab.py 拆出
v9.9.8：按职责拆分为 4 个 Mixin 子模块，本文件为纯聚合类
"""
import json
import threading
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

# matplotlib（用于关联度图表）
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
try:
    plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Arial Unicode MS']
    plt.rcParams['axes.unicode_minus'] = False
except Exception:
    pass

from ...widgets import (
    make_card, styled_btn, styled_entry, apply_highlight,
    load_col_widths, save_col_widths,
)
from ...core import (
    config as cfg_mod,
    history as hist_mod,
    api_client, my_sectors,
    tag_relation as tr,
)
from ...bus import bus, Events, state

# 三种视图常量（与主文件保持同步）
VIEW_FAV  = "favorites"
VIEW_USER = "user_sector"
VIEW_TAG  = "tag_relation"

# 子模块（v9.9.8：按职责拆分）
from .tag_relation_view import TagRelationViewMixin
from .tag_relation_scan import TagRelationScanMixin
from .tag_relation_ai import TagRelationAIMixin
from .tag_relation_manager import TagRelationManagerMixin


class TagRelationMixin(
    TagRelationViewMixin,
    TagRelationScanMixin,
    TagRelationAIMixin,
    TagRelationManagerMixin,
):
    """所有标签关联度相关方法的聚合类（v9.9.8：多重继承，仅做聚合）"""
