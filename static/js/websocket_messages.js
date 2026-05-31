// Legacy WebSocket message dispatch for the main browser client.

function renderIfIdle() {
  if (!animFrameId) render();
}

function handleGameStartMessage(msg) {
  clearGameLog();
  twoPlayerMode = !!msg.two_player;
  gameState = msg;
  syncChallengeSessionFromState(msg);
  myColor = msg.player_color;
  aiColor = msg.ai_color;
  lastAiMove = null;
  previousBoard = null;
  analysis = { winrate: 0.5, score: 0, top_moves: [], ownership: [], analysis_ready: false };
  analysisReady = false;
  resetWinrateHistory();
  isMyTurn = msg.ai_observer ? false : (twoPlayerMode ? true : (msg.current_player === myColor));
  reviewMode = false;
  sgfLoadedMode = false;
  resizeBoard(msg.size);
  render();
  setButtons(!msg.ai_observer);
  updateUI();
  updateChallengeInfo();
  updateWinRate(0.5);
  initTimers();
  if (timerMode !== "none") startTimerFor(msg.current_player);
  triggerBoardIntro();

  if (msg.ai_observer) {
    logStudyGameStart(msg);
  } else if (twoPlayerMode) {
    logI18n("双人对局开始 — 黑棋先行", "Two-player game started — Black moves first", "二人対局開始 — 黒番から", "2인 대국 시작 — 흑 선착");
  } else {
    logPlayerGameStart(msg);
  }
}

function logStudyGameStart(msg) {
  const blackLevel = msg.ai_level_black;
  const whiteLevel = msg.ai_level_white;
  logRender(() => {
    const blackRank = rankLabel(blackLevel) || blackLevel || "";
    const whiteRank = rankLabel(whiteLevel) || whiteLevel || "";
    return ui(
      `学习模式开始 — 黑 ${blackRank} / 白 ${whiteRank}`,
      `Study mode started — Black ${blackRank} / White ${whiteRank}`,
      `研究モード開始 — 黒 ${blackRank} / 白 ${whiteRank}`,
      `학습 모드 시작 — 흑 ${blackRank} / 백 ${whiteRank}`
    );
  });
}

function logPlayerGameStart(msg) {
  const playerColor = myColor;
  const gameLevel = msg.level;
  logRender(() => {
    const colorName = playerColor === "B" ? ui("黑", "Black", "黒", "흑") : ui("白", "White", "白", "백");
    const levelName = rankLabel(gameLevel) || gameLevel;
    return ui(
      `新对局 — 我执${colorName}棋，AI：${levelName}`,
      `New game — you play ${colorName}, AI: ${levelName}`,
      `新対局 — 持ち色 ${colorName}、AI: ${levelName}`,
      `새 대국 — 내 돌 ${colorName}, AI: ${levelName}`
    );
  });
}

function handleGameStateMessage(msg) {
  const oldBoard = previousBoard || (gameState ? gameState.board : null);
  gameState = msg;
  syncChallengeSessionFromState(msg);
  isMyTurn = msg.ai_observer ? false : (twoPlayerMode ? !msg.game_over : (msg.current_player === myColor));
  activeAiRogueCard = msg.ai_rogue_card || activeAiRogueCard || null;
  aiRogueSeals = msg.ai_rogue_seal_points || [];
  if (msg.rogue_seal_points) rogueSeals = msg.rogue_seal_points;

  if (oldBoard) {
    const newStone = detectNewStone(oldBoard, msg.board, msg.size || boardSize);
    const captured = detectCaptures(oldBoard, msg.board, msg.size || boardSize);
    if (newStone) {
      addPlaceAnimation(newStone.x, newStone.y);
      playStoneSound();
    }
    if (captured.length > 0) {
      addCaptureAnimation(captured);
      playCaptureSound(captured.length);
    }
  }
  previousBoard = msg.board.map(row => [...row]);

  if (msg.rogue_uses) {
    rogueUses = msg.rogue_uses;
    updateRogueBar();
  }
  if (ultimateMode) updateUltimateBar();
  syncCardTurnTimer();
  updateChallengeInfo();

  if (timerMode !== "none" && !msg.game_over) {
    onMoveCompleted(msg.current_player);
  }

  updateUI();
  renderIfIdle();
}

