# Known Limitations

This is the honest list of what the integrated system does **not** do, or does not do well, as of the final integrated version (November 2026).

---

## 1. Deployment status

| Item | Status |
|---|---|
| Local demo on one machine | **Works**, with a local launcher script (kept outside the code repository) that starts the services in order |
| Public production deployment | **Not done and not ready** |
| Production prerequisites not verified | HTTPS / reverse proxy, production secret management, managed MongoDB with backup and restore, a live database index check, multi-instance operation and shared file storage, and a complete production launcher |
| Horizontal scaling (several servers) | **Not supported** by the current design: uploads are on local disk, rate limiters and backend sessions are in memory, and Qdrant runs embedded in the backend process |

## 2. Product scope (not built)

| Feature | Status |
|---|---|
| MP4 / video-file upload | Intentionally excluded; rejected with a clear message |
| Scanned PDFs (image-only pages) | Not supported on the product path. Pages without a text layer produce no text, and the student-facing message for this case is misleading |
| YouTube videos without captions | Cannot be ingested (captions are the source of the text) |
| Account deletion | Not built (pending a product decision) |
| Workspace rename, conversation search, multi-line input | Not built |
| Remembering the last open conversation after reload | Not built |
| Language attributes for non-Latin or right-to-left text in the UI | Optional enhancement, not built |

## 3. Answer quality (open, owned by the RAG side, shared investigation)

| Issue | Effect |
|---|---|
| Different follow-up questions in one session can return the **identical answer** | Confusing follow-ups |
| **Intermittent "not enough context"** declines even when the material contains the answer | Student gets no answer |
| Indic-language PDF text extraction and keyword tokenisation | Known defects, tracked as expected test failures |

These were recorded with evidence in a handover to the backend teams, along with an earlier 22-item answer-quality register.

## 4. Open technical items

| Item | Notes |
|---|---|
| Backend conversation history can diverge from MongoDB history | The backend RAG session (short-lived) and the saved chat history (MongoDB) are separate stores |
| Embedded Qdrant lock | Backend tests fail with lock errors if run **next to a running backend** that uses the same local Qdrant folder. Isolated runs pass |
| yt-dlp format warning on every YouTube ingest | Non-fatal; captions are still fetched |
| Backend diagnostics not written to the log file | Operational gap |
| Legacy backend routes are unauthenticated in **development** mode | They are blocked in production mode by an allowlist |
| Question-length limit is defined on both sides of the service boundary | Must be kept in sync by hand |
| Legacy field `File.currentIngestionGeneration` | Left over from an earlier version's contract; unused in the final build. One project handover note still describes it as written by a Team 4A component that is not part of the final backend ([details](docs/architecture/ARCHITECTURE_VERIFICATION.md)) |
| Workspace deletion does not delete backend RAG sessions | They expire on their own (30-minute TTL) |
| Some browser test specs are desktop-only, one has an outdated selector, and the base URL is hard-coded | Test-code issues; the product works |
| 12 ESLint problems (9 errors, 3 warnings), mostly `any` types in two test files | Pre-existing |
| One frontend test is timing-sensitive in the full Vitest run | Passes when run alone |
| A Mongoose deprecation warning (`new: true` option) | Cosmetic |

## 5. Security limitations

The main ones are in-memory rate limits and replay cache (a single-instance design), no "log out everywhere", local-disk file serving, and no HTTPS or penetration test in the local demo. The full list is in [Authentication and security §10](docs/technical/AUTHENTICATION_AND_SECURITY.md#10-security-limitations). Production requirements are in [Deployment](docs/guides/DEPLOYMENT.md).
