# GoAI

中文简介：

`GoAI` 是一个基于 `KataGo` 引擎制作的围棋娱乐项目，重点不是严肃比赛，而是“好玩、爽快、容易上手”。除了普通对弈模式，它还加入了两种更偏游戏化的玩法：

- `Rogue` 模式：开局三选一卡牌，围绕节奏、陷阱、补子、限制 AI 等效果展开
- `Ultimate` 模式：更夸张的大招卡牌，强调短局、高爆发、强演出

这个项目主要面向 Windows 普通玩家，优先考虑“安装简单、启动稳定、没有 NVIDIA 也能玩”。当前版本支持：

- 有 NVIDIA 时优先尝试 `CUDA`
- 无 `CUDA` 时回退 `OpenCL`
- `OpenCL` 不可用时回退 `CPU`

English summary:

`GoAI` is a hobby Go/Weiqi game project built on top of the `KataGo` engine. It is designed more as a fun playable experience than as a serious tournament or research tool.

- `Rogue Mode`: pick 1 out of 3 cards at the start of the game
- `Ultimate Mode`: fast, flashy, overpowered card battles

The Windows build aims to be easy to install, stable to start, and able to fall back from CUDA to OpenCL or CPU on ordinary machines.

## Project Positioning

- This is a fan-made hobby project, not an official KataGo GUI.
- It is not affiliated with, endorsed by, or maintained by the KataGo project.
- The maintainer is a Go enthusiast, not a professional software engineer.
- For transparency: the code in this project was developed with heavy AI coding assistance, mainly using tools such as `Claude Code` and `Codex`, while the maintainer provided gameplay ideas, testing, packaging goals, and iteration direction.

## Main Features

- Normal AI play with multiple strength presets
- Rogue card mode
- Ultimate overpowered card mode
- Windows desktop launcher
- FastAPI backend + browser frontend
- CUDA / OpenCL / CPU fallback

## Intended Use

This project is intended for:

- casual play
- friends and family entertainment
- experimental roguelike-style Go gameplay ideas

This project is not intended for:

- official tournaments
- benchmark-style engine comparisons
- claiming any official relationship with KataGo

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

### Option 1: Use a packaged Windows release

If you only want to play, the easiest way is to use the packaged Windows installer from the project Releases page.

### Option 2: Run from source

1. Install Python 3.11.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Prepare the `katago/` directory.

This source repository intentionally does not include large third-party engine binaries, neural network weights, or NVIDIA runtime DLLs by default for repository cleanliness and licensing caution. See `katago/README.md` for expected files.

4. Run the backend:

```bash
python server.py
```

5. Or run the launcher:

```bash
python launcher.py
```

## Commercial Use And License

The original code in this repository is released under the MIT License.

That means, in plain language:

- commercial use is allowed
- modification is allowed
- redistribution is allowed
- private use is allowed

The main condition is:

- you must keep the original copyright notice and license text with copies or substantial portions of the project source

So if you reuse this project or parts of its code, please retain the source attribution through the included license notice.

Important:

- this applies to this repository's own original code
- third-party components remain under their own licenses
- bundled or downloaded engine binaries, model files, NVIDIA files, and other third-party materials are not relicensed by this repository

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
- packaged installers should be attached to GitHub Releases rather than committed into the source repository

## Friendly Note

This project was built with enthusiasm first and polish second. The goal is simple: make a playful, approachable Go game that more people can install and enjoy.
