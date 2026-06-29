// Board drawing and visual overlays.

function drawBoard() {
  const size = boardSize, W = boardRenderSize || Math.round(canvas.width / boardRenderDpr);
  const currentParams = `${size}_${W}`;

  if (_boardCacheParams === currentParams && _offScreenBoard) {
    ctx.drawImage(_offScreenBoard, 0, 0);
    return;
  }

  _boardCacheParams = currentParams;
  _offScreenBoard = document.createElement("canvas");
  _offScreenBoard.width = W;
  _offScreenBoard.height = W;
  const bCtx = _offScreenBoard.getContext("2d");
  bCtx.imageSmoothingEnabled = true;
  if ("imageSmoothingQuality" in bCtx) bCtx.imageSmoothingQuality = "high";
  paintBoardBase(bCtx, W);

  bCtx.strokeStyle = "rgba(68, 40, 11, 0.72)";
  bCtx.lineWidth = 1.26;
  for (let i = 0; i < size; i++) {
    const p = PAD + i * CELL;
    bCtx.beginPath(); bCtx.moveTo(p, PAD); bCtx.lineTo(p, PAD + (size-1)*CELL); bCtx.stroke();
    bCtx.beginPath(); bCtx.moveTo(PAD, p); bCtx.lineTo(PAD + (size-1)*CELL, p); bCtx.stroke();
  }

  bCtx.strokeStyle = "rgba(54, 30, 7, 0.88)";
  bCtx.lineWidth = 2.5;
  bCtx.strokeRect(PAD - 1, PAD - 1, (size-1)*CELL + 2, (size-1)*CELL + 2);

  bCtx.fillStyle = "rgba(43, 23, 4, 0.95)";
  getStarPoints(size).forEach(([sx, sy]) => {
    bCtx.beginPath();
    bCtx.arc(PAD + sx*CELL, PAD + sy*CELL, CELL * .13, 0, Math.PI*2);
    bCtx.fill();
  });

  bCtx.fillStyle = "rgba(84, 49, 14, 0.76)";
  const fs = Math.max(9, Math.min(CELL * .35, 14));
  bCtx.font = `600 ${fs}px "Consolas", monospace`;
  bCtx.textAlign = "center"; bCtx.textBaseline = "middle";
  for (let i = 0; i < size; i++) {
    const p = PAD + i * CELL;
    bCtx.fillText(COLS[i], p, PAD * .42);
    bCtx.fillText(COLS[i], p, PAD + (size-1)*CELL + PAD * .58);
    bCtx.fillText(size - i, PAD * .38, p);
    bCtx.fillText(size - i, PAD + (size-1)*CELL + PAD * .62, p);
  }

  ctx.drawImage(_offScreenBoard, 0, 0);
}

function getStarPoints(size) {
  if (size === 19) return [[3,3],[9,3],[15,3],[3,9],[9,9],[15,9],[3,15],[9,15],[15,15]];
  if (size === 13) return [[3,3],[9,3],[3,9],[9,9],[6,6]];
  if (size === 9)  return [[2,2],[6,2],[2,6],[6,6],[4,4]];
  return [];
}

function drawStone(x, y, color, scale) {
  scale = scale || 1;
  const cx = PAD + x * CELL, cy = PAD + y * CELL;
  const r = CELL * .47 * scale;
  if (r <= 0) return;
  const sprite = getStoneSprite(color, r, getStoneVariantId(x, y, color));
  const drawSize = sprite.size / sprite.scale;
  ctx.save();
  ctx.imageSmoothingEnabled = true;
  if ("imageSmoothingQuality" in ctx) ctx.imageSmoothingQuality = "high";
  ctx.drawImage(sprite.canvas, cx - drawSize / 2, cy - drawSize / 2, drawSize, drawSize);
  ctx.restore();
}

function drawStones() {
  const board = getCurrentBoard();
  if (!board) return;
  const sz = getCurrentSize();

  for (let y = 0; y < sz; y++) {
    for (let x = 0; x < sz; x++) {
      const v = board[y][x];
      if (!v) continue;
      const color = v === 1 ? "B" : "W";
      const anim = animations.find(a => a.type === "place" && a.x === x && a.y === y);
      if (anim) {
        const t = (performance.now() - anim.startTime) / anim.duration;
        const scale = Math.min(1, t < 0.5 ? t * 2 * 1.08 : 1.08 - (t - 0.5) * 0.16);
        drawStone(x, y, color, scale);
      } else {
        drawStone(x, y, color);
      }
    }
  }

  const now = performance.now();
  for (const anim of animations) {
    if (anim.type !== "capture") continue;
    const t = (now - anim.startTime) / anim.duration;
    if (t >= 1) continue;
    const alpha = 1 - t;
    const scale = 1 - t * 0.3;
    ctx.save();
    ctx.globalAlpha = alpha;
    drawStone(anim.x, anim.y, anim.color, scale);
    ctx.restore();
  }

  if (!reviewMode) {
    if (lastAiMove && lastAiMove.x !== null) {
      drawLastMoveMarker(lastAiMove.x, lastAiMove.y, lastAiMove.color);
    }
  } else if (reviewIndex >= 0) {
    const lastM = reviewMoves[reviewIndex];
    if (lastM) {
      const coord = gtpToCoord(lastM.gtp, sz);
      if (coord) drawLastMoveMarker(coord[0], coord[1], lastM.color);
    }
  }

  if (showMoveNumbers) drawMoveNumbers();
}

