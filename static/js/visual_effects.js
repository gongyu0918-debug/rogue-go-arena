// Sound, board animations, and card-effect visuals for the legacy frontend.

let animations = []; // { type, x, y, startTime, duration, data }
let animFrameId = null;
let boardIntroPlayed = false;
let boardIntroTimer = null;

let soundEnabled = true;
let audioCtx = null;

const FX_LIMITS = Object.freeze({ boardAnimations: 32, layerElements: 48, captureTrails: 8, cardParticles: 12 });
const fxCleanupTimers = new Map();
const reducedMotionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
const CARD_EFFECT_MOTIONS = {
  puppet: "orbit", exchange: "orbit", mirror: "orbit",
  twin: "surge", god_hand: "surge", sanrensei: "surge", five_in_row: "surge",
  seal: "ward", corner_helper: "ward",
};

function visualMotionEnabled() {
  return !document.hidden && !reducedMotionQuery.matches;
}

function removeVisualEffect(node) {
  clearTimeout(fxCleanupTimers.get(node));
  fxCleanupTimers.delete(node);
  node.remove();
}

function mountVisualEffect(layer, node, duration) {
  while (layer.children.length >= FX_LIMITS.layerElements) removeVisualEffect(layer.firstElementChild);
  layer.appendChild(node);
  fxCleanupTimers.set(node, setTimeout(() => removeVisualEffect(node), duration));
  return node;
}

function clearVisualEffects({ keepBanner = false } = {}) {
  animations = [];
  if (animFrameId !== null) cancelAnimationFrame(animFrameId);
  animFrameId = null;
  clearTimeout(boardIntroTimer);
  boardIntroTimer = null;
  for (const node of fxCleanupTimers.keys()) {
    if (!keepBanner || !node.classList.contains("fx-banner")) removeVisualEffect(node);
  }
  document.getElementById("board-container")?.classList.remove("board-intro");
  // Clearing a capture must also erase its last painted frame.
  if (typeof render === "function" && typeof boardRenderSize !== "undefined" && boardRenderSize) render();
}

function boardEffectPoint(x, y, layer) {
  const boardCanvas = document.getElementById("board-canvas");
  if (!boardCanvas || !layer) return null;
  const boardRect = boardCanvas.getBoundingClientRect();
  const layerRect = layer.getBoundingClientRect();
  const logicalSize = boardRenderSize || boardRect.width;
  if (!logicalSize || !boardRect.width) return null;
  return {
    x: boardRect.left - layerRect.left + (PAD + x * CELL) * boardRect.width / logicalSize,
    y: boardRect.top - layerRect.top + (PAD + y * CELL) * boardRect.height / logicalSize,
    cell: CELL * boardRect.width / logicalSize,
  };
}

function placeBoardEffect(node, point) {
  node.style.left = `${point.x}px`;
  node.style.top = `${point.y}px`;
}

function spawnStoneImpact(x, y, color = null) {
  const layer = document.getElementById("board-fx-layer");
  const point = boardEffectPoint(x, y, layer);
  if (!point) return;
  const impact = document.createElement("span");
  impact.className = color ? "fx-stone-impact fx-capture-impact" : "fx-stone-impact fx-place-impact";
  placeBoardEffect(impact, point);
  impact.style.setProperty("--stone-size", `${point.cell * .92}px`);
  if (color) {
    impact.style.setProperty("--stone-dust", color === "B" ? "rgba(48,32,20,.8)" : "rgba(255,246,220,.92)");
    for (let i = 0; i < 3; i++) {
      const fleck = document.createElement("i");
      const angle = (i * 2 * Math.PI / 3) + (x + y) * .7;
      fleck.style.setProperty("--dust-x", `${Math.cos(angle) * point.cell * .8}px`);
      fleck.style.setProperty("--dust-y", `${Math.sin(angle) * point.cell * .8 - point.cell * .3}px`);
      impact.appendChild(fleck);
    }
  }
  mountVisualEffect(layer, impact, color ? 600 : 440);
}

function queueBoardAnimation(animation) {
  const now = performance.now();
  animations = animations.filter(item => now - item.startTime < item.duration &&
    !(item.type === animation.type && item.x === animation.x && item.y === animation.y));
  animations.push({ ...animation, startTime: now });
  if (animations.length > FX_LIMITS.boardAnimations) animations.splice(0, animations.length - FX_LIMITS.boardAnimations);
}

