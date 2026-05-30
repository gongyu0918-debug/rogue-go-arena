// Sound, board animations, and card-effect visuals for the legacy frontend.

let animations = []; // { type, x, y, startTime, duration, data }
let animFrameId = null;
let boardIntroPlayed = false;
let fxBannerTimer = null;

let soundEnabled = true;
let audioCtx = null;

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
  animations.push({
    type: "place",
    x, y,
    startTime: performance.now(),
    duration: 180,
  });
  startAnimLoop();
}

function addCaptureAnimation(stones) {
  if (!stones || stones.length === 0) return;
  for (const [x, y, color] of stones) {
    animations.push({
      type: "capture",
      x, y, color,
      startTime: performance.now(),
      duration: 300,
    });
  }
  startAnimLoop();
}

function triggerBoardIntro() {
  const container = document.getElementById("board-container");
  if (!container) return;
  container.classList.remove("board-intro");
  void container.offsetWidth;
  container.classList.add("board-intro");
  boardIntroPlayed = true;
  setTimeout(() => container.classList.remove("board-intro"), 1200);
}

function attachButtonRipples() {
  document.querySelectorAll("button").forEach((btn) => {
    if (btn.dataset.rippleBound === "1") return;
    btn.dataset.rippleBound = "1";
    btn.addEventListener("pointerdown", (e) => {
      if (btn.disabled) return;
      const rect = btn.getBoundingClientRect();
      const ripple = document.createElement("span");
      ripple.className = "btn-ripple";
      ripple.style.setProperty("--x", `${e.clientX - rect.left}px`);
      ripple.style.setProperty("--y", `${e.clientY - rect.top}px`);
      btn.appendChild(ripple);
      setTimeout(() => ripple.remove(), 560);
    });
  });
}

function spawnOverlaySparks(kind) {
  const layer = document.getElementById("overlay-sparks");
  if (!layer) return;
  layer.innerHTML = "";
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
    layer.appendChild(spark);
  }
  setTimeout(() => { if (layer) layer.innerHTML = ""; }, 1200);
}

function inferEffectTheme(message) {
  const raw = String(message || "");
  const rule = CARD_EFFECT_THEME_RULES.find((item) => item.match.test(raw)) || DEFAULT_CARD_EFFECT_THEME;
  return resolveCardEffectTheme(rule);
}

function showCardEffectVisual(message, mode = "rogue") {
  const layer = document.getElementById("board-fx-layer");
  if (!layer) return;
  const theme = inferEffectTheme(message);
  const banner = document.createElement("div");
  banner.className = `fx-banner ${theme.cls} ${mode === "ultimate" ? "fx-ultimate" : "fx-rogue"}`;
  banner.innerHTML = `
    <div class="fx-banner-inner">
      <div class="fx-banner-icon">${theme.icon}</div>
      <div class="fx-banner-copy">
        <div class="fx-banner-title">${theme.title}</div>
        <div class="fx-banner-desc">${translateServerEventMessage(message)}</div>
      </div>
    </div>`;

  clearTimeout(fxBannerTimer);
  layer.innerHTML = "";
  layer.appendChild(banner);

  const colors = CARD_EFFECT_PARTICLE_PALETTES[theme.key] || CARD_EFFECT_PARTICLE_PALETTES.rogue;
  for (let i = 0; i < 14; i++) {
    const p = document.createElement("span");
    p.className = "fx-particle";
    const angle = (Math.PI * 2 * i) / 14;
    const dist = 70 + Math.random() * 90;
    p.style.setProperty("--fx-x", `${Math.cos(angle) * dist}px`);
    p.style.setProperty("--fx-y", `${Math.sin(angle) * dist}px`);
    p.style.setProperty("--size", `${10 + Math.random() * 14}px`);
    p.style.setProperty("--core", colors[i % colors.length]);
    p.style.setProperty("--glow", colors[(i + 1) % colors.length]);
    p.style.animationDelay = `${Math.random() * 80}ms`;
    layer.appendChild(p);
  }
  const ring = document.createElement("span");
  ring.className = "fx-ring";
  ring.style.setProperty("--ring", colors[0]);
  layer.appendChild(ring);

  fxBannerTimer = setTimeout(() => {
    layer.innerHTML = "";
  }, 1900);
}

