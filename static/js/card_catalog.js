// Card catalog presentation helpers.
// Runtime effects still come from the server and app/data/cards.json.

const ROGUE_CARD_IDS = [
  "tengen","dice","erosion","puppet","seal","twin","nerf","komi_relief","time_press","lowline",
  "suboptimal","mirror","slip","blackhole","exchange","fog","gravity","golden_corner","sansan","shadow",
  "sprout","joseki_ocd","handicap_quest","god_hand","sansan_trap","corner_helper","sanrensei","no_regret",
  "quickthink","foolish_wisdom","five_in_row","coach_mode","capture_foul","last_stand","defense_first",
  "attack_first","methodical",
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
  "attack_first","methodical","chain","proliferate",
  "double","wildgrow","rejection","territory","shadow_clone","plague","meteor","quantum","devour","timewarp",
  "blackout","magnet","necro","wall","joseki_burst",
]);

function getCardMeta(cardId, mode) {
  const active = activeLocalePack()?.cards?.[mode]?.[cardId];
  const fallback = fallbackLocalePack()?.cards?.[mode]?.[cardId];
  return active || fallback || { name: cardId, desc: "" };
}

function getTranslatedCard(card, mode) {
  const localeCode = { zh: "zh-CN", zht: "zh-TW", en: "en-US", ja: "ja-JP", ko: "ko-KR", fr: "fr-FR", de: "de-DE" }[currentLang] || "zh-CN";
  if (card?.i18n) {
    const name = card.i18n.name?.[localeCode] || card.i18n.name?.["zh-CN"] || card.name;
    const desc = card.i18n.desc?.[localeCode] || card.i18n.desc?.["zh-CN"] || card.desc;
    return { ...card, name, desc };
  }
  const meta = getCardMeta(card.id, mode);
  if (!meta) return card;
  return { ...card, name: meta.name, desc: meta.desc };
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
    return `<div class="rc-icon rc-icon-art" style="background-image:url('assets/icons/cards-tech/${encodeURIComponent(card.id)}.png')"></div>`;
  }
  return `<div class="rc-icon">${escapeHtml(card.icon)}</div>`;
}

function getRogueCardName(cardId) {
  return getCardMeta(cardId, "rogue").name;
}

function getUltimateCardName(cardId) {
  return getCardMeta(cardId, "ultimate").name;
}
