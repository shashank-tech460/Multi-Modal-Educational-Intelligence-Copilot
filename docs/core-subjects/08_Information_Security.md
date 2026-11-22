# 08 — Information Security

| Item | Value |
|---|---|
| Date | 2026-11-22 |
| Subject | Information Security: cryptography, authentication, authorisation, integrity, confidentiality and secure design |
| Relevance | Strong: public-key service tokens, password hashing, session revocation, SSRF defence, isolation between students |
| Main code | `team4c/lib/serviceJwt.ts`, `app/core/auth.py`, `team4c/lib/credentialsAuthorize.ts`, `team4c/app/api/auth/signup/route.ts`, `team4c/lib/authCallbacks.ts`, `team4c/lib/sessionRevocation.ts`, `team4c/lib/authRateLimit.ts`, `team4c/lib/ownership.ts`, `team4c/lib/localStorageCapability.ts`, `team4c/lib/callbackUrl.ts`, `team4c/lib/validation.ts`, `team4c/lib/productionEnv.ts`, `team4c/next.config.ts`, `app/services/source_fetch.py`, `app/services/vector_store.py`, `app/core/production.py`, `app/core/errors.py` |
| Build | Final integrated build (local demo) |
| Owners | Team 4C application (accounts, sessions, ownership, signing), Team 4C integration layer (token verification, SSRF defence, production allow-list, tenant isolation added to the vector store) |
| Status labels | Verified, Implemented, Not verified, Open, Not implemented (see [README](README.md)) |

---

## 1. Introduction

Security answers four separate questions. EduCopilot addresses each with different mechanisms, so it helps to keep them apart:

| Property | Question | Main mechanisms in EduCopilot |
|---|---|---|
| **Authentication** | *Who are you?* | Passwords hashed with bcrypt (students); ES256-signed service JWTs (Next.js → backend) |
| **Authorisation** | *What may you do?* | Ownership checks (404 for foreign data), token audience and scope, workspace-scoped retrieval, production route allow-list |
| **Integrity** | *Has this been changed?* | Digital signatures (ES256, HS256), SHA-256 content hashes, single-use token ids |
| **Confidentiality** | *Who can read this?* | `Secure` cookies and HTTPS (at the TLS proxy), capability URLs, no secrets or content in logs, isolation between workspaces |

The project does **not** implement encryption at rest or end-to-end encryption (see §5).

## 2. Core concepts

| Concept | Where | Owner | Status |
|---|---|---|---|
| Public-key cryptography (ECDSA P-256 / ES256) | `team4c/lib/serviceJwt.ts` (sign), `app/core/auth.py` (verify) | Team 4C (application and integration layer) | Verified (service-token interoperability test) |
| JWT claims: `kid`, `iss`, `aud`, `exp`, `iat`, `scope`, `sub`, `workspace_id`, `jti` | `ServiceJwtVerifier.verify` | Team 4C (integration layer) | Verified (service-token interoperability test) |
| Single-use tokens / replay prevention | `ReplayCache` | Team 4C (integration layer) | Verified (interoperability test: second use → 401) |
| Password hashing | bcrypt cost 12 (`SALT_ROUNDS = 12`), dummy-hash timing equalisation | Team 4C | Implemented (`team4c/tests/unit/bcrypt.test.ts`, `credentials-authorize.test.ts`) |
| SHA-256 integrity and deduplication | Upload route, ingest store, source fetcher | Team 4C (application and integration layer) | Verified (dedupe, Tasks 8, 13) |
| SSRF protection | `app/services/source_fetch.py` | Team 4C (integration layer) | Implemented (`tests/test_source_fetch.py`) |
| CSP and security headers | `team4c/next.config.ts`; `_BLOCKED_HEADERS` in `app/core/production.py` | Team 4C (application and integration layer) | Verified (Task 10) |
| Cookie security | Auth.js JWT cookie, `__Secure-` / `Secure` when `AUTH_URL` is https | Team 4C | Implemented; public HTTPS deployment **Not verified** |
| Session revocation | `team4c/lib/authCallbacks.ts`, `team4c/lib/sessionRevocation.ts` | Team 4C | Verified (Tasks 8, 9, 21) |
| Capability-based file access | `team4c/lib/localStorageCapability.ts` | Team 4C | Implemented; used by every PDF ingestion in Task 21 |
| Rate limiting | `team4c/lib/rateLimit.ts`, `team4c/lib/authRateLimit.ts` | Team 4C | Implemented; sign-up limit observed live in Task 21 |
| Input validation | `team4c/lib/validation.ts`, `team4c/lib/callbackUrl.ts`, Pydantic `extra="forbid"` | Team 4C (application and integration layer) | Verified (callback safety, Task 21) |
| Ownership checks and workspace isolation | `assertOwnership`; `RetrievalScope`, `tenant_filter`, `_LegacyClientGuard` | Team 4C (application); Teams 4A/4B with Team 4C workspace scoping | Verified (Task 5: 118/118 live checks; Task 21) |
| Fail-safe production configuration | `team4c/lib/productionEnv.ts`, `app/core/production.py` | Team 4C (application and integration layer) | Verified (Task 10) |

