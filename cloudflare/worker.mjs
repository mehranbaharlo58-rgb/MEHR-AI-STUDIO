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
    "access-control-allow-methods": "GET, POST, OPTIONS",
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

async function verifyOidcAccessToken(request, env) {
  const issuer = env.OIDC_ISSUER_URL;
  const jwksUrl = env.OIDC_JWKS_URL;
  const audience = env.OIDC_AUDIENCE;
  const requiredScopes = (env.OIDC_REQUIRED_SCOPES || "studio:access").trim().split(/\\s+/).filter(Boolean);
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

    const jwksResponse = await fetch(keysUrl.toString(), {
      method: "GET", redirect: "manual", headers: { accept: "application/json" },
      signal: AbortSignal.timeout(5000),
    });
    if (!jwksResponse.ok || (jwksResponse.headers.get("content-type") || "").toLowerCase().split(";")[0] !== "application/json") return null;
    const jwks = await jwksResponse.json();
    if (!Array.isArray(jwks.keys) || jwks.keys.length > 100) return null;
    const jwk = jwks.keys.find((key) => key && key.kid === header.kid && key.kty === "RSA" &&
      key.use !== "enc" && (!key.alg || key.alg === "RS256"));
    if (!jwk) return null;
    const publicKey = await crypto.subtle.importKey(
      "jwk", jwk, { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" }, false, ["verify"],
    );
    const validSignature = await crypto.subtle.verify(
      "RSASSA-PKCS1-v1_5", publicKey, decodeBase64Url(parts[2]),
      new TextEncoder().encode(parts[0] + "." + parts[1]),
    );
    if (!validSignature) return null;

    const now = Math.floor(Date.now() / 1000);
    const audiences = Array.isArray(claims.aud) ? claims.aud : [claims.aud];
    const scopes = typeof claims.scope === "string" ? claims.scope.split(/\\s+/) :
      Array.isArray(claims.scp) && claims.scp.every((scope) => typeof scope === "string") ? claims.scp : [];
    const tenant = claims[tenantClaim];
    const clientId = claims.azp || claims.client_id;
    if (!audiences.includes(audience) || !Number.isFinite(claims.exp) ||
        !Number.isFinite(claims.iat) || claims.exp <= now || claims.iat > now + 60 ||
        claims.exp - claims.iat > 86400 ||
        (claims.nbf !== undefined && (!Number.isFinite(claims.nbf) || claims.nbf > now + 60)) ||
        typeof tenant !== "string" || !/^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$/.test(tenant) ||
        typeof clientId !== "string" || !clientId.trim() ||
        !requiredScopes.every((scope) => scopes.includes(scope))) return null;
    return { subject: claims.sub, tenantId: tenant, clientId, expiresAt: claims.exp };
  } catch {
    return null;
  }
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


    if (url.pathname === "/api/live/capabilities" && request.method === "GET") {
      const principal = await verifyOidcAccessToken(request, env);
      if (!principal) return response({ ok: false, error: "unauthorized" }, 401, cors);
      const configured = Boolean(env.CLOUDFLARE_SFU_APP_ID && env.CLOUDFLARE_SFU_APP_SECRET);
      return response({
        ok: true,
        authenticated: true,
        live_transport: configured ? "cloudflare_realtime_sfu" : "not_configured",
        modes: configured ? ["voice", "voice_vision"] : [],
        session_creation_enabled: false,
        reason: configured ? "session_registry_required" : "sfu_credentials_missing",
        consent_required: { microphone: true, camera: true },
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
