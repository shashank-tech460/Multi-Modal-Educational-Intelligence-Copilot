# Changelog

This changelog tracks the **portfolio documentation repository**. The project's own development timeline is summarised below for context.

## Portfolio repository

### [1.1.0] — Core Computer Engineering Subjects
- New `docs/core-subjects/` folder: an overview and eight subject documents (data structures and algorithms, object-oriented programming, database management systems, operating systems, computer networks, software engineering, computer organization and architecture, information security).
- Each document maps the subject to the project's actual implementation, with source file references, short approved code excerpts, trade-offs, limitations and interview questions.
- Publication of the project documentation and approved code excerpts was approved. The repository still does not contain the full application source code.

### [1.0.0] — Initial documentation release
- README, project overview, technology stack, contributions and known limitations.
- Architecture documents with Mermaid diagrams (system architecture, data flow).
- Technical documents: RAG pipeline, file ingestion, chat and streaming, database design, API documentation, authentication and security, testing.
- Guides: setup, environment, deployment.
- Learning notes: RAG, embeddings and vector databases, BM25/hybrid search/RRF, JWT and authentication, LLM streaming.
- Interview and viva preparation material.
- Documentation only; no application source code.

## Project timeline (context)

| Period (2026) | Milestone |
|---|---|
| September | Project start. Team 4A/4B backend foundation (data models, vector store, conversation memory), then hybrid retrieval and grounded generation. Team 4C architecture decisions, data model, and a mock-first frontend |
| September–October | Multimedia ingestion (backend). Team 4C application: authentication, workspaces, materials, streaming chat, citations, video seeking |
| Late October | Team 4A/4B final integrated backend. Team 4C integration layer: workspace-scoped ingest and query APIs, ES256 service tokens |
| November | Stabilisation tasks: YouTube timestamp verification, workspace isolation, backend integration, browser end-to-end, security and reliability, production hardening, project audit, stop generation, duplicate prevention, rename, drafts, history paging, session expiry, processing recovery, question persistence, final regression, documentation and handover |
