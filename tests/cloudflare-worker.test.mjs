import test from "node:test";
import assert from "node:assert/strict";
import worker, { LiveSessionRegistry, decodeSfuJpegPacket } from "../cloudflare/worker.mjs";

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


function base64urlJson(value) {
  return Buffer.from(JSON.stringify(value)).toString("base64url");
}

async function makeOidcToken(overrides = {}) {
  const pair = await crypto.subtle.generateKey({
    name: "RSASSA-PKCS1-v1_5", modulusLength: 2048,
    publicExponent: Uint8Array.of(1, 0, 1), hash: "SHA-256",
  }, true, ["sign", "verify"]);
  const jwk = await crypto.subtle.exportKey("jwk", pair.publicKey);
  jwk.kid = "test-key";
  jwk.use = "sig";
  jwk.alg = "RS256";
  const now = Math.floor(Date.now() / 1000);
  const header = base64urlJson({ alg: "RS256", typ: "JWT", kid: "test-key" });
  const payload = base64urlJson({
    iss: "https://issuer.example.test",
    aud: "mehr-api",
    sub: "user-123",
    azp: "mehr-web",
    tenant_id: "tenant-123",
    scope: "studio:access",
    iat: now,
    exp: now + 300,
    ...overrides,
  });
  const signingInput = header + "." + payload;
  const signature = await crypto.subtle.sign(
    "RSASSA-PKCS1-v1_5", pair.privateKey, new TextEncoder().encode(signingInput),
  );
  return {
    token: signingInput + "." + Buffer.from(signature).toString("base64url"),
    jwk,
  };
}

test("live capabilities reject requests without a verified OIDC token", async () => {
  const response = await worker.fetch(new Request("https://worker.test/api/live/capabilities", {
    headers: origin,
  }), env);
  assert.equal(response.status, 401);
});

