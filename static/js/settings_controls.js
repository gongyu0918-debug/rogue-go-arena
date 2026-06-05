// Legacy settings drawer controls and card editor entry points.

const QUICKTHINK_CARD_ID = "quickthink";
const ENGINE_IDLE_TIMEOUT_OPTIONS = [0, 120, 300, 600];

function currentWinrate() {
  return analysis ? analysis.winrate : 0.5;
}

function setToggleClass(id, enabled) {
  const toggle = document.getElementById(id);
  if (toggle) toggle.className = "toggle" + (enabled ? " on" : "");
}

function refreshCurrentWinrate() {
  updateWinRate(currentWinrate());
}

function buildCardEditorUrl() {
  const url = new URL("/card-editor", window.location.href);
  url.searchParams.set("embed", "1");
  url.searchParams.set("ts", String(Date.now()));
  return url.href;
}

function setHintOverlayState(enabled) {
  showHints = enabled;
  setToggleClass("hint-toggle", showHints);
}

function hasChallengeCard(cardId) {
  return Array.isArray(gameState?.challenge_cards) && gameState.challenge_cards.includes(cardId);
}

function refreshHintVisibility() {
  const wrap = document.getElementById("winrate-bar-wrap");
  const locked = isHintLockedByCard();
  if (locked && showHints) {
    setHintOverlayState(false);
  }
  const topSlot = document.getElementById("top-winrate-slot");
  if (wrap) wrap.style.display = "block";
  if (topSlot) topSlot.classList.add("active");
  refreshCurrentWinrate();
}

function isHintLockedByCard() {
  return activeRogueCard === QUICKTHINK_CARD_ID || hasChallengeCard(QUICKTHINK_CARD_ID);
}

function openCardEditorPanel() {
  const modal = document.getElementById("card-editor-modal");
  const frame = document.getElementById("card-editor-frame");
  if (!modal || !frame) return;
  frame.src = buildCardEditorUrl();
  modal.classList.add("show");
}

function closeCardEditorPanel() {
  const modal = document.getElementById("card-editor-modal");
  const frame = document.getElementById("card-editor-frame");
  if (modal) modal.classList.remove("show");
  if (frame) frame.src = "about:blank";
}

function toggleTerritory() {
  document.getElementById("territory-toggle").click();
}

function toggleHintOverlay() {
  if (isHintLockedByCard()) {
    setHintOverlayState(false);
    refreshHintVisibility();
    logI18n("⚡ 快速思考已禁用推荐点位", "⚡ Quick Think disables hints.", "⚡ クイック思考により推薦着点は無効です", "⚡ 빠른 사고로 추천 착점이 비활성화됨");
    render();
    return;
  }
  setHintOverlayState(!showHints);
  refreshHintVisibility();
  refreshCurrentWinrate();
  if (showHints && gameState) sendWS({ action: "request_hint" });
  render();
}

function toggleTerritoryOverlay() {
  showTerritory = !showTerritory;
  setToggleClass("territory-toggle", showTerritory);
  setTerritoryToggleVisual();
  refreshCurrentWinrate();
  render();
}

function toggleMoveNumbersOverlay() {
  showMoveNumbers = !showMoveNumbers;
  setToggleClass("move-number-toggle", showMoveNumbers);
  render();
}

function updateLevelSetting(value) {
  if (gameState && !gameState.game_over) {
    sendWS({ action: "set_level", level: value });
  }
}

function syncHandicapKomi(value) {
  if (parseInt(value, 10) > 0) {
    const komiSelect = document.getElementById("sel-komi");
    komiSelect.value = "0";
    syncWoodSelect(komiSelect);
  }
}

function toggleSoundSetting() {
  soundEnabled = !soundEnabled;
  setSoundToggleVisual();
  if (soundEnabled) getAudioCtx();
}

function nearestEngineIdleTimeoutOption(seconds) {
  const value = Number(seconds);
  if (!Number.isFinite(value) || value <= 0) return "0";
  return String(ENGINE_IDLE_TIMEOUT_OPTIONS
    .filter(option => option > 0)
    .reduce((best, option) => (
      Math.abs(option - value) < Math.abs(best - value) ? option : best
    ), 300));
}

function setEngineIdleTimeoutSelect(seconds) {
  const select = document.getElementById("sel-engine-idle-timeout");
  if (!select) return;
  const optionValue = nearestEngineIdleTimeoutOption(seconds);
  select.value = optionValue;
  syncWoodSelect(select);
}

async function syncEngineIdleTimeoutSetting() {
  try {
    const resp = await fetch("/engine_idle_timeout", { headers: { "Accept": "application/json" } });
    if (!resp.ok) throw new Error(`${resp.status} ${resp.statusText}`);
    const payload = await resp.json();
    setEngineIdleTimeoutSelect(payload.seconds);
  } catch (err) {
    console.warn("[Settings] engine idle timeout load failed", err);
  }
}

async function updateEngineIdleTimeoutSetting(value) {
  const seconds = Number(value);
  setEngineIdleTimeoutSelect(seconds);
  try {
    const resp = await fetch("/engine_idle_timeout", {
      method: "POST",
      headers: { "Content-Type": "application/json", "Accept": "application/json" },
      body: JSON.stringify({ seconds }),
    });
    if (!resp.ok) throw new Error(`${resp.status} ${resp.statusText}`);
    const payload = await resp.json();
    setEngineIdleTimeoutSelect(payload.seconds);
  } catch (err) {
    console.warn("[Settings] engine idle timeout save failed", err);
  }
}

function bindSettingsControls() {
  document.getElementById("btn-card-editor")?.addEventListener("click", openCardEditorPanel);
  document.getElementById("card-editor-modal-close")?.addEventListener("click", closeCardEditorPanel);
  document.getElementById("hint-toggle")?.addEventListener("click", toggleHintOverlay);
  document.getElementById("territory-toggle")?.addEventListener("click", toggleTerritoryOverlay);
  document.getElementById("move-number-toggle")?.addEventListener("click", toggleMoveNumbersOverlay);
  document.getElementById("sel-level")?.addEventListener("change", event => {
    updateLevelSetting(event.target.value);
  });
  document.getElementById("sel-handicap")?.addEventListener("change", event => {
    syncHandicapKomi(event.target.value);
  });
  document.getElementById("sound-toggle")?.addEventListener("click", toggleSoundSetting);
  document.getElementById("sound-settings-toggle")?.addEventListener("click", toggleSoundSetting);
  document.getElementById("sel-engine-idle-timeout")?.addEventListener("change", event => {
    updateEngineIdleTimeoutSetting(event.target.value);
  });
  syncEngineIdleTimeoutSetting();
}

bindSettingsControls();

window.refreshHintVisibility = refreshHintVisibility;
window.isHintLockedByCard = isHintLockedByCard;
window.openCardEditorPanel = openCardEditorPanel;
window.closeCardEditorPanel = closeCardEditorPanel;
window.toggleTerritory = toggleTerritory;
window.syncEngineIdleTimeoutSetting = syncEngineIdleTimeoutSetting;