function drawLastMoveMarker(x, y, color) {
  const cx = PAD + x * CELL, cy = PAD + y * CELL;
  ctx.save();
  ctx.strokeStyle = color === "B" ? "#fff" : "#000";
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.arc(cx, cy, CELL * .18, 0, Math.PI * 2);
  ctx.stroke();
  ctx.restore();
}

function drawMoveNumbers() {
  const moves = reviewMode ? reviewMoves : (gameState?.moves_list || []).map(m => ({color: m[0], gtp: m[1]}));
  const sz = getCurrentSize();
  const limit = reviewMode ? reviewIndex + 1 : moves.length;
  const posMap = new Map();
  const board = new LocalBoard(sz);

  for (let i = 0; i < limit; i++) {
    const m = moves[i];
    const coord = gtpToCoord(m.gtp, sz);
    if (!coord) continue;
    const captured = board.play(coord[0], coord[1], m.color);
    for (const [cx, cy] of captured) {
      posMap.delete(`${cx},${cy}`);
    }
    posMap.set(`${coord[0]},${coord[1]}`, { number: i + 1, color: m.color });
  }

  ctx.save();
  const fontSize = Math.max(8, Math.min(CELL * .32, 14));
  ctx.font = `700 ${fontSize}px "Consolas", monospace`;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";

  for (const [key, val] of posMap) {
    const [x, y] = key.split(",").map(Number);
    const cx = PAD + x * CELL, cy = PAD + y * CELL;
    ctx.fillStyle = val.color === "B" ? "#ddd" : "#222";
    ctx.fillText(val.number, cx, cy);
  }
  ctx.restore();
}

function roundedRectPath(x, y, w, h, r) {
  const rr = Math.min(r, w / 2, h / 2);
  ctx.beginPath();
  ctx.moveTo(x + rr, y);
  ctx.arcTo(x + w, y, x + w, y + h, rr);
  ctx.arcTo(x + w, y + h, x, y + h, rr);
  ctx.arcTo(x, y + h, x, y, rr);
  ctx.arcTo(x, y, x + w, y, rr);
  ctx.closePath();
}

function drawHintPercentChip(cx, cy, pct, rank) {
  const chipR = Math.max(12, CELL * 0.27);
  const hue = rank === 0 ? 88 : 84 - rank * 4;
  ctx.save();
  ctx.shadowColor = "rgba(0,0,0,.14)";
  ctx.shadowBlur = CELL * 0.12;
  ctx.beginPath();
  ctx.arc(cx, cy, chipR, 0, Math.PI * 2);
  ctx.fillStyle = `hsla(${hue}, 42%, 58%, 0.88)`;
  ctx.fill();
  ctx.strokeStyle = `hsla(${hue}, 38%, 24%, 0.86)`;
  ctx.lineWidth = 1.4;
  ctx.stroke();
  ctx.shadowBlur = 0;
  ctx.fillStyle = "#1f3216";
  ctx.font = `700 ${Math.max(9, Math.min(13, CELL * 0.24))}px "Microsoft YaHei", sans-serif`;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(`${pct}%`, cx, cy);
  ctx.restore();
}

function drawHints() {
  if (!showHints || reviewMode) return;
  if (isHintLockedByCard()) return;
  if (!analysis || !analysis.top_moves || !analysis.top_moves.length) return;
  if (!gameState || gameState.game_over) return;
  const myTurn = twoPlayerMode ? true : (gameState.current_player === myColor);
  if (!myTurn) return;

  const board = getCurrentBoard();
  const moves = analysis.top_moves.slice(0, 5);
  moves.forEach((m, i) => {
    if (m.x === undefined || m.x === null) return;
    if (board && board[m.y][m.x] !== 0) return;
    const cx = PAD + m.x * CELL;
    const cy = PAD + m.y * CELL;
    const box = CELL * (i === 0 ? 0.56 : 0.5);
    const pct = Math.round(m.winrate * 100);

    if (i > 0) {
      ctx.save();
      roundedRectPath(cx - box / 2, cy - box / 2, box, box, box * 0.14);
      ctx.fillStyle = `rgba(229,219,198,${0.16 - i * 0.025})`;
      ctx.fill();
      ctx.strokeStyle = `rgba(106,78,39,${0.12 - i * 0.014})`;
      ctx.lineWidth = 1;
      ctx.stroke();
      ctx.restore();
    } else {
      const r = CELL * 0.43;
      const g = ctx.createRadialGradient(
        cx - r * 0.35, cy - r * 0.35, r * 0.1,
        cx, cy, r
      );
      g.addColorStop(0, "rgba(76,74,65,.92)");
      g.addColorStop(0.55, "rgba(32,31,28,.94)");
      g.addColorStop(1, "rgba(13,12,10,.94)");
      ctx.save();
      ctx.shadowColor = "rgba(0,0,0,.28)";
      ctx.shadowBlur = CELL * 0.3;
      ctx.beginPath();
      ctx.arc(cx, cy, r, 0, Math.PI * 2);
      ctx.fillStyle = g;
      ctx.fill();
      ctx.lineWidth = 1.5;
      ctx.strokeStyle = "rgba(226,204,154,.13)";
      ctx.stroke();
      ctx.shadowBlur = 0;
      ctx.restore();
    }
    drawHintPercentChip(cx, cy, pct, i);
  });
}

