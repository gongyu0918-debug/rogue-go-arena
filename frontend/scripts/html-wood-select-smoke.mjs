import { launchBrowser } from "./smoke-browser.mjs";
import { runWoodSelectRegressions } from "./legacy-wood-select-regressions.mjs";

const targetUrl = process.argv.find(arg => arg.startsWith("--url="))?.slice(6) || "http://127.0.0.1:8891/";
const browser = await launchBrowser();
try {
  console.log(`HTML dropdown smoke using browser ${browser.version()}`);
  await runWoodSelectRegressions(browser, targetUrl);
} finally {
  await browser.close();
}
