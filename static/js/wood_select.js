(() => {
let activeWoodSelect = null;
let woodSelectPopover = null;

function ensureWoodSelectPopover() {
  if (woodSelectPopover) return woodSelectPopover;
  woodSelectPopover = document.createElement("div");
  woodSelectPopover.className = "wood-select-popover";
  document.body.appendChild(woodSelectPopover);
  return woodSelectPopover;
}

function selectedOption(select) {
  return select?.selectedOptions?.[0] || Array.from(select?.options || []).find(opt => opt.selected) || select?.options?.[0] || null;
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
  return opt ? opt.textContent : "";
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
  if (button) button.setAttribute("aria-expanded", expanded ? "true" : "false");
}

function syncWoodSelectButton(select) {
  const { wrap, button, value } = woodSelectParts(select);
  if (!wrap) return false;
  if (value) value.textContent = selectedOptionLabel(select);
  if (button) {
    button.disabled = !!select.disabled;
    button.setAttribute("aria-expanded", wrap.classList.contains("open") ? "true" : "false");
  }
  return true;
}

function syncWoodSelect(select) {
  if (!select) return;
  if (!syncWoodSelectButton(select)) return;
  if (woodSelectMenuIsOpen(select)) {
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
  const width = Math.max(rect.width, 180);
  pop.style.width = `${width}px`;
  pop.style.left = `${Math.round(rect.left)}px`;
  pop.style.top = `${Math.round(rect.bottom + 6)}px`;
  const popRect = pop.getBoundingClientRect();
  if (popRect.bottom > window.innerHeight - 8) {
    pop.style.top = `${Math.max(8, Math.round(rect.top - popRect.height - 6))}px`;
  }
}

function chooseWoodSelectOption(select, opt) {
  select.value = opt.value;
  select.dispatchEvent(new Event("change", { bubbles: true }));
  syncWoodSelect(select);
  closeWoodSelectMenu();
}

function createWoodSelectOption(select, opt) {
  const item = document.createElement("div");
  item.className = "wood-select-option" + (opt.disabled ? " disabled" : "");
  item.textContent = opt.textContent;
  item.setAttribute("role", "option");
  item.setAttribute("aria-selected", opt.value === select.value ? "true" : "false");
  if (!opt.disabled) {
    item.addEventListener("mousedown", (e) => {
      e.preventDefault();
      chooseWoodSelectOption(select, opt);
    });
  }
  return item;
}

function renderWoodSelectMenu(select) {
  const pop = ensureWoodSelectPopover();
  pop.innerHTML = "";
  Array.from(select.options).forEach((opt) => {
    pop.appendChild(createWoodSelectOption(select, opt));
  });
  pop.classList.add("open");
  placeWoodSelectMenu(select);
}

function openWoodSelectMenu(select) {
  if (!select || select.disabled) return;
  if (woodSelectMenuIsOpen(select)) {
    closeWoodSelectMenu();
    return;
  }
  closeWoodSelectMenu();
  activeWoodSelect = select;
  setWoodSelectExpanded(select, true);
  renderWoodSelectMenu(select);
}

function woodSelectKeyOpensMenu(key) {
  return key === "Enter" || key === " " || key === "ArrowDown";
}

function handleWoodSelectKeydown(select, e) {
  if (woodSelectKeyOpensMenu(e.key)) {
    e.preventDefault();
    openWoodSelectMenu(select);
  } else if (e.key === "Escape") {
    closeWoodSelectMenu();
  }
}

function createWoodSelectButton(select) {
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "wood-select-button";
  btn.setAttribute("aria-haspopup", "listbox");
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
