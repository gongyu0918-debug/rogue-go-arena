// Board texture and stone sprite resources.
// Board drawing still lives in index.html until board_renderer.js is extracted.

let _boardCacheParams = "";
let _offScreenBoard = null;
let _stoneSpriteCache = new Map();
const BOARD_TEXTURE_SRC = "assets/textures/board-kaya-classic-v1.png?v=20260424a";
const BLACK_STONE_TEXTURE_SRC = "assets/textures/stone-black-traditional-v1.png?v=20260423b";
const WHITE_STONE_TEXTURE_SRC = "assets/textures/stone-materials-tech-v3.png?v=20260423a";
const boardTextureImage = new Image();
const blackStoneTexture = new Image();
const whiteStoneTexture = new Image();
boardTextureImage.decoding = "async";
blackStoneTexture.decoding = "async";
whiteStoneTexture.decoding = "async";

function isAssetReady(img) {
  return !!(img && img.complete && img.naturalWidth > 0);
}

function invalidateBoardVisualCaches() {
  _boardCacheParams = "";
  _offScreenBoard = null;
  _stoneSpriteCache = new Map();
}

function refreshBoardVisuals() {
  invalidateBoardVisualCaches();
  if (boardRenderSize && canvas && ctx && typeof render === "function") render();
}

boardTextureImage.onload = refreshBoardVisuals;
blackStoneTexture.onload = refreshBoardVisuals;
whiteStoneTexture.onload = refreshBoardVisuals;
boardTextureImage.src = BOARD_TEXTURE_SRC;
blackStoneTexture.src = BLACK_STONE_TEXTURE_SRC;
whiteStoneTexture.src = WHITE_STONE_TEXTURE_SRC;

