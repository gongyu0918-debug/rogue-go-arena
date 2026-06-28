import { chromium } from "playwright";

const DEFAULT_URL = "http://127.0.0.1:8876/";
const urlArg = process.argv.find((arg) => arg.startsWith("--url="));
const targetUrl = withLanguageParam(
  urlArg ? urlArg.slice("--url=".length) : process.env.LEGACY_NETWORK_CLIENT_URL || DEFAULT_URL,
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

const browser = await launchBrowser();
const page = await browser.newPage({ viewport: { width: 1366, height: 768 }, deviceScaleFactor: 1 });
const errors = [];

page.on("pageerror", (error) => errors.push(error.message));
page.on("console", (message) => {
  if (message.type() === "error") errors.push(message.text());
});

try {
  await page.goto(targetUrl, { waitUntil: "domcontentloaded" });
  await page.locator("#board-canvas").waitFor({ state: "visible", timeout: 10000 });

  const state = await page.evaluate(async () => {
    const publicFns = [
      typeof window.updateNetworkBadge,
      typeof window.refreshNetworkInfo,
      typeof window.sendWS,
      typeof window.syncDesktopExitButton,
      typeof window.confirmDesktopExit,
      typeof window.performDesktopExit,
    ];
    const shellPublicFns = [
      typeof window.setText,
      typeof window.setTitle,
      typeof window.setThinkingText,
      typeof window.setSoundToggleVisual,
      typeof window.setTerritoryToggleVisual,
      typeof window.hasUsableAnalysis,
      typeof window.analysisPanelEnabled,
      typeof window.setConnectionIndicator,
      typeof window.currentModeLabel,
      typeof window.currentTurnLabel,
      typeof window.moveNumberText,
      typeof window.localizeEngineText,
      typeof window.engineStatusText,
      typeof window.syncClientShell,
      typeof window.quickStartRogue,
      typeof window.openNormalSetup,
      typeof window.toggleFullscreen,
      typeof window.setOptionText,
    ];
    const networkStatusDescriptor = Object.getOwnPropertyDescriptor(window, "__rogueGoArenaNetworkStatus");
    const privateFns = [
      typeof window.normalizeNetworkStatus,
      typeof window.fetchNetworkStatus,
      typeof window.websocketIsOpen,
    ];
    const shellPrivateFns = [
      typeof ENGINE_TEXT_REPLACEMENTS,
      typeof clientShellElements,
      typeof currentCardLabel,
      typeof setEngineShellValue,
      typeof hudEngineText,
    ];

    const originalWs = ws;
    const invalidWsWarnings = [];
    const originalConsoleWarn = console.warn;
    console.warn = (...args) => {
      invalidWsWarnings.push(args.map(value => String(value)).join(" "));
    };
    try {
      ws.onmessage({ data: "not-json" });
    } finally {
      console.warn = originalConsoleWarn;
    }
    const sent = [];
    ws = { readyState: WebSocket.OPEN, send: text => sent.push(text) };
    sendWS({ action: "network_smoke", nested: { value: 7 } });
    const openSend = [...sent];

    ws = { readyState: WebSocket.CLOSED, send: text => sent.push(text) };
    sendWS({ action: "closed_smoke" });
    const afterClosedSendCount = sent.length;

    ws = null;
    sendWS({ action: "null_smoke" });
    const afterNullSendCount = sent.length;
    ws = originalWs;

    window.__rogueGoArenaNetworkStatus = { katago_ready: true, engine_backend: "AssignedEngine", engine_model: "AssignedModel" };
    syncClientShell();
    const assignedBadgeState = {
      cachedBackend: window.__rogueGoArenaNetworkStatus?.engine_backend || "",
      engineValue: document.querySelector("#client-engine-value")?.textContent || "",
      hudEngine: document.querySelector("#hud-engine")?.textContent || "",
    };

    window.__rogueGoArenaNetworkStatus = null;
    syncClientShell();
    const clearedBadgeState = {
      cached: window.__rogueGoArenaNetworkStatus,
      engineValue: document.querySelector("#client-engine-value")?.textContent || "",
    };

    updateNetworkBadge({ katago_ready: true, engine_backend: "SmokeEngine", engine_model: "SmokeModel" });
    syncClientShell();
    const manualBadgeState = {
      cachedBackend: window.__rogueGoArenaNetworkStatus?.engine_backend || "",
      engineValue: document.querySelector("#client-engine-value")?.textContent || "",
      engineTitle: document.querySelector("#client-engine-value")?.title || "",
      hudEngine: document.querySelector("#hud-engine")?.textContent || "",
    };

    gameState = null;
    updateNetworkBadge({ desktop_exit_available: false, desktop_exit_token: "ui-token" });
    syncDesktopExitButton();
    const desktopExitInitial = {
      disabled: document.querySelector("#desktop-exit-button")?.disabled ?? null,
      text: document.querySelector("#desktop-exit-button")?.textContent || "",
      title: document.querySelector("#desktop-exit-button")?.title || "",
    };

    updateNetworkBadge({ desktop_exit_available: true, desktop_exit_token: "ui-token" });
    syncDesktopExitButton();
    const desktopExitModelReady = {
      disabled: document.querySelector("#desktop-exit-button")?.disabled ?? null,
      title: document.querySelector("#desktop-exit-button")?.title || "",
    };

    gameState = { move_number: 0, current_player: "B", game_over: false };
    updateNetworkBadge({ desktop_exit_available: false, desktop_exit_token: "ui-token" });
    syncDesktopExitButton();
    const desktopExitGameStarted = {
      disabled: document.querySelector("#desktop-exit-button")?.disabled ?? null,
    };

    updateNetworkBadge({ desktop_exit_available: true });
    syncDesktopExitButton();
    const desktopExitMissingToken = {
      disabled: document.querySelector("#desktop-exit-button")?.disabled ?? null,
    };
    gameState = null;

    const originalFetchForDesktopExit = window.fetch;
    const originalClearPendingWS = clearPendingWS;
    const originalWsForDesktopExit = ws;
    let desktopExitCloseCount = 0;
    let desktopExitClearCount = 0;
    const desktopExitFetches = [];
    gameState = { move_number: 1, current_player: "B", game_over: false };
    updateNetworkBadge({ desktop_exit_available: true, desktop_exit_token: "ui-token" });
    ws = {
      readyState: WebSocket.OPEN,
      close: () => {
        desktopExitCloseCount += 1;
        ws.readyState = WebSocket.CLOSED;
      },
    };
    intentionalClose = false;
    clearPendingWS = window.clearPendingWS = () => { desktopExitClearCount += 1; };
    window.fetch = async (resource) => {
      const url = String(resource);
      desktopExitFetches.push(url);
      if (url.includes("/desktop_exit")) {
        return { ok: false, status: 503, statusText: "SmokeFail", json: async () => ({ ok: false }) };
      }
      return {
        ok: true,
        json: async () => ({
          desktop_exit_available: true,
          desktop_exit_token: "ui-token",
          katago_ready: true,
        }),
      };
    };
    await performDesktopExit();
    const desktopExitFailedRequest = {
      closeCount: desktopExitCloseCount,
      clearCount: desktopExitClearCount,
      intentionalClose,
      disabled: document.querySelector("#desktop-exit-button")?.disabled ?? null,
      fetches: desktopExitFetches,
    };
    window.fetch = originalFetchForDesktopExit;
    clearPendingWS = window.clearPendingWS = originalClearPendingWS;
    ws = originalWsForDesktopExit;
    gameState = null;

    const defaultCardLabel = document.querySelector("#hud-card")?.textContent || "";
    activeRogueCard = "quickthink";
    ultimateMode = false;
    syncClientShell();
    const rogueCardLabel = document.querySelector("#hud-card")?.textContent || "";
    const expectedRogueCardLabel = getRogueCardName("quickthink") || "";
    activeRogueCard = null;
    ultimateMode = true;
    ultimatePlayerCard = "chain";
    syncClientShell();
    const ultimateCardLabel = document.querySelector("#hud-card")?.textContent || "";
    const expectedUltimateCardLabel = getUltimateCardName("chain") || "";
    ultimateMode = false;
    ultimatePlayerCard = null;
    syncClientShell();

    const previousLang = currentLang;
    await ensureLocale("en");
    await ensureLocale("ja");
    await ensureLocale("ko");
    currentLang = "en";
    const englishEngineState = {
      localized: localizeEngineText("CUDA(升级包) 引擎已就绪 CPU 模式 高端"),
      ready: engineStatusText({ katago_ready: true, engine_backend: "CUDA(升级包)", engine_model: "SmokeModel" }, true),
      modelReady: engineStatusText({ katago_model: true, katago_model_name: "SmokeModel" }, true),
      standby: engineStatusText({}, true),
      checking: engineStatusText({}, false),
    };
    currentLang = "ja";
    const japaneseEngineText = localizeEngineText("引擎初始化中 CPU 模式");
    currentLang = "ko";
    const koreanEngineText = localizeEngineText("AI 在线 高端");
    currentLang = previousLang;

    const originalCurrentModeLabel = window.currentModeLabel;
    const originalCurrentTurnLabel = window.currentTurnLabel;
    const originalMoveNumberText = window.moveNumberText;
    const originalEngineStatusText = window.engineStatusText;
    const originalLocalizeEngineText = window.localizeEngineText;
    window.currentModeLabel = () => "Patched Mode";
    window.currentTurnLabel = () => "Patched Turn";
    window.moveNumberText = value => `Patched Move ${value}`;
    window.engineStatusText = () => "Patched Engine";
    window.localizeEngineText = value => `Patched Localized ${value}`;
    gameState = { move_number: 42, current_player: "B", game_over: false };
    window.__rogueGoArenaNetworkStatus = { engine_backend: "PatchedBackend", engine_model: "PatchedModel" };
    syncClientShell();
    const shellMonkeypatchState = {
      modeValue: document.querySelector("#client-mode-value")?.textContent || "",
      runValue: document.querySelector("#client-run-value")?.textContent || "",
      hudMode: document.querySelector("#hud-mode")?.textContent || "",
      hudTurn: document.querySelector("#hud-turn")?.textContent || "",
      engineValue: document.querySelector("#client-engine-value")?.textContent || "",
      hudEngine: document.querySelector("#hud-engine")?.textContent || "",
    };
    window.currentModeLabel = originalCurrentModeLabel;
    window.currentTurnLabel = originalCurrentTurnLabel;
    window.moveNumberText = originalMoveNumberText;
    window.engineStatusText = originalEngineStatusText;
    window.localizeEngineText = originalLocalizeEngineText;
    gameState = null;
    updateNetworkBadge({ katago_ready: true, engine_backend: "SmokeEngine", engine_model: "SmokeModel" });
    syncClientShell();

    const originalSync = syncClientShell;
    let syncCalls = 0;
    syncClientShell = window.syncClientShell = (...args) => {
      syncCalls += 1;
      return originalSync.apply(window, args);
    };

    setConnectionIndicator(true, "Smoke Connected");
    const connectionIndicatorState = {
      syncCalls,
      statusText: document.querySelector("#status-text")?.textContent || "",
      dotClass: document.querySelector("#status-dot")?.className || "",
      dotTitle: document.querySelector("#status-dot")?.title || "",
    };

    const liveStatus = await refreshNetworkInfo();
    const afterLiveRefresh = {
      returnedObject: !!liveStatus && typeof liveStatus === "object",
      cachedSameObject: window.__rogueGoArenaNetworkStatus === liveStatus,
      syncCalls,
      clientStatus: document.querySelector("#client-status-value")?.textContent || "",
      engineText: document.querySelector("#client-engine-value")?.textContent || "",
    };

    const originalFetch = window.fetch;
    window.fetch = async () => ({ ok: false, json: async () => ({ ignored: true }) });
    const notOkStatus = await refreshNetworkInfo();
    const afterNotOk = {
      returnedNull: notOkStatus === null,
      syncCalls,
    };

    window.fetch = async () => ({ ok: true, json: async () => null });
    const okNullStatus = await refreshNetworkInfo();
    const afterOkNull = {
      returnedNull: okNullStatus === null,
      cached: window.__rogueGoArenaNetworkStatus,
      syncCalls,
      engineText: document.querySelector("#client-engine-value")?.textContent || "",
    };

    window.fetch = async () => { throw new Error("network smoke failure"); };
    const failedStatus = await refreshNetworkInfo();
    const afterFailure = {
      returnedNull: failedStatus === null,
      syncCalls,
      clientStatus: document.querySelector("#client-status-value")?.textContent || "",
    };

    window.fetch = originalFetch;
    syncClientShell = window.syncClientShell = originalSync;
    ws = originalWs;

    return {
      publicFns,
      shellPublicFns,
      networkStatusDescriptor: {
        get: typeof networkStatusDescriptor?.get,
        set: typeof networkStatusDescriptor?.set,
        value: typeof networkStatusDescriptor?.value,
      },
      privateFns,
      shellPrivateFns,
      invalidWsWarnings,
      openSend,
      afterClosedSendCount,
      afterNullSendCount,
      assignedBadgeState,
      clearedBadgeState,
      manualBadgeState,
      desktopExitInitial,
      desktopExitModelReady,
      desktopExitGameStarted,
      desktopExitMissingToken,
      desktopExitFailedRequest,
      defaultCardLabel,
      rogueCardLabel,
      expectedRogueCardLabel,
      ultimateCardLabel,
      expectedUltimateCardLabel,
      englishEngineState,
      japaneseEngineText,
      koreanEngineText,
      shellMonkeypatchState,
      connectionIndicatorState,
      afterLiveRefresh,
      afterNotOk,
      afterOkNull,
      afterFailure,
    };
  });

  assert(state.publicFns.every(type => type === "function"), `network client globals missing: ${state.publicFns.join(", ")}`);
  assert(state.shellPublicFns.every(type => type === "function"), `shell UI globals missing: ${state.shellPublicFns.join(", ")}`);
  assert(state.networkStatusDescriptor.get === "function" && state.networkStatusDescriptor.set === "function", `network status cache is not an accessor: ${JSON.stringify(state.networkStatusDescriptor)}`);
  assert(state.networkStatusDescriptor.value === "undefined", `network status cache unexpectedly has data value: ${JSON.stringify(state.networkStatusDescriptor)}`);
  assert(state.privateFns.every(type => type === "undefined"), `network client private helpers leaked globally: ${state.privateFns.join(", ")}`);
  assert(state.shellPrivateFns.every(type => type === "undefined"), `shell UI private helpers leaked globally: ${state.shellPrivateFns.join(", ")}`);
  assert(state.invalidWsWarnings.some(text => text.includes("invalid JSON message")), `invalid WebSocket JSON warning missing: ${JSON.stringify(state.invalidWsWarnings)}`);
  assert(state.openSend.length === 1, `open WebSocket send count changed: ${JSON.stringify(state.openSend)}`);
  assert(JSON.parse(state.openSend[0]).action === "network_smoke", `open WebSocket payload changed: ${state.openSend[0]}`);
  assert(JSON.parse(state.openSend[0]).nested.value === 7, `open WebSocket nested payload changed: ${state.openSend[0]}`);
  assert(state.afterClosedSendCount === 1, `closed WebSocket should not send: ${state.afterClosedSendCount}`);
  assert(state.afterNullSendCount === 1, `null WebSocket should not send: ${state.afterNullSendCount}`);
  assert(state.assignedBadgeState.cachedBackend === "AssignedEngine", `assigned network cache changed: ${JSON.stringify(state.assignedBadgeState)}`);
  assert(state.assignedBadgeState.engineValue.includes("AssignedEngine"), `assigned engine shell text changed: ${state.assignedBadgeState.engineValue}`);
  assert(state.assignedBadgeState.hudEngine.includes("AssignedEngine"), `assigned HUD engine changed: ${state.assignedBadgeState.hudEngine}`);
  assert(state.clearedBadgeState.cached === null, `cleared network cache should be null: ${JSON.stringify(state.clearedBadgeState)}`);
  assert(state.clearedBadgeState.engineValue.length > 0, "cleared network cache did not leave engine fallback text");
  assert(state.manualBadgeState.cachedBackend === "SmokeEngine", `manual network cache changed: ${JSON.stringify(state.manualBadgeState)}`);
  assert(state.manualBadgeState.engineValue.includes("SmokeEngine"), `manual engine text changed: ${state.manualBadgeState.engineValue}`);
  assert(state.manualBadgeState.engineTitle.includes("SmokeEngine"), `manual engine title changed: ${state.manualBadgeState.engineTitle}`);
  assert(state.manualBadgeState.hudEngine.includes("SmokeEngine"), `manual HUD engine changed: ${state.manualBadgeState.hudEngine}`);
  assert(state.desktopExitInitial.disabled === true, `desktop exit should be disabled before engine/game: ${JSON.stringify(state.desktopExitInitial)}`);
  assert(state.desktopExitInitial.text.includes("关闭并退出"), `desktop exit label changed: ${JSON.stringify(state.desktopExitInitial)}`);
  assert(state.desktopExitInitial.title.length > 0, `desktop exit disabled title missing: ${JSON.stringify(state.desktopExitInitial)}`);
  assert(state.desktopExitModelReady.disabled === false, `desktop exit should enable when engine is available: ${JSON.stringify(state.desktopExitModelReady)}`);
  assert(state.desktopExitGameStarted.disabled === false, `desktop exit should enable once a game exists: ${JSON.stringify(state.desktopExitGameStarted)}`);
  assert(state.desktopExitMissingToken.disabled === true, `desktop exit should stay disabled without token: ${JSON.stringify(state.desktopExitMissingToken)}`);
  assert(state.desktopExitFailedRequest.fetches.some(url => url.includes("/desktop_exit")), `desktop exit failure path did not call route: ${JSON.stringify(state.desktopExitFailedRequest)}`);
  assert(state.desktopExitFailedRequest.closeCount === 0, `desktop exit failure should not close websocket: ${JSON.stringify(state.desktopExitFailedRequest)}`);
  assert(state.desktopExitFailedRequest.clearCount === 0, `desktop exit failure should not clear queued WS messages: ${JSON.stringify(state.desktopExitFailedRequest)}`);
  assert(state.desktopExitFailedRequest.intentionalClose === false, `desktop exit failure should not leave intentionalClose true: ${JSON.stringify(state.desktopExitFailedRequest)}`);
  assert(state.desktopExitFailedRequest.disabled === false, `desktop exit failure should re-enable button: ${JSON.stringify(state.desktopExitFailedRequest)}`);
  assert(state.defaultCardLabel.includes("无卡牌") || state.defaultCardLabel.includes("No Card"), `default card HUD changed: ${state.defaultCardLabel}`);
  assert(state.expectedRogueCardLabel.length > 0, "expected rogue card label missing");
  assert(state.rogueCardLabel === state.expectedRogueCardLabel, `rogue card HUD changed: ${state.rogueCardLabel}`);
  assert(state.expectedUltimateCardLabel.length > 0, "expected ultimate card label missing");
  assert(state.ultimateCardLabel === state.expectedUltimateCardLabel, `ultimate card HUD changed: ${state.ultimateCardLabel}`);
  assert(state.englishEngineState.localized.includes("CUDA (upgrade pack)") && state.englishEngineState.localized.includes("engine ready"), `English engine localization changed: ${state.englishEngineState.localized}`);
  assert(state.englishEngineState.localized.includes("CPU mode") && state.englishEngineState.localized.includes("high-end"), `English engine replacements incomplete: ${state.englishEngineState.localized}`);
  assert(state.englishEngineState.ready === "CUDA (upgrade pack) · SmokeModel", `ready engine status changed: ${state.englishEngineState.ready}`);
  assert(state.englishEngineState.modelReady === "Model ready · SmokeModel", `model-ready engine status changed: ${state.englishEngineState.modelReady}`);
  assert(state.englishEngineState.standby === "AI standby", `connected fallback engine status changed: ${state.englishEngineState.standby}`);
  assert(state.englishEngineState.checking === "Checking...", `checking fallback engine status changed: ${state.englishEngineState.checking}`);
  assert(state.japaneseEngineText.includes("エンジン起動中") && state.japaneseEngineText.includes("CPUモード"), `Japanese engine localization changed: ${state.japaneseEngineText}`);
  assert(state.koreanEngineText.includes("AI 온라인") && state.koreanEngineText.includes("하이엔드"), `Korean engine localization changed: ${state.koreanEngineText}`);
  assert(state.shellMonkeypatchState.modeValue === "Patched Mode", `syncClientShell did not use patched currentModeLabel: ${JSON.stringify(state.shellMonkeypatchState)}`);
  assert(state.shellMonkeypatchState.hudMode === "Patched Mode", `HUD mode did not use patched currentModeLabel: ${JSON.stringify(state.shellMonkeypatchState)}`);
  assert(state.shellMonkeypatchState.runValue === "Patched Move 42 · Patched Turn", `run summary did not use patched move/turn helpers: ${JSON.stringify(state.shellMonkeypatchState)}`);
  assert(state.shellMonkeypatchState.hudTurn === "Patched Turn", `HUD turn did not use patched currentTurnLabel: ${JSON.stringify(state.shellMonkeypatchState)}`);
  assert(state.shellMonkeypatchState.engineValue === "Patched Engine", `engine shell did not use patched engineStatusText: ${JSON.stringify(state.shellMonkeypatchState)}`);
  assert(state.shellMonkeypatchState.hudEngine === "Patched Localized PatchedBackend", `HUD engine did not use patched localizeEngineText: ${JSON.stringify(state.shellMonkeypatchState)}`);
  assert(state.connectionIndicatorState.syncCalls === 1, `setConnectionIndicator did not call monkeypatched syncClientShell: ${JSON.stringify(state.connectionIndicatorState)}`);
  assert(state.connectionIndicatorState.statusText === "Smoke Connected", `connection indicator text changed: ${state.connectionIndicatorState.statusText}`);
  assert(state.connectionIndicatorState.dotClass === "ready", `connection indicator dot class changed: ${state.connectionIndicatorState.dotClass}`);
  assert(state.connectionIndicatorState.dotTitle === "Smoke Connected", `connection indicator title changed: ${state.connectionIndicatorState.dotTitle}`);
  assert(state.afterLiveRefresh.returnedObject, "refreshNetworkInfo did not return live status object");
  assert(state.afterLiveRefresh.cachedSameObject, "refreshNetworkInfo did not cache returned status object");
  assert(state.afterLiveRefresh.syncCalls >= 1, `refreshNetworkInfo did not sync shell on success: ${state.afterLiveRefresh.syncCalls}`);
  assert(state.afterLiveRefresh.clientStatus.length > 0, "client status text missing after live refresh");
  assert(state.afterLiveRefresh.engineText.length > 0, "engine text missing after live refresh");
  assert(state.afterNotOk.returnedNull, "non-ok refresh should return null");
  assert(state.afterNotOk.syncCalls === state.afterLiveRefresh.syncCalls, "non-ok refresh should preserve prior no-sync behavior");
  assert(state.afterOkNull.returnedNull, "ok null refresh should return null");
  assert(state.afterOkNull.cached === null, `ok null refresh should cache null: ${JSON.stringify(state.afterOkNull)}`);
  assert(state.afterOkNull.syncCalls === state.afterLiveRefresh.syncCalls + 1, `ok null refresh should sync shell: ${JSON.stringify(state.afterOkNull)}`);
  assert(state.afterOkNull.engineText.length > 0, "ok null refresh did not leave engine fallback text");
  assert(state.afterFailure.returnedNull, "failed refresh should return null");
  assert(state.afterFailure.syncCalls === state.afterOkNull.syncCalls + 1, `failed refresh did not sync shell: ${JSON.stringify(state.afterFailure)}`);
  assert(state.afterFailure.clientStatus.length > 0, "client status text missing after failed refresh");
  assert(errors.length === 0, `browser errors: ${errors.join("; ")}`);

  console.log(JSON.stringify({
    ok: true,
    sent: state.openSend.length,
    syncCalls: state.afterFailure.syncCalls,
    clientStatus: state.afterLiveRefresh.clientStatus,
  }, null, 2));
} finally {
  await browser.close();
}
