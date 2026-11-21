# Data Flow

This document follows the data step by step through the main journeys: adding a PDF, adding a YouTube video, asking a question, and deleting material.

Related: [System architecture](SYSTEM_ARCHITECTURE.md) · [File ingestion](../technical/FILE_INGESTION.md) · [RAG pipeline](../technical/RAG_PIPELINE.md)

Professional diagrams: [Ingestion architecture](ingestion/ingestion-architecture.png) · [End-to-end question and answer flow](end-to-end-flow/question-answer-flow.png)

---

## Diagram 3: PDF ingestion pipeline

```mermaid
sequenceDiagram
    autonumber
    participant B as Browser
    participant N as Next.js (files route)
    participant M as MongoDB
    participant D as Local upload folder
    participant P as Backend /v1/ingest
    participant O as Ollama (all-minilm)
    participant Q as Qdrant

    B->>N: POST multipart PDF (XHR with progress bar)
    N->>N: Session + workspace ownership check<br/>type = PDF, size <= 50 MB
    N->>N: SHA-256 of the content
    N->>M: Same content already in this workspace?
    alt duplicate
        M-->>N: existing File
        N-->>B: reuse existing material (no second copy)
    else new
        N->>D: save bytes under the workspace folder
        N->>M: create File {status: "processing", lease}
        N->>P: POST /v1/ingest {document_id, file_type, file_url, title}<br/>+ ES256 token (aud team4a-ingestion)
        P->>P: verify token, create job (new generation)
        P->>N: GET capability URL (allowed origin only)
        N-->>P: PDF bytes (checks size and %PDF- signature)
        P->>P: pypdf: text page by page
        P->>P: chunk each page (structure-aware, size-bounded),<br/>page_number on every chunk
        P->>O: embed chunks
        O-->>P: 384-dim vectors
        P->>Q: upsert chunks tagged with workspace, document, generation
        P->>P: activate generation (now searchable)<br/>then delete older generations' chunks
        P-->>N: 200 {state: "ready", chunks_indexed}
        N->>M: File.status = "ready"
        N-->>B: 201 File (ready, or failed with a student-friendly message)
    end
```

In the ingest call, `document_id` is the MongoDB `File._id` and `file_url` is a 10-minute capability URL for the stored PDF.

Important points:

- **The call is synchronous.** The backend answers only after the chunks are indexed and activated, and the upload request waits for it (up to 5 minutes). The materials list also polls status, so other tabs and reloads see the change.
- **Generations** make re-ingestion safe. A failed attempt leaves the previous generation active, and partial chunks are never searchable.
- A **processing lease** (renewed every 30 seconds while the request is alive) lets the app detect files stuck in "processing" after a crash and recover them.
- Pages with no text layer (scanned pages) produce no text. OCR is not part of this path.

---

## Diagram 4: YouTube ingestion pipeline

```mermaid
sequenceDiagram
    autonumber
    participant B as Browser
    participant N as Next.js (files route)
    participant M as MongoDB
    participant P as Backend /v1/ingest
    participant Y as YouTube
    participant O as Ollama (all-minilm)
    participant Q as Qdrant

    B->>N: POST form {type: youtube_url, youtubeUrl}
    N->>N: session, ownership, extract 11-char video id
    N->>M: Same video already in this workspace?
    alt duplicate
        N-->>B: existing material
    else new
        N->>M: create File {type: youtube_url, youtubeVideoId, status: processing}
        N->>P: POST /v1/ingest {document_id, file_type: youtube, file_url}<br/>+ ES256 token
        P->>Y: list caption tracks
        P->>P: prefer English (manual, then auto-generated),<br/>else the video's own track
        P->>Y: fetch timed caption segments + title
        P->>P: build chunks from whole caption segments<br/>each with start_seconds / end_seconds
        P->>O: embed chunks
        P->>Q: upsert + activate generation
        P-->>N: 200 ready
        N->>M: status = ready
    end
```

