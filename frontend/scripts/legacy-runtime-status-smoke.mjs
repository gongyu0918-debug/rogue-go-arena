import { chromium } from "playwright";

const DEFAULT_URL = "http://127.0.0.1:8876/";
const urlArg = process.argv.find((arg) => arg.startsWith("--url="));
const targetUrl = withLanguageParam(
  urlArg ? urlArg.slice("--url=".length) : process.env.LEGACY_RUNTIME_STATUS_URL || DEFAULT_URL,
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
    const emptyBoard = (size) => Array.from({ length: size }, () => Array(size).fill(0));
    const sampleCanvas = (selector) => {
      const canvas = document.querySelector(selector);
      const ctx = canvas?.getContext("2d");
      if (!ctx || canvas.width < 10 || canvas.height < 10) return false;
      const data = ctx.getImageData(0, 0, canvas.width, canvas.height).data;
      for (let i = 3; i < data.length; i += 97) {
        if (data[i] !== 0 && (data[i - 1] !== 0 || data[i - 2] !== 0 || data[i - 3] !== 0)) return true;
      }
      return false;
    };

    const publicFns = [
      typeof window.resetWinrateHistory,
      typeof window.pushWinratePoint,
      typeof window.drawWinrateCurve,
      typeof window.setThinking,
      typeof window.showOverlay,
      typeof window.closeOverlay,
      typeof window.reasonText,
      typeof window.formatScoreDisplay,
      typeof window.updateUI,
      typeof window.updateWinRate,
    ];
    const privateFns = [
      typeof WINRATE_CURVE_PADDING,
      typeof clampRange,
      typeof getWinrateCurveLayout,
      typeof resizeCanvasForDpr,
      typeof drawWinrateHistoryLine,
      typeof overlayKindForTitle,
      typeof scoreWinnerLabel,
      typeof scoreUnitText,
      typeof winrateUiReady,
      typeof setWinratePendingState,
      typeof syncScoreButtonForWinrate,
    ];

    setThinking(true);
    const thinkingOn = document.querySelector("#thinking-indicator")?.className || "";
    const thinkingPanelOn = document.querySelector("#thinking-indicator-panel")?.className || "";
    setThinking(false);
    const thinkingOff = document.querySelector("#thinking-indicator")?.className || "";

    showOverlay("胜利", "runtime status smoke", "黑棋", "B+R");
    const overlayOpen = {
      cls: document.querySelector("#overlay")?.className || "",
      title: document.querySelector("#overlay-title")?.textContent || "",
      msg: document.querySelector("#overlay-msg")?.textContent || "",
      winner: document.querySelector("#overlay-winner")?.textContent || "",
      score: document.querySelector("#overlay-score")?.textContent || "",
      sparks: document.querySelectorAll("#overlay-sparks .overlay-spark").length,
    };
    closeOverlay();
    const overlayClosed = document.querySelector("#overlay")?.className || "";
    showOverlay("平局", "runtime draw smoke", "平局", "0");
    const drawOverlayClass = document.querySelector("#overlay")?.className || "";
    closeOverlay();
    showOverlay("失败", "runtime defeat smoke", "白棋", "W+R");
    const defeatOverlayClass = document.querySelector("#overlay")?.className || "";
    closeOverlay();

    await ensureLocale("en");
    await ensureLocale("ja");
    await ensureLocale("ko");
    const previousLang = currentLang;
    currentLang = "zh";
    const scoreZh = formatScoreDisplay("B+3.5", 7.5);
    const reasonZh = reasonText("timeout");
    currentLang = "en";
    const scoreEn = formatScoreDisplay("W+R", 6.5);
    const reasonEn = reasonText("score");
    currentLang = "ja";
    const scoreJa = formatScoreDisplay("B+2.5", 7.5);
    currentLang = "ko";
    const scoreKo = formatScoreDisplay("W+1.5", 6.5);
    currentLang = previousLang;

    gameState = {
      size: 9,
      board: emptyBoard(9),
      captures: { B: 2, W: 1 },
      current_player: "W",
      player_color: "B",
      ai_color: "W",
      level: "10k",
      move_number: 8,
      game_over: false,
      two_player: false,
      ai_observer: false,
    };
    myColor = "B";
    aiColor = "W";
    twoPlayerMode = false;
    isMyTurn = false;
    cardTurnRemaining = 0;
    updateUI();
    const soloInfo = {
      color: document.querySelector("#info-my-color")?.textContent || "",
      player: document.querySelector("#info-player")?.textContent || "",
      move: document.querySelector("#info-move")?.textContent || "",
      capB: document.querySelector("#info-cap-b")?.textContent || "",
      capW: document.querySelector("#info-cap-w")?.textContent || "",
      level: document.querySelector("#info-level")?.textContent || "",
      clientRun: document.querySelector("#client-run-value")?.textContent || "",
      hudMove: document.querySelector("#hud-move")?.textContent || "",
      hudTurn: document.querySelector("#hud-turn")?.textContent || "",
      clientMode: document.querySelector("#client-mode-value")?.textContent || "",
    };

    twoPlayerMode = true;
    gameState.current_player = "B";
    updateUI();
    const twoPlayerInfo = {
      color: document.querySelector("#info-my-color")?.textContent || "",
      player: document.querySelector("#info-player")?.textContent || "",
      level: document.querySelector("#info-level")?.textContent || "",
      hudTurn: document.querySelector("#hud-turn")?.textContent || "",
      clientMode: document.querySelector("#client-mode-value")?.textContent || "",
    };

    twoPlayerMode = false;
    gameState.ai_observer = true;
    gameState.ai_level_black = "9k";
    gameState.ai_level_white = "8k";
    updateUI();
    const observerLevel = document.querySelector("#info-level")?.textContent || "";

    const originalDrawWinrateCurve = window.drawWinrateCurve;
    let monkeypatchDrawCalls = 0;
    window.drawWinrateCurve = () => { monkeypatchDrawCalls += 1; };
    resetWinrateHistory();
    gameState.move_number = 7;
    pushWinratePoint(0.55, 0.5);
    window.drawWinrateCurve = originalDrawWinrateCurve;
    const monkeypatchState = {
      drawCalls: monkeypatchDrawCalls,
      count: winrateHistory.length,
    };

    resetWinrateHistory();
    const emptyCurve = sampleCanvas("#winrate-curve");
    gameState.move_number = 9;
    pushWinratePoint(0.82, 3.5);
    pushWinratePoint(0.82, 3.51);
    gameState.move_number = 10;
    pushWinratePoint(0.64, -1.5);
    const curveState = {
      count: winrateHistory.length,
      nonblank: sampleCanvas("#winrate-curve"),
    };

    showTerritory = true;
    activeRogueCard = null;
    gameState.game_over = false;
    analysisReady = false;
    updateWinRate(0.85);
    const pendingState = {
      blackWidth: document.querySelector("#wr-black")?.style.width || "",
      whiteWidth: document.querySelector("#wr-white")?.style.width || "",
      blackLabel: document.querySelector("#wr-black-label")?.textContent || "",
      scoreDisabled: document.querySelector("#btn-score")?.disabled || false,
    };
    analysisReady = true;
    updateWinRate(0.85);
    const readyState = {
      blackWidth: document.querySelector("#wr-black")?.style.width || "",
      whiteWidth: document.querySelector("#wr-white")?.style.width || "",
      blackLabel: document.querySelector("#wr-black-label")?.textContent || "",
      whiteLabel: document.querySelector("#wr-white-label")?.textContent || "",
      scoreDisabled: document.querySelector("#btn-score")?.disabled || false,
      scoreTitle: document.querySelector("#btn-score")?.title || "",
    };

    updateWinRate(0.6);
    const lowReadyState = {
      blackWidth: document.querySelector("#wr-black")?.style.width || "",
      whiteWidth: document.querySelector("#wr-white")?.style.width || "",
      blackLabel: document.querySelector("#wr-black-label")?.textContent || "",
      whiteLabel: document.querySelector("#wr-white-label")?.textContent || "",
      scoreDisabled: document.querySelector("#btn-score")?.disabled || false,
      scoreTitle: document.querySelector("#btn-score")?.title || "",
    };

    activeRogueCard = "quickthink";
    updateWinRate(0.85);
    const lockedState = {
      wrapClass: document.querySelector("#winrate-bar-wrap")?.className || "",
      blackLabel: document.querySelector("#wr-black-label")?.textContent || "",
      scoreDisabled: document.querySelector("#btn-score")?.disabled || false,
    };

    return {
      publicFns,
      privateFns,
      thinkingOn,
      thinkingPanelOn,
      thinkingOff,
      overlayOpen,
      overlayClosed,
      drawOverlayClass,
      defeatOverlayClass,
      scoreZh,
      reasonZh,
      scoreEn,
      reasonEn,
      scoreJa,
      scoreKo,
      soloInfo,
      twoPlayerInfo,
      observerLevel,
      monkeypatchState,
      emptyCurve,
      curveState,
      pendingState,
      readyState,
      lowReadyState,
      lockedState,
    };
  });

  assert(state.publicFns.every(type => type === "function"), `runtime status globals missing: ${state.publicFns.join(", ")}`);
  assert(state.privateFns.every(type => type === "undefined"), `runtime status private helpers leaked globally: ${state.privateFns.join(", ")}`);
  assert(state.thinkingOn === "show" && state.thinkingPanelOn === "show", "setThinking(true) did not show indicators");
  assert(state.thinkingOff === "", `setThinking(false) did not clear indicator: ${state.thinkingOff}`);
  assert(state.overlayOpen.cls.includes("show") && state.overlayOpen.cls.includes("victory"), `overlay did not open as victory: ${state.overlayOpen.cls}`);
  assert(state.overlayOpen.title === "胜利", `overlay title changed: ${state.overlayOpen.title}`);
  assert(state.overlayOpen.msg === "runtime status smoke", `overlay message changed: ${state.overlayOpen.msg}`);
  assert(state.overlayOpen.winner === "黑棋", `overlay winner changed: ${state.overlayOpen.winner}`);
  assert(state.overlayOpen.score === "B+R", `overlay score changed: ${state.overlayOpen.score}`);
  assert(state.overlayOpen.sparks > 0, "overlay sparks did not spawn");
  assert(state.overlayClosed === "", `closeOverlay did not clear class: ${state.overlayClosed}`);
  assert(state.drawOverlayClass.includes("show") && state.drawOverlayClass.includes("draw"), `draw overlay kind changed: ${state.drawOverlayClass}`);
  assert(state.defeatOverlayClass.includes("show") && state.defeatOverlayClass.includes("defeat"), `defeat overlay kind changed: ${state.defeatOverlayClass}`);
  assert(state.scoreZh === "黑胜3.5子", `Chinese score formatting changed: ${state.scoreZh}`);
  assert(state.reasonZh === "超时", `Chinese reason text changed: ${state.reasonZh}`);
  assert(state.scoreEn === "White +R points", `English score formatting changed: ${state.scoreEn}`);
  assert(state.reasonEn === "Scoring", `English reason text changed: ${state.reasonEn}`);
  assert(state.scoreJa === "黒2.5子勝ち", `Japanese score formatting changed: ${state.scoreJa}`);
  assert(state.scoreKo === "백 1.5집 승", `Korean score formatting changed: ${state.scoreKo}`);
  assert(state.soloInfo.color.includes("黑棋"), `solo color text changed: ${state.soloInfo.color}`);
  assert(state.soloInfo.player.includes("白（AI）"), `solo player text changed: ${state.soloInfo.player}`);
  assert(state.soloInfo.move === "8", `move info changed: ${state.soloInfo.move}`);
  assert(state.soloInfo.capB === "2" && state.soloInfo.capW === "1", `capture info changed: ${JSON.stringify(state.soloInfo)}`);
  assert(state.soloInfo.level.includes("10级"), `rank label changed: ${state.soloInfo.level}`);
  assert(state.soloInfo.clientRun.includes("第8手") && state.soloInfo.clientRun.includes("AI 思考"), `client run summary changed: ${state.soloInfo.clientRun}`);
  assert(state.soloInfo.hudMove === "手数 8", `HUD move changed: ${state.soloInfo.hudMove}`);
  assert(state.soloInfo.hudTurn.includes("AI"), `HUD turn changed: ${state.soloInfo.hudTurn}`);
  assert(state.soloInfo.clientMode.includes("对局"), `client mode changed: ${state.soloInfo.clientMode}`);
  assert(state.twoPlayerInfo.color.includes("双方"), `two-player color text changed: ${state.twoPlayerInfo.color}`);
  assert(state.twoPlayerInfo.player.includes("黑棋落子"), `two-player player text changed: ${state.twoPlayerInfo.player}`);
  assert(state.twoPlayerInfo.level.includes("双人"), `two-player level text changed: ${state.twoPlayerInfo.level}`);
  assert(state.twoPlayerInfo.hudTurn.includes("黑棋落子"), `two-player HUD turn changed: ${state.twoPlayerInfo.hudTurn}`);
  assert(state.twoPlayerInfo.clientMode.includes("双人"), `two-player client mode changed: ${state.twoPlayerInfo.clientMode}`);
  assert(state.observerLevel.includes("9级") && state.observerLevel.includes("8级"), `observer rank text changed: ${state.observerLevel}`);
  assert(state.monkeypatchState.drawCalls === 2, `drawWinrateCurve monkeypatch calls changed: ${JSON.stringify(state.monkeypatchState)}`);
  assert(state.monkeypatchState.count === 1, `winrate history after monkeypatch changed: ${JSON.stringify(state.monkeypatchState)}`);
  assert(state.emptyCurve, "empty winrate curve did not render placeholder");
  assert(state.curveState.count === 2, `winrate history dedupe/count changed: ${state.curveState.count}`);
  assert(state.curveState.nonblank, "winrate curve did not render after points");
  assert(state.pendingState.blackWidth === "50%" && state.pendingState.whiteWidth === "50%", `pending winrate widths changed: ${JSON.stringify(state.pendingState)}`);
  assert(state.pendingState.blackLabel === "", `pending winrate label should be empty: ${state.pendingState.blackLabel}`);
  assert(state.pendingState.scoreDisabled, "pending analysis should disable score button");
  assert(state.readyState.blackWidth === "85%" && state.readyState.whiteWidth === "15%", `ready winrate widths changed: ${JSON.stringify(state.readyState)}`);
  assert(state.readyState.blackLabel.includes("85.0%") && state.readyState.whiteLabel.includes("15.0%"), `ready labels changed: ${JSON.stringify(state.readyState)}`);
  assert(!state.readyState.scoreDisabled, "high winrate should enable score button");
  assert(state.lowReadyState.blackWidth === "60%" && state.lowReadyState.whiteWidth === "40%", `low winrate widths changed: ${JSON.stringify(state.lowReadyState)}`);
  assert(state.lowReadyState.blackLabel.includes("60.0%") && state.lowReadyState.whiteLabel.includes("40.0%"), `low winrate labels changed: ${JSON.stringify(state.lowReadyState)}`);
  assert(state.lowReadyState.scoreDisabled, "low winrate should disable score button");
  assert(state.lowReadyState.scoreTitle.includes("80"), `low winrate score title changed: ${state.lowReadyState.scoreTitle}`);
  assert(state.lockedState.wrapClass.includes("analysis-off"), `quickthink lock did not mark analysis off: ${state.lockedState.wrapClass}`);
  assert(state.lockedState.blackLabel === "", `locked analysis should clear labels: ${state.lockedState.blackLabel}`);
  assert(state.lockedState.scoreDisabled, "locked analysis should disable score button");
  assert(errors.length === 0, `browser errors: ${errors.join("; ")}`);

  console.log(JSON.stringify({
    ok: true,
    winratePoints: state.curveState.count,
    overlayClass: state.overlayOpen.cls,
    readyWinrate: state.readyState.blackLabel,
  }, null, 2));
} finally {
  await browser.close();
}
