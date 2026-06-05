// Board pointer, hover, and fine-tune placement handling.

let fineTunePos = null;
let hoverXY = null;
let lastPlayTime = 0;
let aiResponseTimer = null;
let exchangeModeActive = false;
let exchangeModeSource = null;

function updateFinetuneUI() {
  const ui = document.getElementById("finetune-ui");
  if (!ui) return;
  if (!fineTunePos || reviewMode) {
    ui.classList.remove("show");
    return;
  }
  ui.classList.add("show");

  const rect = canvas.getBoundingClientRect();
  const cCont = document.getElementById("board-container").getBoundingClientRect();

  const internalX = PAD + fineTunePos.x * CELL;
  const internalY = PAD + fineTunePos.y * CELL;

  const logicalSize = boardRenderSize || Math.round(canvas.width / boardRenderDpr);
  const displayX = (internalX / logicalSize) * rect.width;
  const displayY = (internalY / logicalSize) * rect.height;

  const offsetX = displayX + (rect.left - cCont.left);
  const offsetY = displayY + (rect.top - cCont.top);

  ui.style.left = offsetX + "px";
  ui.style.top = offsetY + "px";
}

function boardXY(e) {
  const rect = canvas.getBoundingClientRect();
  const logicalSize = boardRenderSize || Math.round(canvas.width / boardRenderDpr);
  const sx = logicalSize / rect.width;
  const sy = logicalSize / rect.height;
  const clientX = e.touches ? e.touches[0].clientX : e.clientX;
  const clientY = e.touches ? e.touches[0].clientY : e.clientY;
  const x = Math.round(((clientX - rect.left) * sx - PAD) / CELL);
  const y = Math.round(((clientY - rect.top) * sy - PAD) / CELL);
  return { x, y };
}

function isCoachTakingOver() {
  return !twoPlayerMode
    && activeRogueCard === "coach_mode"
    && (gameState?.rogue_coach_moves_left || 0) > 0;
}

function tryPlay(x, y) {
  const now = Date.now();
  const minGap = (ultimateMode && ultimatePlayerCard === "quickthink" && gameState?.ultimate_quickthink_active) ? 80 : 400;
  if (now - lastPlayTime < minGap) return; // debounce touch+click dual-fire
  if (reviewMode) return;
  if (!gameState || gameState.game_over) return;
  if (isCoachTakingOver()) {
    logI18n("🎓 代练上号接管中，请等待强化 AI 完成代打。", "🎓 Coach is controlling this phase. Wait for the boosted AI to finish.", "🎓 コーチモードが代打中です。強化AIの着手完了をお待ちください。", "🎓 코치 모드가 대리 착수 중입니다. 강화 AI가 마칠 때까지 기다려 주세요.");
    return;
  }
  if (!twoPlayerMode && !isMyTurn) return;
  if (x < 0 || x >= boardSize || y < 0 || y >= boardSize) return;

  const mode = document.getElementById("sel-placement").value;
  if (mode === "fine") {
    fineTunePos = { x, y };
    if (!animFrameId) render();
    return;
  }

  if (gameState.board[y][x] !== 0) return;
  if (gameState.ko_point && gameState.ko_point[0] === x && gameState.ko_point[1] === y) return;
  if (activeRogueCard === "puppet"
      && gameState.rogue_puppet_target
      && gameState.rogue_puppet_target[0] === x
      && gameState.rogue_puppet_target[1] === y) {
    logI18n("🎭 这个点已被傀儡术预留给 AI", "🎭 This point is reserved for the AI by Puppet.", "🎭 この点は傀儡術でAI用に予約済みです", "🎭 이 지점은 꼭두각시술로 AI에게 예약되었습니다");
    return;
  }
  commitPlay(x, y);
}

function handleExchangeClick(x, y) {
  if (isCoachTakingOver()) {
    logI18n("🎓 代练上号接管中，暂时不能使用乾坤挪移。", "🎓 Coach is controlling this phase. Exchange is paused.", "🎓 コーチモードが代打中のため、交換は使えません。", "🎓 코치 모드가 대리 착수 중이라 교환을 사용할 수 없습니다.");
    return true;
  }
  if (!exchangeModeActive || !gameState || activeRogueCard !== "exchange" || (rogueUses.exchange || 0) <= 0) {
    exchangeModeActive = false;
    exchangeModeSource = null;
    return false;
  }
  if (!twoPlayerMode && !isMyTurn) return true;
  const playerVal = (twoPlayerMode ? gameState.current_player : myColor) === "B" ? 1 : 2;
  const oppVal = 3 - playerVal;
  if (!exchangeModeSource) {
    if (gameState.board[y][x] !== oppVal) {
      logI18n("🔄 乾坤挪移：先选择一颗对方棋子", "🔄 Exchange: choose one opponent stone first.", "🔄 交換：まず相手の石を選択", "🔄 교환: 먼저 상대 돌 하나를 선택하세요");
      return true;
    }
    exchangeModeSource = { x, y };
    logI18n("🔄 再选择一个空点作为摆动目标", "🔄 Now choose an empty destination.", "🔄 次に空点を移動先として選択", "🔄 이제 빈 점을 이동 목적지로 선택하세요");
    if (!animFrameId) render();
    return true;
  }
  const source = exchangeModeSource;
  if (gameState.board[y][x] !== 0) {
    logI18n("🔄 目标必须是空点", "🔄 Destination must be empty.", "🔄 移動先は空点である必要があります", "🔄 목적지는 빈 점이어야 합니다");
    return true;
  }
  exchangeModeSource = null;
  exchangeModeActive = false;
  sendWS({ action: "rogue_use_exchange", from_x: source.x, from_y: source.y, to_x: x, to_y: y });
  return true;
}

