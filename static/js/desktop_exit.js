// Desktop exit button. Keeps game UI shutdown separate from launcher-only controls.
(() => {
const UI_EXIT_TOKEN_HEADER = "X-Rogue-Go-Ui-Exit-Token";
let desktopExitInFlight = false;

function desktopExitButton() {
  return document.getElementById("desktop-exit-button");
}

function currentDesktopExitStatus() {
  return window.__rogueGoArenaNetworkStatus || null;
}

function desktopExitCanRun(status = currentDesktopExitStatus()) {
  const hasGame = typeof gameState !== "undefined" && !!gameState;
  return !!(status && status.desktop_exit_token && (status.desktop_exit_available || hasGame));
}

function syncDesktopExitButton() {
  const button = desktopExitButton();
  if (!button) return;
  const enabled = desktopExitCanRun() && !desktopExitInFlight;
  const label = desktopExitInFlight
    ? ui("正在退出…", "Exiting...", "終了中…", "종료 중...")
    : ui("关闭并退出", "Exit Game", "終了", "종료");
  button.disabled = !enabled;
  button.classList.toggle("exiting", desktopExitInFlight);
  button.textContent = label;
  button.title = enabled
    ? ui("停止AI并关闭游戏", "Stop AI and close the game", "AIを停止して終了", "AI를 중지하고 종료")
    : ui("模型启动或开始对局后可用", "Available after the model starts or a game begins", "モデル起動後または対局開始後に使用できます", "모델 시작 또는 대국 시작 후 사용할 수 있습니다");
  button.setAttribute("aria-label", button.title);
}

function confirmDesktopExit() {
  if (!desktopExitCanRun() || desktopExitInFlight) return;
  const message = ui(
    "关闭游戏并释放AI资源？",
    "Exit the game and release AI resources?",
    "ゲームを終了してAIリソースを解放しますか？",
    "게임을 종료하고 AI 리소스를 해제할까요?"
  );
  if (typeof showConfirmModal === "function") {
    showConfirmModal(message, () => { void performDesktopExit(); }, {
      confirmText: ui("退出", "Exit", "終了", "종료"),
      cancelText: ui("取消", "Cancel", "キャンセル", "취소"),
    });
    return;
  }
  if (window.confirm(message)) void performDesktopExit();
}

function requestHostWindowClose() {
  const api = window.pywebview && window.pywebview.api;
  if (!api || typeof api.close_window !== "function") return false;
  try {
    const result = api.close_window();
    if (result && typeof result.catch === "function") {
      result.catch((err) => {
        console.warn("[desktop-exit] host close failed", err);
        try {
          window.close();
        } catch (_) {
        }
      });
    }
    return true;
  } catch (err) {
    console.warn("[desktop-exit] host close failed", err);
    return false;
  }
}

async function performDesktopExit() {
  const status = await refreshNetworkInfo().catch(() => null) || currentDesktopExitStatus();
  if (!desktopExitCanRun(status) || desktopExitInFlight) {
    syncDesktopExitButton();
    return;
  }
  desktopExitInFlight = true;
  syncDesktopExitButton();

  try {
    const response = await fetch("/desktop_exit", {
      method: "POST",
      cache: "no-store",
      headers: {
        "Accept": "application/json",
        [UI_EXIT_TOKEN_HEADER]: status.desktop_exit_token,
      },
    });
    if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
    clearPendingWS();
    intentionalClose = true;
    try {
      if (ws && ws.readyState <= WebSocket.OPEN) ws.close();
    } catch (_) {
    }
    logI18n("正在关闭游戏并释放AI资源…", "Exiting and releasing AI resources...", "ゲームを終了しAIリソースを解放中…", "게임을 종료하고 AI 리소스를 해제 중...");
    setConnectionIndicator(false, ui("正在退出…", "Exiting..."));
    window.setTimeout(() => {
      if (!requestHostWindowClose()) window.close();
    }, 250);
    window.setTimeout(() => {
      try {
        window.location.replace("about:blank");
      } catch (_) {
      }
    }, 1200);
  } catch (err) {
    desktopExitInFlight = false;
    intentionalClose = false;
    syncDesktopExitButton();
    logI18n("退出失败，请稍后重试", "Exit failed. Please try again.", "終了に失敗しました。もう一度お試しください", "종료 실패. 다시 시도하세요");
    console.warn("[desktop-exit] request failed", err);
  }
}

desktopExitButton()?.addEventListener("click", confirmDesktopExit);

window.syncDesktopExitButton = syncDesktopExitButton;
window.confirmDesktopExit = confirmDesktopExit;
window.performDesktopExit = performDesktopExit;
})();
