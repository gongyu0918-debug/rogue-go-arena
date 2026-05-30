import { chromium } from "playwright";

const DEFAULT_URL = "http://127.0.0.1:8876/";
const urlArg = process.argv.find((arg) => arg.startsWith("--url="));
const targetUrl = withLanguageParam(
  urlArg ? urlArg.slice("--url=".length) : process.env.LEGACY_RUNTIME_HELPERS_URL || DEFAULT_URL,
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

try {
  await page.goto(targetUrl, { waitUntil: "domcontentloaded" });
  await page.locator("#board-canvas").waitFor({ state: "visible", timeout: 10000 });

  const state = await page.evaluate(() => {
    const emptyBoard = (size) => Array.from({ length: size }, () => Array(size).fill(0));
    const publicFns = [
      typeof window.resetChallengeSession,
      typeof window.syncChallengeSessionFromState,
      typeof window.updateChallengeInfo,
      typeof window.getCurrentBoard,
      typeof window.getCurrentSize,
      typeof window.detectCaptures,
      typeof window.detectNewStone,
    ];
    const stateGlobals = [
      typeof window.challengeSession,
    ];
    const challengeSessionDescriptor = Object.getOwnPropertyDescriptor(window, "challengeSession");
    const privateFns = [
      typeof window.DEFAULT_CHALLENGE_RESOURCES,
      typeof window.cloneChallengeResources,
      typeof window.createChallengeSession,
      typeof window.cloneChallengeCards,
      typeof window.mergeChallengeResources,
      typeof window.syncChallengeLimits,
      typeof window.syncChallengeRemaining,
      typeof window.ensureChallengeInfoElements,
      typeof window.challengeInfoShouldShow,
      typeof window.challengeInfoText,
      typeof window.boardPairIsUsable,
      typeof window.scanBoardDiff,
    ];

    resetChallengeSession();
    const resetState = JSON.parse(JSON.stringify(challengeSession));

    const noSyncBefore = JSON.parse(JSON.stringify(challengeSession));
    syncChallengeSessionFromState({ challenge_beta: false, challenge_stage: 9, challenge_cards: ["ignored"] });
    const noSyncAfter = JSON.parse(JSON.stringify(challengeSession));

    const sourceState = {
      challenge_beta: true,
      challenge_stage: 3,
      challenge_cards: ["quickthink", "seal"],
      challenge_refreshes: 2,
      challenge_limits: { undo: 5, hint: 8 },
      challenge_remaining: { undo: 4, coach: 1 },
    };
    syncChallengeSessionFromState(sourceState);
    sourceState.challenge_cards.push("mutated");
    const syncedState = JSON.parse(JSON.stringify(challengeSession));

    syncChallengeSessionFromState({
      challenge_beta: true,
      challenge_stage: 4,
      challenge_cards: ["coach_mode"],
      challenge_refreshes: 6,
      challenge_limits: { undo: 7, hint: 11, coach: 2 },
    });
    const defaultRemainingState = JSON.parse(JSON.stringify(challengeSession));

    challengeSession = {
      active: true,
      stage: 8,
      cards: ["assigned"],
      refreshes: 9,
      limits: { undo: 1, hint: 2, coach: 3 },
      remaining: { undo: 1, hint: 2, coach: 3 },
      cleared: false,
    };
    const assignedState = JSON.parse(JSON.stringify(challengeSession));

    window.challengeSession = {
      active: true,
      stage: 6,
      cards: ["quickthink", "seal"],
      refreshes: 2,
      limits: { undo: 4, hint: 5, coach: 6 },
      remaining: { undo: 4, hint: 5, coach: 6 },
      cleared: false,
    };
    showRogueCards([
      { id: "quickthink", name: "快速思考", desc: "Smoke challenge offer", icon: "⚡" },
    ], { challenge_beta: true });
    const challengeOffer = {
      title: document.querySelector("#rogue-overlay h2")?.textContent || "",
      sub: document.querySelector("#rogue-overlay p")?.textContent || "",
      refreshDisplay: document.querySelector("#rogue-refresh-wrap")?.style.display || "",
      refreshButton: document.querySelector("#rogue-refresh-btn")?.textContent || "",
      cardCount: document.querySelectorAll("#rogue-cards .rogue-card").length,
      overlayOpen: document.querySelector("#rogue-overlay")?.classList.contains("show") || false,
      session: JSON.parse(JSON.stringify(window.challengeSession)),
    };
    document.querySelector("#rogue-overlay")?.classList.remove("show");
    resetChallengeSession();

    document.querySelector("#challenge-info-row")?.remove();
    gameState = null;
    challengeSession.active = false;
    updateChallengeInfo();
    const hiddenInfo = {
      rowExists: !!document.querySelector("#challenge-info-row"),
      display: document.querySelector("#challenge-info-row")?.style.display || "",
      text: document.querySelector("#challenge-info")?.textContent || "",
    };

    challengeSession.active = true;
    challengeSession.stage = 5;
    challengeSession.cards = ["quickthink", "seal", "coach_mode"];
    challengeSession.remaining = { undo: 2, hint: 9, coach: 1 };
    challengeSession.refreshes = 4;
    updateChallengeInfo();
    const visibleInfo = {
      display: document.querySelector("#challenge-info-row")?.style.display || "",
      text: document.querySelector("#challenge-info")?.textContent || "",
    };

    gameState = {
      size: 9,
      board: emptyBoard(9),
    };
    gameState.board[2][3] = 1;
    reviewMode = false;
    boardSize = 19;
    const liveBoard = getCurrentBoard();
    const liveSize = getCurrentSize();

    reviewMode = true;
    reviewBoardSize = 9;
    reviewMoves = [
      { color: "B", gtp: "D4" },
      { color: "W", gtp: "E4" },
    ];
    reviewIndex = 1;
    const reviewBoard = getCurrentBoard();
    const reviewSize = getCurrentSize();

    const oldBoard = emptyBoard(5);
    const newBoard = emptyBoard(5);
    oldBoard[1][1] = 1;
    oldBoard[2][2] = 2;
    oldBoard[3][3] = 1;
    newBoard[1][1] = 0;
    newBoard[2][2] = 2;
    newBoard[3][3] = 0;
    newBoard[4][4] = 2;
    const captures = detectCaptures(oldBoard, newBoard, 5);
    const newStone = detectNewStone(oldBoard, newBoard, 5);
    const nullDiff = {
      captures: detectCaptures(null, newBoard, 5),
      newStone: detectNewStone(oldBoard, null, 5),
    };

    return {
      publicFns,
      stateGlobals,
      challengeSessionDescriptor: {
        get: typeof challengeSessionDescriptor?.get,
        set: typeof challengeSessionDescriptor?.set,
        value: typeof challengeSessionDescriptor?.value,
      },
      privateFns,
      resetState,
      noSyncBefore,
      noSyncAfter,
      syncedState,
      defaultRemainingState,
      assignedState,
      challengeOffer,
      hiddenInfo,
      visibleInfo,
      liveBoardValue: liveBoard?.[2]?.[3],
      liveSize,
      reviewBoardValues: {
        black: reviewBoard?.[5]?.[3],
        white: reviewBoard?.[5]?.[4],
      },
      reviewSize,
      captures,
      newStone,
      nullDiff,
    };
  });

  assert(state.publicFns.every(type => type === "function"), `runtime helper globals missing: ${state.publicFns.join(", ")}`);
  assert(state.stateGlobals.join("|") === "object", `runtime helper state globals changed: ${state.stateGlobals.join("|")}`);
  assert(state.challengeSessionDescriptor.get === "function" && state.challengeSessionDescriptor.set === "function", `challengeSession is not an accessor: ${JSON.stringify(state.challengeSessionDescriptor)}`);
  assert(state.challengeSessionDescriptor.value === "undefined", `challengeSession unexpectedly has a data value: ${JSON.stringify(state.challengeSessionDescriptor)}`);
  assert(state.privateFns.every(type => type === "undefined"), `runtime helper private helpers leaked globally: ${state.privateFns.join(", ")}`);
  assert(state.resetState.active === true && state.resetState.stage === 1, `challenge reset base state changed: ${JSON.stringify(state.resetState)}`);
  assert(state.resetState.cards.length === 0 && state.resetState.refreshes === 0, `challenge reset card/refresh state changed: ${JSON.stringify(state.resetState)}`);
  assert(state.resetState.limits.undo === 3 && state.resetState.remaining.hint === 10, `challenge reset limits changed: ${JSON.stringify(state.resetState)}`);
  assert(JSON.stringify(state.noSyncBefore) === JSON.stringify(state.noSyncAfter), "non-challenge state should not sync challenge session");
  assert(state.syncedState.stage === 3, `challenge stage did not sync: ${state.syncedState.stage}`);
  assert(state.syncedState.cards.join(",") === "quickthink,seal", `challenge cards were not cloned/synced: ${state.syncedState.cards.join(",")}`);
  assert(state.syncedState.refreshes === 2, `challenge refreshes did not sync: ${state.syncedState.refreshes}`);
  assert(state.syncedState.limits.undo === 5 && state.syncedState.limits.hint === 8 && state.syncedState.limits.coach === 3, `partial limits changed: ${JSON.stringify(state.syncedState.limits)}`);
  assert(state.syncedState.remaining.undo === 4 && state.syncedState.remaining.hint === 10 && state.syncedState.remaining.coach === 1, `partial remaining changed: ${JSON.stringify(state.syncedState.remaining)}`);
  assert(state.defaultRemainingState.remaining.undo === 7 && state.defaultRemainingState.remaining.hint === 11 && state.defaultRemainingState.remaining.coach === 2, `missing remaining did not default to limits: ${JSON.stringify(state.defaultRemainingState.remaining)}`);
  assert(state.assignedState.stage === 8 && state.assignedState.cards.join(",") === "assigned", `challengeSession accessor assignment changed: ${JSON.stringify(state.assignedState)}`);
  assert(state.assignedState.remaining.hint === 2 && state.assignedState.refreshes === 9, `challengeSession assigned resources changed: ${JSON.stringify(state.assignedState)}`);
  assert(state.challengeOffer.session.stage === 6 && state.challengeOffer.session.refreshes === 2, `window.challengeSession assignment changed: ${JSON.stringify(state.challengeOffer.session)}`);
  assert(state.challengeOffer.overlayOpen, "challenge Rogue offer did not open overlay");
  assert(state.challengeOffer.title.includes("第 6 关"), `challenge Rogue title did not use challengeSession stage: ${state.challengeOffer.title}`);
  assert(state.challengeOffer.sub.includes("刷新 2"), `challenge Rogue subtitle did not use challengeSession refreshes: ${state.challengeOffer.sub}`);
  assert(state.challengeOffer.refreshDisplay === "", `challenge refresh controls did not show: ${JSON.stringify(state.challengeOffer)}`);
  assert(state.challengeOffer.refreshButton.includes("(2)"), `challenge refresh button did not use refresh count: ${state.challengeOffer.refreshButton}`);
  assert(state.challengeOffer.cardCount === 1, `challenge Rogue offer card count changed: ${state.challengeOffer.cardCount}`);
  assert(state.hiddenInfo.rowExists && state.hiddenInfo.display === "none", `challenge info hidden state changed: ${JSON.stringify(state.hiddenInfo)}`);
  assert(state.visibleInfo.display === "" && state.visibleInfo.text.includes("测试第5关"), `challenge info visible text changed: ${JSON.stringify(state.visibleInfo)}`);
  assert(state.visibleInfo.text.includes("卡牌3") && state.visibleInfo.text.includes("刷新4"), `challenge info count text changed: ${state.visibleInfo.text}`);
  assert(state.liveBoardValue === 1, `getCurrentBoard did not return live board: ${state.liveBoardValue}`);
  assert(state.liveSize === 9, `getCurrentSize did not return live size: ${state.liveSize}`);
  assert(state.reviewBoardValues.black === 1 && state.reviewBoardValues.white === 2, `review board values changed: ${JSON.stringify(state.reviewBoardValues)}`);
  assert(state.reviewSize === 9, `review size changed: ${state.reviewSize}`);
  assert(state.captures.length === 2, `capture detection count changed: ${JSON.stringify(state.captures)}`);
  assert(state.captures.some(item => item[0] === 1 && item[1] === 1 && item[2] === "B"), `black capture missing: ${JSON.stringify(state.captures)}`);
  assert(state.captures.some(item => item[0] === 3 && item[1] === 3 && item[2] === "B"), `second capture missing: ${JSON.stringify(state.captures)}`);
  assert(state.newStone?.x === 4 && state.newStone?.y === 4, `new stone detection changed: ${JSON.stringify(state.newStone)}`);
  assert(state.nullDiff.captures.length === 0 && state.nullDiff.newStone === null, `null board diff behavior changed: ${JSON.stringify(state.nullDiff)}`);
  assert(errors.length === 0, `browser errors: ${errors.join("; ")}`);

  console.log(JSON.stringify({
    ok: true,
    challengeText: state.visibleInfo.text,
    captures: state.captures.length,
    reviewSize: state.reviewSize,
  }, null, 2));
} finally {
  await browser.close();
}
