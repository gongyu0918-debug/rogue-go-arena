import { chromium } from "playwright";

const DEFAULT_URL = "http://127.0.0.1:8876/";
const urlArg = process.argv.find((arg) => arg.startsWith("--url="));
const targetUrl = urlArg ? urlArg.slice("--url=".length) : process.env.LEGACY_WOOD_SELECT_URL || DEFAULT_URL;

async function launchBrowser() {
  try {
    return await chromium.launch({ channel: "msedge", headless: true });
  } catch {
    return chromium.launch({ headless: true });
  }
}

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

async function assertKeyboardOpensMenu(page, selector, key) {
  await page.locator(selector).focus();
  await page.keyboard.press(key);
  await page.locator(".wood-select-popover.open").waitFor({ state: "visible", timeout: 5000 });
  const ariaExpanded = await page.locator(selector).getAttribute("aria-expanded");
  assert(ariaExpanded === "true", `${key} did not expand wood select`);
  await page.keyboard.press("Escape");
  await page.waitForFunction(() => !document.querySelector(".wood-select-popover")?.classList.contains("open"));
}

const browser = await launchBrowser();
const page = await browser.newPage({ viewport: { width: 1366, height: 768 }, deviceScaleFactor: 1 });
const errors = [];

page.on("pageerror", (error) => errors.push(error.message));
page.on("console", (message) => {
  if (message.type() === "error") errors.push(message.text());
});

