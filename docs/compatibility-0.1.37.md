# HTML / WebView2 兼容维护

本次从 WebView `7f27fb7` 和 HTML `32155db` 各建独立 worktree。HTML 只移植下拉框、滚轮、绿色落点提示、粒子及打劫同步修复，保留原有卡牌池、规则和数值。GitHub 继续仅维护 `webview` 与 `html-main`。

## 兼容处理

- WebView2 / Edge 109 的 CSS 遮罩需要 `-webkit-mask-image`。雾气和棋桌背景补齐前缀，并保留标准声明。
- 浏览器烟测通过 `SMOKE_BROWSER_EXECUTABLE` 固定真实可执行文件；`SMOKE_BROWSER_MAJOR` 与实际版本不符时失败，不能静默换成新内核。
- 原测试写死旧 CSS 缓存版本、逐字比较等价 RGBA 字符串，以及在滚轮尚未停止时取滚动位置，分别改为校验带版本的资源路径、数值颜色通道和稳定后的滚动位置。原断言失败日志保留。
- WebView 的挑战卡持有“落子无悔”或“急中生智”时，悔棋按钮状态现在与服务端已有的禁悔棋规则一致；没有更改规则。
- 同步 SGF 不再写死中国规则，保留引擎已选规则；卡牌改变贴目也不会切换计分规则。两分支真实 KataGo 各通过 12 个劫争和 4 个规则保持场景，比较同步前后完整 `kata-get-rules` JSON。
- 终极模式若引擎返回本地已占用点，明确报错并停止落子，不再随机改成本地空点。错误路径不会推进棋谱、回合或触发卡牌效果。

## 验证方法

使用微软官方分发的 109.0.1518.140 x64 文件离线解压，未替换系统运行时。安装文件 SHA-256：`70D496873A0A1CA14AE0A038D25856B2121B1B4B7BAD9801CE639B144BAC41F8`。`msedge.exe`、`msedgewebview2.exe` 和 `msedge.dll` 的微软签名均有效。

浏览器覆盖启动、所有下拉框、设置、语言、响应式布局、粒子、提示、卡牌覆盖层、复盘、网络及 React 预览。实际 109.0.1518.140 和 152.0.4191.66 各 15/15 通过。两种内核分别运行：

```powershell
$env:SMOKE_BROWSER_EXECUTABLE = '<109运行时目录>\msedge.exe'
$env:SMOKE_BROWSER_MAJOR = '109'
node frontend/scripts/browser-compatibility-smoke.mjs --url=http://127.0.0.1:8890/ --output=output/webview-edge109-final

# 移除固定路径后，指定本次实际系统 Edge 的主版本。
Remove-Item Env:SMOKE_BROWSER_EXECUTABLE
$env:SMOKE_BROWSER_MAJOR = '152'
node frontend/scripts/browser-compatibility-smoke.mjs --url=http://127.0.0.1:8890/ --output=output/webview-edge152-final
```

原生宿主测试使用 pywebview 的 `WEBVIEW2_RUNTIME_PATH`，加载真实 WebView2、生产 `_DesktopWindowApi` 和前端，无远程调试端口。109 和 152 均完成两种窗口大小及 DPR 1.5 下的下拉选择、绿色像素、遮罩和 JS 到宿主关闭检查。系统减少动态开启时验证不产生动画；浏览器测试另行验证实际粒子、旋转、数量上限及清理。

```powershell
python tests/smoke/runtime/webview_frontend_compat_smoke_test.py --base-url http://127.0.0.1:8890/ --runtime-dir '<109运行时目录>' --expected-major 109 --output output/webview-native109.json
python tests/smoke/gameplay/game_state_undo_smoke_test.py
python tests/smoke/ai/ko_regression_smoke_test.py
python tests/smoke/runtime/source_runtime_smoke_test.py --port 0 --output output/runtime-0.1.37.json
npm run typecheck --prefix frontend
npm run build --prefix frontend
```

HTML 的测试命令、规则边界及结果在该分支的 `docs/compatibility-20260908.md`。最终安装包、安装目录和公开 Release 状态以交付回执为准。

## 复核与边界

真实旧内核遮罩消融中，正常样式与仅保留前缀的截图一致，移除全部遮罩则图像改变。HTML 旧基线的下拉交互和小窗口提示测试失败；仅换回旧同步函数的真实 KataGo 检查报告丢失劫禁，修复版通过。

测试运行于当前 Windows，不能据此宣称 Windows 7/8 的安装、Python 或显卡驱动兼容。109 用于回归验证，运行环境优先保持更新。卡牌趣味性与数值调整仍留到下一轮，详见 [卡牌风险](card-risks-20260907.md)。共享引擎完整回合的事务化，以及劫禁重选与多卡牌禁区的组合验证仍未完成。

本次 `npm audit` 还报告既有构建依赖的 6 个审计项（Babel、Browserslist、esbuild、nanoid、PostCSS、Vite），未在兼容修复中升级整个前端工具链；原报告保存在 `output/npm-audit.json`，列入后续维护。HTML 独立烟测依赖的新目录 `npm ci` 已通过，审计为 0。

参考：[微软 WebView2 分发文档](https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/distribution)、[Chrome 120 遮罩前缀说明](https://developer.chrome.com/blog/chrome-120-beta)、[Playwright 浏览器选择](https://playwright.dev/docs/browsers)。