function handleAiMoveMessage(msg) {
  lastAiMove = msg;
  setThinking(false);
  clearTimeout(aiResponseTimer);
  if (msg.x !== null) {
    const gtp = `${COLS[msg.x]}${boardSize - msg.y}`;
    logI18n(
      `AI(${msg.color === "B" ? "黑" : "白"}) → ${gtp}`,
      `AI (${msg.color === "B" ? "Black" : "White"}) -> ${gtp}`,
      `AI（${msg.color === "B" ? "黒" : "白"}）→ ${gtp}`,
      `AI(${msg.color === "B" ? "흑" : "백"}) → ${gtp}`
    );
  } else {
    logI18n("AI 虚手", "AI passes", "AIパス", "AI 패스");
  }
  renderIfIdle();
}

function handleAnalysisMessage(msg) {
  analysis = msg;
  analysisReady = hasUsableAnalysis(msg);
  updateWinRate(msg.winrate);
  if (!analysisReady) {
    document.getElementById("info-score").textContent = "--";
    document.getElementById("info-territory").textContent = "--";
    setThinking(false);
    renderIfIdle();
    return;
  }
  if (!reviewMode) pushWinratePoint(msg.winrate, msg.score);
  const sc = msg.score;
  const unit = (gameState && gameState.komi === 7.5) ? "子" : "目";
  document.getElementById("info-score").textContent =
    sc > 0.5
      ? ui(`黑领先 ${sc.toFixed(1)}${unit}`, `Black +${sc.toFixed(1)} ${unit === "子" ? "stones" : "points"}`)
      : sc < -0.5
        ? ui(`白领先 ${Math.abs(sc).toFixed(1)}${unit}`, `White +${Math.abs(sc).toFixed(1)} ${unit === "子" ? "stones" : "points"}`)
        : ui("持平", "Even");

  if (msg.ownership && msg.ownership.length > 0) {
    const own = msg.ownership;
    let bTerr = 0;
    let wTerr = 0;
    own.forEach(v => { if (v > 0.5) bTerr++; else if (v < -0.5) wTerr++; });
    const diff = bTerr - wTerr;
    document.getElementById("info-territory").textContent =
      diff > 0
        ? ui(`黑多 ${diff} ${unit}`, `Black +${diff} ${unit === "子" ? "stones" : "points"}`)
        : diff < 0
          ? ui(`白多 ${Math.abs(diff)} ${unit}`, `White +${Math.abs(diff)} ${unit === "子" ? "stones" : "points"}`)
          : ui("均势", "Balanced");
  } else {
    document.getElementById("info-territory").textContent = "--";
  }
  setThinking(false);
  renderIfIdle();
}

function handleGameOverMessage(msg) {
  if (gameState) gameState.game_over = true;
  isMyTurn = false;
  setThinking(false);
  setButtons(false);
  stopTimerTick();
  clearCardTurnTimer();
  const winnerName = msg.winner === "B" ? ui("黑棋", "Black", "黒", "흑") : msg.winner === "W" ? ui("白棋", "White", "白", "백") : ui("平局", "Draw", "持碁", "무승부");
  const youWin = twoPlayerMode ? false : (msg.winner === myColor);
  const titleText = twoPlayerMode
    ? `${winnerName}${ui("胜！", " wins!")}`
    : (youWin ? ui("你赢了！", "You win!") : msg.winner ? ui("AI 胜利", "AI wins") : ui("平局", "Draw"));
  const scoreRaw = msg.score || "";
  const scoreKomi = gameState?.komi;
  const scoreDisplay = formatScoreDisplay(scoreRaw, scoreKomi);
  showOverlay(titleText, reasonText(msg.reason), winnerName, scoreDisplay);
  logGameOverMessage(msg, scoreRaw, scoreKomi);
  handleChallengeGameOver(msg, youWin);
}

