// Legacy shared state for the classic-script frontend.
// These bindings intentionally stay in the global lexical scope so existing
// modules can keep using bare identifiers until the React preview reaches parity.

const RANK_GROUPS = [
  { label: "── 级位 ──", separator: true },
  ...["18k", "17k", "16k", "15k", "14k", "13k", "12k", "11k", "10k",
    "9k", "8k", "7k", "6k", "5k", "4k", "3k", "2k", "1k"].map(id => ({ id, label: id.replace("k", "级") })),
  { label: "── 业余段位 ──", separator: true },
  ...["a1d", "a2d", "a3d", "a4d", "a5d", "a6d", "a7d", "a8d", "a9d"].map((id, i) => ({
    id, label: `业余${i + 1}段`
  })),
  { label: "── 职业段位 ──", separator: true },
  ...["p1d", "p2d", "p3d", "p4d", "p5d", "p6d", "p7d", "p8d", "p9d"].map((id, i) => ({
    id, label: ["职业一段", "职业二段", "职业三段", "职业四段", "职业五段",
      "职业六段", "职业七段", "职业八段", "职业九段"][i]
  })),
];

const RANK_LABELS = {};
RANK_GROUPS.filter(rank => !rank.separator).forEach(rank => { RANK_LABELS[rank.id] = rank.label; });

const COLS = "ABCDEFGHJKLMNOPQRST".split("");

let gameId = localStorage.getItem("rogue_go_arena_game_id") || Math.random().toString(36).slice(2);
localStorage.setItem("rogue_go_arena_game_id", gameId);

let ws = null;
let intentionalClose = false;
let gameState = null;
let previousBoard = null;
let lastAiMove = null;
let boardSize = 19;
let PAD = 0;
let CELL = 0;
let myColor = "B";
let aiColor = "W";
let isMyTurn = false;
let twoPlayerMode = false;
let showHints = false;
let showTerritory = true;
let showMoveNumbers = false;
let startMode = "normal";
let stagePreset = localStorage.getItem("rogue_go_arena_stage_preset") || "auto";
let analysis = { winrate: 0.5, score: 0, top_moves: [], ownership: [], analysis_ready: false };
let analysisReady = false;
let winrateHistory = [];
