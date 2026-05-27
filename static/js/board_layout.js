// Board canvas sizing and recovery helpers.
// Rendering itself stays in index.html for now.

const canvas = document.getElementById("board-canvas");
const ctx = canvas.getContext("2d");
const boardContainer = document.getElementById("board-container");
const mainLayout = document.querySelector(".main-layout");
const sidePanel = document.querySelector(".side-panel");
let boardRecoveryTimer = null;
let boardWatchdogTimer = null;
let boardRenderSize = 0;
let boardRenderDpr = 1;
const SCENE_W = 1672;
const SCENE_H = 941;
const SCENE_ASPECT = SCENE_W / SCENE_H;

function stagePresetConfig() {
  return {
    "1080": { factor: 0.92, maxWidth: 1920 },
    "1440": { factor: 0.95, maxWidth: 2560 },
    "2160": { factor: 0.96, maxWidth: 3840 },
    auto: { factor: 0.96, maxWidth: 3840 },
  }[stagePreset] || { factor: 0.96, maxWidth: 3840 };
}

function syncBoardFitFrame() {
  if (!boardContainer || !canvas) return;
  boardContainer.style.setProperty("--board-fit-x", `${canvas.offsetLeft}px`);
  boardContainer.style.setProperty("--board-fit-y", `${canvas.offsetTop}px`);
  boardContainer.style.setProperty("--board-fit-size", `${canvas.offsetWidth}px`);
}

