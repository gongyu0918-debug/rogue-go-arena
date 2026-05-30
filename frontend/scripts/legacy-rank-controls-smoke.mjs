import { chromium } from "playwright";

const DEFAULT_URL = "http://127.0.0.1:8876/";
const urlArg = process.argv.find((arg) => arg.startsWith("--url="));
const targetUrl = withLanguageParam(
  urlArg ? urlArg.slice("--url=".length) : process.env.LEGACY_RANK_CONTROLS_URL || DEFAULT_URL,
  "zh"
);

async function launchBrowser() {
  try {
    return await chromium.launch({ channel: "msedge", headless: true });
  } catch {
    return chromium.launch({ headless: true });
  }
}

function withLanguageParam(rawUrl, lang) {
  const url = new URL(rawUrl);
  url.searchParams.set("lang", lang);
  return url.toString();
}

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

const browser = await launchBrowser();
const page = await browser.newPage({ viewport: { width: 1366, height: 768 }, deviceScaleFactor: 1 });
const errors = [];

page.on("pageerror", (error) => errors.push(error.message));
page.on("console", (message) => {
  if (message.type() === "error") errors.push(message.text());
});

await page.route("**/gpu", async route => {
  await route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({ default_rank: "5k", slow_from: "a1d" }),
  });
});

try {
  await page.goto(targetUrl, { waitUntil: "domcontentloaded" });
  await page.waitForFunction(() => ws && ws.readyState === WebSocket.OPEN, null, { timeout: 10000 });
  await page.waitForFunction(() => document.querySelector("#sel-level")?.value === "5k", null, { timeout: 10000 });
  await page.locator("#board-canvas").waitFor({ state: "visible", timeout: 10000 });

  const initialState = await page.evaluate(() => {
    const selectors = ["sel-level", "sel-level-black", "sel-level-white"];
    const selectStates = selectors.map(id => {
      const select = document.getElementById(id);
      const options = Array.from(select?.options || []);
      return {
        id,
        value: select?.value || "",
        optionCount: options.length,
        disabledCount: options.filter(option => option.disabled).length,
        slowA1d: select?.querySelector('option[value="a1d"]')?.textContent || "",
        slowP9d: select?.querySelector('option[value="p9d"]')?.textContent || "",
        fast1k: select?.querySelector('option[value="1k"]')?.textContent || "",
        slowMarkedA1d: select?.querySelector('option[value="a1d"]')?.dataset.slowMarked || "",
        slowMarked1k: select?.querySelector('option[value="1k"]')?.dataset.slowMarked || "",
        woodValue: document.querySelector(`#${id} + .wood-select-button .wood-select-value`)?.textContent?.trim() || "",
      };
    });
    const customSelect = document.createElement("select");
    populateRankSelect(customSelect, "p3d");
    const customOptions = Array.from(customSelect.options);
    return {
      publicFns: [
        typeof window.initializeRankControls,
        typeof window.refreshRankSelectLabels,
        typeof window.applySlowRankWarnings,
        typeof window.populateRankSelect,
      ],
      selectStates,
      customSelect: {
        value: customSelect.value,
        optionCount: customOptions.length,
        disabledCount: customOptions.filter(option => option.disabled).length,
        selectedP3d: customSelect.querySelector('option[value="p3d"]')?.selected || false,
        selectedText: customSelect.querySelector('option[value="p3d"]')?.textContent || "",
      },
    };
  });

  assert(initialState.publicFns.every(type => type === "function"), `rank control globals missing: ${initialState.publicFns.join(", ")}`);
  assert(initialState.customSelect.value === "p3d", `custom default rank did not select p3d: ${JSON.stringify(initialState.customSelect)}`);
  assert(initialState.customSelect.optionCount === 39, `custom rank option count changed: ${initialState.customSelect.optionCount}`);
  assert(initialState.customSelect.disabledCount === 3, `custom rank separator count changed: ${initialState.customSelect.disabledCount}`);
  assert(initialState.customSelect.selectedP3d, `custom p3d option was not selected: ${JSON.stringify(initialState.customSelect)}`);
  assert(initialState.customSelect.selectedText.length > 0, "custom selected rank text missing");
  initialState.selectStates.forEach(state => {
    assert(state.value === "5k", `${state.id}: GPU default rank did not apply: ${state.value}`);
    assert(state.optionCount === 39, `${state.id}: rank option count changed: ${state.optionCount}`);
    assert(state.disabledCount === 3, `${state.id}: rank separator count changed: ${state.disabledCount}`);
    assert(state.slowMarkedA1d === "1", `${state.id}: a1d was not slow-marked`);
    assert(state.slowA1d.includes("⚠") && state.slowA1d.includes("推理较慢"), `${state.id}: slow a1d label changed: ${state.slowA1d}`);
    assert(state.slowP9d.includes("⚠") && state.slowP9d.includes("推理较慢"), `${state.id}: slow p9d label changed: ${state.slowP9d}`);
    assert(!state.fast1k.includes("⚠"), `${state.id}: 1k should not be slow-marked: ${state.fast1k}`);
    assert(state.slowMarked1k === "", `${state.id}: 1k got slow marker`);
    assert(state.woodValue.includes("5级"), `${state.id}: wood select did not sync selected rank: ${state.woodValue}`);
  });

  await page.evaluate(async () => {
    await setLanguage("en");
  });

  const englishState = await page.evaluate(() => {
    const select = document.getElementById("sel-level");
    return {
      htmlLang: document.documentElement.lang,
      currentLang,
      value: select?.value || "",
      slowA1d: select?.querySelector('option[value="a1d"]')?.textContent || "",
      fast5k: select?.querySelector('option[value="5k"]')?.textContent || "",
      slowMarkedA1d: select?.querySelector('option[value="a1d"]')?.dataset.slowMarked || "",
      woodValue: document.querySelector("#sel-level + .wood-select-button .wood-select-value")?.textContent?.trim() || "",
    };
  });

  assert(englishState.htmlLang === "en", `language did not switch to English: ${englishState.htmlLang}`);
  assert(englishState.currentLang === "en", `currentLang did not switch: ${englishState.currentLang}`);
  assert(englishState.value === "5k", `rank selection was not preserved after localization: ${englishState.value}`);
  assert(englishState.slowMarkedA1d === "1", "slow marker was not preserved after localization");
  assert(
    englishState.slowA1d.includes("⚠") && englishState.slowA1d.includes("Amateur 1 dan") && englishState.slowA1d.includes("(slower)"),
    `English slow label changed: ${englishState.slowA1d}`
  );
  assert(englishState.fast5k === "5 kyu", `English 5k label changed: ${englishState.fast5k}`);
  assert(englishState.woodValue === "5 kyu", `English wood select value did not sync: ${englishState.woodValue}`);

  assert(errors.length === 0, `browser errors: ${errors.join("; ")}`);
  console.log(JSON.stringify({
    ok: true,
    rank: englishState.value,
    slowLabel: englishState.slowA1d,
  }, null, 2));
} finally {
  await browser.close();
}
