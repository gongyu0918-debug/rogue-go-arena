// Card-driven turn timers, used by Rogue Quick Thinking and Ultimate Quick Thinking.

function clearCardTurnTimer() {
  if (cardTurnTimer) {
    clearTimeout(cardTurnTimer);
    cardTurnTimer = null;
  }
  if (cardTurnTick) {
    clearInterval(cardTurnTick);
    cardTurnTick = null;
  }
  cardTurnDeadline = 0;
  cardTurnRemaining = 0;
  cardTurnLabel = "";
  cardTurnKey = "";
}

function startCardTurnTimer(seconds, key, label, onExpire) {
  clearCardTurnTimer();
  cardTurnDeadline = performance.now() + seconds * 1000;
  cardTurnRemaining = seconds;
  cardTurnLabel = label;
  cardTurnKey = key;
  updateUI();
  cardTurnTick = setInterval(() => {
    cardTurnRemaining = Math.max(0, (cardTurnDeadline - performance.now()) / 1000);
    updateUI();
  }, 100);
  cardTurnTimer = setTimeout(() => {
    cardTurnRemaining = 0;
    updateUI();
    clearCardTurnTimer();
    onExpire();
  }, Math.max(0, seconds * 1000));
}

function syncCardTurnTimer() {
  if (!gameState || gameState.game_over || twoPlayerMode || !isMyTurn) {
    clearCardTurnTimer();
    return;
  }

  if (activeRogueCard === "quickthink" && gameState.rogue_quickthink_stage > 0) {
    const seconds = gameState.rogue_quickthink_seconds || (gameState.rogue_quickthink_stage === 1 ? 1 : 0.5);
    const key = `rq:${gameState.move_number}:${gameState.rogue_quickthink_stage}`;
    if (cardTurnKey !== key) {
      logI18n(
        `⚡ 快速思考：${seconds} 秒内完成这一手`,
        `⚡ Quick Thinking: finish this move within ${seconds} seconds.`,
        `⚡ クイック思考：${seconds}秒以内に着手`,
        `⚡ 빠른 사고: ${seconds}초 안에 착수`
      );
      startCardTurnTimer(seconds, key, ui("快棋", "Fast"), () => {
        // Safety: do not auto-pass if it's no longer the player's turn.
        if (!isMyTurn || (gameState && gameState.current_player !== myColor)) return;
        logI18n("⚡ 快速思考超时，自动虚手", "⚡ Quick Thinking timed out. Auto-pass.", "⚡ クイック思考が時間切れになり、自動パス", "⚡ 빠른 사고 시간 초과, 자동 패스");
        sendWS({ action: "pass" });
        if (!twoPlayerMode) {
          isMyTurn = false;
          setThinking(true);
        }
      });
    }
    return;
  }

  if (ultimateMode && ultimatePlayerCard === "quickthink" && gameState.ultimate_quickthink_active) {
    const seconds = gameState.ultimate_quickthink_seconds || 5;
    const key = `uq:${gameState.ultimate_quickthink_token || 0}:${seconds}`;
    if (cardTurnKey !== key) {
      logI18n(
        `⚡ 大招快速思考：${seconds} 秒自由落子开始`,
        `⚡ Ultimate Quick Thinking: free placement begins for ${seconds} seconds.`,
        `⚡ 必殺クイック思考：${seconds}秒の自由着手開始`,
        `⚡ 궁극기 빠른 사고: ${seconds}초 자유 착수 시작`
      );
      startCardTurnTimer(seconds, key, ui("自由落子", "Free"), () => {
        // Safety: do not end quickthink if it's no longer the player's turn.
        if (!isMyTurn || (gameState && gameState.current_player !== myColor)) return;
        logI18n("⚡ 自由落子时间结束，AI 开始读盘", "⚡ Free placement ended. The AI is reading the board.", "⚡ 自由着手時間が終了し、AIが読みを開始", "⚡ 자유 착수 시간이 끝나 AI가 판을 읽습니다");
        sendWS({ action: "ultimate_quickthink_end" });
        if (!twoPlayerMode) {
          isMyTurn = false;
          setThinking(true);
        }
      });
    }
    return;
  }

  clearCardTurnTimer();
}