No file is stored for a YouTube link; the backend fetches the captions itself. The duplicate check uses the video id, so the same lecture is never indexed twice in one workspace. YouTube ingestion is turned on with `INGEST_YOUTUBE_ENABLED=true`. A video without captions cannot be ingested.

---

## Diagram 5: Question answering and citation generation

```mermaid
sequenceDiagram
    autonumber
    participant B as Browser (useChat)
    participant N as Next.js /api/chat
    participant M as MongoDB
    participant P as Backend /api/v1/query/stream
    participant R as Hybrid retriever
    participant L as llama3 (Ollama)

    B->>N: POST {messages, workspaceId, conversationId}
    N->>N: session, rate limit (20/min default),<br/>question length check
    N->>M: user owns workspace AND conversation?
    N->>M: save the user's question (state: generating)
    N->>M: read conversation source scope -> document ids
    N->>P: {query, session_id, retrieval_config: {document_ids}}<br/>+ ES256 token (aud team4b-query)
    P->>P: verify token, workspace = token.workspace_id
    P->>P: follow-up? add the conversation topic to the search query
    P->>R: retrieve_scoped(query, workspace, documents, active generations)
    R-->>P: top 5 chunks + neighbour chunks
    P->>L: system prompt + evidence C1..Cn + recent history + question<br/>(JSON output, temperature 0)
    L-->>P: {"answer": "... [C2] ...", "citations": ["C2"]}
    P->>P: keep only real labels, renumber to [1], [2]
    P->>P: decline? weak support (< 25%)? unverifiable citation?<br/>-> "not enough context", no citations
    P->>P: save turn in conversation memory
    P-->>N: NDJSON: delta, delta, ... then done {answer, source_attributions}
    N->>M: map document ids -> this workspace's Files,<br/>drop anything outside the workspace
    N->>M: save assistant message with citations,<br/>auto-title new conversation
    N-->>B: UI message stream: text + data-citations
    B->>B: render answer + citation chips<br/>PDF -> open file#page=N, video -> seek to t
```

The question is checked and saved **before** the backend is called, so it is never lost. The backend decides the workspace only from the token. It retrieves, generates, and **verifies before streaming**. The Next.js server then filters citations against the workspace's own files and saves the answer. Step-by-step detail: [Chat and streaming](../technical/CHAT_AND_STREAMING.md#2-what-the-chat-route-does).

### What a citation contains at each step

| Step | Shape |
|---|---|
| Stored chunk metadata (backend) | `source_type: pdf/youtube`, `title`, `page_number` **or** `start_seconds` + `end_seconds` |
| Backend response (`source_attributions`) | `document_id`, `document_title`, `chunk_id`, `relevance_score`, `page_number` **or** `start_timestamp`/`end_timestamp` |
| Saved in MongoDB (`Message.citations`) | `fileId`, `type: pdf/video`, `pageNumber` **or** `timestampSeconds` |
| Shown in UI | file's real name, page or `mm:ss`, a link or seek action |

The display name always comes from **MongoDB** (`File.originalName`), not from the backend. The backend only knows its storage name.

---

## Deleting material or a workspace

**Diagram: Order of operations when a file is deleted**

```mermaid
flowchart LR
    A["Delete file request"] --> B["Ownership check"]
    B --> C["Backend: DELETE /v1/documents/{id}<br/>(no longer retrievable, chunks removed)"]
    C --> D["Delete bytes from upload folder"]
    D --> E["Delete File record"]
```

The backend is cleaned up **first**, so a deleted file can never still be cited. Deleting a workspace repeats this for every file, then deletes its messages, conversations and the workspace itself. Backend conversation sessions are not deleted by a workspace delete; they expire after 30 minutes.

---

## Where data lives

All stores, their owners and how each one isolates workspaces are listed in [Database design §6](../technical/DATABASE_DESIGN.md#6-where-every-piece-of-data-lives).
