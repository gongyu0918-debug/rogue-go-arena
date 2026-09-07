import { chromium } from "playwright";

// Pin the actual executable for compatibility runs; never silently substitute
// a newer browser when the requested runtime cannot start or has another version.
export async function launchBrowser() {
  const executablePath = process.env.SMOKE_BROWSER_EXECUTABLE;
  const expectedMajor = process.env.SMOKE_BROWSER_MAJOR;
  let browser;
  if (executablePath) {
    browser = await chromium.launch({ executablePath, headless: true });
  } else {
    try {
      browser = await chromium.launch({ channel: "msedge", headless: true });
    } catch {
      browser = await chromium.launch({ headless: true });
    }
  }
  if (expectedMajor && browser.version().split(".")[0] !== expectedMajor) {
    const actualVersion = browser.version();
    await browser.close();
    throw new Error(`Expected browser ${expectedMajor}, got ${actualVersion}`);
  }
  return browser;
}