function paintBoardBase(bCtx, W) {
  if (isAssetReady(boardTextureImage)) {
    const crop = Math.floor(boardTextureImage.naturalWidth * 0.14);
    bCtx.drawImage(
      boardTextureImage,
      crop,
      crop,
      boardTextureImage.naturalWidth - crop * 2,
      boardTextureImage.naturalHeight - crop * 2,
      0,
      0,
      W,
      W
    );
  } else {
    const woodGrad = bCtx.createLinearGradient(0, 0, 0, W);
    woodGrad.addColorStop(0, "#c89547");
    woodGrad.addColorStop(0.45, "#d6a85a");
    woodGrad.addColorStop(1, "#b67d38");
    bCtx.fillStyle = woodGrad;
    bCtx.fillRect(0, 0, W, W);

    let grainSeed = boardSize * 131 + W * 17;
    const grainRand = () => {
      grainSeed = (grainSeed * 1664525 + 1013904223) >>> 0;
      return grainSeed / 4294967296;
    };
    bCtx.lineCap = "round";
    for (let i = 0; i < 28; i++) {
      const startY = grainRand() * W;
      const driftA = (grainRand() - 0.5) * W * 0.16;
      const driftB = (grainRand() - 0.5) * W * 0.14;
      const endY = startY + (grainRand() - 0.5) * W * 0.12;
      bCtx.strokeStyle = `rgba(88, 52, 19, ${0.022 + grainRand() * 0.028})`;
      bCtx.lineWidth = Math.max(1.1, W * (0.0014 + grainRand() * 0.0016));
      bCtx.beginPath();
      bCtx.moveTo(-W * 0.08, startY);
      bCtx.bezierCurveTo(W * 0.24, startY + driftA, W * 0.72, startY + driftB, W * 1.08, endY);
      bCtx.stroke();
    }
    for (let i = 0; i < 20; i++) {
      const startY = grainRand() * W;
      const driftA = (grainRand() - 0.5) * W * 0.12;
      const driftB = (grainRand() - 0.5) * W * 0.1;
      const endY = startY + (grainRand() - 0.5) * W * 0.08;
      bCtx.strokeStyle = `rgba(255, 231, 186, ${0.01 + grainRand() * 0.018})`;
      bCtx.lineWidth = Math.max(0.8, W * (0.0008 + grainRand() * 0.001));
      bCtx.beginPath();
      bCtx.moveTo(-W * 0.06, startY);
      bCtx.bezierCurveTo(W * 0.28, startY + driftA, W * 0.68, startY + driftB, W * 1.04, endY);
      bCtx.stroke();
    }
    for (let i = 0; i < 7; i++) {
      const knotX = W * (0.12 + grainRand() * 0.76);
      const knotY = W * (0.12 + grainRand() * 0.76);
      const knotR = W * (0.015 + grainRand() * 0.026);
      const knot = bCtx.createRadialGradient(knotX - knotR * 0.24, knotY - knotR * 0.18, knotR * 0.1, knotX, knotY, knotR);
      knot.addColorStop(0, `rgba(102, 58, 20, ${0.12 + grainRand() * 0.08})`);
      knot.addColorStop(0.45, `rgba(132, 78, 30, ${0.06 + grainRand() * 0.05})`);
      knot.addColorStop(1, "rgba(132, 78, 30, 0)");
      bCtx.fillStyle = knot;
      bCtx.beginPath();
      bCtx.ellipse(knotX, knotY, knotR * (1.2 + grainRand() * 0.5), knotR * (0.7 + grainRand() * 0.25), grainRand() * Math.PI, 0, Math.PI * 2);
      bCtx.fill();
    }
  }

  const edgeGrad = bCtx.createRadialGradient(W / 2, W / 2, W * 0.26, W / 2, W / 2, W * 0.76);
  edgeGrad.addColorStop(0, "rgba(255,255,255,0)");
  edgeGrad.addColorStop(0.72, "rgba(0,0,0,0.035)");
  edgeGrad.addColorStop(1, "rgba(0,0,0,0.13)");
  bCtx.fillStyle = edgeGrad;
  bCtx.fillRect(0, 0, W, W);

  // The kaya texture is lit from the top-left; shade that corner so the four
  // corners read evenly instead of the top-left glaring.
  const frameGrad = bCtx.createLinearGradient(0, 0, W, W);
  frameGrad.addColorStop(0, "rgba(90, 52, 14, 0.24)");
  frameGrad.addColorStop(0.5, "rgba(90, 52, 14, 0.06)");
  frameGrad.addColorStop(1, "rgba(90, 52, 14, 0)");
  bCtx.fillStyle = frameGrad;
  bCtx.fillRect(0, 0, W, W);

  bCtx.save();
  bCtx.globalCompositeOperation = "multiply";
  const comfortGrad = bCtx.createRadialGradient(W * 0.5, W * 0.48, W * 0.08, W * 0.5, W * 0.48, W * 0.72);
  comfortGrad.addColorStop(0, "rgba(106, 72, 31, 0.22)");
  comfortGrad.addColorStop(0.42, "rgba(116, 76, 28, 0.14)");
  comfortGrad.addColorStop(0.78, "rgba(116, 76, 28, 0.06)");
  comfortGrad.addColorStop(1, "rgba(255,255,255,0)");
  bCtx.fillStyle = comfortGrad;
  bCtx.fillRect(0, 0, W, W);
  bCtx.restore();
}

function getStoneVariantId(x, y, color) {
  return ((x + 3) * 73856093 ^ (y + 5) * 19349663 ^ (color === "B" ? 83492791 : 29765729)) >>> 0;
}

