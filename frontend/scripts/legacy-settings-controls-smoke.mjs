import { chromium } from "playwright";

const DEFAULT_URL = "http://127.0.0.1:8876/";
const urlArg = process.argv.find((arg) => arg.startsWith("--url="));
const targetUrl = withLanguageParam(
  urlArg ? urlArg.slice("--url=".length) : process.env.LEGACY_SETTINGS_CONTROLS_URL || DEFAULT_URL,
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
  await page.locator("#btn-settings").click();
  await page.locator("#settings-drawer.open").waitFor({ state: "visible", timeout: 5000 });

  const publicState = await page.evaluate(() => ({
    publicFns: [
      typeof window.refreshHintVisibility,
      typeof window.isHintLockedByCard,
      typeof window.openCardEditorPanel,
      typeof window.closeCardEditorPanel,
      typeof window.toggleTerritory,
    ],
  }));
  assert(publicState.publicFns.every(type => type === "function"), `settings control globals missing: ${publicState.publicFns.join(", ")}`);

  await page.locator("#btn-card-editor").click();
  const cardEditorOpen = await page.evaluate(() => ({
    shown: document.querySelector("#card-editor-modal")?.classList.contains("show") || false,
    src: document.querySelector("#card-editor-frame")?.src || "",
  }));
  assert(cardEditorOpen.shown, "card editor modal did not open");
  assert(cardEditorOpen.src.includes("/card-editor") && cardEditorOpen.src.includes("embed=1"), `card editor iframe src changed: ${cardEditorOpen.src}`);
  assert(cardEditorOpen.src.includes("ts="), `card editor iframe cachebuster missing: ${cardEditorOpen.src}`);

  await page.locator("#card-editor-modal-close").click();
  const cardEditorClosed = await page.evaluate(() => ({
    shown: document.querySelector("#card-editor-modal")?.classList.contains("show") || false,
    src: document.querySelector("#card-editor-frame")?.getAttribute("src") || "",
  }));
  assert(!cardEditorClosed.shown, "card editor modal did not close");
  assert(cardEditorClosed.src === "about:blank", `card editor iframe did not reset: ${cardEditorClosed.src}`);

  await page.evaluate(() => {
    window.__settingsSmoke = { payloads: [], renderCalls: 0, winrateCalls: 0, audioCalls: 0, logs: [] };
    const originalRender = render;
    const originalUpdateWinRate = updateWinRate;
    const originalLogI18n = logI18n;
    sendWS = window.sendWS = payload => { window.__settingsSmoke.payloads.push(payload); };
    render = window.render = (...args) => {
      window.__settingsSmoke.renderCalls += 1;
      return originalRender.apply(this, args);
    };
    updateWinRate = window.updateWinRate = (...args) => {
      window.__settingsSmoke.winrateCalls += 1;
      return originalUpdateWinRate.apply(this, args);
    };
    logI18n = window.logI18n = (...args) => {
      window.__settingsSmoke.logs.push(args[0]);
      return originalLogI18n.apply(this, args);
    };
    getAudioCtx = window.getAudioCtx = () => {
      window.__settingsSmoke.audioCalls += 1;
      return {};
    };
    gameState = {
      size: 9,
      board: Array.from({ length: 9 }, () => Array(9).fill(null)),
      current_player: "B",
      captures: { B: 0, W: 0 },
      move_number: 1,
      game_over: false,
      challenge_cards: [],
    };
    analysis = { winrate: 0.66, score: 2.5, top_moves: [], ownership: [], analysis_ready: true };
    analysisReady = true;
    activeRogueCard = null;
    showHints = false;
    showTerritory = true;
    showMoveNumbers = false;
    soundEnabled = true;
    document.querySelector("#hint-toggle").className = "toggle";
    document.querySelector("#territory-toggle").className = "toggle on";
    document.querySelector("#move-number-toggle").className = "toggle";
    setSoundToggleVisual();
    setTerritoryToggleVisual();
  });

  await page.locator("#hint-toggle").click();
  const hintState = await page.evaluate(() => ({
    showHints,
    className: document.querySelector("#hint-toggle")?.className || "",
    requestHint: window.__settingsSmoke.payloads.some(payload => payload.action === "request_hint"),
    renderCalls: window.__settingsSmoke.renderCalls,
    winrateCalls: window.__settingsSmoke.winrateCalls,
  }));
  assert(hintState.showHints, "hint toggle did not enable hints");
  assert(hintState.className.includes("on"), `hint toggle class did not update: ${hintState.className}`);
  assert(hintState.requestHint, "hint toggle did not request a hint while gameState exists");
  assert(hintState.renderCalls >= 1, "hint toggle did not render");
  assert(hintState.winrateCalls >= 2, `hint toggle did not preserve winrate refresh calls: ${hintState.winrateCalls}`);

  const lockedState = await page.evaluate(() => {
    const beforeRender = window.__settingsSmoke.renderCalls;
    activeRogueCard = "quickthink";
    showHints = true;
    document.querySelector("#hint-toggle").className = "toggle on";
    document.querySelector("#hint-toggle").click();
    return {
      showHints,
      className: document.querySelector("#hint-toggle")?.className || "",
      rendered: window.__settingsSmoke.renderCalls > beforeRender,
      logs: window.__settingsSmoke.logs,
    };
  });
  assert(!lockedState.showHints, "quickthink lock did not force hints off");
  assert(!lockedState.className.includes("on"), `quickthink lock left hint toggle on: ${lockedState.className}`);
  assert(lockedState.rendered, "quickthink lock did not render");
  assert(lockedState.logs.some(text => String(text).includes("快速思考")), "quickthink lock did not log feedback");

  const challengeLockedState = await page.evaluate(() => {
    const beforeRender = window.__settingsSmoke.renderCalls;
    activeRogueCard = null;
    gameState.challenge_cards = ["quickthink"];
    showHints = true;
    document.querySelector("#hint-toggle").className = "toggle on";
    document.querySelector("#hint-toggle").click();
    return {
      locked: isHintLockedByCard(),
      showHints,
      className: document.querySelector("#hint-toggle")?.className || "",
      rendered: window.__settingsSmoke.renderCalls > beforeRender,
      logs: window.__settingsSmoke.logs,
    };
  });
  assert(challengeLockedState.locked, "challenge quickthink card did not lock hints");
  assert(!challengeLockedState.showHints, "challenge quickthink lock did not force hints off");
  assert(!challengeLockedState.className.includes("on"), `challenge quickthink lock left hint toggle on: ${challengeLockedState.className}`);
  assert(challengeLockedState.rendered, "challenge quickthink lock did not render");
  assert(challengeLockedState.logs.some(text => String(text).includes("快速思考")), "challenge quickthink lock did not log feedback");

  const territoryState = await page.evaluate(() => {
    activeRogueCard = null;
    gameState.challenge_cards = [];
    const beforeRender = window.__settingsSmoke.renderCalls;
    toggleTerritory();
    return {
      showTerritory,
      className: document.querySelector("#territory-toggle")?.className || "",
      icon: document.querySelector("#btn-territory-toggle .toolbar-icon")?.dataset.icon || "",
      rendered: window.__settingsSmoke.renderCalls > beforeRender,
    };
  });
  assert(!territoryState.showTerritory, "territory toggle did not disable territory");
  assert(!territoryState.className.includes("on"), `territory toggle class did not update: ${territoryState.className}`);
  assert(territoryState.icon === "territory-off", `territory toolbar icon did not update: ${territoryState.icon}`);
  assert(territoryState.rendered, "territory toggle did not render");

  await page.locator("#move-number-toggle").click();
  const moveNumberState = await page.evaluate(() => ({
    showMoveNumbers,
    className: document.querySelector("#move-number-toggle")?.className || "",
  }));
  assert(moveNumberState.showMoveNumbers, "move number toggle did not enable move numbers");
  assert(moveNumberState.className.includes("on"), `move number toggle class did not update: ${moveNumberState.className}`);

  const selectState = await page.evaluate(() => {
    const beforePayloadCount = window.__settingsSmoke.payloads.length;
    document.querySelector("#sel-level").value = "8k";
    document.querySelector("#sel-level").dispatchEvent(new Event("change", { bubbles: true }));
    document.querySelector("#sel-komi").value = "6.5";
    syncWoodSelect(document.querySelector("#sel-komi"));
    document.querySelector("#sel-handicap").value = "2";
    document.querySelector("#sel-handicap").dispatchEvent(new Event("change", { bubbles: true }));
    return {
      levelPayload: window.__settingsSmoke.payloads.slice(beforePayloadCount).find(payload => payload.action === "set_level") || null,
      komi: document.querySelector("#sel-komi")?.value || "",
    };
  });
  assert(selectState.levelPayload?.level === "8k", `level change payload changed: ${JSON.stringify(selectState.levelPayload)}`);
  assert(selectState.komi === "0", `handicap change did not force zero komi: ${selectState.komi}`);

  const soundState = await page.evaluate(() => {
    document.querySelector("#sound-toggle").click();
    const afterOff = {
      soundEnabled,
      icon: document.querySelector("#sound-toggle .toolbar-icon")?.dataset.icon || "",
      muted: document.querySelector("#sound-toggle")?.classList.contains("muted") || false,
    };
    document.querySelector("#sound-toggle").click();
    const afterToolbarOn = {
      soundEnabled,
      icon: document.querySelector("#sound-toggle .toolbar-icon")?.dataset.icon || "",
      muted: document.querySelector("#sound-toggle")?.classList.contains("muted") || false,
      audioCalls: window.__settingsSmoke.audioCalls,
    };
    const settingsToggle = document.querySelector("#sound-settings-toggle");
    let afterSettingsOff = null;
    if (settingsToggle) {
      settingsToggle.click();
      afterSettingsOff = {
        soundEnabled,
        icon: document.querySelector("#sound-toggle .toolbar-icon")?.dataset.icon || "",
        muted: document.querySelector("#sound-toggle")?.classList.contains("muted") || false,
        audioCalls: window.__settingsSmoke.audioCalls,
      };
      settingsToggle.click();
    }
    return {
      afterOff,
      afterToolbarOn,
      afterSettingsOff,
      settingsTogglePresent: Boolean(settingsToggle),
      soundEnabled,
      icon: document.querySelector("#sound-toggle .toolbar-icon")?.dataset.icon || "",
      muted: document.querySelector("#sound-toggle")?.classList.contains("muted") || false,
      audioCalls: window.__settingsSmoke.audioCalls,
    };
  });
  assert(!soundState.afterOff.soundEnabled, "sound toggle did not disable sound");
  assert(soundState.afterOff.icon === "sound-off", `sound icon did not switch off: ${soundState.afterOff.icon}`);
  assert(soundState.afterOff.muted, "sound button did not show muted state");
  assert(soundState.afterToolbarOn.soundEnabled, "toolbar sound toggle did not re-enable sound");
  assert(soundState.afterToolbarOn.audioCalls === 1, `toolbar sound toggle did not initialize audio once: ${soundState.afterToolbarOn.audioCalls}`);
  if (soundState.settingsTogglePresent) {
    assert(!soundState.afterSettingsOff.soundEnabled, "settings sound toggle did not disable sound");
    assert(soundState.afterSettingsOff.icon === "sound-off", `settings sound toggle did not switch off icon: ${soundState.afterSettingsOff.icon}`);
    assert(soundState.afterSettingsOff.audioCalls === 1, `settings sound off should not initialize audio: ${soundState.afterSettingsOff.audioCalls}`);
  }
  assert(soundState.soundEnabled, "sound toggle did not re-enable sound");
  assert(soundState.icon === "sound-on", `sound icon did not switch on: ${soundState.icon}`);
  assert(!soundState.muted, "sound button stayed muted after re-enable");
  assert(soundState.audioCalls === (soundState.settingsTogglePresent ? 2 : 1), `sound toggles did not initialize audio on each enable: ${soundState.audioCalls}`);

  assert(errors.length === 0, `browser errors: ${errors.join("; ")}`);
  console.log(JSON.stringify({
    ok: true,
    payloads: await page.evaluate(() => window.__settingsSmoke.payloads.map(payload => payload.action)),
  }, null, 2));
} finally {
  await browser.close();
}
