import { chromium } from "playwright";

const DEFAULT_URL = "http://127.0.0.1:8876/";
const urlArg = process.argv.find((arg) => arg.startsWith("--url="));
const simulatePywebviewClose = process.argv.includes("--simulate-pywebview-close");
const targetUrl = withLanguageParam(
  urlArg ? urlArg.slice("--url=".length) : process.env.LEGACY_DESKTOP_EXIT_CLICK_URL || DEFAULT_URL,
  "zh"
);

function withLanguageParam(rawUrl, lang) {
  const url = new URL(rawUrl);
  url.searchParams.set("lang", lang);
  return url.toString();
}

async function launchBrowser() {
  try {
    return await chromium.launch({ channel: "msedge", headless: true });
  } catch {
    return chromium.launch({ headless: true });
  }
}

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

const browser = await launchBrowser();
const page = await browser.newPage({ viewport: { width: 1366, height: 768 }, deviceScaleFactor: 1 });
const errors = [];

if (simulatePywebviewClose) {
  await page.addInitScript(() => {
    window.__hostCloseCalls = 0;
    window.pywebview = {
      api: {
        close_window() {
          window.__hostCloseCalls += 1;
          return Promise.resolve({ ok: true, action: "window_destroy" });
        },
      },
    };
  });
}

page.on("pageerror", (error) => errors.push(error.message));
page.on("console", (message) => {
  if (message.type() === "error") errors.push(message.text());
});

try {
  await page.goto(targetUrl, { waitUntil: "domcontentloaded" });
  await page.locator("#board-canvas").waitFor({ state: "visible", timeout: 10000 });
  await page.locator("#desktop-exit-button").waitFor({ state: "visible", timeout: 10000 });
  await page.waitForFunction(() => {
    const button = document.querySelector("#desktop-exit-button");
    return !!button && button.disabled && button.title.length > 0;
  }, null, { timeout: 10000 });

  const exitButton = page.locator("#desktop-exit-button");
  const board = page.locator("#board-canvas");
  const topDeck = page.locator("#client-command-deck");
  const initialDisabled = await exitButton.isDisabled();
  const initialTitle = await exitButton.getAttribute("title");
  const exitBox = await exitButton.boundingBox();
  const boardBox = await board.boundingBox();
  const topDeckBox = await topDeck.boundingBox();

  assert(initialDisabled, "desktop exit button should be disabled before game/model starts");
  assert(initialTitle && initialTitle.length > 0, "desktop exit disabled title should be present");
  assert(exitBox && boardBox && topDeckBox, "layout boxes missing for exit button, board, or top deck");
  assert(exitBox.y < boardBox.y, `desktop exit button overlaps board vertically: ${JSON.stringify({ exitBox, boardBox })}`);
  assert(exitBox.x + exitBox.width <= topDeckBox.x + topDeckBox.width + 1, `desktop exit button overflows top deck: ${JSON.stringify({ exitBox, topDeckBox })}`);

  await page.locator("#btn-setup").click();
  await page.locator("#setup-modal.show").waitFor({ state: "visible", timeout: 10000 });
  await page.locator("#mode-two").click();
  await page.locator("#btn-new").click();
  await page.waitForFunction(() => typeof gameState !== "undefined" && !!gameState, null, { timeout: 15000 });
  await page.waitForFunction(() => {
    const button = document.querySelector("#desktop-exit-button");
    return !!button && !button.disabled;
  }, null, { timeout: 10000 });

  const afterStartDisabled = await exitButton.isDisabled();
  const afterStartTitle = await exitButton.getAttribute("title");
  assert(!afterStartDisabled, "desktop exit button should enable after two-player game starts");
  assert(afterStartTitle && afterStartTitle.includes("停止AI"), `unexpected enabled title: ${afterStartTitle}`);

  await exitButton.click();
  await page.locator("#confirm-modal.show").waitFor({ state: "visible", timeout: 5000 });
  const confirmText = await page.locator("#confirm-msg").textContent();
  assert(confirmText && confirmText.includes("释放AI资源"), `desktop exit confirm text changed: ${confirmText}`);
  await page.locator("#btn-confirm-ok").click();

  await page.waitForFunction(() => {
    const text = document.querySelector("#status-text")?.textContent || "";
    return window.location.href === "about:blank" || text.includes("退出");
  }, null, { timeout: 8000 });
  if (simulatePywebviewClose) {
    await page.waitForFunction(() => window.__hostCloseCalls === 1, null, { timeout: 5000 });
  }

  const finalUrl = page.url();
  const statusText = await page.evaluate(() => document.querySelector("#status-text")?.textContent || "").catch(() => "");

  assert(errors.length === 0, `browser errors: ${errors.join("; ")}`);
  const hostCloseCalls = await page.evaluate(() => window.__hostCloseCalls || 0).catch(() => 0);
  if (simulatePywebviewClose) {
    assert(hostCloseCalls === 1, `expected one pywebview host close call, got ${hostCloseCalls}`);
  }
  console.log(JSON.stringify({
    ok: true,
    initialDisabled,
    afterStartDisabled,
    finalUrl,
    statusText,
    hostCloseCalls,
  }, null, 2));
} finally {
  await browser.close();
}
