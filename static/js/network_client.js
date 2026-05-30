// Network status refresh and lightweight WebSocket send helper.

function updateNetworkBadge(status) {
  window.__rogueGoArenaNetworkStatus = status || null;
}

async function refreshNetworkInfo() {
  try {
    const resp = await fetch("/status", { cache: "no-store" });
    if (!resp.ok) return null;
    const status = await resp.json();
    updateNetworkBadge(status);
    syncClientShell();
    return status;
  } catch (_) {
    syncClientShell();
    return null;
  }
}

function sendWS(data) {
  if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(data));
}

window.updateNetworkBadge = updateNetworkBadge;
window.refreshNetworkInfo = refreshNetworkInfo;
window.sendWS = sendWS;
