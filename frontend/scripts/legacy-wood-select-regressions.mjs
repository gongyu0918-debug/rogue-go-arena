// Browser regressions for interactions that value-only selectOption() tests miss.
function assert(condition, message) {
  if (!condition) throw new Error(message);
}

async function selectValue(page, id, value) {
  const index = await page.locator(`#${id}`).evaluate((select, expected) => (
    Array.from(select.options).findIndex(option => option.value === expected)
  ), value);
  assert(index >= 0, `${id}: missing option ${value}`);
  await page.locator(`#${id} + .wood-select-button`).click();
  await page.locator(".wood-select-popover.open .wood-select-option").nth(index).click();
  const state = await page.locator(`#${id}`).evaluate(select => ({
    value: select.value,
    label: select.selectedOptions[0]?.textContent,
    buttonLabel: select.nextElementSibling?.textContent,
  }));
  assert(state.value === value, `${id}: expected ${value}, got ${state.value}`);
  assert(state.label === state.buttonLabel, `${id}: displayed label is stale`);
}

async function openSetup(page) {
  await page.locator("#btn-setup").click();
  await page.locator("#setup-modal.show").waitFor();
}

async function keyboardSelection(page) {
  await openSetup(page);
  const button = page.locator("#sel-size + .wood-select-button");
  await button.focus();
  await page.keyboard.press("Enter");
  await page.keyboard.press("ArrowDown");
  assert(await button.getAttribute("aria-expanded") === "true", "ArrowDown closed the open menu instead of moving to an option");
  await page.keyboard.press("Enter");
  assert(await page.locator("#sel-size").inputValue() === "13", "keyboard confirmation did not select 13x13");
  await page.keyboard.press("Space");
  await page.keyboard.press("End");
  await page.keyboard.press("Escape");
  assert(await page.locator("#sel-size").inputValue() === "13", "Escape committed a pending option");
  await page.keyboard.press("ArrowUp");
  await page.keyboard.press("Home");
  await page.keyboard.press("Space");
  assert(await page.locator("#sel-size").inputValue() === "19", "Home/Space did not confirm the first option");
  await page.keyboard.press("Enter");
  await page.keyboard.press("Tab");
  assert(await button.getAttribute("aria-expanded") === "false", "Tab left the menu open");
  assert(await page.evaluate(() => document.activeElement?.matches(".wood-select-button")), "Tab stopped on an invisible native select");

  const rankButton = page.locator("#sel-level + .wood-select-button");
  await rankButton.focus();
  await page.keyboard.press("Enter");
  await page.keyboard.press("Home");
  await page.keyboard.press("Enter");
  assert(await page.locator("#sel-level").inputValue() === "18k", "Home selected the disabled rank separator");
  await page.keyboard.press("Enter");
  await page.keyboard.press("End");
  const activeVisible = await page.evaluate(() => {
    const activeId = document.querySelector("#sel-level + .wood-select-button")?.getAttribute("aria-activedescendant");
    const active = document.getElementById(activeId || "");
    const menu = document.querySelector(".wood-select-popover.open");
    const bounds = active?.getBoundingClientRect();
    const menuBounds = menu?.getBoundingClientRect();
    return !!bounds && !!menuBounds && bounds.top >= menuBounds.top && bounds.bottom <= menuBounds.bottom;
  });
  assert(activeVisible, "last keyboard option is outside the visible rank list");
  await page.keyboard.press("Enter");
  assert(await page.locator("#sel-level").inputValue() === "p9d", "End did not select the last enabled rank");
}

async function pointerSelection(page) {
  await openSetup(page);
  const button = page.locator("#sel-size + .wood-select-button");
  await button.click();
  const option = page.locator(".wood-select-popover.open .wood-select-option").nth(1);
  await option.click({ button: "right" });
  assert(await page.locator("#sel-size").inputValue() === "19", "right mouse button changed the selection");
  const bounds = await option.boundingBox();
  assert(bounds, "option disappeared after a right click");
  await page.mouse.move(bounds.x + bounds.width / 2, bounds.y + bounds.height / 2);
  await page.mouse.down();
  assert(await page.locator("#sel-size").inputValue() === "19", "mousedown committed an option before the click completed");
  await page.mouse.up();
  assert(await page.locator("#sel-size").inputValue() === "13", "completed primary click did not select the option");
}