function resizeBoard(size) {
  boardSize = size;
  const compact = window.innerWidth <= 640;
  const stacked = window.innerWidth <= 980;
  const deckRect = document.getElementById("client-command-deck")?.getBoundingClientRect();
  const topClear = Math.ceil((deckRect?.bottom || 64) + (stacked ? 10 : 14));
  const bottomClear = compact ? 8 : 18;
  const horizontalMargin = compact ? 12 : (stacked ? 20 : 72);
  const availableViewportWidth = Math.max(300, window.innerWidth - horizontalMargin);
  const availableViewportHeight = Math.max(360, window.innerHeight - topClear - bottomClear);
  const preset = stagePresetConfig();
  const stageWidth = Math.floor(Math.max(
    compact ? Math.min(availableViewportWidth, 320) : Math.min(availableViewportWidth, 900),
    Math.min(
      availableViewportWidth,
      window.innerWidth * preset.factor,
      availableViewportHeight * SCENE_ASPECT,
      preset.maxWidth
    )
  ));
  const stageHeight = Math.floor(stageWidth / SCENE_ASPECT);
  const boardTop = Math.round(stageHeight * (compact ? 0.05 : 0.04));
  const toolbarBottomInset = Math.round(Math.min(compact ? 12 : 18, Math.max(8, window.innerHeight * 0.0095)));
  const toolbarButtonHeight = compact
    ? 66
    : Math.round(Math.min(82, Math.max(64, window.innerWidth * 0.0365)));
  const toolbarFramePadY = Math.round(Math.min(compact ? 20 : 24, Math.max(compact ? 16 : 18, window.innerWidth * 0.011)));
  const windowedTight = !compact && availableViewportHeight < 1050;
  const toolbarSafeClear = toolbarButtonHeight + toolbarFramePadY + toolbarBottomInset + (windowedTight ? 18 : 10);
  const toolbarBaseClear = Math.round(Math.min(
    compact ? 92 : 112,
    Math.max(compact ? 64 : 58, stageHeight * (compact ? 0.075 : 0.058))
  ));
  const toolbarClear = Math.max(toolbarBaseClear, toolbarSafeClear);
  const boardHeightLimit = Math.max(compact ? 260 : 360, stageHeight - boardTop - toolbarClear);
  const preferredBoardTarget = Math.min(
    stageWidth * (compact ? 0.7 : 0.54),
    boardHeightLimit
  );
  const minimumBoardTarget = compact
    ? Math.min(280, boardHeightLimit)
    : Math.min(520, Math.max(360, boardHeightLimit));
  const boardTarget = Math.max(minimumBoardTarget, preferredBoardTarget);
  const padRatio = 1.3;
  const denominator = 2 * padRatio + size - 1;
  CELL = Math.floor(boardTarget / denominator);
  const minCell = compact ? (boardTarget < 310 ? 13 : 15) : (boardTarget < 460 ? 18 : 22);
  CELL = Math.max(minCell, Math.min(CELL, compact ? 30 : 96));
  PAD = Math.floor(CELL * padRatio);
  const minBoardTotal = compact ? Math.min(280, boardTarget) : minimumBoardTarget;
  const total = Math.max(minBoardTotal, PAD * 2 + CELL * (size - 1));
  const boardLeft = Math.round((stageWidth - total) / 2);
  const boardRight = Math.max(0, stageWidth - boardLeft - total);
  const boardBottom = Math.max(toolbarClear, stageHeight - boardTop - total);
  const nextDpr = Math.max(1, Math.min(window.devicePixelRatio || 1, 3));
  const layoutUnchanged =
    boardContainer &&
    boardRenderSize === total &&
    boardRenderDpr === nextDpr &&
    canvas.style.width === `${total}px` &&
    canvas.style.height === `${total}px` &&
    boardContainer.style.width === `${stageWidth}px` &&
    boardContainer.style.getPropertyValue("--stage-pad-left") === `${boardLeft}px` &&
    boardContainer.style.getPropertyValue("--stage-pad-right") === `${boardRight}px` &&
    boardContainer.style.getPropertyValue("--stage-pad-top") === `${boardTop}px` &&
    boardContainer.style.getPropertyValue("--stage-pad-bottom") === `${boardBottom}px`;
  if (layoutUnchanged) {
    syncBoardFitFrame();
    return;
  }
  document.documentElement.style.setProperty("--arena-stage-width", `${stageWidth}px`);
  if (boardContainer) {
    boardContainer.style.width = `${stageWidth}px`;
    boardContainer.style.setProperty("--stage-pad-left", `${boardLeft}px`);
    boardContainer.style.setProperty("--stage-pad-right", `${boardRight}px`);
    boardContainer.style.setProperty("--stage-pad-top", `${boardTop}px`);
    boardContainer.style.setProperty("--stage-pad-bottom", `${boardBottom}px`);
    boardContainer.style.setProperty("--toolbar-bottom", `${toolbarBottomInset}px`);
    boardContainer.style.setProperty("--toolbar-width", `${Math.min(stageWidth * 0.72, Math.max(1120, total * 1.08))}px`);
  }
  boardRenderSize = total;
  boardRenderDpr = nextDpr;
  canvas.width = Math.floor(total * boardRenderDpr);
  canvas.height = Math.floor(total * boardRenderDpr);
  canvas.style.width = `${total}px`;
  canvas.style.height = `${total}px`;
  syncBoardFitFrame();
  ctx.setTransform(boardRenderDpr, 0, 0, boardRenderDpr, 0, 0);
  ctx.imageSmoothingEnabled = true;
  if ("imageSmoothingQuality" in ctx) ctx.imageSmoothingQuality = "high";
}

function boardLooksReady() {
  if (!canvas || !ctx || !boardContainer) return false;
  const rect = canvas.getBoundingClientRect();
  const containerRect = boardContainer.getBoundingClientRect();
  return (
    boardRenderSize >= 200 &&
    rect.width >= 180 &&
    rect.height >= 180 &&
    containerRect.width >= 180
  );
}

function scheduleBoardRecovery(delay = 250) {
  if (boardRecoveryTimer) clearTimeout(boardRecoveryTimer);
  boardRecoveryTimer = setTimeout(() => {
    boardRecoveryTimer = null;
    try {
      resizeBoard(reviewMode ? reviewBoardSize : (gameState?.size || boardSize || 19));
      _boardCacheParams = "";
      _offScreenBoard = null;
      render();
    } catch (_) {}
  }, delay);
}

function ensureBoardReady(delay = 250) {
  if (!boardLooksReady()) scheduleBoardRecovery(delay);
}