try {
  await page.goto(targetUrl, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(700);
  await page.locator("#board-canvas").waitFor({ state: "visible", timeout: 10000 });

  await page.locator("#btn-setup").click();
  await page.locator("#setup-modal.show").waitFor({ state: "visible", timeout: 5000 });

  const initialState = await page.evaluate(() => {
    const select = document.querySelector("#sel-size");
    const wrapper = select?.closest(".wood-select");
    const button = wrapper?.querySelector(".wood-select-button");
    return {
      enhanced: select?.dataset.woodEnhanced === "1",
      nativeHidden: select?.classList.contains("wood-select-native") || false,
      buttonText: button?.textContent?.trim() || "",
      ariaExpanded: button?.getAttribute("aria-expanded") || "",
      publicFns: [
        typeof window.enhanceWoodSelects,
        typeof window.syncWoodSelect,
        typeof window.syncWoodSelects,
        typeof window.closeWoodSelectMenu,
      ],
      privateFns: [
        typeof window.woodSelectParts,
        typeof window.selectedOptionLabel,
        typeof window.woodSelectMenuIsOpen,
        typeof window.createWoodSelectOption,
        typeof window.handleWoodSelectKeydown,
      ],
    };
  });

  assert(initialState.enhanced, "board size select was not enhanced");
  assert(initialState.nativeHidden, "native select did not receive wood-select-native class");
  assert(initialState.buttonText.includes("19"), `unexpected initial button text: ${initialState.buttonText}`);
  assert(initialState.ariaExpanded === "false", "wood select should start collapsed");
  assert(
    initialState.publicFns.every((type) => type === "function"),
    `wood select public functions missing: ${initialState.publicFns.join(", ")}`
  );
  assert(
    initialState.privateFns.every((type) => type === "undefined"),
    `wood select private helpers leaked globally: ${initialState.privateFns.join(", ")}`
  );

  const disabledButtonState = await page.evaluate(() => {
    const select = document.querySelector("#sel-handicap");
    const button = select?.closest(".wood-select")?.querySelector(".wood-select-button");
    const wasDisabled = select?.disabled || false;
    if (select) select.disabled = true;
    window.syncWoodSelect(select);
    const buttonDisabled = button?.disabled || false;
    if (select) select.disabled = wasDisabled;
    window.syncWoodSelect(select);
    return {
      buttonDisabled,
      restoredDisabled: button?.disabled || false,
    };
  });

  assert(disabledButtonState.buttonDisabled, "disabled native select did not disable wood select button");
  assert(!disabledButtonState.restoredDisabled, "wood select button did not restore after native select was enabled");

  await assertKeyboardOpensMenu(page, "#sel-size + .wood-select-button", "Enter");
  await assertKeyboardOpensMenu(page, "#sel-size + .wood-select-button", "Space");

  await page.locator("#sel-size + .wood-select-button").focus();
  await page.keyboard.press("ArrowDown");
  await page.locator(".wood-select-popover.open").waitFor({ state: "visible", timeout: 5000 });
  const keyboardOpenState = await page.evaluate(() => {
    const button = document.querySelector("#sel-size")?.closest(".wood-select")?.querySelector(".wood-select-button");
    return {
      ariaExpanded: button?.getAttribute("aria-expanded") || "",
      selectedOption: Array.from(document.querySelectorAll(".wood-select-popover.open .wood-select-option"))
        .find((item) => item.getAttribute("aria-selected") === "true")
        ?.textContent?.trim() || "",
    };
  });

  assert(keyboardOpenState.ariaExpanded === "true", "ArrowDown did not expand wood select");
  assert(keyboardOpenState.selectedOption.includes("19×19"), `selected option was not marked: ${keyboardOpenState.selectedOption}`);
  await page.keyboard.press("Escape");
  await page.waitForFunction(() => !document.querySelector(".wood-select-popover")?.classList.contains("open"));

  await page.locator("#sel-size + .wood-select-button").click();
  await page.locator(".wood-select-popover.open").waitFor({ state: "visible", timeout: 5000 });
  await page.locator(".wood-select-popover.open .wood-select-option", { hasText: "13×13" }).click();

  const selectedState = await page.evaluate(() => {
    const select = document.querySelector("#sel-size");
    const button = select?.closest(".wood-select")?.querySelector(".wood-select-button");
    const popover = document.querySelector(".wood-select-popover");
    return {
      value: select?.value || "",
      buttonText: button?.textContent?.trim() || "",
      ariaExpanded: button?.getAttribute("aria-expanded") || "",
      popoverOpen: popover?.classList.contains("open") || false,
      selectedOption: Array.from(popover?.querySelectorAll(".wood-select-option") || [])
        .find((item) => item.getAttribute("aria-selected") === "true")
        ?.textContent?.trim() || "",
    };
  });

  assert(selectedState.value === "13", `native select value did not update: ${selectedState.value}`);
  assert(selectedState.buttonText === "13×13", `button text did not update: ${selectedState.buttonText}`);
  assert(selectedState.ariaExpanded === "false", "wood select did not collapse after selection");
  assert(!selectedState.popoverOpen, "popover remained open after selecting an option");

  const disabledOptionValue = await page.evaluate(() => {
    const select = document.querySelector("#sel-komi");
    const option = document.createElement("option");
    option.value = "smoke-disabled";
    option.textContent = "Smoke Disabled";
    option.disabled = true;
    select?.appendChild(option);
    window.syncWoodSelect(select);
    return select?.value || "";
  });

  await page.locator("#sel-komi + .wood-select-button").click();
  await page.locator(".wood-select-popover.open").waitFor({ state: "visible", timeout: 5000 });
  await page.locator(".wood-select-popover.open .wood-select-option.disabled", { hasText: "Smoke Disabled" }).click();
  const disabledOptionState = await page.evaluate(() => {
    const button = document.querySelector("#sel-komi")?.closest(".wood-select")?.querySelector(".wood-select-button");
    return {
      value: document.querySelector("#sel-komi")?.value || "",
      popoverOpen: document.querySelector(".wood-select-popover")?.classList.contains("open") || false,
      ariaExpanded: button?.getAttribute("aria-expanded") || "",
    };
  });

  assert(disabledOptionState.value === disabledOptionValue, "disabled option changed the native select value");
  assert(disabledOptionState.popoverOpen, "disabled option unexpectedly closed the popover");
  assert(disabledOptionState.ariaExpanded === "true", "disabled option should leave aria-expanded true while open");

  await page.mouse.click(20, 20);
  const closedByOutsideClick = await page.evaluate(() => {
    const button = document.querySelector("#sel-komi")?.closest(".wood-select")?.querySelector(".wood-select-button");
    return {
      popoverOpen: document.querySelector(".wood-select-popover")?.classList.contains("open") || false,
      ariaExpanded: button?.getAttribute("aria-expanded") || "",
    };
  });

  assert(!closedByOutsideClick.popoverOpen, "popover did not close on outside click");
  assert(closedByOutsideClick.ariaExpanded === "false", "aria-expanded did not reset after outside click");
  assert(errors.length === 0, `browser errors: ${errors.join("; ")}`);

  console.log(JSON.stringify({ ok: true, selectedBoardSize: selectedState.value }, null, 2));
} finally {
  await browser.close();
}
