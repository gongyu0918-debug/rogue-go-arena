// Start-game preparation overlay. Keeps engine/model loading feedback out of setup and WS handlers.

(() => {
let startProgressVisible = false;
let startProgressDraftHideTimer = null;
let startProgressWatchdogTimer = null;
let startProgressShownAt = 0;
let startProgressReadyAt = 0;

function startProgressElements() {
  return {
    modal: document.getElementById("start-progress-modal"),
    title: document.getElementById("start-progress-title"),
    message: document.getElementById("start-progress-message"),
    detail: document.getElementById("start-progress-detail"),
  };
}

function setStartProgressText(title, message, detail) {
  const els = startProgressElements();
  if (els.title) els.title.textContent = title || ui("准备中…", "Getting ready…");
  if (els.message) els.message.textContent = message || "";
  if (els.detail) els.detail.textContent = detail || "";
}

function clearStartProgressDraftHideTimer() {
  if (startProgressDraftHideTimer) {
    clearTimeout(startProgressDraftHideTimer);
    startProgressDraftHideTimer = null;
  }
}

function clearStartProgressWatchdog() {
  if (startProgressWatchdogTimer) {
    clearInterval(startProgressWatchdogTimer);
    startProgressWatchdogTimer = null;
  }
  startProgressReadyAt = 0;
}

function ensureStartProgressWatchdog() {
  if (startProgressWatchdogTimer) return;
  startProgressWatchdogTimer = setInterval(checkStartProgressHealth, 2000);
}

function showStartProgress(title, message, detail) {
  const els = startProgressElements();
  if (!els.modal) return;
  clearStartProgressDraftHideTimer();
  startProgressVisible = true;
  startProgressShownAt = Date.now();
  startProgressReadyAt = 0;
  setStartProgressText(title, message, detail);
  els.modal.classList.add("show");
  ensureStartProgressWatchdog();
}

function updateStartProgress(title, message, detail) {
  if (!startProgressVisible) return;
  setStartProgressText(title, message, detail);
}

function hideStartProgress() {
  const els = startProgressElements();
  clearStartProgressDraftHideTimer();
  clearStartProgressWatchdog();
  startProgressVisible = false;
  if (els.modal) els.modal.classList.remove("show");
}

function hideStartProgressSoon(delayMs = 1200) {
  clearStartProgressDraftHideTimer();
  startProgressDraftHideTimer = setTimeout(() => {
    startProgressDraftHideTimer = null;
    hideStartProgress();
  }, delayMs);
}

async function checkStartProgressHealth() {
  if (!startProgressVisible) return;
  let status = null;
  try {
    status = await refreshNetworkInfo();
  } catch (_) {
    return;
  }
  if (!startProgressVisible || !status) return;
  const phase = String(status.engine_phase || "");
  const elapsedMs = Date.now() - startProgressShownAt;
  if (status.katago_ready || phase === "ready") {
    if (gameState) {
      hideStartProgress();
      return;
    }
    if (!startProgressReadyAt) startProgressReadyAt = Date.now();
    if (Date.now() - startProgressReadyAt > 10000) {
      updateStartProgress(
        ui("模型已就绪", "Model ready"),
        ui("对局消息没有返回，请重新开始对局。", "The game did not answer. Please start again."),
        ""
      );
      logI18n(
        "模型已就绪，但对局消息未返回，请重新开始对局。",
        "The model is ready, but the game did not answer. Please start again.",
        "モデルは準備完了ですが、対局応答がありません。再度開始してください。",
        "모델은 준비됐지만 대국 응답이 없습니다. 다시 시작해 주세요."
      );
      hideStartProgressSoon(2200);
    }
    return;
  }
  startProgressReadyAt = 0;
  if (phase === "failed" || phase === "disabled") {
    updateStartProgress(
      ui("模型启动失败", "Model startup failed"),
      status.engine_message || ui("KataGo 未能启动。", "KataGo could not start."),
      status.engine_last_error || ""
    );
    hideStartProgressSoon(3200);
    return;
  }
  if (phase === "stopped" && elapsedMs > 8000) {
    updateStartProgress(
      ui("模型未在运行", "Model is not running"),
      status.engine_message || ui("KataGo 已停止，请重新开始对局。", "KataGo stopped. Please start again."),
      ""
    );
    hideStartProgressSoon(2600);
    return;
  }
  if (phase === "initializing" && elapsedMs > 180000) {
    updateStartProgress(
      ui("仍在加载…", "Still loading…"),
      ui("若长时间没有反应，请重启游戏", "If nothing happens, restart the app."),
      ""
    );
  }
}

function showGameStartProgress(options = {}) {
  const message = options.twoPlayer
    ? ui("正在摆好棋盘…", "Setting up the board…")
    : ui("正在加载 AI…", "Loading the AI…");
  showStartProgress(ui("准备中…", "Getting ready…"), message, "");
}

function advanceStartProgressForGameStart(msg) {
  if (!startProgressVisible) return;
  if (msg?.ultimate || msg?.rogue_enabled) {
    updateStartProgress(ui("准备好了！", "Ready!"), "", "");
    return;
  }
  hideStartProgress();
}

function updateStartProgressForEngineNotReady(msg) {
  showStartProgress(
    ui("正在加载 AI…", "Loading the AI…"),
    ui("首次启动会稍慢一些", "The first start takes a bit longer."),
    msg?.last_error ? String(msg.last_error) : ""
  );
}

function showDraftReadyProgress() {
  showStartProgress(ui("准备好了！", "Ready!"), ui("选一张卡牌开始吧", "Pick a card to begin."), "");
  hideStartProgressSoon();
}

window.showStartProgress = showStartProgress;
window.updateStartProgress = updateStartProgress;
window.hideStartProgress = hideStartProgress;
window.showGameStartProgress = showGameStartProgress;
window.advanceStartProgressForGameStart = advanceStartProgressForGameStart;
window.updateStartProgressForEngineNotReady = updateStartProgressForEngineNotReady;
window.showDraftReadyProgress = showDraftReadyProgress;
})();
