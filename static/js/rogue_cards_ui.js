// Rogue/Ultimate card UI helpers.
// Loaded before the main inline script; functions resolve shared globals at call time.

// Features the server reports in /status. Ultimate mode is archived unless the
// server says otherwise, so it stays hidden until /status confirms it.
let serverFeatures = { ultimate: false };

function ultimateAvailable() {
  return !!serverFeatures.ultimate;
}

function applyServerFeatures(features) {
  if (features && typeof features === "object") serverFeatures = { ...serverFeatures, ...features };
  const available = ultimateAvailable();
  const option = document.querySelector('#sel-rogue-variant option[value="ultimate"]');
  if (option) {
    option.hidden = !available;
    option.disabled = !available;
  }
  const select = document.getElementById("sel-rogue-variant");
  if (select && select.value === "ultimate" && !available) {
    select.value = "solo";
    if (typeof updateVariantOptionRows === "function") updateVariantOptionRows();
  }
  ["rogue-wiki-ultimate-title", "rogue-wiki-ultimate-cards"].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.hidden = !available;
  });
  renderRogueWiki();
}

function localizedModeField(item, field) {
  const key = field.toLowerCase();
  return item[key] || "";
}

function renderRogueWiki() {
  const intro = document.getElementById("rogue-wiki-intro");
  const modeWrap = document.getElementById("rogue-wiki-modes");
  const rogueWrap = document.getElementById("rogue-wiki-rogue-cards");
  const ultimateWrap = document.getElementById("rogue-wiki-ultimate-cards");
  if (!intro || !modeWrap || !rogueWrap || !ultimateWrap) return;

  intro.textContent = ultimateAvailable()
    ? ui(
      "这里汇总 Rogue AI 的三种主玩法、闯关路线，以及所有 Rogue 强化卡与大招卡的效果说明。",
      "This index covers Rogue AI game variants, challenge runs, and the full effect list for Rogue and Ultimate cards.",
      "Rogue AIの主な遊び方、チャレンジルート、Rogue強化カードと必殺カードの効果をまとめています。",
      "Rogue AI의 주요 모드, 도전 루트, Rogue 강화 카드와 궁극기 카드 효과를 모았습니다."
    )
    : ui(
      "这里汇总 Rogue AI 的玩法、闯关路线，以及所有 Rogue 卡牌的效果说明。",
      "This index covers Rogue AI game variants, challenge runs, and the full effect list for every Rogue card.",
      "Rogue AIの遊び方、チャレンジルート、すべてのRogueカードの効果をまとめています。",
      "Rogue AI의 모드, 도전 루트, 모든 Rogue 카드 효과를 모았습니다."
    );

  const modes = (activeLocalePack()?.wikiModes || fallbackLocalePack()?.wikiModes || [])
    .filter(item => item.key !== "ultimate" || ultimateAvailable());
  modeWrap.innerHTML = modes.map(item => `
    <article class="wiki-mode-card">
      <h3>${escapeHtml(localizedModeField(item, "Title"))}</h3>
      <p>${escapeHtml(localizedModeField(item, "Desc"))}</p>
    </article>
  `).join("");

  rogueWrap.innerHTML = ROGUE_CARD_IDS.map(cardId => {
    const meta = getCardMeta(cardId, "rogue");
    return `
      <article class="wiki-card-item">
        ${getCardIconMarkup({ id: cardId, icon: "?" })}
        <div class="wiki-card-copy">
          <h4>${escapeHtml(meta.name)}</h4>
          ${getCardMetaMarkup({ id: cardId }, "rogue")}
          <p>${escapeHtml(meta.desc)}</p>
        </div>
      </article>
    `;
  }).join("");

  ultimateWrap.innerHTML = !ultimateAvailable() ? "" : ULTIMATE_CARD_IDS.map(cardId => {
    const meta = getCardMeta(cardId, "ultimate");
    return `
      <article class="wiki-card-item">
        ${getCardIconMarkup({ id: cardId, icon: "?" })}
        <div class="wiki-card-copy">
          <h4>${escapeHtml(meta.name)}</h4>
          ${getCardMetaMarkup({ id: cardId }, "ultimate")}
          <p>${escapeHtml(meta.desc)}</p>
        </div>
      </article>
    `;
  }).join("");
}

