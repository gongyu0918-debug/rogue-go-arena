// Legacy setup modal, mode selection, and new-game controls.

function getRogueVariantMode() {
  return document.getElementById("sel-rogue-variant")?.value || "solo";
}

function openSetupModal() {
  refreshSetupModeHint();
  updateVariantOptionRows();
  document.getElementById("setup-modal").classList.add("show");
}

function closeSetupModal() {
  document.getElementById("setup-modal").classList.remove("show");
}

function openRogueWiki() {
  renderRogueWiki();
  document.getElementById("rogue-wiki-modal").classList.add("show");
}

function closeRogueWiki() {
  document.getElementById("rogue-wiki-modal").classList.remove("show");
}

function showConfirmModal(msg, onConfirm) {
  document.getElementById("confirm-msg").textContent = msg;
  const btnOk = document.getElementById("btn-confirm-ok");
  btnOk.onclick = () => { closeConfirmModal(); onConfirm(); };
  document.getElementById("confirm-modal").classList.add("show");
}

function closeConfirmModal() {
  document.getElementById("confirm-modal").classList.remove("show");
}

function newGameFromOverlay() {
  closeOverlay();
  document.getElementById("btn-new").click();
}

function setMode(mode) {
  startMode = mode;
  document.querySelectorAll(".mode-btn").forEach(b => b.classList.remove("active"));
  document.getElementById("mode-" + mode).classList.add("active");

  const hint = document.getElementById("mode-hint");
  if (hint) hint.style.display = "block";
  refreshSetupModeHint();
  updateVariantOptionRows();
}

function updateTimeSettingsVisibility(mode) {
  document.getElementById("time-settings").style.display = mode === "none" ? "none" : "";
  document.getElementById("row-byoyomi").style.display = mode === "byoyomi" ? "flex" : "none";
}

function applyStagePreset(value) {
  stagePreset = value || "auto";
  localStorage.setItem("rogue_go_arena_stage_preset", stagePreset);
  invalidateBoardVisualCaches();
  resizeBoard(reviewMode ? reviewBoardSize : (gameState?.size || boardSize || 19));
  render();
}

function resetGameUiBeforeStart() {
  twoPlayerMode = startMode === "two";
  gameState = null;
  analysis = { winrate: 0.5, score: 0, top_moves: [], ownership: [], analysis_ready: false };
  analysisReady = false;
  resetWinrateHistory();
  lastAiMove = null;
  previousBoard = null;
  animations = [];
  reviewMode = false;
  sgfLoadedMode = false;
  document.getElementById("game-log").innerHTML = "";
  document.getElementById("info-territory").textContent = "—";

  const mainBar = document.getElementById("main-toolbar");
  if (mainBar) mainBar.style.display = "flex";
  const revBar = document.getElementById("review-toolbar");
  if (revBar) revBar.style.display = "none";
  document.getElementById("review-info").textContent = "";

  updateWinRate(0.5);
  closeSetupModal();
  setButtons(false);
  stopTimerTick();

  gameId = Math.random().toString(36).slice(2);
  localStorage.setItem("rogue_go_arena_game_id", gameId);

  resetRogueState();
  intentionalClose = true;
  if (ws) ws.close();
}

