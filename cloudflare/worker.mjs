const JSON_HEADERS = { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" };
const MAX_BODY_BYTES = 16 * 1024;
const MAX_PROMPT_CHARS = 12000;
const MAX_PROVIDER_RESPONSE_BYTES = 1024 * 1024;

function response(data, status, cors = {}) {
  return new Response(JSON.stringify(data), { status, headers: { ...JSON_HEADERS, ...cors } });
}

function corsHeaders(request, env) {
  const origin = request.headers.get("Origin");
  if (!origin || origin !== env.ALLOWED_ORIGIN) return null;
  return {
    "access-control-allow-origin": origin,
    "access-control-allow-methods": "GET, POST, PUT, DELETE, OPTIONS",
    "access-control-allow-headers": "Authorization, Content-Type",
    "access-control-max-age": "86400",
    "vary": "Origin",
  };
}

function equalSecret(a, b) {
  if (typeof a !== "string" || typeof b !== "string") return false;
  let diff = a.length ^ b.length;
  const n = Math.max(a.length, b.length);
  for (let i = 0; i < n; i += 1) {
    diff |= (a.charCodeAt(i) || 0) ^ (b.charCodeAt(i) || 0);
  }
  return diff === 0;
}

function trimTrailingSlashes(value) {
  let result = value;
  while (result.endsWith("/")) result = result.slice(0, -1);
  return result;
}

function authorized(request, env) {
  const configured = env.MEHR_API_TOKEN;
  const header = request.headers.get("Authorization") || "";
  const supplied = header.startsWith("Bearer ") ? header.slice(7) : "";
  return typeof configured === "string" && configured.length >= 32 &&
    equalSecret(supplied, configured);
}


function decodeBase64Url(value) {
  if (typeof value !== "string" || !/^[A-Za-z0-9_-]+$/.test(value)) throw new Error("invalid_base64url");
  const normalized = value.replace(/-/g, "+").replace(/_/g, "/");
  const binary = atob(normalized.padEnd(Math.ceil(normalized.length / 4) * 4, "="));
  return Uint8Array.from(binary, (char) => char.charCodeAt(0));
}

function parseJwtPart(value) {
  return JSON.parse(new TextDecoder().decode(decodeBase64Url(value)));
}

let jwksCache = null;

async function loadJwks(url, forceRefresh = false) {
  const now = Date.now();
  if (!forceRefresh && jwksCache && jwksCache.url === url && now - jwksCache.fetchedAt < 300000) return jwksCache.keys;
  const result = await fetch(url, { method: "GET", redirect: "manual", headers: { accept: "application/json" }, signal: AbortSignal.timeout(5000) });
  if (!result.ok || (result.headers.get("content-type") || "").toLowerCase().split(";")[0] !== "application/json") throw new Error("jwks_unavailable");
  const data = await result.json();
  if (!Array.isArray(data.keys) || data.keys.length > 100) throw new Error("jwks_invalid");
  jwksCache = { url, fetchedAt: now, keys: data.keys };
  return data.keys;
}

async function verifyOidcAccessToken(request, env) {
  const issuer = env.OIDC_ISSUER_URL;
  const jwksUrl = env.OIDC_JWKS_URL;
  const audience = env.OIDC_AUDIENCE;
  const requiredScopes = (env.OIDC_REQUIRED_SCOPES || "studio:access").trim().split(/\s+/).filter(Boolean);
  const tenantClaim = env.OIDC_TENANT_CLAIM || "tenant_id";
  try {
    const issuerUrl = new URL(issuer);
    const keysUrl = new URL(jwksUrl);
    if (issuerUrl.protocol !== "https:" || keysUrl.protocol !== "https:" ||
        issuerUrl.username || issuerUrl.password || keysUrl.username || keysUrl.password ||
        keysUrl.search || keysUrl.hash || !audience || !requiredScopes.length) return null;

    const authorization = request.headers.get("Authorization") || "";
    if (!authorization.startsWith("Bearer ")) return null;
    const token = authorization.slice(7);
    if (!token || token.length > 16384) return null;
    const parts = token.split(".");
    if (parts.length !== 3) return null;
    const header = parseJwtPart(parts[0]);
    const claims = parseJwtPart(parts[1]);
    if (header.alg !== "RS256" || typeof header.kid !== "string" ||
        claims.iss !== issuer || typeof claims.sub !== "string" || !claims.sub.trim()) return null;

    let keys = await loadJwks(keysUrl.toString());
    let jwk = keys.find((key) => key && key.kid === header.kid && key.kty === "RSA" &&
      key.use !== "enc" && (!key.alg || key.alg === "RS256"));
    if (!jwk) {
      keys = await loadJwks(keysUrl.toString(), true);
      jwk = keys.find((key) => key && key.kid === header.kid && key.kty === "RSA" &&
        key.use !== "enc" && (!key.alg || key.alg === "RS256"));
    }
    if (!jwk) return null;
    const publicKey = await crypto.subtle.importKey(
      "jwk", jwk, { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" }, false, ["verify"],
    );
    let validSignature = await crypto.subtle.verify(
      "RSASSA-PKCS1-v1_5", publicKey, decodeBase64Url(parts[2]),
      new TextEncoder().encode(parts[0] + "." + parts[1]),
    );
    if (!validSignature) {
      // A cached JWKS can be stale when an issuer rotates key material.
      keys = await loadJwks(keysUrl.toString(), true);
      jwk = keys.find((key) => key && key.kid === header.kid && key.kty === "RSA" &&
        key.use !== "enc" && (!key.alg || key.alg === "RS256"));
      if (!jwk) return null;
      const refreshedKey = await crypto.subtle.importKey(
        "jwk", jwk, { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" }, false, ["verify"],
      );
      validSignature = await crypto.subtle.verify(
        "RSASSA-PKCS1-v1_5", refreshedKey, decodeBase64Url(parts[2]),
        new TextEncoder().encode(parts[0] + "." + parts[1]),
      );
    }
    if (!validSignature) return null;

    const now = Math.floor(Date.now() / 1000);
    const audiences = Array.isArray(claims.aud) ? claims.aud : [claims.aud];
    const scopes = typeof claims.scope === "string" ? claims.scope.split(/\s+/) :
      Array.isArray(claims.scp) && claims.scp.every((scope) => typeof scope === "string") ? claims.scp : [];
    const tenant = claims[tenantClaim];
    const clientId = claims.azp || claims.client_id;
    if (!audiences.includes(audience) || !Number.isFinite(claims.exp) ||
        !Number.isFinite(claims.iat) || claims.exp <= now || claims.iat > now + 60 ||
        claims.exp - claims.iat > 86400 ||
        (claims.nbf !== undefined && (!Number.isFinite(claims.nbf) || claims.nbf > now + 60)) ||
        typeof tenant !== "string" || !/^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$/.test(tenant) ||
        typeof clientId !== "string" || !clientId.trim() ||
        (env.OIDC_CLIENT_ID && clientId !== env.OIDC_CLIENT_ID) ||
        !requiredScopes.every((scope) => scopes.includes(scope))) return null;
    return { subject: claims.sub, tenantId: tenant, clientId, expiresAt: claims.exp };
  } catch {
    return null;
  }
}


const MAX_LIVE_BODY_BYTES = 128 * 1024;
const MAX_LIVE_DURATION_SECONDS = 600;

async function readJsonLimited(request, limit) {
  const raw = await readLimitedText(request, limit);
  if (raw === null) return { error: "request_too_large" };
  try { return { value: JSON.parse(raw || "{}") }; }
  catch { return { error: "invalid_json" }; }
}

async function sfuRequest(env, path, init = {}) {
  const appId = env.CLOUDFLARE_SFU_APP_ID;
  const secret = env.CLOUDFLARE_SFU_APP_SECRET;
  if (!appId || !secret) throw new Error("sfu_not_configured");
  const url = "https://rtc.live.cloudflare.com/v1/apps/" + encodeURIComponent(appId) + path;
  const result = await fetch(url, {
    ...init, redirect: "manual",
    headers: { authorization: "Bearer " + secret, "content-type": "application/json", ...(init.headers || {}) },
    signal: AbortSignal.timeout(15000),
  });
  const contentType = (result.headers.get("content-type") || "").toLowerCase().split(";")[0];
  if (!result.ok || contentType !== "application/json") throw new Error("sfu_request_failed");
  const data = await result.json();
  if (data.errorCode || data.error || data.success === false) throw new Error("sfu_request_failed");
  return data;
}

async function sessionRegistry(env, appSessionId, operation, payload) {
  if (!env.LIVE_SESSIONS) throw new Error("session_registry_not_configured");
  const id = env.LIVE_SESSIONS.idFromName(appSessionId);
  const stub = env.LIVE_SESSIONS.get(id);
  return stub.fetch("https://live-session.internal/" + operation, {
    method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(payload),
  });
}

async function closeSfuTracks(env, providerSessionId, mids) {
  if (!Array.isArray(mids) || mids.length === 0) return;
  await sfuRequest(env, "/sessions/" + encodeURIComponent(providerSessionId) + "/tracks/close", {
    method: "PUT",
    body: JSON.stringify({ tracks: mids.map((mid) => ({ mid })), force: true }),
  });
}

async function readLimitedText(response, limit) {
  const declaredLength = Number(response.headers.get("Content-Length") || 0);
  if (declaredLength > limit) return null;
  if (!response.body) return "";
  const reader = response.body.getReader();
  const chunks = [];
  let total = 0;
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    total += value.byteLength;
    if (total > limit) {
      await reader.cancel();
      return null;
    }
    chunks.push(value);
  }
  const merged = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) {
    merged.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return new TextDecoder().decode(merged);
}

export default {
  async fetch(request, env) {
    const cors = corsHeaders(request, env);
    if (!cors) return response({ ok: false, error: "origin_not_allowed" }, 403);

    const url = new URL(request.url);
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: cors });
    }





    if (url.pathname === "/api/live/oidc/config" && request.method === "GET") {
      try {
        const authorizationUrl = new URL(env.OIDC_AUTHORIZATION_URL);
        const tokenUrl = new URL(env.OIDC_TOKEN_URL);
        const redirectUri = new URL(env.OIDC_REDIRECT_URI);
        if (authorizationUrl.protocol !== "https:" || tokenUrl.protocol !== "https:" ||
            redirectUri.protocol !== "https:" || authorizationUrl.username || authorizationUrl.password ||
            tokenUrl.username || tokenUrl.password || redirectUri.origin !== env.ALLOWED_ORIGIN ||
            !env.OIDC_CLIENT_ID) throw new Error("oidc_spa_not_configured");
        return response({
          ok: true,
          authorization_url: authorizationUrl.toString(),
          token_url: tokenUrl.toString(),
          client_id: env.OIDC_CLIENT_ID,
          redirect_uri: redirectUri.toString(),
          scopes: (env.OIDC_PUBLIC_SCOPES || "openid profile studio:access").trim(),
        }, 200, cors);
      } catch {
        return response({ ok: false, error: "oidc_pkce_not_configured" }, 503, cors);
      }
    }

    // Direct one-to-one Realtime WebRTC: audio travels directly between browser and model.
    // Camera frames, when consented, are sampled as still images over the data channel.
    if (url.pathname === "/api/live/realtime/calls" && request.method === "POST") {
      const principal = await verifyOidcAccessToken(request, env);
      if (!principal) return response({ ok: false, error: "unauthorized" }, 401, cors);
      if (typeof env.OPENAI_API_KEY !== "string" || !env.OPENAI_API_KEY.trim()) {
        return response({ ok: false, error: "realtime_provider_not_configured" }, 503, cors);
      }
      const parsed = await readJsonLimited(request, MAX_LIVE_BODY_BYTES);
      if (parsed.error) return response({ ok: false, error: parsed.error }, parsed.error === "request_too_large" ? 413 : 400, cors);
      const sdp = parsed.value?.sessionDescription;
      const consent = parsed.value?.consent;
      if (typeof sdp !== "string" || sdp.length < 20 || sdp.length > 100000 ||
          !/^v=0/m.test(sdp) || !/^m=audio\s/m.test(sdp) || /^m=video\s/m.test(sdp) ||
          !consent || consent.microphone !== true || typeof consent.camera !== "boolean") {
        return response({ ok: false, error: "invalid_realtime_offer_or_consent" }, 422, cors);
      }
      try {
        const identity = new TextEncoder().encode(principal.tenantId + ":" + principal.subject);
        const digest = new Uint8Array(await crypto.subtle.digest("SHA-256", identity));
        const safetyIdentifier = Array.from(digest, (byte) => byte.toString(16).padStart(2, "0")).join("");
        const session = {
          type: "realtime",
          model: env.OPENAI_REALTIME_MODEL || "gpt-realtime-2.1",
          instructions: "You are MEHR, a precise bilingual voice assistant. Reply in the user's language. When image frames are supplied, describe only what is visible and distinguish observations from assumptions.",
          audio: {
            input: { transcription: { model: "gpt-4o-mini-transcribe" }, turn_detection: { type: "semantic_vad" } },
            output: { voice: env.OPENAI_REALTIME_VOICE || "marin" },
          },
        };
        const form = new FormData();
        form.set("sdp", sdp);
        form.set("session", JSON.stringify(session));
        const upstream = await fetch("https://api.openai.com/v1/realtime/calls", {
          method: "POST",
          redirect: "manual",
          headers: {
            authorization: "Bearer " + env.OPENAI_API_KEY,
            "OpenAI-Safety-Identifier": safetyIdentifier,
          },
          body: form,
          signal: AbortSignal.timeout(20000),
        });
        if (!upstream.ok) {
          return response({ ok: false, error: "realtime_provider_request_failed", provider_status: upstream.status }, 502, cors);
        }
        const contentType = (upstream.headers.get("content-type") || "").toLowerCase().split(";")[0].trim();
        if (contentType !== "application/sdp") {
          return response({ ok: false, error: "realtime_provider_response_invalid" }, 502, cors);
        }
        const answer = await readLimitedText(upstream, 100000);
        if (answer === null || answer.length < 20 || !/^v=0/m.test(answer)) {
          return response({ ok: false, error: "realtime_provider_response_invalid" }, 502, cors);
        }
        return new Response(answer, {
          status: 200,
          headers: { ...cors, "content-type": "application/sdp", "cache-control": "no-store" },
        });
      } catch (error) {
        const timedOut = error?.name === "TimeoutError" || error?.name === "AbortError";
        return response({ ok: false, error: timedOut ? "realtime_provider_timeout" : "realtime_provider_unavailable" }, 502, cors);
      }
    }

    if (url.pathname === "/api/live/sessions" && request.method === "POST") {
      const principal = await verifyOidcAccessToken(request, env);
      if (!principal) return response({ ok: false, error: "unauthorized" }, 401, cors);
      if (!env.CLOUDFLARE_SFU_APP_ID || !env.CLOUDFLARE_SFU_APP_SECRET || !env.LIVE_SESSIONS) {
        return response({ ok: false, error: "live_transport_not_configured" }, 503, cors);
      }
      const parsed = await readJsonLimited(request, 4096);
      if (parsed.error) return response({ ok: false, error: parsed.error }, parsed.error === "request_too_large" ? 413 : 400, cors);
      const body = parsed.value;
      const mode = body?.mode;
      const consent = body?.consent;
      if (!["voice", "voice_vision"].includes(mode) ||
          !consent || Object.keys(consent).some((key) => !["microphone", "camera"].includes(key)) ||
          consent.microphone !== true ||
          (mode === "voice_vision" && consent.camera !== true) ||
          (mode === "voice" && consent.camera !== false)) {
        return response({ ok: false, error: "invalid_consent_or_mode" }, 422, cors);
      }
      try {
        const created = await sfuRequest(env, "/sessions/new", { method: "POST", body: "{}" });
        if (typeof created.sessionId !== "string" || !created.sessionId) throw new Error("sfu_response_invalid");
        const appSessionId = crypto.randomUUID();
        const expiresAt = Math.floor(Date.now() / 1000) + MAX_LIVE_DURATION_SECONDS;
        const stored = await sessionRegistry(env, appSessionId, "create", {
          subject: principal.subject, tenantId: principal.tenantId,
          providerSessionId: created.sessionId, expiresAt, consent,
        });
        if (!stored.ok) throw new Error("session_registry_write_failed");
        return response({ ok: true, session: { id: appSessionId, expiresAt, mode, consent } }, 201, cors);
      } catch {
        return response({ ok: false, error: "live_session_creation_failed" }, 502, cors);
      }
    }

    const livePublishMatch = url.pathname.match(/^\/api\/live\/sessions\/([0-9a-f-]{36})\/publish$/i);
    if (livePublishMatch && request.method === "POST") {
      const principal = await verifyOidcAccessToken(request, env);
      if (!principal) return response({ ok: false, error: "unauthorized" }, 401, cors);
      const appSessionId = livePublishMatch[1];
      const parsed = await readJsonLimited(request, MAX_LIVE_BODY_BYTES);
      if (parsed.error) return response({ ok: false, error: parsed.error }, parsed.error === "request_too_large" ? 413 : 400, cors);
      const body = parsed.value;
      const sdp = body?.sessionDescription;
      const tracks = body?.tracks;
      if (!sdp || sdp.type !== "offer" || typeof sdp.sdp !== "string" ||
          sdp.sdp.length < 20 || sdp.sdp.length > 100000 ||
          !Array.isArray(tracks) || tracks.length < 1 || tracks.length > 2 ||
          tracks.some((track) => !track || track.location !== "local" ||
            !/^[0-9]{1,3}$/.test(String(track.mid)) ||
            !["microphone", "camera"].includes(track.trackName)) ||
          new Set(tracks.map((track) => track.trackName)).size !== tracks.length ||
          !tracks.some((track) => track.trackName === "microphone")) {
        return response({ ok: false, error: "invalid_publish_request" }, 422, cors);
      }
      let providerSessionId = null;
      let publishedMids = [];
      try {
        const auth = await sessionRegistry(env, appSessionId, "authorize", {
          subject: principal.subject, tenantId: principal.tenantId,
        });
        if (!auth.ok) return response({ ok: false, error: "session_not_found" }, 404, cors);
        const owned = await auth.json();
        providerSessionId = owned.providerSessionId;
        if (owned.consent?.camera !== tracks.some((track) => track.trackName === "camera")) {
          return response({ ok: false, error: "consent_mismatch" }, 403, cors);
        }
        const result = await sfuRequest(env, "/sessions/" + encodeURIComponent(providerSessionId) + "/tracks/new", {
          method: "POST", body: JSON.stringify({ sessionDescription: sdp, tracks }),
        });
        const trackResults = Array.isArray(result.tracks) ? result.tracks : [];
        const requestedMids = new Set(tracks.map((track) => String(track.mid)));
        publishedMids = trackResults
          .filter((item) => item && !item.errorCode && !item.errorDescription &&
            typeof item.mid === "string" && requestedMids.has(item.mid))
          .map((item) => item.mid);
        const description = result.sessionDescription;
        if (!description || !["answer", "offer"].includes(description.type) ||
            typeof description.sdp !== "string" || !description.sdp.trim()) {
          throw new Error("sfu_session_description_invalid");
        }
        if (publishedMids.length) {
          const stored = await sessionRegistry(env, appSessionId, "update", {
            subject: principal.subject, tenantId: principal.tenantId, mids: publishedMids,
          });
          if (!stored.ok) throw new Error("session_registry_update_failed");
        }
        return response({
          ok: true,
          partial: publishedMids.length !== tracks.length,
          sessionDescription: description,
          tracks: trackResults,
        }, 200, cors);
      } catch {
        // If provider publication succeeded but our durable ownership update failed,
        // close those tracks so they cannot outlive an untracked application session.
        if (providerSessionId && publishedMids.length) {
          try { await closeSfuTracks(env, providerSessionId, publishedMids); } catch { /* best-effort compensation */ }
        }
        return response({ ok: false, error: "live_publish_failed" }, 502, cors);
      }
    }

    const liveInspectMatch = url.pathname.match(/^\/api\/live\/sessions\/([0-9a-f-]{36})$/i);
    if (liveInspectMatch && request.method === "GET") {
      const principal = await verifyOidcAccessToken(request, env);
      if (!principal) return response({ ok: false, error: "unauthorized" }, 401, cors);
      try {
        const auth = await sessionRegistry(env, liveInspectMatch[1], "authorize", {
          subject: principal.subject, tenantId: principal.tenantId,
        });
        if (!auth.ok) return response({ ok: false, error: "session_not_found" }, 404, cors);
        const owned = await auth.json();
        const state = await sfuRequest(env, "/sessions/" + encodeURIComponent(owned.providerSessionId), {
          method: "GET",
        });
        if (!Array.isArray(state.tracks) || state.tracks.length > 64 ||
            state.tracks.some((track) => !track || typeof track.mid !== "string")) {
          throw new Error("sfu_session_state_invalid");
        }
        const tracks = state.tracks.map((track) => ({
          mid: track.mid,
          trackName: typeof track.trackName === "string" ? track.trackName : null,
          location: track.location === "local" || track.location === "remote" ? track.location : null,
          status: ["active", "inactive", "initializing"].includes(track.status) ? track.status : "unknown",
        }));
        return response({ ok: true, expiresAt: owned.expiresAt, tracks }, 200, cors);
      } catch {
        return response({ ok: false, error: "live_session_inspection_failed" }, 502, cors);
      }
    }

    const liveRenegotiateMatch = url.pathname.match(/^\/api\/live\/sessions\/([0-9a-f-]{36})\/renegotiate$/i);
    if (liveRenegotiateMatch && request.method === "PUT") {
      const principal = await verifyOidcAccessToken(request, env);
      if (!principal) return response({ ok: false, error: "unauthorized" }, 401, cors);
      const appSessionId = liveRenegotiateMatch[1];
      const parsed = await readJsonLimited(request, MAX_LIVE_BODY_BYTES);
      if (parsed.error) return response({ ok: false, error: parsed.error }, parsed.error === "request_too_large" ? 413 : 400, cors);
      const description = parsed.value?.sessionDescription;
      if (!description || description.type !== "answer" ||
          typeof description.sdp !== "string" || description.sdp.length < 20 ||
          description.sdp.length > 100000) {
        return response({ ok: false, error: "invalid_renegotiation_answer" }, 422, cors);
      }
      try {
        const auth = await sessionRegistry(env, appSessionId, "authorize", {
          subject: principal.subject, tenantId: principal.tenantId,
        });
        if (!auth.ok) return response({ ok: false, error: "session_not_found" }, 404, cors);
        const owned = await auth.json();
        const result = await sfuRequest(env, "/sessions/" + encodeURIComponent(owned.providerSessionId) + "/renegotiate", {
          method: "PUT", body: JSON.stringify({ sessionDescription: description }),
        });
        return response({ ok: true, result }, 200, cors);
      } catch {
        return response({ ok: false, error: "live_renegotiation_failed" }, 502, cors);
      }
    }

    const liveCloseMatch = url.pathname.match(/^\/api\/live\/sessions\/([0-9a-f-]{36})$/i);
    if (liveCloseMatch && request.method === "DELETE") {
      const principal = await verifyOidcAccessToken(request, env);
      if (!principal) return response({ ok: false, error: "unauthorized" }, 401, cors);
      const appSessionId = liveCloseMatch[1];
      try {
        const auth = await sessionRegistry(env, appSessionId, "authorize", {
          subject: principal.subject, tenantId: principal.tenantId,
        });
        if (!auth.ok) return response({ ok: false, error: "session_not_found" }, 404, cors);
        const owned = await auth.json();
        if (owned.mids?.length) {
          const closed = await sfuRequest(env, "/sessions/" + encodeURIComponent(owned.providerSessionId) + "/tracks/close", {
            method: "PUT", body: JSON.stringify({ tracks: owned.mids.map((mid) => ({ mid })), force: true }),
          });
          const closeResults = Array.isArray(closed.tracks) ? closed.tracks : [];
          const unresolved = owned.mids.filter((mid) => {
            const item = closeResults.find((entry) => entry && String(entry.mid) === String(mid));
            return !item || (item.errorCode && item.errorCode !== "close_track_error");
          });
          if (unresolved.length) throw new Error("sfu_track_close_incomplete");
        }
        const removed = await sessionRegistry(env, appSessionId, "delete", {
          subject: principal.subject, tenantId: principal.tenantId,
        });
        if (!removed.ok) throw new Error("session_registry_delete_failed");
        return response({ ok: true, closed: true }, 200, cors);
      } catch {
        return response({ ok: false, error: "live_session_close_failed" }, 502, cors);
      }
    }

    if (url.pathname === "/api/live/capabilities" && request.method === "GET") {
      const principal = await verifyOidcAccessToken(request, env);
      if (!principal) return response({ ok: false, error: "unauthorized" }, 401, cors);
      const configured = Boolean(env.CLOUDFLARE_SFU_APP_ID && env.CLOUDFLARE_SFU_APP_SECRET && env.LIVE_SESSIONS);
      return response({
        ok: true,
        authenticated: true,
        live_transport: configured ? "cloudflare_realtime_sfu" : "not_configured",
        modes: configured ? ["voice", "voice_vision"] : [],
        session_creation_enabled: configured,
        reason: configured ? null : "sfu_credentials_missing",
        consent_required: { microphone: true, camera: "voice_vision_only" },
      }, configured ? 200 : 503, cors);
    }

    if (url.pathname === "/api/health" && request.method === "GET") {
      if (!authorized(request, env)) {
        return response({ ok: false, error: "unauthorized" }, 401, cors);
      }
      return response({ ok: true, service: "MEHR AI STUDIO API", provider_configured: Boolean(env.AI_BASE_URL && env.AI_API_KEY && env.AI_MODEL) }, 200, cors);
    }

    if (url.pathname !== "/api/generate" || request.method !== "POST") {
      return response({ ok: false, error: "not_found" }, 404, cors);
    }

    if (!authorized(request, env)) {
      return response({ ok: false, error: "unauthorized" }, 401, cors);
    }

    const declaredLength = Number(request.headers.get("Content-Length") || 0);
    if (declaredLength > MAX_BODY_BYTES) {
      return response({ ok: false, error: "request_too_large" }, 413, cors);
    }

    let raw;
    try {
      raw = await readLimitedText(request, MAX_BODY_BYTES);
    } catch {
      return response({ ok: false, error: "invalid_request" }, 400, cors);
    }
    if (raw === null) {
      return response({ ok: false, error: "request_too_large" }, 413, cors);
    }

    let body;
    try {
      body = JSON.parse(raw);
    } catch {
      return response({ ok: false, error: "invalid_json" }, 400, cors);
    }
    const prompt = body && typeof body.prompt === "string" ? body.prompt.trim() : "";
    if (!prompt || prompt.length > MAX_PROMPT_CHARS) {
      return response({ ok: false, error: "invalid_prompt" }, 422, cors);
    }

    if (!env.AI_BASE_URL || !env.AI_API_KEY || !env.AI_MODEL) {
      return response({ ok: false, error: "provider_not_configured" }, 503, cors);
    }

    let endpoint;
    try {
      endpoint = new URL(trimTrailingSlashes(env.AI_BASE_URL));
      if (endpoint.protocol !== "https:" || endpoint.username || endpoint.password) {
        throw new Error("https_required");
      }
      if (!endpoint.pathname.endsWith("/chat/completions")) {
        endpoint.pathname = trimTrailingSlashes(endpoint.pathname) + "/chat/completions";
      }
    } catch {
      return response({ ok: false, error: "provider_configuration_invalid" }, 503, cors);
    }

    try {
      const upstream = await fetch(endpoint.toString(), {
        method: "POST",
        redirect: "manual",
        headers: {
          "authorization": `Bearer ${env.AI_API_KEY}`,
          "content-type": "application/json",
        },
        body: JSON.stringify({
          model: env.AI_MODEL,
          messages: [
            { role: "system", content: "You are MEHR AI STUDIO, a precise and helpful production assistant. Respond in the language requested by the user." },
            { role: "user", content: prompt },
          ],
          temperature: 0.6,
        }),
        signal: AbortSignal.timeout(30000),
      });
      if (!upstream.ok) {
        return response({ ok: false, error: "provider_request_failed", provider_status: upstream.status }, 502, cors);
      }
      const contentType = upstream.headers.get("Content-Type") || "";
      const mediaType = contentType.toLowerCase().split(";")[0].trim();
      if (mediaType !== "application/json" && !mediaType.endsWith("+json")) {
        return response({ ok: false, error: "provider_response_invalid" }, 502, cors);
      }
      const rawResult = await readLimitedText(upstream, MAX_PROVIDER_RESPONSE_BYTES);
      if (rawResult === null) {
        return response({ ok: false, error: "provider_response_too_large" }, 502, cors);
      }
      let result;
      try {
        result = JSON.parse(rawResult);
      } catch {
        return response({ ok: false, error: "provider_response_invalid" }, 502, cors);
      }
      const text = result?.choices?.[0]?.message?.content;
      if (typeof text !== "string" || !text.trim()) {
        return response({ ok: false, error: "provider_response_invalid" }, 502, cors);
      }
      return response({ ok: true, generated: { text, model: result.model || env.AI_MODEL } }, 200, cors);
    } catch (error) {
      const timedOut = error?.name === "TimeoutError" || error?.name === "AbortError";
      return response({ ok: false, error: timedOut ? "provider_timeout" : "provider_unavailable" }, 502, cors);
    }
  },
};


