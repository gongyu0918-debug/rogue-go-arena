# GoAI

一个更像游戏、而不只是工具的围棋 AI 项目。

`GoAI` 基于 `KataGo` 引擎，但它的目标不是做一套严肃比赛向的围棋平台，而是做一款“朋友也愿意马上点开玩一局”的 Roguelike 风格围棋游戏。

它最核心的特色不是单纯的强棋力，而是：

- 开局就有 `Rogue` 三选一卡牌
- 还有更夸张、更爽快的 `Ultimate` 大招模式
- 支持普通 AI 对弈，也支持更偏娱乐化、偏演出化的玩法
- 支持中英双语界面切换
- 优先照顾普通 Windows 玩家，尽量做到装上就能跑

English:

`GoAI` is a Go / Weiqi game project built on top of `KataGo`, but it is not trying to be just another serious engine frontend. The goal is to make Go feel playful, fast, surprising, and easy to share with friends.

The headline features are:

- `Rogue Mode`: pick 1 out of 3 cards at the start of the game
- `Ultimate Mode`: absurd, flashy overpowered card battles
- normal AI play is still available
- bilingual Chinese / English UI toggle
- Windows builds aim for easy installation and stable startup

## Why It Feels Different

普通围棋 AI 项目更像分析工具，而 `GoAI` 更像“围棋 + Roguelike 卡牌规则”的轻游戏：

- 有的卡会限制 AI 走法
- 有的卡会奖励补子、爆发、连击
- 有的卡会触发隐藏区域、角部机关、愚形连锁
- 大招模式里则强调 20 手内爆发、翻盘、演出感

English:

Most Go engine apps feel like training or analysis tools. `GoAI` tries to feel more like a playful board game:

- some cards nerf or mislead the AI
- some cards spawn extra stones or create traps
- some cards reward patterns, shape tricks, or hidden triggers
- Ultimate mode turns the game into a short explosive showdown

## Main Modes

### 1. Normal Play

- Standard AI play with multiple strength presets
- Suitable when you just want to play a regular game

### 2. Rogue Mode

- At the start of the game, choose 1 of 3 cards
- Cards reshape the rules of that game
- The tone is “clever advantage, trick plays, tempo abuse, and weird board events”

Typical examples:

- make the AI pass sometimes
- block zones the AI cannot enter
- complete joseki targets for bonus stones
- trigger hidden effects from shape patterns

### 3. Ultimate Mode

- You and the AI each get an overpowered card
- The pace is intentionally faster and more explosive
- Designed for short, dramatic games rather than classical balance

Typical examples:

- extra turns
- mass stone generation
- board-wide wipe effects
- chain reactions from patterns or hidden areas

## Rogue 卡牌总表

