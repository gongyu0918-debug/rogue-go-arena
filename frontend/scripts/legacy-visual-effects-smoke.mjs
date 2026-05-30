import { chromium } from "playwright";

const DEFAULT_URL = "http://127.0.0.1:8876/";
const urlArg = process.argv.find((arg) => arg.startsWith("--url="));
const targetUrl = withLanguageParam(
  urlArg ? urlArg.slice("--url=".length) : process.env.LEGACY_VISUAL_EFFECTS_URL || DEFAULT_URL,
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

  const state = await page.evaluate(async () => {
    const fxLayer = document.querySelector("#board-fx-layer");
    const globalLayer = document.querySelector("#global-fx-layer");
    const overlaySparks = document.querySelector("#overlay-sparks");
    const clearFx = () => {
      if (fxLayer) fxLayer.innerHTML = "";
      if (globalLayer) globalLayer.innerHTML = "";
      if (overlaySparks) overlaySparks.innerHTML = "";
    };

    const publicFns = [
      typeof window.getAudioCtx,
      typeof window.playStoneSound,
      typeof window.playCaptureSound,
      typeof window.playTimerWarningSound,
      typeof window.addPlaceAnimation,
      typeof window.addCaptureAnimation,
      typeof window.triggerBoardIntro,
      typeof window.attachButtonRipples,
      typeof window.spawnOverlaySparks,
      typeof window.inferEffectTheme,
      typeof window.showCardEffectVisual,
      typeof window.playGodHandFlash,
      typeof window.playFogFlowEffect,
      typeof window.playSanrenseiConstellation,
      typeof window.playFiveInRowBurst,
      typeof window.playLastStandPulse,
      typeof window.triggerSignatureCardEffect,
      typeof window.startAnimLoop,
    ];

    soundEnabled = false;
    audioCtx = null;
    playStoneSound();
    playCaptureSound(2);
    playTimerWarningSound();
    const soundDisabledState = {
      soundEnabled,
      audioCtxIsNull: audioCtx === null,
    };
    soundEnabled = true;

    const originalRender = render;
    window.__visualFxSmoke = { renderCalls: 0 };
    render = window.render = () => {
      window.__visualFxSmoke.renderCalls += 1;
    };
    animations = [];
    animFrameId = null;
    addPlaceAnimation(1, 2);
    addCaptureAnimation([[3, 4, "B"], [5, 6, "W"]]);
    const animationQueuedState = {
      count: animations.length,
      hasPlace: animations.some(a => a.type === "place" && a.x === 1 && a.y === 2),
      captureCount: animations.filter(a => a.type === "capture").length,
      animFrameIsSet: animFrameId !== null,
    };
    await new Promise(resolve => requestAnimationFrame(resolve));
    animations = [];
    await new Promise(resolve => requestAnimationFrame(resolve));
    const animationLoopState = {
      renderCalls: window.__visualFxSmoke.renderCalls,
      animFrameIsNull: animFrameId === null,
    };
    render = window.render = originalRender;

    triggerBoardIntro();
    const boardIntroState = {
      played: boardIntroPlayed,
      className: document.querySelector("#board-container")?.className || "",
    };

    const setupButton = document.querySelector("#btn-setup");
    setupButton.dataset.rippleBound = "";
    attachButtonRipples();
    const rippleBound = setupButton.dataset.rippleBound === "1";
    setupButton.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true, clientX: 8, clientY: 8 }));
    const rippleCount = setupButton.querySelectorAll(".btn-ripple").length;

    clearFx();
    spawnOverlaySparks("victory");
    const sparkState = {
      count: document.querySelectorAll("#overlay-sparks .overlay-spark").length,
    };

    const themeState = {
      puppet: inferEffectTheme("傀儡术发动").key,
      fog: inferEffectTheme("Fog of War").key,
      fallback: inferEffectTheme("unknown smoke event").key,
    };

    clearFx();
    showCardEffectVisual("傀儡术发动", "rogue");
    const cardFxState = {
      bannerClass: document.querySelector("#board-fx-layer .fx-banner")?.className || "",
      title: document.querySelector("#board-fx-layer .fx-banner-title")?.textContent || "",
      desc: document.querySelector("#board-fx-layer .fx-banner-desc")?.textContent || "",
      particles: document.querySelectorAll("#board-fx-layer .fx-particle").length,
      rings: document.querySelectorAll("#board-fx-layer .fx-ring").length,
    };

    clearFx();
    playGodHandFlash();
    const godHandState = {
      flashes: document.querySelectorAll("#global-fx-layer .fx-godflash").length,
    };

    clearFx();
    PAD = 20;
    CELL = 30;
    boardSize = 9;
    gameState = { size: 9 };
    rogueSeals = [[1, 1], [2, 2]];
    playFogFlowEffect([[1, 1], [2, 2], [3, 3]]);
    const fogState = {
      veils: document.querySelectorAll("#board-fx-layer .fx-fog-veil").length,
      clouds: document.querySelectorAll("#board-fx-layer .fx-fog-cloud").length,
    };

    clearFx();
    playSanrenseiConstellation(false);
    const starState = {
      pulses: document.querySelectorAll("#board-fx-layer .fx-star-pulse").length,
      links: document.querySelectorAll("#board-fx-layer .fx-star-link").length,
    };

    clearFx();
    playFiveInRowBurst();
    const fiveState = {
      lines: document.querySelectorAll("#board-fx-layer .fx-five-line").length,
    };

    clearFx();
    playLastStandPulse();
    const lastStandState = {
      pulses: document.querySelectorAll("#board-fx-layer .fx-last-stand-pulse").length,
    };

    clearFx();
    triggerSignatureCardEffect("神之一手 Five in a Row");
    const signatureState = {
      flashes: document.querySelectorAll("#global-fx-layer .fx-godflash").length,
      fiveLines: document.querySelectorAll("#board-fx-layer .fx-five-line").length,
    };

    return {
      publicFns,
      soundDisabledState,
      animationQueuedState,
      animationLoopState,
      boardIntroState,
      rippleBound,
      rippleCount,
      sparkState,
      themeState,
      cardFxState,
      godHandState,
      fogState,
      starState,
      fiveState,
      lastStandState,
      signatureState,
    };
  });

  assert(state.publicFns.every(type => type === "function"), `visual effect globals missing: ${state.publicFns.join(", ")}`);
  assert(state.soundDisabledState.soundEnabled === false, "sound disabled state did not persist during disabled sound calls");
  assert(state.soundDisabledState.audioCtxIsNull, "disabled sound calls should not create AudioContext");
  assert(state.animationQueuedState.count === 3, `animations were not queued: ${JSON.stringify(state.animationQueuedState)}`);
  assert(state.animationQueuedState.hasPlace, "place animation missing");
  assert(state.animationQueuedState.captureCount === 2, `capture animations missing: ${state.animationQueuedState.captureCount}`);
  assert(state.animationQueuedState.animFrameIsSet, "animation loop was not scheduled");
  assert(state.animationLoopState.renderCalls >= 1, `animation loop did not render: ${state.animationLoopState.renderCalls}`);
  assert(state.animationLoopState.animFrameIsNull, "animation loop did not settle after clearing animations");
  assert(state.boardIntroState.played && state.boardIntroState.className.includes("board-intro"), `board intro did not run: ${JSON.stringify(state.boardIntroState)}`);
  assert(state.rippleBound, "button ripple binding was not attached");
  assert(state.rippleCount >= 1, `button ripple was not spawned: ${state.rippleCount}`);
  assert(state.sparkState.count === 16, `overlay sparks count changed: ${state.sparkState.count}`);
  assert(state.themeState.puppet === "puppet" && state.themeState.fog === "fog" && state.themeState.fallback === "rogue", `effect theme inference changed: ${JSON.stringify(state.themeState)}`);
  assert(state.cardFxState.bannerClass.includes("fx-puppet"), `card banner class changed: ${state.cardFxState.bannerClass}`);
  assert(state.cardFxState.title.includes("傀儡"), `card banner title changed: ${state.cardFxState.title}`);
  assert(state.cardFxState.desc.length > 0, "card banner description missing");
  assert(state.cardFxState.particles === 14 && state.cardFxState.rings === 1, `card particles changed: ${JSON.stringify(state.cardFxState)}`);
  assert(state.godHandState.flashes === 1, `god hand flash did not spawn: ${state.godHandState.flashes}`);
  assert(state.fogState.veils === 1 && state.fogState.clouds === 3, `fog effect changed: ${JSON.stringify(state.fogState)}`);
  assert(state.starState.pulses >= 5 && state.starState.links >= 4, `star constellation changed: ${JSON.stringify(state.starState)}`);
  assert(state.fiveState.lines === 3, `five-in-row burst changed: ${state.fiveState.lines}`);
  assert(state.lastStandState.pulses === 1, `last stand pulse changed: ${state.lastStandState.pulses}`);
  assert(state.signatureState.flashes === 1 && state.signatureState.fiveLines === 3, `signature effect dispatch changed: ${JSON.stringify(state.signatureState)}`);
  assert(errors.length === 0, `browser errors: ${errors.join("; ")}`);

  console.log(JSON.stringify({
    ok: true,
    animations: state.animationQueuedState.count,
    particles: state.cardFxState.particles,
    sparks: state.sparkState.count,
  }, null, 2));
} finally {
  await browser.close();
}
