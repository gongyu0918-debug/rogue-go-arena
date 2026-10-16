// Card catalog presentation helpers.
// Runtime effects still come from the server and app/data/cards.json.

const ROGUE_CARD_IDS = [
  "tengen","dice","erosion","puppet","seal","twin","nerf","komi_relief","time_press","lowline",
  "suboptimal","mirror","slip","blackhole","exchange","fog","gravity","golden_corner","sansan","shadow",
  "sprout","joseki_ocd","handicap_quest","god_hand","sansan_trap","corner_helper","sanrensei","no_regret",
  "quickthink","foolish_wisdom","five_in_row","coach_mode","capture_foul","last_stand","defense_first",
  "attack_first","methodical","momentum","iron_wall","capture_chain",
];

const ULTIMATE_CARD_IDS = [
  "chain","proliferate","double","wildgrow","rejection","territory","shadow_clone","plague","meteor","quantum",
  "devour","timewarp","blackout","magnet","necro","wall","joseki_burst","god_hand","corner_helper",
  "sanrensei","quickthink","foolish_wisdom","five_in_row","capture_foul","last_stand",
];

const ROGUE_CARD_META = {
  puppet: { tier: "S", category: "主动", complexity: "高" },
  twin: { tier: "A", category: "主动", complexity: "中" },
  exchange: { tier: "A", category: "主动", complexity: "低" },
  coach_mode: { tier: "S", category: "主动", complexity: "中" },
  dice: { tier: "B+", category: "AI干扰", complexity: "低" },
  mirror: { tier: "B+", category: "AI干扰", complexity: "低" },
  slip: { tier: "B+", category: "AI干扰", complexity: "低" },
  god_hand: { tier: "A", category: "爆发", complexity: "中" },
  sansan_trap: { tier: "A", category: "陷阱", complexity: "中" },
  sanrensei: { tier: "A", category: "开局构筑", complexity: "中" },
  joseki_ocd: { tier: "A", category: "任务", complexity: "中" },
  no_regret: { tier: "B+", category: "风险收益", complexity: "低" },
  quickthink: { tier: "A", category: "节奏", complexity: "高" },
  five_in_row: { tier: "A", category: "连线构筑", complexity: "高" },
  defense_first: { tier: "A", category: "构筑", complexity: "中" },
  attack_first: { tier: "A", category: "构筑", complexity: "中" },
  methodical: { tier: "A", category: "节奏", complexity: "高" },
  momentum: { tier: "A", category: "连击", complexity: "低" },
  iron_wall: { tier: "A", category: "连击", complexity: "低" },
  capture_chain: { tier: "A", category: "连击", complexity: "中" },
};

const ULTIMATE_CARD_META = {
  chain: { tier: "S", category: "连动", complexity: "低" },
  double: { tier: "S", category: "连动", complexity: "低" },
  quickthink: { tier: "S", category: "节奏", complexity: "高" },
  joseki_burst: { tier: "S", category: "任务爆发", complexity: "中" },
  god_hand: { tier: "S", category: "爆发", complexity: "中" },
  five_in_row: { tier: "S", category: "连线构筑", complexity: "高" },
};

const CARD_ART_IDS = new Set([
  "tengen","dice","erosion","puppet","seal","twin","nerf","komi_relief","time_press","lowline",
  "suboptimal","mirror","slip","blackhole","exchange","fog","gravity","golden_corner","sansan","shadow",
  "sprout","joseki_ocd","handicap_quest","god_hand","sansan_trap","corner_helper","sanrensei","no_regret",
  "quickthink","foolish_wisdom","five_in_row","coach_mode","capture_foul","last_stand","defense_first",
  "attack_first","methodical","momentum","iron_wall","capture_chain","chain","proliferate",
  "double","wildgrow","rejection","territory","shadow_clone","plague","meteor","quantum","devour","timewarp",
  "blackout","magnet","necro","wall","joseki_burst",
]);

