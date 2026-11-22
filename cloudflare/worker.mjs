const JSON_HEADERS = { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" };
const MAX_BODY_BYTES = 16 * 1024;
const MAX_PROMPT_CHARS = 12000;

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

function authorized(request, env) {
  const configured = env.MEHR_API_TOKEN;
  const header = request.headers.get("Authorization") || "";
  const supplied = header.startsWith("Bearer ") ? header.slice(7) : "";
  return typeof configured === "string" && configured.length >= 32 &&
    equalSecret(supplied, configured);
}

export default {
  async fetch(request, env) {
    const cors = corsHeaders(request, env);
    if (!cors) return response({ ok: false, error: "origin_not_allowed" }, 403);

    const url = new URL(request.url);
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: cors });
    }

    if (url.pathname === "/api/health" && request.method === "GET") {
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
      raw = await request.text();
    } catch {
      return response({ ok: false, error: "invalid_request" }, 400, cors);
    }
    if (new TextEncoder().encode(raw).byteLength > MAX_BODY_BYTES) {
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
      endpoint = new URL(env.AI_BASE_URL.replace(/\/+$/, ""));
      if (endpoint.protocol !== "https:") throw new Error("https_required");
      if (!endpoint.pathname.endsWith("/chat/completions")) {
        endpoint.pathname = endpoint.pathname.replace(/\/+$/, "") + "/chat/completions";
      }
    } catch {
      return response({ ok: false, error: "provider_configuration_invalid" }, 503, cors);
    }

    try {
      const upstream = await fetch(endpoint.toString(), {
        method: "POST",
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
      const result = await upstream.json();
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
