// Language selection, locale packs, and small localization helpers.

function normalizeLang(lang) {
  const raw = String(lang || "").trim().toLowerCase();
  if (raw.startsWith("zh-tw") || raw.startsWith("zh-hk") || raw.startsWith("zh-mo") || raw.startsWith("zh-hant") || raw === "zht") return "zht";
  if (raw.startsWith("ja")) return "ja";
  if (raw.startsWith("ko") || raw.startsWith("kr")) return "ko";
  if (raw.startsWith("fr")) return "fr";
  if (raw.startsWith("de")) return "de";
  if (raw.startsWith("en")) return "en";
  return "zh";
}

const urlLang = new URLSearchParams(window.location.search).get("lang");
let currentLang = normalizeLang(urlLang || localStorage.getItem("rogue_go_arena_lang") || navigator.language || "zh");
const LOCALE_FILES = {
  zh: "zh-CN.json",
  zht: "zh-TW.json",
  en: "en-US.json",
  ja: "ja-JP.json",
  ko: "ko-KR.json",
  fr: "fr-FR.json",
  de: "de-DE.json",
};
const localeCache = {};

function activeLocalePack() {
  return localeCache[currentLang] || localeCache.zh || null;
}

function fallbackLocalePack() {
  return localeCache.zh || activeLocalePack();
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, char => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;",
  })[char]);
}

async function loadLocalePack(lang) {
  const normalized = normalizeLang(lang);
  if (localeCache[normalized]) return localeCache[normalized];
  const file = LOCALE_FILES[normalized] || LOCALE_FILES.zh;
  const response = await fetch("/static/locales/" + file + "?v=20260602a", { cache: "no-cache" });
  if (!response.ok) throw new Error("Failed to load locale " + file + ": " + response.status);
  const pack = await response.json();
  localeCache[normalized] = pack;
  return pack;
}

async function ensureLocale(lang = currentLang) {
  try {
    await loadLocalePack("zh");
    const normalized = normalizeLang(lang);
    if (normalized !== "zh") await loadLocalePack(normalized);
  } catch (err) {
    console.warn("[i18n] locale loading failed", err);
  }
}

function localizedValue(zh, en, ja, ko) {
  const packValue = activeLocalePack()?.phrases?.[zh];
  if (packValue !== undefined) return packValue;
  if (currentLang === "en") return en ?? zh;
  if (currentLang === "ja") return ja ?? zh;
  if (currentLang === "ko") return ko ?? zh;
  return fallbackLocalePack()?.phrases?.[zh] ?? zh;
}

function ui(zh, en, ja, ko) {
  return localizedValue(zh, en, ja, ko);
}

function langObjectValue(value) {
  if (!value || typeof value !== "object") return value || "";
  const localeCode = { zh: "zh-CN", zht: "zh-TW", en: "en-US", ja: "ja-JP", ko: "ko-KR", fr: "fr-FR", de: "de-DE" }[currentLang];
  return value[localeCode] ?? value[currentLang] ?? value.zh ?? value.en ?? "";
}

function rankLabel(rankId) {
  if (!rankId) return "";
  const kyuMatch = String(rankId).match(/^(\d+)k$/);
  if (kyuMatch) {
    const n = kyuMatch[1];
    if (currentLang === "en") return `${n} kyu`;
    if (currentLang === "ja") return `${n}級`;
    if (currentLang === "ko") return `${n}급`;
    if (currentLang === "zht") return `${n}級`;
    if (currentLang === "fr") return `${n} kyu`;
    if (currentLang === "de") return `${n}. Kyu`;
    return `${n}级`;
  }
  const amaMatch = String(rankId).match(/^a(\d+)d$/);
  if (amaMatch) {
    const n = amaMatch[1];
    if (currentLang === "en") return `Amateur ${n} dan`;
    if (currentLang === "ja") return `アマ${n}段`;
    if (currentLang === "ko") return `아마 ${n}단`;
    if (currentLang === "zht") return `業餘${n}段`;
    if (currentLang === "fr") return `${n} dan amateur`;
    if (currentLang === "de") return `${n}. Dan Amateur`;
    return `业余${n}段`;
  }
  const proMatch = String(rankId).match(/^p(\d+)d$/);
  if (proMatch) {
    const n = proMatch[1];
    if (currentLang === "en") return `Pro ${n} dan`;
    if (currentLang === "ja") return `プロ${n}段`;
    if (currentLang === "ko") return `프로 ${n}단`;
    if (currentLang === "zht") return ["職業一段","職業二段","職業三段","職業四段","職業五段","職業六段","職業七段","職業八段","職業九段"][Number(n) - 1] || rankId;
    if (currentLang === "fr") return `${n} dan pro`;
    if (currentLang === "de") return `${n}. Dan Profi`;
    return ["职业一段","职业二段","职业三段","职业四段","职业五段","职业六段","职业七段","职业八段","职业九段"][Number(n) - 1] || rankId;
  }
  return RANK_LABELS[rankId] || rankId;
}

function rankGroupLabel(label) {
  const groups = activeLocalePack()?.rankGroups || fallbackLocalePack()?.rankGroups || {};
  if (label.includes("级位")) return groups.kyu || label;
  if (label.includes("业余")) return groups.amateur || label;
  if (label.includes("职业")) return groups.pro || label;
  return label;
}

async function setLanguage(lang) {
  closeWoodSelectMenu();
  currentLang = normalizeLang(lang);
  localStorage.setItem("rogue_go_arena_lang", currentLang);
  await ensureLocale(currentLang);
  applyLanguage();
}
