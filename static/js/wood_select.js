(() => {
let activeWoodSelect = null;
let woodSelectPopover = null;
let activeWoodOption = null;
const woodOptionElements = new WeakMap();
const WOOD_SELECT_POPOVER_ID = "wood-select-listbox";

function ensureWoodSelectPopover() {
  if (woodSelectPopover) return woodSelectPopover;
  woodSelectPopover = document.createElement("div");
  woodSelectPopover.id = WOOD_SELECT_POPOVER_ID;
  woodSelectPopover.className = "wood-select-popover";
  woodSelectPopover.setAttribute("role", "listbox");
  woodSelectPopover.addEventListener("mousedown", event => {
    // Keep keyboard focus on the combobox until a complete primary click.
    if (event.button === 0 && event.target.closest(".wood-select-option")) event.preventDefault();
  });
  woodSelectPopover.addEventListener("click", event => {
    if (event.button !== 0) return;
    const item = event.target.closest(".wood-select-option");
    const option = item && woodOptionElements.get(item);
    if (option) chooseWoodSelectOption(activeWoodSelect, option);
  });
  woodSelectPopover.addEventListener("wheel", handleWoodSelectWheel, { passive: false });
  document.body.appendChild(woodSelectPopover);
  return woodSelectPopover;
}

function selectedOption(select) {
  return select?.selectedOptions?.[0] || Array.from(select?.options || []).find(opt => opt.selected) || null;
}

function woodSelectParts(select) {
  const wrap = select?.closest(".wood-select") || null;
  return {
    wrap,
    button: wrap?.querySelector(".wood-select-button") || null,
    value: wrap?.querySelector(".wood-select-value") || null,
  };
}

function selectedOptionLabel(select) {
  const opt = selectedOption(select);
  return opt ? opt.label : "";
}

function woodSelectMenuIsOpen(select) {
  return activeWoodSelect === select && woodSelectPopover?.classList.contains("open");
}

function setWoodSelectExpanded(select, expanded) {
  const { wrap, button } = woodSelectParts(select);
  if (expanded) {
    wrap?.classList.add("open");
  } else {
    wrap?.classList.remove("open");
  }
  if (button) {
    button.setAttribute("aria-expanded", expanded ? "true" : "false");
    if (!expanded) button.removeAttribute("aria-activedescendant");
  }
}

function syncWoodSelectButton(select) {
  const { wrap, button, value } = woodSelectParts(select);
  if (!wrap) return false;
  if (value) value.textContent = selectedOptionLabel(select);
  if (button) {
    button.disabled = !!select.disabled;
    button.setAttribute("aria-expanded", wrap.classList.contains("open") ? "true" : "false");
    const label = select.labels?.[0] || select.closest(".form-row")?.querySelector("label");
    const name = select.getAttribute("aria-label") || label?.textContent || select.title;
    if (name) button.setAttribute("aria-label", name);
  }
  return true;
}

function syncWoodSelect(select) {
  if (!select) return;
  if (!syncWoodSelectButton(select)) return;
  if (woodSelectMenuIsOpen(select)) {
    if (select.disabled || !woodSelectParts(select).button?.getClientRects().length) {
      closeWoodSelectMenu();
      return;
    }
    renderWoodSelectMenu(select);
  }
}

function syncWoodSelects() {
  document.querySelectorAll("select").forEach(syncWoodSelect);
}

function closeWoodSelectMenu() {
  if (activeWoodSelect) {
    setWoodSelectExpanded(activeWoodSelect, false);
  }
  activeWoodSelect = null;
  activeWoodOption = null;
  if (woodSelectPopover) {
    woodSelectPopover.classList.remove("open");
    woodSelectPopover.innerHTML = "";
  }
}

function placeWoodSelectMenu(select) {
  const { button } = woodSelectParts(select);
  const pop = ensureWoodSelectPopover();
  if (!button) return;
  const rect = button.getBoundingClientRect();
  const margin = 8;
  const gap = 6;
  const width = Math.min(Math.max(rect.width, 180), window.innerWidth - margin * 2);
  pop.style.width = `${width}px`;
  pop.style.left = `${Math.max(margin, Math.min(Math.round(rect.left), window.innerWidth - width - margin))}px`;
  pop.style.maxHeight = "";
  const desiredHeight = pop.getBoundingClientRect().height;
  const below = window.innerHeight - rect.bottom - gap - margin;
  const above = rect.top - gap - margin;
  const openAbove = below < desiredHeight && above > below;
  const height = Math.max(0, Math.min(desiredHeight, openAbove ? above : below));
  pop.style.maxHeight = `${height}px`;
  pop.style.top = `${Math.max(margin, Math.round(openAbove ? rect.top - height - gap : rect.bottom + gap))}px`;
}

function woodOptionDisabled(opt) {
  return !opt || opt.disabled || opt.hidden || opt.closest("optgroup")?.disabled;
}

function chooseWoodSelectOption(select, opt) {
  if (!select || select.disabled || !select.contains(opt) || woodOptionDisabled(opt)) return;
  select.selectedIndex = opt.index;
  // Close first: change handlers can rebuild options, hide the field, or start a game.
  closeWoodSelectMenu();
  select.dispatchEvent(new Event("input", { bubbles: true }));
  select.dispatchEvent(new Event("change", { bubbles: true }));
  syncWoodSelect(select);
}

function createWoodSelectOption() {
  const item = document.createElement("div");
  item.className = "wood-select-option";
  item.setAttribute("role", "option");
  return item;
}

function renderWoodSelectMenu(select) {
  const pop = ensureWoodSelectPopover();
  const options = Array.from(select.options);
  const previousValue = activeWoodOption?.value;
  activeWoodOption = options.find(opt => !woodOptionDisabled(opt) && opt === activeWoodOption)
    || options.find(opt => !woodOptionDisabled(opt) && opt.value === previousValue)
    || options.find(opt => !woodOptionDisabled(opt) && opt.selected)
    || options.find(opt => !woodOptionDisabled(opt)) || null;
  // Update in place so a delayed label refresh cannot discard a pointer target
  // or reset the scroll position while someone is choosing from a long list.
  options.forEach((opt, index) => {
    const item = pop.children[index] || pop.appendChild(createWoodSelectOption());
    woodOptionElements.set(item, opt);
    item.id = `${WOOD_SELECT_POPOVER_ID}-option-${index}`;
    if (item.textContent !== opt.label) item.textContent = opt.label;
    item.hidden = opt.hidden;
    item.classList.toggle("disabled", !!woodOptionDisabled(opt));
    item.classList.toggle("active", opt === activeWoodOption);
    item.setAttribute("aria-disabled", woodOptionDisabled(opt) ? "true" : "false");
    item.setAttribute("aria-selected", opt.selected ? "true" : "false");
  });
  while (pop.children.length > options.length) pop.lastElementChild.remove();
  pop.classList.add("open");
  placeWoodSelectMenu(select);
  updateWoodSelectActiveOption(select);
}

function updateWoodSelectActiveOption(select, reveal = false) {
  const { button } = woodSelectParts(select);
  let activeItem = null;
  for (const item of woodSelectPopover?.children || []) {
    const active = woodOptionElements.get(item) === activeWoodOption;
    item.classList.toggle("active", active);
    if (active) activeItem = item;
  }
  if (!activeItem) {
    button?.removeAttribute("aria-activedescendant");
    return;
  }
  button?.setAttribute("aria-activedescendant", activeItem.id);
  if (!reveal) return;
  const pop = woodSelectPopover;
  if (activeItem.offsetTop < pop.scrollTop) pop.scrollTop = activeItem.offsetTop;
  else if (activeItem.offsetTop + activeItem.offsetHeight > pop.scrollTop + pop.clientHeight) {
    pop.scrollTop = activeItem.offsetTop + activeItem.offsetHeight - pop.clientHeight;
  }
}

function openWoodSelectMenu(select) {
  if (!select || select.disabled) return;
  if (woodSelectMenuIsOpen(select)) {
    closeWoodSelectMenu();
    return;
  }
  closeWoodSelectMenu();
  activeWoodSelect = select;
  activeWoodOption = selectedOption(select);
  setWoodSelectExpanded(select, true);
  renderWoodSelectMenu(select);
  updateWoodSelectActiveOption(select, true);
}

function moveWoodSelectActiveOption(select, key) {
  const options = Array.from(select.options).filter(opt => !woodOptionDisabled(opt));
  if (!options.length) return;
  const index = options.indexOf(activeWoodOption);
  const nextIndex = key === "Home" ? 0 : key === "End" ? options.length - 1
    : Math.max(0, Math.min(options.length - 1, index + (key === "ArrowUp" ? -1 : 1)));
  activeWoodOption = options[nextIndex];
  updateWoodSelectActiveOption(select, true);
}

function handleWoodSelectWheel(event) {
  if (!activeWoodSelect || event.ctrlKey || !event.deltaY || Math.abs(event.deltaX) > Math.abs(event.deltaY)) return;
  const pop = woodSelectPopover;
  // Long lists keep native wheel/trackpad scrolling. A short list has no scroll
  // range, so browse its options without committing until click or Enter.
  if (pop.scrollHeight > pop.clientHeight + 1) return;
  event.preventDefault();
  event.stopPropagation();
  moveWoodSelectActiveOption(activeWoodSelect, event.deltaY < 0 ? "ArrowUp" : "ArrowDown");
}

function handleWoodSelectKeydown(select, e) {
  if (select.disabled) return;
  const open = woodSelectMenuIsOpen(select);
  if (e.key === "Tab") {
    if (open && activeWoodOption) chooseWoodSelectOption(select, activeWoodOption);
    else closeWoodSelectMenu();
    return;
  }
  const navigation = ["ArrowDown", "ArrowUp", "Home", "End"].includes(e.key);
  const confirmation = e.key === "Enter" || e.key === " ";
  if (!navigation && !confirmation && e.key !== "Escape") return;
  e.preventDefault();
  // Review shortcuts must not consume combobox navigation or cancellation.
  e.stopPropagation();
  if (e.key === "Escape") {
    closeWoodSelectMenu();
  } else if (!open) {
    openWoodSelectMenu(select);
    if (e.key === "Home" || e.key === "End") moveWoodSelectActiveOption(select, e.key);
  } else if (confirmation) {
    if (activeWoodOption) chooseWoodSelectOption(select, activeWoodOption);
    else closeWoodSelectMenu();
  } else {
    moveWoodSelectActiveOption(select, e.key);
  }
}

function createWoodSelectButton(select) {
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "wood-select-button";
  btn.setAttribute("role", "combobox");
  btn.setAttribute("aria-haspopup", "listbox");
  btn.setAttribute("aria-controls", WOOD_SELECT_POPOVER_ID);
  btn.setAttribute("aria-expanded", "false");
  btn.innerHTML = '<span class="wood-select-value"></span>';
  btn.addEventListener("click", (e) => {
    e.preventDefault();
    openWoodSelectMenu(select);
  });
  btn.addEventListener("keydown", (e) => handleWoodSelectKeydown(select, e));
  return btn;
}

function enhanceWoodSelect(select) {
  if (!select || select.dataset.woodEnhanced === "1") return;
  select.dataset.woodEnhanced = "1";
  select.classList.add("wood-select-native");
  select.tabIndex = -1;
  select.setAttribute("aria-hidden", "true");
  const wrap = document.createElement("span");
  wrap.className = "wood-select";
  select.parentNode.insertBefore(wrap, select);
  wrap.appendChild(select);
  wrap.appendChild(createWoodSelectButton(select));
  select.addEventListener("change", () => syncWoodSelect(select));
  syncWoodSelect(select);
}

function enhanceWoodSelects() {
  document.querySelectorAll("select").forEach(enhanceWoodSelect);
}

function pointerIsInsideActiveWoodSelect(target) {
  if (!activeWoodSelect) return false;
  const { wrap } = woodSelectParts(activeWoodSelect);
  const pop = ensureWoodSelectPopover();
  return targetIsInside(wrap, target) || targetIsInside(pop, target);
}

function targetIsInside(container, target) {
  return !!(container && target instanceof Node && container.contains(target));
}

document.addEventListener("mousedown", (e) => {
  if (!activeWoodSelect) return;
  if (pointerIsInsideActiveWoodSelect(e.target)) return;
  closeWoodSelectMenu();
});

document.addEventListener("focusin", event => {
  if (activeWoodSelect && !pointerIsInsideActiveWoodSelect(event.target)) closeWoodSelectMenu();
});

window.addEventListener("resize", () => {
  if (activeWoodSelect) placeWoodSelectMenu(activeWoodSelect);
});

document.addEventListener("scroll", (event) => {
  if (!activeWoodSelect || targetIsInside(woodSelectPopover, event.target)) return;
  closeWoodSelectMenu();
}, true);

window.enhanceWoodSelects = enhanceWoodSelects;
window.syncWoodSelect = syncWoodSelect;
window.syncWoodSelects = syncWoodSelects;
window.closeWoodSelectMenu = closeWoodSelectMenu;
})();