// One plain type per Rogue card; the only tag on the pick screen.
const ROGUE_CARD_KINDS = {
  gift: ["sprout","joseki_ocd","god_hand","sansan_trap","corner_helper","sanrensei","no_regret",
    "foolish_wisdom","five_in_row","capture_foul","last_stand","defense_first","attack_first"],
  combo: ["momentum","iron_wall","capture_chain"],
  active: ["puppet","twin","exchange","coach_mode"],
  hinder: ["tengen","dice","seal","nerf","time_press","lowline","suboptimal","mirror","slip",
    "blackhole","fog","gravity","golden_corner","sansan","shadow"],
  tempo: ["quickthink","methodical","handicap_quest"],
  komi: ["erosion","komi_relief"],
};
const ROGUE_KIND_BY_ID = Object.fromEntries(
  Object.entries(ROGUE_CARD_KINDS).flatMap(([kind, ids]) => ids.map(id => [id, kind]))
);
const CARD_KIND_LABELS = {
  gift: ["白送棋子", "Free stones"],
  combo: ["连击", "Combo"],
  active: ["主动技能", "Active skill"],
  hinder: ["干扰 AI", "Hinders the AI"],
  tempo: ["节奏", "Tempo"],
  komi: ["贴目", "Komi"],
};
const CARD_ART_VERSION = "20261012a";

function getCardKindMarkup(card, mode) {
  const kind = mode === "rogue" ? ROGUE_KIND_BY_ID[card.id] : null;
  if (!kind) return "";
  const [zh, en] = CARD_KIND_LABELS[kind];
  return `<span class="card-kind kind-${kind}">${escapeHtml(ui(zh, en))}</span>`;
}

function getCardMeta(cardId, mode) {
  const active = activeLocalePack()?.cards?.[mode]?.[cardId];
  const fallback = fallbackLocalePack()?.cards?.[mode]?.[cardId];
  return active || fallback || { name: cardId, desc: "" };
}

function getTranslatedCard(card, mode) {
  const localeCode = { zh: "zh-CN", zht: "zh-TW", en: "en-US", ja: "ja-JP", ko: "ko-KR", fr: "fr-FR", de: "de-DE" }[currentLang] || "zh-CN";
  const meta = getCardMeta(card.id, mode);
  if (card?.i18n) {
    const name = card.i18n.name?.[localeCode] || card.i18n.name?.["zh-CN"] || card.name;
    const desc = card.i18n.desc?.[localeCode] || card.i18n.desc?.["zh-CN"] || card.desc;
    const summary = card.i18n.summary?.[localeCode] || meta?.summary || card.i18n.summary?.["zh-CN"] || "";
    return { ...card, name, desc, summary };
  }
  if (!meta) return card;
  return { ...card, name: meta.name, desc: meta.desc, summary: meta.summary || "" };
}

function localizeCardMetaValue(value) {
  if (!value) return "";
  return activeLocalePack()?.cardMeta?.[value]
    || fallbackLocalePack()?.cardMeta?.[value]
    || value;
}

function inferCardMeta(card, mode) {
  const defaults = mode === "ultimate"
    ? { tier: "S", category: "大招", complexity: "中" }
    : { tier: "B", category: "规则改写", complexity: "中" };
  const localMeta = mode === "ultimate" ? ULTIMATE_CARD_META[card.id] : ROGUE_CARD_META[card.id];
  return { ...defaults, ...(localMeta || {}), ...(card.meta || {}) };
}

function getCardMetaMarkup(card, mode) {
  const meta = inferCardMeta(card, mode);
  return `<div class="card-meta-row">
    <span class="card-tag tier">${escapeHtml(ui("强度", "Tier", "強さ", "강도"))} ${escapeHtml(meta.tier)}</span>
    <span class="card-tag">${escapeHtml(localizeCardMetaValue(meta.category))}</span>
    <span class="card-tag complexity">${escapeHtml(ui("理解", "Read", "理解", "이해"))} ${escapeHtml(localizeCardMetaValue(meta.complexity))}</span>
  </div>`;
}

function getCardIconMarkup(card) {
  if (CARD_ART_IDS.has(card.id)) {
    return `<div class="rc-icon rc-icon-art" style="background-image:url('assets/icons/cards-medal/${encodeURIComponent(card.id)}.png?v=${CARD_ART_VERSION}')"></div>`;
  }
  return `<div class="rc-icon">${escapeHtml(card.icon)}</div>`;
}

function getRogueCardName(cardId) {
  return getCardMeta(cardId, "rogue").name;
}

function getUltimateCardName(cardId) {
  return getCardMeta(cardId, "ultimate").name;
}
