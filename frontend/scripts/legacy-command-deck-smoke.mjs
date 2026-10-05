import { mkdir } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { launchBrowser } from "./smoke-browser.mjs";

const targetUrl = process.argv.find(arg => arg.startsWith("--url="))?.slice(6) || "http://127.0.0.1:8890/";
const artifactDir = fileURLToPath(new URL("../../output/playwright/", import.meta.url));
const browser = await launchBrowser();
const cases = [];
const errors = [];
try {
  const page = await browser.newPage();
  page.on("pageerror", error => errors.push(error.message));
  await page.goto(targetUrl, { waitUntil: "load" });
  const languages = await page.locator("#lang-toggle option").evaluateAll(options => options.map(option => option.value));
  for (const width of [1920, 980, 768, 640, 390, 320]) {
    await page.setViewportSize({ width, height: 900 });
    for (const lang of languages) {
      await page.evaluate(lang => {
        currentLang = lang;
        applyLanguage();
        showHints = true;
        updateWinRate(.625);
      }, lang);
      await page.waitForTimeout(80);
      const state = await page.evaluate(() => {
        const deck = document.getElementById("client-command-deck");
        const bounds = deck.getBoundingClientRect();
        const scale = bounds.width / deck.offsetWidth;
        const children = [...deck.children].filter(element => getComputedStyle(element).display !== "none");
        const title = document.getElementById("client-title");
        const range = document.createRange();
        range.selectNodeContents(title);
        return { width: innerWidth, lang: currentLang, scale, height: bounds.height,
          titleLines: range.getClientRects().length,
          children: children.map(element => {
            const rect = element.getBoundingClientRect();
            return { id: element.id || element.className, left: rect.left, right: rect.right,
              top: rect.top, bottom: rect.bottom, height: rect.height,
              scaleX: rect.width / element.offsetWidth, scaleY: rect.height / element.offsetHeight };
          }), bounds: { left: bounds.left, right: bounds.right, top: bounds.top, bottom: bounds.bottom } };
      });
      if (state.titleLines !== 1 || state.bounds.left < -1 || state.bounds.right > width + 1 ||
          state.children.some(child => child.top < state.bounds.top - 1 || child.bottom > state.bounds.bottom + 1 ||
            child.left < state.bounds.left - 1 || child.right > state.bounds.right + 1 ||
            Math.abs((child.top + child.bottom - state.bounds.top - state.bounds.bottom) / 2) > 2 ||
            Math.abs(child.scaleX - state.scale) > .02 || Math.abs(child.scaleY - state.scale) > .02)) {
        throw new Error(`command deck wrapped, overflowed, or scaled unevenly: ${JSON.stringify(state)}`);
      }
      cases.push({ width, lang, scale: state.scale, height: state.height, titleLines: state.titleLines });
    }
  }
  // The scaled language button remains a real target; its menu is outside the
  // transformed/clipped frame and must stay visible and usable at phone width.
  await page.locator(".client-locale-controls .wood-select-button").click();
  const menu = page.locator(".wood-select-popover.open");
  await menu.waitFor({ state: "visible" });
  await menu.locator('[role="option"]').filter({ hasText: "English" }).click();
  if (await page.locator("#lang-toggle").inputValue() !== "en") throw new Error("scaled language control did not select English");
  if (errors.length) throw new Error(errors.join("; "));
  await mkdir(artifactDir, { recursive: true });
  await page.screenshot({ path: `${artifactDir}/command-deck-${new URL(targetUrl).port}-320.png` });
  await page.setViewportSize({ width: 768, height: 900 });
  await page.waitForTimeout(100);
  await page.screenshot({ path: `${artifactDir}/command-deck-${new URL(targetUrl).port}-768.png` });
  console.log(JSON.stringify({ ok: true, browser: browser.version(), cases, scaledLanguageSelection: true }, null, 2));
} finally { await browser.close(); }
