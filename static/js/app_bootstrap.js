// Legacy app startup, WebSocket connection setup, and board recovery hooks.

let legacyBootstrapHooksInstalled = false;

function connect() {
  const wsScheme = location.protocol === "https:" ? "wss" : "ws";
  const wsUrl = `${wsScheme}://${location.host}/ws/${gameId}`;
  ws = new WebSocket(wsUrl);
  ws.onopen = () => {
    setConnectionIndicator(true, ui("已连接", "Connected"));
    logI18n("已连接", "Connected", "接続済み", "연결됨");
    refreshNetworkInfo();
    if (!gameState) sendWS({ action: "reconnect" });
  };
  ws.onclose = () => {
    if (intentionalClose) {
      intentionalClose = false;
      return;
    }
    setConnectionIndicator(false, ui("连接断开，重连中…", "Disconnected, reconnecting..."));
    setTimeout(connect, 2000);
  };
  ws.onmessage = event => handleMessage(JSON.parse(event.data));
  ws.onerror = () => { setConnectionIndicator(false, ui("连接错误", "Connection error")); };
}

function initBoard() {
  resizeBoard(boardSize || 19);
  _boardCacheParams = "";
  _offScreenBoard = null;
  render();
  ensureBoardReady(300);
}

async function bootstrapApp() {
  await ensureLocale(currentLang);
  applyLanguage();
  setSoundToggleVisual();
  setTerritoryToggleVisual();
  refreshHintVisibility();
  attachButtonRipples();
  initBoard();
  setMode(startMode);
  triggerBoardIntro();
  refreshNetworkInfo();
  connect();
}

function installLegacyBootstrapHooks() {
  if (legacyBootstrapHooksInstalled) return;
  legacyBootstrapHooksInstalled = true;

  window.addEventListener("load", () => {
    initBoard();
  });

  window.addEventListener("pageshow", () => {
    ensureBoardReady(0);
  });

  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) ensureBoardReady(0);
  });

  if (typeof ResizeObserver !== "undefined" && boardContainer) {
    const observer = new ResizeObserver(() => {
      ensureBoardReady(0);
    });
    observer.observe(boardContainer);
  }

  window.addEventListener("resize", () => {
    _boardCacheParams = "";
    _offScreenBoard = null;
    _stoneSpriteCache = new Map();
    resizeBoard(reviewMode ? reviewBoardSize : boardSize);
    render();
    drawWinrateCurve();
    ensureBoardReady(100);
  });

  boardWatchdogTimer = window.setInterval(() => {
    ensureBoardReady(0);
  }, 1500);
}

window.connect = connect;
window.initBoard = initBoard;
window.bootstrapApp = bootstrapApp;
window.installLegacyBootstrapHooks = installLegacyBootstrapHooks;
