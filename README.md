# GoAI

一个更像游戏、而不只是工具的围棋 AI 项目。`GoAI` 基于 `KataGo`，但目标不是做成纯分析面板，而是把围棋做成更容易上手、分享和反复游玩的 Roguelike 风格产品。

`GoAI` is a Go / Weiqi project built on top of `KataGo`, but it is not trying to be just another serious engine frontend. The goal is to make Go feel playful, fast, surprising, and easy to share.

## 核心特色

- `对局`：常规 AI 对弈，支持多个强度档位
- `学习`：观看 AI 与 AI 对弈，适合复盘和找灵感
- `双人`：本地双人对局
- `Rogue 模式`：开局三选一卡牌，整局规则都会被改写
- `Ultimate 模式`：双方各拿一张夸张大招，短局高爆发
- `闯关β`：测试中的构筑闯关模式，卡牌可叠加并带有限次资源
- 中英双语界面
- Windows 优先，兼顾老电脑与驱动回退

## Why It Feels Different

普通围棋 AI 更像分析工具，`GoAI` 更像“围棋 + Roguelike 卡牌规则”的轻游戏：

- 有的卡会限制 AI 落点
- 有的卡会奖励补子、爆发、连锁
- 有的卡会奖励特殊形状、隐藏触发、陷阱反打
- 大招模式强调短局翻盘和视觉演出

Most Go engine apps feel like training or analysis tools. `GoAI` is designed to feel more like a playful board game:

- some cards nerf or mislead the AI
- some cards spawn extra stones or trigger traps
- some cards reward patterns, shape tricks, or hidden areas
- Ultimate mode turns the board into a short explosive showdown

## 主要模式

### 1. 对局

- 标准 AI 对弈
- 适合正常下棋和练习

### 2. 学习

- 观看双方都是 AI 的对弈
- 适合看布局、节奏和取舍

### 3. 双人

- 本地双人模式
- 适合娱乐局和线下分享

### 4. Rogue 模式

- 开局三选一卡牌
- 一张卡就能改变整局节奏
- 偏“巧手、套路、节奏差、局部事件”

### 5. Ultimate 模式

- 双方各拿一张超规格大招
- 节奏更快，局势更炸裂
- 适合短时间高演出对局

## Rogue 卡牌总表

