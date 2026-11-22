# 05 — Computer Networks (CN)

| Item | Value |
|---|---|
| Date | 2026-11-22 |
| Subject | Computer Networks: application-layer protocols, client–server design, streaming, network security and reliability |
| Relevance | Strong: three network hops (browser → Next.js → FastAPI → Ollama), streamed answers, token-based service authentication |
| Main code | `team4c/app/api/chat/route.ts`, `team4c/services/teamB/client.ts`, `team4c/services/teamB/streamEvents.ts`, `team4c/services/teamA/client.ts`, `team4c/lib/serviceJwt.ts`, `team4c/lib/localStorageCapability.ts`, `team4c/lib/authRateLimit.ts`, `team4c/lib/networkMonitor.ts`, `team4c/lib/networkQuality.ts`, `team4c/next.config.ts`, `app/api/canonical_query.py`, `app/api/ingest_v1.py`, `app/core/auth.py`, `app/services/source_fetch.py`, `app/services/vector_store.py` |
| Build | Final integrated build (local demo) |
| Owners | Team 4C application (browser and Next.js side), Team 4C integration layer (backend contract routes, token verification, fetcher), Teams 4A/4B (vector-store retries), Team 4B (Ollama client) |
| Status labels | Verified, Implemented, Not verified, Open, Not implemented (see [README](README.md)) |

---

## 1. Introduction

Every EduCopilot feature is a network conversation. A student's browser talks to the Next.js server. The Next.js server talks to MongoDB and to the FastAPI backend. The backend talks to Ollama, fetches the uploaded PDF back from Next.js, and downloads YouTube captions.

All of this uses **HTTP at the application layer** over TCP, provided by the operating system and the libraries (Node.js `fetch`, Python `httpx`). The project does not implement its own transport protocol. What it does implement is the application-level design: who may call whom, how requests are authenticated, how answers are streamed, how failures are retried, and how the browser detects a bad connection.

## 2. Core concepts

