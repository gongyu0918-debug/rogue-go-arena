// Legacy page localization bindings and UI refresh routines.

const LANGUAGE_OPTIONS = [
  ["zh", "中文", "Chinese", "中国語", "중국어"],
  ["en", "English", "English", "英語", "영어"],
  ["ja", "日语", "Japanese", "日本語", "일본어"],
  ["ko", "韩语", "Korean", "韓国語", "한국어"],
];

const AI_STYLE_OPTIONS = [
  ["balanced", "均衡", "Balanced", "バランス", "균형"],
  ["territory", "注重实地", "Territory", "地重視", "실리 중시"],
  ["influence", "注重外势", "Influence", "厚み重視", "세력 중시"],
  ["attack", "注重进攻", "Attack", "攻め重視", "공격 중시"],
  ["defense", "注重防守", "Defense", "守り重視", "수비 중시"],
];

function ensureLanguageControl() {
  const panel = document.getElementById("lang-panel")
    || document.getElementById("lang-panel-title")?.closest(".panel-card")
    || document.getElementById("lang-select")?.closest(".panel-card");
  if (panel) panel.remove();
}

function rebuildCurveLegend() {
  const legend = document.querySelector(".curve-legend");
  if (!legend) return;
  legend.innerHTML = `
    <span class="curve-dot black"></span><span id="curve-label-black-winrate">${ui("黑方胜率", "Black Winrate")}</span>
    <span class="curve-dot red"></span><span id="curve-label-white-winrate">${ui("白方胜率", "White Winrate")}</span>
    <span class="curve-dot gold"></span><span id="curve-label-score">${ui("目差", "Score Lead")}</span>
  `;
}

function syncLanguageSelectControls() {
  const langSelect = document.getElementById("lang-toggle");
  if (langSelect) {
    langSelect.value = currentLang;
    langSelect.title = ui("选择界面语言", "Choose interface language", "表示言語を選択", "표시 언어 선택");
  }
  const settingsLanguageSelect = document.getElementById("settings-language-select");
  if (settingsLanguageSelect) settingsLanguageSelect.value = currentLang;
  setText("#settings-language-label", ui("语言", "Language", "言語", "언어"));
}

function localizeClientHeader() {
  setText("#header-main h1", ui("围棋对弈场", "Rogue Go Arena", "囲碁対局場", "바둑 대국장"));
  setText("#client-kicker", ui("ROGUE", "ROGUE"));
  setText("#client-title", ui("rogue-go-arena", "rogue-go-arena", "rogue-go-arena", "rogue-go-arena"));
  setText("#quick-rogue", ui("Rogue", "Rogue"));
  setText("#quick-setup", ui("开始", "Start"));
  setText("#quick-fullscreen", ui("全屏", "Fullscreen"));
  setText("#client-status-label", ui("连接", "Connection"));
  setText("#client-engine-label", ui("引擎", "Engine"));
  setText("#client-mode-label", ui("模式", "Mode"));
  setText("#client-run-label", ui("手数", "Move"));
}

function localizeToolbarControls() {
  setTitle("#sound-toggle", ui("音效开关", "Sound", "効果音", "효과음"));
  setTitle("#btn-setup", ui("开始", "Start", "開始", "시작"));
  setTitle("#btn-quick-rogue", ui("Rogue", "Rogue", "Rogue", "Rogue"));
  setTitle("#btn-pass", ui("虚手", "Pass", "パス", "패스"));
  setTitle("#btn-undo", ui("悔棋", "Undo", "待った", "무르기"));
  setTitle("#btn-score", ui("计算", "Score", "計算", "계산"));
  setTitle("#btn-territory-toggle", ui("形势", "Territory", "形勢", "형세"));
  setTitle("#btn-resign", ui("认输", "Resign", "投了", "불계패"));
  setTitle("#btn-rogue-wiki", ui("Wiki", "Wiki"));
  setTitle("#btn-settings", ui("设置", "Settings", "設定", "설정"));
  setTitle("#btn-review-settings", ui("打开功能", "Settings", "機能を開く", "기능 열기"));
  setTitle("#btn-review-first", ui("第一手", "First Move", "初手", "첫 수"));
  setTitle("#btn-review-prev", ui("上一手", "Previous Move", "前の手", "이전 수"));
  setTitle("#btn-review-next", ui("下一手", "Next Move", "次の手", "다음 수"));
  setTitle("#btn-review-last", ui("最后一手", "Last Move", "最終手", "마지막 수"));
  setTitle("#btn-review-exit", ui("退出复盘", "Exit Review", "検討を終了", "복기 종료"));
  [
    ["#btn-setup .tool-label", "开始", "Start", "開始", "시작"],
    ["#btn-quick-rogue .tool-label", "Rogue", "Rogue"],
    ["#btn-rogue-wiki .tool-label", "Wiki", "Wiki"],
    ["#btn-pass .tool-label", "虚手", "Pass", "パス", "패스"],
    ["#btn-undo .tool-label", "悔棋", "Undo", "待った", "무르기"],
    ["#btn-score .tool-label", "计算", "Score", "計算", "계산"],
    ["#btn-territory-toggle .tool-label", "形势", "Area", "形勢", "형세"],
    ["#btn-resign .tool-label", "认输", "Resign", "投了", "불계패"],
    ["#btn-settings .tool-label", "设置", "Settings", "設定", "설정"],
    ["#btn-skill .tool-label", "技能", "Skill", "スキル", "스킬"],
  ].forEach(([selector, zh, en, ja, ko]) => setText(selector, ui(zh, en, ja, ko)));
  setTitle(".drawer-close", ui("关闭", "Close"));
  setTitle("#overlay-close", ui("关闭", "Close"));
  setTitle(".modal-close", ui("关闭", "Close"));
  setTitle("#ft-up", ui("上移", "Up", "上へ", "위로"));
  setTitle("#ft-down", ui("下移", "Down", "下へ", "아래로"));
  setTitle("#ft-left", ui("左移", "Left", "左へ", "왼쪽"));
  setTitle("#ft-right", ui("右移", "Right", "右へ", "오른쪽"));
  setTitle("#ft-ok", ui("确认落子", "Confirm Move", "着手を確定", "착수 확정"));
}

