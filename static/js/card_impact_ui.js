// Card impact popup (win-rate swing after a player card fires) and card evolution meter.

const CARD_IMPACT_POPUP_MS = 2600;
const CARD_EVOLVED_POPUP_MS = 3200;
const narrowEffectsQuery = window.matchMedia("(max-width: 980px)");

function formatSignedPercent(delta) {
  const pct = Math.round(delta * 1000) / 10;
  if (pct === 0) return "±0%";
  return `${pct > 0 ? "+" : "−"}${Math.abs(pct)}%`;
}

function formatSignedPoints(delta) {
  const rounded = Math.round(delta * 10) / 10;
  return `${rounded > 0 ? "+" : rounded < 0 ? "−" : "±"}${Math.abs(rounded)}`;
}

function cardImpactTone(msg) {
  if (!msg.measured) return "neutral";
  if (msg.winrate_delta >= 0.005) return "gain";
  if (msg.winrate_delta <= -0.005) return "loss";
  return "neutral";
}

function cardImpactDetails(msg) {
  const parts = [];
  if (msg.stones_gained > 0) parts.push(`${ui("己方棋子", "Your stones")} +${msg.stones_gained}`);
  if (msg.enemy_stones_lost > 0) parts.push(`${ui("对方棋子", "Enemy stones")} −${msg.enemy_stones_lost}`);
  if (msg.komi_gain) parts.push(`${ui("贴目", "Komi")} ${formatSignedPoints(msg.komi_gain)}`);
  if (msg.measured) parts.push(`${ui("目差", "Lead")} ${formatSignedPoints(msg.lead_delta)}`);
  return parts.join(" · ");
}

function evolutionPips(evolution) {
  if (!evolution) return "";
  if (evolution.next == null) return "MAX";
  const floor = evolution.floor || 0;
  const total = Math.max(1, evolution.next - floor);
  const filled = Math.max(0, Math.min(total, evolution.charge - floor));
  return "◆".repeat(filled) + "◇".repeat(total - filled);
}

function evolutionLabel(evolution) {
  if (!evolution) return "";
  return `Lv${evolution.level} ${evolutionPips(evolution)}`;
}

function buildCardImpactPopup(msg) {
  const tone = cardImpactTone(msg);
  const popup = document.createElement("div");
  popup.className = `fx-impact fx-impact--${tone}`;
  popup.setAttribute("role", "status");

  const title = document.createElement("div");
  title.className = "fx-impact-title";
  const name = msg.card_id ? getRogueCardName(msg.card_id) : ui("卡牌", "Card");
  title.textContent = `${name} · ${ui("局势影响", "Game impact")}`;

  const swing = document.createElement("div");
  swing.className = "fx-impact-swing";
  swing.textContent = msg.measured ? formatSignedPercent(msg.winrate_delta) : ui("触发！", "Triggered!");

  popup.append(title, swing);
  if (msg.measured) {
    const range = document.createElement("div");
    range.className = "fx-impact-range";
    const before = Math.round(msg.winrate_before * 100);
    const after = Math.round(msg.winrate_after * 100);
    range.textContent = `${ui("胜率", "Win rate")} ${before}% → ${after}%`;
    const meter = document.createElement("div");
    meter.className = "fx-impact-meter";
    const fill = document.createElement("div");
    fill.className = "fx-impact-meter-fill";
    fill.style.setProperty("--from", `${before}%`);
    fill.style.setProperty("--to", `${after}%`);
    meter.appendChild(fill);
    popup.append(range, meter);
  }
  const details = cardImpactDetails(msg);
  if (details) {
    const line = document.createElement("div");
    line.className = "fx-impact-details";
    line.textContent = details;
    popup.appendChild(line);
  }
  const echoCount = (msg.echo_points || []).length;
  if (echoCount || msg.echo_komi) {
    const echo = document.createElement("div");
    echo.className = "fx-impact-echo";
    echo.textContent = echoCount
      ? `${ui("进化回响", "Evolution echo")} +${echoCount}`
      : `${ui("进化回响", "Evolution echo")} ${ui("贴目", "Komi")} ${formatSignedPoints(msg.echo_komi)}`;
    popup.appendChild(echo);
  }
  return popup;
}

function showCardImpact(msg) {
  if (gameState && msg.evolution) gameState.rogue_evolution = msg.evolution;
  syncClientShell();
  const layer = document.getElementById("board-fx-layer");
  if (layer && !document.hidden) {
    layer.querySelectorAll(".fx-impact").forEach(removeVisualEffect);
    // Narrow layouts centre both the card banner and this popup at the top; the popup names the card, so it takes over.
    if (narrowEffectsQuery.matches) layer.querySelectorAll(".fx-banner").forEach(removeVisualEffect);
    mountVisualEffect(layer, buildCardImpactPopup(msg), CARD_IMPACT_POPUP_MS);
    for (const [x, y] of msg.echo_points || []) spawnStoneImpact(x, y, gameState?.player_color);
  }
  const summary = msg.measured
    ? `${formatSignedPercent(msg.winrate_delta)} (${Math.round(msg.winrate_before * 100)}% → ${Math.round(msg.winrate_after * 100)}%)`
    : cardImpactDetails(msg);
  log(`📈 ${ui("卡牌影响", "Card impact")}: ${summary}`);
}

function showCardEvolved(msg) {
  if (gameState) {
    const { level, charge, floor, next, max_level } = msg;
    gameState.rogue_evolution = { level, charge, floor, next, max_level };
  }
  syncClientShell();
  const name = msg.card_id ? getRogueCardName(msg.card_id) : ui("卡牌", "Card");
  const ascended = msg.level >= msg.max_level;
  const twin = ascended && msg.ultimate_twin ? getUltimateCardName(msg.ultimate_twin) : "";
  const echoText = `${ui("之后每次触发额外回响", "Each trigger now echoes")} +${msg.level - 1}`;
  const layer = document.getElementById("board-fx-layer");
  if (layer && !document.hidden) {
    const popup = document.createElement("div");
    popup.className = `fx-evolved${ascended ? " fx-evolved--max" : ""}`;
    popup.setAttribute("role", "status");
    const badge = document.createElement("div");
    badge.className = "fx-evolved-badge";
    badge.textContent = `Lv${msg.level}`;
    const title = document.createElement("div");
    title.className = "fx-evolved-title";
    title.textContent = ascended ? `${name} · ${ui("觉醒！", "Ascended!")}` : `${name} · ${ui("进化！", "Evolved!")}`;
    const desc = document.createElement("div");
    desc.className = "fx-evolved-desc";
    desc.textContent = twin ? `${echoText} · ${ui("大招之影", "Echo of")} ${twin}` : echoText;
    popup.append(badge, title, desc);
    layer.querySelectorAll(".fx-evolved").forEach(removeVisualEffect);
    mountVisualEffect(layer, popup, CARD_EVOLVED_POPUP_MS);
    if (typeof spawnOverlaySparks === "function" && visualMotionEnabled()) spawnOverlaySparks("rogue");
  }
  log(`✨ ${name} Lv${msg.level} — ${echoText}`);
}

window.evolutionLabel = evolutionLabel;
window.showCardImpact = showCardImpact;
window.showCardEvolved = showCardEvolved;
