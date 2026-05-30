// Per-game clock state and timer display helpers for the legacy frontend.

let timerMode = "none"; // none | byoyomi | absolute
let mainTimeSetting = 300;
let byoPeriodsSetting = 3;
let byoTimeSetting = 30;
let blackTimer = { main: 0, byoPeriods: 0, byoTime: 0, running: false };
let whiteTimer = { main: 0, byoPeriods: 0, byoTime: 0, running: false };
let timerInterval = null;
let lastTimerTick = 0;

function initTimers() {
  if (timerMode === "none") {
    document.getElementById("timer-wrap").classList.add("timer-hidden");
    stopTimerTick();
    return;
  }
  document.getElementById("timer-wrap").classList.remove("timer-hidden");
  blackTimer = { main: mainTimeSetting, byoPeriods: byoPeriodsSetting, byoTime: byoTimeSetting, running: false };
  whiteTimer = { main: mainTimeSetting, byoPeriods: byoPeriodsSetting, byoTime: byoTimeSetting, running: false };
  if (timerMode === "absolute") {
    blackTimer.byoPeriods = 0;
    whiteTimer.byoPeriods = 0;
  }
  updateTimerDisplay();
}

function startTimerFor(color) {
  if (timerMode === "none") return;
  blackTimer.running = (color === "B");
  whiteTimer.running = (color === "W");
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

function tickTimer() {
  const now = performance.now();
  const dt = (now - lastTimerTick) / 1000;
  lastTimerTick = now;

  for (const [color, timer] of [["B", blackTimer], ["W", whiteTimer]]) {
    if (!timer.running) continue;
    if (timer.main > 0) {
      timer.main = Math.max(0, timer.main - dt);
      if (timer.main <= 0 && timer.byoPeriods > 0) {
        timer.byoTime = (color === "B" ? byoTimeSetting : byoTimeSetting);
      }
      if (timer.main <= 10 && timer.main > 9.9) playTimerWarningSound();
    } else if (timer.byoPeriods > 0) {
      timer.byoTime -= dt;
      if (timer.byoTime <= 5 && timer.byoTime > 4.9) playTimerWarningSound();
      if (timer.byoTime <= 0) {
        timer.byoPeriods--;
        if (timer.byoPeriods <= 0) {
          timer.running = false;
          stopTimerTick();
          sendWS({ action: "time_expired", color });
          return;
        }
        timer.byoTime = byoTimeSetting;
      }
    } else {
      timer.running = false;
      stopTimerTick();
      sendWS({ action: "time_expired", color });
      return;
    }
  }
  updateTimerDisplay();
}

function onMoveCompleted(nextColor) {
  if (timerMode === "none") return;
  const prevColor = nextColor === "B" ? "W" : "B";
  const prevTimer = prevColor === "B" ? blackTimer : whiteTimer;
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

function updateTimerDisplay() {
  const formatTimer = (t) => {
    if (t.main > 0) return formatTime(t.main);
    if (t.byoPeriods > 0) return `${Math.ceil(t.byoTime)}s ×${t.byoPeriods}`;
    return "0:00";
  };

  const bt = document.getElementById("timer-black");
  const wt = document.getElementById("timer-white");
  document.getElementById("timer-black-text").textContent = formatTimer(blackTimer);
  document.getElementById("timer-white-text").textContent = formatTimer(whiteTimer);

  bt.classList.toggle("active", blackTimer.running);
  wt.classList.toggle("active", whiteTimer.running);
  bt.classList.toggle("danger", blackTimer.main <= 0 && blackTimer.byoPeriods <= 1 && blackTimer.running);
  wt.classList.toggle("danger", whiteTimer.main <= 0 && whiteTimer.byoPeriods <= 1 && whiteTimer.running);
}

window.initTimers = initTimers;
window.startTimerFor = startTimerFor;
window.stopTimerTick = stopTimerTick;
window.tickTimer = tickTimer;
window.onMoveCompleted = onMoveCompleted;
window.formatTime = formatTime;
window.updateTimerDisplay = updateTimerDisplay;
