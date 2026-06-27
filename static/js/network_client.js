// Network status refresh and lightweight WebSocket send helper.

(() => {
let networkStatus = null;
const pendingMessages = [];
const MAX_PENDING_MESSAGES = 32;

function normalizeNetworkStatus(status) {
  return status || null;
}

function updateNetworkBadge(status) {
  networkStatus = normalizeNetworkStatus(status);
}

async function fetchNetworkStatus() {
  const resp = await fetch("/status", { cache: "no-store" });
  if (!resp.ok) return { ok: false, status: null };
  return { ok: true, status: await resp.json() };
}

async function refreshNetworkInfo() {
  try {
    const result = await fetchNetworkStatus();
    if (!result.ok) return null;
    updateNetworkBadge(result.status);
    syncClientShell();
    if (typeof window.syncDesktopExitButton === "function") window.syncDesktopExitButton();
    return result.status;
  } catch (_) {
    syncClientShell();
    if (typeof window.syncDesktopExitButton === "function") window.syncDesktopExitButton();
    return null;
  }
}

function websocketIsOpen(socket) {
  return !!socket && socket.readyState === WebSocket.OPEN;
}

function flushPendingWS() {
  if (!websocketIsOpen(ws)) return 0;
  let sent = 0;
  while (pendingMessages.length) {
    ws.send(JSON.stringify(pendingMessages.shift()));
    sent += 1;
  }
  return sent;
}

function clearPendingWS() {
  pendingMessages.length = 0;
}

function sendWS(data) {
  if (websocketIsOpen(ws)) {
    ws.send(JSON.stringify(data));
    return true;
  }
  pendingMessages.push(data);
  if (pendingMessages.length > MAX_PENDING_MESSAGES) pendingMessages.shift();
  return false;
}

Object.defineProperty(window, "__rogueGoArenaNetworkStatus", {
  configurable: true,
  enumerable: true,
  get: () => networkStatus,
  set: value => { networkStatus = normalizeNetworkStatus(value); },
});

window.updateNetworkBadge = updateNetworkBadge;
window.refreshNetworkInfo = refreshNetworkInfo;
window.clearPendingWS = clearPendingWS;
window.flushPendingWS = flushPendingWS;
window.sendWS = sendWS;
})();
