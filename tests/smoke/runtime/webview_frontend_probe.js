(() => {
  const assert = (condition, message) => { if (!condition) throw new Error(message); };
  document.querySelector("#btn-setup").click();
  const select = document.querySelector("#sel-size");
  select.value = "19";
  syncWoodSelect(select);
  const button = select.parentElement.querySelector(".wood-select-button");
  button.click();
  const menu = document.querySelector(".wood-select-popover.open");
  assert(menu, "native dropdown did not open");
  menu.dispatchEvent(new WheelEvent("wheel", { deltaY: 120, bubbles: true, cancelable: true }));
  assert(select.value === "19", "wheel committed before confirmation");
  button.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true, cancelable: true }));
  assert(select.value === "13", "native wheel/keyboard selection failed");
  closeWoodSelectMenu();
  document.querySelector("#setup-modal").classList.remove("show");

  clearVisualEffects();
  reviewMode = false;
  twoPlayerMode = true;
  showHints = true;
  showTerritory = false;
  hoverXY = null;
  fineTunePos = null;
  activeRogueCard = null;
  gameState = { size: 19, board: Array.from({ length: 19 }, () => Array(19).fill(0)),
    current_player: "B", game_over: false };
  analysis = { top_moves: [{ x: 9, y: 9, winrate: .64 }], ownership: [] };
  resizeBoard(19);
  render();
  const pixels = ctx.getImageData(0, 0, canvas.width, canvas.height).data;
  let greenPixels = 0;
  for (let i = 0; i < pixels.length; i += 4) {
    const [r, g, b, a] = pixels.slice(i, i + 4);
    if (g > r + 12 && g > b + 35 && g <= 205 && a === 255) greenPixels++;
  }
  assert(greenPixels >= 30, "native hint green is missing or faint");
  const fog = document.createElement("div");
  fog.className = "fx-fog-grid";
  document.body.appendChild(fog);
  const fogMask = getComputedStyle(fog).getPropertyValue("-webkit-mask-image");
  fog.remove();
  assert(fogMask.includes("gradient"), "native fog mask fallback is missing");
  const motionEnabled = !document.hidden && !matchMedia("(prefers-reduced-motion: reduce)").matches;
  addPlaceAnimation(3, 3);
  assert(motionEnabled ? animations.length > 0 && animations.length <= 32 : animations.length === 0,
    "native placement animation did not follow the system motion preference");
  clearVisualEffects();
  const originalSendWS = sendWS;
  const originalPlace = addPlaceAnimation;
  const originalSound = playStoneSound;
  let placements = 0;
  let sounds = 0;
  try {
    sendWS = () => {};
    addPlaceAnimation = (...args) => { placements++; originalPlace(...args); };
    playStoneSound = () => { sounds++; };
    commitPlay(3, 3);
    handleMessage({ ...gameState, type: "game_state", board: gameState.board.map(row => [...row]),
      current_player: "W", move_number: 1 });
    assert(placements === 1 && sounds === 1, "native confirmation replayed the local placement");
  } finally {
    sendWS = originalSendWS;
    addPlaceAnimation = originalPlace;
    playStoneSound = originalSound;
  }
  const deck = document.getElementById("client-command-deck");
  const bounds = deck.getBoundingClientRect();
  assert(getComputedStyle(deck).display === "flex" && getComputedStyle(deck).flexWrap === "nowrap",
    "native command deck allowed multiple rows");
  assert(bounds.right <= innerWidth && bounds.left >= 0, "native command deck overflowed");
  clearVisualEffects();
  return { userAgent: navigator.userAgent, viewport: [innerWidth, innerHeight],
    dpr: devicePixelRatio, selectedSize: select.value, greenPixels, fogMask, motionEnabled,
    placements, sounds, commandDeckScale: bounds.width / deck.offsetWidth,
    dropdownCount: document.querySelectorAll("select.wood-select-native").length,
    bridgeReady: typeof window.pywebview?.api?.close_window === "function" };
})()