function logGameOverMessage(msg, scoreRaw, scoreKomi) {
  const winnerCode = msg.winner;
  const reasonCode = msg.reason;
  logRender(() => {
    const winner = winnerCode === "B" ? ui("黑棋", "Black", "黒", "흑") : winnerCode === "W" ? ui("白棋", "White", "白", "백") : ui("平局", "Draw", "持碁", "무승부");
    const score = formatScoreDisplay(scoreRaw, scoreKomi);
    const reason = reasonText(reasonCode);
    return ui(
      `${winner}胜 ${score} (${reason})`,
      `${winner} wins ${score} (${reason})`,
      `${winner}勝ち ${score} (${reason})`,
      `${winner} 승 ${score} (${reason})`
    );
  });
}

function handleChallengeGameOver(msg, youWin) {
  if (!gameState?.challenge_beta) return;
  const currentStage = gameState.challenge_stage || challengeSession.stage || 1;
  if (youWin && currentStage === 1) {
    challengeSession.active = true;
    challengeSession.stage = 2;
    challengeSession.cards = Array.isArray(gameState.challenge_cards) ? [...gameState.challenge_cards] : [];
    challengeSession.refreshes = (gameState.challenge_refreshes || 0) + 1;
    challengeSession.limits = {
      undo: (gameState.challenge_limits?.undo || challengeSession.limits.undo || 0) + 3,
      hint: (gameState.challenge_limits?.hint || challengeSession.limits.hint || 0) + 10,
      coach: (gameState.challenge_limits?.coach || challengeSession.limits.coach || 0) + 3,
    };
    challengeSession.remaining = { ...challengeSession.limits };
    updateChallengeInfo();
    setTimeout(() => {
      showConfirmModal(
        ui("已通过第 1 关，进入第 2 关。你将执白并按让 2 子开局，同时再选 1 张卡。", "Stage 1 cleared. Start Stage 2 as White with a 2-stone handicap opening and one more card?"),
        () => {
          closeOverlay();
          document.getElementById("btn-new").click();
        }
      );
    }, 120);
  } else if (youWin && currentStage >= 2) {
    challengeSession.cleared = true;
    challengeSession.active = true;
    updateChallengeInfo();
    logI18n("闯关前两关已通关。", "Challenge cleared.", "チャレンジの最初の2面を突破しました。", "도전 첫 두 단계를 통과했습니다.");
  }
}

function handleReconnectedMessage(msg) {
  twoPlayerMode = !!msg.two_player;
  gameState = msg;
  syncChallengeSessionFromState(msg);
  myColor = msg.player_color;
  aiColor = msg.ai_color;
  lastAiMove = null;
  previousBoard = msg.board ? msg.board.map(row => [...row]) : null;
  resetWinrateHistory();
  isMyTurn = msg.ai_observer ? false : (twoPlayerMode ? !msg.game_over : (msg.current_player === myColor));
  activeRogueCard = msg.rogue_card || null;
  rogueUses = msg.rogue_uses || {};
  rogueSeals = msg.rogue_seal_points || [];
  activeAiRogueCard = msg.ai_rogue_card || null;
  aiRogueSeals = msg.ai_rogue_seal_points || [];
  rogueSealing = false;
  puppetMode = false;
  updateRogueBar();
  syncCardTurnTimer();
  updateChallengeInfo();
  ultimateMode = !!msg.ultimate;
  ultimatePlayerCard = msg.ultimate_player_card || null;
  ultimateAiCard = msg.ultimate_ai_card || null;
  if (ultimateMode) updateUltimateBar();
  resizeBoard(msg.size);
  render();
  setButtons(!msg.game_over);
  updateUI();
  logI18n(
    `已恢复对局（第${msg.move_number}手）`,
    `Game restored (move ${msg.move_number})`,
    `対局を復元しました（${msg.move_number}手）`,
    `대국을 복원했습니다(${msg.move_number}수)`
  );
  if (msg.game_over) logI18n("对局已结束", "The game is already over", "対局は終了しています", "대국이 이미 종료되었습니다");
}