function paintStoneTexture(sctx, color, cx, cy, r, variantId) {
  const normalized = (variantId % 997) / 997;
  const normalizedY = ((variantId >>> 8) % 991) / 991;
  if (color === "B" && isAssetReady(blackStoneTexture)) {
    const sourceSize = Math.max(
      Math.floor(blackStoneTexture.naturalWidth * 0.42),
      Math.floor(blackStoneTexture.naturalWidth * (0.46 + normalized * 0.18))
    );
    const maxSourceX = Math.max(0, blackStoneTexture.naturalWidth - sourceSize);
    const maxSourceY = Math.max(0, blackStoneTexture.naturalHeight - sourceSize);
    const sourceX = Math.floor(maxSourceX * normalized);
    const sourceY = Math.floor(maxSourceY * normalizedY);
    const angle = ((variantId % 5) - 2) * 0.03;
    sctx.save();
    sctx.translate(cx, cy);
    sctx.rotate(angle);
    sctx.globalAlpha = 0.18;
    sctx.drawImage(
      blackStoneTexture,
      sourceX,
      sourceY,
      sourceSize,
      sourceSize,
      -r * 1.02,
      -r * 1.02,
      r * 2.04,
      r * 2.04
    );
    sctx.restore();
    return;
  }

  if (color === "W" && isAssetReady(whiteStoneTexture)) {
    const halfWidth = Math.floor(whiteStoneTexture.naturalWidth / 2);
    const sheetHeight = whiteStoneTexture.naturalHeight;
    const sourceSize = Math.max(
      Math.floor(halfWidth * 0.54),
      Math.floor(halfWidth * (0.58 + normalized * 0.18))
    );
    const maxSourceX = Math.max(0, halfWidth - sourceSize);
    const maxSourceY = Math.max(0, sheetHeight - sourceSize);
    const sourceX = halfWidth + Math.floor(maxSourceX * normalized);
    const sourceY = Math.floor(maxSourceY * normalizedY);
    sctx.save();
    sctx.translate(cx, cy);
    sctx.rotate(((variantId % 7) - 3) * 0.05);
    sctx.globalAlpha = 0.58;
    sctx.drawImage(
      whiteStoneTexture,
      sourceX,
      sourceY,
      sourceSize,
      sourceSize,
      -r * 1.04,
      -r * 1.04,
      r * 2.08,
      r * 2.08
    );
    sctx.restore();
    sctx.save();
    sctx.globalCompositeOperation = "multiply";
    const warmShade = sctx.createRadialGradient(cx - r * 0.18, cy - r * 0.22, r * 0.12, cx, cy, r * 1.06);
    warmShade.addColorStop(0, "rgba(235, 224, 205, 0.12)");
    warmShade.addColorStop(0.58, "rgba(202, 187, 162, 0.18)");
    warmShade.addColorStop(1, "rgba(152, 132, 104, 0.24)");
    sctx.fillStyle = warmShade;
    sctx.beginPath();
    sctx.arc(cx, cy, r, 0, Math.PI * 2);
    sctx.fill();
    sctx.restore();
    return;
  }

  const fill = sctx.createRadialGradient(cx - r * 0.34, cy - r * 0.36, r * 0.08, cx + r * 0.16, cy + r * 0.2, r * 1.12);
  if (color === "B") {
    fill.addColorStop(0, "#363a3f");
    fill.addColorStop(0.22, "#171b1f");
    fill.addColorStop(0.72, "#07090d");
    fill.addColorStop(1, "#010203");
  } else {
    fill.addColorStop(0, "#eee8dc");
    fill.addColorStop(0.28, "#e5dfd1");
    fill.addColorStop(0.72, "#cfc6b7");
    fill.addColorStop(1, "#a69b89");
  }
  sctx.fillStyle = fill;
  sctx.fill();
}

