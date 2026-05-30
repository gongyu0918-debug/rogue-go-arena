// Network status refresh and lightweight WebSocket send helper.

(() => {
let networkStatus = null;

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
    return result.status;
  } catch (_) {
    syncClientShell();
    return null;
  }
}

function websocketIsOpen(socket) {
  return !!socket && socket.readyState === WebSocket.OPEN;
}

function sendWS(data) {
  if (websocketIsOpen(ws)) ws.send(JSON.stringify(data));
}

Object.defineProperty(window, "__rogueGoArenaNetworkStatus", {
  configurable: true,
  enumerable: true,
  get: () => networkStatus,
  set: value => { networkStatus = normalizeNetworkStatus(value); },
});

window.updateNetworkBadge = updateNetworkBadge;
window.refreshNetworkInfo = refreshNetworkInfo;
window.sendWS = sendWS;
})();
