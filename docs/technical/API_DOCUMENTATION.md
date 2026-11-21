# API Documentation

EduCopilot has two API layers:

1. **Application API**: Next.js route handlers called by the browser. They use **Auth.js session cookies**.
2. **Integration API**: FastAPI routes called **only by the Next.js server**. They use **ES256 service JWTs**.

Every endpoint below exists in the final integrated code. Hostnames are not shown; locally, the app runs on port 3000 and the backend on port 8001.

## Endpoint summary

| Method | Endpoint | Purpose | Authentication |
|---|---|---|---|
| POST | `/api/auth/signup` | Create an account | Public (rate-limited) |
| GET/POST | `/api/auth/[...nextauth]` | Auth.js sign-in, session, sign-out, CSRF | Public (Auth.js) |
| GET, POST | `/api/workspaces` | List or create workspaces | Session |
| GET, DELETE | `/api/workspaces/{id}` | Read or delete a workspace | Session + ownership |
| GET, POST | `/api/workspaces/{id}/files` | List or add materials | Session + ownership |
| DELETE | `/api/workspaces/{id}/files/{fileId}` | Delete a material | Session + ownership |
| POST | `/api/workspaces/{id}/files/{fileId}/retry` | Retry a failed material | Session + ownership |
| GET | `/api/local-storage/{workspaceId}/{publicId}` | Download a stored file | Session + ownership, **or** capability token |
| GET, POST | `/api/workspaces/{id}/conversations` | List (paged) or create conversations | Session + ownership |
| PATCH, DELETE | `/api/conversations/{id}` | Rename or delete a conversation | Session + ownership |
| GET | `/api/conversations/{id}/messages` | Conversation history | Session + ownership |
| GET, PATCH | `/api/conversations/{id}/scope` | Read or set selected sources | Session + ownership |
| POST | `/api/chat` | Ask a question (streamed answer) | Session + ownership |
| GET | `/api/health` | Liveness and readiness | Public |
| GET | `/api/network-check` | Network-quality probe | Public (rate-limited) |
| POST | `/v1/ingest` | Ingest a PDF or YouTube video | Service JWT (`team4a-ingestion`) |
| GET | `/v1/ingest/jobs/{job_id}` | Ingest job status | Service JWT (`team4a-ingestion`) |
| DELETE | `/v1/documents/{document_id}` | Remove a document from retrieval | Service JWT (`team4a-ingestion`) |
| POST | `/api/v1/query`, `/api/v1/query/stream` | Answer a question (JSON or NDJSON) | Service JWT (`team4b-query`) |
| POST, DELETE, GET | `/api/v1/sessions/{id}[/seed \| /history]` | Seed, delete or check a backend session | Service JWT (`team4b-query`) |
| GET | `/healthz` | Backend liveness probe | Public |

---

## Common rules (Application API)

| Rule | Behaviour |
|---|---|
| Authentication | Auth.js session cookie. Missing or expired → **401** `{"error":"Unauthorized."}` |
| Ownership | The workspace (and the conversation or file) must belong to the user. Otherwise → **404** `{"error":"Not found."}`. It is a 404, not a 403, so the API does not reveal that someone else's item exists |
| Validation errors | **400** `{"error": "<message>"}` |
| Rate limits | **429** with a friendly message |
| Error text | Short and student-friendly; technical details stay in server logs |

---

## 1. Authentication

### `POST /api/auth/signup`
Creates an account. **Public**, rate-limited.

| Case | Response |
|---|---|
| Request body | `{"name": "Student", "email": "student@example.com", "password": "..."}` |
| 201 | Account created (the client then signs in automatically) |
| 400 | Invalid body or field errors: `{"errors": {...}}` |
| 409 | Email already registered |
| 429 | Too many sign-up attempts |

### `GET/POST /api/auth/[...nextauth]`
Auth.js endpoints (CSRF token, credentials sign-in, session, sign-out). Sign-in uses the **credentials** provider; a failure always returns the generic message *"Invalid email or password"*.

---

## 2. Workspaces

