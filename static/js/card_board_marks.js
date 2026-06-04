// Card-specific board overlay drawing.

const CARD_MASK_TILE_CACHE = new Map();

const CARD_MASK_THEMES = {
  blackhole: {
    key: "blackhole",
    fill: ["rgba(56,24,78,.16)", "rgba(80,32,124,.24)"],
    stripe: "rgba(215,176,255,.11)",
    edge: "rgba(145,72,200,.42)",
    glow: "rgba(123,62,185,.24)",
    glyph: "?",
  },
  golden_corner: {
    key: "golden_corner",
    fill: ["rgba(120,89,24,.12)", "rgba(212,175,55,.22)"],
    stripe: "rgba(255,227,142,.12)",
    edge: "rgba(230,190,82,.44)",
    glow: "rgba(212,175,55,.22)",
    glyph: "!",
  },
  fog: {
    key: "fog",
    fill: ["rgba(40,72,92,.12)", "rgba(84,138,168,.22)"],
    stripe: "rgba(202,225,238,.11)",
    edge: "rgba(118,182,213,.4)",
    glow: "rgba(92,170,210,.2)",
    glyph: "",
  },
  seal: {
    key: "seal",
    fill: ["rgba(74,31,26,.12)", "rgba(168,54,48,.2)"],
    stripe: "rgba(255,194,170,.1)",
    edge: "rgba(220,82,72,.52)",
    glow: "rgba(220,68,52,.2)",
    glyph: "x",
  },
  pending_seal: {
    key: "pending_seal",
    fill: ["rgba(64,48,20,.12)", "rgba(212,175,55,.23)"],
    stripe: "rgba(255,233,166,.16)",
    edge: "rgba(244,203,100,.68)",
    glow: "rgba(244,203,100,.28)",
    glyph: "",
  },
  ai: {
    key: "ai",
    fill: ["rgba(92,26,38,.12)", "rgba(184,58,76,.21)"],
    stripe: "rgba(255,184,194,.11)",
    edge: "rgba(244,110,126,.48)",
    glow: "rgba(220,72,86,.2)",
    glyph: "!",
  },
};

function maskThemeForCard(cardId, ai = false) {
  if (ai && !["blackhole", "golden_corner", "fog"].includes(cardId)) return CARD_MASK_THEMES.ai;
  if (ai) return { ...CARD_MASK_THEMES[cardId], glyph: "!" };
  return CARD_MASK_THEMES[cardId] || CARD_MASK_THEMES.seal;
}

function buildMaskTile(theme, size) {
  const tile = document.createElement("canvas");
  tile.width = size;
  tile.height = size;
  const tctx = tile.getContext("2d");
  const gradient = tctx.createLinearGradient(0, 0, size, size);
  gradient.addColorStop(0, theme.fill[0]);
  gradient.addColorStop(1, theme.fill[1]);
  tctx.fillStyle = gradient;
  tctx.fillRect(0, 0, size, size);

  tctx.strokeStyle = theme.stripe;
  tctx.lineWidth = Math.max(1, size * 0.035);
  for (let d = -size; d < size * 2; d += Math.max(7, size * 0.34)) {
    tctx.beginPath();
    tctx.moveTo(d, size);
    tctx.lineTo(d + size, 0);
    tctx.stroke();
  }

  tctx.fillStyle = theme.glow;
  tctx.beginPath();
  tctx.arc(size * 0.5, size * 0.5, size * 0.42, 0, Math.PI * 2);
  tctx.fill();

  tctx.globalCompositeOperation = "destination-out";
  const hole = size * 0.24;
  tctx.fillStyle = "rgba(0,0,0,1)";
  tctx.fillRect(size * 0.5 - size * 0.035, 0, size * 0.07, size);
  tctx.fillRect(0, size * 0.5 - size * 0.035, size, size * 0.07);
  tctx.beginPath();
  tctx.arc(size * 0.5, size * 0.5, hole, 0, Math.PI * 2);
  tctx.fill();
  tctx.globalCompositeOperation = "source-over";

  tctx.strokeStyle = theme.edge;
  tctx.lineWidth = Math.max(1, size * 0.045);
  tctx.strokeRect(size * 0.06, size * 0.06, size * 0.88, size * 0.88);
  return tile;
}

function getMaskTile(theme) {
  const size = Math.max(14, Math.round(CELL));
  const key = `${theme.key}:${size}`;
  if (!CARD_MASK_TILE_CACHE.has(key)) {
    CARD_MASK_TILE_CACHE.set(key, buildMaskTile(theme, size));
  }
  return CARD_MASK_TILE_CACHE.get(key);
}

function drawTexturedMaskPoint(x, y, theme, glyph = theme.glyph) {
  const px = PAD + x * CELL;
  const py = PAD + y * CELL;
  const tile = getMaskTile(theme);
  ctx.drawImage(tile, px - CELL / 2, py - CELL / 2, CELL, CELL);

  ctx.save();
  ctx.strokeStyle = theme.edge;
  ctx.lineWidth = Math.max(1, CELL * 0.045);
  ctx.beginPath();
  ctx.arc(px, py, CELL * 0.36, 0, Math.PI * 2);
  ctx.stroke();
  if (glyph) {
    ctx.fillStyle = theme.edge;
    ctx.font = `${CELL * 0.22}px sans-serif`;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(glyph, px + CELL * 0.23, py - CELL * 0.22);
  }
  ctx.restore();
}