function drawTerritory() {
  if (!showTerritory || !analysis || !analysis.ownership || analysis.ownership.length === 0) return;
  const board = getCurrentBoard();
  const sz = getCurrentSize();
  const own = analysis.ownership;

  for (let y = 0; y < sz; y++) {
    for (let x = 0; x < sz; x++) {
      if (board && board[y][x] !== 0) continue;
      const v = own[y * sz + x];
      if (v === undefined || Math.abs(v) < 0.25) continue;
      const cx = PAD + x * CELL, cy = PAD + y * CELL;
      const alpha = Math.min(0.52, Math.abs(v) * 0.58);
      const r = CELL * 0.22;
      ctx.beginPath();
      ctx.arc(cx, cy, r, 0, Math.PI * 2);
      if (v > 0) {
        ctx.fillStyle = `rgba(30,30,30,${alpha})`;
        ctx.fill();
        ctx.strokeStyle = `rgba(0,0,0,${alpha * 0.6})`; ctx.lineWidth = 0.5; ctx.stroke();
      } else {
        ctx.fillStyle = `rgba(222,214,198,${alpha})`;
        ctx.fill();
        ctx.strokeStyle = `rgba(132,118,96,${alpha * 0.55})`; ctx.lineWidth = 0.5; ctx.stroke();
      }
    }
  }
}

function drawReviewHints() {
  if (!reviewMode || !showHints) return;
  if (isHintLockedByCard()) return;
  if (!analysis.top_moves || !analysis.top_moves.length) return;

  const board = buildBoardAtIndex(reviewMoves, reviewBoardSize, reviewIndex);
  const moves = analysis.top_moves.slice(0, 5);
  moves.forEach((m, i) => {
    if (m.x === undefined || m.x === null) return;
    if (board.grid[m.y][m.x] !== 0) return;
    const cx = PAD + m.x * CELL;
    const cy = PAD + m.y * CELL;
    const pct = Math.round(m.winrate * 100);

    if (i === 0) {
      const r = CELL * 0.43;
      const g = ctx.createRadialGradient(cx - r * 0.35, cy - r * 0.35, r * 0.1, cx, cy, r);
      g.addColorStop(0, "rgba(76,74,65,.86)");
      g.addColorStop(0.55, "rgba(32,31,28,.9)");
      g.addColorStop(1, "rgba(13,12,10,.9)");
      ctx.save();
      ctx.shadowColor = "rgba(0,0,0,.28)";
      ctx.shadowBlur = CELL * 0.3;
      ctx.beginPath(); ctx.arc(cx, cy, r, 0, Math.PI * 2);
      ctx.fillStyle = g; ctx.fill();
      ctx.shadowBlur = 0;
      ctx.restore();
    } else {
      const box = CELL * 0.5;
      ctx.save();
      roundedRectPath(cx - box / 2, cy - box / 2, box, box, box * 0.14);
      ctx.fillStyle = `rgba(229,219,198,${0.15 - i * 0.024})`;
      ctx.fill();
      ctx.restore();
    }
    drawHintPercentChip(cx, cy, pct, i);
  });
}

function render() {
  ctx.setTransform(boardRenderDpr, 0, 0, boardRenderDpr, 0, 0);
  ctx.clearRect(0, 0, boardRenderSize, boardRenderSize);
  drawBoard();
  drawTerritory();
  drawStones();
  drawRogueMarks();
  if (reviewMode) {
    drawReviewHints();
  } else {
    drawHints();
  }

  if (!reviewMode) {
    const canClick = twoPlayerMode ? (gameState && !gameState.game_over) : isMyTurn;
    const hoverColor = twoPlayerMode ? (gameState && gameState.current_player) || myColor : myColor;
    const board = getCurrentBoard();
    if (canClick && board) {
      if (fineTunePos) {
        ctx.save();
        ctx.globalAlpha = 0.55;
        drawStone(fineTunePos.x, fineTunePos.y, hoverColor, 0.95);
        ctx.restore();
      } else if (hoverXY) {
        const {x, y} = hoverXY;
        if (x >= 0 && x < boardSize && y >= 0 && y < boardSize && board[y][x] === 0) {
          ctx.save();
          ctx.globalAlpha = 0.4;
          drawStone(x, y, hoverColor, 0.95);
          ctx.restore();
        }
      }
    }
  }
  updateFinetuneUI();
}