## 3. Project implementation, step by step

### 3.1 Public-key cryptography and ES256

**ES256** = ECDSA signatures on the NIST P-256 curve with SHA-256.

- The **private key** (PKCS8 PEM in `SERVICE_JWT_PRIVATE_KEY`) exists only on the Next.js server. It is loaded by `loadServiceJwtSigningConfigFromEnv` and imported with `importPKCS8`. The code comments state it is never logged.
- The backend holds only the **public keys**, as a JWKS file (`SERVICE_JWT_JWKS_FILE`). `load_jwks` in `app/core/auth.py` accepts at most 20 keys in at most 64 KiB, and rejects any key that is not an EC **P-256 public** key.

**Why asymmetric here?** If the backend were compromised, an attacker would learn only public keys and still could not create valid tokens. With a shared secret (for example HS256), anyone who can verify can also sign.

### 3.2 JWT signing and verification

`mintServiceJwt` in `team4c/lib/serviceJwt.ts` creates a token for each backend call. `ServiceJwtVerifier.verify(token, audience)` in `app/core/auth.py` checks it **in this order**, rejecting at the first failure:

| # | Check | Defends against |
|---|---|---|
| 1 | String, at most 4,096 characters, exactly two dots | Oversized or malformed input |
| 2 | Header `alg` must be exactly `ES256` | **Algorithm confusion** (for example `alg: none`, or HS256 using the public key as a secret) |
| 3 | Header must not contain `jwk`, `jku`, `x5u`, `x5c` or `crit` (`FORBIDDEN_HEADERS`) | Attacker-supplied keys or key URLs |
| 4 | `typ` absent or `JWT`; `kid` known | Using an unknown key |
| 5 | Signature, `aud` (strict), `iss`, `exp`, `iat`, `nbf`, with 30 s leeway; required claims `exp, iat, iss, aud, sub, jti` | Forged or altered tokens, tokens for another service |
| 6 | Re-check `aud` and `iss` exactly; `exp`/`iat` are integers; `exp > iat`; lifetime ≤ 300 s; `iat` not in the future | Long-lived or odd tokens (defence in depth) |
| 7 | `scope` equals the audience's scope (`team4a-ingestion` → `ingest`, `team4b-query` → `query`) | Using an ingest token to query, or the reverse (403) |
| 8 | `workspace_id` matches `^[A-Za-z0-9_-]{1,128}$`; `sub` present, at most 256 characters | Injection through identity fields |
| 9 | `jti` well formed and **not used before** (`ReplayCache.use_once`) | **Replay** (401 "token already used") |

The result is a frozen `ServicePrincipal` (subject, workspace, scope, audience, token id, expiry). Route handlers take the workspace **only** from it, never from the request body. Rejections are logged with a short reason and the audience, never the token.

If the JWKS file or issuer is missing or invalid, `build_service_jwt_verifier` returns `None` and every protected route answers **503**: the system fails closed instead of accepting unverified requests.

### 3.3 Single-use token ids and replay prevention

