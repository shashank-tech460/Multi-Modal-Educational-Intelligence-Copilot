# Technology Stack

A quick reference of every technology **verified in the final integrated code**. It shows what each one is for and where EduCopilot uses it.

- How each technology works, and interview questions: [Tech stack deep dive](docs/technical/TECH_STACK_DEEP_DIVE.md)
- Alternatives and trade-offs: [Technology: why and why not](docs/interview/TECHNOLOGY_WHY_AND_WHY_NOT.md)

---

## Core stack

| Layer | Technology | Version | Purpose | Usage in EduCopilot |
|---|---|---|---|---|
| Frontend framework | **Next.js** (App Router) | 16.3 | UI routing and server-side code | Pages, layouts and server route handlers (`app/api/*`) that act as the app's own backend |
| UI | **React** | 19.2 | Component-based UI | Chat panel, conversation sidebar, materials list, video player |
| Language | **TypeScript** | 5 | Static typing | All frontend and Next.js server code; typed wire contracts for the backend |
| Authentication | **Auth.js** (next-auth) | 5.0 beta | Login and sessions | Credentials provider, JWT session cookie, route protection |
| Password hashing | **bcrypt** | 6 | Secure password storage | Hashes with cost factor 12 |
| Database | **MongoDB** | Not recorded | Document storage | Users, workspaces, conversations, messages, files, revoked sessions |
| ODM | **Mongoose** | 9 | Schemas and validation | Six models, validation rules, indexes |
| Chat streaming | **Vercel AI SDK** (`ai`, `@ai-sdk/react`) | 7 / 4 | Streaming chat UI and protocol | `useChat` in the browser; UI message stream from `/api/chat` |
| Backend language | **Python** | 3.11 | AI and document processing | Entire backend |
| Backend framework | **FastAPI** + Uvicorn | 0.115 / 0.34 | HTTP API | Ingestion and query endpoints; NDJSON streaming |
| Validation | **Pydantic** | 2.10 | Typed request and settings models | Strict validation of every backend input |
| Vector store | **Qdrant** (`qdrant-client`) | 1.12 | Vector similarity search | Chunk embeddings with workspace payload filters; embedded local mode in the demo |
| Keyword search | **rank-bm25** | 0.2.2 | BM25 (Okapi) ranking | Keyword half of hybrid retrieval |
| Rank fusion | **Reciprocal Rank Fusion** | In-house code, k = 60 | Merging two rankings | Combines BM25 and vector results |
| Model runtime | **Ollama** | Not recorded | Runs local models over HTTP | Chat and embedding calls from the backend |
| Answer model | **Llama 3** (`llama3:latest`) | — | Text generation | Writes grounded answers as structured JSON |
| Embedding model | **all-minilm** | — | Text embeddings | 384-dimensional vectors for chunks and questions |
| PDF extraction | **pypdf** | 5.1 | PDF text extraction | Text extracted page by page, keeping page numbers |
| YouTube captions | **youtube-transcript-api**, **yt-dlp** | 0.6 / 2024.11 | Captions and metadata | Timed caption segments; video title |
| Service tokens | **jose** (sign), **PyJWT** + cryptography (verify) | 6.2 / 2.15 | JWT signing and verification | ES256 service tokens; HS256 file capability tokens |
| Conversation memory | **FakeRedis / Redis** | — | Short-lived session store | Recent conversation turns for follow-ups (30-minute TTL) |

## Supporting frontend libraries

| Technology | Version | Purpose | Usage in EduCopilot |
|---|---|---|---|
| TanStack Query | 5 | Server-data caching | Workspaces, files and history |
| TanStack Virtual | 3 | List virtualisation | Long chat message lists |
| Zustand | 5 | Small global stores | Active workspace, offline queue, network quality, toasts |
| Tailwind CSS + shadcn/ui (Radix UI) | 4 | Styling and accessible primitives | Dialogs, menus, tooltips, layout |
| video.js + videojs-youtube | 8 / 3 | Controllable video player | Seeking to cited timestamps |
| react-markdown + remark-gfm | 10 / 4 | Markdown rendering | Formatted answers (lists, tables, code) |

## Testing

| Technology | Purpose | Usage in EduCopilot |
|---|---|---|
| Vitest + React Testing Library + jsdom | Frontend unit and component tests | 119 test files |
| Playwright + axe-core | Browser end-to-end and accessibility tests | Workflow and accessibility specs |
| pytest (+ pytest-asyncio, pytest-mock) | Backend tests | Integration and unit tests |
| Hypothesis | Property-based tests | Invariants in Team 4A/4B backend tests |

## Present but not used on the product path

These exist in the backend codebase (built by Teams 4A/4B) but are **disabled, optional, or used only by the legacy developer workbench**: faster-whisper (local transcription), RapidOCR (image OCR), Groq/Gemini media APIs, the LAYA re-ranker (disabled), a remote Qwen3 embedding option, and Docker Compose for standalone Qdrant/Redis.

> **Configuration notes**
> - `react-player` and `pdf-parse` are frontend dependencies. `react-player` is not imported; `pdf-parse` is used only by the development mock backend.
> - The backend's example environment file still names older model settings (`gemma3:1b`, Qwen3 embeddings). The **verified demo configuration** is `llama3:latest` + `all-minilm` (384 dimensions).
