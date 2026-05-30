// Challenge-session state and small runtime board helpers for the legacy client.

let challengeSession = {
  active: false,
  stage: 1,
  cards: [],
  refreshes: 0,
  limits: { undo: 3, hint: 10, coach: 3 },
  remaining: { undo: 3, hint: 10, coach: 3 },
  cleared: false,
};

function resetChallengeSession() {
  challengeSession = {
    active: true,
    stage: 1,
    cards: [],
    refreshes: 0,
    limits: { undo: 3, hint: 10, coach: 3 },
    remaining: { undo: 3, hint: 10, coach: 3 },
    cleared: false,
  };
}

function syncChallengeSessionFromState(state) {
  if (!state || !state.challenge_beta) return;
  challengeSession.active = true;
  challengeSession.stage = state.challenge_stage || challengeSession.stage || 1;
  challengeSession.cards = Array.isArray(state.challenge_cards) ? [...state.challenge_cards] : [...challengeSession.cards];
  challengeSession.refreshes = Number.isFinite(state.challenge_refreshes) ? state.challenge_refreshes : challengeSession.refreshes;
  if (state.challenge_limits) {
    challengeSession.limits = {
      undo: state.challenge_limits.undo ?? challengeSession.limits.undo,
      hint: state.challenge_limits.hint ?? challengeSession.limits.hint,
      coach: state.challenge_limits.coach ?? challengeSession.limits.coach,
    };
  }
  if (state.challenge_remaining) {
    challengeSession.remaining = {
      undo: state.challenge_remaining.undo ?? challengeSession.remaining.undo,
      hint: state.challenge_remaining.hint ?? challengeSession.remaining.hint,
      coach: state.challenge_remaining.coach ?? challengeSession.remaining.coach,
    };
  } else {
    challengeSession.remaining = {
      undo: challengeSession.limits.undo,
      hint: challengeSession.limits.hint,
      coach: challengeSession.limits.coach,
    };
  }
}

function updateChallengeInfo() {
  let row = document.getElementById("challenge-info-row");
  let val = document.getElementById("challenge-info");
  if (!row || !val) {
    const moveInfo = document.getElementById("move-info");
    if (!moveInfo) return;
    row = document.createElement("div");
    row.className = "info-row";
    row.id = "challenge-info-row";
    row.style.display = "none";
    row.innerHTML = `<span>${ui("闯关进度", "Challenge")}</span><span class="info-val" id="challenge-info">—</span>`;
    moveInfo.appendChild(row);
    val = document.getElementById("challenge-info");
  }
  if (!(gameState?.challenge_beta || challengeSession.active)) {
    row.style.display = "none";
    return;
  }
  row.style.display = "";
  val.textContent = ui(
    `测试第${challengeSession.stage}关 | 卡牌${challengeSession.cards.length} | 悔棋${challengeSession.remaining.undo} 推荐${challengeSession.remaining.hint} 代下${challengeSession.remaining.coach} 刷新${challengeSession.refreshes}`,
    `Beta S${challengeSession.stage} | Cards ${challengeSession.cards.length} | Undo ${challengeSession.remaining.undo} Hint ${challengeSession.remaining.hint} Coach ${challengeSession.remaining.coach} Refresh ${challengeSession.refreshes}`
  );
}

function getCurrentBoard() {
  if (reviewMode) {
    const b = buildBoardAtIndex(reviewMoves, reviewBoardSize, reviewIndex);
    return b.grid;
  }
  return gameState?.board;
}

function getCurrentSize() {
  return reviewMode ? reviewBoardSize : (gameState?.size || boardSize);
}

function detectCaptures(oldBoard, newBoard, size) {
  if (!oldBoard || !newBoard) return [];
  const captured = [];
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      if (oldBoard[y][x] !== 0 && newBoard[y][x] === 0) {
        captured.push([x, y, oldBoard[y][x] === 1 ? "B" : "W"]);
      }
    }
  }
  return captured;
}

function detectNewStone(oldBoard, newBoard, size) {
  if (!oldBoard || !newBoard) return null;
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      if (oldBoard[y][x] === 0 && newBoard[y][x] !== 0) {
        return { x, y };
      }
    }
  }
  return null;
}

window.resetChallengeSession = resetChallengeSession;
window.syncChallengeSessionFromState = syncChallengeSessionFromState;
window.updateChallengeInfo = updateChallengeInfo;
window.getCurrentBoard = getCurrentBoard;
window.getCurrentSize = getCurrentSize;
window.detectCaptures = detectCaptures;
window.detectNewStone = detectNewStone;