| Method | Endpoint | Purpose | Success | Errors |
|---|---|---|---|---|
| GET | `/api/workspaces` | List the user's workspaces | 200 `[...]` | 401 |
| POST | `/api/workspaces` | Create `{"name": "Operating Systems"}` | 201 workspace | 400, 401 |
| GET | `/api/workspaces/{id}` | One workspace | 200 | 401, 404 |
| DELETE | `/api/workspaces/{id}` | Delete with cascade (backend documents first) | 200 | 401, 404, **502** if backend clean-up fails |

## 3. Learning materials (files)

| Method | Endpoint | Purpose | Success | Errors |
|---|---|---|---|---|
| GET | `/api/workspaces/{id}/files` | List materials (recovers abandoned "processing" items first) | 200 `[file...]` | 401, 404 |
| POST | `/api/workspaces/{id}/files` | Multipart form: `type` (`pdf` or `youtube_url`) plus `file` or `youtubeUrl`, and an optional `uploadIdempotencyKey`. Runs ingestion before answering | **201** new file · **200** reused existing (duplicate content or video) | 400 (type, size, bad link), 401, 404, **409** same video or upload already in progress |
| DELETE | `/api/workspaces/{id}/files/{fileId}` | Delete (backend → bytes → record) | 200 | 401, 404, 502 |
| POST | `/api/workspaces/{id}/files/{fileId}/retry` | Retry a failed file | 200 | 401, 404, 409 (not retryable) |

**File object (example):**
```json
{
  "id": "665f...a1",
  "originalName": "OS-Unit3.pdf",
  "type": "pdf",
  "status": "ready",
  "processingError": null,
  "storageUrl": "/api/local-storage/665f...10/2b6c...-OS-Unit3.pdf",
  "createdAt": "2026-11-18T10:21:00.000Z",
  "sizeBytes": 734003
}
```
*(Illustrative values; these are the fields the server returns.)*

### `GET /api/local-storage/{workspaceId}/{publicId}`
Serves a stored file. Allowed with **(a)** a session that owns the workspace, or **(b)** a valid `?capability=` token (HS256, 10 minutes, bound to this exact workspace and file). An invalid token is a **401** and does **not** fall back to the session. → 200 bytes / 401 / 404.

## 4. Conversations

| Method | Endpoint | Purpose | Success | Errors |
|---|---|---|---|---|
| GET | `/api/workspaces/{id}/conversations?limit=&cursor=` | Paged list, newest first | 200 `{"conversations": [...], "nextCursor": "..." \| null}` | 401, 404 |
| POST | `/api/workspaces/{id}/conversations` | New conversation ("New conversation") | 201 | 400, 401, 404 |
| PATCH | `/api/conversations/{id}?workspaceId=` | Rename `{"title": "..."}`; sets `titleSetManually` | 200 | 400, 401, 404 |
| DELETE | `/api/conversations/{id}?workspaceId=` | Delete conversation, messages and backend session | 200 `{"success": true}` | 400, 401, 404, 500 |
| GET | `/api/conversations/{id}/messages?workspaceId=` | Full history, including failed and stopped questions | 200 | 401, 404 |
| GET | `/api/conversations/{id}/scope` | Selected sources | 200 `{"document_ids": [...] \| null}` | 401, 404 |
| PATCH | `/api/conversations/{id}/scope` | Set sources `{"document_ids": [...] \| null}` (max 100; each must be a file in the workspace) | 200 | 400, 401, 404 |

**Cursor paging:** the cursor encodes `(updatedAt, _id)` of the last item. The next page asks for items strictly older than it. This stays correct even when new conversations are added between page loads, which offset paging (`skip`) does not.

## 5. Chat

### `POST /api/chat`
Asks a question and returns a **streamed** answer (Vercel AI SDK UI message stream).

**Request** (sent by `useChat`):
```json
{
  "messages": [{ "id": "msg-123", "role": "user", "parts": [{ "type": "text", "text": "What is a deadlock?" }] }],
  "workspaceId": "665f...10",
  "conversationId": "6660...22",
  "videoTimestamp": null
}
```

**Stream contents:** text parts (the answer), a `data-citations` part:
```json
[{ "fileId": "665f...a1", "type": "pdf_page", "location": 12, "sourceFile": "OS-Unit3.pdf",
   "fileUrl": "/api/local-storage/..." }]
```
and optional draft parts (unverified preview) when drafts are enabled. *(Illustrative.)*