const CARD_EFFECT_THEME_RULES = [
  { key: "puppet", match: /傀儡|Puppet/i, title: () => ui("傀儡术发动", "Puppet unleashed"), icon: "🎭", cls: "fx-puppet fx-rogue" },
  { key: "twin", match: /连击|双子星辰|Combo/i, title: () => ui("连击加速", "Combo surge"), icon: "⚡", cls: "fx-twin fx-rogue" },
  { key: "exchange", match: /乾坤挪移|Swap Turn/i, title: () => ui("回合窃取", "Turn stolen"), icon: "🔄", cls: "fx-exchange fx-rogue" },
  { key: "fog", match: /迷雾|战争迷雾|Fog/i, title: () => ui("战争迷雾刷新", "Fog of War"), icon: "🌫", cls: "fx-fog fx-rogue" },
  { key: "seal", match: /封印|Seal/i, title: () => ui("封印术成型", "Seal locked in"), icon: "🚫", cls: "fx-seal fx-rogue" },
  { key: "god_hand", match: /神之一手|Hand of God/i, title: () => ui("神之一手", "Hand of God"), icon: "✨", cls: "fx-god_hand fx-rogue" },
  { key: "sanrensei", match: /三连星|Star/i, title: () => ui("星位共鸣", "Star ignition"), icon: "✦", cls: "fx-sanrensei fx-rogue" },
  { key: "corner_helper", match: /守角|Corner/i, title: () => ui("角部强化", "Corner fortified"), icon: "🏯", cls: "fx-corner_helper fx-rogue" },
  { key: "foolish_wisdom", match: /大智若愚|愚形|Wise Fool|Fool/i, title: () => ui("愚形连锁", "Ugly shape chain"), icon: "🪤", cls: "fx-foolish_wisdom fx-rogue" },
  { key: "five_in_row", match: /五子连珠|Five in a Row/i, title: () => ui("五子连珠", "Five in a Row"), icon: "🎯", cls: "fx-five_in_row fx-rogue" },
  { key: "last_stand", match: /起死回生|Last Stand/i, title: () => ui("起死回生", "Last Stand"), icon: "🫀", cls: "fx-last_stand fx-rogue" },
  { key: "mirror", match: /镜像|Mirror/i, title: () => ui("镜像偏折", "Mirror pulse"), icon: "🪞", cls: "fx-mirror fx-rogue" },
  { key: "slip", match: /手滑|Butter/i, title: () => ui("手滑偏移", "Butterfingers"), icon: "🍃", cls: "fx-slip fx-rogue" },
];

const DEFAULT_CARD_EFFECT_THEME = {
  key: "rogue",
  title: () => ui("Rogue 规则生效", "Rogue effect"),
  icon: "🃏",
  cls: "fx-rogue",
};

const CARD_EFFECT_PARTICLE_PALETTES = {
  puppet: ["rgba(196,170,255,.95)", "rgba(112,78,255,.85)"],
  twin: ["rgba(255,231,133,.95)", "rgba(255,183,39,.85)"],
  exchange: ["rgba(119,240,230,.92)", "rgba(57,188,180,.82)"],
  fog: ["rgba(205,220,235,.7)", "rgba(132,155,186,.7)"],
  god_hand: ["rgba(255,239,157,.98)", "rgba(255,186,88,.88)"],
  sanrensei: ["rgba(163,205,255,.95)", "rgba(88,153,255,.84)"],
  corner_helper: ["rgba(143,228,182,.92)", "rgba(53,176,125,.84)"],
  foolish_wisdom: ["rgba(210,235,121,.95)", "rgba(160,193,62,.85)"],
  mirror: ["rgba(185,238,255,.95)", "rgba(97,188,255,.85)"],
  slip: ["rgba(255,198,129,.95)", "rgba(255,147,74,.82)"],
  seal: ["rgba(255,154,169,.92)", "rgba(255,99,122,.82)"],
  rogue: ["rgba(255,228,151,.95)", "rgba(212,175,55,.82)"],
};

function resolveCardEffectTheme(rule) {
  return { ...rule, title: rule.title() };
}