function localizeSettingsDrawer() {
  const drawerTitle = document.querySelector("#settings-drawer h2");
  if (drawerTitle) drawerTitle.textContent = ui("全局设定", "Settings", "全体設定", "전체 설정");
  const panelTitles = document.querySelectorAll("#settings-drawer .panel-card h3:not(#lang-panel-title)");
  if (panelTitles[0]) panelTitles[0].textContent = ui("界面选项", "Interface", "画面設定", "화면 옵션");
  if (panelTitles[1]) panelTitles[1].textContent = ui("辅助分析", "Analysis", "補助分析", "보조 분석");
  if (panelTitles[2]) panelTitles[2].textContent = ui("复盘/棋谱", "Review / SGF", "検討 / SGF", "복기 / 기보");
  if (panelTitles[4]) panelTitles[4].textContent = ui("对局信息", "Game Info", "対局情報", "대국 정보");
  if (panelTitles[5]) panelTitles[5].textContent = ui("棋谱记录", "Game Log", "棋譜記録", "기보 기록");
  setText("#card-editor-section-title", ui("卡牌配置", "Card Config", "カード設定", "카드 설정"));

  const settingsLabels = Array.from(document.querySelectorAll("#settings-drawer .form-row label"))
    .filter(el => el.id !== "lang-panel-label");
  if (settingsLabels[0]) settingsLabels[0].textContent = ui("落子模式", "Placement", "着手方式", "착수 방식");
  setText("#settings-stage-label", ui("画面尺寸", "Display Size", "画面サイズ", "화면 크기"));
  setText("#btn-card-editor", ui("卡牌编辑器", "Card Editor", "カード編集", "카드 편집기"));
  setTitle("#btn-card-editor", ui("打开卡牌强度编辑器", "Open Card Editor", "カード編集を開く", "카드 편집기 열기"));
  setText("#card-editor-modal-title", ui("卡牌编辑器", "Card Editor", "カード編集", "카드 편집기"));
  setTitle("#card-editor-modal-close", ui("关闭", "Close", "閉じる", "닫기"));

  const toggleLabels = Array.from(document.querySelectorAll("#settings-drawer .toggle-label"))
    .filter(el => !el.id || !el.id.startsWith("settings-"));
  if (toggleLabels[0]) toggleLabels[0].textContent = ui("显示推荐落点", "Show Suggested Moves", "推薦着点を表示", "추천 착점 표시");
  if (toggleLabels[1]) toggleLabels[1].textContent = ui("显示手数", "Show Move Numbers", "手数を表示", "수순 표시");
  if (toggleLabels[2]) toggleLabels[2].textContent = ui("形势判断", "Territory Estimate", "形勢判断", "형세 판단");
  setText("#btn-sgf-save", ui("保存棋谱", "Save SGF", "棋譜を保存", "기보 저장"));
  setText("#btn-sgf-load", ui("导入棋谱", "Load SGF", "棋譜を読み込み", "기보 불러오기"));
}