function commitPlay(x, y) {
  closeWoodSelectMenu();
  if (gameState.board[y][x] !== 0) return;
  fineTunePos = null;
  updateFinetuneUI();

  const methodicalRemaining = Number(gameState?.rogue_methodical_remaining || 0);
  const methodicalContinues = (
    (activeRogueCard === "methodical" || gameState?.rogue_card === "methodical") &&
    methodicalRemaining > 1
  );
  const expectsAi = !(
    (activeRogueCard === "quickthink" && gameState?.rogue_quickthink_stage === 1) ||
    (ultimateMode && ultimatePlayerCard === "quickthink" && gameState?.ultimate_quickthink_active) ||
    methodicalContinues
  );

  lastPlayTime = Date.now();
  previousBoard = gameState.board.map(row => [...row]);

  const myVal = (twoPlayerMode ? gameState.current_player : myColor) === "B" ? 1 : 2;
  gameState.board[y][x] = myVal;
  addPlaceAnimation(x, y);
  playStoneSound();
  if (!animFrameId) render();

  sendWS({ action: "play", x, y });
  if (!twoPlayerMode) {
    quickthinkAwaitingAiMove = expectsAi && activeRogueCard === "quickthink";
    isMyTurn = !expectsAi;
    setThinking(expectsAi);
    clearTimeout(aiResponseTimer);
    aiResponseTimer = setTimeout(() => {
      if (!isMyTurn && gameState && !gameState.game_over) {
        logI18n("⚠ AI 响应超时，尝试重新请求…", "⚠ AI response timed out. Retrying...", "⚠ AIの応答がタイムアウトしました。再要求中…", "⚠ AI 응답 시간 초과, 다시 요청 중…");
        sendWS({ action: "request_hint" });
        setThinking(false);
        if (gameState) isMyTurn = (gameState.current_player === myColor);
      }
    }, 30000);
  }
}

canvas.addEventListener("click", e => {
  closeWoodSelectMenu();
  const {x, y} = boardXY(e);
  if (x < 0 || x >= boardSize || y < 0 || y >= boardSize) return;
  if (rogueSealing) {
    if (handleRogueSealBoardClick(x, y)) return;
    return;
  }
  if (puppetMode) {
    if (isCoachTakingOver()) {
      logI18n("🎓 代练上号接管中，暂时不能指定傀儡点。", "🎓 Coach is controlling this phase. Puppet targeting is paused.", "🎓 コーチモードが代打中のため、傀儡点は指定できません。", "🎓 코치 모드가 대리 착수 중이라 꼭두각시 지점을 지정할 수 없습니다.");
      return;
    }
    puppetMode = false;
    sendWS({ action: "rogue_use_puppet", x, y });
    return;
  }
  if (exchangeModeActive || exchangeModeSource) {
    if (handleExchangeClick(x, y)) return;
  }
  tryPlay(x, y);
});

canvas.addEventListener("mousemove", e => {
  if (reviewMode) return;
  const {x, y} = boardXY(e);
  hoverXY = {x, y};
  if (!animFrameId) render();
});

canvas.addEventListener("mouseleave", () => {
  hoverXY = null;
  if (!animFrameId) render();
});

canvas.addEventListener("touchend", e => {
  e.preventDefault();
  closeWoodSelectMenu();
  if (!e.changedTouches || !e.changedTouches[0]) return;
  const touch = e.changedTouches[0];
  const {x, y} = boardXY(touch);
  if (x < 0 || x >= boardSize || y < 0 || y >= boardSize) return;
  if (rogueSealing) {
    if (handleRogueSealBoardClick(x, y)) return;
    return;
  }
  if (puppetMode) {
    if (isCoachTakingOver()) {
      logI18n("🎓 代练上号接管中，暂时不能指定傀儡点。", "🎓 Coach is controlling this phase. Puppet targeting is paused.", "🎓 コーチモードが代打中のため、傀儡点は指定できません。", "🎓 코치 모드가 대리 착수 중이라 꼭두각시 지점을 지정할 수 없습니다.");
      return;
    }
    puppetMode = false;
    sendWS({ action: "rogue_use_puppet", x, y });
    return;
  }
  if (exchangeModeActive || exchangeModeSource) {
    if (handleExchangeClick(x, y)) return;
  }
  tryPlay(x, y);
}, { passive: false });

canvas.addEventListener("touchstart", e => { e.preventDefault(); }, { passive: false });

document.getElementById("ft-up").addEventListener("click", () => { if(fineTunePos) { fineTunePos.y = Math.max(0, fineTunePos.y-1); render(); }});
document.getElementById("ft-down").addEventListener("click", () => { if(fineTunePos) { fineTunePos.y = Math.min(boardSize-1, fineTunePos.y+1); render(); }});
document.getElementById("ft-left").addEventListener("click", () => { if(fineTunePos) { fineTunePos.x = Math.max(0, fineTunePos.x-1); render(); }});
document.getElementById("ft-right").addEventListener("click", () => { if(fineTunePos) { fineTunePos.x = Math.min(boardSize-1, fineTunePos.x+1); render(); }});
document.getElementById("ft-ok").addEventListener("click", () => {
  if(fineTunePos) commitPlay(fineTunePos.x, fineTunePos.y);
});
