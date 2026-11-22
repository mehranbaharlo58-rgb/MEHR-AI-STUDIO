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
