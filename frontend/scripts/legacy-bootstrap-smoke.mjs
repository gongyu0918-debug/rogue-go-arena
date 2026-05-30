import { chromium } from "playwright";

const DEFAULT_URL = "http://127.0.0.1:8876/";
const urlArg = process.argv.find((arg) => arg.startsWith("--url="));
const targetUrl = withLanguageParam(
  urlArg ? urlArg.slice("--url=".length) : process.env.LEGACY_BOOTSTRAP_URL || DEFAULT_URL,
  "zh"
);

async function launchBrowser() {
  try {
    return await chromium.launch({ channel: "msedge", headless: true });
  } catch {
    return chromium.launch({ headless: true });
  }
}

function withLanguageParam(rawUrl, lang) {
  const url = new URL(rawUrl);
  url.searchParams.set("lang", lang);
  return url.toString();
}

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

async function pageState(page) {
  return page.evaluate(() => {
    const canvasNonblank = () => {
      const canvas = document.querySelector("#board-canvas");
      const ctx = canvas?.getContext("2d");
      if (!ctx || canvas.width < 10 || canvas.height < 10) return false;
      const data = ctx.getImageData(0, 0, canvas.width, canvas.height).data;
      for (let i = 3; i < data.length; i += 101) {
        if (data[i] !== 0 && (data[i - 1] !== 0 || data[i - 2] !== 0 || data[i - 3] !== 0)) return true;
      }
      return false;
    };
    const rect = document.querySelector("#board-canvas")?.getBoundingClientRect();
    return {
      publicFns: [
        typeof window.connect,
        typeof window.initBoard,
        typeof window.bootstrapApp,
        typeof window.installLegacyBootstrapHooks,
      ],
      htmlLang: document.documentElement.lang,
      currentLang,
      wsReadyState: ws?.readyState ?? -1,
      wsOpenConstant: WebSocket.OPEN,
      statusText: document.querySelector("#status-text")?.textContent || "",
      logText: document.querySelector("#game-log")?.textContent || "",
      boardWatchdogActive: !!boardWatchdogTimer,
      boardRenderSize,
      boardRect: rect
        ? {
            width: Math.round(rect.width),
            height: Math.round(rect.height),
          }
        : null,
      canvasNonblank: canvasNonblank(),
    };
  });
}

const browser = await launchBrowser();
const page = await browser.newPage({ viewport: { width: 1366, height: 768 }, deviceScaleFactor: 1 });
const errors = [];

page.on("pageerror", (error) => errors.push(error.message));
page.on("console", (message) => {
  if (message.type() === "error") errors.push(message.text());
});

