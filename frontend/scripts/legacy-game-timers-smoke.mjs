import { chromium } from "playwright";

const DEFAULT_URL = "http://127.0.0.1:8876/";
const urlArg = process.argv.find((arg) => arg.startsWith("--url="));
const targetUrl = withLanguageParam(
  urlArg ? urlArg.slice("--url=".length) : process.env.LEGACY_GAME_TIMERS_URL || DEFAULT_URL,
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

  const state = await page.evaluate(() => {
    const emptyBoard = (size) => Array.from({ length: size }, () => Array(size).fill(0));
    const baseState = (overrides = {}) => ({
      type: "game_state",
      size: 9,
      board: emptyBoard(9),
      captures: { B: 0, W: 0 },
      current_player: "B",
      player_color: "B",
      ai_color: "W",
      level: "10k",
      move_number: 0,
      komi: 6.5,
      game_over: false,
      two_player: false,
      ai_observer: false,
      rogue_uses: {},
      ...overrides,
    });
    const timerText = () => ({
      blackText: document.querySelector("#timer-black-text")?.textContent || "",
      whiteText: document.querySelector("#timer-white-text")?.textContent || "",
      blackClass: document.querySelector("#timer-black")?.className || "",
      whiteClass: document.querySelector("#timer-white")?.className || "",
      wrapClass: document.querySelector("#timer-wrap")?.className || "",
    });

    window.__timerSmoke = { payloads: [], warnings: 0 };
    sendWS = window.sendWS = payload => { window.__timerSmoke.payloads.push(payload); };
    playTimerWarningSound = window.playTimerWarningSound = () => { window.__timerSmoke.warnings += 1; };

    const publicFns = [
      typeof window.initTimers,
      typeof window.startTimerFor,
      typeof window.stopTimerTick,
      typeof window.tickTimer,
      typeof window.onMoveCompleted,
      typeof window.formatTime,
      typeof window.updateTimerDisplay,
    ];
    const stateGlobals = [
      typeof window.timerMode,
      typeof window.mainTimeSetting,
      typeof window.byoPeriodsSetting,
      typeof window.byoTimeSetting,
      typeof window.blackTimer,
      typeof window.whiteTimer,
      typeof window.timerInterval,
      typeof window.lastTimerTick,
    ];
    const privateFns = [
      typeof window.createTimer,
      typeof window.timerPairs,
      typeof window.timerForColor,
      typeof window.setTimerWrapHidden,
      typeof window.resetTimerState,
      typeof window.setRunningColor,
      typeof window.timerElapsedSeconds,
      typeof window.maybePlayMainTimeWarning,
      typeof window.maybePlayByoyomiWarning,
      typeof window.expireTimer,
      typeof window.tickMainTime,
      typeof window.tickByoyomi,
      typeof window.tickActiveTimer,
      typeof window.formatTimer,
      typeof window.syncTimerPanel,
      typeof window.defineTimerGlobal,
    ];

    stopTimerTick();
    timerMode = "absolute";
    mainTimeSetting = 12;
    byoPeriodsSetting = 3;
    byoTimeSetting = 20;
    handleMessage({ ...baseState(), type: "game_start", current_player: "B" });
    const messageStartState = {
      timerMode,
      black: { ...blackTimer },
      white: { ...whiteTimer },
      timerIntervalIsSet: timerInterval !== null,
      currentPlayer: gameState?.current_player || "",
      ...timerText(),
    };

    handleMessage({
      ...baseState({
        board: emptyBoard(9),
        current_player: "W",
        move_number: 1,
      }),
      type: "game_state",
    });
    const messageSwitchState = {
      black: { ...blackTimer },
      white: { ...whiteTimer },
      timerIntervalIsSet: timerInterval !== null,
      currentPlayer: gameState?.current_player || "",
      ...timerText(),
    };

    stopTimerTick();
    timerMode = "none";
    initTimers();
    const noneState = {
      timerMode,
      timerIntervalIsNull: timerInterval === null,
      blackRunning: blackTimer.running,
      whiteRunning: whiteTimer.running,
      ...timerText(),
    };

    timerMode = "absolute";
    mainTimeSetting = 5;
    byoPeriodsSetting = 3;
    byoTimeSetting = 20;
    initTimers();
    const absoluteInit = {
      black: { ...blackTimer },
      white: { ...whiteTimer },
      ...timerText(),
    };

    startTimerFor("B");
    const absoluteStarted = {
      black: { ...blackTimer },
      white: { ...whiteTimer },
      timerIntervalIsSet: timerInterval !== null,
      ...timerText(),
    };

    lastTimerTick = performance.now() - 2100;
    tickTimer();
    const absoluteTicked = {
      black: { ...blackTimer },
      white: { ...whiteTimer },
      ...timerText(),
    };

    onMoveCompleted("W");
    const switchedToWhite = {
      black: { ...blackTimer },
      white: { ...whiteTimer },
      ...timerText(),
    };

    stopTimerTick();
    timerMode = "byoyomi";
    mainTimeSetting = 0;
    byoPeriodsSetting = 2;
    byoTimeSetting = 3;
    initTimers();
    startTimerFor("W");
    lastTimerTick = performance.now() - 1100;
    tickTimer();
    const byoyomiTicked = {
      black: { ...blackTimer },
      white: { ...whiteTimer },
      ...timerText(),
    };

    onMoveCompleted("B");
    const byoyomiSwitched = {
      black: { ...blackTimer },
      white: { ...whiteTimer },
      ...timerText(),
    };

    stopTimerTick();
    timerMode = "byoyomi";
    mainTimeSetting = 0;
    byoPeriodsSetting = 1;
    byoTimeSetting = 1;
    initTimers();
    blackTimer = { main: 0, byoPeriods: 1, byoTime: 0.2, running: true };
    whiteTimer = { main: 0, byoPeriods: 1, byoTime: 1, running: false };
    lastTimerTick = performance.now() - 1000;
    tickTimer();
    const expiredState = {
      black: { ...blackTimer },
      white: { ...whiteTimer },
      timerIntervalIsNull: timerInterval === null,
      payloads: [...window.__timerSmoke.payloads],
      warnings: window.__timerSmoke.warnings,
      ...timerText(),
    };

    stopTimerTick();

    return {
      publicFns,
      stateGlobals,
      privateFns,
      messageStartState,
      messageSwitchState,
      formatted: [formatTime(0), formatTime(65), formatTime(599.9)],
      noneState,
      absoluteInit,
      absoluteStarted,
      absoluteTicked,
      switchedToWhite,
      byoyomiTicked,
      byoyomiSwitched,
      expiredState,
    };
  });

  assert(state.publicFns.every(type => type === "function"), `timer globals missing: ${state.publicFns.join(", ")}`);
  assert(state.stateGlobals.join("|") === "string|number|number|number|object|object|object|number", `timer state globals changed: ${state.stateGlobals.join("|")}`);
  assert(state.privateFns.every(type => type === "undefined"), `timer private helpers leaked globally: ${state.privateFns.join(", ")}`);
  assert(state.messageStartState.black.running && !state.messageStartState.white.running, `game_start did not start black timer: ${JSON.stringify(state.messageStartState)}`);
  assert(state.messageStartState.timerIntervalIsSet, "game_start did not create timer interval");
  assert(state.messageStartState.black.main === 12 && state.messageStartState.white.main === 12, `game_start did not use absolute timer settings: ${JSON.stringify(state.messageStartState)}`);
  assert(state.messageStartState.blackClass.includes("active") && !state.messageStartState.whiteClass.includes("active"), `game_start timer classes changed: ${JSON.stringify(state.messageStartState)}`);
  assert(!state.messageSwitchState.black.running && state.messageSwitchState.white.running, `game_state did not switch running timer to white: ${JSON.stringify(state.messageSwitchState)}`);
  assert(state.messageSwitchState.currentPlayer === "W", `game_state did not update current player: ${state.messageSwitchState.currentPlayer}`);
  assert(state.formatted.join("|") === "0:00|1:05|9:59", `formatTime changed: ${state.formatted.join("|")}`);
  assert(state.noneState.wrapClass.includes("timer-hidden"), `none mode should hide timer: ${state.noneState.wrapClass}`);
  assert(state.noneState.timerIntervalIsNull, "none mode did not stop timer interval");
  assert(!state.noneState.blackRunning && !state.noneState.whiteRunning, "none mode should stop both clocks");

  assert(!state.absoluteInit.wrapClass.includes("timer-hidden"), `absolute mode should show timer: ${state.absoluteInit.wrapClass}`);
  assert(state.absoluteInit.black.main === 5 && state.absoluteInit.white.main === 5, `absolute main time changed: ${JSON.stringify(state.absoluteInit)}`);
  assert(state.absoluteInit.black.byoPeriods === 0 && state.absoluteInit.white.byoPeriods === 0, "absolute mode should clear byo periods");
  assert(state.absoluteInit.blackText === "0:05" && state.absoluteInit.whiteText === "0:05", `absolute display changed: ${JSON.stringify(state.absoluteInit)}`);
  assert(state.absoluteStarted.black.running && !state.absoluteStarted.white.running, "startTimerFor(B) did not activate black only");
  assert(state.absoluteStarted.timerIntervalIsSet, "startTimerFor did not create interval");
  assert(state.absoluteStarted.blackClass.includes("active") && !state.absoluteStarted.whiteClass.includes("active"), `active timer class changed: ${JSON.stringify(state.absoluteStarted)}`);
  assert(state.absoluteTicked.black.main < 3.2 && state.absoluteTicked.black.main > 2.5, `absolute tick did not decrement main time: ${state.absoluteTicked.black.main}`);
  assert(!state.switchedToWhite.black.running && state.switchedToWhite.white.running, "onMoveCompleted(W) did not switch active timer to white");

  assert(state.byoyomiTicked.white.byoPeriods === 2, `byoyomi period count changed too early: ${state.byoyomiTicked.white.byoPeriods}`);
  assert(state.byoyomiTicked.white.byoTime < 2.1 && state.byoyomiTicked.white.byoTime > 1.5, `byoyomi tick did not decrement byo time: ${state.byoyomiTicked.white.byoTime}`);
  assert(state.byoyomiTicked.whiteText.includes("s ×2"), `byoyomi display changed: ${state.byoyomiTicked.whiteText}`);
  assert(state.byoyomiSwitched.white.byoTime === 3, `onMoveCompleted did not reset previous byo time: ${state.byoyomiSwitched.white.byoTime}`);
  assert(state.byoyomiSwitched.black.running && !state.byoyomiSwitched.white.running, "onMoveCompleted(B) did not switch active timer to black");

  assert(state.expiredState.payloads.length === 1, `time expiry payload count changed: ${JSON.stringify(state.expiredState.payloads)}`);
  assert(state.expiredState.payloads[0].action === "time_expired" && state.expiredState.payloads[0].color === "B", `time expiry payload changed: ${JSON.stringify(state.expiredState.payloads)}`);
  assert(state.expiredState.timerIntervalIsNull, "time expiry did not stop interval");
  assert(!state.expiredState.black.running, "time expiry did not stop expired timer");
  assert(state.expiredState.warnings === 0, `manual smoke should not trigger warning sounds: ${state.expiredState.warnings}`);
  assert(errors.length === 0, `browser errors: ${errors.join("; ")}`);

  console.log(JSON.stringify({
    ok: true,
    absoluteBlackMainAfterTick: Number(state.absoluteTicked.black.main.toFixed(2)),
    byoyomiWhiteTimeAfterTick: Number(state.byoyomiTicked.white.byoTime.toFixed(2)),
    payloads: state.expiredState.payloads,
  }, null, 2));
} finally {
  await browser.close();
}