function getAudioCtx() {
  if (!audioCtx) {
    const AC = window.AudioContext || window.webkitAudioContext;
    if (AC) audioCtx = new AC();
  }
  return audioCtx;
}

function playStoneSound() {
  if (!soundEnabled) return;
  const ctx = getAudioCtx();
  if (!ctx) return;
  try {
    const dur = 0.07;
    const buf = ctx.createBuffer(1, Math.ceil(ctx.sampleRate * dur), ctx.sampleRate);
    const data = buf.getChannelData(0);
    for (let i = 0; i < data.length; i++) {
      data[i] = (Math.random() * 2 - 1) * Math.exp(-i / (ctx.sampleRate * 0.012));
    }
    const src = ctx.createBufferSource();
    src.buffer = buf;
    const bp = ctx.createBiquadFilter();
    bp.type = "bandpass";
    bp.frequency.value = 3200;
    bp.Q.value = 2.5;
    const gain = ctx.createGain();
    gain.gain.setValueAtTime(0.6, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + dur);
    src.connect(bp).connect(gain).connect(ctx.destination);
    src.start();
    src.stop(ctx.currentTime + dur);
  } catch (_) {}
}

function playCaptureSound(count) {
  if (!soundEnabled || count === 0) return;
  const ctx = getAudioCtx();
  if (!ctx) return;
  try {
    const n = Math.min(count, 6);
    for (let i = 0; i < n; i++) {
      setTimeout(() => {
        const dur = 0.05;
        const buf = ctx.createBuffer(1, Math.ceil(ctx.sampleRate * dur), ctx.sampleRate);
        const d = buf.getChannelData(0);
        for (let j = 0; j < d.length; j++) {
          d[j] = (Math.random() * 2 - 1) * Math.exp(-j / (ctx.sampleRate * 0.008));
        }
        const src = ctx.createBufferSource();
        src.buffer = buf;
        const bp = ctx.createBiquadFilter();
        bp.type = "bandpass";
        bp.frequency.value = 1800 + i * 200;
        bp.Q.value = 1.5;
        const gain = ctx.createGain();
        gain.gain.setValueAtTime(0.3, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + dur);
        src.connect(bp).connect(gain).connect(ctx.destination);
        src.start();
        src.stop(ctx.currentTime + dur);
      }, i * 50);
    }
  } catch (_) {}
}

function playTimerWarningSound() {
  if (!soundEnabled) return;
  const ctx = getAudioCtx();
  if (!ctx) return;
  try {
    const osc = ctx.createOscillator();
    osc.type = "sine";
    osc.frequency.value = 880;
    const gain = ctx.createGain();
    gain.gain.setValueAtTime(0.15, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.15);
    osc.connect(gain).connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + 0.15);
  } catch (_) {}
}

function addPlaceAnimation(x, y) {
  if (!visualMotionEnabled()) return;
  queueBoardAnimation({
    type: "place",
    x, y,
    duration: 180,
  });
  spawnStoneImpact(x, y);
  startAnimLoop();
}

function addCaptureAnimation(stones) {
  if (!visualMotionEnabled() || !Array.isArray(stones) || stones.length === 0) return;
  for (const [index, [x, y, color]] of stones.slice(-FX_LIMITS.boardAnimations).entries()) {
    queueBoardAnimation({
      type: "capture",
      x, y, color,
      duration: 320,
    });
    if (index < FX_LIMITS.captureTrails) spawnStoneImpact(x, y, color);
  }
  startAnimLoop();
}

function triggerBoardIntro() {
  const container = document.getElementById("board-container");
  if (!container) return;
  boardIntroPlayed = true;
  if (!visualMotionEnabled()) return;
  clearTimeout(boardIntroTimer);
  container.classList.remove("board-intro");
  void container.offsetWidth;
  container.classList.add("board-intro");
  boardIntroTimer = setTimeout(() => {
    container.classList.remove("board-intro");
    boardIntroTimer = null;
  }, 1200);
}