function drawMaskPoints(points, cardId, ai = false) {
  if (!Array.isArray(points) || points.length === 0) return;
  const theme = maskThemeForCard(cardId, ai);
  points.forEach(([sx, sy]) => drawTexturedMaskPoint(sx, sy, theme));
}

function drawSealSelectionOverlay() {
  if (!rogueSealing) return;
  const boardPx = PAD - CELL / 2;
  const boardSizePx = CELL * (boardSize - 1) + CELL;
  ctx.save();
  ctx.fillStyle = "rgba(0,0,0,.16)";
  ctx.fillRect(boardPx, boardPx, boardSizePx, boardSizePx);
  ctx.strokeStyle = "rgba(244,203,100,.18)";
  ctx.lineWidth = Math.max(1, CELL * 0.035);
  for (let i = 0; i < boardSize; i += 2) {
    const pos = PAD + i * CELL;
    ctx.beginPath();
    ctx.moveTo(PAD, pos);
    ctx.lineTo(PAD + (boardSize - 1) * CELL, pos);
    ctx.stroke();
  }
  pendingRogueSealPoints.forEach(([sx, sy], index) => {
    drawTexturedMaskPoint(sx, sy, CARD_MASK_THEMES.pending_seal, String(index + 1));
  });
  ctx.restore();
}

function drawRogueMarks() {
  ctx.save();
  drawSealSelectionOverlay();
  drawMaskPoints(rogueSeals, activeRogueCard, false);

  if (gameState && gameState.ko_point && !reviewMode) {
    const [kx, ky] = gameState.ko_point;
    if (gameState.board[ky][kx] === 0) {
      const px = PAD + kx * CELL;
      const py = PAD + ky * CELL;
      const r = CELL * 0.18;
      ctx.fillStyle = "rgba(220, 40, 40, 0.55)";
      ctx.fillRect(px - r, py - r, r * 2, r * 2);
    }
  }

  if (activeRogueCard === "joseki_ocd" && gameState
      && gameState.rogue_joseki_targets && !gameState.rogue_joseki_done) {
    const board = getCurrentBoard();
    gameState.rogue_joseki_targets.forEach(([tx, ty]) => {
      if (board && board[ty] && board[ty][tx] !== 0) return;
      const px = PAD + tx * CELL;
      const py = PAD + ty * CELL;
      ctx.strokeStyle = "rgba(0, 200, 80, 0.7)";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.arc(px, py, CELL * 0.38, 0, Math.PI * 2);
      ctx.stroke();
      ctx.fillStyle = "rgba(0, 200, 80, 0.15)";
      ctx.fill();
    });
  }

  if (activeRogueCard === "puppet" && gameState?.rogue_puppet_target) {
    const [tx, ty] = gameState.rogue_puppet_target;
    const board = getCurrentBoard();
    if (board && board[ty] && board[ty][tx] === 0) {
      const px = PAD + tx * CELL;
      const py = PAD + ty * CELL;
      ctx.strokeStyle = "rgba(188, 120, 255, 0.9)";
      ctx.lineWidth = 2.5;
      ctx.beginPath();
      ctx.arc(px, py, CELL * 0.34, 0, Math.PI * 2);
      ctx.stroke();
      ctx.fillStyle = "rgba(188, 120, 255, 0.18)";
      ctx.beginPath();
      ctx.arc(px, py, CELL * 0.24, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  if (activeRogueCard === "exchange" && typeof exchangeModeSource !== "undefined" && exchangeModeSource) {
    const px = PAD + exchangeModeSource.x * CELL;
    const py = PAD + exchangeModeSource.y * CELL;
    ctx.strokeStyle = "rgba(77, 209, 199, 0.95)";
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.arc(px, py, CELL * 0.42, 0, Math.PI * 2);
    ctx.stroke();
  }

  if (ultimatePlayerCard === "joseki_burst" && gameState
      && gameState.ultimate_joseki_targets && !gameState.ultimate_joseki_done) {
    const board = getCurrentBoard();
    gameState.ultimate_joseki_targets.forEach(([tx, ty]) => {
      if (board && board[ty] && board[ty][tx] === (myColor === "B" ? 1 : 2)) return;
      const px = PAD + tx * CELL;
      const py = PAD + ty * CELL;
      ctx.strokeStyle = "rgba(255, 120, 20, 0.85)";
      ctx.lineWidth = 2.5;
      ctx.beginPath();
      ctx.arc(px, py, CELL * 0.26, 0, Math.PI * 2);
      ctx.stroke();
      ctx.fillStyle = "rgba(255, 120, 20, 0.18)";
      ctx.beginPath();
      ctx.arc(px, py, CELL * 0.2, 0, Math.PI * 2);
      ctx.fill();
    });
  }

  drawMaskPoints(aiRogueSeals, activeAiRogueCard, true);
  ctx.restore();
}
