import { chromium } from "playwright";

const DEFAULT_URL = "http://127.0.0.1:8876/";
const urlArg = process.argv.find((arg) => arg.startsWith("--url="));
const targetUrl = withLanguageParam(
  urlArg ? urlArg.slice("--url=".length) : process.env.LEGACY_SETUP_CONTROLS_URL || DEFAULT_URL,
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

  await page.locator("#btn-setup").click();
  await page.locator("#setup-modal.show").waitFor({ state: "visible", timeout: 5000 });

  const modeState = await page.evaluate(() => {
    setMode("rogue");
    return {
      publicFns: [
        typeof window.getRogueVariantMode,
        typeof window.openSetupModal,
        typeof window.closeSetupModal,
        typeof window.openRogueWiki,
        typeof window.closeRogueWiki,
        typeof window.showConfirmModal,
        typeof window.closeConfirmModal,
        typeof window.newGameFromOverlay,
        typeof window.setMode,
        typeof window.startGameFromSetup,
      ],
      startMode,
      rogueVariantRow: document.querySelector("#row-rogue-variant")?.style.display || "",
      sizeRow: document.querySelector("#row-size")?.style.display || "",
      handicapRow: document.querySelector("#row-handicap")?.style.display || "",
      hint: document.querySelector("#mode-hint")?.textContent || "",
      sizeValue: document.querySelector("#sel-size")?.value || "",
      handicapValue: document.querySelector("#sel-handicap")?.value || "",
    };
  });

  assert(modeState.publicFns.every((type) => type === "function"), `setup control globals missing: ${modeState.publicFns.join(", ")}`);
  assert(modeState.startMode === "rogue", `setMode did not switch to rogue: ${modeState.startMode}`);
  assert(modeState.rogueVariantRow === "flex", `rogue variant row not visible: ${modeState.rogueVariantRow}`);
  assert(modeState.sizeRow === "none", `board size row not hidden for rogue: ${modeState.sizeRow}`);
  assert(modeState.handicapRow === "none", `handicap row not hidden for rogue: ${modeState.handicapRow}`);
  assert(modeState.hint.includes("单人抽卡"), `rogue hint did not render: ${modeState.hint}`);
  assert(modeState.sizeValue === "19", `rogue mode did not force 19x19: ${modeState.sizeValue}`);
  assert(modeState.handicapValue === "0", `rogue mode did not clear handicap: ${modeState.handicapValue}`);

  const variantAndTimeState = await page.evaluate(() => {
    document.querySelector("#sel-rogue-variant").value = "dual";
    document.querySelector("#sel-rogue-variant").dispatchEvent(new Event("change", { bubbles: true }));
    document.querySelector("#sel-time-mode").value = "byoyomi";
    document.querySelector("#sel-time-mode").dispatchEvent(new Event("change", { bubbles: true }));
    return {
      rogueVariant: getRogueVariantMode(),
      hint: document.querySelector("#mode-hint")?.textContent || "",
      timeSettingsDisplay: document.querySelector("#time-settings")?.style.display || "",
      byoyomiDisplay: document.querySelector("#row-byoyomi")?.style.display || "",
    };
  });

  assert(variantAndTimeState.rogueVariant === "dual", `variant did not update: ${variantAndTimeState.rogueVariant}`);
  assert(variantAndTimeState.hint.includes("双人抽卡"), `variant hint did not update: ${variantAndTimeState.hint}`);
  assert(variantAndTimeState.timeSettingsDisplay === "", `time settings did not show: ${variantAndTimeState.timeSettingsDisplay}`);
  assert(variantAndTimeState.byoyomiDisplay === "flex", `byoyomi row did not show: ${variantAndTimeState.byoyomiDisplay}`);

  const stageState = await page.evaluate(() => {
    const originalResizeBoard = resizeBoard;
    const originalRender = render;
    window.__setupStageSmoke = {
      resizeCalls: 0,
      resizeSizes: [],
      renderCalls: 0,
      cacheParams: "setup-stage-cache",
      offscreen: { smoke: true },
      stoneSprites: new Map([["smoke", true]]),
    };
    resizeBoard = function(...args) {
      window.__setupStageSmoke.resizeCalls += 1;
      window.__setupStageSmoke.resizeSizes.push(args[0]);
      return originalResizeBoard.apply(this, args);
    };
    render = function(...args) {
      window.__setupStageSmoke.renderCalls += 1;
      return originalRender.apply(this, args);
    };
    _boardCacheParams = window.__setupStageSmoke.cacheParams;
    _offScreenBoard = window.__setupStageSmoke.offscreen;
    _stoneSpriteCache = window.__setupStageSmoke.stoneSprites;
    document.querySelector("#sel-stage-preset").value = "1440";
    document.querySelector("#sel-stage-preset").dispatchEvent(new Event("change", { bubbles: true }));
    return {
      stagePreset,
      stored: localStorage.getItem("rogue_go_arena_stage_preset"),
      boardRenderSize,
      resizeCalls: window.__setupStageSmoke.resizeCalls,
      resizeSizes: window.__setupStageSmoke.resizeSizes,
      renderCalls: window.__setupStageSmoke.renderCalls,
      cacheInvalidated: {
        boardParams: _boardCacheParams !== window.__setupStageSmoke.cacheParams,
        offscreen: _offScreenBoard !== window.__setupStageSmoke.offscreen,
        stoneSprites: _stoneSpriteCache !== window.__setupStageSmoke.stoneSprites,
      },
    };
  });

  assert(stageState.stagePreset === "1440", `stage preset did not update: ${stageState.stagePreset}`);
  assert(stageState.stored === "1440", `stage preset was not persisted: ${stageState.stored}`);
  assert(stageState.resizeCalls >= 1, `stage preset did not call resizeBoard: ${JSON.stringify(stageState)}`);
  assert(stageState.resizeSizes.some(size => Number(size) > 0), `stage preset resized with invalid board size: ${JSON.stringify(stageState)}`);
  assert(stageState.renderCalls >= 1, `stage preset did not render: ${JSON.stringify(stageState)}`);
  assert(Object.values(stageState.cacheInvalidated).every(Boolean), `stage preset did not invalidate board caches: ${JSON.stringify(stageState)}`);

  const confirmState = await page.evaluate(() => {
    window.__setupSmokeConfirmed = false;
    showConfirmModal("setup smoke confirm", () => { window.__setupSmokeConfirmed = true; });
    const opened = document.querySelector("#confirm-modal")?.classList.contains("show") || false;
    document.querySelector("#btn-confirm-ok").click();
    return {
      opened,
      confirmed: window.__setupSmokeConfirmed,
      closed: !(document.querySelector("#confirm-modal")?.classList.contains("show") || false),
    };
  });

  assert(confirmState.opened, "showConfirmModal did not open");
  assert(confirmState.confirmed, "confirm callback did not run");
  assert(confirmState.closed, "confirm modal did not close after OK");

  const payloadState = await page.evaluate(async () => {
    const delay = (ms) => new Promise(resolve => setTimeout(resolve, ms));
    const setSelectValue = (selector, value) => {
      const select = document.querySelector(selector);
      if (!select) return;
      select.value = value;
    };
    const captureNewGamePayload = async (name, configure) => {
      const beforePayloadCount = window.__setupSmoke.payloads.length;
      const beforeConnectCalls = window.__setupSmoke.connectCalls;
      configure();
      document.querySelector("#btn-new").click();
      await delay(750);
      return {
        name,
        connectCalls: window.__setupSmoke.connectCalls - beforeConnectCalls,
        payload: window.__setupSmoke.payloads[beforePayloadCount] || null,
        timerMode,
        mainTimeSetting,
        byoPeriodsSetting,
        byoTimeSetting,
        modalOpen: document.querySelector("#setup-modal")?.classList.contains("show") || false,
        twoPlayerMode,
        gameStateIsNull: gameState === null,
        reviewMode,
        gameLogHtml: document.querySelector("#game-log")?.innerHTML || "",
      };
    };

    window.__setupSmoke = { connectCalls: 0, payloads: [] };
    connect = window.connect = () => { window.__setupSmoke.connectCalls += 1; };
    sendWS = window.sendWS = (payload) => { window.__setupSmoke.payloads.push(payload); };

    const scenarios = [];
    scenarios.push(await captureNewGamePayload("normal", () => {
      setMode("normal");
      setSelectValue("#sel-size", "13");
      setSelectValue("#sel-komi", "6.5");
      setSelectValue("#sel-handicap", "0");
      setSelectValue("#sel-color", "W");
      setSelectValue("#sel-level", "10k");
      setSelectValue("#sel-ai-style", "attack");
      setSelectValue("#sel-time-mode", "none");
    }));
    scenarios.push(await captureNewGamePayload("two", () => {
      setMode("two");
      setSelectValue("#sel-size", "9");
      setSelectValue("#sel-komi", "7.5");
      setSelectValue("#sel-handicap", "2");
      setSelectValue("#sel-color", "W");
      setSelectValue("#sel-level", "12k");
    }));
    scenarios.push(await captureNewGamePayload("watch", () => {
      setMode("watch");
      setSelectValue("#sel-size", "19");
      setSelectValue("#sel-komi", "6.5");
      setSelectValue("#sel-color", "W");
      setSelectValue("#sel-level", "10k");
      setSelectValue("#sel-level-black", "5k");
      setSelectValue("#sel-level-white", "a1d");
      setSelectValue("#sel-ai-style-black", "territory");
      setSelectValue("#sel-ai-style-white", "defense");
    }));
    scenarios.push(await captureNewGamePayload("rogue-solo", () => {
      setMode("rogue");
      setSelectValue("#sel-rogue-variant", "solo");
      document.querySelector("#sel-rogue-variant").dispatchEvent(new Event("change", { bubbles: true }));
      setSelectValue("#sel-color", "W");
      setSelectValue("#sel-komi", "6.5");
      setSelectValue("#sel-ai-style", "influence");
    }));
    scenarios.push(await captureNewGamePayload("rogue-dual", () => {
      setMode("rogue");
      setSelectValue("#sel-rogue-variant", "dual");
      document.querySelector("#sel-rogue-variant").dispatchEvent(new Event("change", { bubbles: true }));
      setSelectValue("#sel-color", "B");
      setSelectValue("#sel-time-mode", "byoyomi");
      setSelectValue("#sel-main-time", "180");
      setSelectValue("#sel-byo-periods", "5");
      setSelectValue("#sel-byo-time", "20");
    }));
    scenarios.push(await captureNewGamePayload("rogue-ultimate", () => {
      setMode("rogue");
      setSelectValue("#sel-rogue-variant", "ultimate");
      document.querySelector("#sel-rogue-variant").dispatchEvent(new Event("change", { bubbles: true }));
      setSelectValue("#sel-color", "B");
    }));
    scenarios.push(await captureNewGamePayload("challenge", () => {
      challengeSession.active = false;
      challengeSession.cleared = true;
      setMode("challenge");
      setSelectValue("#sel-size", "13");
      setSelectValue("#sel-komi", "0");
      setSelectValue("#sel-color", "B");
      setSelectValue("#sel-level", "8k");
    }));

    return { scenarios };
  });

  const scenarios = Object.fromEntries(payloadState.scenarios.map(item => [item.name, item]));
  payloadState.scenarios.forEach((scenario) => {
    assert(scenario.connectCalls === 1, `${scenario.name}: new game did not call connect once: ${scenario.connectCalls}`);
    assert(scenario.payload?.action === "new_game", `${scenario.name}: payload missing: ${JSON.stringify(scenario.payload)}`);
    assert(!scenario.modalOpen, `${scenario.name}: setup modal did not close`);
    assert(scenario.gameStateIsNull, `${scenario.name}: gameState was not cleared before server response`);
    assert(!scenario.reviewMode, `${scenario.name}: review mode was not cleared`);
    assert(scenario.gameLogHtml === "", `${scenario.name}: game log was not cleared`);
  });

  assert(scenarios.normal.payload.size === 13, `normal size changed: ${scenarios.normal.payload.size}`);
  assert(scenarios.normal.payload.komi === 6.5, `normal komi changed: ${scenarios.normal.payload.komi}`);
  assert(scenarios.normal.payload.player_color === "W", `normal color changed: ${scenarios.normal.payload.player_color}`);
  assert(scenarios.normal.payload.level === "10k", `normal level changed: ${scenarios.normal.payload.level}`);
  assert(scenarios.normal.payload.ai_style === "attack", `normal style changed: ${scenarios.normal.payload.ai_style}`);
  assert(!scenarios.normal.payload.two_player && !scenarios.normal.payload.ai_observer, "normal flags changed");
  assert(!scenarios.normal.payload.rogue && !scenarios.normal.payload.ai_rogue && !scenarios.normal.payload.ultimate && !scenarios.normal.payload.challenge_beta, "normal mode enabled special flags");

  assert(scenarios.two.payload.size === 9, `two-player size changed: ${scenarios.two.payload.size}`);
  assert(scenarios.two.payload.handicap === 2, `two-player handicap changed: ${scenarios.two.payload.handicap}`);
  assert(scenarios.two.payload.player_color === "B", `two-player color should force black: ${scenarios.two.payload.player_color}`);
  assert(scenarios.two.payload.two_player === true, "two-player flag missing");
  assert(scenarios.two.twoPlayerMode === true, "two-player state did not sync");
  assert(!scenarios.two.payload.ai_observer && !scenarios.two.payload.rogue && !scenarios.two.payload.ultimate, "two-player special flags changed");

  assert(scenarios.watch.payload.ai_observer === true, "watch mode did not enable observer");
  assert(scenarios.watch.payload.player_color === "B", `watch mode should force black: ${scenarios.watch.payload.player_color}`);
  assert(scenarios.watch.payload.level === "5k", `watch level should follow black rank: ${scenarios.watch.payload.level}`);
  assert(scenarios.watch.payload.ai_level_black === "5k", `watch black level changed: ${scenarios.watch.payload.ai_level_black}`);
  assert(scenarios.watch.payload.ai_level_white === "a1d", `watch white level changed: ${scenarios.watch.payload.ai_level_white}`);
  assert(scenarios.watch.payload.ai_style_black === "territory", `watch black style changed: ${scenarios.watch.payload.ai_style_black}`);
  assert(scenarios.watch.payload.ai_style_white === "defense", `watch white style changed: ${scenarios.watch.payload.ai_style_white}`);

  assert(scenarios["rogue-solo"].payload.size === 19, `rogue solo size changed: ${scenarios["rogue-solo"].payload.size}`);
  assert(scenarios["rogue-solo"].payload.handicap === 0, `rogue solo handicap changed: ${scenarios["rogue-solo"].payload.handicap}`);
  assert(scenarios["rogue-solo"].payload.player_color === "W", `rogue solo color changed: ${scenarios["rogue-solo"].payload.player_color}`);
  assert(scenarios["rogue-solo"].payload.rogue === true, "rogue solo flag missing");
  assert(scenarios["rogue-solo"].payload.ai_rogue === false, "rogue solo should not enable ai_rogue");
  assert(scenarios["rogue-solo"].payload.ultimate === false, "rogue solo should not enable ultimate");

  assert(scenarios["rogue-dual"].payload.size === 19, `rogue dual size changed: ${scenarios["rogue-dual"].payload.size}`);
  assert(scenarios["rogue-dual"].payload.handicap === 0, `rogue dual handicap changed: ${scenarios["rogue-dual"].payload.handicap}`);
  assert(scenarios["rogue-dual"].payload.player_color === "B", `rogue dual color changed: ${scenarios["rogue-dual"].payload.player_color}`);
  assert(scenarios["rogue-dual"].payload.rogue === true, "rogue dual flag missing");
  assert(scenarios["rogue-dual"].payload.ai_rogue === true, "rogue dual ai_rogue flag missing");
  assert(scenarios["rogue-dual"].payload.ultimate === false, "rogue dual should not enable ultimate");
  assert(scenarios["rogue-dual"].timerMode === "byoyomi", `timer mode did not sync: ${scenarios["rogue-dual"].timerMode}`);
  assert(scenarios["rogue-dual"].mainTimeSetting === 180, `main time did not sync: ${scenarios["rogue-dual"].mainTimeSetting}`);
  assert(scenarios["rogue-dual"].byoPeriodsSetting === 5, `byoyomi periods did not sync: ${scenarios["rogue-dual"].byoPeriodsSetting}`);
  assert(scenarios["rogue-dual"].byoTimeSetting === 20, `byoyomi time did not sync: ${scenarios["rogue-dual"].byoTimeSetting}`);

  assert(scenarios["rogue-ultimate"].payload.size === 19, `ultimate size changed: ${scenarios["rogue-ultimate"].payload.size}`);
  assert(scenarios["rogue-ultimate"].payload.rogue === false, "ultimate variant should not enable rogue flag");
  assert(scenarios["rogue-ultimate"].payload.ai_rogue === false, "ultimate variant should not enable ai_rogue");
  assert(scenarios["rogue-ultimate"].payload.ultimate === true, "ultimate variant flag missing");

  assert(scenarios.challenge.payload.player_color === "W", `challenge should force white: ${scenarios.challenge.payload.player_color}`);
  assert(scenarios.challenge.payload.komi === 7.5, `challenge should force komi 7.5: ${scenarios.challenge.payload.komi}`);
  assert(scenarios.challenge.payload.rogue === true, "challenge should enable rogue");
  assert(scenarios.challenge.payload.ai_rogue === false, "challenge should disable ai_rogue");
  assert(scenarios.challenge.payload.ultimate === false, "challenge should disable ultimate");
  assert(scenarios.challenge.payload.challenge_beta === true, "challenge flag missing");
  assert(scenarios.challenge.payload.challenge_stage === 1, `challenge stage did not reset: ${scenarios.challenge.payload.challenge_stage}`);
  assert(Array.isArray(scenarios.challenge.payload.challenge_cards), "challenge cards payload missing");
  assert(scenarios.challenge.payload.challenge_limits?.undo === 3, `challenge limits did not reset: ${JSON.stringify(scenarios.challenge.payload.challenge_limits)}`);

  assert(errors.length === 0, `browser errors: ${errors.join("; ")}`);
  console.log(JSON.stringify({
    ok: true,
    scenarios: payloadState.scenarios.map(item => item.name),
    stagePreset: stageState.stagePreset,
  }, null, 2));
} finally {
  await browser.close();
}