| Status | When |
|---|---|
| 200 stream | Answer (including the honest "not enough context" answer) |
| 400 | Blank question, question longer than 2,000 characters, or invalid body (checked before anything is stored or sent to the backend) |
| 401 | Not signed in |
| 404 | Workspace or conversation not owned |
| 409 | "This question is already being answered" (same question still in progress) |
| 422 | The backend refused the query as invalid ("Your question couldn't be processed...") |
| 429 | Chat rate limit (default 20 per minute) |
| 499 | Browser aborted before the stream started |
| 500 / 502 | Server error / backend refused or unavailable (student-friendly text) |

## 6. Utility

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/health` | Liveness → 200 `{"status":"ok"}` |
| GET | `/api/health?ready=1` | Readiness: MongoDB ping → 200 `ok` or 503 `unavailable`. Reveals nothing else |
| GET | `/api/network-check` | Tiny latency/bandwidth probe for the network-quality indicator (rate-limited) |

---

## 7. Integration API (FastAPI, server-to-server)

**Authentication:** `Authorization: Bearer <ES256 JWT>` on every route. The workspace comes **only** from the token's `workspace_id` claim, never from the body.

| Audience | Scope | Routes |
|---|---|---|
| `team4a-ingestion` | `ingest` | `/v1/ingest`, `/v1/ingest/jobs/{id}`, `/v1/documents/{id}` |
| `team4b-query` | `query` | `/api/v1/query`, `/api/v1/query/stream`, `/api/v1/sessions/...` |

**Error envelope** (safe, no internals):
```json
{ "error": { "code": "unauthorized", "message": "..." } }
```
Codes include `unauthorized` (401), `forbidden` (403), `not_found` (404), `conflict` (409), `invalid_request` (422), `upstream_unavailable` / `auth_unavailable` (503). *(Shape shown in simplified form.)*

### `POST /v1/ingest`
```json
{ "document_id": "665f...a1", "file_type": "pdf", "file_url": "<capability URL>", "title": "OS-Unit3.pdf" }
```
`file_type`: `pdf` or `youtube` (`mp4` → 422 unsupported). Returns **200 only after indexing and activation**:
```json
{ "job_id": "...", "document_id": "665f...a1", "generation": 2, "state": "ready", "error": null, "chunks_indexed": 41 }
```
Any failure is a non-2xx error envelope. The previous generation stays active.

### `GET /v1/ingest/jobs/{job_id}`
Job status. **404** for an unknown job or another workspace's job.

### `DELETE /v1/documents/{document_id}`
`{"document_id": "...", "state": "deleted"}`. Idempotent; the document stops being retrievable immediately.

### `POST /api/v1/query`
```json
{ "query": "What is a deadlock?", "session_id": "<uuid v4 or null>",
  "retrieval_config": { "document_ids": ["665f...a1"] } }
```
→ `{"answer": "...", "session_id": "...", "source_attributions": [...], "retrieval_metadata": {...}}`

`retrieval_config` may also carry `top_k`, `score_threshold` and `search_mode` (validated ranges). EduCopilot sends only `document_ids`, or `null` for the whole workspace.

**Source attribution fields:** `document_id`, `document_title`, `chunk_id`, `relevance_score`, `page_number` (PDF) or `start_timestamp`/`end_timestamp` (video), `section_heading`.

### `POST /api/v1/query/stream[?draft=1]`
Same body. NDJSON response: `delta` events, then exactly one `done` (same body as `/api/v1/query`) or `error`. With `?draft=1`, unverified `draft` events come first.

### Sessions
| Method | Route | Purpose |
|---|---|---|
| POST | `/api/v1/sessions/{id}/seed` | Restore an expired session from saved history `{"turns": [{role, content}]}` → `{session_id, seeded, turn_count}`; **409** if it already exists (never overwrites) |
| DELETE | `/api/v1/sessions/{id}` | `{"deleted": true}` |
| GET | `/api/v1/sessions/{id}/history` | 200 if it exists for this workspace, otherwise 404 |

### `GET /healthz`
Liveness probe (no authentication). In production mode, it and the routes above are the **only** reachable paths. Everything else returns 404 and the API docs pages are disabled.