function getStoneSprite(color, radius, variantId = 0) {
  const spriteScale = Math.max(5, Math.ceil(boardRenderDpr * 4));
  const spriteRadius = Math.max(18, Math.round(radius * spriteScale));
  const key = `${color}_${spriteRadius}_${spriteScale}_${variantId % 9}`;
  if (_stoneSpriteCache.has(key)) return _stoneSpriteCache.get(key);

  const pad = Math.ceil(spriteRadius * 0.48);
  const size = spriteRadius * 2 + pad * 2;
  const surface = document.createElement("canvas");
  surface.width = size;
  surface.height = size;
  const sctx = surface.getContext("2d");
  const cx = size / 2;
  const cy = size / 2;
  const r = spriteRadius;
  sctx.imageSmoothingEnabled = true;
  if ("imageSmoothingQuality" in sctx) sctx.imageSmoothingQuality = "high";

  sctx.save();
  sctx.shadowColor = "rgba(0,0,0,0.55)";
  sctx.shadowBlur = r * 0.45;
  sctx.shadowOffsetX = r * 0.18;
  sctx.shadowOffsetY = r * 0.22;
  sctx.beginPath();
  sctx.arc(cx, cy, r, 0, Math.PI * 2);
  const baseFill = sctx.createRadialGradient(cx - r * 0.34, cy - r * 0.36, r * 0.08, cx + r * 0.16, cy + r * 0.2, r * 1.12);
  if (color === "B") {
    baseFill.addColorStop(0, "#2a2d31");
    baseFill.addColorStop(0.42, "#14171a");
    baseFill.addColorStop(1, "#050607");
  } else {
    baseFill.addColorStop(0, "#eee8dc");
    baseFill.addColorStop(0.56, "#ded7ca");
    baseFill.addColorStop(1, "#bfb5a5");
  }
  sctx.fillStyle = baseFill;
  sctx.fill();
  sctx.restore();

  sctx.save();
  sctx.beginPath();
  sctx.arc(cx, cy, r, 0, Math.PI * 2);
  sctx.clip();
  paintStoneTexture(sctx, color, cx, cy, r, variantId);
  if (color === "B") {
    const rimShade = sctx.createRadialGradient(cx, cy, r * 0.58, cx, cy, r * 1.04);
    rimShade.addColorStop(0, "rgba(0,0,0,0)");
    rimShade.addColorStop(1, "rgba(0,0,0,0.20)");
    sctx.fillStyle = rimShade;
    sctx.fillRect(cx - r, cy - r, r * 2, r * 2);
  } else {
    const pearlShade = sctx.createRadialGradient(cx + r * 0.12, cy + r * 0.18, r * 0.16, cx, cy, r * 1.04);
    pearlShade.addColorStop(0, "rgba(255,255,255,0)");
    pearlShade.addColorStop(0.48, "rgba(242,232,212,0.04)");
    pearlShade.addColorStop(1, "rgba(126, 108, 86, 0.22)");
    sctx.fillStyle = pearlShade;
    sctx.fillRect(cx - r, cy - r, r * 2, r * 2);
  }
  sctx.strokeStyle = color === "B" ? "rgba(255,255,255,0.035)" : "rgba(242,232,210,0.36)";
  sctx.lineWidth = Math.max(1.1, r * 0.032);
  sctx.beginPath();
  sctx.arc(cx, cy, r - sctx.lineWidth / 2, 0, Math.PI * 2);
  sctx.stroke();

  const highlight = sctx.createRadialGradient(cx - r * 0.38, cy - r * 0.44, r * 0.02, cx - r * 0.34, cy - r * 0.38, r * 0.55);
  if (color === "B") {
    highlight.addColorStop(0, "rgba(255,255,255,0.055)");
    highlight.addColorStop(0.5, "rgba(255,255,255,0.016)");
    highlight.addColorStop(1, "rgba(255,255,255,0)");
  } else {
    highlight.addColorStop(0, "rgba(255,250,238,0.12)");
    highlight.addColorStop(0.5, "rgba(255,246,232,0.035)");
    highlight.addColorStop(1, "rgba(255,255,255,0)");
  }
  sctx.fillStyle = highlight;
  sctx.beginPath();
  sctx.ellipse(cx - r * 0.31, cy - r * 0.35, r * 0.22, r * 0.12, -Math.PI / 4, 0, Math.PI * 2);
  sctx.fill();

  if (color === "B") {
    sctx.fillStyle = "rgba(255,255,255,0.008)";
    sctx.beginPath();
    sctx.ellipse(cx + r * 0.02, cy - r * 0.02, r * 0.36, r * 0.18, -Math.PI / 7, 0, Math.PI * 2);
    sctx.fill();
  } else {
    sctx.fillStyle = "rgba(126, 112, 92, 0.055)";
    sctx.beginPath();
    sctx.ellipse(cx + r * 0.12, cy + r * 0.16, r * 0.34, r * 0.15, Math.PI / 8, 0, Math.PI * 2);
    sctx.fill();
  }
  sctx.restore();

  const sprite = { canvas: surface, size, scale: spriteScale };
  _stoneSpriteCache.set(key, sprite);
  return sprite;
}
