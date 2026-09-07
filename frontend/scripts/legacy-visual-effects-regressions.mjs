import { mkdir } from "node:fs/promises";
import { fileURLToPath } from "node:url";

const artifactDir = fileURLToPath(new URL("../../output/playwright/", import.meta.url));

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

async function verifyCoordinates(page) {
  return page.evaluate(() => {
    clearVisualEffects();
    const layer = document.getElementById("board-fx-layer");
    const boardRect = canvas.getBoundingClientRect();
    const layerRect = layer.getBoundingClientRect();
    const expected = (x, y) => ({
      x: boardRect.left + (PAD + x * CELL) * boardRect.width / boardRenderSize,
      y: boardRect.top + (PAD + y * CELL) * boardRect.height / boardRenderSize,
    });
    const errorAt = (node, x, y) => {
      const target = expected(x, y);
      return Math.hypot(layerRect.left + parseFloat(node.style.left) - target.x,
        layerRect.top + parseFloat(node.style.top) - target.y);
    };
    playFogFlowEffect([[3, 3]]);
    playSanrenseiConstellation(true);
    addPlaceAnimation(5, 6);
    playFiveInRowBurst();
    const star = getStarPoints(getCurrentSize())[0];
    const link = layer.querySelector(".fx-star-link");
    const diagonal = layer.querySelectorAll(".fx-five-line")[1];
    // Sample the actual animated transform, not just the requested style property.
    for (const node of [link, diagonal]) {
      for (const animation of node.getAnimations()) {
        animation.pause();
        animation.currentTime = 400;
      }
    }
    const angle = node => {
      const matrix = new DOMMatrix(getComputedStyle(node).transform);
      return Math.atan2(matrix.b, matrix.a);
    };
    const expectedAngle = parseFloat(link.style.getPropertyValue("--link-angle"));
    return {
      fogError: errorAt(layer.querySelector(".fx-fog-cloud"), 3, 3),
      starError: errorAt(layer.querySelector(".fx-star-pulse"), ...star),
      impactError: errorAt(layer.querySelector(".fx-place-impact"), 5, 6),
      linkAngleError: Math.abs(angle(link) - expectedAngle),
      diagonalAngleError: Math.abs(angle(diagonal) - Math.PI / 4),
      deviceScale: boardRenderDpr,
    };
  });
}

async function playCaptureThroughBoard(page) {
  await page.locator("#btn-setup").click();
  await page.locator("#mode-two").click();
  await page.locator("#btn-new").click();
  await page.waitForFunction(() => gameState?.board && twoPlayerMode && isMyTurn);
  await page.locator("#setup-modal").waitFor({ state: "hidden" });
  await page.evaluate(() => {
    soundEnabled = false;
    window.__capturedInFxSmoke = [];
    const originalCapture = addCaptureAnimation;
    addCaptureAnimation = window.addCaptureAnimation = stones => {
      window.__capturedInFxSmoke.push(...stones);
      originalCapture(stones);
    };
  });
  const moves = [[8, 9], [9, 9], [9, 8], [3, 3], [10, 9], [15, 15], [9, 10]];
  for (const [index, [x, y]] of moves.entries()) {
    await page.waitForFunction(() => Date.now() - lastPlayTime >= 420);
    if (index === moves.length - 1) await page.evaluate(() => showCardEffectVisual("连击加速"));
    const point = await page.evaluate(([x, y]) => {
      const rect = canvas.getBoundingClientRect();
      const px = rect.left + (PAD + x * CELL) * rect.width / boardRenderSize;
      const py = rect.top + (PAD + y * CELL) * rect.height / boardRenderSize;
      return { x: px, y: py, target: document.elementFromPoint(px, py)?.id };
    }, [x, y]);
    assert(point.target === "board-canvas", `effect blocked a board click: ${JSON.stringify(point)}`);
    await page.mouse.click(point.x, point.y);
    await page.waitForFunction(count => gameState?.moves_list?.length === count, index + 1);
  }
  const captured = await page.evaluate(() => ({
    stones: window.__capturedInFxSmoke,
    intersection: gameState.board[9][9],
  }));
  assert(captured.intersection === 0 && captured.stones.some(([x, y, color]) => x === 9 && y === 9 && color === "W"),
    `real capture did not reach the visual path: ${JSON.stringify(captured)}`);
  return moves.length;
}

async function captureRepresentativeFrame(page, message, name) {
  await page.evaluate(message => {
    clearVisualEffects();
    showCardEffectVisual(message);
    addPlaceAnimation(9, 10);
    addCaptureAnimation([[9, 9, "W"]]);
    // Sample the Canvas and CSS at the same point in the short animation.
    cancelAnimationFrame(animFrameId);
    animFrameId = null;
    animations.forEach(animation => { animation.startTime = performance.now() - 250; });
    render();
    animations = [];
    for (const animation of document.getElementById("board-fx-layer").getAnimations({ subtree: true })) {
      animation.pause();
      animation.currentTime = 250;
    }
  }, message);
  await page.screenshot({ path: `${artifactDir}${name}.png` });
}

