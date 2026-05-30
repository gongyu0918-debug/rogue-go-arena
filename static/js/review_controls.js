// Local review board, SGF import/export, and review-control bindings for the legacy UI.
// Review mode state
let reviewMode = false;
let reviewMoves = [];  // [{color, gtp}, ...]
let reviewIndex = -1;  // -1 = empty board
let reviewBoardSize = 19;
let reviewKomi = 7.5;
let sgfLoadedMode = false; // true if reviewing a loaded SGF


// LOCAL BOARD LOGIC (for review mode)
// ═══════════════════════════════════════════════════════════════════════════════
class LocalBoard {
  constructor(size) {
    this.size = size;
    this.grid = Array.from({length: size}, () => new Array(size).fill(0));
    this.captures = { B: 0, W: 0 };
  }

  clone() {
    const b = new LocalBoard(this.size);
    for (let y = 0; y < this.size; y++)
      for (let x = 0; x < this.size; x++)
        b.grid[y][x] = this.grid[y][x];
    b.captures.B = this.captures.B;
    b.captures.W = this.captures.W;
    return b;
  }

  neighbors(x, y) {
    const n = [];
    if (x > 0) n.push([x-1, y]);
    if (x < this.size-1) n.push([x+1, y]);
    if (y > 0) n.push([x, y-1]);
    if (y < this.size-1) n.push([x, y+1]);
    return n;
  }

  getGroup(x, y) {
    const color = this.grid[y][x];
    if (!color) return [];
    const group = [];
    const visited = new Set();
    const stack = [[x, y]];
    while (stack.length) {
      const [cx, cy] = stack.pop();
      const key = cy * this.size + cx;
      if (visited.has(key)) continue;
      visited.add(key);
      group.push([cx, cy]);
      for (const [nx, ny] of this.neighbors(cx, cy)) {
        if (this.grid[ny][nx] === color && !visited.has(ny * this.size + nx)) {
          stack.push([nx, ny]);
        }
      }
    }
    return group;
  }

  hasLiberty(group) {
    for (const [x, y] of group) {
      for (const [nx, ny] of this.neighbors(x, y)) {
        if (this.grid[ny][nx] === 0) return true;
      }
    }
    return false;
  }

  play(x, y, color) {
    const cv = color === "B" ? 1 : 2;
    const ov = 3 - cv;
    this.grid[y][x] = cv;
    let captured = [];
    for (const [nx, ny] of this.neighbors(x, y)) {
      if (this.grid[ny][nx] === ov) {
        const grp = this.getGroup(nx, ny);
        if (!this.hasLiberty(grp)) {
          for (const [gx, gy] of grp) {
            this.grid[gy][gx] = 0;
          }
          captured.push(...grp);
        }
      }
    }
    this.captures[color] += captured.length;
    return captured;
  }
}

function gtpToCoord(gtp, size) {
  if (!gtp || gtp.toUpperCase() === "PASS") return null;
  const col = COLS.indexOf(gtp[0].toUpperCase());
  const row = size - parseInt(gtp.slice(1));
  if (col >= 0 && col < size && row >= 0 && row < size) return [col, row];
  return null;
}

// Build board state at move index (-1 = empty)
function buildBoardAtIndex(moves, size, index) {
  const board = new LocalBoard(size);
  const limit = Math.min(index + 1, moves.length);
  for (let i = 0; i < limit; i++) {
    const coord = gtpToCoord(moves[i].gtp, size);
    if (coord) board.play(coord[0], coord[1], moves[i].color);
  }
  return board;
}

// ═══════════════════════════════════════════════════════════════════════════════

// SGF IMPORT / EXPORT
// ═══════════════════════════════════════════════════════════════════════════════
function coordToSgf(x, y) {
  return String.fromCharCode(97 + x) + String.fromCharCode(97 + y);
}

function sgfToCoord(sgf, size) {
  if (!sgf || sgf.length < 2) return null;
  const x = sgf.charCodeAt(0) - 97;
  const y = sgf.charCodeAt(1) - 97;
  if (x >= 0 && x < size && y >= 0 && y < size) return [x, y];
  return null;
}

