// Keyed server messages (see app/domain/event_text.py): the server sends a
// language-neutral key + params next to the legacy Chinese text. Render the key
// with the active locale pack's "events" templates; otherwise fall back to the
// legacy regex translator.
//
// Template placeholders: {name} or {name|type[:arg:arg]}.
//   card / ucard  Rogue / Ultimate card id -> localized card name
//   color         "B" / "W"                -> eventTerms color.*
//   corner        "tl" / "tr" / "bl" / "br" -> eventTerms corner.*
//   set           challenge set id(s)       -> eventTerms set.*, joined with " / "
//   rank          rank id ("5k", "a3d", "p2d") -> rankLabel()
//   list          array -> joined with eventTerms list.separator
//   chain         array -> joined with "–"
//   pl:one:other  number -> the plural form for the active locale (Intl.PluralRules)

function eventPack() {
  return typeof localeCache === "object" ? localeCache[currentLang] || null : null;
}

function eventTerm(id) {
  return eventPack()?.eventTerms?.[id] ?? (typeof fallbackLocalePack === "function" ? fallbackLocalePack()?.eventTerms?.[id] : undefined) ?? null;
}

function eventPluralCategory(value) {
  const locale = eventPack()?.locale || "en-US";
  try {
    return new Intl.PluralRules(locale).select(Number(value));
  } catch {
    return Number(value) === 1 ? "one" : "other";
  }
}

const EVENT_PARAM_FORMATTERS = {
  card: value => (typeof getRogueCardName === "function" && getRogueCardName(value)) || value,
  ucard: value => (typeof getUltimateCardName === "function" && getUltimateCardName(value)) || value,
  color: value => eventTerm(`color.${value}`) ?? value,
  corner: value => eventTerm(`corner.${value}`) ?? value,
  set: value => (Array.isArray(value) ? value : [value]).map(id => eventTerm(`set.${id}`) ?? id).join(" / "),
  rank: value => (typeof rankLabel === "function" ? rankLabel(value) : value),
  list: value => (Array.isArray(value) ? value : [value]).join(eventTerm("list.separator") ?? ", "),
  chain: value => (Array.isArray(value) ? value : [value]).join("–"),
  pl: (value, one, other) => (eventPluralCategory(value) === "one" ? one : other),
};

function renderEventTemplate(template, params = {}) {
  return String(template).replace(/\{(\w+)(?:\|([^{}]+))?\}/g, (whole, name, spec) => {
    if (!(name in params)) return whole;
    const value = params[name];
    if (!spec) return String(value);
    const [type, ...args] = spec.split(":");
    const format = EVENT_PARAM_FORMATTERS[type];
    return format ? String(format(value, ...args)) : String(value);
  });
}

function localizeServerEvent(text, key, params) {
  if (key) {
    const template = eventPack()?.events?.[key];
    if (typeof template === "string") return renderEventTemplate(template, params || {});
  }
  return translateServerEventMessage(text);
}

window.localizeServerEvent = localizeServerEvent;
window.renderEventTemplate = renderEventTemplate;
