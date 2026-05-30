// Challenge-session state and small runtime board helpers for the legacy client.

(() => {
const DEFAULT_CHALLENGE_RESOURCES = { undo: 3, hint: 10, coach: 3 };

let challengeSession = createChallengeSession();

function cloneChallengeResources(resources = DEFAULT_CHALLENGE_RESOURCES) {
  return {
    undo: resources.undo ?? DEFAULT_CHALLENGE_RESOURCES.undo,
    hint: resources.hint ?? DEFAULT_CHALLENGE_RESOURCES.hint,
    coach: resources.coach ?? DEFAULT_CHALLENGE_RESOURCES.coach,
  };
}

function createChallengeSession(overrides = {}) {
  return {
    active: false,
    stage: 1,
    cards: [],
    refreshes: 0,
    limits: cloneChallengeResources(),
    remaining: cloneChallengeResources(),
    cleared: false,
    ...overrides,
  };
}

function resetChallengeSession() {
  challengeSession = createChallengeSession({ active: true });
}

function cloneChallengeCards(cards, fallbackCards) {
  if (Array.isArray(cards)) return [...cards];
  return [...fallbackCards];
}

function mergeChallengeResources(source, fallback) {
  return {
    undo: source?.undo ?? fallback.undo,
    hint: source?.hint ?? fallback.hint,
    coach: source?.coach ?? fallback.coach,
  };
}

function syncChallengeLimits(state) {
  if (!state.challenge_limits) return;
  challengeSession.limits = mergeChallengeResources(state.challenge_limits, challengeSession.limits);
}

function syncChallengeRemaining(state) {
  if (state.challenge_remaining) {
    challengeSession.remaining = mergeChallengeResources(state.challenge_remaining, challengeSession.remaining);
    return;
  }
  challengeSession.remaining = cloneChallengeResources(challengeSession.limits);
}

function syncChallengeSessionFromState(state) {
  if (!state || !state.challenge_beta) return;
  challengeSession.active = true;
  challengeSession.stage = state.challenge_stage || challengeSession.stage || 1;
  challengeSession.cards = cloneChallengeCards(state.challenge_cards, challengeSession.cards);
  challengeSession.refreshes = Number.isFinite(state.challenge_refreshes) ? state.challenge_refreshes : challengeSession.refreshes;
  syncChallengeLimits(state);
  syncChallengeRemaining(state);
}

function ensureChallengeInfoElements() {
  let row = document.getElementById("challenge-info-row");
  let val = document.getElementById("challenge-info");
  if (row && val) return { row, val };
  const moveInfo = document.getElementById("move-info");
  if (!moveInfo) return null;
  row = document.createElement("div");
  row.className = "info-row";
  row.id = "challenge-info-row";
  row.style.display = "none";
  row.innerHTML = `<span>${ui("闯关进度", "Challenge")}</span><span class="info-val" id="challenge-info">—</span>`;
  moveInfo.appendChild(row);
  val = document.getElementById("challenge-info");
  return { row, val };
}

function challengeInfoShouldShow() {
  return !!(gameState?.challenge_beta || challengeSession.active);
}

function challengeInfoText() {
  return ui(
    `测试第${challengeSession.stage}关 | 卡牌${challengeSession.cards.length} | 悔棋${challengeSession.remaining.undo} 推荐${challengeSession.remaining.hint} 代下${challengeSession.remaining.coach} 刷新${challengeSession.refreshes}`,
    `Beta S${challengeSession.stage} | Cards ${challengeSession.cards.length} | Undo ${challengeSession.remaining.undo} Hint ${challengeSession.remaining.hint} Coach ${challengeSession.remaining.coach} Refresh ${challengeSession.refreshes}`
  );
}

function updateChallengeInfo() {
  const elements = ensureChallengeInfoElements();
  if (!elements) return;
  const { row, val } = elements;
  if (!challengeInfoShouldShow()) {
    row.style.display = "none";
    return;
  }
  row.style.display = "";
  val.textContent = challengeInfoText();
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

function boardPairIsUsable(oldBoard, newBoard) {
  return !!(oldBoard && newBoard);
}

function scanBoardDiff(oldBoard, newBoard, size, visitor) {
  if (!boardPairIsUsable(oldBoard, newBoard)) return;
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      if (visitor(x, y, oldBoard[y][x], newBoard[y][x]) === true) return;
    }
  }
}

function detectCaptures(oldBoard, newBoard, size) {
  const captured = [];
  scanBoardDiff(oldBoard, newBoard, size, (x, y, oldValue, newValue) => {
    if (oldValue !== 0 && newValue === 0) {
      captured.push([x, y, oldValue === 1 ? "B" : "W"]);
    }
  });
  return captured;
}

function detectNewStone(oldBoard, newBoard, size) {
  let stone = null;
  scanBoardDiff(oldBoard, newBoard, size, (x, y, oldValue, newValue) => {
    if (!stone && oldValue === 0 && newValue !== 0) {
      stone = { x, y };
      return true;
    }
    return false;
  });
  return stone;
}

Object.defineProperty(window, "challengeSession", {
  configurable: true,
  enumerable: true,
  get: () => challengeSession,
  set: value => { challengeSession = value; },
});

window.resetChallengeSession = resetChallengeSession;
window.syncChallengeSessionFromState = syncChallengeSessionFromState;
window.updateChallengeInfo = updateChallengeInfo;
window.getCurrentBoard = getCurrentBoard;
window.getCurrentSize = getCurrentSize;
window.detectCaptures = detectCaptures;
window.detectNewStone = detectNewStone;
})();