| 卡牌 | 效果 |
| --- | --- |
| 天元 | 开局 2 手，AI 被天元与星位吸引 |
| 掷骰 | AI 每手有 14% 概率直接跳过 |
| 蚕食 | 每提 1 子，贴目向有利方向偏移 2 目 |
| 傀儡术 | 选定一点，强制 AI 在此落子（限 1 次） |
| 封印术 | 指定 3 个禁区，AI 全局无法落子 |
| 连击 | 一回合连落两手（限 1 次） |
| 弱化 | AI 搜索算力直降 60% |
| 贴目减半 | 贴目从 7.5 直降至 2.5 |
| 限时压制 | AI 每手最多思考 0.7 秒 |
| 低空飞行 | AI 前 6 手偏向二三路低位 |
| 次优之选 | AI 前 10 手只能选第 3~5 优的点 |
| 镜像 | AI 有 30% 概率模仿你的上一手 |
| 手滑了 | AI 有 38% 概率偏到目标旁边 |
| 黑洞 | 棋盘中心 13 路区域对 AI 完全禁入 |
| 乾坤挪移 | 强制 AI 虚手，你继续行棋（限 1 次） |
| 战争迷雾 | AI 每手前刷新一个 3×3 禁区遮罩 |
| 星位引力 | AI 前 5 手被星位磁场牵引 |
| 黄金角 | 随机封锁一角 4×4 区域，AI 禁入 |
| 三三开局 | AI 先冲三三，之后回避角部 5×5 |
| 影子 | AI 前 3 手紧跟上一手的位置 |
| 萌芽 | 每提 1 子，旁边自动长出 1 颗己棋 |
| 定式强迫症 | 开局亮出 7 个目标点，下中其中 3 个，剩下 4 个会自动补成你的棋子 |
| 让子任务 | 先虚手 1 次，之后每 4 手奖励 AI 虚手 |
| 神之一手 | 踩中隐藏菱形区，5×5 内爆出 5 颗己棋 |
| 三三陷阱 | AI 开在三三？旁边立刻长出 3 颗反击棋 |
| 守角辅助 | 任一角的 5×5 区域里有 2 颗己子时，就会在那个角再补 2 颗援军 |
| 三连星 | 前 3 手全落星位，额外生成 3 颗己棋 |
| 永不悔棋 | 禁用悔棋，但每手 14% 概率白送一子 |
| 快速思考 | 3 秒内落子可追加 2 秒连击窗口 |
| 大智若愚 | 摆出孤立愚形，5×5 内随机长出 1 颗己棋 |
| 五子连珠 | 这是五子棋，不是围棋。每当我方横、竖、斜正好连成 5 颗同色棋，就会在首尾各补 1 颗棋子 |
| 代练上号 | 主动技能：后 20 手由比对方段位更强的 AI 代打；若下完后胜率仍低于 40%，则额外再代打 5 手 |
| 提子犯规 | 若对手单次或累计提子超过 5 颗，有 50% 概率触发“提子未放在棋盒”；每多 1 子概率再加 10%。若触发，则被惩罚方罚 1.5 目，随后概率重新计数，必须再提够 5 子后重新开始 |
| 起死回生 | 当我方胜率跌到 30% 以下时，仅触发 1 次：在上一手周围 3×3 内随机消掉 1 颗敌子，并随机补 1 颗己棋（不会落在禁着点） |

## Ultimate 大招总表

| 卡牌 | 效果 |
| --- | --- |
| 连珠棋 | 每手 65% 概率触发追加行动 |
| 无限增殖 | 落子后 5×5 范围内爆出 5 颗同色棋 |
| 双刀流 | 每回合固定连下 2 手，但整回合只计 1 手数 |
| 狂野生长 | 4 颗己子向四周蔓延扩张 |
| 排异反应 | 落点 5×5 内敌子被推开或摧毁 |
| 绝对领地 | 落点周围 4 格形成禁入结界 |
| 影分身 | 先生成一颗镜像棋；下一回合会按原落点和镜像点强制连成一整条线，就算两端棋子被提掉也照样连线 |
| 瘟疫 | 3×3 内所有敌子转化为己方 |
| 陨石雨 | 随机轰掉 5 颗对方棋子 |
| 量子纠缠 | 全盘随机位置生成 5 颗同色棋 |
| 吞噬 | 5×5 范围内敌子全部清空 |
| 时空裂缝 | 85% 概率抹去对手最近 2 手 |
| 天崩地裂 | 十字方向清除所有敌子 |
| 磁力吸附 | 己方棋子飞速聚拢，碾碎路径上的敌子 |
| 亡灵召唤 | 召唤 3 颗己棋 + 策反 2 颗敌棋 |
| 万里长城 | 有 60% 概率发动：整行或整列筑起一面不可逾越的棋墙 |
| 定式爆发 | 命中定式后补满目标，并额外爆出 50 颗同色棋 |
| 神之一手 | 踩中 5×5 隐藏菱形，清空敌子并铺满 50 颗己棋 |
| 守角要塞 | 四个角分别独立结算：某个角的 5×5 区域里有 2 颗己子时，就会封满该角 8×8 边界并清掉里面的敌子 |
| 三连星爆发 | 前 3 手全落星位，引爆全盘星位势力 |
| 极速风暴 | 5 秒内不限次数连续落子，结束后 AI 再读盘，整段只计 1 手数 |
| 愚形连锁 | 检测到愚形就连锁生成，最多铺满 20 颗己棋 |
| 五子连珠爆发 | 这是五子棋，不是围棋。每当我方横、竖、斜正好连成 5 颗同色棋，就会随机清除对方 30 颗棋子，并在全盘随机补下 30 颗己棋；该效果可连锁触发 |
| 提子犯规 | 若对手提子数量超过 5 颗，则 100% 触发“提子未放在棋盒”，被惩罚方立刻罚 50 目；每次触发后重新计数，之后仍可重复触发 |
| 起死回生 | 当我方胜率跌到 30% 以下时：全盘随机清除对方 30 颗棋子，并随机补下 30 颗己棋 |

