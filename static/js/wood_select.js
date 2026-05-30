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

function syncWoodSelect(select) {
  if (!select) return;
  const wrap = select.closest(".wood-select");
  if (!wrap) return;
  const valueEl = wrap.querySelector(".wood-select-value");
  const btn = wrap.querySelector(".wood-select-button");
  const opt = selectedOption(select);
  if (valueEl) valueEl.textContent = opt ? opt.textContent : "";
  if (btn) {
    btn.disabled = !!select.disabled;
    btn.setAttribute("aria-expanded", wrap.classList.contains("open") ? "true" : "false");
  }
  if (activeWoodSelect === select && woodSelectPopover?.classList.contains("open")) {
    renderWoodSelectMenu(select);
  }
}

function syncWoodSelects() {
  document.querySelectorAll("select").forEach(syncWoodSelect);
}

function closeWoodSelectMenu() {
  if (activeWoodSelect) {
    const wrap = activeWoodSelect.closest(".wood-select");
    if (wrap) wrap.classList.remove("open");
    const btn = wrap?.querySelector(".wood-select-button");
    if (btn) btn.setAttribute("aria-expanded", "false");
  }
  activeWoodSelect = null;
  if (woodSelectPopover) {
    woodSelectPopover.classList.remove("open");
    woodSelectPopover.innerHTML = "";
  }
}

function placeWoodSelectMenu(select) {
  const wrap = select.closest(".wood-select");
  const btn = wrap?.querySelector(".wood-select-button");
  const pop = ensureWoodSelectPopover();
  if (!btn) return;
  const rect = btn.getBoundingClientRect();
  const width = Math.max(rect.width, 180);
  pop.style.width = `${width}px`;
  pop.style.left = `${Math.round(rect.left)}px`;
  pop.style.top = `${Math.round(rect.bottom + 6)}px`;
  const popRect = pop.getBoundingClientRect();
  if (popRect.bottom > window.innerHeight - 8) {
    pop.style.top = `${Math.max(8, Math.round(rect.top - popRect.height - 6))}px`;
  }
}

function renderWoodSelectMenu(select) {
  const pop = ensureWoodSelectPopover();
  pop.innerHTML = "";
  Array.from(select.options).forEach((opt) => {
    const item = document.createElement("div");
    item.className = "wood-select-option" + (opt.disabled ? " disabled" : "");
    item.textContent = opt.textContent;
    item.setAttribute("role", "option");
    item.setAttribute("aria-selected", opt.value === select.value ? "true" : "false");
    if (!opt.disabled) {
      item.addEventListener("mousedown", (e) => {
        e.preventDefault();
        select.value = opt.value;
        select.dispatchEvent(new Event("change", { bubbles: true }));
        syncWoodSelect(select);
        closeWoodSelectMenu();
      });
    }
    pop.appendChild(item);
  });
  pop.classList.add("open");
  placeWoodSelectMenu(select);
}

function openWoodSelectMenu(select) {
  if (!select || select.disabled) return;
  if (activeWoodSelect === select && woodSelectPopover?.classList.contains("open")) {
    closeWoodSelectMenu();
    return;
  }
  closeWoodSelectMenu();
  activeWoodSelect = select;
  const wrap = select.closest(".wood-select");
  wrap?.classList.add("open");
  const btn = wrap?.querySelector(".wood-select-button");
  if (btn) btn.setAttribute("aria-expanded", "true");
  renderWoodSelectMenu(select);
}

function enhanceWoodSelect(select) {
  if (!select || select.dataset.woodEnhanced === "1") return;
  select.dataset.woodEnhanced = "1";
  select.classList.add("wood-select-native");
  const wrap = document.createElement("span");
  wrap.className = "wood-select";
  select.parentNode.insertBefore(wrap, select);
  wrap.appendChild(select);
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
  btn.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " " || e.key === "ArrowDown") {
      e.preventDefault();
      openWoodSelectMenu(select);
    } else if (e.key === "Escape") {
      closeWoodSelectMenu();
    }
  });
  wrap.appendChild(btn);
  select.addEventListener("change", () => syncWoodSelect(select));
  syncWoodSelect(select);
}

function enhanceWoodSelects() {
  document.querySelectorAll("select").forEach(enhanceWoodSelect);
}

document.addEventListener("mousedown", (e) => {
  if (!activeWoodSelect) return;
  const wrap = activeWoodSelect.closest(".wood-select");
  const pop = ensureWoodSelectPopover();
  if (wrap?.contains(e.target) || pop.contains(e.target)) return;
  closeWoodSelectMenu();
});

window.addEventListener("resize", () => {
  if (activeWoodSelect) placeWoodSelectMenu(activeWoodSelect);
});

document.addEventListener("scroll", () => {
  if (activeWoodSelect) closeWoodSelectMenu();
}, true);
