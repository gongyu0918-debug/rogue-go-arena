import { chromium } from "playwright";

const DEFAULT_URL = "http://127.0.0.1:8876/";
const urlArg = process.argv.find((arg) => arg.startsWith("--url="));
const targetUrl = urlArg ? urlArg.slice("--url=".length) : process.env.LEGACY_RESPONSIVE_URL || DEFAULT_URL;

const viewports = [
  { name: "tight-desktop", width: 1280, height: 720 },
  { name: "short-desktop", width: 1280, height: 480, allowVerticalScroll: true },
  { name: "laptop", width: 1366, height: 768 },
  { name: "desktop", width: 1920, height: 1080 },
  { name: "qhd", width: 2560, height: 1440 },
  { name: "tablet", width: 768, height: 1024 },
  { name: "mobile", width: 390, height: 844 },
];

const boardSizes = [9, 13, 19];

async function launchBrowser() {
  try {
    return await chromium.launch({ channel: "msedge", headless: true });
  } catch {
    return chromium.launch({ headless: true });
  }
}

function assertLayoutState(state) {
  const failures = [];
  const minBoard = state.viewport.width <= 640 ? 260 : 340;

  if (!state.board.nonblank) failures.push("board canvas is blank");
  if (state.board.width < minBoard || state.board.height < minBoard) {
    failures.push(`board too small: ${state.board.width}x${state.board.height}`);
  }
  if (state.board.x < 0 || state.board.right > state.viewport.width) {
    failures.push("board exceeds viewport horizontally");
  }
  if (state.board.y < state.deck.bottom + 6) {
    failures.push("board overlaps top command deck");
  }
  if (state.toolbar.y < state.board.bottom + 4) {
    failures.push("toolbar overlaps board canvas");
  }
  if (state.toolbar.x < 0 || state.toolbar.right > state.viewport.width) {
    failures.push("toolbar exceeds viewport horizontally");
  }
  if (!state.viewport.allowVerticalScroll && state.toolbar.bottom > state.viewport.height + 1) {
    failures.push("toolbar exceeds viewport height");
  }
  if (state.pageScrollWidth > state.viewport.width + 2) {
    failures.push(`page has horizontal overflow: ${state.pageScrollWidth}px`);
  }
  if (!state.wiki.visible) failures.push("wiki modal did not open");
  if (state.wiki.modal.right > state.viewport.width + 2 || state.wiki.modal.x < -2) {
    failures.push("wiki modal exceeds viewport width");
  }
  if (!state.viewport.allowVerticalScroll && (state.wiki.modal.bottom > state.viewport.height + 2 || state.wiki.modal.y < -2)) {
    failures.push("wiki modal exceeds viewport height");
  }
  if (state.wiki.scrollWidth > state.wiki.clientWidth + 2) {
    failures.push("wiki content has horizontal overflow");
  }
  if (!state.wiki.cardBackground.includes("ui-dark-wood")) {
    failures.push("wiki cards are not using the shared wood texture");
  }
  if (state.viewport.width <= 720 && state.wiki.icon.width > 70) {
    failures.push(`mobile wiki icon too wide: ${state.wiki.icon.width}px`);
  }
  if (state.scrollHeight > state.viewport.height + 2 && !state.viewport.allowVerticalScroll) {
    failures.push(`unexpected vertical scroll: ${state.scrollHeight}px`);
  }
  if (state.errors.length) {
    failures.push(`browser errors: ${state.errors.join("; ")}`);
  }

  if (failures.length) {
    throw new Error(`${state.viewport.name}: ${failures.join("; ")}`);
  }
}

const browser = await launchBrowser();
const results = [];