function attachButtonRipples() {
  document.querySelectorAll("button").forEach((btn) => {
    if (btn.dataset.rippleBound === "1") return;
    btn.dataset.rippleBound = "1";
    btn.addEventListener("pointerdown", (e) => {
      if (btn.disabled || !visualMotionEnabled()) return;
      btn.querySelectorAll(".btn-ripple").forEach(removeVisualEffect);
      const rect = btn.getBoundingClientRect();
      const ripple = document.createElement("span");
      ripple.className = "btn-ripple";
      ripple.style.setProperty("--x", `${e.clientX - rect.left}px`);
      ripple.style.setProperty("--y", `${e.clientY - rect.top}px`);
      mountVisualEffect(btn, ripple, 560);
    });
  });
}

function spawnOverlaySparks(kind) {
  const layer = document.getElementById("overlay-sparks");
  if (!layer) return;
  Array.from(layer.children).forEach(removeVisualEffect);
  if (!visualMotionEnabled()) return;
  const colors = kind === "victory"
    ? ["rgba(255,220,120,.95)", "rgba(255,246,210,.92)", "rgba(255,174,66,.88)"]
    : kind === "defeat"
      ? ["rgba(255,120,120,.75)", "rgba(168,128,255,.6)", "rgba(255,255,255,.55)"]
      : ["rgba(151,205,255,.78)", "rgba(255,255,255,.72)", "rgba(202,227,255,.72)"];
  for (let i = 0; i < 16; i++) {
    const spark = document.createElement("span");
    spark.className = "overlay-spark";
    spark.style.setProperty("--tx", `${(Math.random() - 0.5) * 260}px`);
    spark.style.setProperty("--ty", `${(Math.random() - 0.5) * 180 + 30}px`);
    spark.style.setProperty("--rot", `${(Math.random() - 0.5) * 180}deg`);
    spark.style.setProperty("--spark-color", colors[i % colors.length]);
    spark.style.animationDelay = `${Math.random() * 140}ms`;
    mountVisualEffect(layer, spark, 1200);
  }
}

function inferEffectTheme(message) {
  const raw = String(message || "");
  const rule = CARD_EFFECT_THEME_RULES.find((item) => item.match.test(raw)) || DEFAULT_CARD_EFFECT_THEME;
  return resolveCardEffectTheme(rule);
}

function spawnCardParticles(layer, theme) {
  if (!visualMotionEnabled()) return;
  const point = boardEffectPoint((getCurrentSize() - 1) / 2, (getCurrentSize() - 1) / 2, layer);
  if (!point) return;
  const motion = CARD_EFFECT_MOTIONS[theme.key] || "drift";
  const colors = CARD_EFFECT_PARTICLE_PALETTES[theme.key] || CARD_EFFECT_PARTICLE_PALETTES.rogue;
  const burst = document.createElement("div");
  burst.className = `fx-card-burst fx-motion-${motion}`;
  burst.dataset.motion = motion;
  placeBoardEffect(burst, point);
  const radius = Math.min(104, Math.max(44, point.cell * 2.5));
  for (let i = 0; i < FX_LIMITS.cardParticles; i++) {
    const particle = document.createElement("span");
    particle.className = `fx-particle fx-particle--${motion}`;
    const angle = Math.PI * 2 * i / FX_LIMITS.cardParticles;
    const distance = radius * (.7 + (i % 3) * .15);
    const start = motion === "ward" ? distance : (motion === "orbit" ? distance * .6 : 8);
    const endAngle = motion === "orbit" ? angle + Math.PI * .55 : angle;
    const end = motion === "ward" ? distance * .35 : distance;
    particle.style.setProperty("--fx-start-x", `${Math.cos(angle) * start}px`);
    particle.style.setProperty("--fx-start-y", `${Math.sin(angle) * start}px`);
    particle.style.setProperty("--fx-mid-x", `${Math.cos(angle + (endAngle - angle) * .5) * distance}px`);
    particle.style.setProperty("--fx-mid-y", `${Math.sin(angle + (endAngle - angle) * .5) * distance}px`);
    particle.style.setProperty("--fx-x", `${Math.cos(endAngle) * end}px`);
    particle.style.setProperty("--fx-y", `${Math.sin(endAngle) * end + (motion === "drift" ? -24 : 0)}px`);
    particle.style.setProperty("--fx-angle", `${angle}rad`);
    particle.style.setProperty("--size", `${4 + i % 3}px`);
    particle.style.setProperty("--core", colors[i % colors.length]);
    particle.style.setProperty("--glow", colors[(i + 1) % colors.length]);
    particle.style.animationDelay = `${i % 3 * 35}ms`;
    burst.appendChild(particle);
  }
  const ring = document.createElement("span");
  ring.className = `fx-ring fx-ring--${motion}`;
  ring.style.setProperty("--ring", colors[0]);
  ring.style.setProperty("--ring-size", `${radius * 1.35}px`);
  burst.appendChild(ring);
  mountVisualEffect(layer, burst, 1050);
}

