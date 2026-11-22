# EduCopilot — Core Computer Engineering Subjects

| Item | Value |
|---|---|
| Date | 2026-11-22 |
| Build | Final integrated build (local demo) |
| Audience | Final-year Computer Engineering students, reviewers and interviewers who want to see how core subjects appear in a real project |
| Scope | The **integrated product**: the Team 4C Next.js application (`team4c/`), the joint Team 4A/4B FastAPI backend (`app/`) and the Team 4C integration layer inside it. Older backend code that is not part of the integrated product is labelled as such |
| Status labels | **Verified** = executed and passed in a recorded verification task (named in the text). **Implemented** = in the code and covered by unit tests, without a separate live check. **Not verified** = not tested. **Open** = known defect or limitation. **Not implemented** = not in the code |

This folder explains how core Computer Engineering subjects appear in EduCopilot's actual code. Every claim points to a real file, class or function. When the project does not use a concept, the documents say so.

These documents do not replace the system documentation. For the architecture, start with [System architecture](../architecture/SYSTEM_ARCHITECTURE.md) and the [RAG pipeline](../technical/RAG_PIPELINE.md). The full documentation list is in the [repository README](../../README.md#documentation).

---

## 1. Documents

| # | Document | Relevance to the project | Main topics |
|---|---|---|---|
| 1 | [01_Data_Structures_and_Algorithms.md](01_Data_Structures_and_Algorithms.md) | Strong | BM25, vector search, Reciprocal Rank Fusion, hybrid retrieval, chunking, hashing, LRU, FIFO, keyset pagination, replay cache |
| 2 | [02_Object_Oriented_Programming.md](02_Object_Oriented_Programming.md) | Strong | Encapsulation, frozen dataclasses, Proxy, Factory/Strategy, dependency injection, exception hierarchies, state machines |
| 3 | [03_Database_Management_Systems.md](03_Database_Management_Systems.md) | Strong | MongoDB modelling, indexes, idempotency, compare-and-set, leases and fencing, Redis transactions, generations, Qdrant filters |
| 4 | [04_Operating_Systems.md](04_Operating_Systems.md) | Strong | Locks, RLock, event loop, thread pools, semaphores, timeouts, cancellation, leases, fsync, subprocesses |
| 5 | [05_Computer_Networks.md](05_Computer_Networks.md) | Strong | Client–server, REST, status codes, NDJSON streaming, service JWTs, cookies, SSRF, retries, rate limits, network quality |
| 6 | [06_Software_Engineering.md](06_Software_Engineering.md) | Strong | Team integration, contracts, phased tasks, testing pyramid, mocks, production validation, defect tracking |
| 7 | [07_Computer_Organization_and_Architecture.md](07_Computer_Organization_and_Architecture.md) | Limited (short document) | Floating-point embeddings, cosine similarity, CPU inference, INT8 quantisation (older pipeline only) |
| 8 | [08_Information_Security.md](08_Information_Security.md) | Strong | ES256, JWT claims, replay prevention, bcrypt, SHA-256, SSRF, CSP, cookies, revocation, capability URLs |

**Computer Graphics is intentionally not covered.** There is no meaningful connection to the integrated product. The only graphics-like code is a CSS 3D hover effect (`team4c/components/shared/TiltCard.tsx`) and an older MP4 keyframe/OCR pipeline (`app/processors/scene_detector.py`, `app/processors/slide_ocr.py`) that the integrated product does not use (MP4 upload is rejected).

## 2. Structure of every subject document

1. Metadata table
2. Introduction (simple English)
3. Core concepts table
4. Project implementation (files, classes, functions, APIs)
5. Step-by-step walkthroughs
6. Code examples (short, only where they help)
7. Alternatives and design trade-offs
8. Limitations and concepts not implemented
9. Interview questions with answers (8–12)
10. References

## 3. About source references and internal records

- **Source paths.** Paths such as `app/services/hybrid_retriever.py` or `team4c/lib/rateLimit.ts` refer to the project's source code. This portfolio does not contain the full application source code, so these paths are written as text, not links. The short code excerpts in these documents are abridged extracts published with approval.
- **Internal records.** Task numbers (for example "Task 21") and finding ids (for example T4AB-02, VAL-04, TM-1) refer to the team's internal verification reports and registers, which are not published. Each mention also describes the finding in plain words. Public summaries are in [Testing](../technical/TESTING.md) and [Known limitations](../../KNOWN_LIMITATIONS.md).

## 4. Ownership labels

These labels follow [Contributions](../../CONTRIBUTIONS.md). Team 4A or Team 4B is named only where that page does so. Otherwise the documents say "Teams 4A/4B".

| Label | Meaning | Examples |
|---|---|---|
| **Team 4A** | Original ingestion processors (PDF, documents, video, YouTube, OCR), chunking, embeddings | `app/services/chunking.py`, `app/services/video_transcriber.py` |
| **Team 4B** | Hybrid retrieval (BM25 + vectors + RRF), the generation prompt and output format, the Ollama client, conversation memory | `app/services/bm25_index.py`, `hybrid_retriever.py`, `llm_generator.py`, `ollama.py`, `conversation.py` |
| **Teams 4A/4B** | Joint backend code that Contributions does not attribute to one team, for example the vector-store foundation | `app/services/vector_store.py` |
| **Team 4C (application)** | The student-facing Next.js application, authentication, MongoDB data, uploads, chat UI, citations, persistence | `team4c/` |
| **Team 4C (integration layer)** | Code inside the backend that connects the application to the Team 4A/4B modules: service-token verification, workspace-scoped ingestion and query APIs, production hardening | `app/api/canonical_query.py`, `app/api/ingest_v1.py`, `app/core/auth.py`, `app/core/production.py`, `app/services/ingest_store.py`, `app/services/source_fetch.py` |
| **Integration layer (individual ownership not explicitly specified)** | Integration-side backend modules for which [Contributions](../../CONTRIBUTIONS.md) gives no file-level owner | `app/services/local_qdrant.py`, `app/core/errors.py`, `app/models/canonical.py` |

Team 4C also added workspace scoping to the existing retriever, vector store and conversation memory. Where that matters, the documents say "Teams 4A/4B, with Team 4C workspace scoping".

## 5. Integrated product vs older code

| Part of the source | Status in these documents |
|---|---|
| Next.js app (`team4c/`), canonical query (`/api/v1/query/stream`), v1 ingestion (`/v1/ingest`), service-token auth, workspace-scoped retrieval | **Integrated product**: the main subject of every document |
| Older backend workbench routes (`/api/v1/chat`, legacy sessions, OKF, video and YouTube routes in `app/api/ingestion.py`, `youtube.py`, `videos.py`, `okf.py`), the static workbench UI (`app/static/`) | **Outside the integrated product.** Blocked with 404 when `ENVIRONMENT=production` (`app/core/production.py`). Mentioned only where it helps explain a concept |
| MP4 pipeline: `app/services/video_transcriber.py` (faster-whisper), `app/processors/scene_detector.py`, `app/processors/slide_ocr.py` | **Outside the integrated product.** `/v1/ingest` answers `422 unsupported_type` for MP4 |

**Code defaults vs demo configuration.** Values quoted from `app/core/config.py` are **code defaults**. The demo launcher used to run the integrated product overrides one retrieval value: `SCORE_THRESHOLD_DEFAULT=0.25` instead of the code default 0.5. The documents state which value they mean (see [01 DSA §4.3](01_Data_Structures_and_Algorithms.md#43-reciprocal-rank-fusion-rrf) and [RAG pipeline](../technical/RAG_PIPELINE.md)). **Test results** come from different runs: Task 21 recorded Vitest 1,635/1,635, and a later re-run recorded 1,634/1,635 with one timing-sensitive failure (see [06 Software Engineering §6.2](06_Software_Engineering.md#62-final-results-from-the-task-21-report-unless-stated-reported-separately) and [Testing](../technical/TESTING.md)).

## 6. How to use these documents for interviews

- Start with the architecture in [System architecture](../architecture/SYSTEM_ARCHITECTURE.md#a-overall-architecture): Browser → Next.js → FastAPI → Qdrant, the session store (FakeRedis in local mode) and Ollama.
- For each subject, read the **core concepts table**, then the **interview questions**. Each answer covers what the project does, why, the alternative and the trade-off.
- Do not claim more than the documents claim. Every document has a "not implemented" section. Saying what the project does **not** do is part of a good answer.
- For project-level questions, use [Interview preparation](../interview/INTERVIEW_PREPARATION.md) and [Technical questions](../interview/TECHNICAL_QUESTIONS.md).

## 7. Related documentation

| Document | Use |
|---|---|
| [System architecture](../architecture/SYSTEM_ARCHITECTURE.md) | Components, communication and deployment shape |
| [RAG pipeline](../technical/RAG_PIPELINE.md) | Retrieval and generation, with configuration values |
| [Database design](../technical/DATABASE_DESIGN.md) | Collections, relationships and indexes |
| [Authentication and security](../technical/AUTHENTICATION_AND_SECURITY.md) | Trust boundaries and security measures |
| [Testing](../technical/TESTING.md) | Test results by suite |
| [Known limitations](../../KNOWN_LIMITATIONS.md) | What is open or not built |
| [Contributions](../../CONTRIBUTIONS.md) | Who built which part |
