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
    ];

    const originalWs = ws;
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

    updateNetworkBadge({ katago_ready: true, engine_backend: "SmokeEngine", engine_model: "SmokeModel" });
    syncClientShell();
    const manualBadgeState = {
      cachedBackend: window.__rogueGoArenaNetworkStatus?.engine_backend || "",
      engineValue: document.querySelector("#client-engine-value")?.textContent || "",
      hudEngine: document.querySelector("#hud-engine")?.textContent || "",
    };

    const originalSync = syncClientShell;
    let syncCalls = 0;
    syncClientShell = window.syncClientShell = (...args) => {
      syncCalls += 1;
      return originalSync.apply(window, args);
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
      openSend,
      afterClosedSendCount,
      afterNullSendCount,
      manualBadgeState,
      afterLiveRefresh,
      afterNotOk,
      afterFailure,
    };
  });

  assert(state.publicFns.every(type => type === "function"), `network client globals missing: ${state.publicFns.join(", ")}`);
  assert(state.openSend.length === 1, `open WebSocket send count changed: ${JSON.stringify(state.openSend)}`);
  assert(JSON.parse(state.openSend[0]).action === "network_smoke", `open WebSocket payload changed: ${state.openSend[0]}`);
  assert(JSON.parse(state.openSend[0]).nested.value === 7, `open WebSocket nested payload changed: ${state.openSend[0]}`);
  assert(state.afterClosedSendCount === 1, `closed WebSocket should not send: ${state.afterClosedSendCount}`);
  assert(state.afterNullSendCount === 1, `null WebSocket should not send: ${state.afterNullSendCount}`);
  assert(state.manualBadgeState.cachedBackend === "SmokeEngine", `manual network cache changed: ${JSON.stringify(state.manualBadgeState)}`);
  assert(state.manualBadgeState.engineValue.includes("SmokeEngine"), `manual engine text changed: ${state.manualBadgeState.engineValue}`);
  assert(state.manualBadgeState.hudEngine.includes("SmokeEngine"), `manual HUD engine changed: ${state.manualBadgeState.hudEngine}`);
  assert(state.afterLiveRefresh.returnedObject, "refreshNetworkInfo did not return live status object");
  assert(state.afterLiveRefresh.cachedSameObject, "refreshNetworkInfo did not cache returned status object");
  assert(state.afterLiveRefresh.syncCalls >= 1, `refreshNetworkInfo did not sync shell on success: ${state.afterLiveRefresh.syncCalls}`);
  assert(state.afterLiveRefresh.clientStatus.length > 0, "client status text missing after live refresh");
  assert(state.afterLiveRefresh.engineText.length > 0, "engine text missing after live refresh");
  assert(state.afterNotOk.returnedNull, "non-ok refresh should return null");
  assert(state.afterNotOk.syncCalls === state.afterLiveRefresh.syncCalls, "non-ok refresh should preserve prior no-sync behavior");
  assert(state.afterFailure.returnedNull, "failed refresh should return null");
  assert(state.afterFailure.syncCalls === state.afterLiveRefresh.syncCalls + 1, `failed refresh did not sync shell: ${JSON.stringify(state.afterFailure)}`);
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
