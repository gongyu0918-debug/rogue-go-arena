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
