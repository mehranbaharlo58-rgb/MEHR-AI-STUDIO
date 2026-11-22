import test from "node:test";
import assert from "node:assert/strict";
import worker from "../cloudflare/worker.mjs";

const env = {
  ALLOWED_ORIGIN: "https://mehranbaharlo58-rgb.github.io",
  MEHR_API_TOKEN: "test-token-that-is-at-least-32-characters",
  AI_BASE_URL: "https://api.example.test/v1",
  AI_API_KEY: "provider-secret",
  AI_MODEL: "test-model",
};
const origin = { Origin: env.ALLOWED_ORIGIN };
const generationRequest = () => new Request("https://worker.test/api/generate", {
  method: "POST",
  headers: { ...origin, Authorization: `Bearer ${env.MEHR_API_TOKEN}`, "Content-Type": "application/json" },
  body: JSON.stringify({ prompt: "Write a short welcome message." }),
});

test("rejects unapproved browser origins", async () => {
  const request = new Request("https://worker.test/api/health", { headers: { Origin: "https://attacker.test" } });
  const response = await worker.fetch(request, env);
  assert.equal(response.status, 403);
});

test("health rejects requests without the owner token", async () => {
  const request = new Request("https://worker.test/api/health", { headers: origin });
  const response = await worker.fetch(request, env);
  assert.equal(response.status, 401);
});

test("health reports configuration without exposing secrets", async () => {
  const request = new Request("https://worker.test/api/health", {
    headers: { ...origin, Authorization: `Bearer ${env.MEHR_API_TOKEN}` },
  });
  const response = await worker.fetch(request, env);
  const body = await response.json();
  assert.equal(response.status, 200);
  assert.equal(body.provider_configured, true);
  assert.equal(JSON.stringify(body).includes(env.AI_API_KEY), false);
});

test("rejects generation without the owner token", async () => {
  const request = new Request("https://worker.test/api/generate", {
    method: "POST", headers: { ...origin, "Content-Type": "application/json" },
    body: JSON.stringify({ prompt: "hello" }),
  });
  const response = await worker.fetch(request, env);
  assert.equal(response.status, 401);
});

test("validates prompt before contacting provider", async () => {
  const request = new Request("https://worker.test/api/generate", {
    method: "POST",
    headers: { ...origin, Authorization: `Bearer ${env.MEHR_API_TOKEN}`, "Content-Type": "application/json" },
    body: JSON.stringify({ prompt: " " }),
  });
  const response = await worker.fetch(request, env);
  assert.equal(response.status, 422);
});

test("generates through the configured OpenAI-compatible provider", async () => {
  const originalFetch = globalThis.fetch;
  let sent;
  globalThis.fetch = async (url, init) => {
    sent = { url: String(url), init };
    return new Response(JSON.stringify({ model: "test-model", choices: [{ message: { content: "Generated output" } }] }), {
      status: 200, headers: { "Content-Type": "application/json" },
    });
  };
  try {
    const response = await worker.fetch(generationRequest(), env);
    const body = await response.json();
    assert.equal(response.status, 200);
    assert.equal(body.generated.text, "Generated output");
    assert.equal(sent.url, "https://api.example.test/v1/chat/completions");
    assert.equal(new Headers(sent.init.headers).get("authorization"), "Bearer provider-secret");
    assert.equal(sent.init.redirect, "manual");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("does not follow provider redirects with authorization credentials", async () => {
  const originalFetch = globalThis.fetch;
  let sent;
  globalThis.fetch = async (_url, init) => {
    sent = init;
    return new Response(null, { status: 302, headers: { Location: "https://attacker.test/collect" } });
  };
  try {
    const response = await worker.fetch(generationRequest(), env);
    assert.equal(response.status, 502);
    assert.equal(sent.redirect, "manual");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("rejects provider responses larger than one megabyte", async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => new Response("oversized", {
    status: 200,
    headers: { "Content-Type": "application/json", "Content-Length": String(1024 * 1024 + 1) },
  });
  try {
    const response = await worker.fetch(generationRequest(), env);
    const body = await response.json();
    assert.equal(response.status, 502);
    assert.equal(body.error, "provider_response_too_large");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("rejects non-JSON provider responses", async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => new Response("not json", {
    status: 200, headers: { "Content-Type": "text/html" },
  });
  try {
    const response = await worker.fetch(generationRequest(), env);
    const body = await response.json();
    assert.equal(response.status, 502);
    assert.equal(body.error, "provider_response_invalid");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("rejects oversized streamed request bodies without Content-Length", async () => {
  let cancelled = false;
  const body = new ReadableStream({
    start(controller) {
      controller.enqueue(new TextEncoder().encode("x".repeat(20 * 1024)));
    },
    cancel() {
      cancelled = true;
    },
  });
  const request = new Request("https://worker.test/api/generate", {
    method: "POST",
    headers: { ...origin, Authorization: `Bearer ${env.MEHR_API_TOKEN}`, "Content-Type": "application/json" },
    body,
    duplex: "half",
  });
  const response = await worker.fetch(request, env);
  const result = await response.json();
  assert.equal(response.status, 413);
  assert.equal(result.error, "request_too_large");
  assert.equal(cancelled, true);
});
