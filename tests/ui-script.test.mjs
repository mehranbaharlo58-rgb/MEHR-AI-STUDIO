import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";

const html = readFileSync(new URL("../ui/index.html", import.meta.url), "utf8");
const scripts = [...html.matchAll(/<script>([\\s\\S]*?)<\\/script>/gi)].map((match) => match[1]);

test("dashboard contains one parseable inline application script", () => {
  assert.equal(scripts.length, 1);
  assert.doesNotThrow(() => new vm.Script(scripts[0]));
});

test("dashboard keeps API credentials out of committed frontend storage", () => {
  assert.match(html, /sessionStorage\\.setItem\\("mehr-api-token"/);
  assert.doesNotMatch(html, /localStorage\\.setItem\\("mehr-api-token"/);
  assert.match(html, /Authorization:\\s*"Bearer "\\s*\\+\\s*c\\.token/);
});

test("dashboard warns that file selection is not a real upload", () => {
  assert.match(html, /File names shown only; upload\\/content processing is not implemented yet/);
});
