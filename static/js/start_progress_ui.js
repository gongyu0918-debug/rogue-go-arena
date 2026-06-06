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
  if (els.title) els.title.textContent = title || ui("对局准备中", "Preparing game");
  if (els.message) els.message.textContent = message || ui("正在连接服务与加载模型…", "Connecting and loading the model...");
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

function engineLogText(item) {
  if (!item) return "";
  if (typeof item === "string") return item;
  if (typeof item === "object") return item.message || item.detail || "";
  return String(item);
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
      ui("模型仍在启动", "Model is still starting"),
      ui("启动时间异常偏长，请关闭后重开，或切换 CPU/OpenCL 后再试。", "Startup is taking too long. Restart the app or try CPU/OpenCL."),
      status.engine_message || ""
    );
  }
}

function showGameStartProgress(options = {}) {
  const mode = options.mode || "normal";
  const isTwoPlayer = !!options.twoPlayer;
  const isObserver = !!options.aiObserver;
  const title = mode === "ultimate"
    ? ui("Ultimate 对局准备中", "Preparing Ultimate game")
    : mode === "rogue"
      ? ui("Rogue 对局准备中", "Preparing Rogue game")
      : isObserver
        ? ui("AI 学习对局准备中", "Preparing AI study game")
        : ui("对局准备中", "Preparing game");
  const message = isTwoPlayer
    ? ui("正在创建棋盘与同步界面…", "Creating board and syncing the UI...")
    : ui("正在加载模型、同步棋盘与规则…", "Loading model, board, and rules...");
  const detail = mode === "rogue"
    ? ui("模型就绪后会进入卡牌选择。", "Card draft opens after the model is ready.")
    : mode === "ultimate"
      ? ui("模型就绪后会进入大招卡选择。", "Ultimate draft opens after the model is ready.")
      : ui("请稍候，完成后会自动开始。", "Please wait. The game will start automatically.");
  showStartProgress(title, message, detail);
}

function advanceStartProgressForGameStart(msg) {
  if (!startProgressVisible) return;
  if (msg?.ultimate) {
    updateStartProgress(
      ui("模型已就绪", "Model ready"),
      ui("正在准备大招卡选择…", "Preparing Ultimate card draft..."),
      ""
    );
    return;
  }
  if (msg?.rogue_enabled) {
    updateStartProgress(
      ui("模型已就绪", "Model ready"),
      ui("正在准备 Rogue 卡牌选择…", "Preparing Rogue card draft..."),
      ""
    );
    return;
  }
  hideStartProgress();
}

function engineProgressDetail(msg) {
  const phase = msg?.phase ? String(msg.phase) : "";
  const lastError = msg?.last_error ? String(msg.last_error) : "";
  const logTail = Array.isArray(msg?.log_tail)
    ? msg.log_tail.map(engineLogText).filter(Boolean).slice(-2).join(" / ")
    : "";
  if (lastError) return lastError;
  if (logTail) return logTail;
  if (phase && phase !== "ready") {
    return ui(`当前阶段：${phase}`, `Current phase: ${phase}`);
  }
  return ui("首次启动可能需要更久，请不要重复点击开始。", "The first launch can take longer. Please do not start again.");
}

function updateStartProgressForEngineNotReady(msg) {
  showStartProgress(
    ui("模型加载中", "Loading model"),
    msg?.message || ui("KataGo 正在随游戏启动…", "KataGo is starting with the game..."),
    engineProgressDetail(msg)
  );
}

function showDraftReadyProgress(mode) {
  const isUltimate = mode === "ultimate";
  showStartProgress(
    ui("模型已就绪", "Model ready"),
    isUltimate
      ? ui("大招卡选择已打开。", "Ultimate card draft is open.")
      : ui("Rogue 卡牌选择已打开。", "Rogue card draft is open."),
    ui("请选择卡牌后继续对局。", "Choose a card to continue.")
  );
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
