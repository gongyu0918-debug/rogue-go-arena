// Shared UI shell helpers for labels, connection state, and top HUD state.

const ENGINE_TEXT_REPLACEMENTS = {
  en: [
    [/CUDA\(升级包\)/g, "CUDA (upgrade pack)"],
    [/升级包/g, "upgrade pack"],
    [/引擎已就绪/g, "engine ready"],
    [/引擎初始化中/g, "engine starting"],
    [/引擎检测中/g, "checking engine"],
    [/检测中/g, "checking"],
    [/AI 待命/g, "AI ready"],
    [/AI 在线/g, "AI online"],
    [/CPU 模式/g, "CPU mode"],
    [/高端/g, "high-end"],
  ],
  ja: [
    [/CUDA\(升级包\)/g, "CUDA(アップグレード版)"],
    [/升级包/g, "アップグレード版"],
    [/引擎已就绪/g, "エンジン準備完了"],
    [/引擎初始化中/g, "エンジン起動中"],
    [/引擎检测中/g, "エンジン確認中"],
    [/检测中/g, "確認中"],
    [/AI 待命/g, "AI待機中"],
    [/AI 在线/g, "AIオンライン"],
    [/CPU 模式/g, "CPUモード"],
    [/高端/g, "ハイエンド"],
  ],
  ko: [
    [/CUDA\(升级包\)/g, "CUDA(업그레이드팩)"],
    [/升级包/g, "업그레이드팩"],
    [/引擎已就绪/g, "엔진 준비됨"],
    [/引擎初始化中/g, "엔진 시작 중"],
    [/引擎检测中/g, "엔진 확인 중"],
    [/检测中/g, "확인 중"],
    [/AI 待命/g, "AI 대기"],
    [/AI 在线/g, "AI 온라인"],
    [/CPU 模式/g, "CPU 모드"],
    [/高端/g, "하이엔드"],
  ],
};

function setText(selector, text) {
  const el = document.querySelector(selector);
  if (el) el.textContent = text;
}

function setTitle(selector, text) {
  const el = document.querySelector(selector);
  if (el) el.title = text;
}

function setThinkingText(text) {
  ["thinking-indicator", "thinking-indicator-panel"].forEach((id) => {
    const el = document.getElementById(id);
    if (!el) return;
    el.innerHTML = "";
    const spinner = document.createElement("span");
    spinner.className = "spinner";
    el.appendChild(spinner);
    el.appendChild(document.createTextNode(text));
  });
}

function setSoundToggleVisual() {
  const button = document.getElementById("sound-toggle");
  const label = ui("音效开关", "Sound");
  const icon = button?.querySelector(".toolbar-icon");
  if (icon) icon.dataset.icon = soundEnabled ? "sound-on" : "sound-off";
  if (button) {
    button.title = label;
    button.setAttribute("aria-label", label);
    button.classList.toggle("muted", !soundEnabled);
  }
  const settingsToggle = document.getElementById("sound-settings-toggle");
  if (settingsToggle) settingsToggle.className = "toggle" + (soundEnabled ? " on" : "");
}

function setTerritoryToggleVisual() {
  const icon = document.querySelector("#btn-territory-toggle .toolbar-icon");
  if (icon) icon.dataset.icon = showTerritory ? "territory-on" : "territory-off";
}

function hasUsableAnalysis(value) {
  return !!value && value.analysis_ready === true && Number.isFinite(Number(value.winrate));
}

function analysisPanelEnabled() {
  return showTerritory && !isHintLockedByCard();
}

function setConnectionIndicator(ready, text) {
  const dot = document.getElementById("status-dot");
  const status = document.getElementById("status-text");
  const label = text || (ready ? ui("已连接", "Connected") : ui("连接中…", "Connecting..."));
  if (dot) {
    dot.className = ready ? "ready" : "";
    dot.title = label;
    dot.setAttribute("aria-label", label);
  }
  if (status) status.textContent = label;
  syncClientShell();
}

function currentModeLabel() {
  if (gameState?.challenge_beta || startMode === "challenge") return ui("闯关", "Challenge");
  if (ultimateMode) return ui("Rogue · 大招对战", "Rogue · Ultimate Duel");
  if (activeRogueCard || activeAiRogueCard || startMode === "rogue") {
    const variant = getRogueVariantMode();
    if (variant === "dual") return ui("Rogue · 双人抽卡", "Rogue · Dual Draft");
    if (variant === "ultimate") return ui("Rogue · 大招对战", "Rogue · Ultimate Duel");
    return ui("Rogue · 单人抽卡", "Rogue · Solo Draft");
  }
  if (twoPlayerMode || startMode === "two") return ui("双人对局", "Two Players");
  if (gameState?.ai_observer || startMode === "watch") return ui("AI 学习", "AI Study");
  return ui("普通对局", "Classic Game");
}