try {
  for (const viewport of viewports) {
    const page = await browser.newPage({
      viewport: { width: viewport.width, height: viewport.height },
      deviceScaleFactor: 1,
    });
    const errors = [];
    page.on("pageerror", (error) => errors.push(error.message));
    page.on("console", (message) => {
      if (message.type() === "error") errors.push(message.text());
    });

    await page.goto(targetUrl, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(700);
    await page.locator("#board-canvas").waitFor({ state: "visible", timeout: 10000 });
    await page.click("#btn-rogue-wiki");
    await page.locator("#rogue-wiki-modal.show").waitFor({ state: "visible", timeout: 5000 });

    const state = await page.evaluate((viewportName) => {
      const rect = (selector) => {
        const element = document.querySelector(selector);
        if (!element) return null;
        const r = element.getBoundingClientRect();
        return {
          x: Math.round(r.x),
          y: Math.round(r.y),
          width: Math.round(r.width),
          height: Math.round(r.height),
          right: Math.round(r.right),
          bottom: Math.round(r.bottom),
        };
      };
      const canvas = document.querySelector("#board-canvas");
      const canvasNonblank = (element) => {
        const ctx = element?.getContext("2d");
        if (!ctx || element.width < 10 || element.height < 10) return false;
        const data = ctx.getImageData(0, 0, element.width, element.height).data;
        for (let i = 3; i < data.length; i += 101) {
          if (data[i] !== 0 && (data[i - 1] !== 0 || data[i - 2] !== 0 || data[i - 3] !== 0)) {
            return true;
          }
        }
        return false;
      };
      const wikiContent = document.querySelector("#rogue-wiki-modal .modal-content");
      const wikiCard = document.querySelector("#rogue-wiki-modal .wiki-card-item");
      return {
        viewport: { name: viewportName, width: window.innerWidth, height: window.innerHeight },
        board: { ...rect("#board-canvas"), nonblank: canvasNonblank(canvas) },
        toolbar: rect("#main-toolbar"),
        deck: rect("#client-command-deck"),
        pageScrollWidth: document.documentElement.scrollWidth,
        scrollHeight: document.documentElement.scrollHeight,
        wiki: {
          visible: document.querySelector("#rogue-wiki-modal")?.classList.contains("show") || false,
          modal: rect("#rogue-wiki-modal .modal-content"),
          icon: rect("#rogue-wiki-modal .wiki-card-item .rc-icon"),
          clientWidth: wikiContent?.clientWidth || 0,
          scrollWidth: wikiContent?.scrollWidth || 0,
          cardBackground: wikiCard ? getComputedStyle(wikiCard).backgroundImage : "",
        },
      };
    }, viewport.name);

    state.viewport.allowVerticalScroll = !!viewport.allowVerticalScroll;
    state.errors = errors;
    assertLayoutState(state);
    results.push({
      viewport: state.viewport,
      board: state.board,
      toolbar: state.toolbar,
      wiki: {
        modal: state.wiki.modal,
        icon: state.wiki.icon,
        scrollWidth: state.wiki.scrollWidth,
        clientWidth: state.wiki.clientWidth,
      },
    });
    await page.close();
  }

  for (const size of boardSizes) {
    const page = await browser.newPage({
      viewport: { width: 1366, height: 768 },
      deviceScaleFactor: 1,
    });
    await page.goto(targetUrl, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(700);
    await page.evaluate((boardSize) => {
      window.resizeBoard?.(boardSize);
      window.render?.();
    }, size);
    await page.waitForTimeout(200);
    const state = await page.evaluate((boardSize) => {
      const rect = (selector) => {
        const element = document.querySelector(selector);
        if (!element) return null;
        const r = element.getBoundingClientRect();
        return {
          x: Math.round(r.x),
          y: Math.round(r.y),
          width: Math.round(r.width),
          height: Math.round(r.height),
          right: Math.round(r.right),
          bottom: Math.round(r.bottom),
        };
      };
      const canvas = document.querySelector("#board-canvas");
      const canvasNonblank = (element) => {
        const ctx = element?.getContext("2d");
        if (!ctx || element.width < 10 || element.height < 10) return false;
        const data = ctx.getImageData(0, 0, element.width, element.height).data;
        for (let i = 3; i < data.length; i += 101) {
          if (data[i] !== 0 && (data[i - 1] !== 0 || data[i - 2] !== 0 || data[i - 3] !== 0)) {
            return true;
          }
        }
        return false;
      };
      return {
        boardSize,
        viewport: { width: window.innerWidth, height: window.innerHeight },
        board: { ...rect("#board-canvas"), nonblank: canvasNonblank(canvas) },
        toolbar: rect("#main-toolbar"),
        pageScrollWidth: document.documentElement.scrollWidth,
      };
    }, size);
    const failures = [];
    if (!state.board.nonblank) failures.push("board blank");
    if (state.toolbar.y < state.board.bottom + 4) failures.push("toolbar overlaps board");
    if (state.board.x < 0 || state.board.right > state.viewport.width) failures.push("board horizontally out of viewport");
    if (state.toolbar.x < 0 || state.toolbar.right > state.viewport.width) failures.push("toolbar horizontally out of viewport");
    if (state.pageScrollWidth > state.viewport.width + 2) failures.push("horizontal overflow");
    if (failures.length) {
      throw new Error(`board-size-${size}: ${failures.join("; ")}`);
    }
    results.push({ boardSize: size, board: state.board, toolbar: state.toolbar });
    await page.close();
  }
} finally {
  await browser.close();
}

console.log(JSON.stringify(results, null, 2));
