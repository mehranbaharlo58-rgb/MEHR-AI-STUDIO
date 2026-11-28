const JSON_HEADERS = {
  "content-type": "application/json; charset=utf-8",
  "cache-control": "no-store",
  "x-content-type-options": "nosniff",
};
const MAX_BODY_BYTES = 16 * 1024;
const MAX_PROMPT_CHARS = 12_000;
const MAX_COMPLETION_TOKENS = 600;
const DEFAULT_MODEL = "@cf/zai-org/glm-4.7-flash";

function json(data, status, cors = {}) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { ...JSON_HEADERS, ...cors },
  });
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
  const length = Math.max(a.length, b.length);
  for (let i = 0; i < length; i += 1) {
    diff |= (a.charCodeAt(i) || 0) ^ (b.charCodeAt(i) || 0);
  }
  return diff === 0;
}

function authorized(request, env) {
  const configured = env.MEHR_API_TOKEN;
  const header = request.headers.get("Authorization") || "";
  const supplied = header.startsWith("Bearer ") ? header.slice(7) : "";
  return typeof configured === "string" &&
    configured.length >= 32 &&
    equalSecret(supplied, configured);
}

async function readLimitedText(request, limit) {
  const declaredLength = Number(request.headers.get("Content-Length") || 0);
  if (declaredLength > limit) return null;
  if (!request.body) return "";
  const reader = request.body.getReader();
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

function extractText(result) {
  const content = result?.choices?.[0]?.message?.content;
  if (typeof content === "string" && content.trim()) return content.trim();
  if (typeof result?.response === "string" && result.response.trim()) {
    return result.response.trim();
  }
  return null;
}

export default {
  async fetch(request, env) {
    const cors = corsHeaders(request, env);
    if (!cors) return json({ ok: false, error: "origin_not_allowed" }, 403);

    const url = new URL(request.url);
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: cors });
    }

    if (url.pathname === "/api/health" && request.method === "GET") {
      if (!authorized(request, env)) {
        return json({ ok: false, error: "unauthorized" }, 401, cors);
      }
      return json({
        ok: true,
        service: "MEHR AI STUDIO API",
        provider_configured: Boolean(env.AI && (env.AI_MODEL || DEFAULT_MODEL)),
        model: env.AI_MODEL || DEFAULT_MODEL,
        auth: "owner-token",
      }, 200, cors);
    }

    if (url.pathname !== "/api/generate" || request.method !== "POST") {
      return json({ ok: false, error: "not_found" }, 404, cors);
    }

    if (!authorized(request, env)) {
      return json({ ok: false, error: "unauthorized" }, 401, cors);
    }

    let raw;
    try {
      raw = await readLimitedText(request, MAX_BODY_BYTES);
    } catch {
      return json({ ok: false, error: "invalid_request" }, 400, cors);
    }
    if (raw === null) {
      return json({ ok: false, error: "request_too_large" }, 413, cors);
    }

    let body;
    try {
      body = JSON.parse(raw);
    } catch {
      return json({ ok: false, error: "invalid_json" }, 400, cors);
    }

    const prompt = body && typeof body.prompt === "string" ? body.prompt.trim() : "";
    if (!prompt || prompt.length > MAX_PROMPT_CHARS) {
      return json({ ok: false, error: "invalid_prompt" }, 422, cors);
    }

    if (!env.AI || typeof env.AI.run !== "function") {
      return json({ ok: false, error: "workers_ai_binding_missing" }, 503, cors);
    }

    const model = env.AI_MODEL || DEFAULT_MODEL;
    try {
      const result = await env.AI.run(model, {
        messages: [
          {
            role: "system",
            content: "You are MEHR AI STUDIO, a precise and helpful assistant. Reply in the user's language. Be transparent about uncertainty and never invent completed actions.",
          },
          { role: "user", content: prompt },
        ],
        max_completion_tokens: MAX_COMPLETION_TOKENS,
        temperature: 0.35,
        stream: false,
      });
      const text = extractText(result);
      if (!text) {
        return json({ ok: false, error: "provider_response_invalid" }, 502, cors);
      }
      return json({
        ok: true,
        generated: { text, model },
        usage: result?.usage || null,
      }, 200, cors);
    } catch (error) {
      const message = typeof error?.message === "string" ? error.message : "";
      const isLimit = /limit|quota|billing|neuron/i.test(message);
      return json({
        ok: false,
        error: isLimit ? "ai_quota_or_billing_limit" : "provider_unavailable",
      }, isLimit ? 429 : 502, cors);
    }
  },
};