function playGodHandFlash() {
  const layer = document.getElementById("global-fx-layer");
  if (!layer) return;
  const flash = document.createElement("div");
  flash.className = "fx-godflash";
  layer.appendChild(flash);
  setTimeout(() => flash.remove(), 1400);
}

function playFogFlowEffect(points) {
  const layer = document.getElementById("board-fx-layer");
  if (!layer) return;
  const veil = document.createElement("div");
  veil.className = "fx-fog-veil";
  const list = Array.isArray(points) && points.length ? points : rogueSeals;
  const uniquePoints = (list || []).slice(0, 9);
  uniquePoints.forEach(([sx, sy], idx) => {
    const cx = PAD + sx * CELL;
    const cy = PAD + sy * CELL;
    const cloud = document.createElement("span");
    cloud.className = "fx-fog-cloud";
    cloud.style.left = `${cx - 90}px`;
    cloud.style.top = `${cy - 90}px`;
    cloud.style.animationDelay = `${idx * 45}ms`;
    veil.appendChild(cloud);
  });
  const grid = document.createElement("span");
  grid.className = "fx-fog-grid";
  veil.appendChild(grid);
  layer.appendChild(veil);
  setTimeout(() => veil.remove(), 1900);
}

function playSanrenseiConstellation(isUltimate = false) {
  const layer = document.getElementById("board-fx-layer");
  if (!layer) return;
  const stars = getStarPoints(getCurrentSize());
  const chosen = isUltimate ? stars : stars.slice(0, Math.min(5, stars.length));
  chosen.forEach(([sx, sy], idx) => {
    const pulse = document.createElement("span");
    pulse.className = "fx-star-pulse";
    pulse.style.left = `${PAD + sx * CELL}px`;
    pulse.style.top = `${PAD + sy * CELL}px`;
    pulse.style.animationDelay = `${idx * 70}ms`;
    layer.appendChild(pulse);
    setTimeout(() => pulse.remove(), 1100 + idx * 70);
  });
  for (let i = 0; i < chosen.length - 1; i++) {
    const [x1, y1] = chosen[i];
    const [x2, y2] = chosen[i + 1];
    const px1 = PAD + x1 * CELL;
    const py1 = PAD + y1 * CELL;
    const px2 = PAD + x2 * CELL;
    const py2 = PAD + y2 * CELL;
    const link = document.createElement("span");
    link.className = "fx-star-link";
    link.style.left = `${px1}px`;
    link.style.top = `${py1}px`;
    const dx = px2 - px1;
    const dy = py2 - py1;
    link.style.width = `${Math.hypot(dx, dy)}px`;
    link.style.transform = `translateY(-50%) rotate(${Math.atan2(dy, dx)}rad)`;
    link.style.animationDelay = `${i * 90}ms`;
    layer.appendChild(link);
    setTimeout(() => link.remove(), 1200 + i * 90);
  }
}

function playFiveInRowBurst() {
  const layer = document.getElementById("board-fx-layer");
  if (!layer) return;
  [0, 45, -45].forEach((deg, idx) => {
    const line = document.createElement("span");
    line.className = "fx-five-line";
    line.style.transform = `translate(-50%, -50%) rotate(${deg}deg)`;
    line.style.animationDelay = `${idx * 70}ms`;
    layer.appendChild(line);
    setTimeout(() => line.remove(), 1100 + idx * 70);
  });
}

function playLastStandPulse() {
  const layer = document.getElementById("board-fx-layer");
  if (!layer) return;
  const pulse = document.createElement("span");
  pulse.className = "fx-last-stand-pulse";
  layer.appendChild(pulse);
  setTimeout(() => pulse.remove(), 1260);
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
  if (animFrameId) return;
  function loop() {
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
