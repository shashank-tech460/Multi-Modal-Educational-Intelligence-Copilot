# Changelog

This changelog tracks the **portfolio documentation repository**. The project's own development timeline is summarised below for context.

## Portfolio repository

### [1.0.0] — Initial documentation release
- README, project overview, technology stack, contributions and known limitations.
- Architecture documents with Mermaid diagrams (system architecture, data flow).
- Technical documents: RAG pipeline, file ingestion, chat and streaming, database design, API documentation, authentication and security, testing.
- Guides: setup, environment, deployment.
- Learning notes: RAG, embeddings and vector databases, BM25/hybrid search/RRF, JWT and authentication, LLM streaming.
- Interview and viva preparation material.
- Documentation only; no application source code (publication permission for the integrated code is not established).

## Project timeline (context)

| Period (2026) | Milestone |
|---|---|
| September | Project start. Team 4A/4B backend foundation (data models, vector store, conversation memory), then hybrid retrieval and grounded generation. Team 4C architecture decisions, data model, and a mock-first frontend |
| September–October | Multimedia ingestion (backend). Team 4C application: authentication, workspaces, materials, streaming chat, citations, video seeking |
| Late October | Team 4A/4B final integrated backend. Team 4C integration layer: workspace-scoped ingest and query APIs, ES256 service tokens |
| November | Stabilisation tasks: YouTube timestamp verification, workspace isolation, backend integration, browser end-to-end, security and reliability, production hardening, project audit, stop generation, duplicate prevention, rename, drafts, history paging, session expiry, processing recovery, question persistence, final regression, documentation and handover |
