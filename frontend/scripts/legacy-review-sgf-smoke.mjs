import fs from "node:fs/promises";
import { chromium } from "playwright";

const DEFAULT_URL = "http://127.0.0.1:8876/";
const urlArg = process.argv.find((arg) => arg.startsWith("--url="));
const targetUrl = urlArg ? urlArg.slice("--url=".length) : process.env.LEGACY_REVIEW_SGF_URL || DEFAULT_URL;

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
const context = await browser.newContext({
  acceptDownloads: true,
  viewport: { width: 1366, height: 768 },
  deviceScaleFactor: 1,
});
const page = await context.newPage();
const errors = [];

page.on("pageerror", (error) => errors.push(error.message));
page.on("console", (message) => {
  if (message.type() === "error") errors.push(message.text());
});

try {
  await page.goto(targetUrl, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(700);
  await page.locator("#board-canvas").waitFor({ state: "visible", timeout: 10000 });

  const parsed = await page.evaluate(() => {
    const parsedSgf = parseSgf("(;GM[1]FF[4]SZ[9]KM[6.5];B[dd];W[];B[ee])");
    return {
      size: parsedSgf.size,
      komi: parsedSgf.komi,
      moves: parsedSgf.moves,
      publicFns: [
        typeof window.parseSgf,
        typeof window.loadSgfFile,
        typeof window.exportSgf,
        typeof window.enterReviewMode,
        typeof window.reviewGo,
        typeof window.exitReviewMode,
      ],
    };
  });

  assert(parsed.size === 9, `unexpected parsed board size: ${parsed.size}`);
  assert(parsed.komi === 6.5, `unexpected parsed komi: ${parsed.komi}`);
  assert(parsed.moves.length === 3, `unexpected parsed move count: ${parsed.moves.length}`);
  assert(parsed.moves[0].gtp === "D6", `unexpected first GTP move: ${parsed.moves[0].gtp}`);
  assert(parsed.moves[1].gtp === "pass", `unexpected pass move: ${parsed.moves[1].gtp}`);
  assert(
    parsed.publicFns.every((type) => type === "function"),
    `review/SGF public functions missing: ${parsed.publicFns.join(", ")}`
  );

  await page.locator("#btn-settings").click();
  await page.locator("#settings-drawer.open").waitFor({ state: "visible", timeout: 5000 });

  const fileChooserPromise = page.waitForEvent("filechooser");
  await page.locator("#btn-sgf-load").click();
  const fileChooser = await fileChooserPromise;
  await fileChooser.setFiles({
    name: "review-smoke.sgf",
    mimeType: "application/x-go-sgf",
    buffer: Buffer.from("(;GM[1]FF[4]SZ[9]KM[6.5];B[dd];W[];B[ee])", "utf8"),
  });
  await page.waitForFunction(() => reviewMode && reviewMoves.length === 3 && reviewIndex === 2);

  const loaded = await page.evaluate(() => ({
    reviewMode,
    sgfLoadedMode,
    reviewIndex,
    reviewBoardSize,
    reviewKomi,
    reviewInfo: document.querySelector("#review-info")?.textContent || "",
    canvasNonblank: (() => {
      const canvas = document.querySelector("#board-canvas");
      const ctx = canvas?.getContext("2d");
      if (!ctx || canvas.width < 10 || canvas.height < 10) return false;
      const data = ctx.getImageData(0, 0, canvas.width, canvas.height).data;
      for (let i = 3; i < data.length; i += 101) {
        if (data[i] !== 0 && (data[i - 1] !== 0 || data[i - 2] !== 0 || data[i - 3] !== 0)) {
          return true;
        }
      }
      return false;
    })(),
  }));

  assert(loaded.reviewMode, "SGF load did not enter review mode");
  assert(loaded.sgfLoadedMode, "SGF load did not mark sgfLoadedMode");
  assert(loaded.reviewBoardSize === 9, `unexpected review board size: ${loaded.reviewBoardSize}`);
  assert(loaded.reviewKomi === 6.5, `unexpected review komi: ${loaded.reviewKomi}`);
  assert(loaded.reviewInfo.includes("3/3"), `unexpected review info after load: ${loaded.reviewInfo}`);
  assert(loaded.canvasNonblank, "board canvas is blank after SGF load");

  await page.keyboard.press("ArrowLeft");
  await page.waitForFunction(() => reviewIndex === 1);
  await page.keyboard.press("Home");
  await page.waitForFunction(() => reviewIndex === -1);
  await page.keyboard.press("End");
  await page.waitForFunction(() => reviewIndex === 2);

  const downloadPromise = page.waitForEvent("download");
  await page.locator("#btn-sgf-save").click();
  const download = await downloadPromise;
  const downloadPath = await download.path();
  const sgfText = await fs.readFile(downloadPath, "utf8");

  assert(download.suggestedFilename().endsWith(".sgf"), `unexpected download filename: ${download.suggestedFilename()}`);
  assert(sgfText.includes("SZ[9]KM[6.5]"), "exported SGF lost size or komi");
  assert(sgfText.includes(";B[dd]"), "exported SGF missing black move");
  assert(sgfText.includes(";W[]"), "exported SGF missing pass move");
  assert(sgfText.includes(";B[ee]"), "exported SGF missing final black move");

  await page.keyboard.press("Escape");
  await page.waitForFunction(() => !reviewMode);

  assert(errors.length === 0, `browser errors: ${errors.join("; ")}`);
  console.log(JSON.stringify({ ok: true, moves: parsed.moves.length, exportedBytes: sgfText.length }, null, 2));
} finally {
  await context.close();
  await browser.close();
}
