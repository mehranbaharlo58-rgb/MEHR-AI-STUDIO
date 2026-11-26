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


test("MEHR Live exposes separate media controls and clearly discloses sampled camera transmission", () => {
  assert.ok(html.includes('id="livePanel"'));
  assert.ok(html.includes('id="liveMicStart"'));
  assert.ok(html.includes('id="liveCameraStart"'));
  assert.ok(html.includes("فریم‌های ثابت هر ۳ ثانیه ارسال می‌شوند"));
  assert.ok(html.includes("صدا فقط هنگام اتصال به مدل ارسال می‌شود"));
});

test("MEHR Live uses separate local media permissions and stops tracks", () => {
  assert.ok(appScript.includes('getUserMedia({audio:true,video:false})'));
  assert.ok(appScript.includes('getUserMedia({audio:false,video:'));
  assert.ok(appScript.includes('getTracks().forEach(t=>t.stop())'));
  assert.ok(appScript.includes('window.addEventListener("pagehide",()=>{disconnectLiveSession();stopLiveDevices();})'));
  assert.ok(appScript.includes('if(p!=="live"&&typeof stopLiveDevices==="function"){if(typeof disconnectLiveSession==="function")void disconnectLiveSession();stopLiveDevices();}'));
});


test("MEHR Live uses authenticated direct Realtime WebRTC with server-held credentials", () => {
  assert.ok(html.includes('id="liveOidcLogin"'));
  assert.ok(appScript.includes('"/api/live/realtime/calls"'));
  assert.ok(appScript.includes('pc.createDataChannel("oai-events")'));
  assert.ok(appScript.includes('await pc.setRemoteDescription({type:"answer",sdp:answer})'));
  assert.ok(appScript.includes('liveAccessToken||$("#liveOidcToken").value.trim()'));
});

test("browser OIDC login uses Authorization Code with PKCE S256 and state validation", () => {
  assert.ok(appScript.includes('code_challenge_method","S256"'));
  assert.ok(appScript.includes('code_verifier:verifier'));
  assert.ok(appScript.includes('params.get("state")!==expectedState'));
  assert.ok(appScript.includes('liveAccessToken=tokens.access_token'));
  assert.ok(!appScript.includes('sessionStorage.setItem("mehr-oidc-access-token"'));
});

test("camera vision sends bounded sampled still images and pauses while the page is hidden", () => {
  assert.ok(appScript.includes('setInterval(()=>sendSampledCameraFrame(active.channel),3000)'));
  assert.ok(appScript.includes("document.hidden"));
  assert.ok(appScript.includes('640/video.videoWidth'));
  assert.ok(appScript.includes('channel.bufferedAmount>512*1024'));
  assert.ok(appScript.includes('type:"input_image",detail:"low"'));
  assert.ok(appScript.includes('clearInterval(active.frameTimer)'));
});

test("stopping the camera preserves an active voice connection", () => {
  const start = appScript.indexOf("function stopLiveCamera()");
  const end = appScript.indexOf("function stopLiveDevices()", start);
  assert.ok(start >= 0 && end > start);
  const stopCamera = appScript.slice(start, end);
  assert.ok(stopCamera.includes("clearInterval(active.frameTimer)"));
  assert.ok(!stopCamera.includes("disconnectLiveSession"));
  assert.ok(stopCamera.includes("stopSfuVideoBridge(active)"));
});

test("Realtime connect button prevents duplicate concurrent sessions", () => {
  assert.ok(appScript.includes("if(liveConnection){say("));
  assert.ok(appScript.includes("connect.disabled=!!liveConnection"));
});

test("Realtime remote audio playback handles browser autoplay restrictions", () => {
  assert.ok(appScript.includes("const playResult=playback.play()"));
  assert.ok(appScript.includes("playResult.catch"));
});

test("MEHR Live publishes the camera to SFU and forwards JPEG frames into the Realtime vision channel", () => {
  assert.ok(appScript.includes('"/api/live/sessions"'));
  assert.ok(appScript.includes('"/publish"'));
  assert.ok(appScript.includes('"/video-adapter"'));
  assert.ok(appScript.includes('new WebSocket(adapter.viewer_url)'));
  assert.ok(appScript.includes('type:"input_image",detail:"low",image_url:imageUrl'));
  assert.ok(appScript.includes('active.sfu={sessionId,pc,socket}'));
});

test("MEHR Live tears down the SFU video session independently from the voice call", () => {
  assert.ok(appScript.includes("async function stopSfuVideoBridge(active)"));
  assert.ok(appScript.includes('method:"DELETE"'));
  assert.ok(appScript.includes('if(active?.sfu)stopSfuVideoBridge(active).catch(()=>null)'));
});

test("Realtime network failure clears the session and restores controls", () => {
  assert.ok(appScript.includes('pc.connectionState==="disconnected"'));
  assert.ok(appScript.includes('pc.connectionState==="failed"||pc.connectionState==="closed"'));
  assert.ok(appScript.includes('$("#liveConnect").disabled=false;$("#liveDisconnect").disabled=true;'));
});


test("Realtime transcript completion does not duplicate streamed transcript deltas", () => {
  assert.ok(appScript.includes("const streamedItems=new Set()"));
  assert.ok(appScript.includes("streamedItems.has(itemKey)"));
  assert.ok(appScript.includes('appendLiveTranscript("\\n")'));
});

test("dashboard copy reflects the implemented PKCE flow and required provider setup", () => {
  assert.ok(html.includes("ورود یکپارچه با Authorization Code + PKCE آماده است"));
  assert.ok(!html.includes("ورود یکپارچه Authorization Code + PKCE هنوز در حال تکمیل است"));
});
