import { chromium } from "playwright";

const DEFAULT_URL = "http://127.0.0.1:8876/";
const urlArg = process.argv.find((arg) => arg.startsWith("--url="));
const targetUrl = withLanguageParam(
  urlArg ? urlArg.slice("--url=".length) : process.env.LEGACY_LOCALIZATION_URL || DEFAULT_URL,
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

async function chooseWoodOption(page, selectId, optionText) {
  await page.locator(`#${selectId} + .wood-select-button`).click();
  const option = page.locator(".wood-select-popover.open .wood-select-option", { hasText: optionText });
  await option.waitFor({ state: "visible", timeout: 5000 });
  await option.click();
}

async function assertLanguageState(page, expected) {
  await page.waitForFunction((lang) => document.documentElement.lang === lang.htmlLang, expected);
  const state = await page.evaluate(() => ({
    htmlLang: document.documentElement.lang,
    currentLang,
    topValue: document.querySelector("#lang-toggle")?.value || "",
    settingsValue: document.querySelector("#settings-language-select")?.value || "",
    topButtonText: document.querySelector("#lang-toggle + .wood-select-button .wood-select-value")?.textContent?.trim() || "",
    settingsButtonText: document.querySelector("#settings-language-select + .wood-select-button .wood-select-value")?.textContent?.trim() || "",
    storedLang: localStorage.getItem("rogue_go_arena_lang"),
    title: document.title,
    setupButton: document.querySelector("#btn-new")?.textContent?.trim() || "",
    settingsLanguageLabel: document.querySelector("#settings-language-label")?.textContent?.trim() || "",
    headerTitle: document.querySelector("#header-main h1")?.textContent?.trim() || "",
    publicFns: [
      typeof window.applyLanguage,
      typeof window.ensureLanguageControl,
      typeof window.rebuildCurveLegend,
    ],
    staleLanguagePanel: !!document.querySelector("#lang-panel, #lang-select"),
  }));

  assert(state.htmlLang === expected.htmlLang, `unexpected html lang: ${state.htmlLang}`);
  assert(state.currentLang === expected.value, `unexpected currentLang: ${state.currentLang}`);
  assert(state.topValue === expected.value, `top language select did not sync: ${state.topValue}`);
  assert(state.settingsValue === expected.value, `settings language select did not sync: ${state.settingsValue}`);
  assert(state.topButtonText === expected.buttonText, `top language button did not sync: ${state.topButtonText}`);
  assert(
    state.settingsButtonText === expected.buttonText,
    `settings language button did not sync: ${state.settingsButtonText}`
  );
  const expectedStoredLang = Object.prototype.hasOwnProperty.call(expected, "storedLang")
    ? expected.storedLang
    : expected.value;
  assert(state.storedLang === expectedStoredLang, `stored language did not sync: ${state.storedLang}`);
  assert(state.title === "rogue-go-arena", `document title changed unexpectedly: ${state.title}`);
  assert(state.setupButton === expected.setupButton, `unexpected setup button text: ${state.setupButton}`);
  assert(state.settingsLanguageLabel === expected.settingsLabel, `unexpected settings label: ${state.settingsLanguageLabel}`);
  assert(state.headerTitle === expected.headerTitle, `unexpected header title: ${state.headerTitle}`);
  assert(state.publicFns.every((type) => type === "function"), `localization globals missing: ${state.publicFns.join(", ")}`);
  assert(!state.staleLanguagePanel, "stale language panel was not removed");
}

const browser = await launchBrowser();
const page = await browser.newPage({ viewport: { width: 1366, height: 768 }, deviceScaleFactor: 1 });
const errors = [];

page.on("pageerror", (error) => errors.push(error.message));
page.on("console", (message) => {
  if (message.type() === "error") errors.push(message.text());
});

try {
  await page.goto(targetUrl, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(700);
  await page.locator("#board-canvas").waitFor({ state: "visible", timeout: 10000 });

  await assertLanguageState(page, {
    value: "zh",
    htmlLang: "zh-CN",
    storedLang: null,
    buttonText: "中文",
    setupButton: "确认开始",
    settingsLabel: "语言",
    headerTitle: "围棋对弈场",
  });

  await chooseWoodOption(page, "lang-toggle", "English");
  await assertLanguageState(page, {
    value: "en",
    htmlLang: "en",
    buttonText: "English",
    setupButton: "Start",
    settingsLabel: "Language",
    headerTitle: "Rogue Go Arena",
  });

  await page.locator("#btn-settings").click();
  await page.locator("#settings-drawer.open").waitFor({ state: "visible", timeout: 5000 });
  await chooseWoodOption(page, "settings-language-select", "Korean");
  await assertLanguageState(page, {
    value: "ko",
    htmlLang: "ko",
    buttonText: "한국어",
    setupButton: "시작",
    settingsLabel: "언어",
    headerTitle: "바둑 대국장",
  });

  await chooseWoodOption(page, "settings-language-select", "일본어");
  await assertLanguageState(page, {
    value: "ja",
    htmlLang: "ja",
    buttonText: "日本語",
    setupButton: "開始する",
    settingsLabel: "言語",
    headerTitle: "囲碁対局場",
  });

  await chooseWoodOption(page, "settings-language-select", "中国語");
  await assertLanguageState(page, {
    value: "zh",
    htmlLang: "zh-CN",
    buttonText: "中文",
    setupButton: "确认开始",
    settingsLabel: "语言",
    headerTitle: "围棋对弈场",
  });

  assert(errors.length === 0, `browser errors: ${errors.join("; ")}`);
  console.log(JSON.stringify({ ok: true, checkedLanguages: ["zh", "en", "ko", "ja", "zh"] }, null, 2));
} finally {
  await browser.close();
}
