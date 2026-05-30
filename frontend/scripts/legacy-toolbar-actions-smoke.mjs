import { chromium } from "playwright";

const DEFAULT_URL = "http://127.0.0.1:8876/";
const urlArg = process.argv.find((arg) => arg.startsWith("--url="));
const targetUrl = withLanguageParam(
  urlArg ? urlArg.slice("--url=".length) : process.env.LEGACY_TOOLBAR_ACTIONS_URL || DEFAULT_URL,
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
    publicFns: [
      typeof window.setButtons,
      typeof window.handlePassAction,
      typeof window.handleUndoAction,
      typeof window.handleScoreAction,
      typeof window.handleResignAction,
    ],
  }));
  assert(publicState.publicFns.every(type => type === "function"), `toolbar globals missing: ${publicState.publicFns.join(", ")}`);

  await page.evaluate(() => {
    window.__toolbarSmoke = { payloads: [], logs: [], thinking: [], confirmMessages: [] };
    sendWS = window.sendWS = payload => { window.__toolbarSmoke.payloads.push(payload); };
    logI18n = window.logI18n = (...args) => { window.__toolbarSmoke.logs.push(args[0]); };
    const originalSetThinking = setThinking;
    setThinking = window.setThinking = value => {
      window.__toolbarSmoke.thinking.push(value);
      return originalSetThinking(value);
    };
    const board = Array.from({ length: 9 }, () => Array(9).fill(null));
    board[0][0] = "B";
    gameState = {
      size: 9,
      board,
      current_player: "B",
      captures: { B: 0, W: 0 },
      move_number: 1,
      game_over: false,
      rogue_undo_disabled: false,
      ultimate_quickthink_active: false,
      challenge_cards: [],
    };
    analysis = { winrate: 0.85, score: 3.5, top_moves: [], ownership: [], analysis_ready: true };
    analysisReady = true;
    activeRogueCard = null;
    showTerritory = true;
    twoPlayerMode = false;
    isMyTurn = true;
    myColor = "B";
    ultimateMode = false;
    ultimatePlayerCard = null;
    previousBoard = null;
    setButtons(true);
  });

  const activeButtons = await page.evaluate(() => ({
    pass: !document.querySelector("#btn-pass")?.disabled,
    undo: !document.querySelector("#btn-undo")?.disabled,
    score: !document.querySelector("#btn-score")?.disabled,
    resign: !document.querySelector("#btn-resign")?.disabled,
    newDisabled: document.querySelector("#btn-new")?.disabled || false,
    newText: document.querySelector("#btn-new")?.textContent || "",
    newOpacity: document.querySelector("#btn-new")?.style.opacity || "",
    newCursor: document.querySelector("#btn-new")?.style.cursor || "",
    setupDisabled: document.querySelector("#btn-setup")?.disabled || false,
    setupOpacity: document.querySelector("#btn-setup")?.style.opacity || "",
    setupCursor: document.querySelector("#btn-setup")?.style.cursor || "",
  }));
  assert(activeButtons.pass && activeButtons.undo && activeButtons.score && activeButtons.resign, `setButtons(true) did not enable toolbar: ${JSON.stringify(activeButtons)}`);
  assert(activeButtons.newDisabled && activeButtons.setupDisabled, `setButtons(true) did not disable start controls: ${JSON.stringify(activeButtons)}`);
  assert(activeButtons.newText.includes("对局进行中"), `setButtons(true) did not update start text: ${JSON.stringify(activeButtons)}`);
  assert(activeButtons.newOpacity === "0.5" && activeButtons.newCursor === "not-allowed", `setButtons(true) did not lock start button style: ${JSON.stringify(activeButtons)}`);
  assert(activeButtons.setupOpacity === "0.5" && activeButtons.setupCursor === "not-allowed", `setButtons(true) did not lock setup button style: ${JSON.stringify(activeButtons)}`);

  const whiteDominantScoreState = await page.evaluate(() => {
    analysis.winrate = 0.15;
    setButtons(true);
    const state = {
      scoreDisabled: document.querySelector("#btn-score")?.disabled || false,
      scoreTitle: document.querySelector("#btn-score")?.title || "",
    };
    analysis.winrate = 0.85;
    setButtons(true);
    return state;
  });
  assert(!whiteDominantScoreState.scoreDisabled, `white-dominant score should be enabled: ${JSON.stringify(whiteDominantScoreState)}`);
  assert(whiteDominantScoreState.scoreTitle.includes("计算胜负") || whiteDominantScoreState.scoreTitle.includes("Score"), `white-dominant score title changed: ${whiteDominantScoreState.scoreTitle}`);

  const inactiveButtonsState = await page.evaluate(() => {
    setButtons(false);
    const state = {
      passDisabled: document.querySelector("#btn-pass")?.disabled || false,
      undoDisabled: document.querySelector("#btn-undo")?.disabled || false,
      scoreDisabled: document.querySelector("#btn-score")?.disabled || false,
      resignDisabled: document.querySelector("#btn-resign")?.disabled || false,
      newDisabled: document.querySelector("#btn-new")?.disabled || false,
      newText: document.querySelector("#btn-new")?.textContent || "",
      newOpacity: document.querySelector("#btn-new")?.style.opacity || "",
      newCursor: document.querySelector("#btn-new")?.style.cursor || "",
      setupDisabled: document.querySelector("#btn-setup")?.disabled || false,
      setupOpacity: document.querySelector("#btn-setup")?.style.opacity || "",
      setupCursor: document.querySelector("#btn-setup")?.style.cursor || "",
    };
    setButtons(true);
    return state;
  });
  assert(inactiveButtonsState.passDisabled && inactiveButtonsState.undoDisabled && inactiveButtonsState.scoreDisabled && inactiveButtonsState.resignDisabled, `setButtons(false) did not disable active toolbar: ${JSON.stringify(inactiveButtonsState)}`);
  assert(!inactiveButtonsState.newDisabled && inactiveButtonsState.newText.includes("确认开始"), `setButtons(false) did not reset start button: ${JSON.stringify(inactiveButtonsState)}`);
  assert(inactiveButtonsState.newOpacity === "" && inactiveButtonsState.newCursor === "", `setButtons(false) did not clear start button lock styles: ${JSON.stringify(inactiveButtonsState)}`);
  assert(!inactiveButtonsState.setupDisabled && inactiveButtonsState.setupOpacity === "" && inactiveButtonsState.setupCursor === "", `setButtons(false) did not clear setup button lock styles: ${JSON.stringify(inactiveButtonsState)}`);

  await page.locator("#btn-pass").click();
  const passState = await page.evaluate(() => ({
    payloads: window.__toolbarSmoke.payloads,
    isMyTurn,
    previousBoardCopied: previousBoard?.[0]?.[0] === "B" && previousBoard !== gameState.board,
    thinking: window.__toolbarSmoke.thinking,
    logs: window.__toolbarSmoke.logs,
  }));
  assert(passState.payloads.at(-1)?.action === "pass", `pass did not send payload: ${JSON.stringify(passState.payloads)}`);
  assert(passState.isMyTurn === false, "pass did not end the local player turn");
  assert(passState.previousBoardCopied, "pass did not snapshot previous board");
  assert(passState.thinking.at(-1) === true, `pass did not set thinking: ${JSON.stringify(passState.thinking)}`);
  assert(passState.logs.some(text => String(text).includes("虚手")), "pass did not log feedback");

  const blockedPassState = await page.evaluate(() => {
    const beforePayloadCount = window.__toolbarSmoke.payloads.length;
    isMyTurn = false;
    handlePassAction();
    return {
      payloadCount: window.__toolbarSmoke.payloads.length,
      beforePayloadCount,
    };
  });
  assert(blockedPassState.payloadCount === blockedPassState.beforePayloadCount, "pass should no-op when it is not my turn");

  const quickThinkPassState = await page.evaluate(() => {
    const beforePayloadCount = window.__toolbarSmoke.payloads.length;
    isMyTurn = true;
    ultimateMode = true;
    ultimatePlayerCard = "quickthink";
    gameState.ultimate_quickthink_active = true;
    handlePassAction();
    ultimateMode = false;
    ultimatePlayerCard = null;
    gameState.ultimate_quickthink_active = false;
    return {
      payload: window.__toolbarSmoke.payloads[beforePayloadCount] || null,
      isMyTurn,
      thinking: window.__toolbarSmoke.thinking,
      logs: window.__toolbarSmoke.logs,
    };
  });
  assert(quickThinkPassState.payload?.action === "ultimate_quickthink_end", `quickthink pass payload changed: ${JSON.stringify(quickThinkPassState.payload)}`);
  assert(quickThinkPassState.isMyTurn === false, "quickthink pass did not end local turn");
  assert(quickThinkPassState.thinking.at(-1) === true, "quickthink pass did not set thinking");
  assert(quickThinkPassState.logs.some(text => String(text).includes("快速思考")), "quickthink pass did not log feedback");

  await page.evaluate(() => {
    isMyTurn = true;
    gameState.rogue_undo_disabled = false;
    setButtons(true);
  });
  await page.locator("#btn-undo").click();
  const undoState = await page.evaluate(() => ({
    payload: window.__toolbarSmoke.payloads.at(-1),
    thinking: window.__toolbarSmoke.thinking,
    previousBoardCopied: previousBoard?.[0]?.[0] === "B" && previousBoard !== gameState.board,
    logs: window.__toolbarSmoke.logs,
  }));
  assert(undoState.payload?.action === "undo", `undo did not send payload: ${JSON.stringify(undoState.payload)}`);
  assert(undoState.thinking.at(-1) === false, "undo did not clear thinking");
  assert(undoState.previousBoardCopied, "undo did not snapshot previous board");
  assert(undoState.logs.some(text => String(text).includes("悔棋")), "undo did not log feedback");

  const undoDisabledState = await page.evaluate(() => {
    const beforePayloadCount = window.__toolbarSmoke.payloads.length;
    gameState.rogue_undo_disabled = true;
    setButtons(true);
    handleUndoAction();
    return {
      undoDisabled: document.querySelector("#btn-undo")?.disabled || false,
      title: document.querySelector("#btn-undo")?.title || "",
      payloadCount: window.__toolbarSmoke.payloads.length,
      beforePayloadCount,
      logs: window.__toolbarSmoke.logs,
    };
  });
  assert(undoDisabledState.undoDisabled, "rogue disabled undo did not disable the button");
  assert(undoDisabledState.title.includes("禁用") || undoDisabledState.title.includes("disabled"), `undo disabled title changed: ${undoDisabledState.title}`);
  assert(undoDisabledState.payloadCount === undoDisabledState.beforePayloadCount, "disabled undo should not send payload");
  assert(undoDisabledState.logs.some(text => String(text).includes("禁用")), "disabled undo did not log feedback");

  const lowScoreState = await page.evaluate(() => {
    const beforePayloadCount = window.__toolbarSmoke.payloads.length;
    analysis.winrate = 0.55;
    handleScoreAction();
    return {
      payloadCount: window.__toolbarSmoke.payloads.length,
      beforePayloadCount,
      confirmOpen: document.querySelector("#confirm-modal")?.classList.contains("show") || false,
      logs: window.__toolbarSmoke.logs,
    };
  });
  assert(lowScoreState.payloadCount === lowScoreState.beforePayloadCount, "low winrate scoring should not send payload");
  assert(!lowScoreState.confirmOpen, "low winrate scoring should not open confirm modal");
  assert(lowScoreState.logs.some(text => String(text).includes("胜率未达80")), "low winrate scoring did not log feedback");

  await page.evaluate(() => {
    analysis.winrate = 0.85;
    analysisReady = true;
    showTerritory = true;
    activeRogueCard = null;
    gameState.rogue_undo_disabled = false;
    setButtons(true);
  });
  await page.locator("#btn-score").click();
  const scoreConfirmState = await page.evaluate(() => ({
    confirmOpen: document.querySelector("#confirm-modal")?.classList.contains("show") || false,
    message: document.querySelector("#confirm-msg")?.textContent || "",
  }));
  assert(scoreConfirmState.confirmOpen, "score did not open confirmation");
  assert(scoreConfirmState.message.includes("形势") || scoreConfirmState.message.includes("scoring"), `score confirmation text changed: ${scoreConfirmState.message}`);
  await page.locator("#btn-confirm-ok").click();
  const scorePayloadState = await page.evaluate(() => ({
    payload: window.__toolbarSmoke.payloads.at(-1),
    confirmOpen: document.querySelector("#confirm-modal")?.classList.contains("show") || false,
    logs: window.__toolbarSmoke.logs,
  }));
  assert(scorePayloadState.payload?.action === "score", `score did not send payload: ${JSON.stringify(scorePayloadState.payload)}`);
  assert(!scorePayloadState.confirmOpen, "score confirmation did not close after OK");
  assert(scorePayloadState.logs.some(text => String(text).includes("终局计分")), "score did not log feedback");

  await page.locator("#btn-resign").click();
  const resignConfirmState = await page.evaluate(() => ({
    confirmOpen: document.querySelector("#confirm-modal")?.classList.contains("show") || false,
    message: document.querySelector("#confirm-msg")?.textContent || "",
  }));
  assert(resignConfirmState.confirmOpen, "resign did not open confirmation");
  assert(resignConfirmState.message.includes("认输") || resignConfirmState.message.includes("resign"), `resign confirmation text changed: ${resignConfirmState.message}`);
  await page.locator("#btn-confirm-ok").click();
  const resignPayloadState = await page.evaluate(() => ({
    payload: window.__toolbarSmoke.payloads.at(-1),
    passDisabled: document.querySelector("#btn-pass")?.disabled || false,
    undoDisabled: document.querySelector("#btn-undo")?.disabled || false,
    resignDisabled: document.querySelector("#btn-resign")?.disabled || false,
    newDisabled: document.querySelector("#btn-new")?.disabled || false,
    setupDisabled: document.querySelector("#btn-setup")?.disabled || false,
    logs: window.__toolbarSmoke.logs,
  }));
  assert(resignPayloadState.payload?.action === "resign", `resign did not send payload: ${JSON.stringify(resignPayloadState.payload)}`);
  assert(resignPayloadState.passDisabled && resignPayloadState.undoDisabled && resignPayloadState.resignDisabled, "resign did not disable active toolbar buttons");
  assert(!resignPayloadState.newDisabled && !resignPayloadState.setupDisabled, "resign did not re-enable start controls");
  assert(resignPayloadState.logs.some(text => String(text).includes("认输")), "resign did not log feedback");

  assert(errors.length === 0, `browser errors: ${errors.join("; ")}`);
  console.log(JSON.stringify({
    ok: true,
    payloads: await page.evaluate(() => window.__toolbarSmoke.payloads.map(payload => payload.action)),
  }, null, 2));
} finally {
  await browser.close();
}