async function allDropdowns(page) {
  const visited = new Set();
  async function choose(id, value) {
    await selectValue(page, id, value);
    visited.add(id);
  }
  await openSetup(page);
  await choose("sel-color", "W");
  await choose("sel-size", "9");
  await choose("sel-level", "10k");
  await choose("sel-ai-style", "attack");
  await choose("sel-handicap", "2");
  assert(await page.locator("#sel-komi").inputValue() === "0", "handicap did not synchronize komi");
  assert((await page.locator("#sel-komi + .wood-select-button").textContent()).includes("0"), "komi display did not follow handicap");
  await choose("sel-komi", "6.5");
  await choose("sel-time-mode", "byoyomi");
  await choose("sel-main-time", "600");
  await choose("sel-byo-periods", "5");
  await choose("sel-byo-time", "60");
  await page.locator("#mode-watch").click();
  await choose("sel-level-black", "a2d");
  await choose("sel-level-white", "a4d");
  await choose("sel-ai-style-black", "territory");
  await choose("sel-ai-style-white", "influence");
  await page.locator("#mode-rogue").click();
  await choose("sel-rogue-variant", "dual");
  await page.locator("#setup-modal .modal-close").click();
  await page.locator("#btn-settings").click();
  await page.locator("#settings-drawer.open").waitFor();
  await choose("sel-placement", "fine");
  await choose("sel-stage-preset", "1080");
  await choose("settings-language-select", "en");
  await page.locator("#settings-drawer .drawer-close").click();
  await choose("lang-toggle", "zh");
  const ids = await page.locator("select[data-wood-enhanced='1']").evaluateAll(selects => selects.map(select => select.id));
  assert(ids.every(id => visited.has(id)), `untested dropdowns: ${ids.filter(id => !visited.has(id)).join(", ")}`);
  return { dropdownCount: visited.size };
}

async function delayedGpuDefaults(page, releaseGpu) {
  await openSetup(page);
  await selectValue(page, "sel-level", "10k");
  await page.locator("#sel-level + .wood-select-button").click();
  const menu = page.locator(".wood-select-popover.open");
  const bounds = await menu.boundingBox();
  await page.mouse.move(bounds.x + bounds.width / 2, bounds.y + bounds.height / 2);
  await page.mouse.wheel(0, 450);
  await page.waitForFunction(() => document.querySelector(".wood-select-popover.open")?.scrollTop > 0);
  // mouse.wheel() returns before Chromium finishes its scroll animation.
  await page.waitForTimeout(180);
  const scrollTop = await menu.evaluate(element => element.scrollTop);
  releaseGpu();
  await page.waitForFunction(() => document.querySelector("#sel-level option[value='a1d']")?.dataset.slowMarked === "1");
  assert(await page.locator("#sel-level").inputValue() === "10k", "late GPU response overwrote the user's rank selection");
  assert(await page.locator("#sel-level-black").inputValue() === "5k", "GPU default was not applied to an untouched rank");
  assert(await page.locator("#sel-level-white").inputValue() === "5k", "GPU default was not applied to the untouched white rank");
  const refreshedScrollTop = await menu.evaluate(element => element.scrollTop);
  assert(refreshedScrollTop === scrollTop, `asynchronous option-label sync reset the open rank list scroll position: ${scrollTop} -> ${refreshedScrollTop}`);
  const amateurIndex = await page.locator("#sel-level").evaluate(select => Array.from(select.options).findIndex(option => option.value === "a1d"));
  assert((await menu.locator(".wood-select-option").nth(amateurIndex).textContent()).includes("⚠"), "open menu labels did not refresh after GPU detection");
}

async function menuRefresh(page) {
  await openSetup(page);
  await page.locator("#sel-level + .wood-select-button").click();
  const menu = page.locator(".wood-select-popover.open");
  const bounds = await menu.boundingBox();
  await page.mouse.move(bounds.x + bounds.width / 2, bounds.y + bounds.height / 2);
  await page.mouse.wheel(0, 350);
  await page.waitForFunction(() => document.querySelector(".wood-select-popover.open")?.scrollTop > 0);
  const scrollTop = await menu.evaluate(element => element.scrollTop);
  await page.evaluate(() => window.syncWoodSelects());
  assert(await menu.evaluate(element => element.scrollTop) === scrollTop, "refreshing controls reset the scrolled rank menu");
  await page.evaluate(() => window.closeSetupModal());
  assert(await page.locator(".wood-select-popover.open").count() === 0, "closing setup left an orphaned dropdown");

  await page.locator("#btn-settings").click();
  await page.locator("#sel-placement + .wood-select-button").click();
  await page.evaluate(() => window.closeSettingsDrawer());
  assert(await page.locator(".wood-select-popover.open").count() === 0, "closing settings left an orphaned dropdown");
}

