from __future__ import annotations

from _path_bootstrap import ensure_repo_root

ensure_repo_root(__file__)

import asyncio
import json

from playwright.async_api import async_playwright

from tests.smoke._managed_source_server import ManagedSourceServer


async def run_probe(base_url: str) -> None:
    async with async_playwright() as pw:
        try:
            browser = await pw.chromium.launch(channel="msedge", headless=True)
        except Exception:
            browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1280, "height": 900})
        await page.goto(base_url + "/card-editor")
        await page.wait_for_selector("#advancedJsonBtn")
        await page.click("#advancedJsonBtn")

        payload = await page.evaluate(
            """
            async () => {
              const response = await fetch('/api/card-config', { cache: 'no-store' });
              return await response.json();
            }
            """
        )
        config = payload["config"]
        config["cards"]["rogue"]["puppet"]["uses"] = '" autofocus onfocus="window.__cardEditorXss=1" x="'
        spec = config["tuning"]["ROGUE_DICE_PASS_CHANCE"]
        spec["min"] = '" autofocus onfocus="window.__cardEditorXss=1" x="'
        spec["max"] = '" autofocus onfocus="window.__cardEditorXss=1" x="'
        spec["step"] = '" autofocus onfocus="window.__cardEditorXss=1" x="'

        await page.fill("#jsonText", json.dumps(config, ensure_ascii=False))
        await page.click("#applyJsonBtn")
        await page.click('[data-tab="rogue"]')
        await page.fill("#searchBox", "puppet")
        await page.locator('.card-row[data-id="puppet"] [data-field="uses"]').focus()
        await page.click('[data-tab="tuning"]')
        await page.fill("#searchBox", "ROGUE_DICE_PASS_CHANCE")
        await page.locator('.tune-row[data-key="ROGUE_DICE_PASS_CHANCE"] [data-tune="min"]').focus()

        executed = await page.evaluate("Boolean(window.__cardEditorXss)")
        await browser.close()
        if executed:
            raise AssertionError("card editor rendered executable attribute injection")


def main() -> int:
    with ManagedSourceServer(
        port=0,
        no_katago=True,
        artifact_subdir="card-editor-xss-smoke",
        startup_timeout=30.0,
    ) as server:
        asyncio.run(run_probe(server.base_url))
    print("card_editor_xss_smoke_test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
