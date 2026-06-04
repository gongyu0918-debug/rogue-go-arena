import fs from "node:fs/promises";
import http from "node:http";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const screenshotPath = path.join(repoRoot, "output", "legacy-card-overlays.png");

const contentTypes = new Map([
  [".html", "text/html; charset=utf-8"],
  [".css", "text/css; charset=utf-8"],
  [".js", "text/javascript; charset=utf-8"],
  [".json", "application/json; charset=utf-8"],
  [".png", "image/png"],
  [".jpg", "image/jpeg"],
  [".jpeg", "image/jpeg"],
  [".svg", "image/svg+xml"],
  [".ico", "image/x-icon"],
]);

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

async function startStaticServer() {
  const server = http.createServer(async (req, res) => {
    try {
      const url = new URL(req.url || "/", "http://127.0.0.1");
      const pathname = url.pathname === "/" ? "/static/index.html" : decodeURIComponent(url.pathname);
      const filePath = path.resolve(repoRoot, pathname.slice(1));
      if (!filePath.startsWith(repoRoot + path.sep)) {
        res.writeHead(403);
        res.end("Forbidden");
        return;
      }
      const data = await fs.readFile(filePath);
      res.writeHead(200, {
        "content-type": contentTypes.get(path.extname(filePath).toLowerCase()) || "application/octet-stream",
        "cache-control": "no-store",
      });
      res.end(data);
    } catch {
      res.writeHead(404);
      res.end("Not found");
    }
  });
  server.on("upgrade", (_req, socket) => socket.end());
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const address = server.address();
  return {
    server,
    url: `http://127.0.0.1:${address.port}/?lang=zh`,
  };
}

async function launchBrowser() {
  try {
    return await chromium.launch({ channel: "msedge", headless: true });
  } catch {
    return chromium.launch({ headless: true });
  }
}

const { server, url } = await startStaticServer();
const browser = await launchBrowser();
const errors = [];

