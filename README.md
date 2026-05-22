一键导入股票
<img width="1200" height="849" alt="image" src="https://github.com/user-attachments/assets/a4311ffd-44e5-49d8-97ab-23b2eb296eb6" />



调整提示词 让ai分析你需要的股票还有信息
<img width="1190" height="847" alt="image" src="https://github.com/user-attachments/assets/2f029d9a-4dc8-4658-b15d-cf5fdcaf5856" />


多个ai任你选择，需要自己去注册api
<img width="1206" height="843" alt="image" src="https://github.com/user-attachments/assets/855160a9-9af8-4650-9b13-286dbe516212" />


也可以点击刷新再一键分析
<img width="1175" height="866" alt="image" src="https://github.com/user-attachments/assets/b720fad2-56e9-47f3-a5a9-013488feb47e" />


带有 悬浮窗 一键分析就会显示这些信息了  点击上面的蓝字可以自动跳转到对应的股票
也会跟随你当前的股票信息做显示
<img width="2560" height="1389" alt="image" src="https://github.com/user-attachments/assets/5c348cbc-0008-4a44-b3d3-ffab9fa6fb0e" />








Stock AI Engine v10.0
AI Native 量化金融操作系统 —— 为多 AI Agent 长期协同而设计的股票分析平台。
项目定位
本项目是一款专注 A 股涨停复盘与实时盯盘的本地化桌面端工具，特别适合龙头股选手、短线/超短线交易者以及追求高效复盘的量化爱好者使用。
经过 v10.0 版本的激进式架构重构，项目从原有的单文件架构彻底升级为模块化、可扩展的 AI Native 操作系统，实现了 AI 能力与软件架构的深度融合。

核心价值与功能亮点

多模型 AI 智能分析系统
支持千帆、火山、OpenAI、Anthropic（Claude）等多家大模型自动路由与智能切换。能够对涨停个股进行深度复盘，包括：涨停原因拆解、板块情绪判断、资金逻辑分析、概念关联挖掘等。
动态概念知识图谱
构建「概念 → 子概念 → 个股」的层级化知识图谱，支持热度传播、时间衰减与动态更新，帮助用户快速理解市场主线与概念轮动。
可插拔 AI Skill 系统
所有 AI 能力均模块化为 Skill，支持链式调用、自动重试、结果缓存、熔断降级等企业级特性，便于长期迭代与能力扩展。
同花顺深度联动
通过内存桥接实现双向同步，可将 AI 分析结果直接推送到同花顺软件，并实时跟随行情变化。
多源数据整合
整合东方财富（涨停板、板块、龙虎榜）、腾讯实时行情等权威数据源，确保信息及时性与准确性。
智能标签关联与聚类
利用 AI 挖掘标签共现关系与隐含关联，提供超越传统板块分类的深度市场洞察。


系统架构（v10.0 重构成果）
采用分层、模块化设计，核心目录结构如下：
Bashstock_app/
├── skills/          # AI 技能系统（BaseSkill + Registry + Executor）
├── prompts/         # Prompt 模板集中管理与版本控制
├── runtime/         # AI 运行时（路由、限流、熔断、Token 管理）
├── state/           # 统一状态管理（App / Market / Skill）
├── events/          # 事件驱动架构（30+ 事件类型）
├── workflows/       # 工作流引擎（支持 DAG 编排）
├── cache/           # 概念图谱与缓存层
├── repositories/    # 数据访问层（SQLite + JSON）
├── integrations/    # 外部系统集成（东方财富、同花顺等）
├── ui/ & tabs/      # 界面层（8 大功能 Tab + 浮窗系统）
└── core/            # 基础工具库
重构成果：

133 个 Python 文件，总代码行数约 18,784 行
最大单文件控制在 593 行以内，代码结构清晰可维护
架构完成度约 80%，为后续持续演进奠定坚实基础


适用人群

短线、超短线及龙头战法实战选手
需要每日高效复盘的交易者
对 AI + 量化结合感兴趣的开发者与投资者
希望拥有本地化、私密性强股票分析工具的用户


快速开始
Bash# 1. 克隆仓库
git clone https://github.com/ZY12345yF/-.git

# 2. 安装依赖
pip install -r requirements.txt

# 3. 启动程序
python main.py
环境要求：Python 3.10+，推荐 Windows 系统（同花顺联动需 pywin32）

技术栈

语言：Python
界面：Tkinter + matplotlib
数据库：SQLite
AI 能力：千帆 / 火山 / OpenAI / Claude
数据源：东方财富、腾讯行情、同花顺


项目文档

ARCHITECTURE.md —— 整体架构设计
AI_SKILL_SYSTEM.md —— AI 技能系统详解
EVENT_SYSTEM.md —— 事件驱动机制
STATE_SYSTEM.md —— 状态管理设计
ROADMAP.md —— 未来路线图
TECH_DEBT.md —— 技术债记录
PROJECT_STATE.md —— 当前项目状态


愿景：打造一款真正属于中国散户与量化爱好者的、强大且可持续演进的 AI 量化金融操作系统。
欢迎 Star、Fork 与共同建设！
