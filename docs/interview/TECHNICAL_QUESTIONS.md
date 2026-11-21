# Technical Interview Questions and Answers

**82 questions**, each answered **in terms of EduCopilot**. Levels: **[Basic]**, **[Intermediate]**, **[Advanced]**.
Exam-style questions are in [Viva preparation](VIVA_PREPARATION.md).

---

## Contents

1. [Project and architecture](#1-project-and-architecture) (Q1–Q10)
2. [Next.js, React and TypeScript](#2-nextjs-react-and-typescript) (Q11–Q22)
3. [APIs](#3-apis) (Q23–Q29)
4. [Authentication, JWT and security](#4-authentication-jwt-and-security) (Q30–Q43)
5. [MongoDB and data](#5-mongodb-and-data) (Q44–Q51)
6. [RAG, retrieval and LLM](#6-rag-retrieval-and-llm) (Q52–Q67)
7. [Streaming](#7-streaming) (Q68–Q72)
8. [Testing](#8-testing) (Q73–Q77)
9. [Deployment and system design](#9-deployment-and-system-design) (Q78–Q82)

---

## 1. Project and architecture

**Q1 [Basic] What does EduCopilot do?**

It lets students upload PDFs and YouTube lectures into private workspaces and ask an AI tutor questions. Answers are generated from passages retrieved from that material. Grounded answers include citations to the exact PDF page or video timestamp, and the tutor declines when the evidence is insufficient.

**Q2 [Basic] What was your role?**

I was a Team 4C member. Team 4C built the Next.js student application and integrated it with the Python RAG backend built by Teams 4A and 4B. I worked on auth, workspaces, uploads, streaming chat, citations, the integration APIs, service-token security, hardening and testing.

**Q3 [Basic] What are the main components?**

A Next.js app (UI + server route handlers), a FastAPI backend (ingestion + RAG), MongoDB (app data), Qdrant (vectors), and Ollama (llama3 for answers, all-minilm for embeddings).

**Q4 [Intermediate] Why does the browser not call the AI backend directly?**

The Next.js server must first check the session and workspace ownership, then sign a token that names only that workspace. If the browser called the backend directly, the signing key would have to be exposed, or the backend would have to trust client-supplied workspace ids.

**Q5 [Intermediate] What is a Backend-for-Frontend (BFF)?**

A server layer built for one UI. Our Next.js route handlers are the BFF: they shape data for the UI, hold secrets, enforce ownership and adapt the backend's stream into the format `useChat` expects.

**Q6 [Intermediate] Is this a microservices architecture?**

It is two services with a clear HTTP contract and signed tokens between them, not a large microservice mesh. The backend itself is one process that does both ingestion and RAG. That was simpler to run as a local demo.

**Q7 [Intermediate] How do the two services share data?**

They share **identifiers, not databases**. MongoDB is read only by Next.js. The backend has Qdrant, a job registry and conversation memory. `File._id` is the backend `document_id`; `Workspace._id` is the token `workspace_id`.

**Q8 [Intermediate] Why two languages, TypeScript and Python?**

TypeScript is best for the web app (Next.js, React, Auth.js, the AI SDK). Python has the AI and PDF ecosystem (pypdf, rank-bm25, the Qdrant client). A typed HTTP contract connects them.

**Q9 [Advanced] What happens end to end when a student asks a question?**

Session + rate-limit + ownership checks → the question is saved (`generating`) → source scope → an ES256 token is signed → backend: token verified → follow-up expansion → BM25 + vector search → RRF → top 5 + neighbours → llama3 JSON answer → verification → saved in backend memory → NDJSON stream → Next.js maps and filters citations, saves the answer and auto-titles → UI message stream → chips.

*Say it short:* "Check, save, sign a token, retrieve hybrid, generate, verify, stream, then save and show citations."

**Q10 [Advanced] What is the weakest part of the architecture, and how would you fix it?**

State held in one process: local-disk uploads, in-memory rate limits and replay cache, embedded Qdrant. Fix: object storage, Redis for shared state, a Qdrant server, then several app instances behind a load balancer.

*Say it short:* "Single-process state; I'd move it to object storage, Redis and a Qdrant server before scaling."

## 2. Next.js, React and TypeScript

**Q11 [Basic] What is the Next.js App Router?**

Folder-based routing under `app/`. `page.tsx` renders a page and `route.ts` defines server API handlers. We use route groups like `(auth)` and `(dashboard)` to organise layouts.

**Q12 [Basic] What is a route handler?**

A server-only function (`GET`, `POST`, ...) in `route.ts`. Example: `POST /api/chat` checks auth, calls the backend and streams the answer.

**Q13 [Intermediate] What is `proxy.ts`?**

Next.js 16's name for middleware. It runs before matched requests. Ours redirects signed-out users from `/dashboard` and `/workspace/*` to `/login` with a safe callback URL, and redirects signed-in users away from `/login` and `/signup`.

**Q14 [Intermediate] Server vs client components?**

Server components render on the server and can read data securely. Client components (`"use client"`) run in the browser and use state and effects. The chat panel, uploads and video player are client components because they are interactive.

**Q15 [Basic] What is a React hook? Give a custom one you used.**

A function that adds state or effects to components. `useChatStream` wraps `useChat` with history seeding, citations, a watchdog, offline replay, retry and Stop.

**Q16 [Intermediate] Why TanStack Query?**

It caches server data (workspaces, files, history), handles loading and error states, and refetches when needed. That removes a lot of hand-written fetching code.

**Q17 [Intermediate] Why Zustand, and why not Redux?**

We only needed a few global stores (active workspace, offline queue, network quality, toasts). Zustand has almost no boilerplate. The team decided to use React state by default and Zustand only for shared state.

**Q18 [Intermediate] What is list virtualisation and why use it?**

Rendering only the visible items of a long list. TanStack Virtual keeps long conversations fast because hundreds of message bubbles are not all in the DOM.

**Q19 [Intermediate] How does a citation seek the video?**

The chip calls the player (video.js with the YouTube tech) to select that video and seek to `timestampSeconds`. It waits for the video metadata to load first, so the seek is not lost.

**Q20 [Intermediate] How did TypeScript help integration?**

Wire types for the backend (`types/teamA.ts`, `types/teamB.ts`) and one interface implemented by both the mock and real clients. Switching from mock to real needed no UI changes, and mismatches were caught at compile time.

**Q21 [Basic] What does `tsc --noEmit` do?**

It type-checks the project without writing output files. It was clean in the final run.

**Q22 [Intermediate] How did you make the UI accessible?**

Accessible names on repeated buttons ("Delete OS-Unit3.pdf"), regions with labels, a keyboard-scrollable chat area, keyboard navigation in the sidebar, and automated axe-core checks in Playwright.

## 3. APIs

**Q23 [Basic] REST status codes you used?**

200/201 success, 400 validation, 401 not signed in, 404 not found or not yours, 409 duplicate or conflict, 422 refused input, 429 rate limit, 502/503 upstream problems.

**Q24 [Intermediate] Why return 404 instead of 403 for another user's workspace?**

A 403 would confirm that the id exists. A 404 reveals nothing, which prevents enumeration of other users' resources.

**Q25 [Intermediate] How is conversation paging implemented?**

Cursor-based: the cursor encodes `(updatedAt, _id)` of the last item, and the next page asks for strictly older items. Unlike `skip`/offset paging, it stays correct when new conversations are added.

**Q26 [Intermediate] What is idempotency, and where did you use it?**

Repeating a request has the same effect as doing it once. Uploads carry an idempotency key (unique sparse index), and questions carry a `clientMessageId` (unique per conversation), so retries do not create duplicates.

**Q27 [Intermediate] What does the ingestion API return, and when?**

`POST /v1/ingest` returns `200 {job_id, document_id, generation, state: "ready", chunks_indexed}` **only after** the chunks are indexed and the generation is activated. Any failure is an error envelope, and the previous generation stays active.

**Q28 [Advanced] Why is ingestion synchronous, and what are the risks?**

It is simpler (no queue or worker), and the upload request knows the final result. The risks are long requests and crashes mid-way. We handled crashes with a processing **lease** (30 s heartbeat, 6-minute expiry) and automatic recovery. A production system would move to a job queue.

*Say it short:* "Simple and the request knows the result; we added a lease so crashes don't leave files stuck."

**Q29 [Intermediate] How do backend errors avoid leaking internals?**

A safe error envelope `{error: {code, message}}` with fixed messages. The frontend maps backend errors to fixed student-friendly text, and details only go to server logs.

## 4. Authentication, JWT and security

**Q30 [Basic] Authentication vs authorization?**

Authentication = who you are (login). Authorization = what you may do (ownership checks on every request).

**Q31 [Basic] How are passwords stored?**

bcrypt hashes with cost factor 12, in a field excluded from queries by default (`select: false`).

**Q32 [Intermediate] What does Auth.js do for you?**

Sign-in flow, CSRF protection, a signed HttpOnly session cookie (JWT strategy) and callbacks. Our `authorize()` adds rate limits, timing-safe lookup and bcrypt.

**Q33 [Intermediate] JWT session vs database session: why JWT?**

JWT needs no session store and works in server components and the proxy. The trade-off is logout, which we solved with a revocation list keyed by a random session id.

**Q34 [Intermediate] How do you prevent user enumeration at login?**

The same "Invalid email or password" message for both cases, and a dummy bcrypt comparison when the email doesn't exist, so the timing is similar. Rate limits are checked before the lookup.

**Q35 [Intermediate] What rate limits exist?**

Sign-in: 10 per email and 30 per IP per 15 minutes, plus 300 per minute overall. Sign-up: 5 per email, 10 per IP and 100 overall per hour. Chat: 20 questions per minute per user. All are configurable.

**Q36 [Intermediate] What is a JWT made of?**

Header (algorithm, key id), payload (claims such as `sub`, `exp`, `aud`) and signature, each Base64URL-encoded. The payload is readable by anyone, so it holds no secrets.

**Q37 [Advanced] Describe the service token between Next.js and the backend.**

ES256-signed, 5-minute lifetime. Claims: `sub`, `workspace_id`, `aud` (`team4a-ingestion` or `team4b-query`), `scope` (`ingest` or `query`), `iss`, `iat`, `exp`, `jti`. The backend verifies the algorithm (ES256 only), `kid`, signature, exact issuer and audience, matching scope, lifetime ≤ 300 s, and single use of `jti`. Missing key configuration → 503.

*Say it short:* "A five-minute ES256 token naming one workspace, one audience and one scope, usable once."

**Q38 [Advanced] Why ES256 rather than HS256?**

With HS256 the backend would hold the shared secret and could forge tokens. With ES256 the backend holds only the public key, so it can verify but not sign. A leaked public key is harmless.

*Say it short:* "With ES256 the backend can check tokens but can't create them."

**Q39 [Advanced] What attacks does the verifier block?**

`alg: none` and algorithm switching (pinned to ES256), attacker-supplied keys (`jwk`/`jku`/`x5u`/`x5c` headers rejected), cross-service use (exact audience and scope), long-lived theft (5-minute maximum) and replay (`jti` cache).

*Say it short:* "Algorithm swaps, injected keys, cross-service reuse, long-lived theft and replay."

**Q40 [Intermediate] Where else do you use JWTs?**

A file capability token: HS256, 10 minutes, bound to one workspace and file, so the backend can download an uploaded PDF without a browser cookie. A symmetric key is fine here because the same server signs and verifies it.

**Q41 [Advanced] Explain the logout race condition you fixed.**

A session-refresh response already in flight during logout re-set the old JWT cookie, which was still valid because JWTs are stateless. Fix: a random `sid` per session, revoked on logout (MongoDB TTL record + memory), checked in the JWT callback. Tokens without a `sid` are rejected.

*Say it short:* "An in-flight response re-set the old cookie; we added a revocable session id."

**Q42 [Intermediate] Why are frontend checks not enough for security?**

Users can modify anything in the browser and call APIs directly. Only server-side checks against the real session and database enforce access. The same principle applies between our services: the backend trusts only the signed token.

**Q43 [Intermediate] What security headers do you send?**

CSP `frame-ancestors 'none'`, `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, a strict Referrer-Policy and Permissions-Policy, HSTS only when the app URL is HTTPS, and no `X-Powered-By`.

## 5. MongoDB and data

**Q44 [Basic] Which collections exist?**

users, workspaces, conversations, messages, files, revokedsessions.

**Q45 [Intermediate] Embed or reference? Give examples.**

Citations are **embedded** in messages (they are always read together). Messages **reference** conversations, conversations reference workspaces, and workspaces reference users (lists that can grow, plus the ownership chain).

**Q46 [Intermediate] What is a TTL index? Where is it used?**

An index that makes MongoDB delete documents automatically after a time. `revokedsessions.expiresAt` deletes revocation records once the session would have expired anyway.

**Q47 [Advanced] Sparse vs partial unique index?**

Sparse ignores documents **missing** the field (used for `ragSessionId` and `uploadIdempotencyKey`). Partial ignores documents that don't match a filter (`contentSha256` and `youtubeVideoId` only when they are strings). Both enforce uniqueness only where a value exists.

*Say it short:* "Sparse skips missing fields; partial skips documents that don't match a filter."

**Q48 [Advanced] How do you prevent duplicate uploads under concurrency?**

A unique partial index on `{workspaceId, contentSha256}`. If two uploads race, the database rejects one and the app reuses the existing file. YouTube uses `{workspaceId, youtubeVideoId}`.

*Say it short:* "A unique partial index on workspace plus content hash lets the database reject the second insert."

**Q49 [Intermediate] How are indexes managed in production?**

A script (`db:indexes`) creates the 12 required indexes, and `--check` verifies them without changes. It reports missing or incompatible indexes.

**Q50 [Intermediate] What happens when a workspace is deleted?**

For each file: the backend document is deleted first, then the bytes and the record. Then messages, conversations and the workspace are deleted. Backend sessions expire by TTL.

**Q51 [Advanced] Would you choose PostgreSQL instead?**

It would work well: the ownership chain is relational, and foreign keys plus transactions would enforce integrity. MongoDB was chosen for flexible, nested chat documents and its fit with the JavaScript stack. We enforced integrity with ownership checks and unique indexes.

*Say it short:* "Postgres would be a fine choice; we picked MongoDB for nested chat data and enforced integrity in code."

## 6. RAG, retrieval and LLM

**Q52 [Basic] What is RAG?**

Retrieve relevant passages from the user's documents, then generate an answer grounded in them, with citations.

**Q53 [Basic] Why RAG instead of fine-tuning?**

Each student's material is private and changes constantly. RAG updates instantly when a document is indexed and gives citations; fine-tuning is slow, costly and cannot cite sources.

**Q54 [Intermediate] How are PDFs processed?**

pypdf extracts text page by page. Each page is chunked separately (chunks never cross pages), every chunk stores `page_number`, and pages without a text layer are skipped (no OCR).

**Q55 [Intermediate] How are YouTube videos processed?**

Timed captions are fetched (English preferred, otherwise the video's own track). Chunks are built from whole caption segments with `start_seconds`/`end_seconds`, so citations seek to the exact moment.

**Q56 [Intermediate] How does chunking work?**

It is structure-aware: it splits by headings, lists, tables and paragraphs, merges blocks under the same heading while they fit, and splits oversized blocks at sentence, then line, then word boundaries. Limits: 1,200 characters and a roughly 496-byte embedding budget (512 tokens counted as bytes). There is no overlap; neighbour chunks are added at retrieval time.

**Q57 [Intermediate] What is an embedding? Which model?**

A vector representing meaning. We use all-minilm through Ollama, which gives 384 dimensions, for both chunks and questions.

**Q58 [Intermediate] Why must ingestion and query use the same embedding model?**

Different models produce incompatible vector spaces. The backend also refuses to search if the collection's dimension doesn't match the configuration.

**Q59 [Intermediate] How does Qdrant keep workspaces separate?**

Each point's payload has `workspace_id`; every search filters on the id from the verified token (and `document_id` if sources are selected). The retriever checks the scope again before returning results.

**Q60 [Intermediate] Explain BM25.**

A keyword score that rewards query words appearing in the chunk (with diminishing returns), weights rare words higher (IDF), and normalises for chunk length. We use `rank-bm25` over the workspace's chunks.

**Q61 [Intermediate] Why hybrid retrieval?**

Vectors handle paraphrases; BM25 handles exact terms. Together they beat either one alone.

**Q62 [Advanced] Explain RRF with numbers.**

Score = Σ 1/(60 + rank). A chunk ranked 1st by vectors and 2nd by BM25 gets 1/61 + 1/62 = 0.0325. Divided by the maximum (2/61), that is 0.99. A chunk found only by BM25 at rank 3 gets 1/63 = 0.0159 → 0.48.

*Say it short:* "Add 1/(60+rank) from each list, then normalise; agreement between both lists wins."

**Q63 [Intermediate] What are the retrieval parameters?**

Hybrid mode; 50 candidates per method; score threshold 0.5 by default (0.25 in the demo); top 5; neighbour window ±3 chunks from the same document.

**Q64 [Advanced] How are follow-up questions handled?**

A detector recognises follow-ups (pronouns, "what about", at most 3 topic words; English and Hindi) and adds the conversation's topic words to the **search** query. The model still sees the original question and recent history.

*Say it short:* "We detect follow-ups and add the conversation's topic to the search query."

**Q65 [Intermediate] How is the prompt built?**

System rules (answer only from evidence; treat evidence as data, not instructions; cite labels; JSON output) + evidence items `C1..Cn` (metadata + text, whole chunks within a byte budget) + a summary and recent turns + the question. The output schema allows only the provided labels.

**Q66 [Advanced] How do you verify the answer?**

The JSON must parse, and all citations (including inline ones) must be real labels. Declines and echoed questions lose their citations. Under 25% content-word support in the cited chunks means the answer is withheld. Every citation needs valid source metadata. Any failure → "The available documents do not provide enough context to answer this question."

*Say it short:* "Real labels, no declines with citations, at least 25% support, valid metadata, or 'not enough context'."

**Q67 [Advanced] How do you defend against prompt injection inside a PDF?**

The prompt tells the model that evidence is untrusted data, never instructions, and never to reveal system instructions. Independently, the backend verifies support and citations, so an injected instruction cannot produce an unsupported, cited answer.

*Say it short:* "Evidence is treated as data, and the answer is verified independently of the model."

## 7. Streaming

**Q68 [Basic] Why stream answers?**

Local generation can take seconds. Streaming shows progress and allows Stop.

**Q69 [Intermediate] What formats are used?**

Backend → Next.js: NDJSON (`delta`, optional `draft`, then exactly one `done` or `error`). Next.js → browser: the Vercel AI SDK UI message stream (text + a `data-citations` part).

**Q70 [Advanced] Why verify before streaming?**

Streaming raw text meant students sometimes saw answers that verification then withdrew. Now the backend verifies the full answer, then streams it. An optional draft preview shows unverified text separately and is never saved.

*Say it short:* "So students never see an answer that is later withdrawn."

**Q71 [Intermediate] How does Stop work end to end?**

`useChat().stop()` aborts the fetch. The route's abort signal cancels the backend call, and the question is saved as `stopped` with any partial text.

**Q72 [Intermediate] Why not WebSockets?**

Answer streaming is one-way; a streamed HTTP response is simpler, stateless and proxy-friendly.

## 8. Testing

**Q73 [Basic] What test levels did you use?**

Unit, component (React Testing Library), backend integration (FastAPI test client with in-memory stores), property-based (Hypothesis), browser end-to-end (Playwright) and accessibility (axe-core).

**Q74 [Intermediate] What were the final results?**

Backend 798 passed, 5 skipped, 8 expected failures, 0 failed. Frontend 1,634 of 1,635 (one timing-sensitive test that passes alone). TypeScript clean. ESLint 12 known issues. Production build succeeded. Browser tests weren't re-run for the portfolio; the last recorded results were 30/30 desktop and 29/30 mobile.

**Q75 [Intermediate] What are xfail tests, and why keep them?**

Tests expected to fail because of a known defect (Indic text extraction and tokenisation). They document the bug, and if someone fixes it they show up as XPASS.

**Q76 [Advanced] How did you test security?**

Negative tests (wrong algorithm, wrong audience, expired or replayed tokens, missing keys → 503, cross-workspace access), 118 live isolation checks, and fault injection (MongoDB made unreachable during login and logout).

*Say it short:* "Negative token tests, 118 live isolation checks and database fault injection."

**Q77 [Intermediate] How did mocks help?**

Mock backends with the same interface let the UI be built and tested before the real backend existed. In tests, mocks isolate the unit under test.

## 9. Deployment and system design

**Q78 [Basic] Is it deployed?**

No. It ran as a local demo on one machine. It was hardened for a controlled single host but not deployed publicly.

**Q79 [Intermediate] What would production need?**

A TLS reverse proxy, a secret manager, managed MongoDB with backups and a tested restore, object storage, Redis for shared state, a Qdrant server, a process supervisor running the backend in production mode, monitoring, and a key-rotation procedure.

**Q80 [Advanced] How would you scale to 10,000 students?**

Stateless Next.js instances behind a load balancer; Redis for rate limits, revocations and replay cache; object storage; a Qdrant cluster; a job queue for ingestion; GPU-backed model serving (or a hosted model); caching of frequent queries; per-tenant quotas.

*Say it short:* "Stateless app instances, shared Redis, object storage, a Qdrant cluster and a job queue."

**Q81 [Advanced] Why not deploy on Vercel?**

Uploads are on local disk, the backend is a long-running process with embedded Qdrant, and answers can stream for minutes. Serverless time limits and temporary disks don't fit. The plan is a single host behind a TLS proxy.

*Say it short:* "Local disk, a long-running backend and long streams don't fit serverless limits."

**Q82 [Advanced] If retrieval quality is poor, how would you investigate?**

Trace one query end to end: the retrieval query (after follow-up expansion), the BM25 and vector rankings, the RRF scores against the threshold, the chunks sent to the model, the raw model JSON, and which verification rule withheld the answer. The project did exactly this kind of trace for the intermittent "not enough context" issue and handed the evidence to the RAG owners.

*Say it short:* "Trace one query through each stage and find where the good chunk drops out."