test("verifies OIDC signature and trusted claims before live capability checks", async () => {
  const { token, jwk } = await makeOidcToken();
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (url, init) => {
    assert.equal(String(url), "https://issuer.example.test/jwks.json");
    assert.equal(init.redirect, "manual");
    return new Response(JSON.stringify({ keys: [jwk] }), {
      status: 200, headers: { "Content-Type": "application/json" },
    });
  };
  try {
    const response = await worker.fetch(new Request("https://worker.test/api/live/capabilities", {
      headers: { ...origin, Authorization: "Bearer " + token },
    }), {
      ...env,
      OIDC_ISSUER_URL: "https://issuer.example.test",
      OIDC_JWKS_URL: "https://issuer.example.test/jwks.json",
      OIDC_AUDIENCE: "mehr-api",
      OIDC_REQUIRED_SCOPES: "studio:access",
    });
    const body = await response.json();
    assert.equal(response.status, 503);
    assert.equal(body.authenticated, true);
    assert.equal(body.live_transport, "not_configured");
    assert.equal(body.session_creation_enabled, false);
    assert.equal(JSON.stringify(body).includes(token), false);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("rejects an OIDC token with a modified signature", async () => {
  const { token, jwk } = await makeOidcToken();
  const parts = token.split(".");
  parts[2] = "AAAA";
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => new Response(JSON.stringify({ keys: [jwk] }), {
    status: 200, headers: { "Content-Type": "application/json" },
  });
  try {
    const response = await worker.fetch(new Request("https://worker.test/api/live/capabilities", {
      headers: { ...origin, Authorization: "Bearer " + parts.join(".") },
    }), {
      ...env,
      OIDC_ISSUER_URL: "https://issuer.example.test",
      OIDC_JWKS_URL: "https://issuer.example.test/jwks.json",
      OIDC_AUDIENCE: "mehr-api",
      OIDC_REQUIRED_SCOPES: "studio:access",
    });
    assert.equal(response.status, 401);
  } finally {
    globalThis.fetch = originalFetch;
  }
});


test("live capabilities accurately report a configured session transport", async () => {
  const { token, jwk } = await makeOidcToken();
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => new Response(JSON.stringify({ keys: [jwk] }), {
    status: 200, headers: { "Content-Type": "application/json" },
  });
  try {
    const response = await worker.fetch(new Request("https://worker.test/api/live/capabilities", {
      headers: { ...origin, Authorization: "Bearer " + token },
    }), {
      ...env,
      OIDC_ISSUER_URL: "https://issuer.example.test",
      OIDC_JWKS_URL: "https://issuer.example.test/jwks-capabilities-configured.json",
      OIDC_AUDIENCE: "mehr-api",
      CLOUDFLARE_SFU_APP_ID: "test-app",
      CLOUDFLARE_SFU_APP_SECRET: "test-secret",
      LIVE_SESSIONS: { idFromName: () => "session-id", get: () => ({ fetch: async () => new Response(null, { status: 200 }) }) },
    });
    const body = await response.json();
    assert.equal(response.status, 200);
    assert.equal(body.session_creation_enabled, true);
    assert.equal(body.live_transport, "cloudflare_realtime_sfu");
    assert.equal(body.reason, null);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("decodes a Cloudflare SFU protobuf JPEG packet", () => {
  const packet = Uint8Array.from([0x2a, 0x04, 0xff, 0xd8, 0xff, 0xd9]);
  assert.deepEqual(Array.from(decodeSfuJpegPacket(packet)), [0xff, 0xd8, 0xff, 0xd9]);
});

test("rejects malformed, non-JPEG, and oversized SFU video packets", () => {
  assert.equal(decodeSfuJpegPacket(Uint8Array.from([0x2a, 0x04, 0xff, 0xd8])), null);
  assert.equal(decodeSfuJpegPacket(Uint8Array.from([0x2a, 0x04, 1, 2, 3, 4])), null);
  assert.equal(decodeSfuJpegPacket(Uint8Array.from([0x2a, 0x80])), null);
  assert.equal(decodeSfuJpegPacket(new Uint8Array(1024 * 1024 + 100)), null);
});

test("creates a session-owned Cloudflare JPEG egress adapter only for a published consented camera", async () => {
  const { token, jwk } = await makeOidcToken();
  const originalFetch = globalThis.fetch;
  let adapterRequest = null;
  const registryCalls = [];
  globalThis.fetch = async (url, init = {}) => {
    const target = String(url);
    if (target.endsWith("/jwks-video-adapter.json")) {
      return Response.json({ keys: [jwk] });
    }
    if (target === "https://rtc.live.cloudflare.com/v1/apps/test-app/adapters/websocket/new") {
      adapterRequest = JSON.parse(init.body);
      return Response.json({ tracks: [{ adapterId: "adapter-123" }] });
    }
    assert.fail("Unexpected outbound request: " + target);
  };
  try {
    const response = await worker.fetch(new Request("https://worker.test/api/live/sessions/123e4567-e89b-12d3-a456-426614174000/video-adapter", {
      method: "POST",
      headers: { ...origin, Authorization: "Bearer " + token, "Content-Type": "application/json" },
      body: "{}",
    }), {
      ...env,
      OIDC_ISSUER_URL: "https://issuer.example.test",
      OIDC_JWKS_URL: "https://issuer.example.test/jwks-video-adapter.json",
      OIDC_AUDIENCE: "mehr-api",
      CLOUDFLARE_SFU_APP_ID: "test-app",
      CLOUDFLARE_SFU_APP_SECRET: "sfu-secret",
      LIVE_SESSIONS: {
        idFromName: (id) => id,
        get: () => ({ fetch: async (url, init) => {
          const path = new URL(url).pathname;
          registryCalls.push(path);
          if (path === "/lock" || path === "/unlock") return new Response(null, { status: 200 });
          if (path === "/authorize") return Response.json({
            providerSessionId: "provider-session", expiresAt: Math.floor(Date.now() / 1000) + 240,
            consent: { microphone: true, camera: true },
            tracks: [{ mid: "1", trackName: "camera" }],
            videoRelay: null,
          });
          if (path === "/prepare-video") {
            const body = JSON.parse(init.body);
            assert.match(body.ingestToken, /^[a-f0-9]{64}$/);
            assert.equal("viewerToken" in body, false);
            return new Response(null, { status: 201 });
          }
          if (path === "/complete-video") {
            assert.equal(JSON.parse(init.body).adapterId, "adapter-123");
            return new Response(null, { status: 200 });
          }
          if (path === "/issue-viewer-ticket") {
            const body = JSON.parse(init.body);
            assert.match(body.ticket, /^[a-f0-9]{64}$/);
            assert.ok(body.ticketExpiresAt > Math.floor(Date.now() / 1000));
            return new Response(null, { status: 201 });
          }
          assert.fail("Unexpected registry operation: " + path);
        }}),
      },
    });
    const body = await response.json();
    assert.equal(response.status, 201);
    assert.equal(body.adapter_active, true);
    assert.equal(body.frame_format, "jpeg");
    assert.match(body.viewer_url, /^wss:\/\/worker\.test\/api\/live\/media\//);
    assert.match(body.viewer_ticket, /^[a-f0-9]{64}$/);
    assert.equal(body.viewer_url.includes("token="), false);
    assert.equal(registryCalls.includes("/issue-viewer-ticket"), true);
    assert.equal(adapterRequest.tracks[0].location, "remote");
    assert.equal(adapterRequest.tracks[0].sessionId, "provider-session");
    assert.equal(adapterRequest.tracks[0].trackName, "camera");
    assert.equal(adapterRequest.tracks[0].outputCodec, "jpeg");
    assert.match(adapterRequest.tracks[0].endpoint, /^wss:\/\/worker\.test\/api\/live\/media\//);
    assert.equal(registryCalls.includes("/complete-video"), true);
    assert.equal(registryCalls.includes("/lock"), true);
    assert.equal(registryCalls.includes("/unlock"), true);
    assert.equal(registryCalls.indexOf("/lock") < registryCalls.indexOf("/authorize"), true);
    assert.equal(JSON.stringify(body).includes("sfu-secret"), false);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("does not create a Cloudflare adapter when the session mutation lock is busy", async () => {
  const { token, jwk } = await makeOidcToken();
  const originalFetch = globalThis.fetch;
  let adapterRequest = null;
  const registryCalls = [];
  globalThis.fetch = async (url, init = {}) => {
    const target = String(url);
    if (target.endsWith("/jwks-video-adapter.json")) {
      return Response.json({ keys: [jwk] });
    }
    if (target === "https://rtc.live.cloudflare.com/v1/apps/test-app/adapters/websocket/new") {
      adapterRequest = JSON.parse(init.body);
      return Response.json({ tracks: [{ adapterId: "adapter-123" }] });
    }
    assert.fail("Unexpected outbound request: " + target);
  };
  try {
    const response = await worker.fetch(new Request("https://worker.test/api/live/sessions/123e4567-e89b-12d3-a456-426614174000/video-adapter", {
      method: "POST",
      headers: { ...origin, Authorization: "Bearer " + token, "Content-Type": "application/json" },
      body: "{}",
    }), {
      ...env,
      OIDC_ISSUER_URL: "https://issuer.example.test",
      OIDC_JWKS_URL: "https://issuer.example.test/jwks-video-adapter.json",
      OIDC_AUDIENCE: "mehr-api",
      CLOUDFLARE_SFU_APP_ID: "test-app",
      CLOUDFLARE_SFU_APP_SECRET: "sfu-secret",
      LIVE_SESSIONS: {
        idFromName: (id) => id,
        get: () => ({ fetch: async (url, init) => {
          const path = new URL(url).pathname;
          registryCalls.push(path);
          if (path === "/lock") return new Response(null, { status: 409 });
          if (path === "/unlock") return new Response(null, { status: 200 });
          if (path === "/authorize") return Response.json({
            providerSessionId: "provider-session", expiresAt: Math.floor(Date.now() / 1000) + 240,
            consent: { microphone: true, camera: true },
            tracks: [{ mid: "1", trackName: "camera" }],
            videoRelay: null,
          });
          if (path === "/prepare-video") {
            const body = JSON.parse(init.body);
            assert.match(body.ingestToken, /^[a-f0-9]{64}$/);
            assert.equal("viewerToken" in body, false);
            return new Response(null, { status: 201 });
          }
          if (path === "/complete-video") {
            assert.equal(JSON.parse(init.body).adapterId, "adapter-123");
            return new Response(null, { status: 200 });
          }
          if (path === "/issue-viewer-ticket") {
            const body = JSON.parse(init.body);
            assert.match(body.ticket, /^[a-f0-9]{64}$/);
            assert.ok(body.ticketExpiresAt > Math.floor(Date.now() / 1000));
            return new Response(null, { status: 201 });
          }
          assert.fail("Unexpected registry operation: " + path);
        }}),
      },
    });
    const body = await response.json();
    assert.equal(response.status, 409);
    assert.equal(body.error, "session_busy");
    assert.equal(adapterRequest, null);
    assert.deepEqual(registryCalls, ["/lock"]);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("live session registry binds records to subject and tenant", async () => {
  const values = new Map();
  const state = { storage: {
    get: async (key) => values.get(key),
    put: async (key, value) => values.set(key, value),
    delete: async (key) => values.delete(key),
  }};
  const registry = new LiveSessionRegistry(state);
  const created = await registry.fetch(new Request("https://session.internal/create", {
    method: "POST", body: JSON.stringify({
      subject: "user-1", tenantId: "tenant-1", providerSessionId: "sfu-1",
      expiresAt: Math.floor(Date.now() / 1000) + 300,
      consent: { microphone: true, camera: false },
    }),
  }));
  assert.equal(created.status, 201);

  const denied = await registry.fetch(new Request("https://session.internal/authorize", {
    method: "POST", body: JSON.stringify({ subject: "user-2", tenantId: "tenant-1" }),
  }));
  assert.equal(denied.status, 404);

  const wrongTenant = await registry.fetch(new Request("https://session.internal/authorize", {
    method: "POST", body: JSON.stringify({ subject: "user-1", tenantId: "tenant-2" }),
  }));
  assert.equal(wrongTenant.status, 404);

  const allowed = await registry.fetch(new Request("https://session.internal/authorize", {
    method: "POST", body: JSON.stringify({ subject: "user-1", tenantId: "tenant-1" }),
  }));
  assert.equal(allowed.status, 200);
  assert.equal((await allowed.json()).providerSessionId, "sfu-1");
});

test("live session registry stores camera track identity and gates video relay tokens", async () => {
  const values = new Map();
  const registry = new LiveSessionRegistry({ storage: {
    get: async (key) => values.get(key),
    put: async (key, value) => values.set(key, value),
    delete: async (key) => values.delete(key),
  }});
  const expiresAt = Math.floor(Date.now() / 1000) + 300;
  assert.equal((await registry.fetch(new Request("https://session.internal/create", {
    method: "POST", body: JSON.stringify({
      subject: "owner", tenantId: "tenant", providerSessionId: "sfu",
      expiresAt, consent: { microphone: true, camera: true },
    }),
  }))).status, 201);
  assert.equal((await registry.fetch(new Request("https://session.internal/update", {
    method: "POST", body: JSON.stringify({
      subject: "owner", tenantId: "tenant", mids: ["0", "1"],
      tracks: [{ mid: "0", trackName: "microphone" }, { mid: "1", trackName: "camera" }],
    }),
  }))).status, 200);
  const prepared = await registry.fetch(new Request("https://session.internal/prepare-video", {
    method: "POST", body: JSON.stringify({
      subject: "owner", tenantId: "tenant", ingestToken: "a".repeat(64), expiresAt,
    }),
  }));
  assert.equal(prepared.status, 201);
  const authorized = await registry.fetch(new Request("https://session.internal/authorize", {
    method: "POST", body: JSON.stringify({ subject: "owner", tenantId: "tenant" }),
  }));
  const data = await authorized.json();
  assert.equal(data.tracks.find((track) => track.trackName === "camera").mid, "1");
  assert.equal(data.videoRelay.ingestToken, "a".repeat(64));
  assert.equal("viewerToken" in data.videoRelay, false);
  assert.equal((await registry.fetch(new Request("https://session.internal/complete-video", {
    method: "POST", body: JSON.stringify({ subject: "owner", tenantId: "tenant", adapterId: "adapter-1" }),
  }))).status, 200);
  const ticket = "c".repeat(64);
  assert.equal((await registry.fetch(new Request("https://session.internal/issue-viewer-ticket", {
    method: "POST", body: JSON.stringify({
      subject: "owner", tenantId: "tenant", ticket,
      ticketExpiresAt: Math.floor(Date.now() / 1000) + 20,
    }),
  }))).status, 201);
  assert.equal(values.get("session").viewerTicket.token, ticket);
  assert.equal((await registry.fetch(new Request("https://session.internal/prepare-video", {
    method: "POST", body: JSON.stringify({
      subject: "owner", tenantId: "tenant", ingestToken: "d".repeat(64), expiresAt,
    }),
  }))).status, 409);
});

test("live session registry rejects expired sessions", async () => {
  const values = new Map([["session", {
    subject: "user-1", tenantId: "tenant-1", providerSessionId: "sfu-1",
    expiresAt: Math.floor(Date.now() / 1000) - 1, mids: [],
  }]]);
  const registry = new LiveSessionRegistry({ storage: {
    get: async (key) => values.get(key),
    put: async (key, value) => values.set(key, value),
    delete: async (key) => values.delete(key),
  }});
  const result = await registry.fetch(new Request("https://session.internal/authorize", {
    method: "POST", body: JSON.stringify({ subject: "user-1", tenantId: "tenant-1" }),
  }));
  assert.equal(result.status, 404);
});


test("live session creation enforces explicit camera consent", async () => {
  const { token, jwk } = await makeOidcToken();
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (url) => {
    if (String(url).endsWith("/jwks-live-consent.json")) {
      return new Response(JSON.stringify({ keys: [jwk] }), { status: 200, headers: { "Content-Type": "application/json" } });
    }
    assert.fail("SFU must not be contacted for invalid consent");
  };
  try {
    const response = await worker.fetch(new Request("https://worker.test/api/live/sessions", {
      method: "POST",
      headers: { ...origin, Authorization: "Bearer " + token, "Content-Type": "application/json" },
      body: JSON.stringify({ mode: "voice", consent: { microphone: true } }),
    }), {
      ...env,
      OIDC_ISSUER_URL: "https://issuer.example.test",
      OIDC_JWKS_URL: "https://issuer.example.test/jwks-live-consent.json",
      OIDC_AUDIENCE: "mehr-api",
      CLOUDFLARE_SFU_APP_ID: "test-app",
      CLOUDFLARE_SFU_APP_SECRET: "test-secret",
      LIVE_SESSIONS: { idFromName: () => "session-id", get: () => ({ fetch: async () => new Response(null, { status: 201 }) }) },
    });
    assert.equal(response.status, 422);
    assert.equal((await response.json()).error, "invalid_consent_or_mode");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("creates an opaque app session after OIDC validation and durable ownership write", async () => {
  const { token, jwk } = await makeOidcToken();
  const originalFetch = globalThis.fetch;
  let sfuCalls = 0;
  let registryPath = "";
  globalThis.fetch = async (url, init) => {
    if (String(url).endsWith("/jwks-live-create.json")) {
      return new Response(JSON.stringify({ keys: [jwk] }), { status: 200, headers: { "Content-Type": "application/json" } });
    }
    if (String(url) === "https://rtc.live.cloudflare.com/v1/apps/test-app/sessions/new") {
      sfuCalls += 1;
      assert.equal(init.redirect, "manual");
      return new Response(JSON.stringify({ sessionId: "internal-sfu-session-id" }), {
        status: 200, headers: { "Content-Type": "application/json" },
      });
    }
    assert.fail("Unexpected outbound request");
  };
  try {
    const response = await worker.fetch(new Request("https://worker.test/api/live/sessions", {
      method: "POST",
      headers: { ...origin, Authorization: "Bearer " + token, "Content-Type": "application/json" },
      body: JSON.stringify({ mode: "voice", consent: { microphone: true, camera: false } }),
    }), {
      ...env,
      OIDC_ISSUER_URL: "https://issuer.example.test",
      OIDC_JWKS_URL: "https://issuer.example.test/jwks-live-create.json",
      OIDC_AUDIENCE: "mehr-api",
      CLOUDFLARE_SFU_APP_ID: "test-app",
      CLOUDFLARE_SFU_APP_SECRET: "test-secret",
      LIVE_SESSIONS: {
        idFromName: (name) => name,
        get: () => ({ fetch: async (_url, init) => {
          registryPath = new URL(_url).pathname;
          if (registryPath === "/consume") return new Response(null, { status: 200 });
          const stored = JSON.parse(init.body);
          assert.equal(stored.subject, "user-123");
          assert.equal(stored.tenantId, "tenant-123");
          assert.equal(stored.providerSessionId, "internal-sfu-session-id");
          return new Response(null, { status: 201 });
        }}),
      },
    });
    const body = await response.json();
    assert.equal(response.status, 201);
    assert.equal(sfuCalls, 1);
    assert.equal(registryPath, "/create");
    assert.match(body.session.id, /^[0-9a-f-]{36}$/i);
    assert.equal(JSON.stringify(body).includes("internal-sfu-session-id"), false);
    assert.equal(body.session.consent.camera, false);
  } finally {
    globalThis.fetch = originalFetch;
  }
});


test("compensates published SFU tracks when durable MID persistence fails", async () => {
  const { token, jwk } = await makeOidcToken();
  const originalFetch = globalThis.fetch;
  const closed = [];
  globalThis.fetch = async (url, init = {}) => {
    const target = String(url);
    if (target.endsWith("/jwks-live-compensation.json")) {
      return new Response(JSON.stringify({ keys: [jwk] }), {
        status: 200, headers: { "Content-Type": "application/json" },
      });
    }
    if (target === "https://rtc.live.cloudflare.com/v1/apps/test-app/sessions/provider-session/tracks/new") {
      return Response.json({
        sessionDescription: { type: "answer", sdp: "v=0\\r\\nvalid-answer" },
        tracks: [{ mid: "0" }],
      });
    }
    if (target === "https://rtc.live.cloudflare.com/v1/apps/test-app/sessions/provider-session/tracks/close") {
      closed.push(JSON.parse(init.body));
      return Response.json({ tracks: [{ mid: "0", errorCode: null }] });
    }
    assert.fail("Unexpected outbound request: " + target);
  };
  try {
    const response = await worker.fetch(new Request("https://worker.test/api/live/sessions/123e4567-e89b-12d3-a456-426614174000/publish", {
      method: "POST",
      headers: {
        ...origin,
        Authorization: "Bearer " + token,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        sessionDescription: { type: "offer", sdp: "v=0\\r\\noffer-sdp-content" },
        tracks: [{ location: "local", mid: "0", trackName: "microphone" }],
      }),
    }), {
      ...env,
      OIDC_ISSUER_URL: "https://issuer.example.test",
      OIDC_JWKS_URL: "https://issuer.example.test/jwks-live-compensation.json",
      OIDC_AUDIENCE: "mehr-api",
      CLOUDFLARE_SFU_APP_ID: "test-app",
      CLOUDFLARE_SFU_APP_SECRET: "test-secret",
      LIVE_SESSIONS: {
        idFromName: (id) => id,
        get: () => ({
          fetch: async (url) => {
            const path = new URL(url).pathname;
            if (path === "/consume" || path === "/lock" || path === "/unlock") return new Response(null, { status: 200 });
            if (path === "/authorize") {
              return Response.json({
                providerSessionId: "provider-session",
                consent: { microphone: true, camera: false },
                mids: [],
              });
            }
            if (path === "/update") return new Response(null, { status: 500 });
            assert.fail("Unexpected registry operation: " + path);
          },
        }),
      },
    });
    assert.equal(response.status, 502);
    assert.equal((await response.json()).error, "live_publish_failed");
    assert.equal(closed.length, 1);
    assert.deepEqual(closed[0], { tracks: [{ mid: "0" }], force: true });
  } finally {
    globalThis.fetch = originalFetch;
  }
});


test("forwards an authenticated SFU renegotiation answer only for the owned session", async () => {
  const { token, jwk } = await makeOidcToken();
  const originalFetch = globalThis.fetch;
  let forwarded = null;
  globalThis.fetch = async (url, init = {}) => {
    const target = String(url);
    if (target.endsWith("/jwks-live-renegotiate.json")) {
      return new Response(JSON.stringify({ keys: [jwk] }), {
        status: 200, headers: { "Content-Type": "application/json" },
      });
    }
    if (target === "https://rtc.live.cloudflare.com/v1/apps/test-app/sessions/provider-session/renegotiate") {
      forwarded = { method: init.method, body: JSON.parse(init.body), authorization: new Headers(init.headers).get("authorization") };
      return Response.json({ success: true });
    }
    assert.fail("Unexpected outbound request: " + target);
  };
  try {
    const response = await worker.fetch(new Request("https://worker.test/api/live/sessions/123e4567-e89b-12d3-a456-426614174000/renegotiate", {
      method: "PUT",
      headers: { ...origin, Authorization: "Bearer " + token, "Content-Type": "application/json" },
      body: JSON.stringify({ sessionDescription: { type: "answer", sdp: "v=0\\r\\nvalid-renegotiation-answer" } }),
    }), {
      ...env,
      OIDC_ISSUER_URL: "https://issuer.example.test",
      OIDC_JWKS_URL: "https://issuer.example.test/jwks-live-renegotiate.json",
      OIDC_AUDIENCE: "mehr-api",
      CLOUDFLARE_SFU_APP_ID: "test-app",
      CLOUDFLARE_SFU_APP_SECRET: "test-secret",
      LIVE_SESSIONS: {
        idFromName: (id) => id,
        get: () => ({
          fetch: async (url) => {
            const path = new URL(url).pathname;
            if (path === "/consume" || path === "/lock" || path === "/unlock") return new Response(null, { status: 200 });
            assert.equal(path, "/authorize");
            return Response.json({ providerSessionId: "provider-session", mids: [] });
          },
        }),
      },
    });
    assert.equal(response.status, 200);
    assert.equal(forwarded.method, "PUT");
    assert.deepEqual(forwarded.body, { sessionDescription: { type: "answer", sdp: "v=0\\r\\nvalid-renegotiation-answer" } });
    assert.equal(forwarded.authorization, "Bearer test-secret");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("rejects malformed renegotiation SDP before contacting the SFU", async () => {
  const { token, jwk } = await makeOidcToken();
  const originalFetch = globalThis.fetch;
  let sfuCalled = false;
  globalThis.fetch = async (url) => {
    const target = String(url);
    if (target.endsWith("/jwks-live-invalid-renegotiate.json")) {
      return new Response(JSON.stringify({ keys: [jwk] }), {
        status: 200, headers: { "Content-Type": "application/json" },
      });
    }
    sfuCalled = true;
    throw new Error("SFU must not be called");
  };
  try {
    const response = await worker.fetch(new Request("https://worker.test/api/live/sessions/123e4567-e89b-12d3-a456-426614174000/renegotiate", {
      method: "PUT",
      headers: { ...origin, Authorization: "Bearer " + token, "Content-Type": "application/json" },
      body: JSON.stringify({ sessionDescription: { type: "offer", sdp: "bad" } }),
    }), {
      ...env,
      OIDC_ISSUER_URL: "https://issuer.example.test",
      OIDC_JWKS_URL: "https://issuer.example.test/jwks-live-invalid-renegotiate.json",
      OIDC_AUDIENCE: "mehr-api",
    });
    assert.equal(response.status, 422);
    assert.equal(sfuCalled, false);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("CORS preflight explicitly permits the renegotiation PUT method", async () => {
  const response = await worker.fetch(new Request("https://worker.test/api/live/sessions/123e4567-e89b-12d3-a456-426614174000/renegotiate", {
    method: "OPTIONS",
    headers: { ...origin, "Access-Control-Request-Method": "PUT" },
  }), env);
  assert.equal(response.status, 204);
  assert.match(response.headers.get("access-control-allow-methods"), /PUT/);
});


test("does not delete an application session when SFU track closure has unresolved errors", async () => {
  const { token, jwk } = await makeOidcToken();
  const originalFetch = globalThis.fetch;
  let deleted = false;
  globalThis.fetch = async (url) => {
    const target = String(url);
    if (target.endsWith("/jwks-live-close-failure.json")) {
      return new Response(JSON.stringify({ keys: [jwk] }), {
        status: 200, headers: { "Content-Type": "application/json" },
      });
    }
    if (target === "https://rtc.live.cloudflare.com/v1/apps/test-app/sessions/provider-session/tracks/close") {
      return Response.json({ tracks: [{ mid: "0", errorCode: "internal_error" }] });
    }
    assert.fail("Unexpected outbound request: " + target);
  };
  try {
    const response = await worker.fetch(new Request("https://worker.test/api/live/sessions/123e4567-e89b-12d3-a456-426614174000", {
      method: "DELETE",
      headers: { ...origin, Authorization: "Bearer " + token },
    }), {
      ...env,
      OIDC_ISSUER_URL: "https://issuer.example.test",
      OIDC_JWKS_URL: "https://issuer.example.test/jwks-live-close-failure.json",
      OIDC_AUDIENCE: "mehr-api",
      CLOUDFLARE_SFU_APP_ID: "test-app",
      CLOUDFLARE_SFU_APP_SECRET: "test-secret",
      LIVE_SESSIONS: {
        idFromName: (id) => id,
        get: () => ({
          fetch: async (url) => {
            const path = new URL(url).pathname;
            if (path === "/consume" || path === "/lock" || path === "/unlock") return new Response(null, { status: 200 });
            if (path === "/authorize") return Response.json({
              providerSessionId: "provider-session", mids: ["0"],
            });
            if (path === "/delete") { deleted = true; return new Response(null, { status: 200 }); }
            assert.fail("Unexpected registry operation: " + path);
          },
        }),
      },
    });
    assert.equal(response.status, 502);
    assert.equal(deleted, false);
  } finally {
    globalThis.fetch = originalFetch;
  }
});


test("rejects signed OIDC tokens with invalid issuer, audience, expiry, or required scope", async () => {
  const invalidClaims = [
    { iss: "https://attacker.example.test" },
    { aud: "another-api" },
    { exp: Math.floor(Date.now() / 1000) - 10 },
    { scope: "profile:read" },
    { tenant_id: "../invalid" },
  ];
  for (let index = 0; index < invalidClaims.length; index += 1) {
    const { token, jwk } = await makeOidcToken(invalidClaims[index]);
    const originalFetch = globalThis.fetch;
    globalThis.fetch = async () => new Response(JSON.stringify({ keys: [jwk] }), {
      status: 200, headers: { "Content-Type": "application/json" },
    });
    try {
      const response = await worker.fetch(new Request("https://worker.test/api/live/capabilities", {
        headers: { ...origin, Authorization: "Bearer " + token },
      }), {
        ...env,
        OIDC_ISSUER_URL: "https://issuer.example.test",
        OIDC_JWKS_URL: "https://issuer.example.test/jwks-invalid-claims-" + index + ".json",
        OIDC_AUDIENCE: "mehr-api",
        OIDC_REQUIRED_SCOPES: "studio:access",
      });
      assert.equal(response.status, 401, "invalid claim set " + index + " must be rejected");
    } finally {
      globalThis.fetch = originalFetch;
    }
  }
});


test("inspects SFU track state for the verified owner without exposing provider session IDs", async () => {
  const { token, jwk } = await makeOidcToken();
  const originalFetch = globalThis.fetch;
  let inspectedUrl = null;
  globalThis.fetch = async (url, init = {}) => {
    const target = String(url);
    if (target.endsWith("/jwks-live-inspect.json")) {
      return new Response(JSON.stringify({ keys: [jwk] }), {
        status: 200, headers: { "Content-Type": "application/json" },
      });
    }
    inspectedUrl = target;
    assert.equal(init.method, "GET");
    return Response.json({
      sessionId: "provider-session-secret",
      tracks: [
        { mid: "0", trackName: "microphone", location: "local", status: "active" },
        { mid: "1", trackName: "camera", location: "local", status: "inactive" },
      ],
    });
  };
  try {
    const response = await worker.fetch(new Request("https://worker.test/api/live/sessions/123e4567-e89b-12d3-a456-426614174000", {
      method: "GET",
      headers: { ...origin, Authorization: "Bearer " + token },
    }), {
      ...env,
      OIDC_ISSUER_URL: "https://issuer.example.test",
      OIDC_JWKS_URL: "https://issuer.example.test/jwks-live-inspect.json",
      OIDC_AUDIENCE: "mehr-api",
      CLOUDFLARE_SFU_APP_ID: "test-app",
      CLOUDFLARE_SFU_APP_SECRET: "test-secret",
      LIVE_SESSIONS: {
        idFromName: (id) => id,
        get: () => ({
          fetch: async (url) => {
            const path = new URL(url).pathname;
            if (path === "/consume") return new Response(null, { status: 200 });
            assert.equal(path, "/authorize");
            return Response.json({ providerSessionId: "provider-session-secret", expiresAt: 1234567890 });
          },
        }),
      },
    });
    const body = await response.json();
    assert.equal(response.status, 200);
    assert.match(inspectedUrl, /provider-session-secret$/);
    assert.deepEqual(body.tracks, [
      { mid: "0", trackName: "microphone", location: "local", status: "active" },
      { mid: "1", trackName: "camera", location: "local", status: "inactive" },
    ]);
    assert.equal(JSON.stringify(body).includes("provider-session-secret"), false);
    assert.equal(JSON.stringify(body).includes("sessionId"), false);
  } finally {
    globalThis.fetch = originalFetch;
  }
});


test("creates an authenticated direct Realtime WebRTC call without exposing the API key", async () => {
  const { token, jwk } = await makeOidcToken();
  const originalFetch = globalThis.fetch;
  let captured = null;
  globalThis.fetch = async (url, init = {}) => {
    const target = String(url);
    if (target.endsWith("/jwks-realtime-call.json")) {
      return new Response(JSON.stringify({ keys: [jwk] }), {
        status: 200, headers: { "Content-Type": "application/json" },
      });
    }
    assert.equal(target, "https://api.openai.com/v1/realtime/calls");
    captured = { init, form: init.body };
    return new Response(["v=0", "valid-realtime-answer-sdp"].join("\r\n"), {
      status: 200, headers: { "Content-Type": "application/sdp" },
    });
  };
  try {
    const response = await worker.fetch(new Request("https://worker.test/api/live/realtime/calls", {
      method: "POST",
      headers: { ...origin, Authorization: "Bearer " + token, "Content-Type": "application/json" },
      body: JSON.stringify({
        sessionDescription: ["v=0", "o=- 1 1 IN IP4 127.0.0.1", "m=audio 9 UDP/TLS/RTP/SAVPF 111", "m=application 9 UDP/DTLS/SCTP webrtc-datachannel"].join("\r\n"),
        consent: { microphone: true, camera: false },
      }),
    }), {
      ...env,
      OIDC_ISSUER_URL: "https://issuer.example.test",
      OIDC_JWKS_URL: "https://issuer.example.test/jwks-realtime-call.json",
      OIDC_AUDIENCE: "mehr-api",
      OPENAI_API_KEY: "server-only-realtime-secret",
      OPENAI_REALTIME_MODEL: "gpt-realtime-2.1",
      LIVE_SESSIONS: {
        idFromName: () => "rate-limit",
        get: () => ({ fetch: async () => new Response(null, { status: 200 }) }),
      },
    });
    const answer = await response.text();
    assert.equal(response.status, 200);
    assert.equal(response.headers.get("content-type"), "application/sdp");
    assert.equal(answer, ["v=0", "valid-realtime-answer-sdp"].join("\r\n"));
    assert.equal(captured.init.redirect, "manual");
    assert.equal(new Headers(captured.init.headers).get("authorization"), "Bearer server-only-realtime-secret");
    assert.match(new Headers(captured.init.headers).get("OpenAI-Safety-Identifier"), /^[a-f0-9]{64}$/);
    assert.equal(captured.form.get("sdp").startsWith("v=0"), true);
    const session = JSON.parse(captured.form.get("session"));
    assert.equal(session.type, "realtime");
    assert.equal(session.model, "gpt-realtime-2.1");
    assert.equal(session.audio.output.voice, "marin");
    assert.equal(answer.includes("server-only-realtime-secret"), false);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("rejects direct Realtime offers containing video tracks because vision uses sampled images", async () => {
  const { token, jwk } = await makeOidcToken();
  const originalFetch = globalThis.fetch;
  let providerCalled = false;
  globalThis.fetch = async (url) => {
    if (String(url).endsWith("/jwks-realtime-video-reject.json")) {
      return new Response(JSON.stringify({ keys: [jwk] }), {
        status: 200, headers: { "Content-Type": "application/json" },
      });
    }
    providerCalled = true;
    throw new Error("Provider must not be contacted");
  };
  try {
    const response = await worker.fetch(new Request("https://worker.test/api/live/realtime/calls", {
      method: "POST",
      headers: { ...origin, Authorization: "Bearer " + token, "Content-Type": "application/json" },
      body: JSON.stringify({
        sessionDescription: ["v=0", "m=audio 9 UDP/TLS/RTP/SAVPF 111", "m=video 9 UDP/TLS/RTP/SAVPF 96"].join("\r\n"),
        consent: { microphone: true, camera: true },
      }),
    }), {
      ...env,
      OIDC_ISSUER_URL: "https://issuer.example.test",
      OIDC_JWKS_URL: "https://issuer.example.test/jwks-realtime-video-reject.json",
      OIDC_AUDIENCE: "mehr-api",
      OPENAI_API_KEY: "server-only-realtime-secret",
    });
    assert.equal(response.status, 422);
    assert.equal(providerCalled, false);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("reports Realtime as unconfigured without making an upstream call", async () => {
  const { token, jwk } = await makeOidcToken();
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (url) => {
    assert.match(String(url), /jwks-realtime-unconfigured/);
    return new Response(JSON.stringify({ keys: [jwk] }), {
      status: 200, headers: { "Content-Type": "application/json" },
    });
  };
  try {
    const response = await worker.fetch(new Request("https://worker.test/api/live/realtime/calls", {
      method: "POST",
      headers: { ...origin, Authorization: "Bearer " + token, "Content-Type": "application/json" },
      body: JSON.stringify({
        sessionDescription: "v=0\\r\\nm=audio 9 UDP/TLS/RTP/SAVPF 111",
        consent: { microphone: true, camera: false },
      }),
    }), {
      ...env,
      OIDC_ISSUER_URL: "https://issuer.example.test",
      OIDC_JWKS_URL: "https://issuer.example.test/jwks-realtime-unconfigured.json",
      OIDC_AUDIENCE: "mehr-api",
    });
    assert.equal(response.status, 503);
    assert.equal((await response.json()).error, "realtime_provider_not_configured");
  } finally {
    globalThis.fetch = originalFetch;
  }
});


test("publishes only public OIDC Authorization Code with PKCE settings", async () => {
  const response = await worker.fetch(new Request("https://worker.test/api/live/oidc/config", {
    headers: origin,
  }), {
    ...env,
    OIDC_AUTHORIZATION_URL: "https://identity.example.test/oauth2/authorize",
    OIDC_TOKEN_URL: "https://identity.example.test/oauth2/token",
    OIDC_CLIENT_ID: "mehr-web-client",
    OIDC_REDIRECT_URI: "https://mehranbaharlo58-rgb.github.io/MEHR-AI-STUDIO/",
    OIDC_PUBLIC_SCOPES: "openid profile studio:access",
  });
  const body = await response.json();
  assert.equal(response.status, 200);
  assert.equal(body.client_id, "mehr-web-client");
  assert.equal(body.token_url, "https://identity.example.test/oauth2/token");
  assert.equal(body.redirect_uri, "https://mehranbaharlo58-rgb.github.io/MEHR-AI-STUDIO/");
  assert.equal(JSON.stringify(body).includes("client_secret"), false);
});

test("fails closed when OIDC PKCE public client configuration is incomplete", async () => {
  const response = await worker.fetch(new Request("https://worker.test/api/live/oidc/config", {
    headers: origin,
  }), env);
  assert.equal(response.status, 503);
  assert.equal((await response.json()).error, "oidc_pkce_not_configured");
});

test("rejects a validly signed OIDC token issued to a different configured client", async () => {
  const { token, jwk } = await makeOidcToken({ azp: "attacker-client" });
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => new Response(JSON.stringify({ keys: [jwk] }), {
    status: 200, headers: { "Content-Type": "application/json" },
  });
  try {
    const response = await worker.fetch(new Request("https://worker.test/api/live/capabilities", {
      headers: { ...origin, Authorization: "Bearer " + token },
    }), {
      ...env,
      OIDC_ISSUER_URL: "https://issuer.example.test",
      OIDC_JWKS_URL: "https://issuer.example.test/jwks-client-check.json",
      OIDC_AUDIENCE: "mehr-api",
      OIDC_CLIENT_ID: "mehr-web-client",
    });
    assert.equal(response.status, 401);
  } finally {
    globalThis.fetch = originalFetch;
  }
});


test("live rate limiter atomically enforces per-user quotas under concurrent requests", async () => {
  const values = new Map();
  let queue = Promise.resolve();
  let storage;
  storage = {
    get: async (key) => values.get(key),
    put: async (key, value) => values.set(key, value),
    delete: async (key) => values.delete(key),
    transaction: async (callback) => {
      const previous = queue;
      let release;
      queue = new Promise((resolve) => { release = resolve; });
      await previous;
      try { return await callback(storage); }
      finally { release(); }
    },
  };
  const registry = new LiveSessionRegistry({ storage });
  const requests = Array.from({ length: 4 }, () => registry.fetch(new Request("https://session.internal/consume", {
    method: "POST", body: JSON.stringify({ action: "create" }),
  })));
  const responses = await Promise.all(requests);
  assert.deepEqual(responses.map((response) => response.status).sort(), [200, 200, 200, 429]);
  const limited = responses.find((response) => response.status === 429);
  assert.ok((await limited.json()).retryAfter > 0);
});



test("live session registry serializes mutations with an owner-scoped expiring lock", async () => {
  const values = new Map([["session", {
    subject: "user-1", tenantId: "tenant-1", providerSessionId: "sfu-1",
    expiresAt: Math.floor(Date.now() / 1000) + 300, mids: [],
  }]]);
  let queue = Promise.resolve();
  let storage;
  storage = {
    get: async (key) => values.get(key),
    put: async (key, value) => values.set(key, value),
    delete: async (key) => values.delete(key),
    transaction: async (callback) => {
      const previous = queue;
      let release;
      queue = new Promise((resolve) => { release = resolve; });
      await previous;
      try { return await callback(storage); }
      finally { release(); }
    },
  };
  const registry = new LiveSessionRegistry({ storage });
  const lock = (lockToken, path = "lock") => registry.fetch(new Request("https://session.internal/" + path, {
    method: "POST",
    body: JSON.stringify({ subject: "user-1", tenantId: "tenant-1", lockToken }),
  }));
  const [first, competing] = await Promise.all([lock("11111111-1111-4111-8111-111111111111"), lock("22222222-2222-4222-8222-222222222222")]);
  assert.deepEqual([first.status, competing.status].sort(), [200, 409]);
  const winner = first.status === 200 ? "11111111-1111-4111-8111-111111111111" : "22222222-2222-4222-8222-222222222222";
  const loser = winner.startsWith("111") ? "22222222-2222-4222-8222-222222222222" : "11111111-1111-4111-8111-111111111111";
  assert.equal((await lock(loser, "unlock")).status, 409);
  assert.equal((await lock(winner, "unlock")).status, 200);
  assert.equal((await lock(loser)).status, 200);
});
