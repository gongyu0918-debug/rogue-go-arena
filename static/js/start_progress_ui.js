// Start-game preparation overlay. Keeps engine/model loading feedback out of setup and WS handlers.

(() => {
let startProgressVisible = false;

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

function showStartProgress(title, message, detail) {
  const els = startProgressElements();
  if (!els.modal) return;
  startProgressVisible = true;
  setStartProgressText(title, message, detail);
  els.modal.classList.add("show");
}

function updateStartProgress(title, message, detail) {
  if (!startProgressVisible) return;
  setStartProgressText(title, message, detail);
}

function hideStartProgress() {
  const els = startProgressElements();
  startProgressVisible = false;
  if (els.modal) els.modal.classList.remove("show");
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

window.showStartProgress = showStartProgress;
window.updateStartProgress = updateStartProgress;
window.hideStartProgress = hideStartProgress;
window.showGameStartProgress = showGameStartProgress;
window.advanceStartProgressForGameStart = advanceStartProgressForGameStart;
})();
