// Legacy rank selector population and GPU-based slow-rank warnings.

const RANK_ORDER = ["18k", "17k", "16k", "15k", "14k", "13k", "12k", "11k", "10k",
  "9k", "8k", "7k", "6k", "5k", "4k", "3k", "2k", "1k",
  "a1d", "a2d", "a3d", "a4d", "a5d", "a6d", "a7d", "a8d", "a9d",
  "p1d", "p2d", "p3d", "p4d", "p5d", "p6d", "p7d", "p8d", "p9d"];
const RANK_SELECT_IDS = ["sel-level", "sel-level-black", "sel-level-white"];

let rankSelects = [];
let gpuSlowFrom = "";

function createRankOption(rank, defaultRank) {
  const opt = document.createElement("option");
  if (rank.separator) {
    opt.disabled = true;
    opt.textContent = rankGroupLabel(rank.label);
    opt.style.color = "#888";
    return opt;
  }
  opt.value = rank.id;
  opt.textContent = rankLabel(rank.id);
  if (rank.id === defaultRank) opt.selected = true;
  return opt;
}

function populateRankSelect(selectEl, defaultRank = "a3d") {
  if (!selectEl) return;
  selectEl.innerHTML = "";
  RANK_GROUPS.forEach(rank => selectEl.appendChild(createRankOption(rank, defaultRank)));
}

function slowRankSuffix() {
  return ui("(推理较慢)", "(slower)", "（推論遅め）", "(추론 느림)");
}

function rankOrderIndex(rankId) {
  return RANK_ORDER.indexOf(rankId);
}

function isSlowRankValue(value, slowIdx) {
  const rankIdx = rankOrderIndex(value);
  return rankIdx >= slowIdx;
}

function markSlowRankOption(opt) {
  opt.textContent = `⚠ ${rankLabel(opt.value)} ${slowRankSuffix()}`;
  opt.style.color = "#ff9800";
  opt.dataset.slowMarked = "1";
}

function applySlowRankWarnings() {
  const slowIdx = rankOrderIndex(gpuSlowFrom);
  if (slowIdx < 0) return;
  rankSelects.forEach(selectEl => {
    for (const opt of selectEl.options) {
      if (opt.disabled) continue;
      if (isSlowRankValue(opt.value, slowIdx)) markSlowRankOption(opt);
    }
  });
}

function refreshRankSelect(selectEl) {
  const previous = selectEl.value || "a3d";
  populateRankSelect(selectEl, previous);
  selectEl.value = previous;
  syncWoodSelect(selectEl);
}

function refreshRankSelectLabels() {
  rankSelects.forEach(refreshRankSelect);
  applySlowRankWarnings();
}

function applyGpuDefaultRank(defaultRank) {
  if (!defaultRank) return;
  rankSelects.forEach(selectEl => { selectEl.value = defaultRank; });
}

async function detectGPUForRankDefaults() {
  try {
    const resp = await fetch("/gpu");
    if (!resp.ok) return;
    const gpu = await resp.json();
    applyGpuDefaultRank(gpu.default_rank);
    gpuSlowFrom = gpu.slow_from || "";
    applySlowRankWarnings();
    syncWoodSelects();
  } catch (_) {
    // GPU detection is optional; rank controls keep their default values.
  }
}

function initializeRankControls() {
  rankSelects = RANK_SELECT_IDS.map(id => document.getElementById(id)).filter(Boolean);
  rankSelects.forEach(selectEl => populateRankSelect(selectEl));
  void detectGPUForRankDefaults();
}

window.initializeRankControls = initializeRankControls;
window.refreshRankSelectLabels = refreshRankSelectLabels;
window.applySlowRankWarnings = applySlowRankWarnings;
window.populateRankSelect = populateRankSelect;
