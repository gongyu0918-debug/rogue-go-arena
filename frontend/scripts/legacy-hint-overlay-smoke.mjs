import { mkdir, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { launchBrowser } from "./smoke-browser.mjs";

const urlArg = process.argv.find(arg => arg.startsWith("--url="));
const targetUrl = urlArg ? urlArg.slice(6) : "http://127.0.0.1:8876/?lang=zh";
const artifactDir = fileURLToPath(new URL("../../output/playwright/", import.meta.url));
const viewports = [{ width: 900, height: 600 }, { width: 1366, height: 768 }, { width: 1920, height: 1080 }];

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

async function inspectHints(page) {
  return page.evaluate(() => {
    clearVisualEffects();
    reviewMode = false;
    twoPlayerMode = true;
    showHints = false;
    showTerritory = false;
    hoverXY = null;
    fineTunePos = null;
    activeRogueCard = null;
    gameState = { size: 19, board: Array.from({ length: 19 }, () => Array(19).fill(0)), current_player: "B", game_over: false };
    gameState.board[9][11] = 1;
    gameState.board[10][9] = 2;
    analysis = { top_moves: [
      { x: 9, y: 9, winrate: .64 },
      { x: 10, y: 9, winrate: .61 },
      { x: 0, y: 0, winrate: .57 },
      { x: 11, y: 9, winrate: .54 }, // Occupied points must remain visible as stones.
      { x: 3, y: 4, winrate: .5 },
    ], ownership: [] };
    const visibleMoves = analysis.top_moves.filter(move => gameState.board[move.y][move.x] === 0);
    const snapshot = () => ctx.getImageData(0, 0, canvas.width, canvas.height).data;
    const pixel = (data, x, y) => Array.from(data.slice((y * canvas.width + x) * 4, (y * canvas.width + x) * 4 + 4));
    const centers = visibleMoves.map(move => ({
      x: Math.round((PAD + move.x * CELL) * boardRenderDpr),
      y: Math.round((PAD + move.y * CELL) * boardRenderDpr),
    }));
    const colorAt = (data, point) => {
      const radius = Math.floor(CELL * boardRenderDpr * .5);
      const histogram = new Map();
      for (let y = point.y - radius; y <= point.y + radius; y++) {
        for (let x = point.x - radius; x <= point.x + radius; x++) {
          const [r, g, b, a] = pixel(data, x, y);
          if (g > r + 60 && g > b + 40 && a === 255) {
            const key = `${r},${g},${b},${a}`;
            histogram.set(key, (histogram.get(key) || 0) + 1);
          }
        }
      }
      const [color, count] = [...histogram].sort((a, b) => b[1] - a[1])[0] || ["", 0];
      return { color, count };
    };
    render();
    const withoutHints = snapshot();
    showHints = true;
    const labels = [];
    const originalFillText = ctx.fillText;
    ctx.fillText = function(text, ...args) {
      if (/^\d+%$/.test(String(text))) labels.push(text);
      return originalFillText.call(this, text, ...args);
    };
    render();
    ctx.fillText = originalFillText;
    const withHints = snapshot();
    const normalColors = centers.map(point => colorAt(withHints, point));
    let spillPixels = 0;
    let occupiedChanges = 0;
    const cellHalf = CELL * boardRenderDpr * .5 + 1;
    for (let y = 0; y < canvas.height; y++) {
      for (let x = 0; x < canvas.width; x++) {
        const index = (y * canvas.width + x) * 4;
        if (withoutHints[index] === withHints[index] && withoutHints[index + 1] === withHints[index + 1] &&
          withoutHints[index + 2] === withHints[index + 2]) continue;
        if (!centers.some(point => Math.abs(x - point.x) <= cellHalf && Math.abs(y - point.y) <= cellHalf)) spillPixels++;
        const stoneX = (PAD + 11 * CELL) * boardRenderDpr;
        const stoneY = (PAD + 9 * CELL) * boardRenderDpr;
        if (Math.abs(x - stoneX) < CELL * boardRenderDpr * .35 && Math.abs(y - stoneY) < CELL * boardRenderDpr * .35) occupiedChanges++;
      }
    }

    hoverXY = { x: 9, y: 9 };
    render();
    const hoverColor = colorAt(snapshot(), centers[0]);
    fineTunePos = { x: 9, y: 9 };
    render();
    const fineTuneColor = colorAt(snapshot(), centers[0]);
    hoverXY = null;
    fineTunePos = null;
    showTerritory = true;
    analysis.ownership = Array.from({ length: 361 }, (_, i) => i % 2 ? 1 : -1);
    render();
    const territoryColor = colorAt(snapshot(), centers[0]);

    showTerritory = false;
    reviewMode = true;
    reviewBoardSize = 19;
    reviewMoves = [{ color: "B", gtp: "M10" }, { color: "W", gtp: "K9" }];
    reviewIndex = 1;
    render();
    const reviewColors = centers.map(point => colorAt(snapshot(), point));
    reviewMode = false;
    render();
    const rect = canvas.getBoundingClientRect();
    return { cell: CELL, boardRenderDpr, canvasWidth: canvas.width, boardRenderSize, displayWidth: rect.width,
      labels, normalColors, hoverColor, fineTuneColor, territoryColor, reviewColors, spillPixels, occupiedChanges };
  });
}

const browser = await launchBrowser();
const results = [];
const errors = [];
let referenceColor = null;
try {
  await mkdir(artifactDir, { recursive: true });
  for (const dpr of [1, 2]) {
    const page = await browser.newPage({ viewport: viewports[0], deviceScaleFactor: dpr });
    page.on("pageerror", error => errors.push(error.message));
    await page.goto(targetUrl, { waitUntil: "domcontentloaded" });
    await page.waitForFunction(() => boardRenderSize > 0 && isAssetReady(boardTextureImage) &&
      isAssetReady(blackStoneTexture) && isAssetReady(whiteStoneTexture));
    for (const viewport of viewports) {
      await page.setViewportSize(viewport);
      // Exercise the same resize path used by a window changing size.
      await page.evaluate(() => { resizeBoard(19); render(); });
      const state = await inspectHints(page);
      const name = `${viewport.width}x${viewport.height}-dpr${dpr}`;
      assert(state.canvasWidth === Math.floor(state.boardRenderSize * dpr), `${name}: canvas bitmap has the wrong DPR`);
      assert(state.labels.join(",") === "64%,61%,57%,50%", `${name}: hint values or occupied-point filtering changed: ${state.labels}`);
      assert(state.spillPixels === 0 && state.occupiedChanges === 0, `${name}: hint covered neighboring cells or stones: ${JSON.stringify(state)}`);
      const samples = [...state.normalColors, ...state.reviewColors, state.hoverColor, state.fineTuneColor, state.territoryColor];
      for (const sample of samples) {
        assert(sample.count >= 12 * dpr * dpr, `${name}: green is too faint or too small: ${JSON.stringify(sample)}`);
        referenceColor ||= sample.color;
        assert(sample.color === referenceColor, `${name}: green changed with size, rank, preview, territory, or review: ${JSON.stringify(sample)}`);
      }
      const [r, g, b] = referenceColor.split(",").map(Number);
      assert(g >= 190 && g - r >= 100 && g - b >= 60, `${name}: hint is no longer a distinct green: ${referenceColor}`);
      if (dpr === 1) {
        await page.screenshot({ path: `${artifactDir}hints-${name}.png` });
        await page.locator("#board-canvas").screenshot({ path: `${artifactDir}hints-board-${name}.png` });
      }
      results.push({ viewport: name, ...state });
    }
    await page.close();
  }
  assert(errors.length === 0, `hint browser errors: ${errors.join("; ")}`);
  await writeFile(`${artifactDir}hint-overlay-report.json`, JSON.stringify({ referenceColor, cases: results }, null, 2));
  console.log(JSON.stringify({ ok: true, referenceColor, cases: results.map(result => ({
    viewport: result.viewport, cell: result.cell, canvasWidth: result.canvasWidth, displayWidth: result.displayWidth,
    spillPixels: result.spillPixels, occupiedChanges: result.occupiedChanges,
  })), screenshots: artifactDir }, null, 2));
} finally {
  await browser.close();
}
