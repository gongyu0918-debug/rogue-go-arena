// Runtime status, overlay, score, and winrate UI helpers.
(() => {
const WINRATE_CURVE_PADDING = { left: 28, right: 16, top: 14, bottom: 22 };

function clampRange(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function getWinrateCurveLayout(width, height) {
  const pad = WINRATE_CURVE_PADDING;
  const plotX = pad.left;
  const plotY = pad.top;
  const plotW = Math.max(10, width - pad.left - pad.right);
  const plotH = Math.max(10, height - pad.top - pad.bottom);
  return { plotX, plotY, plotW, plotH };
}

function resizeCanvasForDpr(canvasEl, width, height, dpr) {
  const pixelWidth = Math.floor(width * dpr);
  const pixelHeight = Math.floor(height * dpr);
  if (canvasEl.width !== pixelWidth || canvasEl.height !== pixelHeight) {
    canvasEl.width = pixelWidth;
    canvasEl.height = pixelHeight;
  }
}

function drawWinrateHistoryLine(c, points, plotX, stepX, yForPoint) {
  c.beginPath();
  points.forEach((point, index) => {
    const x = plotX + stepX * index;
    const y = yForPoint(point);
    if (index === 0) c.moveTo(x, y);
    else c.lineTo(x, y);
  });
  c.stroke();
}

function resetWinrateHistory() {
  winrateHistory = [];
  window.drawWinrateCurve();
}

function pushWinratePoint(winrate, score) {
  const move = gameState?.move_number || 0;
  const prev = winrateHistory[winrateHistory.length - 1];
  if (prev && prev.move === move && Math.abs(prev.winrate - winrate) < 0.0005 && Math.abs(prev.score - score) < 0.05) {
    return;
  }
  winrateHistory.push({ move, winrate, score });
  if (winrateHistory.length > 400) winrateHistory.shift();
  window.drawWinrateCurve();
}

function drawWinrateCurve() {
  const canvasEl = document.getElementById("winrate-curve");
  if (!canvasEl) return;
  const width = Math.max(220, Math.floor(canvasEl.clientWidth || 320));
  const height = Math.max(120, Math.floor(canvasEl.clientHeight || 148));
  const dpr = window.devicePixelRatio || 1;
  resizeCanvasForDpr(canvasEl, width, height, dpr);
  const c = canvasEl.getContext("2d");
  if (!c) return;
  c.setTransform(dpr, 0, 0, dpr, 0, 0);
  c.clearRect(0, 0, width, height);

  const { plotX, plotY, plotW, plotH } = getWinrateCurveLayout(width, height);

  c.fillStyle = "rgba(10, 12, 18, 0.92)";
  c.fillRect(0, 0, width, height);
  c.strokeStyle = "rgba(255,255,255,0.08)";
  c.lineWidth = 1;
  for (let i = 0; i <= 4; i++) {
    const y = plotY + (plotH / 4) * i;
    c.beginPath();
    c.moveTo(plotX, y);
    c.lineTo(plotX + plotW, y);
    c.stroke();
  }
  c.strokeStyle = "rgba(255,255,255,0.12)";
  c.beginPath();
  c.moveTo(plotX, plotY);
  c.lineTo(plotX, plotY + plotH);
  c.lineTo(plotX + plotW, plotY + plotH);
  c.stroke();

  c.fillStyle = "rgba(255,255,255,0.55)";
  c.font = '11px "Segoe UI", "Microsoft YaHei", sans-serif';
  c.textAlign = "right";
  c.textBaseline = "middle";
  for (let i = 0; i <= 4; i++) {
    const label = 100 - i * 25;
    const y = plotY + (plotH / 4) * i;
    c.fillText(String(label), plotX - 6, y);
  }

  if (!winrateHistory.length) {
    c.fillStyle = "rgba(255,255,255,0.42)";
    c.textAlign = "center";
    c.textBaseline = "middle";
    c.fillText(ui("对局开始后显示胜率曲线", "Winrate history appears after analysis starts."), width / 2, height / 2);
    return;
  }

  const scoreCap = Math.max(10, ...winrateHistory.map(point => Math.abs(point.score)));
  const stepX = winrateHistory.length === 1 ? 0 : plotW / (winrateHistory.length - 1);
  const mapWinrateY = value => plotY + (1 - clampRange(value, 0, 1)) * plotH;
  const mapBlackWinrateY = value => mapWinrateY(1 - value);
  const mapScoreY = value => plotY + (0.5 - clampRange(value, -scoreCap, scoreCap) / (scoreCap * 2)) * plotH;

  c.lineWidth = 1.4;
  c.strokeStyle = "rgba(243, 200, 91, 0.92)";
  drawWinrateHistoryLine(c, winrateHistory, plotX, stepX, point => mapScoreY(point.score));

  c.lineWidth = 1.7;
  c.strokeStyle = "rgba(159, 179, 217, 0.96)";
  drawWinrateHistoryLine(c, winrateHistory, plotX, stepX, point => mapBlackWinrateY(point.winrate));

  c.lineWidth = 1.8;
  c.strokeStyle = "rgba(255, 103, 103, 0.96)";
  drawWinrateHistoryLine(c, winrateHistory, plotX, stepX, point => mapWinrateY(point.winrate));

  const latest = winrateHistory[winrateHistory.length - 1];
  const latestX = plotX + stepX * Math.max(0, winrateHistory.length - 1);
  c.fillStyle = "rgba(255,255,255,0.78)";
  c.textAlign = "left";
  c.textBaseline = "bottom";
  c.fillText(
    ui(`第 ${latest.move} 手 · 白胜率 ${(latest.winrate * 100).toFixed(1)}% · 目差 ${latest.score.toFixed(1)}`,
       `Move ${latest.move} · White ${(latest.winrate * 100).toFixed(1)}% · Score ${latest.score.toFixed(1)}`),
    plotX,
    plotY - 3
  );
  c.fillStyle = "#ff6767";
  c.beginPath();
  c.arc(latestX, mapWinrateY(latest.winrate), 3.2, 0, Math.PI * 2);
  c.fill();
  const latestBlack = (1 - latest.winrate) * 100;
  const latestWhite = latest.winrate * 100;
  c.fillStyle = "rgba(10, 12, 18, 0.95)";
  c.fillRect(plotX - 4, 0, Math.min(plotW + 8, width - plotX + 4), plotY + 2);
  c.fillStyle = "rgba(255,255,255,0.78)";
  c.textAlign = "left";
  c.textBaseline = "bottom";
  c.fillText(
    ui(`第 ${latest.move} 手 · 黑方胜率 ${latestBlack.toFixed(1)}% · 白方胜率 ${latestWhite.toFixed(1)}% · 目差 ${latest.score.toFixed(1)}`,
       `Move ${latest.move} · Black ${latestBlack.toFixed(1)}% · White ${latestWhite.toFixed(1)}% · Score ${latest.score.toFixed(1)}`),
    plotX,
    plotY - 3
  );
  c.fillStyle = "#9fb3d9";
  c.beginPath();
  c.arc(latestX, mapBlackWinrateY(latest.winrate), 3.1, 0, Math.PI * 2);
  c.fill();
  c.fillStyle = "#f3c85b";
  c.beginPath();
  c.arc(latestX, mapScoreY(latest.score), 2.9, 0, Math.PI * 2);
  c.fill();
}

function setThinking(v) {
  document.getElementById("thinking-indicator").className = v ? "show" : "";
  document.getElementById("thinking-indicator-panel").className = v ? "show" : "";
}

function overlayKindForTitle(title) {
  if (/win|胜|赢/.test(title)) return "victory";
  if (/draw|平/.test(title)) return "draw";
  return "defeat";
}

function showOverlay(title, sub, winner, score) {
  document.getElementById("overlay-title").textContent = title;
  document.getElementById("overlay-msg").textContent = sub;
  document.getElementById("overlay-winner").textContent = winner;
  document.getElementById("overlay-score").textContent = score;
  const overlay = document.getElementById("overlay");
  const kind = overlayKindForTitle(title);
  overlay.className = `show ${kind}`;
  spawnOverlaySparks(kind);
}

function closeOverlay() {
  document.getElementById("overlay").className = "";
  const sparks = document.getElementById("overlay-sparks");
  if (sparks) sparks.innerHTML = "";
}

function reasonText(r) {
  return {
    resign: ui("认输", "Resignation", "投了", "投了"),
    ai_resign: ui("AI认输", "AI resigned", "AI投了", "AI投了"),
    score: ui("计数", "Scoring", "計算", "계가"),
    double_pass: ui("双方虚手", "Double pass", "双方パス", "쌍방 패스"),
    timeout: ui("超时", "Timeout", "時間切れ", "시간 초과"),
    ultimate_20moves: ui("20手决胜", "20-move showdown", "20手決戦", "20수 승부"),
  }[r] || r || "";
}

function scoreWinnerLabel(color) {
  return color === "B" ? ui("黑", "Black", "黒", "흑") : ui("白", "White", "白", "백");
}

function scoreUnitText(isChineseRules) {
  if (currentLang === "en") return isChineseRules ? "stones" : "points";
  if (currentLang === "ko") return "집";
  return isChineseRules ? "子" : "目";
}

function formatScoreDisplay(score, komi) {
  const rawScore = score || "—";
  const m = String(rawScore).match(/^([BW])\+(.+)$/);
  if (!m) return rawScore;
  const who = scoreWinnerLabel(m[1]);
  const isChineseRules = komi === 7.5;
  const unit = scoreUnitText(isChineseRules);
  if (currentLang === "en") return `${who} +${m[2]} ${unit}`;
  if (currentLang === "ja") return `${who}${m[2]}${unit}勝ち`;
  if (currentLang === "ko") return `${who} ${m[2]}${unit} 승`;
  return `${who}胜${m[2]}${unit}`;
}

function updateUI() {
  if (!gameState) return;
  if (twoPlayerMode) {
    document.getElementById("info-my-color").innerHTML = ui("双方（人）", "Human vs Human");
  } else {
    const colorDot = `<span class="my-color-badge" style="background:${myColor==='B'?'#111':'#eee'}"></span>`;
    document.getElementById("info-my-color").innerHTML =
      colorDot + (myColor==="B" ? ui("黑棋", "Black") : ui("白棋", "White"));
  }
  document.getElementById("info-move").textContent = gameState.move_number || 0;
  const cp = gameState.current_player;
  if (twoPlayerMode) {
    document.getElementById("info-player").textContent = cp === "B" ? ui("黑棋落子", "Black to move") : ui("白棋落子", "White to move");
  } else {
    document.getElementById("info-player").textContent =
      cp === myColor
        ? (cp==="B" ? ui("黑（我）", "Black (You)") : ui("白（我）", "White (You)"))
        : (cp==="B" ? ui("黑（AI）", "Black (AI)") : ui("白（AI）", "White (AI)"));
  }
  if (cardTurnRemaining > 0 && isMyTurn) {
    document.getElementById("info-player").textContent += ` ${cardTurnLabel}${cardTurnRemaining.toFixed(1)}s`;
  }
  document.getElementById("info-cap-b").textContent = gameState.captures?.B || 0;
  document.getElementById("info-cap-w").textContent = gameState.captures?.W || 0;
  document.getElementById("info-level").textContent =
    gameState.ai_observer
      ? `${ui("黑", "Black")} ${rankLabel(gameState.ai_level_black) || "—"} / ${ui("白", "White")} ${rankLabel(gameState.ai_level_white) || "—"}`
      : (twoPlayerMode ? ui("双人", "Two Players") : (rankLabel(gameState.level) || "—"));
  syncClientShell();
}

function winrateUiReady(value) {
  return analysisPanelEnabled() && analysisReady && Number.isFinite(Number(value));
}

function setWinratePendingState(btnScore) {
  const black = document.getElementById("wr-black");
  const white = document.getElementById("wr-white");
  const blackLabel = document.getElementById("wr-black-label");
  const whiteLabel = document.getElementById("wr-white-label");
  if (black) black.style.width = "50%";
  if (white) white.style.width = "50%";
  if (blackLabel) blackLabel.textContent = "";
  if (whiteLabel) whiteLabel.textContent = "";
  if (btnScore && gameState && !gameState.game_over) {
    btnScore.disabled = true;
    btnScore.title = ui("计算胜负", "Score");
  }
}

function syncScoreButtonForWinrate(btnScore, rawBlack, rawWhite) {
  if (!btnScore || !gameState || gameState.game_over) return;
  const canScore = rawBlack >= 80 || rawWhite >= 80;
  btnScore.disabled = !canScore;
  btnScore.title = canScore ? ui("计算胜负", "Score") : ui("胜率需≥80%才可计算胜负", "Win rate must reach 80% to score");
}

function updateWinRate(wr) {
  const wrap = document.getElementById("winrate-bar-wrap");
  const topSlot = document.getElementById("top-winrate-slot");
  const enabled = analysisPanelEnabled();
  const ready = winrateUiReady(wr);
  const btnScore = document.getElementById("btn-score");
  if (wrap) {
    wrap.style.display = "block";
    wrap.classList.toggle("analysis-off", !enabled);
    wrap.classList.toggle("analysis-pending", enabled && !ready);
  }
  if (topSlot) topSlot.classList.add("active");
  if (!ready) {
    setWinratePendingState(btnScore);
    return;
  }
  const rawBlack = Math.max(0, Math.min(100, Number(wr) * 100));
  const rawWhite = 100 - rawBlack;
  const b = rawBlack.toFixed(1);
  const w = rawWhite.toFixed(1);
  document.getElementById("wr-black").style.width = rawBlack + "%";
  document.getElementById("wr-white").style.width = rawWhite + "%";
  document.getElementById("wr-black-label").textContent = `${ui("黑", "Black")} ${b}%`;
  document.getElementById("wr-white-label").textContent = `${ui("白", "White")} ${w}%`;
  syncScoreButtonForWinrate(btnScore, rawBlack, rawWhite);
}

window.resetWinrateHistory = resetWinrateHistory;
window.pushWinratePoint = pushWinratePoint;
window.drawWinrateCurve = drawWinrateCurve;
window.setThinking = setThinking;
window.showOverlay = showOverlay;
window.closeOverlay = closeOverlay;
window.reasonText = reasonText;
window.formatScoreDisplay = formatScoreDisplay;
window.updateUI = updateUI;
window.updateWinRate = updateWinRate;
})();