A stolen token would be valid until it expires (up to 300 s). `ReplayCache` stores each `jti` with its expiry and refuses a second use. When the cache is full (100,000 by default) it removes expired ids. If it is still full, it answers **503** rather than forget ids that are still valid. The service-token interoperability test verified that a valid token was accepted once for its correct audience and rejected with 401 on the second use.

**Limitation:** the cache is in process memory. With several backend processes, a token could be replayed on another process. The current design is single-process (see [04 OS §3.11](04_Operating_Systems.md#311-single-process-constraint)).

### 3.4 Password hashing

- **Sign-up** (`team4c/app/api/auth/signup/route.ts`): `bcrypt.hash(password, SALT_ROUNDS)` with `SALT_ROUNDS = 12`. bcrypt adds a random salt and is deliberately slow, so leaked hashes are expensive to crack and identical passwords give different hashes.
- **Sign-in** (`authorizeCredentials` in `team4c/lib/credentialsAuthorize.ts`): the user is loaded with `.select("+passwordHash")`. The code **always** runs one `bcrypt.compare`, against a fixed dummy hash when the email does not exist. Both failure cases take the same time, so response timing does not reveal which emails have accounts.
- `passwordHash` is never returned from `authorize()`, so it never enters the session JWT.
- bcrypt only uses the first 72 bytes of a password. Validation refuses longer passwords by **UTF-8 byte length** (`MAX_PASSWORD_BYTES = 72` in `team4c/lib/validation.ts`), instead of silently ignoring the extra characters.
- An unreachable database during sign-in raises `ServiceUnavailableSignin`, not "wrong password".

### 3.5 SHA-256 for integrity and deduplication

| Use | Where | Purpose |
|---|---|---|
| Upload dedupe | `createHash("sha256")` in `team4c/app/api/workspaces/[id]/files/route.ts`; unique index on `(workspaceId, contentSha256)` | Same content stored once per workspace |
| Spool integrity | `fetch_to_spool` (`app/services/source_fetch.py`), `_sha256_file` (`app/services/ingest_store.py`) | Records the digest of the downloaded bytes; recovery re-queues a job only if its spool is intact |
| Privacy-preserving keys and logs | Rate-limit keys (`authRateLimit.ts`); `SourceRef.path_sha256`; registry file names `sha256(workspace_id)` | Store or log a hash instead of an email, IP address, URL path or id |

SHA-256 is used here as a **hash**, not encryption. It detects changes and duplicates but does not hide content from anyone who has the data. Rate-limit keys hash low-entropy values (emails, IP addresses) without a secret, so they reduce casual exposure in memory dumps but would not stop a determined guess. They are never logged.

### 3.6 SSRF protection

The backend downloads uploaded PDFs from a URL supplied by Next.js. `app/services/source_fetch.py` allows only exact allow-listed origins, requires two URL parsers to agree, refuses user info, fragments, backslashes and non-ASCII characters, never follows redirects, ignores environment proxies, sends no credentials, limits size during streaming, checks the `%PDF-` signature, and never logs or stores the URL's query string. Full walkthrough: [05 Computer Networks §4.7](05_Computer_Networks.md#47-ssrf-protection-when-the-backend-downloads-a-pdf).

### 3.7 CSP and HTTP security headers

`team4c/next.config.ts` sets `Content-Security-Policy: frame-ancestors 'none'; object-src 'none'; base-uri 'self'; form-action 'self'`, `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin` and a `Permissions-Policy` that disables camera, microphone and geolocation. HSTS is optional in the app and primarily set at the TLS proxy. Details: [05 Computer Networks §4.6](05_Computer_Networks.md#46-http-security-headers).

**What the CSP does not cover:** it has no `script-src` or `default-src` directive, so it does not restrict where scripts load from. Its purpose is anti-framing and blocking plugins, `<base>` hijacking and foreign form targets. Cross-site scripting protection therefore relies on React's output escaping and on `team4c/components/chat/MarkdownContent.tsx`, which renders answers with `react-markdown` and does not use `dangerouslySetInnerHTML` or `rehype-raw`, so raw HTML in an answer is not rendered as HTML.

### 3.8 Cookie security

- Auth.js v5 stores the session as a JWT in a cookie (`strategy: "jwt"` in `team4c/lib/auth.ts`).
- With an https `AUTH_URL`, the cookie name gets the `__Secure-` prefix and the `Secure` flag, so browsers send it only over HTTPS ([Authentication and security §2](../technical/AUTHENTICATION_AND_SECURITY.md#2-student-login-authjs)). `productionEnv.ts` requires https for non-loopback production URLs.
- Cookie flags beyond these (for example `HttpOnly` and `SameSite`) use Auth.js defaults. The project does not override them, and this document does not claim specific values for them.

### 3.9 Session revocation

A stateless JWT stays valid until it expires (the Auth.js default lifetime is 30 days, `DEFAULT_SESSION_SECONDS` in `team4c/lib/authCallbacks.ts`). To make logout real:

1. Each sign-in puts a random `sid` (`randomUUID()`) in the token.
2. Logout (`events.signOut`) records the `sid` in MongoDB `revokedsessions` until the token's expiry plus one hour. A TTL index then removes it.
3. The `jwt` callback returns `null` for a revoked or `sid`-less token, which makes Auth.js clear the cookie.
4. **Outage handling (Tasks 8, 9):** revocations are also kept in process memory (up to 50,000 entries), so a session logged out on this server stays rejected while MongoDB is unreachable. Revocations that could not be written are queued and written once MongoDB is back.

**Remaining risk (Open):** a revocation still queued when the process stops during an outage is lost. Documented in `team4c/lib/sessionRevocation.ts`.

### 3.10 Capability-based file access

The backend has no student session but must read one uploaded PDF. Next.js mints a capability token (`mintLocalStorageCapabilityToken`): HS256 with `AUTH_SECRET`, its own issuer and audience, a 10-minute expiry, and bound to exactly one `(workspaceId, publicId)`. `verifyLocalStorageCapabilityToken` rejects a valid token minted for any other file. HS256 is appropriate here because the same server both signs and verifies (one trust boundary). The separate issuer and audience stop it from being accepted anywhere else.

**Limitation:** the token is not single-use. Anyone who obtains the URL can download that one file until it expires. The fetcher never logs the query string, which reduces the chance of leaking it.

### 3.11 Rate limiting

| Limit | Default | Window |
|---|---|---|
| Sign-in per email / per client address / global | 10 / 30 / 300 | 15 min / 15 min / 1 min |
| Sign-up per email / per client address / global | 5 / 10 / 100 | 1 hour each |
| Chat per user | 20 | 1 min |

Limits run **before** any database lookup or bcrypt work, so a flood cannot exhaust CPU. Each limit has its own store, so flooding one cannot evict another's counters. The per-address limit is best effort because `X-Forwarded-For` can be forged when the app is reached directly; the per-email and global limits cannot be bypassed that way. Counters are per process and reset on restart. Details: [05 Computer Networks §4.10](05_Computer_Networks.md#410-rate-limiting-and-trusted-proxies).

### 3.12 Input validation and ownership checks

**Validation (examples):**

| Input | Rule | Where |
|---|---|---|
| Question | Not blank; at most 2,000 code points (`Array.from(text).length`, so an emoji counts once) | `team4c/lib/validation.ts`, backend `MAX_QUERY_CHARS` |
| Conversation title | Length limit; no control characters or bidirectional override/isolate characters (`DISALLOWED_TITLE_CHARACTERS`); must contain a visible character | `validateConversationTitle` |
| Upload | PDF by MIME type with extension fallback; at most 50 MB; MP4 refused with a clear message. The backend then requires the `%PDF-` signature, so a renamed non-PDF fails ingestion | `validateUploadedFile`, `fetch_to_spool` |
| YouTube URL | Strict host and an 11-character video id | `validateYoutubeUrl`, `youtube_video_id` |
| Callback URL after login | Only root-relative `/dashboard…` and `/workspace/<id>…`; anything else → `/dashboard` (prevents open redirects) | `team4c/lib/callbackUrl.ts` |
| Backend request bodies | Unknown fields rejected (`extra="forbid"`) | `app/models/canonical.py` |

Bidirectional override characters can make text display differently from its real content (for example hiding a file extension). Rejecting them in titles prevents that kind of spoofing.

**Authorisation through ownership:**

- `assertOwnership` returns the same 404 for "malformed id", "does not exist" and "belongs to someone else" (no id probing).
- Backend vectors carry `workspace_id`. Every tenant query is built from a `RetrievalScope` and filtered by `tenant_filter`. The older code path is wrapped by `_LegacyClientGuard`, which refuses any `tenant_*` collection.
- Citations are checked again in `/api/chat`: any document outside the workspace is dropped before the student sees it.
- Task 5 ran 118/118 live isolation checks with no defect. Task 21 confirmed a second account got 404 on every read, list, create and delete of the first account's workspace.

### 3.13 Secure failure and logging

- User-visible errors are fixed text chosen by code (`SAFE_MESSAGES` in `app/core/errors.py`, `ERROR_MESSAGES` in `app/services/ingest_store.py`). Exception text, stack traces and host names are never shown.
- `VectorStoreUnavailable` hides raw Qdrant errors, which may contain connection details.
- Production start-up errors name variables, never values (`productionEnv.ts`, `validate_production_settings`).
- With `ENVIRONMENT=production` the backend disables OpenAPI docs and serves only the allow-list. Every other route is 404 before any handler or body parsing runs.
- Evidence was sanitised before it was shared (user-profile paths and secrets removed), following an internal written rule.

## 4. Alternatives and design trade-offs

| Decision | Alternative | Trade-off |
|---|---|---|
| ES256 service tokens | Shared API key or HS256 | Backend cannot forge tokens; needs key distribution (JWKS) and synchronised clocks |
| 300 s single-use tokens | Long-lived tokens | Small replay window and no reuse; needs a replay cache (single process today) |
| JWT session + revocation list | Database sessions only | Fast stateless checks plus real logout; needs the revocation store and outage handling |
| bcrypt cost 12 | Argon2id, or a lower cost | Mature, widely available, deliberately slow; Argon2id is more memory-hard, and the cost must be raised over time |
| 404 for foreign resources | 403 | No id enumeration; slightly harder debugging |
| HS256 capability URL | Presigned object-storage URL, or ES256 | Simple and one trust boundary; not single-use |
| Origin allow-list + no redirects | IP-range blocking | Exact and simple; breaks if a legitimate source redirects |

## 5. Limitations and remaining risks

| Item | Status |
|---|---|
| Encryption at rest (MongoDB, Redis, Qdrant, uploaded files on disk) | **Not implemented** in the project code; depends on hosting |
| End-to-end encryption | **Not implemented** |
| TLS inside the applications | **Not implemented**: HTTPS is expected at a reverse proxy. Public production prerequisites (P-1 to P-8) **Not verified** |
| CSP `script-src` / `default-src` | **Not implemented** (the CSP targets framing, plugins, base URI and form targets) |
| Multi-factor authentication, account lockout notifications, password reset | **Not implemented** |
| Account deletion | **Not implemented** (product decision pending) |
| Replay cache and rate limits shared across instances | **Not implemented** (per process) |
| Per-address rate limit spoofable when reached directly | **Open** (documented) |
| Queued revocation lost if the process stops during a MongoDB outage | **Open** (documented) |
| Legacy workbench routes unauthenticated in development mode, used by the demo launcher | **Open** (T4AB-08); blocked in production |
| Lexical answer-support check cannot detect every unsupported statement | **Open** (VAL-04, GEN-02; answer quality rather than access control) |
| Key rotation procedure for the service JWT key | **Not verified** (the verifier supports multiple keys by `kid`; no rotation was exercised in a recorded task) |

## 6. Interview questions

**Q1. What is the difference between authentication and authorisation in your project?**
Authentication proves identity: bcrypt-checked passwords for students, ES256-signed JWTs for Next.js calling the backend. Authorisation decides access: `assertOwnership` for MongoDB data, token audience and scope for backend routes, and `RetrievalScope` so a query sees only its workspace.

**Q2. Why ES256 instead of HS256 for service tokens?**
With ES256 the backend only needs the public key. A compromised backend cannot mint tokens. With HS256 the verifier holds the same secret as the signer. HS256 is still used for capability URLs, where Next.js both signs and verifies.

**Q3. How do you prevent JWT algorithm-confusion attacks?**
The verifier requires `alg` to be exactly `ES256`, passes only that algorithm to PyJWT, refuses headers that carry keys or key URLs (`jwk`, `jku`, `x5u`, `x5c`, `crit`), and only uses keys from the local JWKS selected by a known `kid`.

**Q4. A service token is stolen. What can the attacker do?**
Very little. It expires within 300 seconds, works only for its audience and scope, is bound to one workspace, and can be used only once: the replay cache rejects a second use with 401. In practice the legitimate request has usually already used it.

**Q5. How are passwords stored, and how do you avoid user enumeration?**
bcrypt with cost 12 (salted, slow). Sign-in always performs one bcrypt comparison, against a dummy hash when the email does not exist, so timing is the same either way, and both cases return the same failure. Rate limits run before the database and bcrypt.

**Q6. How does logout work with stateless JWT sessions?**
Each session token has a random `sid`. Logout stores it in `revokedsessions` (TTL until token expiry + 1 h), and every request rejects revoked or `sid`-less tokens. Revocations are also cached in memory and queued during a MongoDB outage, a fix verified in Tasks 8 and 9.

**Q7. What is SSRF, and why was it a real risk here?**
The backend downloads files from URLs it receives, so a malicious URL could target internal services. The fetcher allows only exact allow-listed origins, refuses redirects and proxies, validates the URL with two parsers and checks the PDF signature.

**Q8. Does the project encrypt data at rest?**
No. The project code does not implement encryption at rest or end-to-end encryption. Confidentiality relies on HTTPS at the proxy, `Secure` cookies, access control, capability URLs and keeping secrets and content out of logs. Encryption at rest would come from the hosting platform and is not verified.

**Q9. Why return 404 rather than 403 for another student's workspace?**
403 would confirm the id exists. Returning the same 404 as for a missing or malformed id prevents enumeration. This was verified with a second account in Task 21.

**Q10. What does your CSP protect against, and what does it not?**
It blocks framing (clickjacking), plugins (`object-src 'none'`), `<base>` tag hijacking and forms posting to other origins. It does not set `script-src`, so XSS protection relies on React's escaping and on `MarkdownContent` rendering answers with `react-markdown` without raw HTML (`rehype-raw` and `dangerouslySetInnerHTML` are not used).

**Q11. Why reject bidirectional control characters in titles?**
Characters such as U+202E (right-to-left override) make text display differently from its actual content, which can disguise names in the UI. `validateConversationTitle` rejects them along with other control characters.

**Q12. What are the main remaining security risks?**
In-process rate limits and replay cache (no multi-instance protection), unauthenticated legacy routes in development mode (T4AB-08), a queued revocation lost on a crash during an outage, no encryption at rest in the project code, and unverified public production prerequisites.

## 7. References

- [Authentication and security](../technical/AUTHENTICATION_AND_SECURITY.md): the three trust boundaries, verification performed and limitations
- [JWT and authentication](../learning/JWT_AND_AUTHENTICATION.md): beginner explanation
- [Security architecture diagram](../architecture/security/security-architecture.png)
- [Challenges and solutions](../interview/CHALLENGES_AND_SOLUTIONS.md): the logout race and revocation fixes
- [Deployment](../guides/DEPLOYMENT.md) and [Known limitations §5](../../KNOWN_LIMITATIONS.md#5-security-limitations)
- Internal verification records (not published): service-token interoperability test, workspace isolation (Task 5), security and reliability stabilisation (Task 8), final integration regression (Task 9), production hardening (Task 10), legacy-route finding (T4AB-08)
- Related subjects: [05 Computer Networks](05_Computer_Networks.md), [03 DBMS](03_Database_Management_Systems.md)
