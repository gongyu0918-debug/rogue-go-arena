# HTML 兼容修复记录

基线为 `32155db659057028c18657310b3003630379b140`，本轮在独立 worktree 回移 WebView 的通用维护修复。HTML 保留 34 张普通卡、原玩法和浏览器入口；没有整合桌面版的卡牌池、机制或数值。GitHub 仅保留 `html-main` 与默认桌面分支 `webview`，Godot 历史只在本地归档。

## 修复

- 下拉框使用完整主键点击提交，支持键盘方向键、Home/End、Enter/Space 确认、Escape 取消；右键不修改值。长菜单用滚轮滚动，短菜单用滚轮切换高亮，确认后提交。关闭弹窗、切换模式会清理菜单；GPU 晚响应不覆盖已选段位。
- 统一绿色提示的实战、复盘及悬停绘制，使用不透明颜色与轮廓，控制在棋盘格内。900×600、1366×768、1920×1080 及 DPR 1/2 下校验颜色与相邻棋子。
- 落子、提子和卡牌视觉效果提取为独立组件；修正相对棋盘坐标、连线旋转，限制粒子数量并清理过期效果。支持系统减少动态。雾气和背景补齐 109 内核需要的 `-webkit-mask-image`。
- KataGo 同步保留可验证棋谱；卡牌改盘后重建最近一次劫提，保留劫禁。使用无空格的可写同步路径，失败时停止操作。打劫重选使用合法候选分析，不再随机选择空点。
- PASS/RESIGN 的引擎历史与本地棋谱保持一致：虚手解除劫禁，替换引擎已提交的 PASS 先撤回，RESIGN 不撤销对手的上一手，失败响应不记入棋谱。
- 同步不覆盖已选计分规则；卡牌改贴目也不改变规则。终极模式遇到引擎返回已占用点会报错停止，不再只在本地随机换点。
- AI 风格下拉框原本因调用不存在的全局分析函数而失效。现在普通 AI 与观战/代练均通过已有评分选择并提交合法着手；引擎拒绝时停止写盘。观战 AI 认输会结束对局，不再当作虚手记入棋谱。

## 可复现验证

```powershell
python -m compileall -q server.py app
python card_smoke_test.py
python ko_regression_smoke_test.py
python ai_style_regression_smoke_test.py
python ko_engine_smoke_test.py --backend cuda
python runtime_smoke_test.py --base-url http://127.0.0.1:<测试端口>

npm ci --prefix frontend
$env:SMOKE_BROWSER_EXECUTABLE = '<实际109目录>\msedge.exe'
$env:SMOKE_BROWSER_MAJOR = '109'
npm run smoke:html-dropdowns --prefix frontend -- --url=http://127.0.0.1:8891/
npm run smoke:html-hints --prefix frontend -- --url=http://127.0.0.1:8891/
npm run smoke:html-effects --prefix frontend -- --url=http://127.0.0.1:8891/
```

实际 109.0.1518.140 与 152.0.4191.66 的下拉测试均覆盖 19 个控件、7 组交互，提示测试覆盖 6 组尺寸/像素比例，特效测试覆盖真实 7 手提子、窄窗、粒子上限与清理。真实 KataGo CUDA 的 12 个场景覆盖 5/9/19 路、黑白提劫和普通/卡牌改盘。旧运行时的普通、Rogue、Ultimate、提子和打劫 5 项通过。

轻量消融只恢复旧同步函数，同一真实引擎检查失败并指出丢失劫禁；修复函数通过。原 HTML 下拉 smoke 7 组失败、小窗口提示检测到 435 个越格像素，修复后均通过。独立 AST review 确认迁移没有改变旧卡牌、LocalBoard、落子及消息处理规则；卡牌配置与数据零差异。

风格/观战回归另有 11 项，保留原风格评分并覆盖双方持不同风格、合法候选、错误阻断及认输终局。真实引擎另比对 4 个中国/日本规则场景的完整 `kata-get-rules` JSON，包括卡牌改变贴目，均保持原规则。HTML 烟测依赖在新目录通过 `npm ci`，未依赖桌面工作树的缓存才通过。

另外使用 WebView 分支的原生宿主测试直接加载本分支页面，在实际 WebView2 109 上完成双窗口、DPR 1.5、下拉滚轮、绿色像素、遮罩及 JS 关闭接口验证。没有安装或降级系统浏览器。

## 下一轮记录

卡牌趣味性与规则统一留到下一轮。HTML 与 WebView 在天元连下、低线、额外棋子、增殖、五子连珠、提子犯规等规则和卡牌数量上存在差异，不能直接整体合并。

共享引擎的完整回合事务化、劫禁重选与多卡牌禁区叠加，以及其他显卡/旧 Windows 系统仍需验证。真实 109 内核运行于当前 Windows，不等于完成 Windows 7/8 安装及驱动验证。旧 HTML 不含 `card_editor_effect_smoke.py`，未把该项记作通过。最终提交与测试回执另随交付记录。
