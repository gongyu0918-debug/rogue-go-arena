// Legacy in-game toolbar actions and toolbar button state.

function handlePassAction() {
  if (!twoPlayerMode && !isMyTurn) return;
  if (!gameState || gameState.game_over) return;
  const passColor = twoPlayerMode ? gameState.current_player : myColor;
  previousBoard = gameState.board.map(row => [...row]);
  if (ultimateMode && ultimatePlayerCard === "quickthink" && gameState.ultimate_quickthink_active) {
    sendWS({ action: "ultimate_quickthink_end" });
    if (!twoPlayerMode) {
      isMyTurn = false;
      setThinking(true);
    }
    logI18n("快速思考结束，轮到 AI 读盘", "Quick Thinking ended. The AI is reading the board.", "クイック思考終了。AIの読み番です", "빠른 사고 종료, AI가 판을 읽습니다");
    return;
  }
  sendWS({ action: "pass" });
  if (!twoPlayerMode) {
    isMyTurn = false;
    setThinking(true);
  }
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
  previousBoard = gameState ? gameState.board.map(row => [...row]) : null;
  sendWS({ action: "undo" });
  setThinking(false);
  logI18n("请求悔棋", "Undo requested", "待ったを要求", "무르기 요청");
}

function handleScoreAction() {
  const wr = analysis ? analysis.winrate : 0.5;
  const blackPct = wr * 100;
  if (blackPct < 80 && (100 - blackPct) < 80) {
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
  ["btn-pass", "btn-undo", "btn-resign"].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.disabled = !active;
  });
  const btnUndo = document.getElementById("btn-undo");
  if (btnUndo) {
    if (gameState && gameState.rogue_undo_disabled) {
      btnUndo.disabled = true;
      btnUndo.title = ui("当前卡牌禁用悔棋", "Undo disabled by current card");
    } else if (active) {
      btnUndo.title = ui("悔棋", "Undo");
    }
  }
  const btnScore = document.getElementById("btn-score");
  if (btnScore) {
    const enabled = analysisPanelEnabled();
    const wr = analysis ? Number(analysis.winrate) : 0.5;
    const bPct = Number.isFinite(wr) ? wr * 100 : 50;
    const canScore = active && enabled && analysisReady && (bPct >= 80 || (100 - bPct) >= 80);
    if (!canScore) {
      btnScore.disabled = true;
      btnScore.title = enabled
        ? ui("胜率需≥80%才可计算胜负", "Win rate must reach 80% to score")
        : ui("计算胜负", "Score");
    } else {
      btnScore.disabled = false;
      btnScore.title = ui("计算胜负", "Score");
    }
  }
  const btnNew = document.getElementById("btn-new");
  if (btnNew) {
    if (active) {
      btnNew.disabled = true;
      btnNew.textContent = ui("对局进行中…", "Game Active...");
      btnNew.style.opacity = "0.5";
      btnNew.style.cursor = "not-allowed";
    } else {
      btnNew.disabled = false;
      btnNew.textContent = ui("确认开始", "Start");
      btnNew.style.opacity = "";
      btnNew.style.cursor = "";
    }
  }
  const btnSetup = document.getElementById("btn-setup");
  if (btnSetup) {
    if (active) {
      btnSetup.disabled = true;
      btnSetup.style.opacity = "0.5";
      btnSetup.style.cursor = "not-allowed";
    } else {
      btnSetup.disabled = false;
      btnSetup.style.opacity = "";
      btnSetup.style.cursor = "";
    }
  }
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
