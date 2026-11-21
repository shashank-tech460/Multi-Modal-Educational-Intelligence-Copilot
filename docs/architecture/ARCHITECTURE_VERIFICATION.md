# Architecture Verification

This report records how the architecture in this portfolio was checked against the available source material, and how a discrepancy with an earlier version of the project was resolved.

**Checked on:** 21 November 2026
**Sources inspected (read-only):**
- The final integrated project snapshot (the commit used for the final regression): application code, dependency files, integration contracts and project reports.
- The local copy of the joint Team 4A/4B backend repository.
- The previous public portfolio repository for this project (milestone **M6**, last updated 28 September 2026): its architecture and integration documents and its file tree.

---

## 1. The discrepancy

| Topic | Previous repository (M6) | This portfolio (final integrated build) |
|---|---|---|
| Backend services | **Three** independently runnable services: Team 4A ingestion (port 8001), Team 4B query (port 8002), Team 4C Next.js (port 3000) | **Two** application services: Next.js (port 3000) and **one** FastAPI backend (port 8001 in the demo) |
| MongoDB access | Shared by all three: Team 4C owns the schema, Team 4A **writes** `File.currentIngestionGeneration`, Team 4B **reads** it | **Only the Next.js app** accesses MongoDB |
| Ingestion call | `POST /v1/ingest` returns **202 Accepted**; a Celery worker processes the job | `POST /v1/ingest` returns **200 only after** chunks are indexed and the generation is activated (synchronous) |
| Generation authority | A Redis lock and counter in Team 4A, plus the MongoDB field | The backend's own ingest registry (JSON files on disk) records the active generation per document |
| Supporting stores | Two Redis instances (Team 4A: queue and locks; Team 4B: conversation history) | FakeRedis in-process in local/demo storage mode (a Redis server only in external mode) for conversation memory only |

## 2. Evidence and findings

| Question | Finding | Evidence |
|---|---|---|
| Does the two-service architecture describe the final integrated build? | **Yes.** | The final snapshot contains one FastAPI application (`app/main.py`) that registers both the ingestion routes (`/v1/ingest`, `/v1/ingest/jobs/{id}`, `/v1/documents/{id}`) and the query routes (`/api/v1/query`, `/api/v1/query/stream`, sessions). The joint Team 4A/4B repository's final commit is a single application ("4a and 4b Final Integrated Project") |
| Were Team 4A and 4B merged, or are they still separately runnable? | **Merged into one application** in the final build. The frontend still keeps two **logical** clients | The Next.js server has separate `TEAM_A_API_URL` and `TEAM_B_API_URL` settings and separate token audiences (`team4a-ingestion`, `team4b-query`). The demo launcher sets both URLs to the same backend |
| Is the M6 three-service design a different version? | **Yes**: an earlier milestone with a different Team 4A/4B implementation | The M6 repository contains a separate Team 4A service (Celery tasks, `mongo_authority.py`, `canonical_ingest.py`) and a separate Team 4B service. None of these files exist in the final integrated snapshot |
| Does the final backend access MongoDB? | **No.** | No MongoDB driver (`pymongo`, `motor`) in the backend's code or `requirements.txt` |
| Who writes and reads `File.currentIngestionGeneration` in the final build? | **Nothing reads it.** The only writer is a Team 4C one-off migration script that backfills `0` on old records | Repository-wide search of the final snapshot: the field appears only in the File model, that script and their tests. The model's comment still describes the M6 Team 4A writer |
| Do the request contracts match? | **Partly.** The query body is the same three fields `{query, session_id, retrieval_config}` in both versions, with the same audiences and scopes. Ingestion differs (202 + job vs synchronous 200), and the final build adds an NDJSON streaming endpoint | M6 integration document; final backend route modules and the Team 4C client |

## 3. Resolution

- The portfolio's **two-service description is correct for the final integrated implementation** and is kept.
- The M6 three-service design is now **explicitly labelled as an earlier version** wherever the architecture is described:
  - [System architecture](SYSTEM_ARCHITECTURE.md#original-team-responsibilities-vs-final-integrated-structure)
  - [Contributions](../../CONTRIBUTIONS.md#1-how-the-work-was-divided)
- The `currentIngestionGeneration` description was made precise in [Database design](../technical/DATABASE_DESIGN.md#35-files) and added to [Known limitations](../../KNOWN_LIMITATIONS.md#4-open-technical-items).

## 4. Remaining inconsistencies (not resolved by this portfolio)

| Item | Status |
|---|---|
| One project handover note (open finding "T4AB-10") says `currentIngestionGeneration` "is written by Team 4A's authority client". That client exists only in the M6 version, not in the final backend | Recorded here as an inconsistency in the project's own documents. Clean-up of the field was deliberately left to agreement with Team 4A |
| The File model's code comment still describes the M6 writer | Same as above (source code is not part of this portfolio and was not changed) |
| Who wrote the Team 4A/4B code shown in the M6 repository | **Not verified.** The M6 repository's documents describe team responsibilities, but per-file authorship was not checked |

## 5. Team boundaries (unchanged)

| Layer | Original responsibility | In the final integrated build |
|---|---|---|
| Ingestion (extraction, chunking, embeddings) | Team 4A | Inside the joint FastAPI backend; reused by Team 4C's integration endpoints |
| Retrieval, ranking, generation, conversation memory | Team 4B | Inside the joint FastAPI backend; workspace scoping added by Team 4C |
| Student application, MongoDB data, authentication | Team 4C | Next.js application |
| Integration layer (workspace-scoped APIs, service-token verification, production allowlist) | Team 4C | Added to the joint FastAPI backend |
