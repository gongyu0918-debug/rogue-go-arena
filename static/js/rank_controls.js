// Legacy rank selector population and GPU-based slow-rank warnings.

const RANK_ORDER = ["18k", "17k", "16k", "15k", "14k", "13k", "12k", "11k", "10k",
  "9k", "8k", "7k", "6k", "5k", "4k", "3k", "2k", "1k",
  "a1d", "a2d", "a3d", "a4d", "a5d", "a6d", "a7d", "a8d", "a9d",
  "p1d", "p2d", "p3d", "p4d", "p5d", "p6d", "p7d", "p8d", "p9d"];

let rankSelects = [];
let gpuSlowFrom = "";

function populateRankSelect(selectEl, defaultRank = "a3d") {
  if (!selectEl) return;
  selectEl.innerHTML = "";
  RANK_GROUPS.forEach(rank => {
    const opt = document.createElement("option");
    if (rank.separator) {
      opt.disabled = true;
      opt.textContent = rankGroupLabel(rank.label);
      opt.style.color = "#888";
    } else {
      opt.value = rank.id;
      opt.textContent = rankLabel(rank.id);
      if (rank.id === defaultRank) opt.selected = true;
    }
    selectEl.appendChild(opt);
  });
}

function slowRankSuffix() {
  return ui("(推理较慢)", "(slower)", "（推論遅め）", "(추론 느림)");
}

function applySlowRankWarnings() {
  const slowIdx = RANK_ORDER.indexOf(gpuSlowFrom);
  if (slowIdx < 0) return;
  rankSelects.forEach(selectEl => {
    for (const opt of selectEl.options) {
      if (opt.disabled) continue;
      const rankIdx = RANK_ORDER.indexOf(opt.value);
      if (rankIdx >= slowIdx) {
        opt.textContent = `⚠ ${rankLabel(opt.value)} ${slowRankSuffix()}`;
        opt.style.color = "#ff9800";
        opt.dataset.slowMarked = "1";
      }
    }
  });
}

function refreshRankSelectLabels() {
  rankSelects.forEach(selectEl => {
    const previous = selectEl.value || "a3d";
    populateRankSelect(selectEl, previous);
    selectEl.value = previous;
    syncWoodSelect(selectEl);
  });
  applySlowRankWarnings();
}

async function detectGPUForRankDefaults() {
  try {
    const resp = await fetch("/gpu");
    if (!resp.ok) return;
    const gpu = await resp.json();
    if (gpu.default_rank) {
      rankSelects.forEach(selectEl => { selectEl.value = gpu.default_rank; });
    }
    gpuSlowFrom = gpu.slow_from || "";
    applySlowRankWarnings();
    syncWoodSelects();
  } catch (_) {
    // GPU detection is optional; rank controls keep their default values.
  }
}

function initializeRankControls() {
  rankSelects = [
    document.getElementById("sel-level"),
    document.getElementById("sel-level-black"),
    document.getElementById("sel-level-white"),
  ].filter(Boolean);
  rankSelects.forEach(selectEl => populateRankSelect(selectEl));
  void detectGPUForRankDefaults();
}

window.initializeRankControls = initializeRankControls;
window.refreshRankSelectLabels = refreshRankSelectLabels;
window.applySlowRankWarnings = applySlowRankWarnings;
window.populateRankSelect = populateRankSelect;