// One offer card: art, name, type, a one-line summary, and the full rules
// behind "How it works" (never truncated). Clicking the card or pressing
// Enter/Space picks it; the details button only expands.
function buildDraftCard(card, mode, container, onPick) {
  const c = getTranslatedCard(card, mode);
  const cls = mode === "ultimate" ? "ultimate-card" : "rogue-card";
  const summary = c.summary || c.desc || "";
  const hasRules = !!(c.summary && c.desc && c.desc !== c.summary);
  const rulesId = `draft-rules-${mode}-${card.id}`;
  const div = document.createElement("div");
  div.className = `${cls} draft-card`;
  div.tabIndex = 0;
  div.setAttribute("role", "button");
  div.setAttribute("aria-label", `${c.name}: ${summary}`);
  div.innerHTML = `${getCardIconMarkup(c)}
    <div class="rc-name">${escapeHtml(c.name)}</div>
    ${getCardKindMarkup(c, mode)}
    <p class="rc-summary">${escapeHtml(summary)}</p>
    ${hasRules ? `<button type="button" class="rc-more" aria-expanded="false" aria-controls="${rulesId}">${escapeHtml(ui("玩法说明", "How it works"))}</button>
    <p class="rc-rules" id="${rulesId}" hidden>${escapeHtml(c.desc)}</p>` : ""}`;
  const more = div.querySelector(".rc-more");
  if (more) {
    more.addEventListener("click", event => {
      event.stopPropagation();
      const rules = div.querySelector(".rc-rules");
      const open = rules.hidden;
      rules.hidden = !open;
      more.setAttribute("aria-expanded", String(open));
      more.textContent = open ? ui("收起说明", "Hide details") : ui("玩法说明", "How it works");
    });
    more.addEventListener("keydown", event => event.stopPropagation());
  }
  const pick = () => {
    if (div.classList.contains("selected")) return;
    container.querySelectorAll(`.${cls}`).forEach(other => other.classList.remove("selected"));
    div.classList.add("selected");
    onPick(c);
  };
  div.addEventListener("click", pick);
  div.addEventListener("keydown", event => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      pick();
    }
  });
  return div;
}

function showRogueCards(cards, meta = {}) {
  rogueOfferCards = Array.isArray(cards) ? cards.map(c => ({ ...c })) : [];
  const inChallenge = !!meta.challenge_beta;
  const stage = meta.challenge_stage || challengeSession.stage || 1;
  const refreshRemaining = meta.refresh_remaining ?? challengeSession.refreshes ?? 0;
  const rogueTitle = document.querySelector("#rogue-overlay h2");
  const rogueSub = document.querySelector("#rogue-overlay p");
  const refreshWrap = document.getElementById("rogue-refresh-wrap");
  const refreshBtn = document.getElementById("rogue-refresh-btn");
  if (rogueTitle) {
    rogueTitle.textContent = inChallenge
      ? ui(`\u95ef\u5173 \u7b2c ${stage} \u5173`, `Challenge - Stage ${stage}`)
      : ui("Rogue", "Rogue");
  }
  if (rogueSub) {
    rogueSub.textContent = inChallenge
      ? ui(`第 ${stage} 关 · 刷新 ${refreshRemaining}`, `Stage ${stage} · Refresh ${refreshRemaining}`)
      : (twoPlayerMode
        ? ui("共享规则卡", "Shared rule card")
        : ui("选择一张卡", "Pick a card"));
  }
  if (refreshWrap && refreshBtn) {
    refreshWrap.style.display = inChallenge && refreshRemaining > 0 ? "" : "none";
    refreshBtn.textContent = ui(`\u5237\u65b0\u5361\u724c (${refreshRemaining})`, `Refresh Cards (${refreshRemaining})`);
    refreshBtn.onclick = () => sendWS({ action: "challenge_refresh_offer" });
  }
  const container = document.getElementById("rogue-cards");
  container.innerHTML = "";
  rogueOfferCards.forEach(c0 => {
    container.appendChild(buildDraftCard(c0, "rogue", container, c => {
      showCardEffectVisual(c0.name || c.name, "rogue");
      setTimeout(() => sendWS({ action: "rogue_select_card", card_id: c0.id }), 160);
    }));
  });
  document.getElementById("rogue-overlay").classList.add("show");
  syncClientShell();
}

function getRogueSkillConfig() {
  if (activeRogueCard === "puppet") {
    return { key: "puppet", uses: rogueUses.puppet || 0, title: ui("主动技能：傀儡术", "Active Skill: Puppet") };
  }
  if (activeRogueCard === "twin") {
    return { key: "twin", uses: rogueUses.twin || 0, title: ui("主动技能：连击", "Active Skill: Combo") };
  }
  if (activeRogueCard === "exchange") {
    return { key: "exchange", uses: rogueUses.exchange || 0, title: ui("主动技能：乾坤挪移", "Active Skill: Stone Shift") };
  }
  if (activeRogueCard === "coach_mode") {
    return { key: "coach_mode", uses: rogueUses.coach_mode || 0, title: ui("主动技能：代练上号", "Active Skill: Coach Mode") };
  }
  return null;
}

