# WebView 0.1.36 维护核查

## 范围与基线

本轮以常用 WebView 桌面安装版为主线，基线为 GitHub `main` / `v0.1.35` 的 `fa04255bd60a86479ecfe794a9c665e80d7a311b`。修复在独立 worktree `fix/dropdowns-ko-20260907` 中完成。卡牌机制与数值本轮不改，风险另见 [卡牌风险记录](card-risks-20260907.md)。

## 已修复

- 下拉框用完整主键点击提交，补齐键盘导航、禁用项过滤和焦点状态；关闭弹窗时清理菜单。GPU 检测和设置接口的晚响应不再覆盖用户刚做出的选择，设置保存依次执行。
- 展开的长菜单支持鼠标滚轮滚动，到达边界后不会带动底层页面；短菜单滚轮切换高亮项，点击或 Enter 确认。
- 同步 KataGo 时保留可验证的落子历史。卡牌改盘后，若可还原最近一次劫提，则从还原的局面重放该手，以保留劫禁。AI 劫禁重选使用合法候选分析；无法选出时虚手，不再随机挑空点。同步失败和 undo 失败会终止该次操作；虚手解除劫禁。
- 落子、提子和卡牌视觉反馈使用有数量上限的粒子及独立效果层，修正坐标和连线旋转。新局、隐藏页面和效果到期会清理；系统“减少动态效果”设置保留静态提示。
- 推荐落点统一使用不透明绿色及轮廓，实战和复盘共用绘制；窗口尺寸、像素比例和悬停叠层不再改变绿色。

## 源码验证

以下为实际执行的检查，终端日志位于本次 worktree 的 `output/`。浏览器使用本机 Edge；Python 浏览器测试及打包使用项目 Python 3.13 环境，其余基础测试也在本机 Python 3.11 运行。

| 命令 / 检查 | 结果 |
| --- | --- |
| `tests/smoke/{ai,gameplay,cards,websocket,frontend}` 中 74 个基础脚本逐一执行 | 74/74；离线评估 fixture 补齐同步 mock 后重跑，XSS 用带 Playwright 的项目环境重跑。原始失败记录与重跑结果分别保留 |
| `python tests/smoke/ai/ko_regression_smoke_test.py` | 15/15 |
| `python tests/smoke/runtime/ko_engine_smoke_test.py --backend cuda` | 12/12；5/9/19 路、黑白提劫、普通与卡牌改盘局面 |
| 将同步函数单独换回 `fa04255`，重跑同一真实 KataGo 检查 | 预期失败：5 路黑方提劫的同步丢失劫禁；最终实现通过 |
| `python tests/smoke/runtime/source_runtime_smoke_test.py --port 0 --output output/runtime-final.json` | 引擎归属、普通、Rogue、Ultimate、观战、提子、打劫 7/7 |
| `npm run smoke:legacy-wood-select --prefix frontend -- --url=http://127.0.0.1:8876/` | 20 个下拉框及 9 组回归；原始版本可检出键盘、右键、异步覆盖、遗留菜单和滚轮问题 |
| `npm run smoke:legacy-visual-effects --prefix frontend -- --url=http://127.0.0.1:8876/` | 实际落子/提子、穿透点击、窄窗、DPR 2、粒子上限与清理通过 |
| `node frontend/scripts/legacy-hint-overlay-smoke.mjs` | 900×600、1366×768、1920×1080 × DPR 1/2 通过；实战、复盘、悬停和预览均为 RGBA(46,216,120,255)，邻格溢出和已有棋子改色均为 0 |
| 仅将 renderer 换回原文件，重跑提示点检查 | 预期失败：小窗口邻格溢出 927 像素、已有棋子改色 14 像素；最终实现通过 |
| `npm run typecheck --prefix frontend`；`npm run build --prefix frontend` | 通过；Vite 的既有纹理运行时 URL 提示不影响构建 |
| React preview、rank/settings/setup、localization、inline-actions、responsive、review-sgf smoke | 通过；响应式覆盖 7 个窗口尺寸和 3 种棋盘大小 |
| `python tests/smoke/cards/card_editor_effect_smoke.py` | 37 张普通卡、25 张终极卡及 33 类基础效果配置/执行检查通过 |
| `python tests/smoke/installers/installer_smoke_test.py`；app-shell、launcher-port-conflict、server-shutdown smoke | 通过 |
| `python tests/smoke/runtime/webview_host_close_smoke_test.py` | 真实 WebView2 JS→桌面关闭通过；旧 fixture 的公开 Window 属性会被 pywebview 递归扫描，改为与生产一致的私有属性后通过，生产接口未改 |

真实 KataGo 劫禁检查使用 `kata-raw-nn` 的非法点策略值，并验证劫材应答后禁点解除及 AI 落点合法。GTP `play` 本身允许部分容错着手，不能将其是否拒绝落子作为这一检查的判据。

## 分支归档

GitHub 维护目标为 `webview`（默认桌面版）和 `html-main`（浏览器版）。本地原 HTML 分支为 `32155db659057028c18657310b3003630379b140`；此次恢复该分支不代表已移植全部桌面修复。Godot 及其他历史开发线只保留本地记录，不再维护。

删除远端旧分支前已在本地创建并验证完整历史 bundle：

| 文件 | SHA-256 |
| --- | --- |
| `branch-archive-20260907/webview-before-release.bundle` | `9B995F2FE7A8A2055C482AAC2FB017FCA49D81BE4DF0CBBD572A85E5B76FF30A` |
| `branch-archive-20260907/godot-and-html-local.bundle` | `D47449B1B918FF5F64977462F532323A6CB30E7DE73ECD94D12BADF418084EEB` |

归档位于工作区父目录，`git bundle verify` 均通过。Godot 本地未合入提交 `a393131b7650264a55cc50504b3b1957e065b9c0` 已包含在内，原 clone 保留。旧常用安装目录另作完整文件备份，不使用硬链接，便于回退。

## 剩余风险与后续范围

- 本机浏览器及真实 KataGo 检查不能代替所有显卡和旧电脑验证；Edge/WebView2 109 尚无实机结果。
- 共享引擎的后台分析与整回合 undo / analyze / play 尚未统一成完整事务；本轮没有重构整套引擎调度。
- 劫禁兜底重选与其他卡牌禁区的组合过滤仍需专项验证。卡牌改点、概率虚手和削弱搜索本身也会有意改变 AI 行为，相关体验与叠加风险见卡牌记录。
- 卡牌趣味性没有人工试玩统计。本轮只记录风险，未将胜率变化当作趣味性改善证据。

安装包、安装目录验证、GitHub Release 和最终远端分支状态以发布后的交付回执为准；本文件记录源码维护范围和验证依据。
