import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";

const html = readFileSync(new URL("../ui/index.html", import.meta.url), "utf8");
const scriptStart = html.indexOf("<script>");
const scriptEnd = html.indexOf("</script>", scriptStart);
const appScript = html.slice(scriptStart + 8, scriptEnd);

test("dashboard defaults to Persian right-to-left layout", () => {
  assert.ok(html.includes('<html lang="fa" dir="rtl">'));
  assert.ok(appScript.endsWith('language("fa");\n'));
});

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


test("MEHR Live exposes local microphone and camera controls without claiming AI connectivity", () => {
  assert.ok(html.includes('id="livePanel"'));
  assert.ok(html.includes('id="liveMicStart"'));
  assert.ok(html.includes('id="liveCameraStart"'));
  assert.ok(html.includes("ارتباط هوش مصنوعی متصل نیست"));
  assert.ok(html.includes("هیچ داده‌ای ارسال نمی‌شود"));
});

test("MEHR Live uses separate local media permissions and stops tracks", () => {
  assert.ok(appScript.includes('getUserMedia({audio:true,video:false})'));
  assert.ok(appScript.includes('getUserMedia({audio:false,video:'));
  assert.ok(appScript.includes('getTracks().forEach(t=>t.stop())'));
  assert.ok(appScript.includes('window.addEventListener("pagehide",stopLiveDevices)'));
  assert.ok(appScript.includes('if(p!=="live"&&typeof stopLiveDevices==="function")stopLiveDevices()'));
});


const liveHtml = readFileSync(new URL("../ui/live-room.html", import.meta.url), "utf8");
const liveStart = liveHtml.indexOf("<script>");
const liveEnd = liveHtml.indexOf("</script>", liveStart);
const liveScript = liveHtml.slice(liveStart + 8, liveEnd);

test("M.B Live Room is an explicit local preview, not a fake connected AI call", () => {
  assert.ok(liveHtml.includes("هنوز به عامل هوش مصنوعی یا سرویس تماس زنده متصل نیست"));
  assert.ok(liveHtml.includes("هنوز پیکربندی نشده"));
  assert.ok(liveHtml.includes("اتصال امن به API و احراز هویت هنوز پیاده‌سازی نشده است"));
  assert.doesNotMatch(liveScript, /fetch\s*\(|new WebSocket|RTCPeerConnection/);
});

test("M.B Live Room script parses and has separate media controls", () => {
  assert.notEqual(liveStart, -1);
  assert.notEqual(liveEnd, -1);
  assert.doesNotThrow(() => new vm.Script(liveScript));
  assert.ok(liveScript.includes('getUserMedia({video,audio})'));
  assert.ok(liveScript.includes('getTracks().forEach(t=>t.stop())'));
});

test("M.B Live Room handles denied permissions and stops media on page exit", () => {
  assert.ok(liveScript.includes('error?.name==="NotAllowedError"'));
  assert.ok(liveScript.includes('window.addEventListener("pagehide",stopMedia)'));
  assert.ok(liveScript.includes('navigator.mediaDevices?.getUserMedia'));
});

test("dashboard links to the compact M.B Live Room page", () => {
  assert.ok(html.includes('href="./live-room.html"'));
  assert.ok(html.includes("باز کردن M.B Live Room فشرده"));
});
