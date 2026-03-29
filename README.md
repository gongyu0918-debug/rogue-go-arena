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

- Windows 10/11
- Python 3.11
- a modern browser
- optional GPU

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