function handleReconnectFailedMessage() {
  logI18n(
    "暂无进行中的对局，请点击「开始对弈」开始",
    "No active game was found. Click Start Game to begin.",
    "進行中の対局はありません。「対局開始」を押してください",
    "진행 중인 대국이 없습니다. 「대국 시작」을 눌러 시작하세요"
  );
}

function handleErrorMessage(msg) {
  logServerEvent(msg.message, "⚠ ");
  setThinking(false);
  if (previousBoard && gameState) {
    gameState.board = previousBoard.map(row => [...row]);
  }
  if (gameState && !gameState.game_over) {
    isMyTurn = twoPlayerMode || (gameState.current_player === myColor);
  }
  renderIfIdle();
}

function handleLevelSetMessage(msg) {
  const selectedLevel = msg.level;
  logRender(() => {
    const levelName = rankLabel(selectedLevel) || selectedLevel;
    return ui(`级别 → ${levelName}`, `Level -> ${levelName}`, `棋力 → ${levelName}`, `기력 → ${levelName}`);
  });
  if (gameState) gameState.level = msg.level;
  updateUI();
}

function handleRogueCardSelectedMessage(msg) {
  gameState = msg;
  syncChallengeSessionFromState(msg);
  activeRogueCard = msg.card_id;
  rogueUses = msg.rogue_uses || {};
  rogueSeals = msg.rogue_seal_points || [];
  activeAiRogueCard = msg.ai_rogue_card || activeAiRogueCard || null;
  aiRogueSeals = msg.ai_rogue_seal_points || aiRogueSeals || [];
  document.getElementById("rogue-overlay").classList.remove("show");
  updateRogueBar();
  syncCardTurnTimer();
  renderIfIdle();
  if (msg.waiting_seal) {
    rogueSealing = true;
    document.getElementById("seal-overlay").style.display = "block";
  }
  showCardEffectVisual(msg.card_name || getRogueCardName(msg.card_id), "rogue");
  logRogueCardSelected(msg);
}

function logRogueCardSelected(msg) {
  const cardIcon = msg.icon || "";
  const cardId = msg.card_id;
  logRender(() => ui(
    `🃏 已选择强化卡：${cardIcon} ${getRogueCardName(cardId)}`,
    `🃏 Card selected: ${cardIcon} ${getRogueCardName(cardId)}`,
    `🃏 強化カード選択：${cardIcon} ${getRogueCardName(cardId)}`,
    `🃏 강화 카드 선택: ${cardIcon} ${getRogueCardName(cardId)}`
  ));
}

function handleRogueAiSelectedMessage(msg) {
  gameState = msg;
  activeAiRogueCard = msg.card_id;
  aiRogueSeals = msg.ai_rogue_seal_points || [];
  updateRogueBar();
  renderIfIdle();
  showCardEffectVisual(msg.card_name || getRogueCardName(msg.card_id), "rogue");
  logRogueAiSelected(msg);
}

function logRogueAiSelected(msg) {
  const cardIcon = msg.icon || "";
  const cardId = msg.card_id;
  logRender(() => ui(
    `🤖 AI 启用了 Rogue 卡：${cardIcon} ${getRogueCardName(cardId)}`,
    `🤖 The AI equipped a Rogue card: ${cardIcon} ${getRogueCardName(cardId)}`,
    `🤖 AIがRogueカードを装備：${cardIcon} ${getRogueCardName(cardId)}`,
    `🤖 AI가 Rogue 카드를 장착: ${cardIcon} ${getRogueCardName(cardId)}`
  ));
}

