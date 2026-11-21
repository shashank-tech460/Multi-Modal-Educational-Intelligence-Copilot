# Technology: Why and Why Not

Short, honest comparisons for a common interview question: **"Why did you use X instead of Y?"**

## How to answer

1. State the **requirement**.
2. Say why the chosen technology **fits** it.
3. Name a **real alternative**.
4. Give a **fair trade-off**. Don't attack the alternative; many would have worked.

> Team 4C chose the frontend, authentication, database and service-token technologies. Teams 4A/4B chose the backend and AI technologies. For those, explain the **fit** rather than claiming the decision. The alternatives below were **not** formally evaluated by the project.

---

## Frontend and application

| Technology | Alternative | Trade-off | Reason for the choice |
|---|---|---|---|
| Next.js | Vite SPA + Express/NestJS | A separate API server gives a cleaner split for large teams, but means two codebases and duplicated types | One TypeScript codebase for the UI and the secure server layer; Auth.js and AI SDK integration |
| TypeScript | Plain JavaScript (+ JSDoc) | Extra typing effort | Compile-time checks across three teams' API contracts; mock and real clients share one interface |
| Vercel AI SDK | Hand-written `fetch` + `ReadableStream`, or SSE | Ties the UI to the SDK's message format | `useChat` handles streaming state, stop and retry; data parts carry citations |
| Zustand | Redux Toolkit, React Context | Redux has stronger tooling and conventions for large apps | Only a few small global stores were needed; minimal boilerplate |
| TanStack Query | SWR, `useEffect` + `fetch` | Another library to learn | Caching, refetching and loading or error states without hand-written code |
| Playwright | Cypress | — | Real-browser tests with axe-core accessibility checks |
| Vitest | Jest | — | Fast, TypeScript-friendly unit and component tests |

## Authentication and security

| Technology | Alternative | Trade-off | Reason for the choice |
|---|---|---|---|
| Auth.js (credentials) | Clerk, Auth0, Firebase Auth | Hosted providers offer MFA, social login and admin consoles out of the box | Free, Next.js-native, and user data stays in the project's MongoDB |
| JWT sessions | Database sessions | Logout needs a revocation list (built with a `sid`) | No session store needed; works in server components and the proxy |
| ES256 service tokens | HS256 shared secret, static API key, mTLS | Needs key management (a JWKS file) | The backend can verify but **not forge** tokens, and the token carries the workspace |
| 5-minute token lifetime | Long-lived tokens | A new token is signed for every call (cheap) | Limits the damage if a token is stolen; combined with single-use `jti` |

## Data

| Technology | Alternative | Trade-off | Reason for the choice |
|---|---|---|---|
| MongoDB | PostgreSQL | SQL would enforce the ownership chain with foreign keys and transactions; with MongoDB it is enforced in code and with indexes | Nested chat documents (embedded citations) and fields that evolved |
| Mongoose | Native driver, Prisma | Some overhead; Prisma's MongoDB support is limited | Schemas, validation, `select: false` and typed models |
| Local-disk file storage | S3-compatible object storage | Works on one host only | Zero-setup local demo; production would need object storage |

## Backend, retrieval and AI

| Technology | Alternative | Trade-off | Reason it fits |
|---|---|---|---|
| Python backend | Node.js for everything | Two languages to maintain | Strongest ecosystem for PDF, search and LLM tooling |
| FastAPI | Flask, Django REST Framework | Smaller built-in admin and ORM features than Django | Async I/O, Pydantic validation, streaming responses, dependency injection |
| Qdrant | pgvector, FAISS, Pinecone, Chroma | Embedded mode allows only one process (it caused test locks); production needs a server | Payload filtering for workspaces; embedded mode for a zero-setup demo |
| BM25 (rank-bm25) | Elasticsearch/OpenSearch | Rebuilt per query over the workspace (capped at 10,000 chunks); not suited to huge collections | No extra server; strong exact-term matching |
| Hybrid search | Vector-only search | More computation and code | Covers both paraphrases and exact terms |
| RRF | Weighted score sum, cross-encoder re-ranker | Ignores score magnitude; a re-ranker may be more accurate but is slower | Merges rankings whose scores are on different scales, using only ranks |
| Ollama (local) | Hosted LLM APIs | Lower quality and speed; some answer-quality issues trace back to this | No cost, no API keys, data stays on the machine |
| `llama3` | Smaller or larger models (Gemma, Mistral, Qwen) | A bigger model would answer better but needs more hardware | Reasonable quality on a laptop; structured output |
| `all-minilm` | Larger embedding models (bge, e5, Qwen3-Embedding-8B) | Weaker multilingual quality; short input budget → small chunks | 384 dimensions, about 46 MB, fast on a CPU |
| NDJSON stream (backend) | Server-Sent Events | No built-in reconnect (not needed server-to-server) | One JSON object per line; simple to produce and parse |
| HTTP streaming | WebSockets | No server push outside a request | Answer streaming is one-way; simpler and proxy-friendly |
| Synchronous ingestion | Job queue (Celery, RQ, BullMQ) | Long requests; a lease-based recovery mechanism was needed | No worker infrastructure; the upload request knows the final result |

---

## Model answers

**"Why MongoDB and not SQL?"**
> "Our chat data is nested: a message has a list of citations. Fields also evolved during the project, like the generation state for stopped answers. MongoDB with Mongoose schemas fitted that well. To be fair, the ownership chain is relational, and PostgreSQL with foreign keys would also have been a good choice. We enforced integrity with server-side ownership checks and unique indexes."

**"Why a local LLM instead of a hosted model?"**
> "Student material is private, and we wanted no API cost or keys, so we used Ollama with llama3 locally. The trade-off is quality and speed, and some of our open answer-quality issues are partly due to that. Generation goes through one client module in the backend, so switching to a hosted model later would be a contained change."

**"Why ES256 between your services?"**
> "The backend needs to verify that a request is genuine and which workspace it is for, but it shouldn't be able to create such requests itself. With ES256, only our Next.js server has the private key; the backend has just the public key. A shared HS256 secret would let anyone holding it forge tokens."
