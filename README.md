<p align="center">
  <img src="goai.png" width="92" alt="GoAI icon">
</p>

<h1 align="center">GoAI · Rogue Go Arena</h1>

<p align="center">
  <strong>Go × KataGo × Roguelike Cards × WebView2 Desktop</strong><br>
  A Windows-first AI Go game that turns every 19×19 match into a draft, counterplay, burst, and comeback run.
</p>

<p align="center">
  <a href="https://github.com/gongyu0918-debug/goai-rogue-arena/releases/latest"><strong>Download for Windows</strong></a>
  ·
  <a href="#english">English</a>
  ·
  <a href="#为什么值得玩">中文</a>
  ·
  <a href="#japanese--日本語">日本語</a>
  ·
  <a href="#korean--한국어">한국어</a>
  ·
  <a href="#quick-start">Quick Start</a>
  ·
  <a href="#game-modes">Modes</a>
  ·
  <a href="#开发命令">Development</a>
</p>

<p align="center">
  <img alt="Desktop branch" src="https://img.shields.io/badge/Branch-main-111111?style=for-the-badge">
  <img alt="WebView2" src="https://img.shields.io/badge/WebView2-desktop-0F6CBD?style=for-the-badge&logo=microsoftedge&logoColor=white">
  <img alt="Python 3.11" src="https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white">
  <img alt="Windows first" src="https://img.shields.io/badge/Windows-first-0078D6?style=for-the-badge&logo=windows&logoColor=white">
  <img alt="KataGo powered" src="https://img.shields.io/badge/KataGo-powered-D4AF37?style=for-the-badge">
  <img alt="MIT license" src="https://img.shields.io/badge/License-MIT-111111?style=for-the-badge">
</p>

<p align="center">
  <img src="docs/assets/goai-hero-current.jpg" alt="GoAI current dark wood board interface">
</p>

