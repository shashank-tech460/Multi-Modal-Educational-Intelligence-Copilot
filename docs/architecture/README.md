# Architecture Diagram Package

Six professional architecture diagrams for EduCopilot, each in a **documentation layout** and a **16:9 presentation layout**, as SVG and PNG. They describe the **verified final integrated build** as run in the local demo. The checks behind them are in [Architecture verification](ARCHITECTURE_VERIFICATION.md).

The original 27 Mermaid diagrams remain in their documents as the editable, in-page diagrams. This package adds polished versions of the six most important views.

---

## The six diagrams

| # | Diagram | What it shows | Detailed explanation |
|---|---|---|---|
| 1 | [Complete System Architecture](complete-system/complete-system-architecture.png) | The flagship view: student, Team 4C Next.js app, Team 4C integration layer, joint Team 4A/4B backend, MongoDB, in-process stores, Ollama and YouTube, with numbered flows | [System architecture](SYSTEM_ARCHITECTURE.md) |
| 2 | [PDF and YouTube Ingestion](ingestion/ingestion-architecture.png) | Separate PDF and YouTube input paths joining one common chunk → embed → index → activate pipeline; file status lifecycle | [Data flow](DATA_FLOW.md) · [File ingestion](../technical/FILE_INGESTION.md) |
| 3 | [RAG Pipeline](rag-pipeline/rag-pipeline-architecture.png) | Follow-up handling, scope, vector + BM25 search, RRF, the single score threshold (0.5 code / 0.25 demo), top 5 + neighbours, generation, verification, answer or refusal | [RAG pipeline](../technical/RAG_PIPELINE.md) |
| 4 | [Authentication and Security](security/security-architecture.png) | The three trust boundaries: user authentication, ownership authorization, ES256 service authentication | [Authentication and security](../technical/AUTHENTICATION_AND_SECURITY.md) |
| 5 | [Database and Storage](database/database-storage-architecture.png) | MongoDB collections and relations (owned by Next.js) vs in-process backend stores (Qdrant, ingest registry, FakeRedis memory) and the shared identifiers | [Database design](../technical/DATABASE_DESIGN.md) |
| 6 | [End-to-End Question and Answer Flow](end-to-end-flow/question-answer-flow.png) | 15 numbered steps from the browser through Next.js, MongoDB, the backend and Ollama, and back | [Chat and streaming](../technical/CHAT_AND_STREAMING.md) |

## Files

Each folder holds four files for one diagram:

| Folder | Documentation SVG | Documentation PNG | 16:9 SVG | 16:9 PNG |
|---|---|---|---|---|
| `complete-system/` | [svg](complete-system/complete-system-architecture.svg) | [png](complete-system/complete-system-architecture.png) | [svg](complete-system/complete-system-architecture-16x9.svg) | [png](complete-system/complete-system-architecture-16x9.png) |
| `ingestion/` | [svg](ingestion/ingestion-architecture.svg) | [png](ingestion/ingestion-architecture.png) | [svg](ingestion/ingestion-architecture-16x9.svg) | [png](ingestion/ingestion-architecture-16x9.png) |
| `rag-pipeline/` | [svg](rag-pipeline/rag-pipeline-architecture.svg) | [png](rag-pipeline/rag-pipeline-architecture.png) | [svg](rag-pipeline/rag-pipeline-architecture-16x9.svg) | [png](rag-pipeline/rag-pipeline-architecture-16x9.png) |
| `security/` | [svg](security/security-architecture.svg) | [png](security/security-architecture.png) | [svg](security/security-architecture-16x9.svg) | [png](security/security-architecture-16x9.png) |
| `database/` | [svg](database/database-storage-architecture.svg) | [png](database/database-storage-architecture.png) | [svg](database/database-storage-architecture-16x9.svg) | [png](database/database-storage-architecture-16x9.png) |
| `end-to-end-flow/` | [svg](end-to-end-flow/question-answer-flow.svg) | [png](end-to-end-flow/question-answer-flow.png) | [svg](end-to-end-flow/question-answer-flow-16x9.svg) | [png](end-to-end-flow/question-answer-flow-16x9.png) |

### Which format to use

| Use | Format |
|---|---|
| GitHub pages and Markdown documents | Documentation **PNG**. It renders the same everywhere; fonts in an SVG depend on the viewer |
| Reports, theses, printed documents | Documentation **SVG**, which scales without blur, or the PNG (3400 px wide) |
| Slides and presentations | **16:9 PNG** (3840 × 2160) or **16:9 SVG** (1920 × 1080) |
| Editing a diagram | `_source/build_diagrams.py`, which regenerates every SVG |

## Design system

| Colour | Meaning |
|---|---|
| Blue | Team 4C application (Next.js) |
| Purple | Team 4C authentication and integration layer (token signer and verifier, ownership checks, ingestion and query APIs, ingest registry) |
| Green | Team 4A/4B capabilities inside the joint FastAPI backend |
| Amber | Data stores |
| Grey | Student, runtime or external service (Ollama, YouTube) |
| Red dashed line | Trust boundary |