async function shortMenuWheel(page) {
  await openSetup(page);
  await page.locator("#sel-size + .wood-select-button").click();
  const bounds = await page.locator(".wood-select-popover.open").boundingBox();
  await page.mouse.move(bounds.x + bounds.width / 2, bounds.y + bounds.height / 2);
  for (const [delta, label] of [[120, "13×13"], [120, "9×9"], [120, "9×9"], [-120, "13×13"]]) {
    await page.mouse.wheel(0, delta);
    await page.waitForTimeout(80);
    const state = await page.evaluate(() => {
      const button = document.querySelector("#sel-size + .wood-select-button");
      const activeId = button.getAttribute("aria-activedescendant");
      return { expanded: button.getAttribute("aria-expanded"),
        label: document.getElementById(activeId)?.textContent,
        value: document.querySelector("#sel-size").value };
    });
    assert(state.expanded === "true", "wheel closed a short dropdown");
    assert(state.label === label, `short-menu wheel did not browse the expected option: ${JSON.stringify(state)}`);
    assert(state.value === "19", "wheel committed a selection without confirmation");
  }
  await page.keyboard.press("Enter");
  assert(await page.locator("#sel-size").inputValue() === "13", "Enter did not confirm the wheel-highlighted option");
}

async function longMenuWheel(page) {
  // This real small-window layout makes the document scrollable behind the menu.
  await page.setViewportSize({ width: 900, height: 600 });
  assert(await page.evaluate(() => document.scrollingElement.scrollHeight > window.innerHeight), "wheel fixture must have scrollable background content");
  await openSetup(page);
  await page.locator("#sel-level + .wood-select-button").click();
  const menu = page.locator(".wood-select-popover.open");
  const bounds = await menu.boundingBox();
  const outsideBefore = await page.evaluate(() => ({
    document: window.scrollY,
    setup: document.querySelector("#setup-modal .modal-content").scrollTop,
  }));
  await page.mouse.move(bounds.x + bounds.width / 2, bounds.y + bounds.height / 2);
  const before = await menu.evaluate(element => element.scrollTop);
  await page.mouse.wheel(0, 200);
  await page.waitForTimeout(120);
  assert(await menu.evaluate(element => element.scrollTop) > before, "wheel did not scroll the long rank list");
  for (const delta of [10000, 240, -10000, -240]) {
    await page.mouse.wheel(0, delta);
    await page.waitForTimeout(120);
    const state = await page.evaluate(() => ({
      open: document.querySelector(".wood-select-popover")?.classList.contains("open"),
      document: window.scrollY,
      setup: document.querySelector("#setup-modal .modal-content").scrollTop,
    }));
    assert(state.open, `wheel at the rank-list boundary closed the dropdown: ${JSON.stringify(state)}`);
    assert(state.document === outsideBefore.document && state.setup === outsideBefore.setup,
      `wheel scrolled the page behind the dropdown: ${JSON.stringify(state)}`);
  }
}

export async function runWoodSelectRegressions(browser, targetUrl) {
  const cases = [
    ["keyboard", keyboardSelection],
    ["pointer", pointerSelection],
    ["all-dropdowns", allDropdowns],
    ["delayed-gpu", delayedGpuDefaults],
    ["menu-refresh", menuRefresh],
    ["wheel-short", shortMenuWheel],
    ["wheel-long", longMenuWheel],
  ];
  const results = [];
  for (const [name, scenario] of cases) {
    const page = await browser.newPage({ viewport: { width: 1366, height: 768 } });
    page.setDefaultTimeout(7000);
    const errors = [];
    page.on("pageerror", error => errors.push(error.message));
    let release;
    const gate = new Promise(resolve => { release = resolve; });
    await page.route("**/gpu", async route => {
      if (name === "delayed-gpu") await gate;
      await route.fulfill({ json: { default_rank: "5k", slow_from: "a1d" } });
    });
    try {
      const url = new URL(targetUrl);
      url.searchParams.set("lang", "zh");
      await page.goto(url.href, { waitUntil: "domcontentloaded" });
      await page.locator("#board-canvas").waitFor();
      await page.locator("#sel-size + .wood-select-button").waitFor({ state: "attached" });
      const details = await scenario(page, release);
      assert(errors.length === 0, `browser errors: ${errors.join("; ")}`);
      results.push({ name, ok: true, ...details });
    } catch (error) {
      results.push({ name, ok: false, error: error.message });
    } finally {
      release();
      await page.close();
    }
  }
  console.log(JSON.stringify({ woodSelectRegressions: results }, null, 2));
  assert(results.every(result => result.ok), "wood select interaction regressions failed (see cases above)");
}