function showCardEffectVisual(message, mode = "rogue") {
  const layer = document.getElementById("board-fx-layer");
  if (!layer || document.hidden) return;
  const theme = inferEffectTheme(message);
  const banner = document.createElement("div");
  banner.className = `fx-banner ${theme.cls} ${mode === "ultimate" ? "fx-ultimate" : "fx-rogue"}`;
  const inner = document.createElement("div");
  inner.className = "fx-banner-inner";
  const icon = document.createElement("div");
  icon.className = "fx-banner-icon";
  icon.textContent = theme.icon;
  const copy = document.createElement("div");
  copy.className = "fx-banner-copy";
  const title = document.createElement("div");
  title.className = "fx-banner-title";
  title.textContent = theme.title;
  const desc = document.createElement("div");
  desc.className = "fx-banner-desc";
  desc.textContent = translateServerEventMessage(message);
  copy.appendChild(title);
  if (desc.textContent !== title.textContent) copy.appendChild(desc);
  inner.append(icon, copy);
  banner.appendChild(inner);

  layer.querySelectorAll(".fx-banner, .fx-card-burst").forEach(removeVisualEffect);
  mountVisualEffect(layer, banner, 1900);
  spawnCardParticles(layer, theme);
}

function playGodHandFlash() {
  const layer = document.getElementById("global-fx-layer");
  if (!layer || !visualMotionEnabled()) return;
  layer.querySelectorAll(".fx-godflash").forEach(removeVisualEffect);
  const flash = document.createElement("div");
  flash.className = "fx-godflash";
  mountVisualEffect(layer, flash, 950);
}

function playFogFlowEffect(points) {
  const layer = document.getElementById("board-fx-layer");
  if (!layer || !visualMotionEnabled()) return;
  layer.querySelectorAll(".fx-fog-veil").forEach(removeVisualEffect);
  const veil = document.createElement("div");
  veil.className = "fx-fog-veil";
  const list = Array.isArray(points) && points.length ? points : rogueSeals;
  const uniquePoints = (list || []).slice(0, 9);
  uniquePoints.forEach(([sx, sy], idx) => {
    const point = boardEffectPoint(sx, sy, layer);
    if (!point) return;
    const cloud = document.createElement("span");
    cloud.className = "fx-fog-cloud";
    placeBoardEffect(cloud, point);
    cloud.style.animationDelay = `${idx * 45}ms`;
    veil.appendChild(cloud);
  });
  const grid = document.createElement("span");
  grid.className = "fx-fog-grid";
  veil.appendChild(grid);
  mountVisualEffect(layer, veil, 1900);
}

function playSanrenseiConstellation(isUltimate = false) {
  const layer = document.getElementById("board-fx-layer");
  if (!layer || !visualMotionEnabled()) return;
  layer.querySelectorAll(".fx-star-pulse, .fx-star-link").forEach(removeVisualEffect);
  const stars = getStarPoints(getCurrentSize());
  const chosen = isUltimate ? stars : stars.slice(0, Math.min(5, stars.length));
  chosen.forEach(([sx, sy], idx) => {
    const point = boardEffectPoint(sx, sy, layer);
    if (!point) return;
    const pulse = document.createElement("span");
    pulse.className = "fx-star-pulse";
    placeBoardEffect(pulse, point);
    pulse.style.animationDelay = `${idx * 70}ms`;
    mountVisualEffect(layer, pulse, 1100 + idx * 70);
  });
  for (let i = 0; i < chosen.length - 1; i++) {
    const [x1, y1] = chosen[i];
    const [x2, y2] = chosen[i + 1];
    const from = boardEffectPoint(x1, y1, layer);
    const to = boardEffectPoint(x2, y2, layer);
    if (!from || !to) continue;
    const link = document.createElement("span");
    link.className = "fx-star-link";
    placeBoardEffect(link, from);
    const dx = to.x - from.x;
    const dy = to.y - from.y;
    link.style.width = `${Math.hypot(dx, dy)}px`;
    link.style.setProperty("--link-angle", `${Math.atan2(dy, dx)}rad`);
    link.style.animationDelay = `${i * 90}ms`;
    mountVisualEffect(layer, link, 1200 + i * 90);
  }
}

