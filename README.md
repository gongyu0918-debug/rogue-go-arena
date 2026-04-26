<p align="center">
  <img src="goai.png" width="92" alt="GoAI icon">
</p>

<h1 align="center">GoAI · Rogue Go Arena</h1>

<p align="center">
  <strong>围棋 × KataGo × Roguelike 卡牌</strong><br>
  一款把传统围棋变成构筑、反制、爆发和翻盘体验的桌面 AI 对弈游戏。
</p>

<p align="center">
  <a href="https://github.com/gongyu0918-debug/rogue-goai/releases/latest"><strong>Download for Windows</strong></a>
  ·
  <a href="#快速开始">Quick Start</a>
  ·
  <a href="#玩法模式">Modes</a>
  ·
  <a href="#开发命令">Development</a>
</p>

<p align="center">
  <img alt="Python 3.11" src="https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white">
  <img alt="Windows first" src="https://img.shields.io/badge/Windows-first-0078D6?style=for-the-badge&logo=windows&logoColor=white">
  <img alt="KataGo powered" src="https://img.shields.io/badge/KataGo-powered-D4AF37?style=for-the-badge">
  <img alt="MIT license" src="https://img.shields.io/badge/License-MIT-111111?style=for-the-badge">
</p>

<p align="center">
  <img src="docs/assets/goai-hero.png" alt="GoAI dark wood board interface">
</p>

## 为什么值得玩

GoAI 把围棋从“引擎分析界面”推进到“可反复开局的策略游戏”。你依然在 19 路棋盘上下棋，但每一局都可能被一张卡牌改写：AI 被迫落子、局部区域封锁、隐藏点位爆发、低胜率反杀、限时连击、AI 自带 Rogue 规则。

核心目标很明确：让围棋更容易被打开、更容易分享，也更适合短时间体验。

## 功能亮点

| 能力 | 说明 |
| --- | --- |
| Rogue 构筑 | 开局抽卡，34 张 Rogue 卡改变整局规则 |
| Ultimate 爆发 | 25 张大招卡，短局也能打出高冲击局势 |
| AI Rogue | AI 也能获得卡牌，普通对弈变成反制博弈 |
| 正常围棋 | 标准 AI 对局、AI 自战学习、本地双人对局 |
| 暗色木纹棋桌 | 正俯视棋盘、木质 UI、棋盒背景、沉浸式桌面体验 |
| 自适应布局 | 窗口化、1080p、2K、4K 视图都能保持棋盘和按钮可用 |
| 引擎回退 | 优先 CUDA，随后 OpenCL，再到 CPU |
| 双语界面 | 中文 / English 可切换 |
| Windows 安装包 | 面向桌面用户的一键安装与启动 |

## 玩法模式

### Classic

标准 AI 对局。适合正常练棋、测试 AI 强度、熟悉棋盘交互。

### Rogue

开局三选一卡牌，一张卡即可改变整局节奏。你可以干扰 AI、制造额外棋子、触发隐藏区域、改变贴目，或者把定式目标变成任务。

### Ultimate

双方各拿一张高爆发大招。连击、增殖、清盘、时间回退、五连爆发都会让棋局进入高压状态。

### Study

观看 AI 与 AI 对弈，用来观察布局、节奏、取舍和引擎风格。

### Local Two Player

本地双人对局，适合线下分享。也可以把 Rogue 卡牌当作派对规则加入对弈。

## 当前版本

这轮发布重点：

- 棋盘主界面改成暗色木纹正俯视桌面。
- 底部工具按钮换成实体棋具风格图标。
- 开始菜单、设置面板、下拉菜单统一成暗木纹视觉。
- 窗口化初始尺寸会给底部 UI 自动留出安全区域。
- Rogue / Ultimate 卡牌数据集中到 `app/data/cards.py`。
- 新增领域层 `app/domain/`，把棋局状态和坐标逻辑拆出。
- 烟测覆盖普通对局、Rogue、Ultimate、吃子、打劫、AI Rogue 和双人 Rogue。

