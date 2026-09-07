import { spawnSync } from "node:child_process";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { launchBrowser } from "./smoke-browser.mjs";

const root = fileURLToPath(new URL("../../", import.meta.url));
const option = (name, fallback) => process.argv.find(arg => arg.startsWith(`--${name}=`))?.slice(name.length + 3) || fallback;
const baseUrl = new URL(option("url", "http://127.0.0.1:8890/"));
const outputDir = path.resolve(root, option("output", "output/browser-compatibility"));
const scenarios = [
  "legacy-bootstrap", "legacy-wood-select", "legacy-rank-controls", "legacy-settings-controls",
  "legacy-setup-controls", "legacy-localization", "legacy-inline-actions", "legacy-responsive",
  "legacy-visual-effects", "legacy-hint-overlay", "legacy-card-overlays", "legacy-review-sgf",
  "legacy-network-client", "legacy-edge109-compat", "react-preview",
];

await mkdir(outputDir, { recursive: true });
const browser = await launchBrowser();
const report = {
  baseUrl: baseUrl.href,
  browserVersion: browser.version(),
  executable: process.env.SMOKE_BROWSER_EXECUTABLE || "system Edge or bundled Chromium",
  expectedMajor: process.env.SMOKE_BROWSER_MAJOR || null,
  results: [],
};
await browser.close();
for (const scenario of scenarios) {
  const script = path.join(root, "frontend/scripts", `${scenario}-smoke.mjs`);
  const url = new URL(scenario === "react-preview" ? "/react-preview" : "/", baseUrl).href;
  const result = spawnSync(process.execPath, [script, `--url=${url}`], {
    cwd: root, env: process.env, encoding: "utf8", timeout: 180000, maxBuffer: 8 * 1024 * 1024,
  });
  await writeFile(path.join(outputDir, `${scenario}.log`), (result.stdout || "") + (result.stderr || ""));
  const entry = { scenario, exitCode: result.status, error: result.error?.message || null };
  report.results.push(entry);
  await writeFile(path.join(outputDir, "report.json"), JSON.stringify(report, null, 2));
  console.log(JSON.stringify(entry));
}
const failures = report.results.filter(result => result.exitCode !== 0);
console.log(JSON.stringify({ browserVersion: report.browserVersion, passed: scenarios.length - failures.length,
  total: scenarios.length, report: path.join(outputDir, "report.json") }));
process.exitCode = failures.length ? 1 : 0;
