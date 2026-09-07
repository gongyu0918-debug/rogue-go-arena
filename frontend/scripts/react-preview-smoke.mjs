import { launchBrowser } from "./smoke-browser.mjs";

const DEFAULT_URL = "http://127.0.0.1:8876/react-preview";
const urlArg = process.argv.find((arg) => arg.startsWith("--url="));
const targetUrl = urlArg ? urlArg.slice("--url=".length) : process.env.REACT_PREVIEW_URL || DEFAULT_URL;

const viewports = [
  { name: "desktop", width: 1366, height: 900 },
  { name: "mobile", width: 390, height: 844 }
];

function isCanvasNonblank(canvas) {
  const ctx = canvas.getContext("2d");
  if (!ctx || canvas.width < 10 || canvas.height < 10) {
    return false;
  }
  const data = ctx.getImageData(0, 0, canvas.width, canvas.height).data;
  for (let i = 3; i < data.length; i += 97) {
    if (data[i] !== 0 && (data[i - 1] !== 0 || data[i - 2] !== 0 || data[i - 3] !== 0)) {
      return true;
    }
  }
  return false;
}

const browser = await launchBrowser();
const results = [];

try {
  for (const viewport of viewports) {
    const page = await browser.newPage({ viewport });
    const errors = [];
    page.on("pageerror", (error) => errors.push(error.message));
    page.on("console", (message) => {
      if (message.type() === "error") {
        errors.push(message.text());
      }
    });

    await page.goto(targetUrl, { waitUntil: "networkidle" });
    const title = await page.title();
    const canvas = page.locator("[data-testid=react-board-canvas]");
    await canvas.waitFor({ state: "visible", timeout: 10000 });
    const box = await canvas.boundingBox();
    if (!box) {
      throw new Error(`canvas missing box for ${viewport.name}`);
    }

    const nonblank = await canvas.evaluate(isCanvasNonblank);
    await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
    const last = await page.locator("[data-testid=last-click]").innerText();
    const stones = await page.locator("[data-testid=stone-count]").innerText();
    const serverRevision = await page.locator("[data-testid=server-revision]").innerText();

    results.push({
      viewport: viewport.name,
      title,
      canvas: {
        width: Math.round(box.width),
        height: Math.round(box.height),
        nonblank
      },
      last,
      stones,
      serverRevision,
      errors
    });

    await page.close();
  }
} finally {
  await browser.close();
}

for (const result of results) {
  if (!result.canvas.nonblank) {
    throw new Error(`${result.viewport} canvas is blank`);
  }
  if (result.last === "none") {
    throw new Error(`${result.viewport} click did not register`);
  }
  if (result.serverRevision === "pending") {
    throw new Error(`${result.viewport} server status did not load`);
  }
  if (result.errors.length > 0) {
    throw new Error(`${result.viewport} browser errors: ${result.errors.join("; ")}`);
  }
}

console.log(JSON.stringify(results, null, 2));
