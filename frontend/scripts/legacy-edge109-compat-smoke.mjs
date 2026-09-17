import { mkdir, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { launchBrowser } from "./smoke-browser.mjs";

const urlArg = process.argv.find(arg => arg.startsWith("--url="));
const targetUrl = urlArg ? urlArg.slice(6) : "http://127.0.0.1:8876/?lang=zh";
const artifactDir = fileURLToPath(new URL("../../output/playwright/", import.meta.url));

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

async function inspectMaskRendering(browser, mode) {
  const page = await browser.newPage({ viewport: { width: 900, height: 600 }, deviceScaleFactor: 1 });
  const errors = [];
  let removedDeclarations = 0;
  page.on("pageerror", error => errors.push(error.message));
  if (mode !== "normal") {
    await page.route("**/static/legacy.css*", async route => {
      const response = await route.fetch();
      const css = await response.text();
      const declaration = mode === "prefix-only"
        ? /^[ \t]*mask-image\s*:[^;]+;[ \t]*\r?\n/gm
        : /^[ \t]*(?:-webkit-)?mask-image\s*:[^;]+;[ \t]*\r?\n/gm;
      const body = css.replace(declaration, () => { removedDeclarations++; return ""; });
      await route.fulfill({ response, body });
    });
  }
  try {
    await page.goto(targetUrl, { waitUntil: "domcontentloaded" });
    await page.waitForFunction(() => typeof playFogFlowEffect === "function" && boardRenderSize > 0);
    const masks = await page.evaluate(() => {
      clearVisualEffects();
      const fixture = document.createElement("div");
      fixture.id = "compat-mask-fixture";
      fixture.style.cssText = "position:fixed;left:20px;top:20px;width:240px;height:240px;z-index:2147483647;background:#102030;";
      const grid = document.createElement("span");
      grid.className = "fx-fog-grid";
      // Keep the production mask, but make its rendered fade easy to compare.
      grid.style.cssText = "animation:none;opacity:1;background:#bdeafe;";
      fixture.appendChild(grid);
      document.body.appendChild(fixture);
      return {
        fog: getComputedStyle(grid).getPropertyValue("-webkit-mask-image"),
        background: getComputedStyle(document.body, "::after").getPropertyValue("-webkit-mask-image"),
        prefixedSupported: CSS.supports("-webkit-mask-image", "radial-gradient(black, transparent)"),
        unprefixedSupported: CSS.supports("mask-image", "radial-gradient(black, transparent)"),
      };
    });
    const screenshot = await page.locator("#compat-mask-fixture").screenshot({
      path: `${artifactDir}edge109-mask-${mode}.png`,
    });
    assert(errors.length === 0, `${mode}: browser errors: ${errors.join("; ")}`);
    return { mode, masks, removedDeclarations, screenshot };
  } finally {
    await page.close();
  }
}

async function inspectBoardFeedback(browser) {
  const page = await browser.newPage({ viewport: { width: 1366, height: 768 }, deviceScaleFactor: 2 });
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  try {
    await page.goto(targetUrl, { waitUntil: "domcontentloaded" });
    await page.waitForFunction(() => boardRenderSize > 0);
    const feedback = await page.evaluate(() => {
      clearVisualEffects();
      showCardEffectVisual("傀儡术发动");
      const particle = document.querySelector(".fx-particle--orbit");
      const animation = particle?.getAnimations()[0];
      if (animation) {
        animation.pause();
        animation.currentTime = 350;
      }
      const particleStyle = particle ? getComputedStyle(particle) : null;
      const center = PAD + 9 * CELL;
      drawHintPercentChip(center, center, 64, 0);
      const radius = Math.floor(CELL * boardRenderDpr * .5);
      const origin = Math.round(center * boardRenderDpr);
      const pixels = ctx.getImageData(origin - radius, origin - radius, radius * 2, radius * 2).data;
      let greenPixels = 0;
      for (let i = 0; i < pixels.length; i += 4) {
        const [r, g, b, a] = pixels.slice(i, i + 4);
        if (g > r + 12 && g > b + 35 && g <= 205 && a === 255) greenPixels++;
      }
      addPlaceAnimation(9, 9);
      return {
        particles: document.querySelectorAll(".fx-particle").length,
        particleWidth: parseFloat(particleStyle?.width || "0"),
        particleTransform: particleStyle?.transform,
        hasAnimation: !!animation,
        greenPixels,
        hasFrame: animFrameId !== null,
        mediaChangeListener: typeof reducedMotionQuery.addEventListener,
      };
    });
    assert(feedback.particles === 12 && feedback.particleWidth > 0 && feedback.hasAnimation &&
      feedback.particleTransform?.startsWith("matrix("), `particle CSS/animation failed: ${JSON.stringify(feedback)}`);
    assert(feedback.greenPixels > 100 && feedback.hasFrame && feedback.mediaChangeListener === "function",
      `Canvas or animation API failed: ${JSON.stringify(feedback)}`);
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.waitForFunction(() => reducedMotionQuery.matches && animFrameId === null);
    const reducedMotion = await page.evaluate(() => ({
      movingElements: document.querySelectorAll(".fx-particle, .fx-stone-impact").length,
      hasBanner: !!document.querySelector(".fx-banner"),
      bannerAnimation: getComputedStyle(document.querySelector(".fx-banner")).animationName,
    }));
    assert(reducedMotion.movingElements === 0 && reducedMotion.hasBanner && reducedMotion.bannerAnimation === "none",
      `reduced-motion change did not take effect: ${JSON.stringify(reducedMotion)}`);
    assert(errors.length === 0, `feedback browser errors: ${errors.join("; ")}`);
    return { feedback, reducedMotion };
  } finally {
    await page.close();
  }
}

const browser = await launchBrowser();
try {
  await mkdir(artifactDir, { recursive: true });
  const normal = await inspectMaskRendering(browser, "normal");
  const fallback = await inspectMaskRendering(browser, "prefix-only");
  const ablated = await inspectMaskRendering(browser, "ablated");
  assert(normal.masks.prefixedSupported, "browser does not support the required prefixed CSS mask");
  assert(fallback.removedDeclarations >= 2, "fallback check did not remove the unprefixed mask declarations");
  for (const key of ["fog", "background"]) {
    assert(normal.masks[key].includes("radial-gradient(") && fallback.masks[key] === normal.masks[key],
      `${key} fade was lost when unprefixed masks were unavailable: ${JSON.stringify({ normal: normal.masks, fallback: fallback.masks })}`);
  }
  assert(normal.screenshot.equals(fallback.screenshot), "prefixed-only mask changed the rendered fog fade");
  assert(ablated.masks.fog === "none" && !normal.screenshot.equals(ablated.screenshot),
    "mask ablation did not change the rendered image; the regression check is ineffective");
  const feedback = await inspectBoardFeedback(browser);
  const report = {
    ok: true,
    browserVersion: browser.version(),
    actual109: browser.version().split(".")[0] === "109",
    masks: { normal: normal.masks, fallback: fallback.masks, ablated: ablated.masks },
    maskScreenshotsEqual: true,
    ablationChangesScreenshot: true,
    ...feedback,
  };
  await writeFile(`${artifactDir}edge109-compat-report.json`, JSON.stringify(report, null, 2));
  console.log(JSON.stringify(report, null, 2));
} finally {
  await browser.close();
}