function updateRogueSkillButton() {
  const btn = document.getElementById("btn-skill");
  if (!btn) return;
  const iconEl = btn.querySelector(".skill-btn-icon");
  const usesEl = btn.querySelector(".skill-use-badge");
  const cfg = getRogueSkillConfig();
  if (!cfg) {
    btn.style.display = "none";
    btn.disabled = true;
    if (iconEl) iconEl.dataset.icon = "skill";
    if (usesEl) usesEl.textContent = "";
    btn.title = ui("主动技能", "Active Skill");
    btn.dataset.skill = "";
    btn.classList.remove("skill-ready");
    btn.classList.remove("has-uses");
    return;
  }
  btn.style.display = "";
  btn.dataset.skill = cfg.key;
  if (iconEl) iconEl.dataset.icon = "skill";
  if (usesEl) usesEl.textContent = String(cfg.uses);
  const pending = cfg.key === "puppet" && gameState?.rogue_puppet_target
    ? ` · ${ui(`已锁 ${COLS[gameState.rogue_puppet_target[0]]}${boardSize - gameState.rogue_puppet_target[1]}`,
                `Locked ${COLS[gameState.rogue_puppet_target[0]]}${boardSize - gameState.rogue_puppet_target[1]}`)}`
    : "";
  btn.title = `${cfg.title} · ${ui("剩余", "Uses")} ${cfg.uses}${pending}`;
  btn.disabled = cfg.uses <= 0;
  btn.classList.toggle("skill-ready", cfg.uses > 0);
  btn.classList.toggle("has-uses", cfg.uses > 0);
}

function updateRogueBar() {
  updateRogueSkillButton();
  refreshHintVisibility();
  syncClientShell();
}

function resetRogueState() {
  activeRogueCard = null;
  activeAiRogueCard = null;
  rogueUses = {};
  rogueSealing = false;
  rogueSeals = [];
  aiRogueSeals = [];
  pendingRogueSealPoints = [];
  rogueSealRequired = 0;
  rogueSealWaitingForOpponent = false;
  quickthinkAwaitingAiMove = false;
  puppetMode = false;
  if (typeof exchangeModeActive !== "undefined") exchangeModeActive = false;
  if (typeof exchangeModeSource !== "undefined") exchangeModeSource = null;
  document.getElementById("rogue-bar").style.display = "none";
  updateRogueSkillButton();
  document.getElementById("rogue-overlay").classList.remove("show");
  if (typeof finishRogueSealSelection === "function") {
    finishRogueSealSelection();
  } else {
    const sealOverlay = document.getElementById("seal-overlay");
    if (sealOverlay) sealOverlay.hidden = true;
  }
  ultimateMode = false;
  ultimatePlayerCard = null;
  ultimateAiCard = null;
  ultimatePlayerName = "";
  ultimateAiName = "";
  document.getElementById("ultimate-bar").style.display = "none";
  document.getElementById("ultimate-overlay").classList.remove("show");
  clearCardTurnTimer();
  syncClientShell();
}

function showUltimateCards(cards) {
  ultimateOfferCards = Array.isArray(cards) ? cards.map(c => ({ ...c })) : [];
  const container = document.getElementById("ultimate-cards");
  if (!container) return;
  container.innerHTML = "";
  ultimateOfferCards.forEach(c0 => {
    container.appendChild(buildDraftCard(c0, "ultimate", container, c => {
      showCardEffectVisual(c0.name || c.name, "ultimate");
      setTimeout(() => sendWS({ action: "ultimate_select_card", card_id: c0.id }), 160);
    }));
  });
  const overlay = document.getElementById("ultimate-overlay");
  overlay.classList.add("show");
  syncClientShell();
}