function localizeGameInfoPanel() {
  const infoLabels = document.querySelectorAll("#move-info .info-row span:first-child");
  const infoTexts = [
    ui("我执", "You Play", "持ち色", "내 돌"),
    ui("当前手数", "Move", "手数", "수순"),
    ui("行棋方", "Turn", "手番", "차례"),
    ui("黑吃子", "Black Captures", "黒のアゲハマ", "흑 따낸 돌"),
    ui("白吃子", "White Captures", "白のアゲハマ", "백 따낸 돌"),
    ui("形势估算", "Score Estimate", "形勢判断", "형세 추정"),
    ui("地盘差", "Territory Diff", "地合い差", "집 차이"),
    ui("对手级别", "Opponent", "相手の棋力", "상대 기력")
  ];
  infoLabels.forEach((el, idx) => { if (infoTexts[idx]) el.textContent = infoTexts[idx]; });
  const challengeInfoLabel = document.querySelector("#challenge-info-row span:first-child");
  if (challengeInfoLabel) challengeInfoLabel.textContent = ui("闯关进度", "Challenge");
}

function localizeOverlays() {
  const overlayStats = document.querySelectorAll("#overlay .score-item .label");
  if (overlayStats[0]) overlayStats[0].textContent = ui("胜方", "Winner", "勝者", "승자");
  if (overlayStats[1]) overlayStats[1].textContent = ui("比分", "Score", "スコア", "점수");
  const overlayBtns = document.querySelectorAll("#overlay .btn-row button");
  if (overlayBtns[0]) overlayBtns[0].textContent = ui("复盘", "Review", "検討", "복기");
  if (overlayBtns[1]) overlayBtns[1].textContent = ui("再来一局", "Play Again", "もう一局", "다시 한 판");

  const setupTitle = document.querySelector("#setup-modal h2");
  if (setupTitle) setupTitle.textContent = ui("开始对弈", "Start Game", "対局開始", "대국 시작");
  setText("#rogue-wiki-title", ui("ROGUE AI WIKI", "ROGUE AI WIKI"));
  setText("#rogue-wiki-mode-title", ui("玩法总览", "Mode Overview", "モード概要", "모드 개요"));
  setText("#rogue-wiki-rogue-title", ui("Rogue 卡牌效果", "Rogue Card Effects", "Rogueカード効果", "Rogue 카드 효과"));
  setText("#rogue-wiki-ultimate-title", ui("大招卡牌效果", "Ultimate Card Effects", "必殺カード効果", "궁극기 카드 효과"));
  setText("#label-color", ui("我执", "Color", "持ち色", "내 돌"));
  setText("#label-rogue-variant", ui("玩法", "Variant", "モード", "모드"));
  setText("#label-board", ui("棋盘", "Board", "碁盤", "바둑판"));
  setText("#label-komi", ui("贴目", "Komi", "コミ", "덤"));
  setText("#label-level", ui("等级", "Rank", "棋力", "기력"));
  setText("#label-level-black", ui("黑棋等级", "Black Rank", "黒の棋力", "흑 기력"));
  setText("#label-level-white", ui("白棋等级", "White Rank", "白の棋力", "백 기력"));
  setText("#label-style", ui("AI行为", "AI Behavior", "AIの棋風", "AI 행마"));
  setText("#label-style-black", ui("黑棋风格", "Black Style", "黒の棋風", "흑 기풍"));
  setText("#label-style-white", ui("白棋风格", "White Style", "白の棋風", "백 기풍"));
  setText("#label-handicap", ui("让子", "Handicap", "置き石", "접바둑"));
  setText("#label-time-mode", ui("用时", "Time", "持ち時間", "제한 시간"));
  setText("#label-main-time", ui("主时", "Main Time", "持ち時間", "기본 시간"));
  setText("#label-byoyomi", ui("读秒", "Byo-yomi", "秒読み", "초읽기"));
  setText("#mode-normal", ui("对局", "Game", "対局", "대국"));
  setText("#mode-rogue", ui("Rogue", "Rogue"));
  setText("#mode-watch", ui("学习", "Study", "研究", "학습"));
  setText("#mode-two", ui("双人", "Two Players", "二人", "2인"));
  setText("#mode-challenge", ui("闯关", "Challenge", "チャレンジ", "도전"));
  setText("#btn-new", ui("确认开始", "Start", "開始する", "시작"));
  setText("#confirm-msg", ui("确认执行此操作？", "Confirm this action?", "この操作を実行しますか？", "이 작업을 실행할까요?"));

  const confirmBtns = document.querySelectorAll("#confirm-modal .btn-row button");
  if (confirmBtns[0]) confirmBtns[0].textContent = ui("取消", "Cancel");
  if (confirmBtns[1]) confirmBtns[1].textContent = ui("确定", "Confirm");
  const rogueTitle = document.querySelector("#rogue-overlay h2");
  if (rogueTitle) rogueTitle.textContent = ui("Rogue 模式", "Rogue Mode", "Rogueモード", "Rogue 모드");
  const ultTitle = document.querySelector("#ultimate-overlay h2");
  if (ultTitle) ultTitle.textContent = ui("大招模式", "Ultimate Mode", "必殺モード", "궁극기 모드");
  const ultSub = document.querySelector("#ultimate-overlay p");
  if (ultSub) ultSub.textContent = ui("选择大招卡", "Pick ultimate card", "必殺カードを選択", "궁극기 카드 선택");
}

