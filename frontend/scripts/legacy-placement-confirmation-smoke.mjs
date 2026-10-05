import { mkdir, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { launchBrowser } from "./smoke-browser.mjs";

const targetUrl = process.argv.find(arg => arg.startsWith("--url="))?.slice(6) || "http://127.0.0.1:8890/";
const artifactDir = fileURLToPath(new URL("../../output/playwright/", import.meta.url));
const browser = await launchBrowser();
const results = [];
const errors = [];
const assert = (condition, message) => { if (!condition) throw new Error(message); };

try {
  const page = await browser.newPage({ viewport: { width: 1366, height: 768 }, reducedMotion: "no-preference" });
  page.setDefaultTimeout(10000);
  page.on("pageerror", error => errors.push(error.message));
  await page.goto(targetUrl, { waitUntil: "load" });
  await page.waitForFunction(() => ws?.readyState === WebSocket.OPEN && boardRenderSize > 0);
  await page.evaluate(() => {
    window.__placementProbe = { places: [], sounds: 0, captures: [], frames: [] };
    // Delay only the processing of real authoritative replies. This also works
    // on Edge 109 without requiring newer browser WebSocket interception APIs.
    window.__ackDelay = 0;
    const originalHandleMessage = handleMessage;
    handleMessage = window.handleMessage = message => {
      if (message.type === "game_state" && window.__ackDelay) {
        setTimeout(() => originalHandleMessage(message), window.__ackDelay);
      } else originalHandleMessage(message);
    };
    const originalPlace = addPlaceAnimation;
    addPlaceAnimation = window.addPlaceAnimation = (x, y) => {
      window.__placementProbe.places.push({ x, y, time: performance.now() });
      originalPlace(x, y);
    };
    playStoneSound = window.playStoneSound = () => { window.__placementProbe.sounds++; };
    const originalCapture = addCaptureAnimation;
    addCaptureAnimation = window.addCaptureAnimation = stones => {
      window.__placementProbe.captures.push(stones);
      originalCapture(stones);
    };
    const originalDraw = drawStone;
    drawStone = window.drawStone = (x, y, color, scale) => {
      if (ctx.globalAlpha === 1) window.__placementProbe.frames.push({ x, y, color, scale: scale ?? 1, time: performance.now() });
      originalDraw(x, y, color, scale);
    };
  });

  async function newGame() {
    await page.evaluate(() => {
      sendWS({ action: "new_game", size: 9, komi: 7.5, handicap: 0, player_color: "B", level: "10k", two_player: true });
    });
    await page.waitForFunction(() => gameState?.size === 9 && gameState.move_number === 0);
    await page.evaluate(() => {
      clearVisualEffects();
      showHints = false;
      showTerritory = false;
      hoverXY = null;
      fineTunePos = null;
      document.getElementById("sel-placement").value = "direct";
    });
  }
  async function clickPoint(x, y, expectedMove) {
    const point = await page.evaluate(({ x, y }) => {
      const rect = canvas.getBoundingClientRect();
      return { x: rect.left + (PAD + x * CELL) * rect.width / boardRenderSize,
        y: rect.top + (PAD + y * CELL) * rect.height / boardRenderSize };
    }, { x, y });
    await page.mouse.click(point.x, point.y);
    if (expectedMove !== undefined) await page.waitForFunction(n => gameState.move_number === n, expectedMove);
  }
  async function resetProbe() {
    await page.evaluate(() => {
      clearVisualEffects();
      lastPlayTime = 0;
      window.__placementProbe = { places: [], sounds: 0, captures: [], frames: [] };
    });
  }
  for (const delay of [60, 280]) {
    await page.evaluate(delay => { window.__ackDelay = delay; }, delay);
    await newGame();
    await resetProbe();
    await clickPoint(4, 4, 1);
    await page.waitForTimeout(210);
    const probe = await page.evaluate(() => ({ ...window.__placementProbe, boardValue: gameState.board[4][4], move: gameState.move_number }));
    results.push({ delay, ...probe });
    assert(probe.places.length === 1, `one click restarted placement ${probe.places.length} times with ${delay}ms acknowledgement delay`);
    assert(probe.sounds === 1, `one click played ${probe.sounds} stone sounds`);
    assert(probe.boardValue === 1 && probe.move === 1, "one click did not remain one authoritative move");
  }

  // Micro-adjust confirmation follows the same optimistic/authoritative path.
  await page.evaluate(() => { window.__ackDelay = 60; });
  await newGame();
  await resetProbe();
  await page.evaluate(() => { document.getElementById("sel-placement").value = "fine"; });
  await clickPoint(3, 3);
  await page.locator("#ft-ok").click();
  await page.waitForFunction(() => gameState.move_number === 1);
  const fine = await page.evaluate(() => ({ ...window.__placementProbe, boardValue: gameState.board[3][3] }));
  assert(fine.places.length === 1 && fine.sounds === 1 && fine.boardValue === 1, "fine placement replayed on confirmation");

  await page.evaluate(() => { window.__ackDelay = 0; });
  await newGame();
  const captureSequence = [[1, 0], [1, 1], [0, 1], [8, 8], [2, 1], [8, 7]];
  for (const [index, [x, y]] of captureSequence.entries()) {
    await resetProbe();
    await clickPoint(x, y, index + 1);
  }
  await resetProbe();
  await clickPoint(1, 2, 7);
  const capture = await page.evaluate(() => ({ ...window.__placementProbe, capturedValue: gameState.board[1][1], capturesB: gameState.captures.B }));
  assert(capture.places.length === 1 && capture.sounds === 1, "capturing move replayed on confirmation");
  assert(capture.capturedValue === 0 && capture.capturesB === 1 && capture.captures.flat().some(s => s[0] === 1 && s[1] === 1), "capture animation/state was lost");

  // The surrounded center is an illegal suicide. The backend must undo the preview.
  await resetProbe();
  await clickPoint(1, 1);
  await page.waitForFunction(() => gameState.board[1][1] === 0 && document.getElementById("game-log").textContent.includes("自杀"));
  const rejected = await page.evaluate(() => ({ boardValue: gameState.board[1][1], move: gameState.move_number, isMyTurn }));
  assert(rejected.boardValue === 0 && rejected.move === 7 && rejected.isMyTurn, "rejected optimistic move did not restore the board/turn");

  // Remote/AI stones have no local preview and must still animate; duplicate
  // state and analysis messages must not replay them.
  const remote = await page.evaluate(() => {
    clearVisualEffects();
    const state = JSON.parse(JSON.stringify(gameState));
    state.board[5][5] = 2;
    state.move_number++;
    window.__placementProbe = { places: [], sounds: 0, captures: [], frames: [] };
    handleMessage({ ...state, type: "game_state" });
    handleMessage({ ...state, type: "game_state" });
    handleMessage({ type: "analysis", winrate: .5, score: 0, top_moves: [], ownership: [], analysis_ready: false });
    return { places: window.__placementProbe.places.length, sounds: window.__placementProbe.sounds };
  });
  assert(remote.places === 1 && remote.sounds === 1, "remote stone animation or duplicate-state handling broke");

  await page.emulateMedia({ reducedMotion: "reduce" });
  await newGame();
  await resetProbe();
  await clickPoint(4, 4, 1);
  const reducedMotion = await page.evaluate(() => ({ ...window.__placementProbe, animations: animations.length, frameIdle: animFrameId === null }));
  assert(reducedMotion.sounds === 1 && reducedMotion.animations === 0 && reducedMotion.frameIdle, "reduced-motion placement is not stable");
  assert(errors.length === 0, `browser errors: ${errors.join("; ")}`);
  await mkdir(artifactDir, { recursive: true });
  await page.screenshot({ path: `${artifactDir}/placement-confirmation.png` });
  console.log(JSON.stringify({ ok: true, browser: browser.version(), delays: results.map(({ delay, places, sounds, frames }) => ({ delay, places: places.length, sounds, renderedFrames: frames.length })), fine: true, capture: true, rejection: rejected, remote, reducedMotion: true }, null, 2));
} catch (error) {
  await mkdir(artifactDir, { recursive: true });
  await writeFile(`${artifactDir}/placement-confirmation-failure.json`, JSON.stringify({ browser: browser.version(), results, error: error.message }, null, 2));
  throw error;
} finally {
  await browser.close();
}
