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
  assert.ok(appScript.includes('window.addEventListener("pagehide",()=>{disconnectLiveSession();stopLiveDevices();})'));
  assert.ok(appScript.includes('if(p!=="live"&&typeof stopLiveDevices==="function"){if(typeof disconnectLiveSession==="function")void disconnectLiveSession();stopLiveDevices();}'));
});


test("dashboard completes an SFU offer-answer renegotiation before marking the session connected", () => {
  assert.ok(appScript.includes('published.sessionDescription.type==="offer"&&published.requiresImmediateRenegotiation===true'));
  assert.ok(appScript.includes('await pc.createAnswer()'));
  assert.ok(appScript.includes('"/api/live/sessions/"+sessionId+"/renegotiate"'));
  assert.ok(appScript.includes('method:"PUT"'));
  assert.ok(appScript.includes('await waitForIceGathering(pc)'));
});


test("dashboard inspects sanitized SFU track state after WebRTC connects", () => {
  assert.ok(appScript.includes('liveApi("/api/live/sessions/"+sessionId)'));
  assert.ok(appScript.includes('inspection.tracks.filter(track=>track.status==="active").length'));
  assert.ok(appScript.includes("این وضعیت تضمین‌کننده رسیدن بسته‌های رسانه نیست"));
});