function localizeSetupOptions() {
  setOptionText("sel-placement", [
    ["direct", "直接落子", "Direct", "直接着手", "바로 착수"],
    ["fine", "精准落子(支持微调)", "Fine-tune", "精密着手（微調整）", "정밀 착수(미세 조정)"]
  ]);
  setOptionText("sel-stage-preset", [
    ["auto", "自适应", "Auto", "自動", "자동"],
    ["1080", "1080p", "1080p"],
    ["1440", "1440p", "1440p"],
    ["2160", "4K", "4K"]
  ]);
  const stageSelect = document.getElementById("sel-stage-preset");
  if (stageSelect) stageSelect.value = stagePreset;
  setOptionText("lang-toggle", LANGUAGE_OPTIONS);
  setOptionText("settings-language-select", LANGUAGE_OPTIONS);
  setOptionText("sel-color", [
    ["B", "黑棋（先手）", "Black (First)", "黒（先番）", "흑(선수)"],
    ["W", "白棋（后手）", "White (Second)", "白（後番）", "백(후수)"],
    ["R", "随机（猜先）", "Random (Guess)", "ランダム（ニギリ）", "무작위(돌 가리기)"]
  ]);
  setOptionText("sel-ai-style", AI_STYLE_OPTIONS);
  setOptionText("sel-ai-style-black", AI_STYLE_OPTIONS);
  setOptionText("sel-ai-style-white", AI_STYLE_OPTIONS);
  setOptionText("sel-time-mode", [
    ["none", "无限制", "No Limit", "無制限", "무제한"],
    ["byoyomi", "包干+读秒", "Main + Byo-yomi", "持ち時間＋秒読み", "기본 시간+초읽기"],
    ["absolute", "包干用时", "Absolute", "切れ負け", "절대 시간"]
  ]);
  setOptionText("sel-rogue-variant", [
    ["solo", "单人抽卡", "Solo Draft", "ソロドラフト", "솔로 드래프트"],
    ["dual", "双人抽卡", "Dual Draft", "デュアルドラフト", "듀얼 드래프트"],
    ["ultimate", "大招对战", "Ultimate Duel", "必殺デュエル", "궁극기 대전"]
  ]);
}

function refreshLocalizedRuntimeViews() {
  if (document.getElementById("rogue-overlay").classList.contains("show") && rogueOfferCards.length) {
    showRogueCards(rogueOfferCards);
  }
  if (document.getElementById("ultimate-overlay").classList.contains("show") && ultimateOfferCards.length) {
    showUltimateCards(ultimateOfferCards);
  }
  if (activeRogueCard) updateRogueBar();
  if (ultimateMode) updateUltimateBar();
  if (gameState) updateUI();
  refreshRankSelectLabels();
  syncClientShell();
  renderRogueWiki();
  refreshSetupModeHint();
  updateVariantOptionRows();
  drawWinrateCurve();
  enhanceWoodSelects();
  syncWoodSelects();
  renderGameLog();
  syncBoardFitFrame();
  if (boardRenderSize) render();
}

function applyLanguage() {
  document.documentElement.lang = { zh: "zh-CN", en: "en", ja: "ja", ko: "ko" }[currentLang] || "zh-CN";
  document.title = ui("rogue-go-arena", "rogue-go-arena", "rogue-go-arena", "rogue-go-arena");

  ensureLanguageControl();
  rebuildCurveLegend();
  syncLanguageSelectControls();
  localizeClientHeader();
  localizeToolbarControls();
  setConnectionIndicator(!!ws && ws.readyState === WebSocket.OPEN);
  setThinkingText(ui("AI 思考中…", "AI is thinking..."));
  localizeSettingsDrawer();
  localizeGameInfoPanel();
  localizeOverlays();
  localizeSetupOptions();
  updateWinRate(analysis?.winrate ?? 0.5);
  setText("#curve-title", ui("胜率曲线", "Winrate Curve", "勝率グラフ", "승률 그래프"));
  setText("#curve-label-winrate", ui("白方胜率", "White Winrate", "白の勝率", "백 승률"));
  setText("#curve-label-score", ui("目差", "Score Lead", "目差", "집 차이"));
  setConnectionIndicator(!!ws && ws.readyState === WebSocket.OPEN);
  refreshLocalizedRuntimeViews();
}

function bindLanguageControl(selectId) {
  const select = document.getElementById(selectId);
  if (!select) return;
  select.addEventListener("change", (event) => {
    void setLanguage(event.target.value || "zh");
  });
}

bindLanguageControl("lang-toggle");
bindLanguageControl("settings-language-select");
window.applyLanguage = applyLanguage;