Dark numbered circles mark the order of the main flows. Double arrowheads mean request and response. Every diagram has a legend. Documentation layouts also carry technical notes.

## Inventory of all 27 Mermaid diagrams

| # | Diagram | Source document | Type | Professional export |
|---|---|---|---|---|
| 1 | High-level system architecture | [README](../../README.md) | flowchart | Basis of diagram 1 |
| 2 | Student journey | [Project overview](../../PROJECT_OVERVIEW.md) | flowchart | No (product flow) |
| 3 | Team 4C components and connections | [Contributions](../../CONTRIBUTIONS.md) | flowchart | Folded into diagram 1 (team colours) |
| 4 | D1 Complete system architecture | [System architecture](SYSTEM_ARCHITECTURE.md) | flowchart | **Diagram 1** |
| 5 | D2 Frontend-to-backend communication | [System architecture](SYSTEM_ARCHITECTURE.md) | sequence | **Diagram 4** |
| 6 | D3 PDF ingestion pipeline | [Data flow](DATA_FLOW.md) | sequence | **Diagram 2** |
| 7 | D4 YouTube ingestion pipeline | [Data flow](DATA_FLOW.md) | sequence | **Diagram 2** |
| 8 | D5 Question answering and citations | [Data flow](DATA_FLOW.md) | sequence | **Diagram 6** |
| 9 | Order of operations when a file is deleted | [Data flow](DATA_FLOW.md) | flowchart | No |
| 10 | Proposed production architecture | [Deployment](../guides/DEPLOYMENT.md) | flowchart | No (not built) |
| 11 | Full-stack startup order | [Setup](../guides/SETUP.md) | flowchart | No |
| 12 | Methodology | [Viva preparation](../interview/VIVA_PREPARATION.md) | flowchart | No |
| 13 | DFD Level 0 | [Viva preparation](../interview/VIVA_PREPARATION.md) | flowchart | No |
| 14 | Fusing rankings with RRF | [BM25 and hybrid search](../learning/BM25_AND_HYBRID_SEARCH.md) | flowchart | No (teaching aid) |
| 15 | Streaming chain | [LLM streaming](../learning/LLM_STREAMING.md) | flowchart | Covered by diagram 6 |
| 16 | The three steps of RAG | [RAG fundamentals](../learning/RAG_FUNDAMENTALS.md) | flowchart | No (teaching aid) |
| 17 | Vector search for one question | [Vector databases](../learning/VECTOR_DATABASES.md) | flowchart | No (teaching aid) |
| 18 | D11 Authentication and authorization flow | [Authentication and security](../technical/AUTHENTICATION_AND_SECURITY.md) | sequence | **Diagram 4** |
| 19 | D12 Workspace ownership verification | [Authentication and security](../technical/AUTHENTICATION_AND_SECURITY.md) | flowchart | **Diagram 4** |
| 20 | Three hops of a chat answer | [Chat and streaming](../technical/CHAT_AND_STREAMING.md) | flowchart | Covered by diagram 6 |
| 21 | MongoDB entity-relationship model | [Database design](../technical/DATABASE_DESIGN.md) | erDiagram | **Diagram 5** |
| 22 | File status lifecycle | [File ingestion](../technical/FILE_INGESTION.md) | state | Inset in diagram 2 |
| 23 | D6 Text extraction and chunking | [RAG pipeline](../technical/RAG_PIPELINE.md) | flowchart | **Diagram 3** |
| 24 | D7 Embedding and vector storage | [RAG pipeline](../technical/RAG_PIPELINE.md) | flowchart | **Diagram 3** |
| 25 | D8 BM25 retrieval | [RAG pipeline](../technical/RAG_PIPELINE.md) | flowchart | **Diagram 3** |
| 26 | D9 Hybrid retrieval and RRF | [RAG pipeline](../technical/RAG_PIPELINE.md) | flowchart | **Diagram 3** |
| 27 | D10 LLM answer generation and verification | [RAG pipeline](../technical/RAG_PIPELINE.md) | flowchart | **Diagram 3** |

## Sources and accuracy

- **Facts:** every component, endpoint, port, field and setting comes from the final integrated build and the documents linked above. Ports and models are those of the verified local demo (Next.js 3000, FastAPI 8001, Ollama 11434; `llama3:latest`, `all-minilm`).
- **Team labels:** Team 4A / 4B labels inside the joint backend follow the original team responsibilities. Per-file authorship is not recorded.
- **Left out on purpose:** a MongoDB host or port (not verified) and any Docker or cloud components (none were part of the verified demo). The proposed production design is **not** drawn here.

## Regenerating the diagrams

1. Edit `_source/build_diagrams.py` (diagram content) or `_source/diagramkit.py` (shared styles). Both use only the Python standard library.
2. Run `python build_diagrams.py` inside `_source/`. It rewrites all twelve SVGs and warns if text overflows a box.
3. Export PNGs from the SVGs with any headless browser at device scale 2. Documentation PNGs are 3400 px wide; 16:9 PNGs are 3840 × 2160.