function sgfCoordToGtp(sgf, size) {
  const coord = sgfToCoord(sgf, size);
  if (!coord) return "pass";
  return COLS[coord[0]] + (size - coord[1]);
}

function exportSgf() {
  const moves = reviewMode ? reviewMoves : (gameState?.moves_list || []).map(m => ({color: m[0], gtp: m[1]}));
  if (!moves.length) { alert("暂无棋谱可保存"); return; }
  const sz = reviewMode ? reviewBoardSize : (gameState?.size || 19);
  const km = reviewMode ? reviewKomi : (gameState?.komi || 7.5);
  const dt = new Date().toISOString().slice(0, 10);

  let sgf = `(;GM[1]FF[4]CA[UTF-8]AP[rogue-go-arena:1.0]SZ[${sz}]KM[${km}]DT[${dt}]\n`;
  for (const m of moves) {
    const gtp = m.gtp || m[1];
    const color = m.color || m[0];
    const coord = gtpToCoord(gtp, sz);
    const prop = color === "B" ? "B" : "W";
    if (coord) {
      sgf += `;${prop}[${coordToSgf(coord[0], coord[1])}]\n`;
    } else {
      sgf += `;${prop}[]\n`; // pass
    }
  }
  sgf += ")\n";

  const blob = new Blob([sgf], { type: "application/x-go-sgf" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `rogue-go-arena_${dt}.sgf`;
  a.click();
  URL.revokeObjectURL(url);
  logI18n("棋谱已保存", "SGF saved", "棋譜を保存しました", "기보 저장됨");
}

function parseSgf(text) {
  const moves = [];
  let size = 19, komi = 7.5;

  // Extract properties
  const szMatch = text.match(/SZ\[(\d+)\]/);
  if (szMatch) size = parseInt(szMatch[1]);
  const kmMatch = text.match(/KM\[([\d.+-]+)\]/);
  if (kmMatch) komi = parseFloat(kmMatch[1]);

  // Extract moves
  const moveRegex = /;([BW])\[([a-s]{0,2})\]/g;
  let m;
  while ((m = moveRegex.exec(text)) !== null) {
    const color = m[1];
    const sgfCoord = m[2];
    const gtp = sgfCoord ? sgfCoordToGtp(sgfCoord, size) : "pass";
    moves.push({ color, gtp });
  }

  return { size, komi, moves };
}

function loadSgfFile(file) {
  const reader = new FileReader();
  reader.onload = (e) => {
    try {
      const { size, komi, moves } = parseSgf(e.target.result);
      if (moves.length === 0) { alert(ui("棋谱中未找到有效着法", "No valid moves were found in the SGF")); return; }

      // Enter review mode with loaded SGF
      sgfLoadedMode = true;
      reviewMoves = moves;
      reviewBoardSize = size;
      reviewKomi = komi;
      reviewIndex = moves.length - 1;
      reviewMode = true;

      resizeBoard(size);
      updateReviewUI();
      render();
      logI18n(
        `已导入棋谱：${moves.length}手 ${size}×${size} 贴目${komi}`,
        `SGF loaded: ${moves.length} moves, ${size}x${size}, komi ${komi}`,
        `棋譜を読み込みました：${moves.length}手 ${size}×${size} コミ${komi}`,
        `기보 불러옴: ${moves.length}수 ${size}×${size} 덤 ${komi}`
      );

      // Request analysis for current position
      requestReviewAnalysis();
    } catch (err) {
      alert(ui("棋谱解析失败: ", "Failed to parse SGF: ") + err.message);
    }
  };
  reader.readAsText(file);
}

// ═══════════════════════════════════════════════════════════════════════════════
// REVIEW MODE
// ═══════════════════════════════════════════════════════════════════════════════
function enterReviewMode() {
  closeOverlay();
  if (!gameState && !sgfLoadedMode) return;

  if (!sgfLoadedMode) {
    const ml = gameState.moves_list || [];
    reviewMoves = ml.map(m => ({ color: m[0], gtp: m[1] }));
    reviewBoardSize = gameState.size || boardSize;
    reviewKomi = gameState.komi || 7.5;
  }
  reviewMode = true;
  reviewIndex = reviewMoves.length - 1;

  stopTimerTick();
  
  // Toggle toolbars
  const mainBar = document.getElementById("main-toolbar");
  if (mainBar) mainBar.style.display = "none";
  const revBar = document.getElementById("review-toolbar");
  if (revBar) revBar.style.display = "flex";

  updateReviewUI();
  render();
  requestReviewAnalysis();
}

function exitReviewMode() {
  reviewMode = false;
  sgfLoadedMode = false;
  reviewMoves = [];
  reviewIndex = -1;
  
  // Toggle toolbars back
  const mainBar = document.getElementById("main-toolbar");
  if (mainBar) mainBar.style.display = "flex";
  const revBar = document.getElementById("review-toolbar");
  if (revBar) revBar.style.display = "none";
  
  document.getElementById("review-info").textContent = "";
  if (gameState) {
    resizeBoard(gameState.size || boardSize);
    render();
  }
}

function reviewGo(idx) {
  if (!reviewMode || reviewMoves.length === 0) return;
  reviewIndex = Math.max(-1, Math.min(idx, reviewMoves.length - 1));
  updateReviewUI();
  render();
  requestReviewAnalysis();
}

function updateReviewUI() {
  const total = reviewMoves.length;
  const cur = reviewIndex + 1;
  const infoEl = document.getElementById("review-info");
  if (infoEl) {
    infoEl.textContent = reviewMode ? ui(`第 ${cur}/${total} 手`, `Move ${cur}/${total}`) : "";
  }
}

function requestReviewAnalysis() {
  if (!reviewMode || reviewMoves.length === 0) return;
  const moves = reviewMoves.slice(0, reviewIndex + 1).map(m => [m.color, m.gtp]);
  sendWS({
    action: "load_position",
    size: reviewBoardSize,
    komi: reviewKomi,
    moves,
  });
}

// ═══════════════════════════════════════════════════════════════════════════════

// Review controls
document.getElementById("btn-review-first").addEventListener("click", () => {
  if (!reviewMode && gameState) enterReviewMode();
  reviewGo(-1);
});
document.getElementById("btn-review-prev").addEventListener("click", () => {
  if (!reviewMode && gameState) enterReviewMode();
  reviewGo(reviewIndex - 1);
});
document.getElementById("btn-review-next").addEventListener("click", () => {
  if (!reviewMode && gameState) enterReviewMode();
  reviewGo(reviewIndex + 1);
});
document.getElementById("btn-review-last").addEventListener("click", () => {
  if (!reviewMode && gameState) enterReviewMode();
  reviewGo(reviewMoves.length - 1);
});
document.getElementById("btn-review-exit").addEventListener("click", () => {
  exitReviewMode();
});

// Keyboard shortcuts for review
document.addEventListener("keydown", (e) => {
  if (e.target.tagName === "INPUT" || e.target.tagName === "SELECT" || e.target.tagName === "TEXTAREA") return;
  if (e.key === "ArrowLeft") {
    if (!reviewMode && gameState) enterReviewMode();
    if (reviewMode) reviewGo(reviewIndex - 1);
    e.preventDefault();
  } else if (e.key === "ArrowRight") {
    if (!reviewMode && gameState) enterReviewMode();
    if (reviewMode) reviewGo(reviewIndex + 1);
    e.preventDefault();
  } else if (e.key === "Home") {
    if (reviewMode) reviewGo(-1);
    e.preventDefault();
  } else if (e.key === "End") {
    if (reviewMode) reviewGo(reviewMoves.length - 1);
    e.preventDefault();
  } else if (e.key === "Escape") {
    if (reviewMode) exitReviewMode();
  }
});

// SGF controls
document.getElementById("btn-sgf-save").addEventListener("click", exportSgf);
document.getElementById("btn-sgf-load").addEventListener("click", () => {
  document.getElementById("sgf-file-input").click();
});
document.getElementById("sgf-file-input").addEventListener("change", (e) => {
  const file = e.target.files[0];
  if (file) loadSgfFile(file);
  e.target.value = ""; // reset so same file can be loaded again
});

