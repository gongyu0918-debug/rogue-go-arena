// Per-game clock state and timer display helpers for the legacy frontend.

(() => {
let timerMode = "none"; // none | byoyomi | absolute
let mainTimeSetting = 300;
let byoPeriodsSetting = 3;
let byoTimeSetting = 30;
let blackTimer = createTimer(0, 0, 0);
let whiteTimer = createTimer(0, 0, 0);
let timerInterval = null;
let lastTimerTick = 0;

function createTimer(main, byoPeriods, byoTime) {
  return { main, byoPeriods, byoTime, running: false };
}

function timerPairs() {
  return [["B", blackTimer], ["W", whiteTimer]];
}

function timerForColor(color) {
  return color === "B" ? blackTimer : whiteTimer;
}

function setTimerWrapHidden(hidden) {
  document.getElementById("timer-wrap").classList.toggle("timer-hidden", hidden);
}

function resetTimerState() {
  blackTimer = createTimer(mainTimeSetting, byoPeriodsSetting, byoTimeSetting);
  whiteTimer = createTimer(mainTimeSetting, byoPeriodsSetting, byoTimeSetting);
  if (timerMode === "absolute") {
    blackTimer.byoPeriods = 0;
    whiteTimer.byoPeriods = 0;
  }
}

function initTimers() {
  if (timerMode === "none") {
    setTimerWrapHidden(true);
    stopTimerTick();
    return;
  }
  setTimerWrapHidden(false);
  resetTimerState();
  updateTimerDisplay();
}

function setRunningColor(color) {
  blackTimer.running = color === "B";
  whiteTimer.running = color === "W";
}

function startTimerFor(color) {
  if (timerMode === "none") return;
  setRunningColor(color);
  lastTimerTick = performance.now();
  if (!timerInterval) {
    timerInterval = setInterval(tickTimer, 100);
  }
  updateTimerDisplay();
}

function stopTimerTick() {
  if (timerInterval) {
    clearInterval(timerInterval);
    timerInterval = null;
  }
  blackTimer.running = false;
  whiteTimer.running = false;
}

function timerElapsedSeconds() {
  const now = performance.now();
  const dt = (now - lastTimerTick) / 1000;
  lastTimerTick = now;
  return dt;
}

function maybePlayMainTimeWarning(timer) {
  if (timer.main <= 10 && timer.main > 9.9) playTimerWarningSound();
}

function maybePlayByoyomiWarning(timer) {
  if (timer.byoTime <= 5 && timer.byoTime > 4.9) playTimerWarningSound();
}

function expireTimer(color, timer) {
  timer.running = false;
  stopTimerTick();
  sendWS({ action: "time_expired", color });
}

function tickMainTime(timer, dt) {
  timer.main = Math.max(0, timer.main - dt);
  if (timer.main <= 0 && timer.byoPeriods > 0) {
    timer.byoTime = byoTimeSetting;
  }
  maybePlayMainTimeWarning(timer);
}

function tickByoyomi(color, timer, dt) {
  timer.byoTime -= dt;
  maybePlayByoyomiWarning(timer);
  if (timer.byoTime > 0) return false;
  timer.byoPeriods--;
  if (timer.byoPeriods <= 0) {
    expireTimer(color, timer);
    return true;
  }
  timer.byoTime = byoTimeSetting;
  return false;
}

function tickActiveTimer(color, timer, dt) {
  if (!timer.running) return false;
  if (timer.main > 0) {
    tickMainTime(timer, dt);
    return false;
  }
  if (timer.byoPeriods > 0) {
    return tickByoyomi(color, timer, dt);
  }
  expireTimer(color, timer);
  return true;
}

function tickTimer() {
  const dt = timerElapsedSeconds();
  for (const [color, timer] of timerPairs()) {
    if (tickActiveTimer(color, timer, dt)) return;
  }
  updateTimerDisplay();
}

function onMoveCompleted(nextColor) {
  if (timerMode === "none") return;
  const prevColor = nextColor === "B" ? "W" : "B";
  const prevTimer = timerForColor(prevColor);
  if (prevTimer.main <= 0 && prevTimer.byoPeriods > 0) {
    prevTimer.byoTime = byoTimeSetting;
  }
  startTimerFor(nextColor);
}

function formatTime(seconds) {
  if (seconds <= 0) return "0:00";
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function formatTimer(timer) {
  if (timer.main > 0) return formatTime(timer.main);
  if (timer.byoPeriods > 0) return `${Math.ceil(timer.byoTime)}s ×${timer.byoPeriods}`;
  return "0:00";
}

function syncTimerPanel(color, timer) {
  const prefix = color === "B" ? "black" : "white";
  const panel = document.getElementById(`timer-${prefix}`);
  document.getElementById(`timer-${prefix}-text`).textContent = formatTimer(timer);
  panel.classList.toggle("active", timer.running);
  panel.classList.toggle("danger", timer.main <= 0 && timer.byoPeriods <= 1 && timer.running);
}

function updateTimerDisplay() {
  syncTimerPanel("B", blackTimer);
  syncTimerPanel("W", whiteTimer);
}

function defineTimerGlobal(name, get, set) {
  Object.defineProperty(window, name, {
    configurable: true,
    enumerable: true,
    get,
    set,
  });
}

defineTimerGlobal("timerMode", () => timerMode, value => { timerMode = value; });
defineTimerGlobal("mainTimeSetting", () => mainTimeSetting, value => { mainTimeSetting = value; });
defineTimerGlobal("byoPeriodsSetting", () => byoPeriodsSetting, value => { byoPeriodsSetting = value; });
defineTimerGlobal("byoTimeSetting", () => byoTimeSetting, value => { byoTimeSetting = value; });
defineTimerGlobal("blackTimer", () => blackTimer, value => { blackTimer = value; });
defineTimerGlobal("whiteTimer", () => whiteTimer, value => { whiteTimer = value; });
defineTimerGlobal("timerInterval", () => timerInterval, value => { timerInterval = value; });
defineTimerGlobal("lastTimerTick", () => lastTimerTick, value => { lastTimerTick = value; });

window.initTimers = initTimers;
window.startTimerFor = startTimerFor;
window.stopTimerTick = stopTimerTick;
window.tickTimer = tickTimer;
window.onMoveCompleted = onMoveCompleted;
window.formatTime = formatTime;
window.updateTimerDisplay = updateTimerDisplay;
})();