> `main` 是当前主力 WebView2 桌面版。原 HTML 浏览器版作为 [`html-main`](https://github.com/gongyu0918-debug/goai-rogue-arena/tree/html-main) 维护分支保留，通用玩法、卡牌、服务端和 HTML UI 更新可从那里继承。

## English

GoAI is a desktop Go arena built for people who want the reading depth of KataGo and the volatility of a roguelike run in the same match. You still play real Go on a 19×19 board, but Rogue cards can force AI moves, seal zones, spawn stones, shift komi, trigger hidden bursts, or turn a losing position into a playable comeback.

The Windows build wraps the same HTML/WebSocket game core in a WebView2 desktop shell. The UI behaves like a local app, the server stays easy to debug, and KataGo runs as a sidecar engine with CUDA, OpenCL, and CPU fallback.

## Screenshots

| Current Board | Rogue Guide |
| --- | --- |
| <img src="docs/assets/goai-hero-current.jpg" alt="GoAI current board with winrate and wood UI"> | <img src="docs/assets/goai-rogue-guide.jpg" alt="GoAI Rogue wiki guide panel"> |

| Rogue Card Draft |
| --- |
| <img src="docs/assets/goai-card-draft.jpg" alt="GoAI Rogue card selection screen"> |

## Why Players Notice It

| Hook | What it means |
| --- | --- |
| Real Go engine | KataGo remains the reading core, so the game still feels like Go instead of a skin over random moves. |
| Roguelike draft | 34 Rogue cards can reshape a match before the first stone lands. |
| Ultimate burst | 25 ultimate cards create short, dramatic games with high-impact turns. |
| AI counterplay | The AI can also receive Rogue rules, turning a normal match into a response game. |
| Wood-board focus | Clean top-down board, restrained dark wood UI, stone bowls, and readable tool icons. |
| Four languages | Chinese, English, Japanese, and Korean are available through external locale packs. |

## Game Modes

### Classic

Standard AI Go. Use it for normal practice, rank testing, and reading-focused games.

### Rogue

Draft one card from three choices at the start. A single pick can change the rhythm of the whole game: forced AI moves, bonus stones, forbidden points, komi pressure, timed combo turns, or hidden-zone explosions.

### Ultimate

Both sides carry a high-impact ultimate card. Chain turns, proliferation, board wipes, time reversal, and five-in-a-row bursts make even short games swing hard.

### Study

Watch AI-vs-AI games to study opening shape, pace, tradeoffs, and engine preferences.

### Local Two Player

Play on one PC with a shared board. Rogue rules can also turn it into a party-style Go variant.

## Quick Start

Download the latest Windows installer from [Latest Release](https://github.com/gongyu0918-debug/goai-rogue-arena/releases/latest), install GoAI, and launch it from the desktop entry.

The packaged build probes engine paths in this order:

```text
CUDA -> OpenCL -> CPU
```

For source development, use Python 3.11:

```bash
pip install -r requirements.txt
python setup.py
python launcher.py
```

## 为什么值得玩

GoAI 把围棋从“引擎分析界面”推进到“可反复开局的策略游戏”。你依然在 19 路棋盘上下棋，但每一局都可能被一张卡牌改写：AI 被迫落子、局部区域封锁、隐藏点位爆发、低胜率反杀、限时连击、AI 自带 Rogue 规则。

桌面版把同一套 HTML/WebSocket 游戏内核装进 WebView2 窗口：启动像本地应用，调试仍像 Web 项目，KataGo 继续作为独立 sidecar 引擎运行。

## 功能亮点

| 能力 | 说明 |
| --- | --- |
| WebView2 桌面壳 | `GoAI.exe` 默认以 WebView2 打开本地游戏窗口 |
| Rogue 构筑 | 开局抽卡，34 张 Rogue 卡改变整局规则 |
| Ultimate 爆发 | 25 张大招卡，短局也能打出高冲击局势 |
| AI Rogue | AI 也能获得卡牌，普通对弈变成反制博弈 |
| 正常围棋 | 标准 AI 对局、AI 自战学习、本地双人对局 |
| 暗色木纹棋桌 | 正俯视棋盘、木质 UI、棋盒背景、沉浸式桌面体验 |
| 自适应布局 | 窗口化、1080p、2K、4K 视图都能保持棋盘和按钮可用 |
| 引擎回退 | 优先 CUDA，随后 OpenCL，再到 CPU |
| 四语界面 | 中文 / English / 日本語 / 한국어 可切换 |
| 浏览器后备 | WebView2 不可用时可回退 Edge app-window 或系统浏览器 |

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

## 桌面运行方式

```text
GoAI.exe
  starts/reuses GoAI_Server.exe
  opens WebView2 through pywebview
  falls back to Edge app-window or browser

GoAI_Server.exe
  serves static/index.html and assets
  owns WebSocket game state
  starts/stops KataGo on demand

katago/*.exe
  isolated GTP engines
  can restart without taking down the desktop shell
```

这不是把游戏逻辑重写成另一套端技术，而是把已经可测的 HTML UI 和 FastAPI 后端封装成主力桌面体验。

## 快速开始

### 下载 Windows 版本

打开 [Latest Release](https://github.com/gongyu0918-debug/goai-rogue-arena/releases/latest)，下载 `GoAI_Setup_*.exe`，安装后启动 GoAI。

安装包会自动尝试可用引擎路径：

```text
CUDA -> OpenCL -> CPU
```

### 从源码运行

建议环境：

- Windows 10 / 11
- Python 3.11
- Microsoft Edge WebView2 Runtime
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

指定桌面壳：

```bash
python launcher.py --shell webview
python launcher.py --shell edge
python launcher.py --shell browser
```

启动本地服务调试：

```bash
python server.py --host 127.0.0.1 --port 8000
```

然后打开：

```text
http://127.0.0.1:8000
```

## 项目结构

```text
app/
  config/          游戏和引擎配置
  data/            Rogue / Ultimate 卡牌数据
  domain/          棋局状态与坐标领域模型
  runtime/         WebSocket 行为和引擎运行逻辑
static/
  index.html       WebView2 加载的主游戏界面
  assets/          棋盘、木纹、棋子、工具栏图标
docs/assets/       README 展示图
katago/            KataGo 配置和本地引擎文件位置
server.py          FastAPI 后端
launcher.py        WebView2 桌面启动入口
card_smoke_test.py 卡牌与关键规则烟测
runtime_smoke_test.py 运行时烟测
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

## Japanese / 日本語

GoAI は、KataGo の読みをそのまま土台にしながら、囲碁を毎局ドラフトと逆転劇が起きるデスクトップゲームへ押し広げます。19路盤の読み合いはそのままに、Rogue カードと Ultimate カードが、禁入エリア、強制着手、追加手、隠し爆発、低勝率からの反撃を盤上へ持ち込みます。

Windows 版は WebView2 デスクトップアプリとして起動します。ローカルの FastAPI/WebSocket サーバーが対局状態を持ち、KataGo は sidecar エンジンとして CUDA、OpenCL、CPU の順に自動フォールバックします。

### 見どころ

| Feature | 内容 |
| --- | --- |
| KataGo powered | 本格的な囲碁エンジンをローカルで起動 |
| Rogue Draft | 34枚の Rogue カードで対局ルールを改変 |
| Ultimate Burst | 25枚の大技カードで短局でも大きな山場を作る |
| AI Rogue | AI 側もカードを持ち、通常対局が読み合いと対策のゲームになる |
| Dark Wood Board | 古典木目の棋盤、棋盒風 UI、視認性重視のデスクトップ画面 |
| Four Languages | 中文 / English / 日本語 / 한국어 をアプリ内で切替 |

### Download

[Latest Release](https://github.com/gongyu0918-debug/goai-rogue-arena/releases/latest) から `GoAI_Setup_*.exe` をダウンロードしてインストールします。

```text
CUDA -> OpenCL -> CPU
```

起動時に利用可能なエンジン経路を自動検出します。NVIDIA GPU があれば CUDA を優先し、環境に合わせて OpenCL または CPU へ切り替わります。

### Game Modes

- Classic: 通常の AI 対局、練習、棋力確認に向いたモード。
- Rogue: 開局でカードを選び、AI の手、禁入点、追加石、コミ、時間制限などを変えるモード。
- Ultimate: 双方が大技カードを持ち、20手前後でも一気に盤面が動くモード。
- Study: AI 同士の対局を観察し、布石や形勢判断を追うモード。
- Local Two Player: ローカル共有用の二人対局。Rogue ルールを加えるとパーティー対局にも使えます。

## Korean / 한국어

GoAI는 KataGo의 수읽기를 기반으로, 전통 바둑을 매 판 드래프트와 역전이 살아 있는 Windows 데스크톱 게임으로 확장합니다. 19줄 바둑판의 기본 감각은 유지하면서 Rogue 카드와 Ultimate 카드가 금지 구역, 강제 착수, 추가 수, 숨은 폭발, 낮은 승률에서의 반격을 만들어 냅니다.

Windows 버전은 WebView2 데스크톱 앱으로 실행됩니다. 로컬 FastAPI/WebSocket 서버가 대국 상태를 관리하고, KataGo는 sidecar 엔진으로 동작하며 CUDA, OpenCL, CPU 순서로 자동 전환됩니다.

### 핵심 매력

| Feature | 설명 |
| --- | --- |
| KataGo powered | 강력한 바둑 엔진을 로컬에서 실행 |
| Rogue Draft | 34장의 Rogue 카드가 한 판의 규칙을 바꿈 |
| Ultimate Burst | 25장의 궁극기 카드로 짧은 대국에도 큰 변곡점을 만듦 |
| AI Rogue | AI도 카드를 얻어 일반 대국이 대응전으로 바뀜 |
| Dark Wood Board | 고전 목재 바둑판, 바둑통 느낌의 UI, 집중하기 좋은 화면 |
| Four Languages | 中文 / English / 日本語 / 한국어 앱 내 전환 지원 |

### Download

[Latest Release](https://github.com/gongyu0918-debug/goai-rogue-arena/releases/latest) 에서 `GoAI_Setup_*.exe` 를 내려받아 설치합니다.

```text
CUDA -> OpenCL -> CPU
```

실행 시 사용 가능한 엔진 경로를 자동으로 감지합니다. NVIDIA GPU가 있으면 CUDA를 우선 사용하고, 환경에 따라 OpenCL 또는 CPU로 전환됩니다.

### Game Modes

- Classic: 일반 AI 대국, 연습, 기력 확인에 적합한 모드.
- Rogue: 시작 시 카드를 선택해 AI 착수, 금지점, 추가 돌, 덤, 시간 압박 등을 바꾸는 모드.
- Ultimate: 양쪽이 궁극기 카드를 들고 20수 전후에도 판세가 크게 흔들리는 모드.
- Study: AI 대 AI 대국을 보며 포석, 흐름, 형세 판단을 관찰하는 모드.
- Local Two Player: 한 PC에서 즐기는 2인 대국. Rogue 규칙을 넣으면 파티형 바둑으로도 어울립니다.

## 开发命令

运行卡牌烟测：

```bash
python card_smoke_test.py
```

运行运行时烟测：

```bash
python runtime_smoke_test.py --base-url http://127.0.0.1:8000
```

构建 WebView2 启动器：

```powershell
python -m PyInstaller --clean --noconfirm GoAI.spec
```

构建服务端：

```powershell
python -m PyInstaller --clean --noconfirm GoAI_Server.spec
```

构建 Windows 安装包：

```powershell
.\build_windows_release.ps1
```

## KataGo 文件

仓库保留源码、配置和 UI 资源。体积较大的引擎文件、模型权重和运行时文件通过安装脚本或 Release 包获取。

KataGo 目录约定见 [katago/README.md](katago/README.md)。

## 分支策略

```text
html-main
  HTML 浏览器版维护分支
  承载共享玩法、卡牌、服务端和静态 UI 更新

main
  WebView2 桌面主力版
  在 html-main 之上增加桌面壳、打包和安装体验
```

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
- FastAPI, Uvicorn, websockets, pywebview and related Python packages

第三方授权说明见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

## 开发透明度

项目开发过程中使用了 AI 编码辅助工具。维护者负责玩法方向、体验判断、打包目标、测试反馈和发布取舍。