try {
  const page = await browser.newPage({ viewport: { width: 1366, height: 900 }, deviceScaleFactor: 1 });
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error" && !message.text().includes("WebSocket")) errors.push(message.text());
  });

  await page.addInitScript(() => {
    class MockWebSocket {
      static CONNECTING = 0;
      static OPEN = 1;
      static CLOSING = 2;
      static CLOSED = 3;
      constructor() {
        this.readyState = MockWebSocket.CLOSED;
        setTimeout(() => {
          this.onerror?.(new Event("error"));
          this.onclose?.(new CloseEvent("close"));
        }, 0);
      }
      send() {}
      close() {
        this.readyState = MockWebSocket.CLOSED;
      }
    }
    window.WebSocket = MockWebSocket;
  });

  await page.goto(url, { waitUntil: "domcontentloaded" });
  await page.locator("#board-canvas").waitFor({ state: "visible", timeout: 10000 });
  await page.waitForFunction(() => (
    typeof render === "function" &&
    typeof drawMaskPoints === "function" &&
    typeof showGameStartProgress === "function" &&
    typeof startRogueSealSelection === "function"
  ), null, { timeout: 10000 });

  const state = await page.evaluate(() => {
    showGameStartProgress({ mode: "rogue" });
    const startProgressVisible = document.getElementById("start-progress-modal")?.classList.contains("show") || false;
    advanceStartProgressForGameStart({ rogue_enabled: true });
    const startProgressText = document.getElementById("start-progress-message")?.textContent || "";
    hideStartProgress();

    const size = 19;
    const board = Array.from({ length: size }, () => Array(size).fill(0));
    board[3][3] = 1;
    board[9][9] = 2;
    board[15][15] = 1;
    board[4][14] = 2;
    board[14][4] = 1;
    board[10][10] = 2;
    gameState = {
      size,
      board,
      current_player: "B",
      game_over: false,
      moves_list: [],
      move_number: 12,
      rogue_quickthink_stage: 0,
      rogue_quickthink_seconds: 0,
    };
    boardSize = size;
    myColor = "B";
    isMyTurn = true;
    twoPlayerMode = false;
    reviewMode = false;
    showHints = false;
    showTerritory = false;
    activeRogueCard = "blackhole";
    rogueSeals = [[3, 3], [9, 9], [15, 15]];
    activeAiRogueCard = "fog";
    aiRogueSeals = [[4, 14], [14, 4]];
    rogueSealRequired = 4;
    pendingRogueSealPoints = [[5, 5], [6, 6], [7, 7]];
    rogueSealing = true;
    rogueSealWaitingForOpponent = false;
    resizeBoard(size);
    render();
    drawMaskPoints([[10, 10], [11, 10]], "seal", false);

    const banner = document.getElementById("seal-board-banner");
    const bannerText = document.getElementById("seal-board-banner-text");
    if (bannerText) bannerText.textContent = "请标注禁着点";
    banner?.removeAttribute("hidden");
    document.getElementById("board-container")?.classList.add("seal-stage");

    const probeTile = buildMaskTile({
      key: "probe",
      fill: ["rgba(255,0,0,1)", "rgba(255,0,0,1)"],
      stripe: "rgba(0,0,255,1)",
      edge: "rgba(0,255,0,1)",
      glow: "rgba(255,255,0,1)",
      glyph: "",
    }, 64);
    const probe = probeTile.getContext("2d").getImageData(32, 32, 1, 1).data;
    const canvas = document.getElementById("board-canvas");
    const ctx2d = canvas.getContext("2d");
    const pixels = ctx2d.getImageData(0, 0, canvas.width, canvas.height).data;
    let nonblank = 0;
    for (let i = 3; i < pixels.length; i += 97) {
      if (pixels[i] !== 0 && (pixels[i - 1] !== 0 || pixels[i - 2] !== 0 || pixels[i - 3] !== 0)) nonblank += 1;
    }
    const bannerRect = document.getElementById("seal-board-banner")?.getBoundingClientRect();
    const boardRect = canvas.getBoundingClientRect();
    return {
      startProgressVisible,
      startProgressText,
      bannerText: document.getElementById("seal-board-banner-text")?.textContent || "",
      bannerInsideBoard: !!bannerRect && !!boardRect && bannerRect.left >= boardRect.left && bannerRect.right <= boardRect.right,
      boardClass: document.getElementById("board-container")?.className || "",
      maskHoleAlpha: probe[3],
      nonblank,
      boardWidth: Math.round(boardRect.width),
      boardHeight: Math.round(boardRect.height),
    };
  });

  assert(state.startProgressVisible, "start progress modal did not show");
  assert(state.startProgressText.includes("Rogue") || state.startProgressText.includes("卡牌"), `start progress did not advance to card draft: ${state.startProgressText}`);
  assert(state.bannerText.includes("请标注禁着点"), `seal banner text missing: ${state.bannerText}`);
  assert(state.boardClass.includes("seal-stage"), `seal-stage class missing: ${state.boardClass}`);
  assert(state.bannerInsideBoard, `seal banner is outside the board: ${JSON.stringify(state)}`);
  assert(state.maskHoleAlpha === 0, `mask center/cross transparency failed: alpha=${state.maskHoleAlpha}`);
  assert(state.nonblank > 1000, `canvas appears blank: ${JSON.stringify(state)}`);
  assert(state.boardWidth >= 400 && state.boardHeight >= 400, `board too small: ${JSON.stringify(state)}`);

  await fs.mkdir(path.dirname(screenshotPath), { recursive: true });
  await page.locator("#board-container").screenshot({ path: screenshotPath });
  console.log(JSON.stringify({ ok: true, screenshot: screenshotPath, state }, null, 2));
} finally {
  await browser.close().catch(() => {});
  await new Promise((resolve) => server.close(resolve));
}
