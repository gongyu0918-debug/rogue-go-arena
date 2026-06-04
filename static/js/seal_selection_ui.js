// Rogue seal point marking UI. The browser stages edits locally, then commits to the server.

(() => {
function pointKey(x, y) {
  return `${x},${y}`;
}

function normalizedSealRequired(value) {
  const n = Number(value);
  return Number.isFinite(n) && n > 0 ? Math.floor(n) : 0;
}

function sealPointIndex(x, y) {
  return pendingRogueSealPoints.findIndex(([px, py]) => px === x && py === y);
}

function setSealStageClass(active, waiting = false) {
  const container = document.getElementById("board-container");
  if (!container) return;
  container.classList.toggle("seal-stage", active);
  container.classList.toggle("seal-stage-waiting", active && waiting);
}

function updateSealBanner(text) {
  const banner = document.getElementById("seal-board-banner");
  const label = document.getElementById("seal-board-banner-text");
  if (!banner || !label) return;
  banner.hidden = !rogueSealing;
  label.textContent = text || "";
}

function sealSelectionText() {
  if (rogueSealWaitingForOpponent) {
    return ui(
      "请等待对方标注禁着点",
      "Waiting for the opponent to mark forbidden points",
      "相手の禁点指定を待っています",
      "상대가 금지점을 표시하는 중입니다"
    );
  }
  const remaining = Math.max(0, rogueSealRequired - pendingRogueSealPoints.length);
  return ui(
    `请标注禁着点 · 剩余 ${remaining}`,
    `Mark forbidden points · ${remaining} left`,
    `禁点を指定 · 残り ${remaining}`,
    `금지점을 표시하세요 · ${remaining}개 남음`
  );
}

function syncSealSelectionUi() {
  const status = document.getElementById("seal-overlay");
  if (!rogueSealing) {
    setSealStageClass(false);
    updateSealBanner("");
    if (status) status.hidden = true;
    return;
  }
  setSealStageClass(true);
  updateSealBanner(sealSelectionText());
  const hint = document.getElementById("seal-hint");
  if (hint) hint.textContent = sealSelectionText();
  if (status) status.hidden = false;
  if (!animFrameId) render();
}

function startRogueSealSelection(required) {
  rogueSealRequired = normalizedSealRequired(required);
  pendingRogueSealPoints = [];
  rogueSealWaitingForOpponent = false;
  rogueSealing = rogueSealRequired > 0;
  syncSealSelectionUi();
  if (rogueSealing) {
    logI18n(
      "🚫 请标注禁着点，标注完成后可确认或重新标注。",
      "🚫 Mark forbidden points. You can confirm or restart after marking.",
      "🚫 禁点を指定してください。完了後に確定またはやり直せます。",
      "🚫 금지점을 표시하세요. 완료 후 확정하거나 다시 표시할 수 있습니다."
    );
  }
}

function resetRogueSealSelection() {
  pendingRogueSealPoints = [];
  rogueSealWaitingForOpponent = false;
  rogueSealing = rogueSealRequired > 0;
  syncSealSelectionUi();
}

function commitRogueSealSelection() {
  const points = pendingRogueSealPoints.slice(0, rogueSealRequired);
  rogueSealing = false;
  rogueSealWaitingForOpponent = false;
  setSealStageClass(false);
  updateSealBanner(ui("正在提交禁着点…", "Submitting forbidden points..."));
  if (!animFrameId) render();
  for (const [x, y] of points) {
    sendWS({ action: "rogue_seal_point", x, y });
  }
}

function showSealConfirmDialog() {
  if (document.getElementById("confirm-modal")?.classList.contains("show")) return;
  const msg = ui(
    "禁着点已标注完成，是否开始对局？",
    "Forbidden points are marked. Start the game?",
    "禁点の指定が完了しました。対局を開始しますか？",
    "금지점 표시가 끝났습니다. 대국을 시작할까요?"
  );
  showConfirmModal(msg, commitRogueSealSelection, {
    confirmText: ui("是，开始对局", "Start game", "対局開始", "대국 시작"),
    cancelText: ui("重新标注", "Mark again", "指定し直す", "다시 표시"),
    onCancel: resetRogueSealSelection,
  });
}

function toggleRogueSealPoint(x, y) {
  const existing = sealPointIndex(x, y);
  if (existing >= 0) {
    pendingRogueSealPoints.splice(existing, 1);
    syncSealSelectionUi();
    return;
  }
  if (pendingRogueSealPoints.length >= rogueSealRequired) {
    logI18n(
      "禁着点数量已满，可点击已选点取消，或在确认框选择重新标注。",
      "The mark limit is reached. Click a marked point to remove it or restart marking.",
      "指定数に達しました。指定済みの点をクリックして解除するか、やり直してください。",
      "표시 수가 가득 찼습니다. 표시한 점을 눌러 취소하거나 다시 표시하세요."
    );
    return;
  }
  pendingRogueSealPoints.push([x, y]);
  syncSealSelectionUi();
  if (pendingRogueSealPoints.length >= rogueSealRequired) {
    showSealConfirmDialog();
  }
}

function handleRogueSealBoardClick(x, y) {
  if (!rogueSealing) return false;
  if (document.getElementById("confirm-modal")?.classList.contains("show")) return true;
  if (rogueSealWaitingForOpponent) {
    logI18n(
      "请等待对方标注禁着点。",
      "Wait for the opponent to mark forbidden points.",
      "相手の禁点指定を待ってください。",
      "상대가 금지점을 표시할 때까지 기다려 주세요."
    );
    return true;
  }
  if (!gameState || !gameState.board || !gameState.board[y] || gameState.board[y][x] !== 0) {
    logI18n("禁着点必须标注在空点。", "Forbidden points must be empty.", "禁点は空点に指定してください。", "금지점은 빈 점에만 표시할 수 있습니다.");
    return true;
  }
  toggleRogueSealPoint(x, y);
  return true;
}

function finishRogueSealSelection() {
  rogueSealing = false;
  rogueSealWaitingForOpponent = false;
  pendingRogueSealPoints = [];
  rogueSealRequired = 0;
  const status = document.getElementById("seal-overlay");
  if (status) status.hidden = true;
  setSealStageClass(false);
  updateSealBanner("");
  if (!animFrameId) render();
}

function showOpponentSealWaiting() {
  rogueSealing = true;
  rogueSealWaitingForOpponent = true;
  pendingRogueSealPoints = [];
  setSealStageClass(true, true);
  updateSealBanner(sealSelectionText());
  if (!animFrameId) render();
}

window.startRogueSealSelection = startRogueSealSelection;
window.resetRogueSealSelection = resetRogueSealSelection;
window.handleRogueSealBoardClick = handleRogueSealBoardClick;
window.finishRogueSealSelection = finishRogueSealSelection;
window.showOpponentSealWaiting = showOpponentSealWaiting;
})();
