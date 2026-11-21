# Technology Stack: Deep Dive

Every major technology in EduCopilot is explained in the same seven parts: **What is it? · Why is it needed? · How is it used in EduCopilot? · How does it work? · Why was it selected? · Alternatives · Interview question.**

> **Who chose what.** Team 4C chose the frontend, authentication, database and service-token technologies. Some reasons are recorded in Team 4C's design decisions: JWT sessions, the credentials provider, mock-first integration, and Zustand only for shared state. Teams 4A/4B chose the backend and AI technologies. For those, "Why was it selected?" explains **why they fit the project**; it is not a decision record. The alternatives listed are reasonable options, **not** options the project formally evaluated.

Quick reference: [Tech stack](../../TECH_STACK.md) · Trade-off table: [Technology: why and why not](../interview/TECHNOLOGY_WHY_AND_WHY_NOT.md)

## Contents

| Area | Technologies |
|---|---|
| Frontend | [1. Next.js](#1-nextjs) · [2. React](#2-react) · [3. TypeScript](#3-typescript) · [4. Auth.js](#4-authjs) · [7. Vercel AI SDK](#7-vercel-ai-sdk) |
| Data | [5. MongoDB](#5-mongodb) · [6. Mongoose](#6-mongoose) · [10. Qdrant](#10-qdrant) |
| Backend | [8. Python](#8-python) · [9. FastAPI](#9-fastapi) |
| Retrieval and AI | [11. BM25](#11-bm25) · [12. Reciprocal Rank Fusion](#12-reciprocal-rank-fusion) · [13. Ollama](#13-ollama) · [14. Llama 3](#14-llama-3) · [15. all-minilm](#15-all-minilm) · [19. RAG](#19-rag) |
| Security and delivery | [16. JWT](#16-jwt) · [17. ES256](#17-es256) · [18. Streaming](#18-streaming) |
| Other | [Supporting libraries](#supporting-libraries) |

---

## 1. Next.js

### What is it?
A React framework that adds routing, server rendering and **server-side code** (route handlers) to React.

### Why is it needed?
EduCopilot needs a UI **and** a secure server layer. That layer holds secrets (the database URI and the token signing key), checks ownership, and calls the AI backend.

### How is it used in EduCopilot?
- Pages in `app/(auth)` and `app/(dashboard)`.
- Server route handlers in `app/api/*`: workspaces, files, chat, conversations, local storage, health.
- `proxy.ts` as the route guard.

For example, `POST /api/chat` reads the Auth.js session, checks ownership in MongoDB, signs an ES256 token and streams the backend's answer to the browser. The secrets never reach the browser.

### How does it work?
Each folder under `app/` is a route. A `page.tsx` renders UI. A `route.ts` exports `GET`/`POST`/... functions that run **only on the server**. Next.js 16 calls the request interceptor `proxy.ts` (formerly `middleware.ts`).

### Why was it selected?
- One language (TypeScript) for the UI and the server.
- First-class support in Auth.js and the Vercel AI SDK.
- A production build and type checks built in.

### Alternatives
A React SPA (Vite) with a separate Express/NestJS server, Remix, SvelteKit, or Angular. A separate server means two codebases and duplicated types.

### Interview question
**Q: Why does the Next.js server call the AI backend instead of the browser?**

A: To keep the signing key secret and to enforce workspace ownership before any backend call.

---

## 2. React

### What is it?
A JavaScript library for building user interfaces from **components** that hold **state**.

### Why is it needed?
The UI changes constantly: streaming text, upload progress, status badges. React updates only the parts that changed.

### How is it used in EduCopilot?
`ChatPanel`, `ConversationSidebar`, the materials list, `VideoPlayer` and the `SourceAttribution` citation chips. Custom hooks such as `useChatStream` hold chat logic.

### How does it work?
Components are functions that return markup. Hooks (`useState`, `useEffect`, custom hooks) hold state and side effects. React compares the new output with the old and updates the DOM. While an answer streams, only that message bubble re-renders, and the virtualiser renders only the visible messages.

### Why was it selected?
It is required by Next.js, and the libraries the project depends on (`@ai-sdk/react`, shadcn/ui, TanStack) are React-first.

### Alternatives
Vue, Svelte, Angular.

### Interview question
**Q: Where did you use an error boundary?**

A: Around each workspace panel, so one broken panel (for example the video player) does not crash the whole page.

---

## 3. TypeScript

### What is it?
JavaScript with **static types**, checked at build time.

### Why is it needed?
The backend and the UI use different shapes for the same data (`document_id`/`page_number` vs `fileId`/`pageNumber`). Types catch mismatches before runtime.

### How is it used in EduCopilot?
All frontend and server code, plus typed wire contracts for the backend (`types/teamA.ts`, `types/teamB.ts`). The mock and real backend clients implement **the same interface**. Switching `USE_MOCK_TEAM_B=false` needed no UI changes; this was the mock-first integration strategy.

### How does it work?
You declare shapes (`interface`, `type`), and the compiler (`tsc`) checks every use. Types are removed from the output JavaScript.

### Why was it selected?
A large codebase (about 300 files) with contracts between three teams. The final type check was **clean**.

### Alternatives
Plain JavaScript with JSDoc comments, or Flow.

### Interview question
**Q: What does `tsc --noEmit` do?**

A: It type-checks the project without writing output files.

---

## 4. Auth.js

### What is it?
An authentication library for Next.js (formerly NextAuth). It handles sign-in, session cookies, CSRF protection and callbacks.

### Why is it needed?
Writing login, cookies and CSRF protection safely by hand is error-prone.

### How is it used in EduCopilot?
- `lib/auth.ts`: configuration (Credentials provider, JWT strategy).
- `lib/credentialsAuthorize.ts`: rate limits, user lookup, bcrypt check.
- `lib/authCallbacks.ts`: random session id (`sid`) and revocation check.
- `/api/auth/[...nextauth]`: Auth.js endpoints.

### How does it work?
The Credentials provider calls `authorize()`. On success, Auth.js creates a **JWT session** signed with `AUTH_SECRET` and stores it in an HttpOnly cookie. On each request, the `jwt` callback runs, and EduCopilot uses it to reject **revoked** session ids. After logout, a stale cookie copy is therefore useless.

### Why was it selected?
It is built for Next.js and needs no external OAuth app. The team recorded the **JWT strategy** decision: no session table, and it works in server components and the proxy.

### Alternatives
Hosted providers (Clerk, Auth0, Firebase Auth), Lucia, Passport.js, or hand-written JWT auth.

### Interview question
**Q: How do you log out a stateless JWT session?**

A: Each session carries a random `sid`. On logout we store that `sid` as revoked until the token expires, and the JWT callback rejects revoked ids.

---

## 5. MongoDB

### What is it?
A **document** database that stores JSON-like documents in collections.

### Why is it needed?
Chat data is naturally nested (a message with its citations), and its fields evolved during development (for example `generationState`).

### How is it used in EduCopilot?
Six collections: users, workspaces, conversations, messages (with embedded citations), files, revoked sessions. Unique partial indexes block duplicates, and a TTL index removes expired revocations. See [Database design](DATABASE_DESIGN.md).

### How does it work?
Documents are stored as BSON. Indexes speed up queries, unique and partial indexes enforce rules, and TTL indexes delete documents automatically.

### Why was it selected?
A flexible schema, natural nesting, and a good fit with Mongoose and Node.js. A fair trade-off: the ownership chain is relational, so SQL foreign keys would also have enforced it. With MongoDB, integrity is enforced in application code and with unique indexes.

### Alternatives
PostgreSQL or MySQL, Firebase Firestore.

### Interview question
**Q: How do you prevent duplicate uploads during a race?**

A: A unique partial index on `(workspaceId, contentSha256)`. The database rejects the second insert, and the app reuses the existing file.

---

## 6. Mongoose

### What is it?
An ODM (Object Document Mapper) for MongoDB in Node.js.

### Why is it needed?
MongoDB accepts any document. Mongoose adds schemas, `required`/`enum` validation, defaults, timestamps, indexes declared in code, and TypeScript types.

### How is it used in EduCopilot?
Six models in `models/*.ts`, used by every route handler. For example, `passwordHash` has `select: false`, so a normal `User.find()` never returns it.

### How does it work?
A schema describes each collection. Mongoose validates documents before saving and maps query results to typed objects.

### Why was it selected?
Schema safety on top of a schemaless database, with types inferred from the schema.

### Alternatives
The native MongoDB driver, Prisma (MongoDB support is limited), Typegoose.

### Interview question
**Q: How are indexes created in production?**

A: With a dedicated `db:indexes` script, which also has a `--check` mode to verify them. We do not rely on automatic index builds.

---

## 7. Vercel AI SDK

### What is it?
A TypeScript library for building AI chat interfaces and streaming responses.

### Why is it needed?
A streaming chat needs message state, partial updates, status, stop, retry and custom data such as citations. That is a lot of fiddly code to write by hand.

### How is it used in EduCopilot?
- **Browser:** `useChat` (`@ai-sdk/react`), wrapped by `useChatStream`.
- **Server:** `createUIMessageStream` and `createUIMessageStreamResponse` in `/api/chat`.

The route forwards backend text as text parts and sends citations as a custom `data-citations` part. The SDK is used **only for the UI and the streaming protocol**; the model is called by the Python backend.

### How does it work?
The server writes a **UI message stream** (text parts and typed data parts). `useChat` reads it and updates its `messages` array live. `stop()` aborts the request.

### Why was it selected?
First-class Next.js and React support, and custom data parts fit citations well.

### Alternatives
Hand-written `fetch` with `ReadableStream` parsing, Server-Sent Events, WebSockets.

### Interview question
**Q: Why send citations as a data part instead of inside the text?**

A: They are structured data (file id, page or timestamp, URL). A separate typed part lets the UI render chips without parsing text.

---

## 8. Python

### What is it?
A programming language with the strongest ecosystem for AI, search and document processing.

### Why is it needed?
The backend needs PDF extraction, BM25, a vector database client, YouTube captions and LLM calls.

### How is it used in EduCopilot?
The whole backend: ingestion, retrieval, generation and the integration APIs.

### How does it work?
The backend runs as a single Python process under Uvicorn and uses `async` I/O for calls to Ollama and Qdrant.

### Why was it selected?
pypdf, rank-bm25, qdrant-client, youtube-transcript-api and Pydantic are all Python-first.

### Alternatives
Node.js for everything, Java/Spring, Go.

### Interview question
**Q: Why use two languages in one project?**

A: Each side uses the best ecosystem for its job. A typed HTTP contract and signed tokens connect them.

---

## 9. FastAPI

### What is it?
A modern, **async** Python web framework with automatic validation through Pydantic.

### Why is it needed?
The backend must validate every input strictly, wait on slow services without blocking, and stream answers.

### How is it used in EduCopilot?
All backend routes, including `/v1/ingest` and `/api/v1/query/stream` (a `StreamingResponse` that emits NDJSON). Every integration route declares `Depends(_principal)`, so it cannot run without a verified service token.

### How does it work?
You declare a function with typed parameters. FastAPI parses and validates the request, calls the function and serialises the result. `Depends(...)` injects shared logic such as authentication.

### Why was it selected?
Async I/O, strict validation, streaming support and good performance.

### Alternatives
Flask, Django REST Framework, Express (Node.js).

### Interview question
**Q: Why parse the request body only after authentication?**

A: So an unauthenticated caller learns nothing from validation error messages.

---

## 10. Qdrant

### What is it?
A **vector database**. It stores vectors with a JSON **payload** and finds the nearest vectors quickly.

### Why is it needed?
To find the chunks closest in meaning to a question across thousands of chunks, while **filtering by workspace**.

### How is it used in EduCopilot?
Every chunk is a point: id + 384-dimensional vector + payload (`workspace_id`, `document_id`, text, page or timestamps, generation). Every search filters on `workspace_id`. The demo runs Qdrant in **embedded local mode** (a folder on disk, inside the backend process).

### How does it work?
A search sends the query vector and a filter. Qdrant returns the top matches by **cosine similarity**. See [Vector databases](../learning/VECTOR_DATABASES.md).

### Why was it selected?
Payload filtering (essential for multi-tenancy), an embedded mode for a zero-setup demo, and a good Python client. One limit: embedded mode allows one process per folder. This caused the "Qdrant lock" issue when tests ran next to a live backend.

### Alternatives
pgvector (PostgreSQL), Chroma, FAISS, Pinecone, Weaviate, Milvus.

### Interview question
**Q: How is multi-tenancy enforced in the vector database?**

A: Each point's payload includes the workspace id. Every search filters on the id from the verified token, and the retriever checks the scope again before returning results.

---

## 11. BM25

### What is it?
A classic **keyword ranking** formula (Okapi BM25), the one used by search engines such as Elasticsearch.

### Why is it needed?
Vector search can miss exact terms (for example "RAID 5" or a formula name). BM25 is strong at exact words.

### How is it used in EduCopilot?
The hybrid retriever builds a `rank-bm25` index **per query** over the workspace's in-scope chunks (capped at 10,000).

### How does it work?
A chunk scores higher when it contains the query words more often (with diminishing returns), when those words are rare across chunks (IDF), and when the chunk is not overly long. See [BM25, hybrid search and RRF](../learning/BM25_AND_HYBRID_SEARCH.md).

### Why was it selected?
No extra server, no training, and it complements vector search.

### Alternatives
TF-IDF, Elasticsearch/OpenSearch, learned sparse retrieval (SPLADE).

### Interview question
**Q: What is a limitation of BM25 in this project?**

A: It does not understand synonyms. Its simple `\w+` tokeniser also splits some Indic-script words incorrectly, which is tracked as a known defect.

---

## 12. Reciprocal Rank Fusion

### What is it?
A simple method that **merges several ranked lists** into one.

### Why is it needed?
BM25 scores and cosine scores are on **different scales**, so they cannot simply be added.

### How is it used in EduCopilot?
`reciprocal_rank_fusion(rankings, k=60)` merges the vector and BM25 rankings. The result is normalised to 0–1, a threshold is applied, and the top 5 are kept.

### How does it work?
Each chunk gets `Σ 1 / (60 + rank)` over the lists. A chunk ranked high in **both** lists wins. A worked example is in [BM25, hybrid search and RRF](../learning/BM25_AND_HYBRID_SEARCH.md#5-merging-rankings-reciprocal-rank-fusion).

### Why was it selected?
It uses only ranks, is robust, and needs no tuning beyond `k`.

### Alternatives
A weighted score sum (needs score normalisation and weight tuning), or a cross-encoder re-ranker (more accurate but adds a model and latency). The backend has an optional re-ranking layer, LAYA, **disabled** in the demo.

### Interview question
**Q: Why k = 60?**

A: It is the common default from the original RRF paper. It makes rank 1 and rank 2 differ only a little, so agreement between the lists matters more than one list's top spot.

---

## 13. Ollama

### What is it?
A tool that runs open-source LLMs and embedding models **locally** behind a simple HTTP API.

### Why is it needed?
No cloud API keys or costs, and student material never leaves the machine.

### How is it used in EduCopilot?
The backend calls Ollama's chat endpoint for answers (with a JSON `format` schema) and its embed endpoint for vectors. Generation uses `temperature: 0`, `num_ctx: 8192` and `num_predict: 512`.

### How does it work?
`ollama pull llama3` downloads a model. The Ollama server loads it into memory (on a GPU if available) and answers HTTP requests.

### Why was it selected?
It is free, local and private, and supports structured output. The trade-off is that local models are slower and less capable than large hosted models.

### Alternatives
Hosted LLM APIs (for example OpenAI, Google Gemini), vLLM, llama.cpp, Hugging Face TGI.

### Interview question
**Q: What is the main downside of local models here?**

A: Lower answer quality and speed. Some open answer-quality issues trace back to it.

---

## 14. Llama 3

### What is it?
Meta's open-weights large language model. The demo uses `llama3:latest` through Ollama.

### Why is it needed?
To write a natural-language answer from the retrieved evidence.

### How is it used in EduCopilot?
It receives a system prompt, evidence items labelled `C1..Cn`, recent history and the question. It must return `{"answer": ..., "citations": [...]}`.

### How does it work?
It generates text token by token. Ollama constrains the output to the JSON schema, so citations can only be labels that were actually provided.

### Why was it selected?
Good quality for its size, free, runs locally, and supports structured output through Ollama.

### Alternatives
Mistral, Gemma (the backend's example config still names `gemma3:1b`), Qwen, hosted models.

### Interview question
**Q: Why temperature 0?**

A: For the most consistent, factual output. Creativity is not wanted when answering from evidence.

---

## 15. all-minilm

### What is it?
A small **sentence-embedding** model that turns text into a **384-number vector**.

### Why is it needed?
Vector search needs embeddings for every chunk and every question, from the **same** model.

### How is it used in EduCopilot?
It embeds chunks at ingestion and questions at query time. The demo launcher measured its output size and set `VECTOR_SIZE=384`.

### How does it work?
A trained neural network maps text with similar meaning to nearby vectors.

### Why was it selected?
It is tiny (about 46 MB), fast on a CPU, and good enough for semantic search over study notes. Its limits are a short input budget (hence small chunks) and weaker multilingual quality.

### Alternatives
Larger embedding models (the backend supports a remote Qwen3-Embedding-8B option with 4,096 dimensions), bge or e5 models, hosted embedding APIs.

### Interview question
**Q: Why must ingestion and query use the same embedding model?**

A: Different models produce incompatible vector spaces. The backend also refuses to search when the collection's vector size does not match the configuration.

---

## 16. JWT

### What is it?
A JSON Web Token: a compact, **signed** set of claims (`header.payload.signature`).

### Why is it needed?
The receiver can verify identity and permissions **without a database lookup**.

### How is it used in EduCopilot?
- **Student sessions:** Auth.js JWT cookie.
- **Service tokens:** Next.js → FastAPI, ES256, 5 minutes, one workspace.
- **File capability tokens:** HS256, 10 minutes, one file.

### How does it work?
The signer creates a signature over the header and payload. The verifier checks the signature and the claims (`exp`, `aud`, `iss`, ...). The payload is readable by anyone, so it never holds secrets. See [JWT and authentication](../learning/JWT_AND_AUTHENTICATION.md).

### Why was it selected?
Stateless verification. EduCopilot handles the usual pitfalls: revocation (`sid` list), replay (`jti` cache), algorithm confusion (ES256 only) and long lifetimes (5-minute service tokens).

### Alternatives
Opaque session ids with a server-side store, static API keys, mutual TLS.

### Interview question
**Q: Is a JWT encrypted?**

A: No. It is signed, not encrypted. Anyone can read the payload, but nobody can change it without breaking the signature.

---

## 17. ES256

### What is it?
ECDSA signatures on the **P-256** curve with SHA-256. The signer uses a **private key**; verifiers use the **public key**.

### Why is it needed?
The backend must verify that a request is genuine and which workspace it is for, **without being able to create** such requests itself.

### How is it used in EduCopilot?
Service tokens are signed with `jose` in Next.js and verified with PyJWT + cryptography in FastAPI, against a JWKS file of public keys. A `kid` header supports key rotation.

### How does it work?
Signing uses the private key; verification checks the signature with the matching public key. Knowing the public key does not allow signing.

### Why was it selected?
The backend can verify but **cannot forge** tokens, and the keys are small. See [Authentication and security §4](AUTHENTICATION_AND_SECURITY.md#4-service-to-service-security-nextjs--fastapi).

### Alternatives
HS256 (shared secret), RS256 (RSA), mutual TLS, static API keys.

### Interview question
**Q: Why not HS256 between the services?**

A: Anyone holding a shared HS256 secret, including the backend, could forge tokens. With ES256 only the Next.js server can sign.

---

## 18. Streaming

### What is it?
Sending a response **in pieces as it is produced**.

### Why is it needed?
An answer can take many seconds. Streaming shows progress immediately and makes **Stop** possible.

### How is it used in EduCopilot?
Ollama → backend (model output); backend → Next.js (**NDJSON**); Next.js → browser (**AI SDK UI message stream**). The backend **verifies the full answer first**, then streams it, so a student never sees text that is later withdrawn.

### How does it work?
The server writes to an open HTTP response, and the client reads it piece by piece. See [LLM streaming](../learning/LLM_STREAMING.md) and [Chat and streaming](CHAT_AND_STREAMING.md).

### Why was it selected?
Streamed HTTP is enough for one-way answer delivery and works through normal proxies.

### Alternatives
Server-Sent Events, WebSockets, no streaming (wait for the full answer).

### Interview question
**Q: Why verify before streaming, if it delays the first word?**

A: An earlier version streamed raw text, and students sometimes saw answers that verification then withdrew. Verifying first means students only see answers the system stands behind.

---

## 19. RAG

### What is it?
Retrieval-Augmented Generation: retrieve relevant passages, then generate an answer grounded in them.

### Why is it needed?
The model does not know the student's notes and can hallucinate. RAG with citations ties answers to retrieved evidence and makes them checkable.

### How is it used in EduCopilot?
The whole question-answering path: hybrid retrieval in one workspace → prompt with labelled evidence → llama3 → verification → streamed answer with citations.

### How does it work?
See [RAG fundamentals](../learning/RAG_FUNDAMENTALS.md) for the concept and [RAG pipeline](RAG_PIPELINE.md) for the implementation.

### Why was it selected?
Students' material is private and changes constantly. RAG updates as soon as a document is indexed, and it can cite sources.

### Alternatives
Fine-tuning a model on the notes (expensive, slow to update, no citations), or long-context prompting with whole documents (does not scale with an 8K context).

### Interview question
**Q: How does EduCopilot stop the model inventing citations?**

A: The output schema allows only real evidence labels, citation metadata comes from storage, and any answer with an unverifiable citation is replaced by the "not enough context" answer.

---

## Supporting libraries

| Library | Role in EduCopilot |
|---|---|
| bcrypt | Password hashing, cost 12 |
| jose | JWT signing (ES256 service tokens, HS256 capability tokens) |
| TanStack Query | Server-data caching and refetching in the UI |
| TanStack Virtual | Renders only the visible chat messages |
| Zustand | Small global stores (active workspace, offline queue, network quality, toasts) |
| Tailwind CSS 4 + shadcn/ui (Radix UI) | Styling and accessible primitives |
| video.js + videojs-youtube | Player with programmatic seeking for timestamp citations |
| react-markdown + remark-gfm | Rendering formatted answers safely |
| Pydantic 2 | Backend request, response and settings validation |
| pypdf | PDF text extraction per page |
| youtube-transcript-api, yt-dlp | Timed captions; video title |
| FakeRedis / Redis | Conversation memory with a TTL |
| Vitest, React Testing Library, Playwright, axe-core | Frontend and browser testing |
| pytest, Hypothesis | Backend and property-based testing |
