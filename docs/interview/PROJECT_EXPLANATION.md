# Project Explanation (Spoken Versions)

Ready-to-speak explanations, from 30 seconds to a detailed walkthrough. Practise them aloud. Keep the honest framing: **a collaborative industry project in which I was a Team 4C member**.

---

## A. 30-second introduction

> "At Accion Labs I worked on the Multi-Modal Educational Intelligence Copilot, an AI study assistant. Students upload PDFs and YouTube lectures into a workspace and ask questions. The tutor answers from their material, and grounded answers carry citations that open the exact PDF page or jump the video to the exact timestamp. If the material doesn't support an answer, it says so. Three teams built it. I was in Team 4C: I worked on the Next.js application and its integration with the Python RAG backend, including authentication, workspace isolation, streaming chat and citations."

## B. 1-minute introduction

> "EduCopilot solves a common student problem: you have long PDFs and hour-long lectures, and finding one answer is slow. General chatbots don't know your notes and can make things up.
>
> In EduCopilot, a student creates a workspace, uploads PDFs or adds YouTube links, and chats with an AI tutor. The backend extracts text page by page, or from captions with timestamps. It chunks the text, creates embeddings with all-minilm, and stores them in Qdrant. For each question it runs hybrid search, BM25 plus vector search merged with Reciprocal Rank Fusion, and llama3 writes an answer that must cite the passages. The backend verifies the answer before streaming it. If the material doesn't support an answer, the tutor says so.
>
> Teams 4A and 4B built the ingestion and RAG backend. My Team 4C work was the Next.js 16 application and the integration layer: Auth.js login, MongoDB data, workspace ownership checks, short-lived ES256 tokens between the services, the streaming chat with citations, and a lot of testing and verification."

## C. 3-minute explanation

**1. Problem (20 s)**

"Students study from PDFs and recorded lectures. Searching them is slow, Ctrl+F misses paraphrases, videos can't be searched, and chatbots hallucinate and give no proof."

**2. Solution (30 s)**

"EduCopilot is a RAG-based tutor. It retrieves passages from the student's own material, answers from them with page-level and timestamp-level citations, and with an honest 'not enough context' answer when the material doesn't cover the question."

**3. Architecture (60 s)**

"There are two services. The **Next.js application** is the student-facing app plus a server layer: Auth.js login, MongoDB through Mongoose, file storage, and route handlers that check ownership. The **FastAPI backend** does ingestion and question answering, using Qdrant for vectors, BM25 for keywords, and Ollama running llama3 and all-minilm locally.
The browser never calls the backend directly. The Next.js server checks that the student owns the workspace, then signs a five-minute ES256 JWT that names only that workspace. The backend verifies everything about the token (algorithm, signature, issuer, audience, scope, lifetime, one-time use) and uses only the token's workspace in every query. So isolation does not depend on the frontend."

**4. Question flow (40 s)**

"When a student asks something, the chat route saves the question, sends it with the conversation's selected sources, and the backend runs BM25 and vector search in parallel and merges them with RRF. It takes the top five chunks plus their neighbours and asks llama3 for a JSON answer with citation labels. Then it checks the answer: citations must be real, the answer must be supported by the cited text, and declines can't carry citations. Only then does it stream. Next.js maps citations to the student's files, saves the answer, and streams it to the browser using the Vercel AI SDK. Clicking a citation opens the PDF page or seeks the video."

**5. My contribution (30 s)**

"In Team 4C I worked on the application (auth, workspaces, uploads with duplicate detection, streaming chat, stop generation, citations, history) and on the integration layer in the backend: the ingestion and query APIs, token verification and production hardening. I also did a lot of verification: workspace-isolation checks, browser end-to-end runs, and fixes for security bugs like a logout race condition."

**6. Results and honesty (20 s)**

"In the final run, the backend suite had 798 passing tests with zero failures. Frontend tests passed 1,634 of 1,635; the one failure is timing-sensitive. TypeScript was clean and the production build succeeded. It ran as a local demo; it is not production-deployed, and some answer-quality issues are still open on the RAG side."

---

## D. Detailed architecture explanation (for a whiteboard)

Draw this:

```text
Browser ──► Next.js (UI + route handlers) ──► MongoDB
                │  ES256 token (5 min, 1 workspace)
                ▼
          FastAPI backend ──► Qdrant (vectors)
                │        └──► Ollama (llama3, all-minilm)
                └──► YouTube captions
```

Explain in this order:
1. **Two services, one boundary.** The UI and the app's own server are in Next.js; AI work is in Python.
2. **Data ownership.** MongoDB holds app data (only Next.js touches it); the backend holds chunks and vectors.
3. **Trust.** The browser → Next.js boundary is protected by session + ownership checks. The Next.js → backend boundary is protected by signed, scoped tokens.
4. **Ingestion path.** Upload → store → capability URL → backend fetch → extract → chunk → embed → index → activate.
5. **Query path.** Question → scope → hybrid retrieval → prompt → llama3 → verify → stream → map citations → save.

Full detail: [System architecture](../architecture/SYSTEM_ARCHITECTURE.md).

## E. Problem statement (one paragraph)

> "Students need quick, trustworthy answers from their own study material (PDFs and video lectures). Manual searching is slow, keyword search misses paraphrases, video content isn't searchable, and general-purpose chatbots don't know the student's material and may hallucinate without giving sources."

## F. Proposed solution (one paragraph)

> "A web application where each student keeps private subject workspaces of PDFs and YouTube lectures, and asks an AI tutor questions. The tutor uses Retrieval-Augmented Generation with hybrid search to find relevant passages in that workspace only, generates an answer with a local LLM, verifies the answer and its citations, and streams it with links to the exact page or timestamp."

## G. Complete workflow (step list)

1. Sign up / log in (Auth.js, bcrypt, JWT cookie).
2. Create a workspace.
3. Upload a PDF (progress bar) or add a YouTube link → duplicate check → stored → backend ingestion → `ready`.
4. Open a conversation; optionally choose sources.
5. Ask a question → the question is saved → the backend retrieves and generates → verified answer streams in.
6. Click a citation → PDF page opens / video seeks.
7. Rename, revisit or delete conversations; delete materials or the workspace (backend cleaned first).
8. Log out → session revoked.

## Tips for delivery

- Say **"we"** for the team's system and **"I"** for your Team 4C work. Be precise about which is which.
- Use one **concrete example**: "Why do processes get stuck waiting forever?" → finds the deadlock page.
- Mention **one real bug** you investigated (see [Challenges and solutions](CHALLENGES_AND_SOLUTIONS.md)). Interviewers love this.
- Be upfront about **limitations**. It shows maturity.
