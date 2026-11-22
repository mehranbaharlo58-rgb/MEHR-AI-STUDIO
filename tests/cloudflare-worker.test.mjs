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

test("rejects unapproved browser origins", async () => {
  const request = new Request("https://worker.test/api/health", { headers: { Origin: "https://attacker.test" } });
  const response = await worker.fetch(request, env);
  assert.equal(response.status, 403);
});

test("health reports configuration without exposing secrets", async () => {
  const request = new Request("https://worker.test/api/health", { headers: origin });
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
    const request = new Request("https://worker.test/api/generate", {
      method: "POST",
      headers: { ...origin, Authorization: `Bearer ${env.MEHR_API_TOKEN}`, "Content-Type": "application/json" },
      body: JSON.stringify({ prompt: "Write a short welcome message." }),
    });
    const response = await worker.fetch(request, env);
    const body = await response.json();
    assert.equal(response.status, 200);
    assert.equal(body.generated.text, "Generated output");
    assert.equal(sent.url, "https://api.example.test/v1/chat/completions");
    assert.equal(new Headers(sent.init.headers).get("authorization"), "Bearer provider-secret");
  } finally {
    globalThis.fetch = originalFetch;
  }
});