try {
  await page.goto(targetUrl, { waitUntil: "domcontentloaded" });
  await page.waitForFunction(() => ws && ws.readyState === WebSocket.OPEN, null, { timeout: 10000 });
  await page.locator("#board-canvas").waitFor({ state: "visible", timeout: 10000 });
  await page.waitForTimeout(500);

  const initialState = await pageState(page);
  assert(initialState.publicFns.every((type) => type === "function"), `bootstrap globals missing: ${initialState.publicFns.join(", ")}`);
  assert(initialState.htmlLang === "zh-CN", `bootstrap did not apply language: ${initialState.htmlLang}`);
  assert(initialState.wsReadyState === initialState.wsOpenConstant, `websocket did not connect: ${initialState.wsReadyState}`);
  assert(initialState.statusText.includes("已连接"), `connection indicator did not update: ${initialState.statusText}`);
  assert(initialState.logText.includes("已连接"), "connection log did not render");
  assert(initialState.boardWatchdogActive, "board watchdog was not installed");
  assert(initialState.boardRenderSize >= 300, `board render size too small: ${initialState.boardRenderSize}`);
  assert(initialState.boardRect?.width >= 300 && initialState.boardRect?.height >= 300, `board rect too small: ${JSON.stringify(initialState.boardRect)}`);
  assert(initialState.canvasNonblank, "board canvas is blank after bootstrap");

  const hookState = await page.evaluate(() => {
    const before = boardWatchdogTimer;
    installLegacyBootstrapHooks();
    return { sameTimer: before === boardWatchdogTimer, hasTimer: !!boardWatchdogTimer };
  });
  assert(hookState.hasTimer && hookState.sameTimer, "bootstrap hooks were installed more than once");

  await page.evaluate(() => {
    const originalEnsureBoardReady = ensureBoardReady;
    const originalResizeBoard = resizeBoard;
    window.__legacyBootstrapHookCounts = {
      ensureBoardReady: 0,
      ensureDelays: [],
      resizeBoard: 0,
      resizeSizes: [],
    };
    ensureBoardReady = function(...args) {
      window.__legacyBootstrapHookCounts.ensureBoardReady += 1;
      window.__legacyBootstrapHookCounts.ensureDelays.push(args[0]);
      return originalEnsureBoardReady.apply(this, args);
    };
    resizeBoard = function(...args) {
      window.__legacyBootstrapHookCounts.resizeBoard += 1;
      window.__legacyBootstrapHookCounts.resizeSizes.push(args[0]);
      return originalResizeBoard.apply(this, args);
    };
    _boardCacheParams = "smoke-cache";
    _offScreenBoard = { smoke: true };
    _stoneSpriteCache = new Map([["smoke", true]]);
    window.__legacyBootstrapCacheSentinels = {
      boardParams: _boardCacheParams,
      offscreen: _offScreenBoard,
      spriteCache: _stoneSpriteCache,
    };
  });

  await page.setViewportSize({ width: 1280, height: 720 });
  await page.evaluate(() => {
    window.dispatchEvent(new Event("pageshow"));
    document.dispatchEvent(new Event("visibilitychange"));
    window.dispatchEvent(new Event("resize"));
  });
  await page.waitForTimeout(300);
  const resizedState = await pageState(page);
  const hookDispatchState = await page.evaluate(() => ({
    counts: window.__legacyBootstrapHookCounts,
    cacheInvalidated: {
      boardParamsChanged: _boardCacheParams !== window.__legacyBootstrapCacheSentinels.boardParams,
      offscreenReplaced: _offScreenBoard !== window.__legacyBootstrapCacheSentinels.offscreen,
      spriteCacheReplaced: _stoneSpriteCache !== window.__legacyBootstrapCacheSentinels.spriteCache,
    },
  }));
  assert(hookDispatchState.counts.resizeBoard >= 1, `resize hook did not call resizeBoard: ${JSON.stringify(hookDispatchState.counts)}`);
  assert(hookDispatchState.counts.ensureBoardReady >= 3, `page recovery hooks did not call ensureBoardReady: ${JSON.stringify(hookDispatchState.counts)}`);
  assert(hookDispatchState.counts.ensureDelays.includes(0), `pageshow/visibility hooks did not request immediate recovery: ${JSON.stringify(hookDispatchState.counts)}`);
  assert(hookDispatchState.counts.ensureDelays.includes(100), `resize hook did not request delayed recovery: ${JSON.stringify(hookDispatchState.counts)}`);
  assert(
    hookDispatchState.cacheInvalidated.boardParamsChanged &&
      hookDispatchState.cacheInvalidated.offscreenReplaced &&
      hookDispatchState.cacheInvalidated.spriteCacheReplaced,
    `resize hook did not invalidate board render caches: ${JSON.stringify(hookDispatchState.cacheInvalidated)}`
  );
  assert(resizedState.boardRenderSize >= 300, `resize hook left board too small: ${resizedState.boardRenderSize}`);
  assert(resizedState.canvasNonblank, "board canvas is blank after resize hook");

  await page.evaluate(() => {
    intentionalClose = true;
    ws.close();
  });
  await page.waitForFunction(() => !ws || ws.readyState === WebSocket.CLOSED, null, { timeout: 5000 });
  await page.evaluate(() => connect());
  await page.waitForFunction(() => ws && ws.readyState === WebSocket.OPEN, null, { timeout: 10000 });
  const reconnectedState = await pageState(page);
  assert(reconnectedState.wsReadyState === reconnectedState.wsOpenConstant, `connect() did not reopen websocket: ${reconnectedState.wsReadyState}`);
  assert(reconnectedState.statusText.includes("已连接"), `connection indicator not restored: ${reconnectedState.statusText}`);

  await page.evaluate(() => {
    intentionalClose = false;
    ws.close();
  });
  await page.waitForFunction(
    () => document.querySelector("#status-text")?.textContent.includes("重连中"),
    null,
    { timeout: 5000 }
  );
  await page.waitForFunction(() => ws && ws.readyState === WebSocket.OPEN, null, { timeout: 10000 });
  const autoReconnectedState = await pageState(page);
  assert(autoReconnectedState.wsReadyState === autoReconnectedState.wsOpenConstant, `automatic reconnect did not reopen websocket: ${autoReconnectedState.wsReadyState}`);
  assert(autoReconnectedState.statusText.includes("已连接"), `automatic reconnect did not restore indicator: ${autoReconnectedState.statusText}`);

  assert(errors.length === 0, `browser errors: ${errors.join("; ")}`);
  console.log(JSON.stringify({
    ok: true,
    boardRenderSize: autoReconnectedState.boardRenderSize,
    statusText: autoReconnectedState.statusText,
  }, null, 2));
} finally {
  await browser.close();
}