function currentTurnLabel() {
  if (!gameState) return ui("待开始", "Ready");
  if (gameState.game_over) return ui("已终局", "Finished");
  const cp = gameState.current_player;
  if (twoPlayerMode) return cp === "B" ? ui("黑棋落子", "Black to move") : ui("白棋落子", "White to move");
  return cp === myColor ? ui("轮到你", "Your turn") : ui("AI 思考", "AI thinking");
}

function moveNumberText(value) {
  if (currentLang === "en") return `Move ${value}`;
  if (currentLang === "ja") return `${value}手`;
  if (currentLang === "ko") return `${value}수`;
  return `第${value}手`;
}

function localizeEngineText(text) {
  if (!text) return "";
  const source = String(text);
  if (currentLang === "zh") return source;
  return (ENGINE_TEXT_REPLACEMENTS[currentLang] || []).reduce(
    (value, [pattern, replacement]) => value.replace(pattern, replacement),
    source
  );
}

function engineStatusText(net, connected) {
  if (net.katago_ready) {
    const backend = net.engine_backend ? localizeEngineText(net.engine_backend) : "KataGo";
    const model = net.engine_model || net.katago_model_name || "";
    return model ? `${backend} · ${model}` : backend;
  }
  if (net.katago_model) {
    const model = net.katago_model_name || "";
    return model
      ? ui(`模型就绪 · ${model}`, `Model ready · ${model}`, `モデル準備完了 · ${model}`, `모델 준비됨 · ${model}`)
      : ui("模型就绪", "Model ready", "モデル準備完了", "모델 준비됨");
  }
  if (net.engine_message) return localizeEngineText(net.engine_message);
  return connected ? ui("AI 待命", "AI ready") : ui("检测中…", "Checking...");
}

function clientShellElements() {
  return {
    statusValue: document.getElementById("client-status-value"),
    engineValue: document.getElementById("client-engine-value"),
    modeValue: document.getElementById("client-mode-value"),
    runValue: document.getElementById("client-run-value"),
    hudMode: document.getElementById("hud-mode"),
    hudMove: document.getElementById("hud-move"),
    hudTurn: document.getElementById("hud-turn"),
    hudCard: document.getElementById("hud-card"),
    hudEngine: document.getElementById("hud-engine"),
  };
}

function currentCardLabel() {
  if (ultimateMode) return `${getUltimateCardName(ultimatePlayerCard) || ui("待选大招", "Pick Ultimate")}`;
  return activeRogueCard ? getRogueCardName(activeRogueCard) : ui("无卡牌", "No Card");
}

function setEngineShellValue(engineValue, net, connected) {
  if (!engineValue) return;
  const engineText = engineStatusText(net, connected);
  engineValue.textContent = engineText;
  engineValue.title = net.katago_model_name
    ? `${engineText} · ${net.katago_model_name}`
    : engineText;
}

function hudEngineText(net, connected) {
  return net.engine_backend
    ? localizeEngineText(net.engine_backend)
    : (connected ? ui("AI 在线", "AI online") : ui("AI 待命", "AI standby"));
}

function syncClientShell() {
  const {
    statusValue,
    engineValue,
    modeValue,
    runValue,
    hudMode,
    hudMove,
    hudTurn,
    hudCard,
    hudEngine,
  } = clientShellElements();
  const connected = !!ws && ws.readyState === WebSocket.OPEN;
  const net = window.__rogueGoArenaNetworkStatus || {};
  const modeLabel = currentModeLabel();
  const turnLabel = currentTurnLabel();
  const moveText = String(gameState?.move_number || 0);
  const cardText = currentCardLabel();
  if (statusValue) statusValue.textContent = connected ? ui("已连接", "Connected") : ui("连接中…", "Connecting...");
  setEngineShellValue(engineValue, net, connected);
  if (modeValue) modeValue.textContent = modeLabel;
  if (runValue) runValue.textContent = gameState ? `${moveNumberText(moveText)} · ${turnLabel}` : ui("待开始", "Ready");
  if (hudMode) hudMode.textContent = modeLabel;
  if (hudMove) hudMove.textContent = `${ui("手数", "Move")} ${moveText}`;
  if (hudTurn) hudTurn.textContent = turnLabel;
  if (hudCard) hudCard.textContent = cardText;
  if (hudEngine) hudEngine.textContent = hudEngineText(net, connected);
}

function quickStartRogue() {
  setMode("rogue");
  const variant = document.getElementById("sel-rogue-variant");
  if (variant) variant.value = "solo";
  updateVariantOptionRows();
  document.getElementById("btn-new").click();
}

function openNormalSetup() {
  setMode("normal");
  openSetupModal();
}

function toggleFullscreen() {
  if (!document.fullscreenElement) {
    document.documentElement.requestFullscreen?.();
  } else {
    document.exitFullscreen?.();
  }
}

function setOptionText(selectId, pairs) {
  const el = document.getElementById(selectId);
  if (!el) return;
  pairs.forEach(([value, zh, en, ja, ko]) => {
    const opt = el.querySelector(`option[value="${value}"]`);
    if (opt) opt.textContent = ui(zh, en, ja, ko);
  });
  syncWoodSelect(el);
}
