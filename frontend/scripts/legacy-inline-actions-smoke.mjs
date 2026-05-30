import { chromium } from "playwright";

const DEFAULT_URL = "http://127.0.0.1:8876/";
const urlArg = process.argv.find((arg) => arg.startsWith("--url="));
const targetUrl = withLanguageParam(
  urlArg ? urlArg.slice("--url=".length) : process.env.LEGACY_INLINE_ACTIONS_URL || DEFAULT_URL,
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
  await page.waitForFunction(() => ws && ws.readyState === WebSocket.OPEN, null, { timeout: 10000 });
  await page.locator("#board-canvas").waitFor({ state: "visible", timeout: 10000 });

  const publicState = await page.evaluate(() => ({
    inlineHandlers: document.querySelectorAll("[onclick], [onchange], [oninput], [onsubmit]").length,
    publicFns: [
      typeof window.openSettingsDrawer,
      typeof window.closeSettingsDrawer,
    ],
  }));
  assert(publicState.inlineHandlers === 0, `inline handlers still present: ${publicState.inlineHandlers}`);
  assert(publicState.publicFns.every(type => type === "function"), `inline action globals missing: ${publicState.publicFns.join(", ")}`);

  await page.evaluate(() => {
    window.__inlineSmoke = { payloads: [], fullscreenRequests: 0, fullscreenExits: 0, reviewAnalysisRequests: 0, renders: 0 };
    sendWS = window.sendWS = payload => { window.__inlineSmoke.payloads.push(payload); };
    connect = window.connect = () => {};
    document.documentElement.requestFullscreen = () => {
      window.__inlineSmoke.fullscreenRequests += 1;
      return Promise.resolve();
    };
    document.exitFullscreen = () => {
      window.__inlineSmoke.fullscreenExits += 1;
      return Promise.resolve();
    };
    requestReviewAnalysis = window.requestReviewAnalysis = () => {
      window.__inlineSmoke.reviewAnalysisRequests += 1;
    };
    const originalRender = render;
    render = window.render = (...args) => {
      window.__inlineSmoke.renders += 1;
      return originalRender.apply(this, args);
    };
  });

  await page.locator("#btn-setup").click();
  const quickSetupState = await page.evaluate(() => ({
    startMode,
    setupOpen: document.querySelector("#setup-modal")?.classList.contains("show") || false,
  }));
  assert(quickSetupState.setupOpen, "toolbar setup did not open setup modal");

  await page.locator("#mode-rogue").click();
  const rogueModeState = await page.evaluate(() => ({
    startMode,
    active: document.querySelector("#mode-rogue")?.classList.contains("active") || false,
    variantVisible: document.querySelector("#row-rogue-variant")?.style.display || "",
  }));
  assert(rogueModeState.startMode === "rogue", `setup mode button did not select rogue: ${rogueModeState.startMode}`);
  assert(rogueModeState.active, "rogue mode button did not become active");
  assert(rogueModeState.variantVisible === "flex", `rogue variant row did not show: ${rogueModeState.variantVisible}`);

  await page.locator("#setup-modal-close").click();
  const setupClosed = await page.evaluate(() => !(document.querySelector("#setup-modal")?.classList.contains("show") || false));
  assert(setupClosed, "setup modal close binding failed");

  const hiddenQuickSetupState = await page.evaluate(() => {
    document.querySelector("#quick-setup").click();
    return {
      startMode,
      setupOpen: document.querySelector("#setup-modal")?.classList.contains("show") || false,
    };
  });
  assert(hiddenQuickSetupState.startMode === "normal", `quick setup did not select normal mode: ${hiddenQuickSetupState.startMode}`);
  assert(hiddenQuickSetupState.setupOpen, "quick setup binding did not open setup modal");
  await page.locator("#setup-modal-close").click();

  await page.evaluate(() => document.querySelector("#quick-fullscreen").click());
  const fullscreenState = await page.evaluate(() => window.__inlineSmoke.fullscreenRequests);
  assert(fullscreenState >= 1, `fullscreen action did not request fullscreen: ${fullscreenState}`);

  await page.locator("#btn-settings").click();
  const drawerOpen = await page.evaluate(() => document.querySelector("#settings-drawer")?.classList.contains("open") || false);
  assert(drawerOpen, "settings toolbar action did not open drawer");
  await page.locator("#settings-drawer-close").click();
  const drawerClosed = await page.evaluate(() => !(document.querySelector("#settings-drawer")?.classList.contains("open") || false));
  assert(drawerClosed, "settings drawer close binding failed");

  await page.locator("#btn-rogue-wiki").click();
  const wikiOpen = await page.evaluate(() => document.querySelector("#rogue-wiki-modal")?.classList.contains("show") || false);
  assert(wikiOpen, "wiki toolbar action did not open modal");
  await page.locator("#rogue-wiki-close").click();
  const wikiClosed = await page.evaluate(() => !(document.querySelector("#rogue-wiki-modal")?.classList.contains("show") || false));
  assert(wikiClosed, "wiki close binding failed");

  await page.evaluate(() => showConfirmModal("inline smoke confirm", () => { window.__inlineSmoke.confirmed = true; }));
  await page.locator("#confirm-cancel").click();
  const confirmCancelled = await page.evaluate(() => ({
    confirmOpen: document.querySelector("#confirm-modal")?.classList.contains("show") || false,
    confirmed: window.__inlineSmoke.confirmed === true,
  }));
  assert(!confirmCancelled.confirmOpen, "confirm cancel did not close modal");
  assert(!confirmCancelled.confirmed, "confirm cancel should not invoke OK callback");

  await page.evaluate(() => {
    showOverlay("胜利", "inline smoke", "B", "B+R");
  });
  await page.locator("#overlay-close").click();
  const overlayClosed = await page.evaluate(() => document.querySelector("#overlay")?.className || "");
  assert(overlayClosed === "", `overlay close binding failed: ${overlayClosed}`);

  await page.evaluate(() => {
    gameState = {
      size: 9,
      board: Array.from({ length: 9 }, () => Array(9).fill(null)),
      moves_list: [["B", "D4"], ["W", "Q16"]],
      current_player: "B",
      captures: { B: 0, W: 0 },
      move_number: 2,
      game_over: true,
    };
    showOverlay("胜利", "inline smoke", "B", "B+R");
  });
  await page.locator("#overlay-review").click();
  const reviewState = await page.evaluate(() => ({
    reviewMode,
    overlayClass: document.querySelector("#overlay")?.className || "",
    mainToolbarDisplay: document.querySelector("#main-toolbar")?.style.display || "",
    reviewToolbarDisplay: document.querySelector("#review-toolbar")?.style.display || "",
    reviewAnalysisRequests: window.__inlineSmoke.reviewAnalysisRequests,
  }));
  assert(reviewState.reviewMode, "overlay review binding did not enter review mode");
  assert(reviewState.overlayClass === "", `overlay review did not close overlay: ${reviewState.overlayClass}`);
  assert(reviewState.mainToolbarDisplay === "none", `review mode did not hide main toolbar: ${reviewState.mainToolbarDisplay}`);
  assert(reviewState.reviewToolbarDisplay === "flex", `review mode did not show review toolbar: ${reviewState.reviewToolbarDisplay}`);
  assert(reviewState.reviewAnalysisRequests >= 1, "review mode did not request review analysis");

  await page.evaluate(() => {
    showOverlay("胜利", "inline smoke", "B", "B+R");
    document.querySelector("#setup-modal")?.classList.remove("show");
  });
  const beforeOverlayNewGamePayloadCount = await page.evaluate(() => window.__inlineSmoke.payloads.length);
  await page.locator("#overlay-new-game").click();
  await page.waitForFunction(
    count => window.__inlineSmoke.payloads.length > count && window.__inlineSmoke.payloads.at(-1)?.action === "new_game",
    beforeOverlayNewGamePayloadCount,
    { timeout: 3000 }
  );
  const newGameState = await page.evaluate(() => ({
    overlayClass: document.querySelector("#overlay")?.className || "",
    latestPayload: window.__inlineSmoke.payloads.at(-1) || null,
  }));
  assert(newGameState.overlayClass === "", `new game shortcut did not close overlay: ${newGameState.overlayClass}`);
  assert(newGameState.latestPayload?.action === "new_game", `new game shortcut did not start a game: ${JSON.stringify(newGameState.latestPayload)}`);

  const beforeTopQuickRoguePayloadCount = await page.evaluate(() => window.__inlineSmoke.payloads.length);
  await page.evaluate(() => document.querySelector("#quick-rogue").click());
  await page.waitForFunction(
    count => window.__inlineSmoke.payloads.length > count && window.__inlineSmoke.payloads.at(-1)?.action === "new_game",
    beforeTopQuickRoguePayloadCount,
    { timeout: 3000 }
  );
  const topQuickRogueState = await page.evaluate(() => ({
    startMode,
    variant: document.querySelector("#sel-rogue-variant")?.value || "",
    latestPayload: window.__inlineSmoke.payloads.at(-1) || null,
  }));
  assert(topQuickRogueState.startMode === "rogue", `top quick rogue did not select rogue: ${topQuickRogueState.startMode}`);
  assert(topQuickRogueState.variant === "solo", `top quick rogue did not select solo variant: ${topQuickRogueState.variant}`);
  assert(topQuickRogueState.latestPayload?.action === "new_game", `top quick rogue did not start a game: ${JSON.stringify(topQuickRogueState.latestPayload)}`);

  const beforeToolbarQuickRoguePayloadCount = await page.evaluate(() => window.__inlineSmoke.payloads.length);
  await page.locator("#btn-quick-rogue").click();
  await page.waitForFunction(
    count => window.__inlineSmoke.payloads.length > count && window.__inlineSmoke.payloads.at(-1)?.action === "new_game",
    beforeToolbarQuickRoguePayloadCount,
    { timeout: 3000 }
  );
  const quickRogueState = await page.evaluate(() => ({
    startMode,
    variant: document.querySelector("#sel-rogue-variant")?.value || "",
    latestPayload: window.__inlineSmoke.payloads.at(-1) || null,
  }));
  assert(quickRogueState.startMode === "rogue", `quick rogue toolbar did not select rogue: ${quickRogueState.startMode}`);
  assert(quickRogueState.variant === "solo", `quick rogue did not select solo variant: ${quickRogueState.variant}`);
  assert(quickRogueState.latestPayload?.action === "new_game", `quick rogue did not start a game: ${JSON.stringify(quickRogueState.latestPayload)}`);

  assert(errors.length === 0, `browser errors: ${errors.join("; ")}`);
  console.log(JSON.stringify({
    ok: true,
    inlineHandlers: publicState.inlineHandlers,
    payloads: await page.evaluate(() => window.__inlineSmoke.payloads.map(payload => payload.action)),
  }, null, 2));
} finally {
  await browser.close();
}