## Project Positioning

- This is a fan-made hobby project
- It is not an official KataGo GUI
- It is not affiliated with, endorsed by, or maintained by the KataGo project
- The maintainer is a Go enthusiast, not a professional software engineer
- For transparency: the project was developed with heavy AI coding assistance, mainly using tools such as `Claude Code` and `Codex`, while the maintainer provided gameplay ideas, balancing direction, packaging goals, and testing feedback

## Runtime Goals

The Windows build is tuned for ordinary users first:

- easy install
- stable startup
- clear fallback behavior
- machines without NVIDIA should still work

Current fallback path:

- use `CUDA` first when available
- fall back to `OpenCL`
- fall back again to `CPU`

## Runtime Environment

Recommended environment for source development:

- Windows 8.1 / 10 / 11
- Python 3.11
- a modern browser
- optional GPU

Runtime notes:

- Older CPUs around the Intel i7-6700K class are supported, but the CPU backend is intentionally tuned for stability rather than maximum strength
- NVIDIA GPUs with outdated drivers may skip CUDA and fall back to OpenCL or CPU automatically
- Windows 8.1 is the practical lower bound for the current Python 3.11 based build pipeline. Plain Windows 8 is not an officially guaranteed target

Python packages used by the source version include:

- `fastapi`
- `uvicorn[standard]`
- `websockets`

Build / packaging tools used by this project:

- `PyInstaller`
- `Inno Setup 6`

## Quick Start

### Option 1: Use the packaged Windows release

If you just want to play, use the installer from the GitHub Releases page.

### Option 2: Run from source

1. Install Python 3.11
2. Install dependencies

```bash
pip install -r requirements.txt
```

3. Prepare the `katago/` directory

This repository intentionally does not include large third-party engine binaries, neural network weights, or NVIDIA runtime DLLs by default. See `katago/README.md` for expected files.

4. Run the backend

```bash
python server.py
```

5. Or run the launcher

```bash
python launcher.py
```

## Non-Commercial By Default

The original code in this repository is available for:

- non-commercial use
- non-commercial modification
- non-commercial redistribution
- non-commercial sharing of source and packaged builds

Commercial use is not automatically granted.

If you want to use this project in a commercial product, paid service, paid deployment, or business setting, please contact the repository owner first.

Important:

- this applies to this repository's original code and original content
- third-party components remain under their own licenses
- engine binaries, model files, NVIDIA files, and other third-party materials are not relicensed by this repository

Please read:

- `LICENSE`
- `THIRD_PARTY_NOTICES.md`

## Third-Party Credits

Core third-party components used by this project include:

- `KataGo` engine by David J Wu (`lightvector`) and contributors
- official KataGo neural network weights from `katagotraining.org`
- Python libraries such as `FastAPI`, `Uvicorn`, and `websockets`

Links:

- KataGo engine: <https://github.com/lightvector/KataGo>
- KataGo networks: <https://katagotraining.org/networks/>
- KataGo neural net license: <https://katagotraining.org/network_license/>

## Repository Policy

To keep the GitHub repository smaller and easier to review:

- source code stays in Git
- logs, build outputs, local test files, models, and packaged binaries stay out of Git
- packaged installers should be attached to GitHub Releases instead of being committed into the source repository

## Friendly Note

这不是一个“完美无瑕的专业软件产品”，而是一个围棋爱好者把自己想玩的玩法做出来、再努力打磨到朋友也能直接安装游玩的项目。

If the app feels a little rough around the edges sometimes, that is honest rather than hidden. The goal is simple: make Go more playful, more surprising, and easier to share.
