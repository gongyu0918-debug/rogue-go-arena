// Game log storage, localization, and rendering.

let gameLogEntries = [];

function log(msg) {
  gameLogEntries.push({ text: String(msg || "") });
  while (gameLogEntries.length > 90) gameLogEntries.shift();
  renderGameLog();
}

function logI18n(zh, en, ja, ko) {
  gameLogEntries.push({ args: [zh, en, ja, ko] });
  while (gameLogEntries.length > 90) gameLogEntries.shift();
  renderGameLog();
}

function logRender(renderer) {
  gameLogEntries.push({ renderer });
  while (gameLogEntries.length > 90) gameLogEntries.shift();
  renderGameLog();
}

function logServerEvent(message, prefix = "", event = null) {
  const raw = String(message || "");
  const key = event?.key;
  const params = event?.params;
  logRender(() => `${prefix}${localizeServerEvent(raw, key, params)}`);
}

function localizeLogText(text) {
  const value = String(text || "");
  const known = {
    "已连接": ["已连接", "Connected", "接続済み", "연결됨"],
    "Connected": ["已连接", "Connected", "接続済み", "연결됨"],
    "接続済み": ["已连接", "Connected", "接続済み", "연결됨"],
    "연결됨": ["已连接", "Connected", "接続済み", "연결됨"],
    "对局已结束": ["对局已结束", "The game is already over", "対局は終了しています", "대국이 이미 종료되었습니다"],
    "The game is already over": ["对局已结束", "The game is already over", "対局は終了しています", "대국이 이미 종료되었습니다"],
    "暂无进行中的对局，请点击「开始对弈」开始": ["暂无进行中的对局，请点击「开始对弈」开始", "No active game was found. Click Start Game to begin.", "進行中の対局はありません。「対局開始」を押してください", "진행 중인 대국이 없습니다. 「대국 시작」을 눌러 시작하세요"],
    "No active game was found. Click Start Game to begin.": ["暂无进行中的对局，请点击「开始对弈」开始", "No active game was found. Click Start Game to begin.", "進行中の対局はありません。「対局開始」を押してください", "진행 중인 대국이 없습니다. 「대국 시작」을 눌러 시작하세요"],
  };
  if (known[value]) return ui(...known[value]);
  let match = value.match(/^已恢复对局（第(\d+)手）$/)
    || value.match(/^Game restored \(move (\d+)\)$/)
    || value.match(/^対局を復元しました（(\d+)手）$/)
    || value.match(/^대국을 복원했습니다\((\d+)수\)$/);
  if (match) {
    const move = match[1];
    return ui(
      `已恢复对局（第${move}手）`,
      `Game restored (move ${move})`,
      `対局を復元しました（${move}手）`,
      `대국을 복원했습니다(${move}수)`
    );
  }
  return value;
}

function renderGameLog() {
  const el = document.getElementById("game-log");
  if (!el) return;
  closeWoodSelectMenu();
  el.innerHTML = "";
  for (const entry of gameLogEntries) {
    const d = document.createElement("div");
    d.textContent = entry.renderer ? entry.renderer() : (entry.args ? ui(...entry.args) : localizeLogText(entry.text));
    el.appendChild(d);
  }
  requestAnimationFrame(() => {
    el.scrollTop = el.scrollHeight;
  });
}

function clearGameLog() {
  gameLogEntries = [];
  const el = document.getElementById("game-log");
  if (el) el.innerHTML = "";
}