const ULTIMATE_NAMES = {
  chain: "连珠棋",
  proliferate: "无限增殖",
  double: "双刀流",
  wildgrow: "狂野生长",
  rejection: "排异反应",
  territory: "绝对领地",
  shadow_clone: "影分身",
  plague: "瘟疫",
  meteor: "陨石雨",
  quantum: "量子纠缠",
  devour: "吞噬",
  timewarp: "时空裂缝",
  blackout: "天崩地裂",
  magnet: "磁力吸附",
  necro: "亡灵召唤",
  wall: "万里长城",
  joseki_burst: "定式爆发",
  god_hand: "神之一手",
  corner_helper: "守角要塞",
  sanrensei: "三连星爆发",
  quickthink: "极速风暴",
  foolish_wisdom: "愚形连锁",
  five_in_row: "五子连珠爆发",
  capture_foul: "提子犯规",
  last_stand: "起死回生",
};

function updateUltimateBar() {
  const bar = document.getElementById("ultimate-bar");
  if (!ultimateMode) { bar.style.display = "none"; syncClientShell(); return; }
  bar.style.display = "flex";
  const pName = ultimatePlayerName || getUltimateCardName(ultimatePlayerCard) || "—";
  const aName = ultimateAiName || getUltimateCardName(ultimateAiCard) || "—";
  document.getElementById("ub-player-card").textContent = ui("你: ", "You: ") + pName;
  document.getElementById("ub-ai-card").textContent = "AI: " + aName;
  const mc = gameState ? (gameState.ultimate_move_count || 0) : 0;
  document.getElementById("ub-moves").textContent = ui(`决胜 ${mc} / 20`, `${mc} / 20`);
  syncClientShell();
}

let rogueSkillButtonsBound = false;

function bindRogueSkillButtons() {
  if (rogueSkillButtonsBound) return;
  rogueSkillButtonsBound = true;

  document.getElementById("rb-puppet").addEventListener("click", () => {
    if (!activeRogueCard || activeRogueCard !== "puppet") return;
    if ((rogueUses.puppet || 0) <= 0) return;
    puppetMode = true;
    logI18n("🎭 傀儡术：先点出 AI 的下一手落点；你随后正常落子", "🎭 Puppet: choose the AI's next forced point first, then play your own move.", "🎭 傀儡術：まずAIの次の着点を指定し、その後通常どおり着手", "🎭 꼭두각시술: 먼저 AI의 다음 착점을 지정하고 이어서 정상 착수");
  });

  document.getElementById("rb-twin").addEventListener("click", () => {
    if (!activeRogueCard || activeRogueCard !== "twin") return;
    if ((rogueUses.twin || 0) <= 0) return;
    sendWS({ action: "rogue_use_twin" });
  });

  document.getElementById("rb-exchange").addEventListener("click", () => {
    if (!activeRogueCard || activeRogueCard !== "exchange") return;
    if ((rogueUses.exchange || 0) <= 0) return;
    exchangeModeActive = true;
    exchangeModeSource = null;
    logI18n("🔄 乾坤挪移：先选择一颗对方棋子，再选择目标空点", "🔄 Stone Shift: choose an opponent stone, then an empty destination.", "🔄 石の移動：相手の石を選び、次に空点を選択", "🔄 돌 이동: 상대 돌을 고른 뒤 빈 목적지를 선택하세요");
  });

  document.getElementById("rb-coach").addEventListener("click", () => {
    if (!activeRogueCard || activeRogueCard !== "coach_mode") return;
    if ((rogueUses.coach_mode || 0) <= 0) return;
    sendWS({ action: "rogue_use_coach" });
  });

  document.getElementById("btn-skill").addEventListener("click", () => {
    const cfg = getRogueSkillConfig();
    if (!cfg || cfg.uses <= 0) return;
    if (cfg.key === "puppet") {
      puppetMode = true;
      logI18n("🎭 傀儡术：先点出 AI 的下一手落点；你随后正常落子", "🎭 Puppet: choose the AI's next forced point first, then play your own move.", "🎭 傀儡術：まずAIの次の着点を指定し、その後通常どおり着手", "🎭 꼭두각시술: 먼저 AI의 다음 착점을 지정하고 이어서 정상 착수");
      return;
    }
    if (cfg.key === "twin") {
      sendWS({ action: "rogue_use_twin" });
      return;
    }
    if (cfg.key === "exchange") {
      exchangeModeActive = true;
      exchangeModeSource = null;
      logI18n("🔄 乾坤挪移：先选择一颗对方棋子，再选择目标空点", "🔄 Stone Shift: choose an opponent stone, then an empty destination.", "🔄 石の移動：相手の石を選び、次に空点を選択", "🔄 돌 이동: 상대 돌을 고른 뒤 빈 목적지를 선택하세요");
      return;
    }
    if (cfg.key === "coach_mode") {
      sendWS({ action: "rogue_use_coach" });
    }
  });
}