function handleRogueSealUpdateMessage(msg) {
  document.getElementById("seal-hint").textContent =
    ui(`🚫 请在棋盘上点击封印点（剩余 ${msg.remaining} 个）`, `🚫 Click points on the board to seal them (${msg.remaining} left)`);
  rogueSeals = msg.points;
  renderIfIdle();
}

function handleRogueSealDoneMessage() {
  rogueSealing = false;
  document.getElementById("seal-overlay").style.display = "none";
  logI18n("🚫 四道封印已设定！", "🚫 Four seals are now in place!", "🚫 4つの封印を設定しました！", "🚫 네 개의 봉인이 설정되었습니다!");
  renderIfIdle();
}

function handleRogueEventMessage(msg) {
  showCardEffectVisual(msg.msg, "rogue");
  triggerSignatureCardEffect(msg.msg);
  logServerEvent(msg.msg);
}

function handleRogueUsesUpdateMessage(msg) {
  rogueUses = msg.uses || {};
  updateRogueBar();
}

function handleUltimateCardsSelectedMessage(msg) {
  gameState = msg;
  ultimateMode = true;
  ultimatePlayerCard = msg.player_card;
  ultimateAiCard = msg.ai_card;
  ultimatePlayerName = "";
  ultimateAiName = "";
  document.getElementById("ultimate-overlay").classList.remove("show");
  updateUltimateBar();
  syncCardTurnTimer();
  renderIfIdle();
  showCardEffectVisual(msg.player_card, "ultimate");
  logUltimateCardsSelected(msg);
  logI18n("20 手决胜开始！", "The 20-move showdown begins!", "20手決戦開始！", "20수 승부 시작!");
}

function logUltimateCardsSelected(msg) {
  const playerIcon = msg.player_icon || "";
  const playerCard = msg.player_card;
  const aiIcon = msg.ai_icon || "";
  const aiCard = msg.ai_card;
  logRender(() => ui(
    `🃏 你选择了 ${playerIcon} ${getUltimateCardName(playerCard)}`,
    `🃏 You chose ${playerIcon} ${getUltimateCardName(playerCard)}`,
    `🃏 ${playerIcon} ${getUltimateCardName(playerCard)}を選択`,
    `🃏 ${playerIcon} ${getUltimateCardName(playerCard)} 선택`
  ));
  logRender(() => ui(
    `🤖 AI 选择了 ${aiIcon} ${getUltimateCardName(aiCard)}`,
    `🤖 The AI chose ${aiIcon} ${getUltimateCardName(aiCard)}`,
    `🤖 AIが${aiIcon} ${getUltimateCardName(aiCard)}を選択`,
    `🤖 AI가 ${aiIcon} ${getUltimateCardName(aiCard)} 선택`
  ));
}

const LEGACY_WEBSOCKET_MESSAGE_HANDLERS = {
  game_start: handleGameStartMessage,
  game_state: handleGameStateMessage,
  ai_move: handleAiMoveMessage,
  analysis: handleAnalysisMessage,
  game_over: handleGameOverMessage,
  reconnected: handleReconnectedMessage,
  reconnect_failed: handleReconnectFailedMessage,
  error: handleErrorMessage,
  level_set: handleLevelSetMessage,
  rogue_offer: msg => showRogueCards(msg.cards, msg),
  rogue_card_selected: handleRogueCardSelectedMessage,
  rogue_ai_selected: handleRogueAiSelectedMessage,
  rogue_seal_update: handleRogueSealUpdateMessage,
  rogue_seal_done: handleRogueSealDoneMessage,
  rogue_event: handleRogueEventMessage,
  rogue_uses_update: handleRogueUsesUpdateMessage,
  ultimate_offer: msg => showUltimateCards(msg.cards),
  ultimate_cards_selected: handleUltimateCardsSelectedMessage,
};

function handleMessage(msg) {
  const handler = LEGACY_WEBSOCKET_MESSAGE_HANDLERS[msg?.type];
  if (handler) handler(msg);
}

window.handleMessage = handleMessage;
