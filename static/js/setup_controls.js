// Legacy setup modal, mode selection, and new-game controls.

const SETUP_ROW_DISPLAY_RULES = [
  { id: "row-color", display: ({ isNormal, isRogue }) => (isNormal || isRogue) ? "flex" : "none" },
  { id: "row-rogue-variant", display: ({ isRogue }) => isRogue ? "flex" : "none" },
  { id: "row-size", display: ({ isRogue }) => isRogue ? "none" : "flex" },
  { id: "row-handicap", display: ({ isWatch, isChallenge, isRogue }) => (isWatch || isChallenge || isRogue) ? "none" : "flex" },
  { id: "row-time", display: () => "flex" },
  { id: "row-level", display: ({ isWatch }) => isWatch ? "none" : "flex" },
  { id: "row-level-black", display: ({ isWatch }) => isWatch ? "flex" : "none" },
  { id: "row-level-white", display: ({ isWatch }) => isWatch ? "flex" : "none" },
  { id: "row-style", display: ({ isTwo, isWatch, isChallenge }) => (!isTwo && !isWatch && !isChallenge) ? "flex" : "none" },
  { id: "row-style-black", display: ({ isWatch }) => isWatch ? "flex" : "none" },
  { id: "row-style-white", display: ({ isWatch }) => isWatch ? "flex" : "none" },
];

const SETUP_ROGUE_VARIANT_HINTS = {
  ultimate: () => ui("当前玩法：大招对战。固定 19×19，用普通规则开局，你与 AI 各自带一张大招卡，20 手决胜。", "Current variant: Ultimate Duel. Fixed at 19x19 with standard rules, one ultimate card per side, and a 20-move showdown."),
  dual: () => ui("当前玩法：双人抽卡。固定 19×19，你先选 1 张 Rogue 卡，AI 也会从受限卡池获得 1 张。", "Current variant: Dual Draft. Fixed at 19x19. You pick 1 Rogue card, and the AI also receives 1 card from the restricted pool."),
  solo: () => ui("当前玩法：单人抽卡。固定 19×19，只有你带 Rogue 卡，保留颜色、贴目、等级、棋风与用时设置。", "Current variant: Solo Draft. Fixed at 19x19. Only you use a Rogue card, while color, komi, rank, style, and time settings stay available."),
};

const SETUP_MODE_HINTS = {
  rogue: () => SETUP_ROGUE_VARIANT_HINTS[getRogueVariantMode()]?.() || SETUP_ROGUE_VARIANT_HINTS.solo(),
  watch: () => ui(
    "学习：黑白双方都由 AI 对弈，可分别调整黑棋与白棋的等级和棋风。",
    "Study: both sides are AI, with separate rank and style controls for Black and White."
  ),
  two: () => ui(
    "双人：黑白双方均由玩家落子，可调整棋盘、贴目、让子与用时。",
    "Two Players: both sides are human, with board size, komi, handicap, and timing controls."
  ),
  challenge: () => ui(
    "闯关：测试版默认执白，按当前关卡自动套用让子与卡组限制。",
    "Challenge: beta mode defaults you to White and applies stage handicap and loadout rules automatically."
  ),
  normal: () => ui(
    "对局：可手选黑白或随机猜先；选择让子时会自动把贴目设为 0，仍可手动改回 6.5 或 7.5。",
    "Game: choose Black, White, or random color; handicap auto-sets komi to 0, but you can still change it back to 6.5 or 7.5."
  ),
};

function getRogueVariantMode() {
  return document.getElementById("sel-rogue-variant")?.value || "solo";
}

function getSetupModeContext(mode = startMode) {
  return {
    mode,
    isNormal: mode === "normal",
    isTwo: mode === "two",
    isWatch: mode === "watch",
    isRogue: mode === "rogue",
    isChallenge: mode === "challenge",
  };
}

function setSetupRowDisplay(id, display) {
  const row = document.getElementById(id);
  if (row) row.style.display = display;
}

function forceRogueBoardOptions() {
  document.getElementById("sel-size").value = "19";
  document.getElementById("sel-handicap").value = "0";
  syncWoodSelect(document.getElementById("sel-size"));
  syncWoodSelect(document.getElementById("sel-handicap"));
}

function getSetupModeHintText(mode = startMode) {
  return (SETUP_MODE_HINTS[mode] || SETUP_MODE_HINTS.normal)();
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

function showConfirmModal(msg, onConfirm, options = {}) {
  document.getElementById("confirm-msg").textContent = msg;
  const btnOk = document.getElementById("btn-confirm-ok");
  const btnCancel = document.getElementById("confirm-cancel");
  if (btnOk) btnOk.textContent = options.confirmText || ui("确定", "OK", "確定", "확인");
  if (btnCancel) {
    btnCancel.textContent = options.cancelText || ui("取消", "Cancel", "キャンセル", "취소");
    btnCancel.onclick = () => {
      closeConfirmModal();
      if (typeof options.onCancel === "function") options.onCancel();
    };
  }
  btnOk.onclick = () => { closeConfirmModal(); onConfirm(); };
  document.getElementById("confirm-modal").classList.add("show");
}

function closeConfirmModal() {
  const modal = document.getElementById("confirm-modal");
  if (modal) modal.classList.remove("show");
  const btnOk = document.getElementById("btn-confirm-ok");
  const btnCancel = document.getElementById("confirm-cancel");
  if (btnOk) btnOk.textContent = ui("确定", "OK", "確定", "확인");
  if (btnCancel) {
    btnCancel.textContent = ui("取消", "Cancel", "キャンセル", "취소");
    btnCancel.onclick = closeConfirmModal;
  }
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

function updateVariantOptionRows() {
  const context = getSetupModeContext();
  SETUP_ROW_DISPLAY_RULES.forEach((rule) => setSetupRowDisplay(rule.id, rule.display(context)));
  if (context.isRogue) forceRogueBoardOptions();
}

function refreshSetupModeHint() {
  const hint = document.getElementById("mode-hint");
  if (!hint) return;
  hint.style.display = "block";
  hint.textContent = getSetupModeHintText();
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
  pendingRogueSealPoints = [];
  rogueSealRequired = 0;
  rogueSealWaitingForOpponent = false;
  quickthinkAwaitingAiMove = false;
  intentionalClose = true;
  clearPendingWS();
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
  showGameStartProgress({
    mode: isUltimateVariant ? "ultimate" : (isRogueMode || isChallenge ? "rogue" : "normal"),
    twoPlayer: isTwoPlayer,
    aiObserver: isAiWatch,
  });

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
window.updateVariantOptionRows = updateVariantOptionRows;
window.refreshSetupModeHint = refreshSetupModeHint;
window.startGameFromSetup = startGameFromSetup;