export class LiveSessionRegistry {
  constructor(state) { this.state = state; }

  async fetch(request) {
    if (request.method !== "POST") return new Response(null, { status: 405 });
    let body;
    try { body = await request.json(); } catch { return new Response(null, { status: 400 }); }
    const path = new URL(request.url).pathname;
    const existing = await this.state.storage.get("session");
    if (path === "/create") {
      if (existing || typeof body.subject !== "string" || !body.subject.trim() || body.subject.length > 256 ||
          typeof body.tenantId !== "string" || !/^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$/.test(body.tenantId) ||
          typeof body.providerSessionId !== "string" || !body.providerSessionId.trim() || body.providerSessionId.length > 256 ||
          !Number.isFinite(body.expiresAt) || body.expiresAt <= Math.floor(Date.now() / 1000) ||
          body.expiresAt > Math.floor(Date.now() / 1000) + MAX_LIVE_DURATION_SECONDS ||
          !body.consent || body.consent.microphone !== true || typeof body.consent.camera !== "boolean") {
        return new Response(null, { status: 409 });
      }
      await this.state.storage.put("session", { ...body, mids: [] });
      return new Response(null, { status: 201 });
    }
    if (!existing || existing.expiresAt <= Math.floor(Date.now() / 1000) ||
        existing.subject !== body.subject || existing.tenantId !== body.tenantId) {
      return new Response(null, { status: 404 });
    }
    if (path === "/authorize") {
      const { providerSessionId, expiresAt, consent, mids } = existing;
      return Response.json({ providerSessionId, expiresAt, consent, mids });
    }
    if (path === "/update") {
      if (!Array.isArray(body.mids) || body.mids.some((mid) => !/^[0-9]{1,3}$/.test(String(mid)))) {
        return new Response(null, { status: 400 });
      }
      const merged = [...new Set([...existing.mids, ...body.mids])];
      await this.state.storage.put("session", { ...existing, mids: merged });
      return new Response(null, { status: 200 });
    }
    if (path === "/delete") {
      await this.state.storage.delete("session");
      return new Response(null, { status: 200 });
    }
    return new Response(null, { status: 404 });
  }
}