export async function verifyVisualEffectRegressions(browser, targetUrl) {
  const page = await browser.newPage({ viewport: { width: 1366, height: 768 }, deviceScaleFactor: 2, reducedMotion: "no-preference" });
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  try {
    await mkdir(artifactDir, { recursive: true });
    await page.goto(targetUrl, { waitUntil: "domcontentloaded" });
    await page.waitForFunction(() => boardRenderSize > 0 && ws?.readyState === WebSocket.OPEN);
    const coordinateCases = [];
    for (const viewport of [{ width: 1366, height: 768 }, { width: 390, height: 844 }]) {
      await page.setViewportSize(viewport);
      await page.waitForFunction(() => boardLooksReady());
      const geometry = await verifyCoordinates(page);
      for (const key of ["fogError", "starError", "impactError"]) {
        assert(geometry[key] < 1, `misaligned ${key} at ${viewport.width}px: ${JSON.stringify(geometry)}`);
      }
      assert(geometry.linkAngleError < .01 && geometry.diagonalAngleError < .01,
        `signature effect lost its direction: ${JSON.stringify(geometry)}`);
      coordinateCases.push({ width: viewport.width, ...geometry });
    }

    await page.setViewportSize({ width: 1366, height: 768 });
    const actualMoves = await playCaptureThroughBoard(page);
    await captureRepresentativeFrame(page, "傀儡术发动", "visual-effects-orbit");
    await captureRepresentativeFrame(page, "封印术成型", "visual-effects-ward");
    const motions = await page.evaluate(() => {
      const result = {};
      for (const message of ["傀儡术", "连击", "封印", "迷雾"]) {
        showCardEffectVisual(message);
        result[message] = document.querySelector(".fx-card-burst")?.dataset.motion;
      }
      return result;
    });
    assert(new Set(Object.values(motions)).size === 4, `card mechanics share the same motion: ${JSON.stringify(motions)}`);

    const budget = await page.evaluate(() => {
      clearVisualEffects();
      for (let i = 0; i < 100; i++) {
        addPlaceAnimation(i % 19, Math.floor(i / 19));
        playGodHandFlash();
      }
      addCaptureAnimation(Array.from({ length: 80 }, (_, i) => [i % 19, Math.floor(i / 19), "W"]));
      showCardEffectVisual("连击");
      return {
        animations: animations.length,
        layerElements: document.getElementById("board-fx-layer").children.length,
        flashes: document.querySelectorAll(".fx-godflash").length,
        particles: document.querySelectorAll(".fx-particle").length,
        timers: fxCleanupTimers.size,
      };
    });
    assert(budget.animations <= 32 && budget.layerElements <= 48 && budget.flashes === 1 && budget.particles === 12 && budget.timers <= 50,
      `effect storm exceeded its budget: ${JSON.stringify(budget)}`);
    await page.waitForFunction(() => fxCleanupTimers.size === 0 && animations.length === 0 && animFrameId === null, null, { timeout: 3500 });
    assert(await page.locator("#board-fx-layer > *, #global-fx-layer > *").count() === 0, "expired effects left DOM behind");

    await page.evaluate(() => { showCardEffectVisual("连击"); addPlaceAnimation(9, 10); });
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.waitForFunction(() => reducedMotionQuery.matches && animations.length === 0 && animFrameId === null);
    const reduced = await page.evaluate(() => {
      addPlaceAnimation(9, 10);
      addCaptureAnimation([[9, 9, "W"]]);
      spawnOverlaySparks("victory");
      triggerSignatureCardEffect("神之一手 Five in a Row 战争迷雾刷新 三连星发动 起死回生");
      triggerBoardIntro();
      showCardEffectVisual("傀儡术发动");
      document.getElementById("btn-setup").dispatchEvent(new PointerEvent("pointerdown", { bubbles: true }));
      return {
        children: document.getElementById("board-fx-layer").children.length,
        title: document.querySelector(".fx-banner-title")?.textContent,
        animation: getComputedStyle(document.querySelector(".fx-banner")).animationName,
        extras: document.querySelectorAll(".fx-card-burst, .fx-stone-impact, .fx-godflash, .overlay-spark, .btn-ripple").length,
        hasLoop: animFrameId !== null,
        intro: document.getElementById("board-container").classList.contains("board-intro"),
      };
    });
    assert(reduced.children === 1 && reduced.title?.includes("傀儡") && reduced.animation === "none" &&
      reduced.extras === 0 && !reduced.hasLoop && !reduced.intro, `reduced motion did not remain static: ${JSON.stringify(reduced)}`);
    await page.screenshot({ path: `${artifactDir}visual-effects-reduced-motion.png` });

    await page.emulateMedia({ reducedMotion: "no-preference" });
    await page.evaluate(() => { showCardEffectVisual("连击"); addPlaceAnimation(9, 10); });
    assert(await page.locator(".fx-particle").count() === 12, "motion preference could not be restored");
    const cleanup = await page.evaluate(() => {
      window.dispatchEvent(new PageTransitionEvent("pagehide"));
      return { timers: fxCleanupTimers.size, animations: animations.length, frame: animFrameId,
        elements: document.querySelectorAll("#board-fx-layer > *, #global-fx-layer > *").length };
    });
    assert(cleanup.timers === 0 && cleanup.animations === 0 && cleanup.frame === null && cleanup.elements === 0,
      `page lifecycle left effects active: ${JSON.stringify(cleanup)}`);
    assert(errors.length === 0, `effect regression browser errors: ${errors.join("; ")}`);
    return { actualMoves, coordinateCases, motions, budget, reduced, cleanup, screenshots: artifactDir };
  } finally {
    await page.close();
  }
}
