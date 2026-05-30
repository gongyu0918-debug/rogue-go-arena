// Legacy markup action bindings formerly expressed as inline onclick handlers.

function bindClick(id, handler) {
  document.getElementById(id)?.addEventListener("click", handler);
}

function openSettingsDrawer() {
  document.getElementById("settings-drawer")?.classList.add("open");
}

function closeSettingsDrawer() {
  document.getElementById("settings-drawer")?.classList.remove("open");
}

function bindSetupModeButtons() {
  document.querySelectorAll(".mode-btn[data-mode]").forEach(button => {
    button.addEventListener("click", () => setMode(button.dataset.mode));
  });
}

function bindInlineActions() {
  bindClick("quick-rogue", () => quickStartRogue());
  bindClick("quick-setup", () => openNormalSetup());
  bindClick("quick-fullscreen", () => toggleFullscreen());
  bindClick("btn-setup", () => openSetupModal());
  bindClick("btn-quick-rogue", () => quickStartRogue());
  bindClick("btn-rogue-wiki", () => openRogueWiki());
  bindClick("btn-territory-toggle", () => toggleTerritory());
  bindClick("btn-settings", openSettingsDrawer);
  bindClick("btn-review-settings", openSettingsDrawer);
  bindClick("settings-drawer-close", closeSettingsDrawer);
  bindClick("overlay-close", () => closeOverlay());
  bindClick("overlay-review", () => enterReviewMode());
  bindClick("overlay-new-game", () => newGameFromOverlay());
  bindClick("setup-modal-close", () => closeSetupModal());
  bindClick("rogue-wiki-close", () => closeRogueWiki());
  bindClick("confirm-cancel", () => closeConfirmModal());
  bindSetupModeButtons();
}

bindInlineActions();

window.openSettingsDrawer = openSettingsDrawer;
window.closeSettingsDrawer = closeSettingsDrawer;