| 卡牌 | 效果 |
| --- | --- |
| 天元 | 开局 3 手，AI 会优先靠近天元与星位落子 |
| 掷骰 | AI 每手有 8% 概率直接虚手 |
| 蚕食 | 每提 1 子，贴目向有利方偏移 4 目 |
| 傀儡术 | 选定一点，强制 AI 在此落子（限 1 次） |
| 封印术 | 指定 4 个禁着点，整局 AI 都不能下在这些点 |
| 连击 | 本回合可连续落两手（限 1 次） |
| 弱化 | AI 大约下降 8 段，搜索算力只剩约 5%，前 12 手也更容易误选备选点 |
| 贴目减半 | 贴目会朝你有利的方向调整 7 目 |
| 限时压制 | AI 大约下降 5 段，且每手最多思考 0.10 秒，前 10 手也更容易仓促误判 |
| 低空飞行 | AI 前 6 手偏向二三路低位 |
| 次优之选 | AI 前 8 手更容易从后几名的候选点里随机挑一手 |
| 镜像 | AI 有 10% 概率按棋盘对称位置镜像模仿你的上一手 |
| 手滑了 | AI 有 10% 概率手滑到相邻的点位 |
| 黑洞 | 棋盘中心 13 子区域对 AI 前 6 手禁入 |
| 乾坤挪移 | 强制 AI 虚手，你继续行棋（限 1 次） |
| 战争迷雾 | AI 前 11 手每手前会刷新一个 3×3 禁区遮罩；之后每回合随机封锁 2 个 AI 禁着点 |
| 星位引力 | AI 前 5 手被星位磁场牵引 |
| 黄金角 | 随机封锁一角 4×4 区域，AI 前 10 手禁入 |
| 三三开局 | 强制 AI 在开局前 2 手去抢四个三三点中的位置，也就是开局硬走三三；之后 2 手暂时避开角上 4×4 区域 |
| 影子 | AI 前 2 手有较高概率紧跟自己的上一手 |
| 萌芽 | 每次提子后，都会在附近自动长出 1 颗己棋 |
| 定式强迫症 | 开局亮出 7 个目标点，只要下中 6 个，剩下的 1 个会自动补成你的棋子 |
| 让子任务 | 先虚手 1 次，之后每满 8 手奖励 AI 虚手一次，最多触发 3 次 |
| 神之一手 | 踩中隐藏菱形区，周围 3×3 内随机爆出 2 颗己棋，只会落在空点 |
| 三三陷阱 | 只有对手第 1 手正好下在四个三三点之一时才会触发，并在那手棋周围反生 8 颗我方棋 |
| 守角辅助 | 每个角各算一次：任一角的 5×5 区域里有 4 颗己子时，就会在那个角补 1 颗援军 |
| 三连星 | 若你前 2 手都落在星位，会自动补出第 3 颗星位棋，并再长出 1 颗援军 |
| 永不悔棋 | 禁用悔棋，但每手 8% 概率白送一子 |
| 快速思考 | 3 秒内落子可追加 1 秒连击窗口；选中后禁用推荐点位与悔棋 |
| 大智若愚 | 摆出愚形，附近 5×5 内随机长出 2 颗己棋 |
| 五子连珠 | 这是五子棋，不是围棋。每当我方横、竖、斜正好连成 5 颗同色棋，就会优先在首尾补子；若首尾被堵住，则改在两端附近补子，并在连线附近再补 4 颗援军 |
| 代练上号 | 主动技能：后 30 手由更强的 AI 代打；若下完后胜率仍低于 50%，则额外再代打 10 手 |
| 提子犯规 | 若对手单次或累计提子达到 4 颗，就会触发“提子未放在棋盒”，被惩罚方罚 4 目，随后重新计数 |
| 起死回生 | 当我方胜率跌到 26% 以下时，仅触发 1 次：在上一手周围 3×3 内随机消掉 1 颗敌子，并随机补 1 颗己棋（不会落在禁着点） |

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

## 项目定位

- 这是一个爱好者驱动的围棋游戏项目
- 它不是官方 KataGo GUI
- 它不隶属于 KataGo 项目
- 项目维护过程中大量使用了 AI 编码辅助工具

For transparency: this project was developed with heavy AI coding assistance, mainly using tools such as `Claude Code` and `Codex`, while the maintainer provided gameplay direction, balancing goals, packaging targets, and testing feedback.

## 运行目标

Windows 版本优先保证：

- 好安装
- 好启动
- 出问题时有清晰回退
- 没有 NVIDIA 也能运行

当前回退路径：

- 优先尝试 `CUDA`
- 不行则尝试 `OpenCL`
- 再不行回退 `CPU`

## Runtime Environment

Recommended environment for source development:

- Windows 8.1 / 10 / 11
- Python 3.11
- a modern browser
- optional GPU

Runtime notes:

- Older CPUs around the Intel i7-6700K class are supported, but the CPU backend is tuned for stability first
- NVIDIA GPUs with outdated drivers may skip CUDA and fall back to OpenCL or CPU automatically
- Windows 8.1 is the practical lower bound for the current Python 3.11 build pipeline

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

## License

This repository is available under the MIT License.

Please also read:

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

这不是一个“完美无瑕的专业软件产品”，而是一个围棋爱好者把自己想玩的玩法做出来、再尽量打磨到别人也能直接下载安装游玩的项目。

If the app feels a little rough around the edges sometimes, that is honest rather than hidden. The goal is simple: make Go more playful, more surprising, and easier to share.