function startGameFromSetup() {
  let playerColor = document.getElementById("sel-color").value;
  let komi = parseFloat(document.getElementById("sel-komi").value);
  const handicap = parseInt(document.getElementById("sel-handicap").value, 10);
  const isTwoPlayer = startMode === "two";
  const isAiWatch = startMode === "watch";
  const isRogueMode = startMode === "rogue";
  const isChallenge = startMode === "challenge";
  const rogueVariant = getRogueVariantMode();
  const isDualDraft = isRogueMode && rogueVariant === "dual";
  const isUltimateVariant = isRogueMode && rogueVariant === "ultimate";
  const aiStyle = document.getElementById("sel-ai-style")?.value || "balanced";
  const aiStyleBlack = document.getElementById("sel-ai-style-black")?.value || aiStyle;
  const aiStyleWhite = document.getElementById("sel-ai-style-white")?.value || aiStyle;
  const aiLevelDefault = document.getElementById("sel-level").value;
  const aiLevelBlack = document.getElementById("sel-level-black")?.value || aiLevelDefault;
  const aiLevelWhite = document.getElementById("sel-level-white")?.value || aiLevelDefault;

  if (isChallenge && (!challengeSession.active || challengeSession.cleared)) {
    resetChallengeSession();
  }

  if ((startMode === "normal" || isRogueMode) && playerColor === "R") {
    playerColor = Math.random() < 0.5 ? "B" : "W";
    logI18n(
      `随机结果：你执${playerColor === "B" ? "黑" : "白"}棋`,
      `Random result: you play ${playerColor === "B" ? "Black" : "White"}`,
      `ニギリ結果：${playerColor === "B" ? "黒" : "白"}番`,
      `돌 가리기 결과: ${playerColor === "B" ? "흑" : "백"}`
    );
  } else if (isTwoPlayer || isAiWatch) {
    playerColor = "B";
  } else if (isChallenge) {
    playerColor = "W";
    komi = 7.5;
  }

  timerMode = document.getElementById("sel-time-mode").value;
  mainTimeSetting = parseInt(document.getElementById("sel-main-time").value, 10);
  byoPeriodsSetting = parseInt(document.getElementById("sel-byo-periods").value, 10);
  byoTimeSetting = parseInt(document.getElementById("sel-byo-time").value, 10);

  resetGameUiBeforeStart();

  setTimeout(() => {
    connect();
    setTimeout(() => {
      const gameSize = isRogueMode ? 19 : parseInt(document.getElementById("sel-size").value, 10);
      const gameHandicap = isRogueMode ? 0 : handicap;
      sendWS({
        action: "new_game",
        size: gameSize,
        komi: komi,
        handicap: gameHandicap,
        player_color: playerColor,
        level: isAiWatch ? aiLevelBlack : aiLevelDefault,
        ai_level_black: aiLevelBlack,
        ai_level_white: aiLevelWhite,
        two_player: isTwoPlayer,
        ai_observer: isAiWatch,
        ai_style: aiStyle,
        ai_style_black: aiStyleBlack,
        ai_style_white: aiStyleWhite,
        rogue: isChallenge ? true : (isRogueMode && !isUltimateVariant),
        ai_rogue: isChallenge ? false : isDualDraft,
        ultimate: isChallenge ? false : isUltimateVariant,
        challenge_beta: isChallenge,
        challenge_stage: isChallenge ? challengeSession.stage : 0,
        challenge_cards: isChallenge ? challengeSession.cards : [],
        challenge_limits: isChallenge ? challengeSession.limits : null,
        challenge_refreshes: isChallenge ? challengeSession.refreshes : 0,
      });
    }, 400);
  }, 200);
}

function bindSetupControls() {
  document.getElementById("sel-rogue-variant")?.addEventListener("change", () => {
    updateVariantOptionRows();
    refreshSetupModeHint();
  });

  document.getElementById("sel-time-mode")?.addEventListener("change", (event) => {
    updateTimeSettingsVisibility(event.target.value);
  });

  document.getElementById("sel-stage-preset")?.addEventListener("change", (event) => {
    applyStagePreset(event.target.value);
  });

  document.getElementById("btn-new")?.addEventListener("click", startGameFromSetup);
}

bindSetupControls();

window.getRogueVariantMode = getRogueVariantMode;
window.openSetupModal = openSetupModal;
window.closeSetupModal = closeSetupModal;
window.openRogueWiki = openRogueWiki;
window.closeRogueWiki = closeRogueWiki;
window.showConfirmModal = showConfirmModal;
window.closeConfirmModal = closeConfirmModal;
window.newGameFromOverlay = newGameFromOverlay;
window.setMode = setMode;
window.startGameFromSetup = startGameFromSetup;