function playFiveInRowBurst() {
  const layer = document.getElementById("board-fx-layer");
  if (!layer || !visualMotionEnabled()) return;
  layer.querySelectorAll(".fx-five-line").forEach(removeVisualEffect);
  [0, 45, -45].forEach((deg, idx) => {
    const line = document.createElement("span");
    line.className = "fx-five-line";
    line.style.setProperty("--line-angle", `${deg}deg`);
    line.style.animationDelay = `${idx * 70}ms`;
    mountVisualEffect(layer, line, 1100 + idx * 70);
  });
}

function playLastStandPulse() {
  const layer = document.getElementById("board-fx-layer");
  if (!layer || !visualMotionEnabled()) return;
  layer.querySelectorAll(".fx-last-stand-pulse").forEach(removeVisualEffect);
  const pulse = document.createElement("span");
  pulse.className = "fx-last-stand-pulse";
  mountVisualEffect(layer, pulse, 1260);
}

function triggerSignatureCardEffect(message) {
  const raw = String(message || "");
  if (/神之一手|Hand of God/i.test(raw)) {
    playGodHandFlash();
  }
  if (/战争迷雾刷新|Fog refreshed|Fog of War/i.test(raw)) {
    playFogFlowEffect(rogueSeals);
  }
  if (/三连星发动|Three-Star Formation triggered/i.test(raw)) {
    playSanrenseiConstellation(false);
  }
  if (/三连星爆发|Star Ignition burst/i.test(raw)) {
    playSanrenseiConstellation(true);
  }
  if (/五子连珠|Five in a Row/i.test(raw)) {
    playFiveInRowBurst();
  }
  if (/起死回生|Last Stand/i.test(raw)) {
    playLastStandPulse();
  }
}

function startAnimLoop() {
  if (animFrameId !== null || !visualMotionEnabled() || animations.length === 0) return;
  function loop() {
    if (!visualMotionEnabled()) {
      clearVisualEffects({ keepBanner: true });
      return;
    }
    const now = performance.now();
    animations = animations.filter(a => now - a.startTime < a.duration);
    render();
    if (animations.length > 0) {
      animFrameId = requestAnimationFrame(loop);
    } else {
      animFrameId = null;
    }
  }
  animFrameId = requestAnimationFrame(loop);
}

window.getAudioCtx = getAudioCtx;
window.playStoneSound = playStoneSound;
window.playCaptureSound = playCaptureSound;
window.playTimerWarningSound = playTimerWarningSound;
window.addPlaceAnimation = addPlaceAnimation;
window.addCaptureAnimation = addCaptureAnimation;
window.triggerBoardIntro = triggerBoardIntro;
window.attachButtonRipples = attachButtonRipples;
window.spawnOverlaySparks = spawnOverlaySparks;
window.inferEffectTheme = inferEffectTheme;
window.showCardEffectVisual = showCardEffectVisual;
window.playGodHandFlash = playGodHandFlash;
window.playFogFlowEffect = playFogFlowEffect;
window.playSanrenseiConstellation = playSanrenseiConstellation;
window.playFiveInRowBurst = playFiveInRowBurst;
window.playLastStandPulse = playLastStandPulse;
window.triggerSignatureCardEffect = triggerSignatureCardEffect;
window.startAnimLoop = startAnimLoop;
window.clearVisualEffects = clearVisualEffects;

reducedMotionQuery.addEventListener("change", () => clearVisualEffects({ keepBanner: true }));
document.addEventListener("visibilitychange", () => { if (document.hidden) clearVisualEffects(); });
window.addEventListener("pagehide", () => clearVisualEffects());
window.addEventListener("resize", () => clearVisualEffects());
