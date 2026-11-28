import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";

const html = readFileSync(new URL("../ui/index.html", import.meta.url), "utf8");
const scriptStart = html.indexOf("<script>");
const scriptEnd = html.indexOf("</script>", scriptStart);
const appScript = html.slice(scriptStart + 8, scriptEnd);

test("dashboard contains one parseable inline application script", () => {
  assert.notEqual(scriptStart, -1);
  assert.notEqual(scriptEnd, -1);
  assert.equal(html.indexOf("<script>", scriptEnd), -1);
  assert.doesNotThrow(() => new vm.Script(appScript));
});

test("dashboard keeps API credentials in session-only browser storage", () => {
  assert.ok(html.includes('sessionStorage.setItem("mehr-api-token"'));
  assert.ok(!html.includes('localStorage.setItem("mehr-api-token"'));
  assert.ok(html.includes('Authorization:"Bearer "+c.token'));
});

test("dashboard warns that file selection is not a real upload", () => {
  assert.ok(html.includes("File names shown only; upload/content processing is not implemented yet"));
});

const liveHtml = readFileSync(new URL("../ui/live-room.html", import.meta.url), "utf8");
const liveStart = liveHtml.indexOf("<script>");
const liveEnd = liveHtml.indexOf("</script>", liveStart);
const liveScript = liveHtml.slice(liveStart + 8, liveEnd);

test("dashboard links to Live Room and defaults to the deployed Worker URL", () => {
  assert.ok(html.includes('id="liveRoomNav"'));
  assert.ok(html.includes('window.location.href="./live-room.html"'));
  assert.ok(html.includes('https://mehr-ai-studio.mehran-baharlo58.workers.dev'));
});

test("Live Room sends text prompts through the authenticated Worker API", () => {
  assert.ok(liveHtml.includes('sessionStorage.getItem("mehr-api-token")'));
  assert.ok(liveScript.includes('"/api/generate"'));
  assert.ok(liveScript.includes('"Authorization":"Bearer "+token'));
  assert.ok(liveHtml.includes("دوربین و میکروفون در این صفحه فقط پیش‌نمایش محلی هستند"));
});

test("Live Room script parses and stops local media on page exit", () => {
  assert.notEqual(liveStart, -1);
  assert.notEqual(liveEnd, -1);
  assert.doesNotThrow(() => new vm.Script(liveScript));
  assert.ok(liveScript.includes('window.addEventListener("pagehide",stopMedia)'));
  assert.ok(liveScript.includes('getTracks().forEach(t=>t.stop())'));
});
