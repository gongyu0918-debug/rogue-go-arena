// Legacy in-game toolbar actions and toolbar button state.

const ACTIVE_TOOLBAR_BUTTON_IDS = ["btn-pass", "btn-undo", "btn-resign"];
const SCORE_WINRATE_THRESHOLD = 80;

function copyBoard(board) {
  return board.map(row => [...row]);
}

function snapshotCurrentBoard() {
  previousBoard = gameState ? copyBoard(gameState.board) : null;
}

function endLocalTurnForAi() {
  if (!twoPlayerMode) {
    isMyTurn = false;
    setThinking(true);
  }
}

function isQuickThinkPassActive() {
  return ultimateMode && ultimatePlayerCard === "quickthink" && gameState.ultimate_quickthink_active;
}

function blackWinratePercentForAction() {
  const wr = analysis ? analysis.winrate : 0.5;
  return wr * 100;
}

function blackWinratePercentForButton() {
  const wr = analysis ? Number(analysis.winrate) : 0.5;
  return Number.isFinite(wr) ? wr * 100 : 50;
}

function isScoreBelowThreshold(blackPct) {
  return blackPct < SCORE_WINRATE_THRESHOLD && (100 - blackPct) < SCORE_WINRATE_THRESHOLD;
}

function canRequestScore(active, panelEnabled) {
  return active && panelEnabled && analysisReady && !isScoreBelowThreshold(blackWinratePercentForButton());
}

function setDisabled(id, disabled) {
  const el = document.getElementById(id);
  if (el) el.disabled = disabled;
}

function setControlLockStyle(el, locked) {
  el.style.opacity = locked ? "0.5" : "";
  el.style.cursor = locked ? "not-allowed" : "";
}

function syncUndoButton(active) {
  const btnUndo = document.getElementById("btn-undo");
  if (!btnUndo) return;
  if (gameState && gameState.rogue_undo_disabled) {
    btnUndo.disabled = true;
    btnUndo.title = ui("当前卡牌禁用悔棋", "Undo disabled by current card");
  } else if (active) {
    btnUndo.title = ui("悔棋", "Undo");
  }
}

function syncScoreButton(active) {
  const btnScore = document.getElementById("btn-score");
  if (!btnScore) return;
  const enabled = analysisPanelEnabled();
  const canScore = canRequestScore(active, enabled);
  btnScore.disabled = !canScore;
  btnScore.title = canScore
    ? ui("计算胜负", "Score")
    : (enabled ? ui("胜率需≥80%才可计算胜负", "Win rate must reach 80% to score") : ui("计算胜负", "Score"));
}

function syncNewGameButton(gameActive) {
  const btnNew = document.getElementById("btn-new");
  if (!btnNew) return;
  btnNew.disabled = gameActive;
  btnNew.textContent = gameActive ? ui("对局进行中…", "Game Active...") : ui("确认开始", "Start");
  setControlLockStyle(btnNew, gameActive);
}

function syncSetupButton(gameActive) {
  const btnSetup = document.getElementById("btn-setup");
  if (!btnSetup) return;
  btnSetup.disabled = gameActive;
  setControlLockStyle(btnSetup, gameActive);
}

function handlePassAction() {
  if (!twoPlayerMode && !isMyTurn) return;
  if (!gameState || gameState.game_over) return;
  const passColor = twoPlayerMode ? gameState.current_player : myColor;
  snapshotCurrentBoard();
  if (isQuickThinkPassActive()) {
    sendWS({ action: "ultimate_quickthink_end" });
    endLocalTurnForAi();
    logI18n("快速思考结束，轮到 AI 读盘", "Quick Thinking ended. The AI is reading the board.", "クイック思考終了。AIの読み番です", "빠른 사고 종료, AI가 판을 읽습니다");
    return;
  }
  sendWS({ action: "pass" });
  endLocalTurnForAi();
  logI18n(
    `${passColor === "B" ? "黑棋" : "白棋"} 虚手`,
    `${passColor === "B" ? "Black" : "White"} passes`,
    `${passColor === "B" ? "黒" : "白"} パス`,
    `${passColor === "B" ? "흑" : "백"} 패스`
  );
}

function handleUndoAction() {
  if (gameState && gameState.rogue_undo_disabled) {
    logI18n("当前卡牌效果禁用了悔棋", "Undo is disabled by the current card", "現在のカード効果で待ったは使えません", "현재 카드 효과로 무르기를 사용할 수 없습니다");
    return;
  }
  snapshotCurrentBoard();
  sendWS({ action: "undo" });
  setThinking(false);
  logI18n("请求悔棋", "Undo requested", "待ったを要求", "무르기 요청");
}

function handleScoreAction() {
  if (isScoreBelowThreshold(blackWinratePercentForAction())) {
    logI18n("⚠ 胜率未达80%，暂不可计算胜负", "⚠ Win rate is below 80%, scoring is unavailable", "⚠ 勝率が80%未満のため終局計算できません", "⚠ 승률이 80% 미만이라 계가할 수 없습니다");
    return;
  }
  showConfirmModal(ui("是否进行形势计算并申请终局？", "Run scoring and request endgame?"), () => {
    sendWS({ action: "score" });
    logI18n("请求终局计分…", "Requesting endgame scoring...", "終局計算を要求中…", "종국 계가 요청 중…");
  });
}

function handleResignAction() {
  showConfirmModal(ui("您确定要认输吗？", "Are you sure you want to resign?"), () => {
    sendWS({ action: "resign" });
    setButtons(false);
    logI18n("你认输了", "You resigned", "投了しました", "불계패했습니다");
  });
}

function setButtons(active) {
  ACTIVE_TOOLBAR_BUTTON_IDS.forEach(id => setDisabled(id, !active));
  syncUndoButton(active);
  syncScoreButton(active);
  syncNewGameButton(active);
  syncSetupButton(active);
}

function bindToolbarActions() {
  document.getElementById("btn-pass")?.addEventListener("click", handlePassAction);
  document.getElementById("btn-undo")?.addEventListener("click", handleUndoAction);
  document.getElementById("btn-score")?.addEventListener("click", handleScoreAction);
  document.getElementById("btn-resign")?.addEventListener("click", handleResignAction);
}

bindToolbarActions();

window.setButtons = setButtons;
window.handlePassAction = handlePassAction;
window.handleUndoAction = handleUndoAction;
window.handleScoreAction = handleScoreAction;
window.handleResignAction = handleResignAction;