## 快速开始

### 下载 Windows 版本

打开 [Latest Release](https://github.com/gongyu0918-debug/rogue-goai/releases/latest)，下载 `GoAI_Setup_*.exe`，安装后启动 GoAI。

安装包会自动尝试可用引擎路径：

```text
CUDA -> OpenCL -> CPU
```

### 从源码运行

建议环境：

- Windows 8.1 / 10 / 11
- Python 3.11
- 现代浏览器
- 可选 NVIDIA / OpenCL GPU

安装依赖：

```bash
pip install -r requirements.txt
```

准备 KataGo：

```bash
python setup.py
```

启动桌面入口：

```bash
python launcher.py
```

启动本地服务：

```bash
python server.py
```

## 项目结构

```text
app/
  config/          游戏和引擎配置
  data/            Rogue / Ultimate 卡牌数据
  domain/          棋局状态与坐标领域模型
  runtime/         WebSocket 行为和引擎运行逻辑
static/
  index.html       主游戏界面
  assets/          棋盘、木纹、棋子、工具栏图标
docs/assets/       README 展示图
katago/            KataGo 配置和本地引擎文件位置
server.py          FastAPI 后端
launcher.py        Windows 桌面启动入口
card_smoke_test.py 卡牌与关键规则烟测
```

## 卡牌系统

当前卡牌池：

- 34 张 Rogue 卡
- 25 张 Ultimate 卡
- Rogue 精选池、AI Rogue 池、双人 Rogue 池、闯关 Beta 池
- Ultimate 精选池和 AI Ultimate 池

完整定义见 [app/data/cards.py](app/data/cards.py)。

<details>
<summary>Rogue 卡牌例子</summary>

| 卡牌 | 效果方向 |
| --- | --- |
| 傀儡术 | 指定 AI 下一手落点 |
| 战争迷雾 | 刷新禁区并持续封锁点位 |
| 神之一手 | 命中隐藏区域后爆出己方棋子 |
| 三连星 | 星位任务触发补子和援军 |
| 快速思考 | 限时连击窗口 |
| 代练上号 | 后段由更强 AI 临时代打 |
| 起死回生 | 低胜率时触发逆转补救 |

</details>

<details>
<summary>Ultimate 大招例子</summary>

| 大招 | 效果方向 |
| --- | --- |
| 连珠棋 | 高概率追加行动 |
| 无限增殖 | 落点周围爆出同色棋 |
| 双刀流 | 每回合固定连续落两手 |
| 时空裂缝 | 抹去对手最近行动 |
| 天崩地裂 | 十字方向清除敌子 |
| 神之一手 | 隐藏命中后清空并铺棋 |
| 五子连珠爆发 | 五连触发大范围清除和补子 |

</details>

## 开发命令

运行卡牌烟测：

```bash
python card_smoke_test.py
```

运行运行时烟测：

```bash
python runtime_smoke_test.py
```

构建 Windows 安装包：

```powershell
.\build_windows_release.ps1
```

## KataGo 文件

仓库保留源码、配置和 UI 资源。体积较大的引擎文件、模型权重和运行时文件通过安装脚本或 Release 包获取。

KataGo 目录约定见 [katago/README.md](katago/README.md)。

## 设计原则

- 棋盘始终是视觉中心。
- UI 服务于下棋，保持棋盘视觉中心。
- 每张卡牌都要带来可感知的局势变化。
- 引擎路径要有回退，旧电脑也能进入游戏。
- 关键规则靠烟测保护，视觉体验靠真实截图验证。

## 第三方与授权

GoAI 使用 MIT License。详见 [LICENSE](LICENSE)。

核心第三方组件：

- KataGo by David J Wu (`lightvector`) and contributors
- KataGo neural network weights from `katagotraining.org`
- FastAPI, Uvicorn, websockets and related Python packages

第三方授权说明见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

## 开发透明度

项目开发过程中使用了 AI 编码辅助工具。维护者负责玩法方向、体验判断、打包目标、测试反馈和发布取舍。
