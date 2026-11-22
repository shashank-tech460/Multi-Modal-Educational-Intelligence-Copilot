# Interview Preparation

Your study guide for explaining EduCopilot in interviews. Start with [Project explanation](PROJECT_EXPLANATION.md) (spoken intros). Then use this page for **your role, integration, concept cards, and honest answers about issues**. Practise with [Technical questions](TECHNICAL_QUESTIONS.md) and [Viva preparation](VIVA_PREPARATION.md). For subject-wise questions (DSA, OOP, DBMS, operating systems, networks, software engineering, security), see [Core subjects](../core-subjects/README.md).

---

## Contents

- [H. My Team 4C contribution](#h-my-team-4c-contribution)
- [I. How Team 4C integrated with the platform](#i-how-team-4c-integrated-with-the-platform)
- [J. Technology choices in one breath](#j-technology-choices-in-one-breath)
- [Concept cards (K–U)](#concept-cards)
- [V. Known issues: how to talk about them](#v-known-issues-how-to-talk-about-them)
- [W. Future improvements](#w-future-improvements)
- [Behavioural questions](#behavioural-questions)

---

## H. My Team 4C contribution

**Say it like this:**
> "I was a member of Team 4C, the application and integration team. I worked on the Next.js application: authentication, workspaces, material uploads, the streaming chat with citations, and conversation history. I also worked on the integration layer inside the Python backend: the workspace-scoped ingestion and query APIs and the service-token verification. Plus security hardening and a lot of testing and verification. The original retrieval, generation and ingestion logic came from Teams 4A and 4B."

**Three things to highlight (pick by audience):**

| Audience | Highlight |
|---|---|
| Frontend role | Streaming chat with the Vercel AI SDK, citation chips that seek video, virtualised history, offline queue, accessibility fixes |
| Backend / security role | ES256 service tokens, workspace isolation (118/118 checks), logout-revocation race fix, production allowlist |
| AI / ML role | Answer verification before streaming (decline detection, support check), hybrid retrieval scoping, follow-up query expansion |

Full list: [CONTRIBUTIONS.md](../../CONTRIBUTIONS.md).

## I. How Team 4C integrated with the platform

1. **Mock-first:** Team 4C built against mock clients that had the same TypeScript interface as the real ones, so the UI was finished before the backend was ready. One environment flag switched to the real backend.
2. **Contract:** the integration API (`/v1/ingest`, `/api/v1/query/stream`) was shaped by Team 4C's client contract and built as a layer **on top of** Team 4A/4B's modules (their chunker, caption fetcher, retriever and generator).
3. **Security boundary:** ES256 tokens carry the workspace; the backend verifies them and filters every query by that workspace.
4. **Shared identifiers, separate stores:** `File._id` = `document_id`; `Workspace._id` = `workspace_id`; `Conversation.ragSessionId` = backend session.
5. **Handover:** open issues in the backend teams' area were written up with evidence and owners. Team 4C did not change other teams' decisions.

## J. Technology choices in one breath

> "Next.js and TypeScript for one codebase that holds the UI and the secure server layer; Auth.js for safe login; MongoDB with Mongoose for flexible chat documents; the Vercel AI SDK for streaming chat; FastAPI in Python because the AI and PDF ecosystem is there; Qdrant for vector search with workspace filters; BM25 for exact terms; RRF to merge rankings with different score scales; and Ollama with llama3 and all-minilm so everything runs locally, for free and privately."

Comparisons: [Technology: why and why not](TECHNOLOGY_WHY_AND_WHY_NOT.md).

---

## Concept cards

Each card: **definition → why needed → how EduCopilot uses it → example → likely follow-up → short answer.**

### K. Database (MongoDB + Mongoose)

| | |
|---|---|
| **Definition** | MongoDB stores JSON-like documents; Mongoose adds schemas, validation and indexes |
| **Why needed** | Persistent users, workspaces, conversations, messages with citations, and file records |
| **How we use it** | Six collections; the ownership chain User → Workspace → Conversation → Message / File; 12 required indexes, including unique partial indexes for duplicates and a TTL index for revoked sessions |
| **Example** | A message document embeds `citations: [{fileId, type: "pdf", pageNumber: 12}]` |
| **Follow-up** | *"How do you stop two identical uploads from both being saved?"* |
| **Short answer** | "A unique partial index on workspace + content hash. The database rejects the second insert, and we reuse the existing file." |

### L. Authentication

| | |
|---|---|
| **Definition** | Proving who the user is, then authorising each action |
| **Why needed** | Private study material; one student must never see another's |
| **How we use it** | Auth.js credentials + bcrypt (cost 12) + JWT cookie with a revocable `sid`; rate limits; ownership checks that return 404; ES256 service tokens to the backend |
| **Example** | Changing the workspace id in the URL gives 404, because the server checks `Workspace.userId` |
| **Follow-up** | *"JWTs are stateless. How do you log someone out?"* |
| **Short answer** | "Each session has a random id in the token. On logout we store it as revoked until the token expires, and our JWT callback rejects revoked ids." |

### M. RAG

| | |
|---|---|
| **Definition** | Retrieve relevant passages, then generate an answer from them |
| **Why needed** | The model doesn't know the student's notes and can hallucinate |
| **How we use it** | Hybrid retrieval in one workspace → top 5 + neighbours → llama3 with JSON output → verification → stream with citations |
| **Example** | "Why do processes wait forever?" → the deadlock page → answer with `[1]` → page 12 |
| **Follow-up** | *"How do you stop the model making things up?"* |
| **Short answer** | "The prompt restricts it to the evidence, and the backend verifies: citations must be real labels, the answer must be supported by the cited text, and declines can't carry citations. Otherwise we return 'not enough context'." |

### N. Hybrid search

| | |
|---|---|
| **Definition** | Combining keyword search and vector search |
| **Why needed** | Each misses what the other finds |
| **How we use it** | BM25 and Qdrant run in parallel; RRF merges them |
| **Example** | "RAID 5" (keyword strength) vs "processes stuck waiting" (meaning strength) |
| **Follow-up** | *"Why not just use vectors?"* |
| **Short answer** | "Small embedding models are weak on exact terms, codes and names. BM25 covers that cheaply." |

### O. BM25

| | |
|---|---|
| **Definition** | A keyword ranking formula: term frequency with saturation × rarity (IDF), normalised for length |
| **Why needed** | Strong exact-word matching |
| **How we use it** | `rank-bm25` index built over the workspace's chunks per query; `\w+` tokens; only chunks sharing a word are kept |
| **Example** | "Banker's algorithm" ranks chunks containing those words first |
| **Follow-up** | *"Limitation?"* |
| **Short answer** | "It doesn't understand synonyms, and our simple tokeniser splits some Indic words incorrectly. That is a known defect, tracked as an expected test failure." |

### P. Vector search

| | |
|---|---|
| **Definition** | Finding texts whose embeddings are closest in meaning |
| **Why needed** | Paraphrased questions |
| **How we use it** | all-minilm → 384-dim vectors → Qdrant with cosine distance and a `workspace_id` payload filter |
| **Example** | "Stuck forever" matches "deadlock" |
| **Follow-up** | *"How is multi-tenancy enforced?"* |
| **Short answer** | "Every point has a workspace id in its payload; every search filters on the id from the verified token; and the retriever checks the scope again before returning." |

### Q. RRF

| | |
|---|---|
| **Definition** | Merging ranked lists by summing 1/(k + rank) |
| **Why needed** | BM25 and cosine scores aren't comparable |
| **How we use it** | k = 60, normalised to 0–1; threshold 0.25 in the demo; top 5 |
| **Example** | Ranked 1st by vectors and 2nd by BM25 → 1/61 + 1/62 → normalised 0.99 |
| **Follow-up** | *"Why k = 60?"* |
| **Short answer** | "It's the standard default. It makes agreement between both lists matter more than one list's top position." |

### R. LLM

| | |
|---|---|
| **Definition** | A model that generates text token by token |
| **Why needed** | To write a natural answer from the retrieved passages |
| **How we use it** | llama3 via Ollama; temperature 0; max 512 tokens; 8K context; JSON schema output `{answer, citations}` |
| **Example** | `{"answer":"... [C1]", "citations":["C1"]}` → renumbered to `[1]` |
| **Follow-up** | *"Why a local model?"* |
| **Short answer** | "No cost, no API keys, and student data stays on the machine. The trade-off is lower quality and speed." |

### S. Streaming

| | |
|---|---|
| **Definition** | Sending the response in pieces as it is produced |
| **Why needed** | Answers take seconds; streaming feels responsive and allows Stop |
| **How we use it** | Backend NDJSON (verified `delta` events, then `done`) → Next.js adapter → Vercel AI SDK UI message stream → `useChat` |
| **Example** | Citations travel as a `data-citations` part |
| **Follow-up** | *"Why not WebSockets?"* |
| **Short answer** | "The stream is one-way, so a streamed HTTP response is simpler and works through normal proxies." |

### T. Security

| | |
|---|---|
| **Definition** | Protecting data and access |
| **Why needed** | Private data; two services; untrusted input (including PDFs) |
| **How we use it** | Ownership checks, ES256 scoped tokens, replay protection, rate limits, capability URLs, security headers, a production allowlist, safe errors, prompt-injection-aware prompt + verification |
| **Example** | A token for ingestion can't be used for queries (exact audience and scope check) |
| **Follow-up** | *"Why not just check in the frontend?"* |
| **Short answer** | "Anything in the browser can be changed. Only the server, with the real session and database, can enforce access." |

### U. Testing

| | |
|---|---|
| **Definition** | Automated checks at several levels |
| **Why needed** | Many moving parts and three teams |
| **How we use it** | Vitest + React Testing Library (1,635 tests), pytest (798 passed), Playwright browser workflows, axe accessibility checks, live fault-injection runs |
| **Example** | A test proves that a replayed service token is rejected |
| **Follow-up** | *"Did everything pass?"* |
| **Short answer** | "Backend 798 passed with zero failures. Frontend 1,634 of 1,635; the one failure passes alone and looks timing-sensitive. ESLint has 12 known issues in test files. I report the suites separately rather than claim 100%." |

---

## V. Known issues: how to talk about them

> "The system works end to end as a local demo, but I'd be clear about three things. First, it's not production-deployed: it would need HTTPS, managed MongoDB with backups, a secret manager and object storage. Second, it's a single-host design: rate limits and some state are in memory. Third, answer quality has open issues, like identical answers to different follow-ups and occasional false 'not enough context' replies. We documented those with evidence for the RAG owners."

Details: [KNOWN_LIMITATIONS.md](../../KNOWN_LIMITATIONS.md).

## W. Future improvements

1. Production deployment (TLS proxy, managed database, secrets, object storage, monitoring).
2. Shared Redis state for horizontal scaling.
3. A cross-encoder re-ranker and threshold tuning for retrieval quality.
4. OCR for scanned PDFs; transcription for videos without captions.
5. Better follow-up handling (query rewriting with the LLM).
6. Workspace rename, conversation search, account deletion, teacher features.

---

## Behavioural questions

| Question | Story to use |
|---|---|
| *A hard bug you solved* | Logout race condition ([Challenges §1](CHALLENGES_AND_SOLUTIONS.md#1-logout-did-not-really-log-you-out-race-condition)) |
| *Working with other teams* | Mock-first integration; writing a handover with evidence instead of changing their code |
| *A time you found your own mistake* | The revocation fix that still failed after a restart (Challenges §2, round 2): found in the final regression and fixed |
| *Handling ambiguity* | Unclear API contract → typed client interfaces + mocks; later the implemented contract was documented |
| *Quality vs deadline* | Reporting test results separately and honestly; not claiming production readiness |
| *User-focused decision* | Verify before streaming, so students never see withdrawn answers |
