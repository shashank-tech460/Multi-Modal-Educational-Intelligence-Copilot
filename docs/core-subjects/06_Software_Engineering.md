# 06 — Software Engineering

| Item | Value |
|---|---|
| Date | 2026-11-22 |
| Subject | Software Engineering: process, integration, contracts, testing, quality and release |
| Relevance | Strong: three teams, one integrated product, 22 recorded tasks with reports and evidence |
| Main sources | The project's internal task reports and handovers (not published), `team4c/docs/decisions.md`, `team4c/docs/api-contracts.md` (superseded), `team4c/tests/`, `tests/`, `team4c/lib/productionEnv.ts`, `app/core/production.py`, `team4c/services/teamA|teamB/` |
| Build | Final integrated build (local demo) |
| Owners | All teams; per-item ownership as described in [Contributions](../../CONTRIBUTIONS.md#1-how-the-work-was-divided) |
| Status labels | Verified, Implemented, Not verified, Open, Not implemented (see [README](README.md)) |

---

## 1. Introduction

Software engineering is about building software that works, can be changed safely, and can be handed to other people. For EduCopilot, the hard part was not one feature. It was **integrating work from three teams** into one product that behaves correctly end to end, and proving it with evidence.

The project's records show a clear process: a written architecture plan, an API contract, phased tasks with acceptance reports, a layered test suite, regression runs, a defect register with owners, documented known limitations and a deployment handover. This document explains that process using the project's own records. All test numbers come from existing records; none were re-run for this document. Most come from the Task 21 report. The later Vitest re-run (§6.2) is described in [Testing](../technical/TESTING.md#1-final-results-re-run-on-the-final-integrated-snapshot-21-nov-2026).

## 2. Core concepts

| Concept | Where | Status |
|---|---|---|
| Team-based integration | Team 4A (ingestion), Team 4B (RAG), Team 4C (application and integration layer) | Verified (Tasks 6, 21) |
| Contract-first development | `team4c/docs/api-contracts.md` (original proposal, now marked superseded) → implemented contracts in [API documentation §7](../technical/API_DOCUMENTATION.md#7-integration-api-fastapi-server-to-server); `team4c/tests/unit/contract-freeze.test.ts` | Implemented |
| Integration boundaries | Next.js ↔ FastAPI via service JWT; mocks behind interfaces | Verified (Task 6, service-token interoperability test) |
| Phased task execution | Tasks 1–22, each with a report or recorded outcome | Verified (records in `docs/`) |
| Ownership and responsibility | Ownership table, handover to Teams 4A/4B, defect owners | Implemented (documented) |
| Testing pyramid | Vitest unit/component, pytest (with Hypothesis), Playwright E2E | Verified (Task 21 results) |
| Regression testing | Tasks 9 and 21; repository E2E specs | Verified |
| Mocks and real-service switching | `getTeamAService()` / `getTeamBService()`, `USE_MOCK_TEAM_A/B` | Implemented |
| Production configuration validation | `team4c/lib/productionEnv.ts`, `app/core/production.py` | Verified (Task 10) |
| Defect tracking | Task 11 audit register (PCA-xx), Teams 4A/4B answer-quality register (ING/RET/GEN/VAL…), T4AB-01..10 | Implemented (documented) |
| Known limitations and evidence | [Known limitations](../../KNOWN_LIMITATIONS.md); internal evidence records (not published) | Implemented (documented) |
| Release and deployment | Deployment handover, hardening guide; local demo ready, public production **Not verified** | Open (P-1 to P-8) |

## 3. Team-based integration

### 3.1 Teams and boundaries

| Team | Owns | Code |
|---|---|---|
| Team 4A | The original ingestion processors (PDF, documents, video, YouTube, OCR), chunking and embeddings | `app/` (joint backend) |
| Team 4B | Hybrid retrieval (BM25 + vectors + RRF), the generation prompt and output format, the Ollama client, conversation memory | `app/services/hybrid_retriever.py`, `bm25_index.py`, `llm_generator.py`, `ollama.py`, `conversation.py` |
| Team 4C integration layer | Backend code that connects the application to the Team 4A/4B modules: service-token verification, workspace-scoped ingestion and query APIs, production hardening, and workspace scoping added to the shared retriever, vector store and conversation memory | `app/api/canonical_query.py`, `app/api/ingest_v1.py`, `app/core/auth.py`, `app/core/production.py`, `app/services/ingest_store.py`, `app/services/source_fetch.py` |
| Integration layer (individual ownership not explicitly specified) | Integration-side backend modules for which [Contributions](../../CONTRIBUTIONS.md) gives no file-level owner | `app/services/local_qdrant.py`, `app/core/errors.py`, `app/models/canonical.py` |
| Team 4C application | Everything the student sees, authentication, MongoDB data, uploads, chat UI, citations, persistence | `team4c/` |

The integration rule that keeps the boundary clean: **the browser never calls the backend**. The Next.js server calls it with a short-lived, audience-scoped service token. Each side can change internally as long as the contract holds.

### 3.2 Ownership in practice

When a defect is found, the reports record **who owns the fix**, with evidence. Example: an identical follow-up answer was reproduced by calling the backend directly, with no Team 4C code involved, so it was assigned to Teams 4A/4B (T4AB-01). The ownership method is described in the internal handover to Teams 4A/4B (not published).

## 4. Contract-first development

1. **Plan:** `team4c/docs/decisions.md` recorded the architecture and phased plan before most code existed (the *why*, not a live status).
2. **Propose:** `team4c/docs/api-contracts.md` proposed the cross-team API. It is now marked **superseded**.
3. **Implement and freeze:** the contracts actually in use are documented in [API documentation §7](../technical/API_DOCUMENTATION.md#7-integration-api-fastapi-server-to-server): `POST /v1/ingest`, job status, `DELETE /v1/documents/{id}`, `POST /api/v1/query/stream` (NDJSON `delta` / `draft` / `done` / `error`), and session seed/delete/history. Backend models in `app/models/canonical.py` reject unknown fields (`extra="forbid"`). `team4c/tests/unit/contract-freeze.test.ts` guards the frontend's side.
4. **Shared limits are written down:** the 2,000-character question limit exists on both sides (backend `MAX_QUERY_CHARS` / `MAX_QUERY_LENGTH`, frontend `MAX_QUESTION_CHARS`, both counting code points). The duplication is itself tracked as a shared risk (T4AB-09).

**Benefit:** teams can work in parallel against mocks. **Cost:** the contract and the code can drift. That is why the original proposal is explicitly marked superseded instead of silently left outdated.

## 5. Phased task execution

Work was split into numbered tasks, each with a goal, an acceptance step and a report. A shortened view (the project timeline is also summarised in the [Changelog](../../CHANGELOG.md#project-timeline-context)):

| Phase | Tasks | Examples |
|---|---|---|
| Verification | 4–6 | YouTube timestamp citations; workspace isolation (118/118 live checks); backend integration (contracts 24/24, smoke 14/14) |
| Stabilisation | 7–9 | Browser E2E (8 defects fixed); security and reliability (7 defects fixed); final regression (1 new security defect fixed and verified) |
| Hardening and audit | 10–11 | Production hardening for a controlled single host; complete audit with a defect register that drove Tasks 12–20 |
| Improvements | 12–20 | Stop generation, YouTube dedupe, rename, drafts, pagination, session expiry, processing recovery, question persistence, P3 fixes |
| Release verification | 21–22 | Final integrated regression; final documentation and handover |

Several tasks were "accepted after blocker rounds" (for example Task 18). The report records the review findings and fixes, not just the final success.

## 6. Testing strategy

### 6.1 The testing pyramid in this project

```
                 ▲   Browser E2E (Playwright)          few, slow, realistic
                ▲▲▲  Integration / contract / smoke    backend contracts, service-token interop, smoke
              ▲▲▲▲▲▲ Unit + component + property       many, fast (Vitest, pytest, Hypothesis)
```

| Layer | Tool | Location | What it checks |
|---|---|---|---|
| Unit | Vitest | `team4c/tests/unit/` | Libraries and route handlers in isolation (e.g. `auth-rate-limit.test.ts`, `question-persistence.test.ts`, `processing-recovery.test.ts`, `pdfRetrieval.test.ts`) |
| Component | Vitest + React Testing Library | `team4c/tests/component/` | UI behaviour (e.g. `ChatPanel.test.tsx`, `ConversationSidebar-pagination.test.tsx`, `SourceAttribution.test.tsx`) |
| Backend unit/integration | pytest, pytest-asyncio | `tests/` | Retrieval, ingestion, auth, isolation, streaming (e.g. `test_service_auth.py`, `test_workspace_isolation.py`, `test_generation_retrieval.py`, `test_concurrent_vector_writes.py`) |
| Property-based | Hypothesis | `tests/test_phase1_properties.py`, `tests/test_phase2.py` | Random inputs to check general rules hold (for example batch caps and validation) |
| End-to-end | Playwright | `team4c/tests/e2e/` | Real browser journeys: `auth-workspace`, `core-rag`, `history-restoration`, `workspace-isolation`, `source-isolation`, `youtube-rag`, `accessibility`, `smoke` |
| Static checks | TypeScript, ESLint | `team4c/` | Types and lint rules |

**Property-based testing** differs from example-based testing: instead of writing "input X gives Y", you state a rule ("a batch never stores more than the cap") and Hypothesis generates many inputs, including edge cases, trying to break it.

### 6.2 Final results (from the Task 21 report unless stated, reported separately)

| Suite | Result | Exceptions |
|---|---|---|
| Vitest unit/component | **1,635 / 1,635 passed** (119 files) in Task 21 | A later re-run (21 Nov 2026, clean export of the final integrated snapshot) gave **1,634 / 1,635**: one conversation-rename test failed under full-suite load and passed 3/3 when run alone (timing-sensitive). These are two different runs; the later one is not a clean full-suite pass |
| TypeScript | **Clean** | — |
| ESLint | **12 problems (9 errors, 3 warnings), all pre-existing** | In test files and unused-variable warnings (TM-4) |
| Backend pytest, isolated run | **798 passed, 5 skipped, 8 xfail** | xfail = known Indic extraction/tokenisation defects (T4AB-06) |
| Backend pytest next to the running demo | 71 errors | Environment: Qdrant lock (T4AB-04), not a product failure |
| Browser 30-step workflow | **Desktop 30/30, mobile 29/30** | Mobile step 10: backend decline (T4AB-02) |
| Database index check | 12/12 on the isolated test database | Live database **Not verified** |

The project rule: **these suites are not added into one pass rate**, because they measure different things.

### 6.3 Regression testing

- Task 9 and Task 21 re-ran the full suites and the browser workflows after many changes.
- When a project Playwright spec failed, the reports separated a **test defect** (for example an outdated selector after Task 14 added Rename buttons, TM-1) from a **product defect** (for example the backend's identical follow-up answer in `core-rag`, T4AB-01).
- Fixes such as the logout race and session revocation have before/after evidence in the internal records (see [Challenges and solutions](../interview/CHALLENGES_AND_SOLUTIONS.md) for the story).

## 7. Mocks and real-service switching

`getTeamAService()` and `getTeamBService()` return a mock or the real client based on `USE_MOCK_TEAM_A/B` (see [02 OOPS §3.4](02_Object_Oriented_Programming.md#34-factory-and-strategy-patterns)).

- **Development:** Team 4C could build the UI before the backend was ready.
- **Tests:** unit and component tests run without a backend.
- **Safety:** an unset flag defaults to the mock in development; production refuses to start unless both flags are `"false"`.

## 8. Production configuration validation (fail fast)

| Side | Code | Refuses to start when… |
|---|---|---|
| Frontend | `team4c/lib/productionEnv.ts` | Mocks are enabled, `AUTH_SECRET` is missing or shorter than 32 characters, required URLs or the signing key are missing, a URL is plain `http` for a non-loopback host, or an unimplemented `STORAGE_PROVIDER` is set |
| Backend | `validate_production_settings` in `app/core/production.py` | Demo storage or a missing JWKS in production. Production also disables OpenAPI docs and serves only the route allow-list |

Error messages name **variables only, never values**, so secrets do not appear in logs. A wrong production setting fails at start-up instead of at the first real request.

## 9. Defect tracking and known limitations

| Register | Where | Examples |
|---|---|---|
| Integrated audit (Task 11) | Internal audit report (not published) | PCA-xx items that drove Tasks 12–20 |
| Teams 4A/4B answer-quality register (22 items) | Internal register (not published); summary in [Known limitations §3](../../KNOWN_LIMITATIONS.md#3-answer-quality-open-owned-by-the-rag-side-shared-investigation) | ING-01/02, GEN-02/04, VAL-04 |
| Final integration findings | Internal handover to Teams 4A/4B (not published) | T4AB-01 (identical follow-ups) … T4AB-10 |
| Test-code issues | Internal Task 21 report; summary in [Testing §4](../technical/TESTING.md#4-known-test-and-quality-issues) | TM-1 to TM-5 |

Each finding records evidence, expected vs actual behaviour, owner and severity. Limitations are published openly in [Known limitations](../../KNOWN_LIMITATIONS.md).

**Evidence handling:** logs, screenshots and scripts were stored with the internal task reports. User-profile paths and secrets were removed before any evidence was shared, following a written sanitisation rule (internal, not published).

## 10. Release and deployment considerations

| Item | Status |
|---|---|
| Local demo | Usable with launcher conditions D-1 to D-4 |
| Controlled single host | Hardened (Task 10) |
| Public production | **Not ready**: prerequisites P-1 to P-8 **Not verified** |
| Horizontal scaling | **Not implemented**: local-disk uploads, in-memory limiters and sessions, embedded Qdrant |
| Production builds | `npm run build` and `npx next build --webpack` both exit 0 (Task 21) |
| Health checks | Frontend `/api/health` (`?ready=1` for readiness); backend `/healthz` (the only unauthenticated backend route in production) |

See [Deployment](../guides/DEPLOYMENT.md) and [Setup](../guides/SETUP.md).

## 11. Alternatives and design trade-offs

| Decision | Alternative | Trade-off |
|---|---|---|
| Contract-first with mocks | Build the backend first, then the UI | Parallel work; risk of contract drift (handled by marking the old contract superseded and freeze tests) |
| Separate suites, separate numbers | One combined pass rate | Honest reporting; harder to summarise in one figure |
| Evidence folders for every task | Reports only | Claims can be checked; large repository size |
| Fail-fast configuration checks | Defaults that "just work" | Misconfiguration found at start-up; stricter setup |
| Documented ownership for each defect | One shared backlog | Clear responsibility across teams; needs root-cause evidence before assignment |

## 12. Limitations and practices not implemented

| Item | Status |
|---|---|
| Continuous integration pipeline (CI) in the project repository | **Not implemented**: no CI configuration was found; suites were run manually per task |
| Containerised deployment of the integrated app | **Not implemented**: `compose.phase1.yml` only starts Qdrant and Redis for the older backend setup |
| Multi-instance / horizontally scaled deployment | **Not implemented** |
| Public production verification (P-1 to P-8) | **Not verified** |
| Pre-existing ESLint errors and outdated E2E selectors (TM-1 to TM-5) | **Open** |
| Answer quality issues (T4AB-01, T4AB-02) | **Open**, Teams 4A/4B; shared investigation |
| Per-file 4A/4B ownership in git | Not recorded |

## 13. Interview questions

**Q1. How did three teams integrate without breaking each other?**
Through a contract and a single boundary. The browser only talks to Next.js. Next.js talks to the backend with a service token and a documented request/response shape. Each side tested against mocks, then Task 6 verified the real integration (contracts 24/24, smoke 14/14), and Task 21 verified the full product.

**Q2. What does contract-first mean in your project?**
The cross-team API was proposed in writing (`team4c/docs/api-contracts.md`) before integration. The implemented contract is now documented in [API documentation §7](../technical/API_DOCUMENTATION.md#7-integration-api-fastapi-server-to-server), and the old proposal is marked superseded. Backend models reject unknown fields, and a frontend freeze test guards the shape.

**Q3. Describe your testing pyramid.**
Many fast unit and component tests (Vitest: 1,635/1,635 in Task 21; a later re-run gave 1,634/1,635 with one timing-sensitive failure that passed when run alone), backend pytest with property-based tests (798 passed, 5 skipped, 8 known xfail), contract and smoke checks, and a smaller set of Playwright browser journeys (desktop 30/30, mobile 29/30 in Task 21). The suites are reported separately.

**Q4. What is property-based testing, and where is it used?**
Instead of hand-picking examples, you state a rule and a library generates many inputs to try to break it. The backend uses Hypothesis in `tests/test_phase1_properties.py` and `tests/test_phase2.py`.

**Q5. How do you tell a test failure from a product bug?**
By reproducing it at the right boundary. In Task 21, `history-restoration` failed because of an outdated selector, and a copy with only the selector fixed passed: a test defect. `core-rag` failed because the backend returned an identical follow-up answer even when called directly: a product defect in the Teams 4A/4B backend.

**Q6. Why use mocks, and how do you stop them reaching production?**
Mocks let the frontend team build and test without a running backend. `productionEnv.ts` refuses to start in production unless `USE_MOCK_TEAM_A` and `USE_MOCK_TEAM_B` are both `"false"`.

**Q7. What does "fail fast" mean in your deployment?**
Both apps validate configuration at start-up. A missing or short secret, enabled mocks, plain-http URLs or a missing JWKS stop the process with a message that names the variable but never prints its value.

**Q8. How are defects tracked and assigned?**
In registers with evidence, expected vs actual behaviour, severity and owner: PCA items (Task 11), the 22-item Teams 4A/4B register, and T4AB-01..10 for final integration findings. Ownership is assigned only after reproducing at a boundary.

**Q9. Is the project production-ready?**
For a local demo and a controlled single host, yes, with documented conditions. For unrestricted public production, no: prerequisites P-1 to P-8 are not verified, and the design does not support horizontal scaling.

**Q10. What would you improve in the engineering process?**
Add a CI pipeline to run the suites on every change (none is configured), fix the open test-code issues TM-1 to TM-5, make the E2E specs viewport-independent, and move the shared question-length limit into one contract source (T4AB-09).

## 14. References

- [Testing](../technical/TESTING.md): results of both runs, skipped tests and known test issues
- [Contributions](../../CONTRIBUTIONS.md): team boundaries
- [API documentation](../technical/API_DOCUMENTATION.md): implemented contracts
- [Known limitations](../../KNOWN_LIMITATIONS.md) and [Deployment](../guides/DEPLOYMENT.md)
- [Changelog](../../CHANGELOG.md): project timeline
- [Repository README](../../README.md#documentation): documentation index
- Internal records (not published): Task 6 backend integration, Task 21 final regression, Task 22 documentation and handover, handover to Teams 4A/4B