| Concept | Where | Owner | Status |
|---|---|---|---|
| Client–server architecture, three tiers | Browser → `team4c` → `app` ([System architecture](../architecture/SYSTEM_ARCHITECTURE.md#a-overall-architecture)) | All | Verified (Task 21) |
| HTTP and REST APIs | Next.js route handlers in `team4c/app/api/`; FastAPI routers in `app/api/` | Team 4C (application and integration layer) | Verified (Tasks 6, 21) |
| HTTP status codes | 400, 401, 403, 404, 409, 413, 422, 429, 500, 502, 503 across both apps | Team 4C (application and integration layer) | Verified (Tasks 5, 8, 21) |
| Streaming: NDJSON (backend) | `StreamingResponse(..., media_type="application/x-ndjson")` in `app/api/canonical_query.py` | Team 4C (integration layer) | Verified (Tasks 6, 21) |
| Streaming: SSE (to the browser) | AI SDK `createUIMessageStreamResponse` (sends `text/event-stream`) in `team4c/app/api/chat/route.ts` | Team 4C | Verified (Task 21) |
| Server-to-server calls | `team4c/services/teamA/client.ts`, `team4c/services/teamB/client.ts` | Team 4C | Verified (Task 6) |
| ES256 service JWT authentication | `mintServiceJwt` in `team4c/lib/serviceJwt.ts`; `ServiceJwtVerifier.verify` in `app/core/auth.py` | Team 4C (application and integration layer) | Verified (service-token interoperability test) |
| Cookies and session revocation | Auth.js JWT cookie; `team4c/lib/authCallbacks.ts`, `team4c/lib/sessionRevocation.ts` | Team 4C | Verified (Tasks 8, 9, 21) |
| Security headers | `team4c/next.config.ts`; blocked-route headers in `app/core/production.py` | Team 4C (application and integration layer) | Verified (Task 10) |
| SSRF protection | `check_source_url`, `fetch_to_spool` in `app/services/source_fetch.py` | Team 4C (integration layer) | Implemented (`tests/test_source_fetch.py`); origin mismatch reproduced in Task 21 |
| Capability URLs | `team4c/lib/localStorageCapability.ts`, `GET /api/local-storage/[...path]` | Team 4C | Verified (PDF ingestion works end to end, Task 21) |
| Retry with exponential backoff | `VectorStoreManager._with_retry` | Teams 4A/4B | Implemented |
| Rate limiting and trusted proxies | `team4c/lib/rateLimit.ts`, `team4c/lib/authRateLimit.ts` (`AUTH_TRUSTED_PROXY_HOPS`) | Team 4C | Implemented |
| Network quality detection | `team4c/lib/networkMonitor.ts`, `team4c/lib/networkQuality.ts`, `GET /api/network-check` | Team 4C | Implemented |
| Offline queue | `team4c/components/chat/OfflineQueue.ts` | Team 4C | Implemented |

## 3. Architecture and request paths

```
            HTTPS (cookie)                     HTTP + Bearer ES256 JWT             HTTP
Browser ───────────────────► Next.js (team4c) ─────────────────────────► FastAPI (app) ─────► Ollama
   ▲  SSE (text/event-stream)    │    ▲            NDJSON stream               │
   └─────────────────────────────┘    └────────────────────────────────────────┘
                                 │
                                 ├──► MongoDB
                                 └◄── backend fetches the PDF via a capability URL (GET /api/local-storage/...)
```

- **The browser never calls the backend.** Only the Next.js server does ([System architecture](../architecture/SYSTEM_ARCHITECTURE.md#a-overall-architecture)). The backend's address and the service keys stay on the server.
- In production, the backend serves only an **allow-list** of routes (`_ALLOWED` in `app/core/production.py`): `/healthz`, `/v1/ingest`, `/v1/ingest/jobs/{id}`, `/v1/documents/{id}`, `/api/v1/query`, `/api/v1/query/stream`, session seed/delete, and session history **only with** an `Authorization` header. Everything else returns 404 before any handler runs.

## 4. Project implementation, step by step

### 4.1 HTTP and REST

Resources are nouns in the URL. Actions are HTTP methods:

| Method + path (Next.js) | Meaning |
|---|---|
| `GET /api/workspaces` / `POST /api/workspaces` | List / create workspaces |
| `GET` / `DELETE /api/workspaces/[id]` | Read / delete (cascade) one workspace |
| `GET` / `POST /api/workspaces/[id]/conversations` | Paginated list / create |
| `PATCH` / `DELETE /api/conversations/[id]` | Rename / delete |
| `POST /api/workspaces/[id]/files`, `DELETE …/files/[fileId]`, `POST …/files/[fileId]/retry` | Upload, delete, retry |
| `POST /api/chat` | Ask a question (streamed) |
| `GET /api/health?ready=1`, `GET /api/network-check` | Readiness, connectivity probe |

The backend contract ([API documentation §7](../technical/API_DOCUMENTATION.md#7-integration-api-fastapi-server-to-server)) uses the same style: `POST /v1/ingest`, `GET /v1/ingest/jobs/{id}`, `DELETE /v1/documents/{id}`, `POST /api/v1/query/stream`, `POST /api/v1/sessions/{id}/seed`, `DELETE /api/v1/sessions/{id}`.

### 4.2 HTTP status codes used deliberately

| Code | Example in the project |
|---|---|
| 400 | Blank question ("Please enter a question."), question over 2,000 characters (`/api/chat`) |
| 401 | No or expired session: every data route answers `{"error":"Unauthorized."}`. Backend: missing, invalid, expired or **replayed** service token (with `WWW-Authenticate: Bearer`) |
| 403 | Backend: token for the wrong audience, or scope does not match the audience |
| 404 | A workspace that exists but belongs to someone else, **the same as** a missing one (`assertOwnership`). Unlisted backend routes in production |
| 409 | A question is "already being answered" by another attempt; ingestion conflict |
| 413 | Backend: source file too large (`file_too_large` → `payload_too_large`) |
| 422 | Backend: invalid request body or unsupported type (MP4) |
| 429 | Chat or sign-in rate limit, with a `Retry-After` header; backend ingest queue full |
| 502 | Backend unreachable or failed upstream (`fetch_failed`, `embed_failed`); workspace delete could not remove documents from search |
| 503 | Backend dependency unavailable (session store, ingest registry, no JWT verifier configured) |

**404 instead of 403 for foreign data** stops "enumeration": an attacker cannot learn which workspace ids exist.

### 4.3 Streaming: NDJSON from the backend, SSE to the browser

An LLM answer takes seconds. Streaming lets the student see progress instead of a blank screen.

**Backend → Next.js: NDJSON (newline-delimited JSON).** `POST /api/v1/query/stream` returns `StreamingResponse(events(), media_type="application/x-ndjson")`. Each line is one JSON object (`_line` in `app/api/canonical_query.py`):

```
{"type": "draft", "text": "…"}        only with ?draft=1: unverified preview text
{"type": "delta", "text": "Deadlock is a "}
{"type": "delta", "text": "situation where …"}
{"type": "done", "answer": "…", "source_attributions": [...], ...}
{"type": "error", "detail": "<fixed safe message>"}
```

Important detail: the backend **checks the complete answer before streaming it** (decline detection, lexical support and citation checks). It then sends the checked answer as `delta` events in word-aligned pieces of about 32 characters (`_pieces`). The live model output is only visible through optional `draft` events, which the UI shows in a separate, clearly marked area.

**Next.js reads the NDJSON stream** in `team4c/services/teamB/client.ts`: `response.body.getReader()` and a `TextDecoder` collect bytes, split them into lines, and `parseTeamBStreamLine` / `classifyTeamBStreamEvent` (`team4c/services/teamB/streamEvents.ts`) validate each event. An unexpected shape raises `TeamBStreamProtocolError`.

**Next.js → browser: Server-Sent Events.** `/api/chat` converts the events into an AI SDK UI message stream with `createUIMessageStream` and returns `createUIMessageStreamResponse`. The installed `ai` package sends it as `text/event-stream` with `cache-control: no-cache` (its `UI_MESSAGE_STREAM_HEADERS`). The browser hook `useChatStream` (built on `useChat` from `@ai-sdk/react`) renders the parts as they arrive.

**Why NDJSON between servers and SSE to the browser?** NDJSON is the simplest line-based format for a server-to-server POST response and is easy to parse in both Python and TypeScript. SSE is what the AI SDK's browser hook expects. Both are one-way, server-to-client streams over an ordinary HTTP response, which is all a chat answer needs. WebSockets (two-way) would add connection management for no benefit.

### 4.4 Next.js → FastAPI: service JWTs

For each backend call, the Next.js server signs a fresh token (`mintServiceJwt` in `team4c/lib/serviceJwt.ts`, `jose` library):

| Claim / header | Value |
|---|---|
| `alg` | `ES256` (ECDSA, P-256 curve) |
| `kid` | Key id, so the backend picks the right public key |
| `iss` | Fixed issuer (`SERVICE_JWT_ISSUER`) |
| `aud` | `team4a-ingestion` or `team4b-query` |
| `scope` | `ingest` or `query` (must match the audience) |
| `sub`, `workspace_id` | From the **server-verified** session and the ownership check, never from the request body |
| `iat`, `exp` | Default lifetime 300 s (`DEFAULT_SERVICE_JWT_TTL_SECONDS`) |
| `jti` | `randomUUID()`: unique id for replay protection |

The token travels as `Authorization: Bearer <token>`. `require_service_principal(audience)` in `app/core/auth.py` reads the header and `ServiceJwtVerifier.verify` checks everything (details in [08 Information Security §3.2](08_Information_Security.md#32-jwt-signing-and-verification)). The backend holds **only the public key** (JWKS file), so even a fully compromised backend cannot mint tokens.

### 4.5 Browser → Next.js: Auth.js cookies and revocation

- Auth.js v5 keeps the session in a **JWT cookie** (`strategy: "jwt"` in `team4c/lib/auth.ts`). Cookies are sent automatically by the browser with each same-site request.
- When `AUTH_URL` uses https, the cookie gets the `__Secure-` prefix and the `Secure` flag, so browsers send it only over HTTPS ([Authentication and security §2](../technical/AUTHENTICATION_AND_SECURITY.md#2-student-login-authjs)).
- Each sign-in puts a random `sid` in the token (`team4c/lib/authCallbacks.ts`). Logout records the `sid` in MongoDB `revokedsessions`, and every request rejects revoked or `sid`-less tokens. Without this, a stateless JWT would stay valid until it expired even after logout.

### 4.6 HTTP security headers

`team4c/next.config.ts` adds to every response:

| Header | Value | Protects against |
|---|---|---|
| `Content-Security-Policy` | `frame-ancestors 'none'; object-src 'none'; base-uri 'self'; form-action 'self'` | Clickjacking, plugin content, `<base>` hijacking, forms posting elsewhere |
| `X-Frame-Options` | `DENY` | Clickjacking (older browsers) |
| `X-Content-Type-Options` | `nosniff` | MIME-type sniffing |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Leaking full URLs to other sites |
| `Permissions-Policy` | `camera=(), microphone=(), geolocation=()` | Unneeded browser features |
| `Strict-Transport-Security` | Optional, only when `HSTS_MAX_AGE` is set and `AUTH_URL` is https | Downgrade to plain HTTP. The primary place for HSTS is the TLS reverse proxy |

The backend's production 404 responses carry `Cache-Control: no-store`, `nosniff` and a restrictive CSP (`_BLOCKED_HEADERS` in `app/core/production.py`).

### 4.7 SSRF protection when the backend downloads a PDF

The backend downloads the uploaded PDF from the URL Next.js gives it. Without care, a URL pointing at an internal service (for example `http://localhost:6379` or a cloud metadata address) would make the backend attack its own network: **Server-Side Request Forgery**. `app/services/source_fetch.py` prevents this:

1. **Origin allow-list:** scheme, host and port must exactly match `INGEST_ALLOWED_ORIGINS`. An empty list allows nothing.
2. **Two parsers must agree:** the origin is computed with `urllib` and with `httpx`. A URL that two parsers read differently is refused (`"ambiguous URL"`).
3. URLs with user info, fragments, backslashes, whitespace or non-ASCII characters are refused.
4. **No redirects** (`follow_redirects=False`; any status other than 200 fails), so an allowed server cannot bounce the request to an internal address.
5. **Environment proxies ignored** (`trust_env=False`); no cookies or credentials are sent.
6. **Size limits** checked against `Content-Length` and again while streaming.
7. **Content check:** the first bytes must be `%PDF-` for a PDF.
8. The URL (whose query string carries a capability token) is never logged; only its origin and a SHA-256 of its path.

`AUTH_URL` (frontend) and `INGEST_ALLOWED_ORIGINS` (backend) must name the same origin. With a mismatch every ingest fails with 422, as reproduced in Task 21 (see [Environment](../guides/ENVIRONMENT.md) and [Setup §5](../guides/SETUP.md#5-troubleshooting-from-project-experience)).

### 4.8 Capability URLs

The backend has no user session, but it must read one specific uploaded file. Next.js gives it a **capability URL**: a link that itself carries the permission.

- `mintLocalStorageCapabilityToken(workspaceId, publicId)` in `team4c/lib/localStorageCapability.ts` signs a token (HS256 with `AUTH_SECRET`, `jose`) bound to exactly that workspace and file, with issuer `edu-copilot-team-c-local-storage`, audience `local-storage-capability` and a **10-minute** expiry.
- `GET /api/local-storage/[...path]` accepts the token only if the signature, issuer, audience and expiry are valid **and** the token's `workspaceId`/`publicId` match the requested file.
- The idea matches a presigned object-storage URL. It applies only to the local storage mode used by this project.

### 4.9 Retry with exponential backoff

`VectorStoreManager._with_retry` (`app/services/vector_store.py`) retries Qdrant calls up to `vector_store_max_retries` times (default 3) on transient errors: connection errors, timeouts, HTTP 429 or 5xx, and gRPC `UNAVAILABLE` / `DEADLINE_EXCEEDED` / `RESOURCE_EXHAUSTED` codes from the Qdrant client. It waits `base × 2^(attempt−1)` between attempts (base 0.5 s: 0.5 s, then 1 s). Non-transient errors (for example HTTP 400) fail immediately. After the last attempt it raises `VectorStoreUnavailable` with a generic message, so host names and credentials in the original error never reach the caller.

The waits have **no random jitter**. With many clients, synchronised retries could arrive together. That does not matter for a single-process backend.

### 4.10 Rate limiting and trusted proxies

- `/api/chat`: 20 requests per minute per user by default (`CHAT_RATE_LIMIT_PER_MINUTE`). Over the limit → **429** with `Retry-After`.
- Sign-in and sign-up have three independent limits each: per email, per client address and global (`AUTH_RATE_LIMIT_POLICIES` in `team4c/lib/authRateLimit.ts`). Example: sign-in 30 per address per 15 minutes; sign-up 10 per address per hour.
- **Client address:** by default the first `X-Forwarded-For` entry. When the app is reached directly, a client can put any value there, so the per-address limit is a best-effort brake; the per-email and global limits cannot be bypassed by changing headers. Behind known reverse proxies that **append** to the header, `AUTH_TRUSTED_PROXY_HOPS` tells the code how many trusted entries to count from the right, so it uses the address the last trusted proxy actually saw.
- Emails and addresses are stored only as SHA-256 hashes inside counter keys.

### 4.11 Network quality detection

`team4c/lib/networkMonitor.ts` and `team4c/lib/networkQuality.ts` show the student a connection indicator:

1. **Browser hints:** `navigator.onLine`, `online`/`offline` events, and the Network Information API (`navigator.connection.effectiveType`, `downlink`, `rtt`) where the browser supports it. These are estimates.
2. **Measured latency:** timed `GET /api/network-check` requests (`performance.now()` before and after). The route does no authentication, database access or logging, so the measurement reflects the network rather than server work.
3. **Measured bandwidth:** `GET /api/network-check?payload=bandwidth` returns exactly 128 KiB of **random** bytes. Random data cannot be compressed by gzip or brotli, so the measured throughput is not inflated. Responses are `Cache-Control: no-store`.
4. `classifyLatency` and `classifyBandwidth` convert numbers into tiers. Measured values take priority over browser estimates. The overall result is one of `good`, `moderate`, `poor`, `very-poor`, `offline` or `unknown`.

### 4.12 Offline queue behaviour

`navigator.onLine` is only a hint: a browser can say "online" while requests still fail. `team4c/components/chat/OfflineQueue.ts` therefore:

- uses `isOffline()` only to decide whether to try sending at all;
- uses `isNetworkError(error)` on a real failed request as the authority;
- keeps unsent messages in memory, and `flushOfflineQueue` sends them in FIFO order when the connection returns. A failed item and everything after it stay queued.

The queue is not persisted, so closing the tab loses it.

## 5. Alternatives and design trade-offs

| Decision | Alternative | Trade-off |
|---|---|---|
| Browser never calls the backend | Expose the backend publicly with CORS | One trust boundary and no service keys in the browser; Next.js is an extra hop and must relay streams |
| NDJSON between servers | SSE, WebSockets, gRPC streaming | Simple to produce and parse; one-way only (enough for answers) |
| SSE to the browser (via AI SDK) | WebSockets | Works over plain HTTP, proxies and the AI SDK hook; server-to-client only |
| Check the full answer, then stream it | Stream raw model tokens | Unsupported or declined text never appears as an answer; the student waits for generation before verified text starts |
| Short-lived ES256 JWT per request | Static API key, or mutual TLS | No long-lived shared secret; backend holds only public keys; requires synchronised clocks (30 s leeway) |
| Capability URL for PDF fetch | Give the backend direct disk access or a shared bucket | Works across hosts and limits access to one file for 10 minutes; the backend must be able to reach Next.js |
| No redirects in the fetcher | Follow redirects with re-validation | Simpler and safer; a storage provider that redirects would not work |
| Exponential backoff without jitter | Backoff with jitter | Simple; jitter only matters with many concurrent clients |

## 6. Limitations and concepts not implemented

| Item | Status |
|---|---|
| WebSockets | **Not implemented** |
| gRPC networking by the project | **Not implemented** (gRPC appears only as error types from the Qdrant client library; `QDRANT_PREFER_GRPC=false` in `.env.example`) |
| Custom TCP/UDP code, sockets programming, routing protocols | **Not implemented** |
| TLS termination inside the apps | **Not implemented**: HTTPS is expected at a reverse proxy; public production deployment prerequisites are **Not verified** ([Deployment](../guides/DEPLOYMENT.md#2-what-a-real-production-deployment-would-require)) |
| Rate limits shared across instances | **Not implemented** (in-process only) |
| Per-address rate limit is spoofable when the app is reached directly | **Open**, documented in `team4c/lib/authRateLimit.ts` |
| Offline queue survives reload | **Not implemented** |
| Legacy workbench routes are unauthenticated in development mode | **Open** (T4AB-08); blocked in production |

## 7. Interview questions

**Q1. Why does the browser never call the FastAPI backend directly?**
So there is one trust boundary. Next.js authenticates the student, checks ownership in MongoDB, and only then calls the backend with a short-lived token whose `workspace_id` comes from that check. The backend address and the signing key never reach the browser. The cost is an extra hop and relaying the stream.

**Q2. How is the answer streamed, and in which formats?**
The backend sends NDJSON, one JSON event per line (`delta`, `draft`, `done`, `error`). Next.js reads it with a stream reader, validates each line, and re-emits it to the browser as an AI SDK UI message stream, which the `ai` package sends as Server-Sent Events (`text/event-stream`). Both are one-way HTTP streams.

**Q3. Is the answer streamed token by token from the model?**
Not the verified answer. The backend generates the full answer, checks it (declines, support and citations), then streams the checked text in about 32-character word-aligned pieces. Live model output is available only as optional `draft` events, shown separately as an unverified preview.

**Q4. Why WebSockets were not used?**
A chat answer is server-to-client only. SSE and NDJSON work over ordinary HTTP responses, pass through proxies, and match the AI SDK. WebSockets would add connection state and reconnection logic for no gain.

**Q5. How does the backend know a request really came from Next.js?**
Each request carries an ES256-signed JWT. The backend verifies the signature with the public key selected by `kid`, and checks issuer, exact audience, scope, lifetime (at most 300 s), required claims and the `jti` (single use). It holds no private key.

**Q6. What is SSRF, and how does the project prevent it?**
SSRF tricks a server into requesting internal addresses. `source_fetch.py` allows only exact allow-listed origins, requires two URL parsers to agree, refuses redirects and environment proxies, limits size, checks the `%PDF-` signature and never logs the URL.

**Q7. What is a capability URL, and how long does it live?**
A URL that carries its own permission: an HS256-signed token bound to one workspace and one file, valid for 10 minutes. The backend uses it to fetch the uploaded PDF without a user session.

**Q8. Why return 404 instead of 403 for another student's workspace?**
403 would confirm that the id exists. Returning the same 404 as for a missing id stops attackers from enumerating ids. Task 21 verified that a second account received 404 on every read, list, create and delete of the first account's workspace.

**Q9. How does retry with backoff work in the project, and what is missing?**
Qdrant calls are retried up to 3 times on transient errors (connection, timeout, 429/5xx, certain gRPC codes), waiting 0.5 s then 1 s. Other errors fail immediately. There is no jitter; with many clients, jitter would spread retries out.

**Q10. How does the rate limiter find the client's IP behind a proxy?**
By default it uses the first `X-Forwarded-For` entry, which a client can forge when reaching the app directly. With `AUTH_TRUSTED_PROXY_HOPS`, it counts back from the right past the trusted proxies to the address they recorded. The per-email and global limits do not depend on the IP at all.

**Q11. How does the app measure bandwidth accurately?**
It downloads exactly 128 KiB of random bytes from `/api/network-check?payload=bandwidth` with caching disabled. Random bytes cannot be compressed, so the bytes transferred equal the bytes counted. Latency uses a tiny request that does no database or authentication work.

**Q12. Which headers protect against clickjacking?**
`Content-Security-Policy: frame-ancestors 'none'` and `X-Frame-Options: DENY`. Both stop other sites from embedding EduCopilot in a frame.

## 8. References

- [System architecture](../architecture/SYSTEM_ARCHITECTURE.md): service-to-service communication and streaming
- [API documentation](../technical/API_DOCUMENTATION.md): every application and integration endpoint
- [Chat and streaming](../technical/CHAT_AND_STREAMING.md): the three hops and the stream events
- [LLM streaming](../learning/LLM_STREAMING.md) and [JWT and authentication](../learning/JWT_AND_AUTHENTICATION.md): beginner explanations
- [Authentication and security](../technical/AUTHENTICATION_AND_SECURITY.md) and [Deployment](../guides/DEPLOYMENT.md): headers, allow-list, production rules
- Internal verification records (not published): backend integration verification (Task 6), service-token interoperability test, draft-streaming report
- Related subjects: [08 Information Security](08_Information_Security.md), [04 OS](04_Operating_Systems.md)
