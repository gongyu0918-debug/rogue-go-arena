import { chromium } from "playwright";

const DEFAULT_URL = "http://127.0.0.1:8876/";
const urlArg = process.argv.find((arg) => arg.startsWith("--url="));
const targetUrl = withLanguageParam(
  urlArg ? urlArg.slice("--url=".length) : process.env.LEGACY_WEBSOCKET_MESSAGES_URL || DEFAULT_URL,
  "zh"
);

const expectedMessageTypes = [
  "engine_not_ready",
  "game_start",
  "game_state",
  "ai_move",
  "analysis",
  "game_over",
  "reconnected",
  "reconnect_failed",
  "error",
  "level_set",
  "rogue_offer",
  "rogue_card_selected",
  "rogue_ai_selected",
  "rogue_seal_update",
  "rogue_seal_done",
  "rogue_event",
  "rogue_uses_update",
  "ultimate_offer",
  "ultimate_cards_selected",
];

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

try {
  await page.goto(targetUrl, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(700);
  await page.locator("#board-canvas").waitFor({ state: "visible", timeout: 10000 });

  const state = await page.evaluate((messageTypes) => {
    const emptyBoard = (size) => Array.from({ length: size }, () => Array(size).fill(0));
    const boardWithStone = (size, x, y, value) => {
      const board = emptyBoard(size);
      board[y][x] = value;
      return board;
    };
    const nonblankCanvas = () => {
      const canvas = document.querySelector("#board-canvas");
      const ctx = canvas?.getContext("2d");
      if (!ctx || canvas.width < 10 || canvas.height < 10) return false;
      const data = ctx.getImageData(0, 0, canvas.width, canvas.height).data;
      for (let i = 3; i < data.length; i += 101) {
        if (data[i] !== 0 && (data[i - 1] !== 0 || data[i - 2] !== 0 || data[i - 3] !== 0)) return true;
      }
      return false;
    };
    const baseState = (overrides = {}) => ({
      type: "game_state",
      size: 9,
      board: emptyBoard(9),
      captures: { B: 0, W: 0 },
      current_player: "B",
      player_color: "B",
      ai_color: "W",
      level: "10k",
      move_number: 0,
      komi: 6.5,
      game_over: false,
      two_player: false,
      ai_observer: false,
      rogue_uses: {},
      ...overrides,
    });

    intentionalClose = true;
    ws?.close();
    closeOverlay();
    document.getElementById("rogue-overlay")?.classList.remove("show");
    document.getElementById("ultimate-overlay")?.classList.remove("show");

    const missingTypes = messageTypes.filter(type => typeof LEGACY_WEBSOCKET_MESSAGE_HANDLERS[type] !== "function");
    const executedTypes = [];
    const dispatch = (msg) => {
      executedTypes.push(msg.type);
      handleMessage(msg);
    };

    dispatch({
      type: "engine_not_ready",
      phase: "initializing",
      message: "KataGo smoke loading",
      log_tail: [{ message: "loading model" }, { message: "warming policy" }],
    });
    const startProgressVisibleAfterEngineWait = document
      .querySelector("#start-progress-modal")
      ?.classList.contains("show") || false;
    const startProgressTextAfterEngineWait = [
      document.querySelector("#start-progress-title")?.textContent || "",
      document.querySelector("#start-progress-message")?.textContent || "",
      document.querySelector("#start-progress-detail")?.textContent || "",
    ].join(" ");

    dispatch({ ...baseState(), type: "game_start" });
    dispatch({
      ...baseState({ move_number: 0 }),
      type: "reconnected",
    });
    const reconnectMoveNumber = gameState?.move_number;

    dispatch({ type: "reconnect_failed" });
    dispatch({ type: "level_set", level: "8k" });
    const levelAfterSet = gameState?.level;

    previousBoard = boardWithStone(9, 1, 1, 1);
    gameState.board = boardWithStone(9, 4, 4, 1);
    dispatch({ type: "error", message: "Smoke rejected move" });
    const errorRevertedBoard = gameState.board?.[1]?.[1] === 1 && gameState.board?.[4]?.[4] === 0;

    dispatch({
      ...baseState({
        board: boardWithStone(9, 4, 4, 1),
        current_player: "W",
        move_number: 1,
      }),
      type: "game_state",
    });

    const methodicalInputProbe = (() => {
      const sent = [];
      const thinking = [];
      const originalSendWS = window.sendWS;
      const originalSetThinking = window.setThinking;
      window.sendWS = (payload) => sent.push(payload);
      window.setThinking = (value) => thinking.push(value);
      try {
        gameState = baseState({
          rogue_card: "methodical",
          rogue_methodical_remaining: 2,
          board: emptyBoard(9),
          current_player: "B",
        });
        activeRogueCard = "methodical";
        twoPlayerMode = false;
        myColor = "B";
        isMyTurn = true;
        commitPlay(1, 1);
        const first = {
          isMyTurn,
          thinking: thinking.at(-1),
          action: sent.at(-1)?.action,
          x: sent.at(-1)?.x,
          boardValue: gameState.board[1][1],
        };
        clearTimeout(aiResponseTimer);

        sent.length = 0;
        thinking.length = 0;
        gameState = baseState({
          rogue_card: "methodical",
          rogue_methodical_remaining: 1,
          board: emptyBoard(9),
          current_player: "B",
        });
        isMyTurn = true;
        commitPlay(2, 2);
        const second = {
          isMyTurn,
          thinking: thinking.at(-1),
          action: sent.at(-1)?.action,
          x: sent.at(-1)?.x,
          boardValue: gameState.board[2][2],
        };
        clearTimeout(aiResponseTimer);
        return { first, second };
      } finally {
        window.sendWS = originalSendWS;
        window.setThinking = originalSetThinking;
      }
    })();

    dispatch({
      type: "analysis",
      winrate: 0.83,
      score: 3.5,
      top_moves: [],
      ownership: Array.from({ length: 81 }, (_item, index) => (index < 45 ? 0.7 : -0.7)),
      analysis_ready: true,
    });
    dispatch({ type: "ai_move", color: "W", x: 3, y: 3, gtp: "D6" });
    dispatch({
      type: "rogue_offer",
      cards: [{ id: "quickthink", name: "快速思考", desc: "Smoke", icon: "⚡" }],
      challenge_beta: false,
    });
    const rogueOfferOpenAfterOffer = document.querySelector("#rogue-overlay")?.classList.contains("show") || false;
    const rogueOfferCardCount = document.querySelectorAll("#rogue-cards .rogue-card").length;
    const startProgressVisibleAfterRogueOffer = document
      .querySelector("#start-progress-modal")
      ?.classList.contains("show") || false;
    const startProgressTextAfterRogueOffer = document.querySelector("#start-progress-message")?.textContent || "";

    dispatch({
      ...baseState({
        board: boardWithStone(9, 4, 4, 1),
        current_player: "W",
        move_number: 1,
      }),
      type: "rogue_card_selected",
      card_id: "quickthink",
      card_name: "快速思考",
      icon: "⚡",
      rogue_uses: { quickthink: 1 },
    });
    dispatch({
      ...baseState({ board: boardWithStone(9, 4, 4, 1), move_number: 1 }),
      type: "rogue_ai_selected",
      card_id: "dice",
      card_name: "骰子",
      icon: "🎲",
      ai_rogue_seal_points: [[2, 2]],
    });
    const aiRogueCardAfterSelected = activeAiRogueCard;

    dispatch({ type: "rogue_seal_update", remaining: 2, points: [[2, 2], [3, 3]] });
    const sealHintAfterUpdate = document.querySelector("#seal-hint")?.textContent || "";
    const rogueSealCountAfterUpdate = rogueSeals.length;

    rogueSealing = true;
    const sealOverlay = document.getElementById("seal-overlay");
    sealOverlay.hidden = false;
    dispatch({ type: "rogue_seal_done" });
    const sealOverlayHiddenAfterDone = document.getElementById("seal-overlay")?.hidden ?? false;
    const rogueSealingAfterDone = rogueSealing;

    dispatch({ type: "rogue_event", msg: "Smoke rogue event" });
    dispatch({ type: "rogue_uses_update", uses: { quickthink: 2 } });
    dispatch({
      type: "ultimate_offer",
      cards: [{ id: "chain", name: "连环", desc: "Smoke", icon: "⛓" }],
    });
    const ultimateOfferOpenAfterOffer = document.querySelector("#ultimate-overlay")?.classList.contains("show") || false;
    const ultimateOfferCardCount = document.querySelectorAll("#ultimate-cards .ultimate-card").length;

    dispatch({
      ...baseState({
        board: boardWithStone(9, 4, 4, 1),
        current_player: "W",
        move_number: 1,
      }),
      type: "ultimate_cards_selected",
      player_card: "chain",
      player_icon: "⛓",
      ai_card: "double",
      ai_icon: "Ⅱ",
    });
    dispatch({ type: "game_over", winner: "B", score: "B+3.5", reason: "score" });

    return {
      handlerType: typeof window.handleMessage,
      missingTypes,
      executedTypes,
      unexecutedTypes: messageTypes.filter(type => !executedTypes.includes(type)),
      boardSize,
      moveNumber: gameState?.move_number,
      currentPlayer: gameState?.current_player,
      gameOver: gameState?.game_over,
      reconnectMoveNumber,
      levelAfterSet,
      startProgressVisibleAfterEngineWait,
      startProgressTextAfterEngineWait,
      methodicalInputProbe,
      errorRevertedBoard,
      activeRogueCard,
      aiRogueCardAfterSelected,
      rogueUses,
      rogueOfferOpenAfterOffer,
      rogueOfferCardCount,
      startProgressVisibleAfterRogueOffer,
      startProgressTextAfterRogueOffer,
      sealHintAfterUpdate,
      rogueSealCountAfterUpdate,
      sealOverlayHiddenAfterDone,
      rogueSealingAfterDone,
      ultimateMode,
      ultimatePlayerCard,
      ultimateAiCard,
      ultimateOfferOpenAfterOffer,
      ultimateOfferCardCount,
      analysisReady,
      winrateHistoryLength: winrateHistory.length,
      infoScore: document.querySelector("#info-score")?.textContent || "",
      infoTerritory: document.querySelector("#info-territory")?.textContent || "",
      overlayClass: document.querySelector("#overlay")?.className || "",
      overlayWinner: document.querySelector("#overlay-winner")?.textContent || "",
      rogueOverlayOpen: document.querySelector("#rogue-overlay")?.classList.contains("show") || false,
      ultimateOverlayOpen: document.querySelector("#ultimate-overlay")?.classList.contains("show") || false,
      logText: document.querySelector("#game-log")?.textContent || "",
      canvasNonblank: nonblankCanvas(),
    };
  }, expectedMessageTypes);

  assert(state.handlerType === "function", `handleMessage is not public: ${state.handlerType}`);
  assert(state.missingTypes.length === 0, `missing message handlers: ${state.missingTypes.join(", ")}`);
  assert(state.unexecutedTypes.length === 0, `message handlers were not executed: ${state.unexecutedTypes.join(", ")}`);
  assert(state.boardSize === 9, `game_start did not resize board: ${state.boardSize}`);
  assert(state.moveNumber === 1, `unexpected move number after message sequence: ${state.moveNumber}`);
  assert(state.currentPlayer === "W", `unexpected current player: ${state.currentPlayer}`);
  assert(state.gameOver, "game_over message did not mark game over");
  assert(state.reconnectMoveNumber === 0, `reconnected message did not restore state: ${state.reconnectMoveNumber}`);
  assert(state.levelAfterSet === "8k", `level_set message did not update level: ${state.levelAfterSet}`);
  assert(state.startProgressVisibleAfterEngineWait, "engine_not_ready did not show start progress");
  assert(
    state.startProgressTextAfterEngineWait.includes("KataGo smoke loading") &&
      state.startProgressTextAfterEngineWait.includes("warming policy"),
    `engine_not_ready did not render progress text: ${state.startProgressTextAfterEngineWait}`
  );
  assert(state.methodicalInputProbe.first.isMyTurn, "methodical first optimistic move should keep player turn");
  assert(
    state.methodicalInputProbe.first.thinking === false &&
      state.methodicalInputProbe.first.action === "play" &&
      state.methodicalInputProbe.first.x === 1 &&
      state.methodicalInputProbe.first.boardValue === 1,
    `methodical first move probe failed: ${JSON.stringify(state.methodicalInputProbe.first)}`
  );
  assert(!state.methodicalInputProbe.second.isMyTurn, "methodical final optimistic move should wait for AI");
  assert(
    state.methodicalInputProbe.second.thinking === true &&
      state.methodicalInputProbe.second.action === "play" &&
      state.methodicalInputProbe.second.x === 2 &&
      state.methodicalInputProbe.second.boardValue === 1,
    `methodical final move probe failed: ${JSON.stringify(state.methodicalInputProbe.second)}`
  );
  assert(state.errorRevertedBoard, "error message did not revert optimistic board state");
  assert(state.rogueOfferOpenAfterOffer, "rogue_offer did not open the Rogue overlay");
  assert(state.rogueOfferCardCount === 1, `rogue_offer did not render a card: ${state.rogueOfferCardCount}`);
  assert(state.startProgressVisibleAfterRogueOffer, "rogue_offer hid the start progress immediately");
  assert(
    state.startProgressTextAfterRogueOffer.includes("Rogue"),
    `rogue_offer did not hand off through start progress: ${state.startProgressTextAfterRogueOffer}`
  );
  assert(state.activeRogueCard === "quickthink", `rogue card did not sync: ${state.activeRogueCard}`);
  assert(state.aiRogueCardAfterSelected === "dice", `rogue_ai_selected did not sync AI card: ${state.aiRogueCardAfterSelected}`);
  assert(
    state.sealHintAfterUpdate.includes("剩余 2") || state.sealHintAfterUpdate.includes("2/2"),
    `rogue_seal_update did not update hint: ${state.sealHintAfterUpdate}`
  );
  assert(state.rogueSealCountAfterUpdate === 2, `rogue_seal_update did not sync points: ${state.rogueSealCountAfterUpdate}`);
  assert(state.sealOverlayHiddenAfterDone === true, `rogue_seal_done did not hide overlay: ${state.sealOverlayHiddenAfterDone}`);
  assert(!state.rogueSealingAfterDone, "rogue_seal_done did not clear rogueSealing");
  assert(state.rogueUses.quickthink === 2, `rogue uses did not sync: ${JSON.stringify(state.rogueUses)}`);
  assert(state.ultimateOfferOpenAfterOffer, "ultimate_offer did not open the Ultimate overlay");
  assert(state.ultimateOfferCardCount === 1, `ultimate_offer did not render a card: ${state.ultimateOfferCardCount}`);
  assert(state.ultimateMode, "ultimate mode was not enabled");
  assert(state.ultimatePlayerCard === "chain", `ultimate player card did not sync: ${state.ultimatePlayerCard}`);
  assert(state.ultimateAiCard === "double", `ultimate AI card did not sync: ${state.ultimateAiCard}`);
  assert(state.analysisReady, "analysis message did not mark analysisReady");
  assert(state.winrateHistoryLength > 0, `analysis message did not append winrate history: ${state.winrateHistoryLength}`);
  assert(state.infoScore.includes("黑领先"), `analysis score text did not update: ${state.infoScore}`);
  assert(state.infoTerritory.includes("黑多"), `analysis territory text did not update: ${state.infoTerritory}`);
  assert(state.overlayClass.includes("show"), `game_over overlay did not open: ${state.overlayClass}`);
  assert(state.overlayWinner === "黑棋", `game_over winner did not render: ${state.overlayWinner}`);
  assert(!state.rogueOverlayOpen, "rogue card selection did not close the Rogue overlay");
  assert(!state.ultimateOverlayOpen, "ultimate card selection did not close the Ultimate overlay");
  assert(
    state.logText.includes("AI") &&
      state.logText.includes("胜") &&
      state.logText.includes("暂无进行中的对局") &&
      state.logText.includes("Smoke rejected move") &&
      state.logText.includes("Smoke rogue event"),
    "message sequence did not append expected logs"
  );
  assert(state.canvasNonblank, "board canvas is blank after WebSocket messages");
  assert(errors.length === 0, `browser errors: ${errors.join("; ")}`);

  console.log(JSON.stringify({
    ok: true,
    checkedTypes: state.executedTypes.length,
    boardSize: state.boardSize,
    activeRogueCard: state.activeRogueCard,
    ultimatePlayerCard: state.ultimatePlayerCard,
  }, null, 2));
} finally {
  await browser.close();
}
