# 03 — Database Management Systems (DBMS)

| Item | Value |
|---|---|
| Date | 2026-11-22 |
| Subject | Database Management Systems |
| Relevance | Strong: three kinds of storage (document database, key-value store, vector database) plus a file-based registry |
| Main code | `team4c/models/*.ts`, `team4c/lib/requiredIndexes.ts`, `team4c/scripts/ensure-indexes.ts`, `team4c/lib/questionPersistence.ts`, `team4c/lib/processingRecovery.ts`, `team4c/lib/mongodb.ts`, `team4c/app/api/workspaces/[id]/route.ts`, `app/services/conversation.py`, `app/services/ingest_store.py`, `app/services/vector_store.py` |
| Build | Final integrated build (local demo) |
| Owners | Team 4C application (MongoDB), Teams 4A/4B with Team 4C workspace scoping (Redis sessions, Qdrant), Team 4C integration layer (ingest registry) |
| Status labels | Verified, Implemented, Not verified, Open, Not implemented (see [README](README.md)) |

---

## 1. Introduction

A DBMS stores data safely, lets many requests use it at the same time, and keeps it consistent when something fails. EduCopilot uses **four storage systems**, each chosen for a different job:

| Store | Used for | Owner |
|---|---|---|
| **MongoDB** (via Mongoose) | Users, workspaces, conversations, messages, files, revoked sessions: the system of record | Team 4C |
| **Redis** (FakeRedis in local mode) | Short-lived RAG conversation sessions with a TTL | Teams 4A/4B, with Team 4C workspace scoping |
| **Qdrant** (embedded in local mode) | Chunk vectors and their payload, for similarity search | Teams 4A/4B, with Team 4C workspace scoping |
| **JSON files** under `data/ingest/` | Ingestion jobs and per-workspace document generations | Team 4C (integration layer) |

The project uses no SQL database. Concepts such as indexing, uniqueness, idempotency, concurrency control, atomicity, durability and cascading deletes are still all present, implemented with the tools above.

## 2. Core concepts

| Concept | Where | Owner | Status |
|---|---|---|---|
| Document modelling and references | `team4c/models/` (User, Workspace, Conversation, Message, File, RevokedSession) | Team 4C | Implemented |
| Ownership chain | `assertOwnership` in `team4c/lib/ownership.ts` | Team 4C | Verified (Tasks 5, 21) |
| Unique, compound, sparse, partial and TTL indexes | `team4c/lib/requiredIndexes.ts`, `team4c/models/File.ts`, `Message.ts`, `RevokedSession.ts` | Team 4C | Implemented; live database **Not verified** in Task 21 |
| Index management | `team4c/scripts/ensure-indexes.ts` (`npm run db:indexes[:check]`) | Team 4C | Verified on the isolated test database (Task 21) |
| Idempotency and duplicate keys (E11000) | `beginQuestionAttempt` in `team4c/lib/questionPersistence.ts`; upload dedupe | Team 4C | Verified (Tasks 13, 19) |
| Compare-and-set writes | Conditional `updateOne` filters in `questionPersistence.ts`, `processingRecovery.ts` | Team 4C | Verified (Task 19); Implemented (Task 18) |
| Leases and fencing tokens | `generationAttemptId`, `generationLeaseExpiresAt`; File processing lease | Team 4C | Verified (Task 19); Implemented (Task 18) |
| Optimistic locking (`WATCH`/`MULTI`/`EXEC`), `SET NX` | `ConversationManager.append_turn`, `create_tenant_session`, `seed_tenant_session` | Teams 4A/4B, with Team 4C workspace scoping | Implemented |
| Atomic, durable file writes | `IngestStore._atomic_write` (fsync + `os.replace`), `recover()` | Team 4C (integration layer) | Implemented |
| Versioning by generations | `IngestStore.activate`, `RetrievalScope.allows`, `tenant_filter` | Team 4C (integration layer) | Implemented |
| Cascade deletion | `DELETE /api/workspaces/[id]` | Team 4C | Verified (Task 20/21) |
| Key-value TTL | Redis `SET … EX session_ttl_seconds` (1800 s) | Team 4B | Implemented |
| Vector database payload filtering | `VectorStoreManager.tenant_filter` (`Filter`, `FieldCondition`, `MatchValue`, `MatchAny`) | Teams 4A/4B, with Team 4C workspace scoping | Verified (workspace isolation, Task 5) |
| Connection caching | `connectToDatabase` in `team4c/lib/mongodb.ts` | Team 4C | Implemented |

## 3. MongoDB: data model and relationships (Team 4C)

### 3.1 Collections and references

```
users ──< workspaces ──< conversations ──< messages
                    └──< files
revokedsessions (independent; TTL)
```

| Model | Key fields (examples) | Reference |
|---|---|---|
| `User` | `email` (unique), `passwordHash` | — |
| `Workspace` | `userId`, `name` | `userId → User` |
| `Conversation` | `workspaceId`, `title`, `ragSessionId` (unique, sparse), source scope | `workspaceId → Workspace` |
| `Message` | `conversationId`, `role`, `content`, `clientMessageId`, `generationState`, `partialAnswer`, `replyTo`, citations | `conversationId → Conversation`, `replyTo → Message` |
| `File` | `workspaceId`, `userId`, `status` (`uploading`, `processing`, `ready`, `failed`), `contentSha256`, `youtubeVideoId`, `uploadIdempotencyKey` | `workspaceId → Workspace` |
| `RevokedSession` | `_id` (the session's `sid` string), `expiresAt` | — |

The model uses **references** (ids stored in child documents), not embedded arrays. A conversation can have many messages and a workspace many files, so embedding them would make one document grow without limit.

### 3.2 Ownership chain

Every data route loads the parent chain and checks the owner:

```
Workspace.userId  →  Conversation.workspaceId  →  Message.conversationId
                  →  File.workspaceId
```

`assertOwnership(workspaceId, userId)` in `team4c/lib/ownership.ts` throws `OwnershipError` when the id is malformed, the workspace does not exist, or it belongs to someone else. All three cases return the **same 404**, so another user cannot tell "exists but not yours" from "does not exist". This is authorisation at the data layer (see [08 Information Security](08_Information_Security.md)).

### 3.3 Indexes

`team4c/lib/requiredIndexes.ts` lists the 12 indexes the application depends on:

| Collection | Index name | Keys | Type | Purpose |
|---|---|---|---|---|
| users | `email_1` | `email` | Unique | One account per email |
| workspaces | `userId_1` | `userId` | Normal | List a user's workspaces |
| conversations | `workspaceId_1` | `workspaceId` | Normal | Workspace queries and deletes |
| conversations | `ragSessionId_1` | `ragSessionId` | Unique + **sparse** | A RAG session belongs to one conversation; old conversations without the field are ignored |
| messages | `conversationId_1` | `conversationId` | Normal | History and cascade deletes |
| messages | `conversation_client_message_unique` | `conversationId, clientMessageId` | **Compound**, unique, **partial** | A question is stored exactly once |
| files | `workspaceId_1` | `workspaceId` | Normal | Workspace queries |
| files | `userId_1` | `userId` | Normal | Owner lookups |
| files | `uploadIdempotencyKey_1` | `uploadIdempotencyKey` | Unique + sparse | A retried upload reuses one File |
| files | `workspace_content_sha256_unique` | `workspaceId, contentSha256` | Compound, unique, partial | No duplicate PDF per workspace |
| files | `workspace_youtube_video_id_unique` | `workspaceId, youtubeVideoId` | Compound, unique, partial | No duplicate YouTube video per workspace |
| revokedsessions | `expiresAt_1` | `expiresAt` | **TTL** (`expireAfterSeconds: 0`) | MongoDB deletes expired revocations automatically |

**Sparse vs partial:** a sparse index skips documents that do not have the field at all. A partial index uses a filter, here `{ contentSha256: { $type: "string" } }`, so it applies only to documents where the field is a string. Both allow older records without the field to coexist with a unique rule for new records.

**Compound index:** `(workspaceId, contentSha256)` makes the pair unique, not each field alone. The same PDF can exist in two different workspaces, but only once in each.

**TTL index:** with `expireAfterSeconds: 0`, MongoDB's background task deletes each document once its `expiresAt` time has passed. Revocations are stored until the token's expiry plus a one-hour margin (`REVOCATION_RETENTION_MARGIN_SECONDS` in `team4c/lib/authCallbacks.ts`), and then disappear by themselves.

### 3.4 Index management

`team4c/scripts/ensure-indexes.ts` compares the required list with what exists (`assessIndex` in `requiredIndexes.ts`):

- **missing** → can be created with `npm run db:indexes`;
- **compatible** → nothing to do;
- **incompatible** (same key with different options, or same name with a different key) → **reported, never dropped**. Dropping a unique index on a live database could allow duplicates, so a human decides.

`npm run db:indexes:check` reported 12/12 on the isolated test database in Task 21. The live database was **not** checked in Task 21 (status: Not verified).

### 3.5 Idempotency and duplicate-key handling

A network retry or double-click must not store a question twice.

1. The browser gives each message an id. The server stores it as `clientMessageId`.
2. The compound unique index `conversation_client_message_unique` allows one row per `(conversationId, clientMessageId)`.
3. If two requests insert at the same time, MongoDB accepts one and rejects the other with **error code 11000** (duplicate key). The code detects that code and **reuses the winner** instead of failing.
4. A retry with the same id finds the stored question and reuses its stored text, so a retry always asks the original question.

The same pattern prevents duplicate uploads (`contentSha256`, `youtubeVideoId`, `uploadIdempotencyKey`).

### 3.6 Compare-and-set writes, leases and fencing

MongoDB updates a **single document** atomically. The project relies on this instead of multi-document transactions.

**Compare-and-set:** an update includes the expected current state in its filter. If the state has changed, the filter matches nothing and the update does nothing.

```ts
// team4c/lib/questionPersistence.ts (abridged)
ownedFilter() {
  return { _id: this.questionId, generationAttemptId: this.attemptId, generationState: "generating" };
}
// every terminal write:
await MessageModel.updateOne(this.ownedFilter(), { $set: { generationState: "answered" } });
```

**Lease:** an attempt to answer a question writes `generationLeaseExpiresAt` (2 minutes ahead) and renews it every 30 seconds while the request is alive (`GENERATION_LEASE_TTL_MS`, `GENERATION_HEARTBEAT_MS`). If the server dies, renewal stops, the lease expires, and the question becomes retryable.

**Fencing token:** `generationAttemptId` is a fresh random UUID per attempt. A new attempt can claim the question only when the old lease has expired, and it writes its own id. When the old attempt wakes up and tries to write, its filter still contains the **old** id and matches nothing, so a stale writer cannot overwrite newer data.

**File processing (Task 18):** the same pattern protects ingestion (`team4c/lib/processingRecovery.ts`): the lease is 6 minutes (`LEASE_TTL_MS`), longer than the 5-minute backend deadline (`TEAM_A_INGEST_TIMEOUT_MS`), and renewed every 30 seconds. Recovery is a single `updateMany` whose filter matches only files in `uploading`/`processing` **and** with an expired lease, so it never touches a live attempt, a finished file or a deleted one. Records without a lease field are never matched (`$lt` does not match a missing field).

### 3.7 Cascade deletion

MongoDB has no foreign-key cascades, so `DELETE /api/workspaces/[id]` (`team4c/app/api/workspaces/[id]/route.ts`) does it in application code, in a safe order:

1. Check ownership (404 if not the owner).
2. Remove every file from **retrieval** first (`removeFromRetrieval` → backend `DELETE /v1/documents/{id}`). If that fails, nothing is deleted and the student can retry (502).
3. Delete stored file bytes, then `FileModel.deleteMany({ workspaceId })`.
4. `MessageModel.deleteMany({ conversationId: { $in: conversationIds } })`, then `ConversationModel.deleteMany({ workspaceId })`.
5. Delete the workspace.
6. Best effort: end each conversation's backend RAG session (`Promise.allSettled`; failures are logged, not fatal).

Without a transaction, a crash between steps can leave orphans (for example, messages whose workspace is already gone). Step 2 comes first on purpose: the worst outcome is leftover private records, never deleted records whose content is still searchable.

### 3.8 Connection caching

`connectToDatabase()` in `team4c/lib/mongodb.ts` stores the connection and the in-flight connection promise on `globalThis`. Every route reuses one Mongoose connection (which has its own driver connection pool) instead of opening a new one per request. A failed attempt resets the promise so the next call retries. `serverSelectionTimeoutMS: 5000` makes an unreachable database fail in about 5 seconds instead of about 30.

## 4. Redis: sessions with TTL and optimistic locking (Teams 4A/4B, with Team 4C workspace scoping)

The backend keeps the recent turns of each RAG conversation in Redis (FakeRedis in local mode, created in `create_app` in `app/main.py`).

| Operation | Redis feature | Why |
|---|---|---|
| Key layout | `tenant_session:{workspace_id}:{session_id}` | The workspace is part of the key, so one workspace cannot read another's session |
| Create | `SET key value EX ttl NX` (`create_tenant_session`) | `NX` = only if it does not exist, so a session is never overwritten |
| Restore | `SET … NX` (`seed_tenant_session`) | Re-seeds a missing session from MongoDB history, never overwrites an existing one |
| Append a turn | `WATCH key` → `GET` → modify → `MULTI` → `SET … EX` → `EXEC`, up to 3 tries (`append_turn`) | **Optimistic locking**: if another request changed the key after `WATCH`, `EXEC` fails with `WatchError` and the code retries |
| Expiry | `EX session_ttl_seconds` (default 1800 s) | Idle sessions disappear; MongoDB remains the permanent history |

**Optimistic vs pessimistic locking:** `WATCH` does not block anyone. It detects a conflict at commit time and retries. That suits sessions, where conflicts are rare.

## 5. Ingest registry: atomic files and generations (Team 4C integration layer)

`IngestStore` (`app/services/ingest_store.py`) keeps ingestion state as JSON files:

```
data/ingest/jobs/<job_id>.json                    one record per job
data/ingest/registry/<sha256(workspace_id)>.json  per-workspace document state
data/ingest/spool/<job_id>.bin                    fetched source bytes
```

### 5.1 Atomic and durable writes

`_atomic_write` writes a new temporary file (exclusive create), flushes, calls **`os.fsync`**, then **`os.replace`** onto the real name. `os.replace` is atomic on the same file system, so after a crash the file is either the complete old version or the complete new version, never half-written. `recover()` removes leftover temp files, re-queues or fails interrupted jobs, and repairs a registry if a crash fell between writing a job and writing its registry entry. A re-entrant lock serialises every read-modify-write inside the process.

### 5.2 Document generations (versioning)

Each time a document is (re)ingested, it gets a new, strictly increasing **generation** number that is never reused, even after deletion or a restart.

1. `create_job` assigns generation `g`.
2. Chunks are written to Qdrant tagged with `generation = g`.
3. `activate(workspace, document, g)` makes `g` the document's **only** citable generation. It refuses if `g` was deleted or a newer generation is already active.
4. Older generations' chunks are cleaned up afterwards (`cleanup_pending`, `cleanup_done`).

Readers take a snapshot with `active_generations(workspace)` and put it in the `RetrievalScope`. `tenant_filter` turns it into a Qdrant filter: a chunk is returned only if its generation equals its document's active generation. A half-finished re-ingestion is therefore **never visible**, and the previous version stays citable until the new one is complete. The idea is close to multi-version concurrency control (MVCC): writers create a new version while readers keep seeing the committed one.

`mark_deleted` makes a document non-citable immediately (`active_generation = None`, `deleted_through = last_generation`) and schedules chunk deletion.

## 6. Qdrant: vector database and payload filtering (Teams 4A/4B, with Team 4C workspace scoping)

- Each point stores a **vector** and a **payload**: `workspace_id`, `document_id`, `chunk_id`, `text`, `generation`, `index` and source metadata (page or timestamps).
- `tenant_filter(scope)` builds the filter from typed objects (`Filter`, `FieldCondition`, `MatchValue`, `MatchAny`, `IsEmptyCondition`). No filter is built by joining strings, so user text cannot change the query's meaning (the vector-database equivalent of preventing SQL injection).
- `_validate_chunk` rejects oversized text or malformed metadata **before** any write. Batch writes are capped at 1,000 points.
- Collection names include a hash of the embedding model and chunk profile plus the vector size, so incompatible vectors never share a collection.

## 7. Alternatives and design trade-offs

| Decision | Alternative | Trade-off |
|---|---|---|
| MongoDB documents with references | A relational schema with joins | Flexible schema and simple single-document atomic updates; integrity (cascades, references) must be enforced in code |
| Single-document compare-and-set + leases | Multi-document transactions | Works without a replica set and avoids long transactions; multi-step operations (cascade delete) are not atomic |
| Optimistic locking in Redis | Pessimistic locks (`SETNX` lock keys) | No blocking; retries under contention (max 3, then the turn is reported unavailable) |
| JSON files with fsync + rename | A database table for jobs | No extra service; single-process only, scans directories on recovery |
| Generations + activation | Delete old chunks, then write new ones | Never shows a half-indexed document; needs clean-up of old generations |
| TTL index for revocations | A scheduled clean-up job | MongoDB does the clean-up; deletion timing is approximate (background task) |
| Report incompatible indexes | Auto-drop and recreate | Safe for live data; needs a manual step |

## 8. Limitations and concepts not implemented

| Item | Status |
|---|---|
| SQL, joins, normalisation to 3NF/BCNF | **Not implemented** (no SQL database; embedded Qdrant uses SQLite internally, but the project never writes SQL) |
| Multi-document MongoDB transactions | **Not implemented** (cascade delete is a sequence of operations) |
| Foreign-key constraints | **Not implemented** (enforced in application code) |
| Two separate histories (MongoDB and the backend session) can differ after a cancel or crash | **Open**, shared between the teams (T4AB-03) |
| Live database index check | **Not verified** in Task 21 |
| Compound index for the sidebar sort `(workspaceId, updatedAt, _id)` | **Not implemented** (see [01 DSA §6](01_Data_Structures_and_Algorithms.md#6-limitations-and-concepts-not-implemented)) |
| Encryption at rest for MongoDB, Redis or Qdrant | **Not implemented** in the project code (depends on hosting; see [08 Information Security](08_Information_Security.md)) |
| Database replication, sharding, backups | **Not implemented** (single-node demo; production prerequisites are listed as unverified in [Deployment](../guides/DEPLOYMENT.md#2-what-a-real-production-deployment-would-require)) |
| Ingest registry and embedded Qdrant support multiple processes | **Not implemented** (single process only) |

## 9. Interview questions

**Q1. Why MongoDB instead of a relational database?**
The original architecture plan (`team4c/docs/decisions.md` in the project source) places all structured metadata in MongoDB Atlas through Mongoose. The document does not record a detailed comparison with SQL databases, so the reasons below are the properties the code actually relies on. The data is a clear ownership tree (user → workspace → conversation → message), which fits documents with references. Single-document atomic updates are enough for the compare-and-set and lease logic. The trade-off is that cascades and integrity checks live in application code, and there are no joins or multi-document transactions in the current code.

**Q2. How do you guarantee a question is stored only once?**
A compound unique partial index on `(conversationId, clientMessageId)`. The browser's message id is the idempotency key. If two inserts race, one fails with duplicate-key error 11000. The code catches it and reuses the stored question.

**Q3. What is the difference between a sparse and a partial index? Where is each used?**
Sparse skips documents that do not have the field. Partial uses a filter expression. `ragSessionId_1` and `uploadIdempotencyKey_1` are unique + sparse. The content-hash, YouTube and client-message indexes are unique + partial with `{$type: "string"}`. Both let old records without the field coexist with uniqueness for new ones.

**Q4. What is a fencing token, and why is it needed with a lease?**
A lease alone does not stop a slow old worker that wakes up after its lease expired. The fencing token, `generationAttemptId`, is a new UUID per attempt, and every write includes it in the filter. When a newer attempt takes over, the old attempt's writes no longer match and change nothing.

**Q5. How does Redis `WATCH`/`MULTI`/`EXEC` prevent lost updates?**
`append_turn` watches the session key, reads it, adds the turn, and commits in `MULTI`/`EXEC`. If another request changed the key in between, `EXEC` fails with `WatchError` and the code retries (up to 3 times). Without it, two simultaneous turns could each read the old list, and one turn would be lost.

**Q6. How is the ingest registry crash-safe without a database?**
Each write goes to a new temp file, which is flushed and fsynced, then atomically renamed over the target with `os.replace`. A crash leaves either the old file or the new one. `recover()` removes temp files and repairs job/registry mismatches on startup.

**Q7. What are document generations, and what problem do they solve?**
Each re-ingestion gets a new, increasing generation. Chunks are tagged with it, and only the activated generation is searchable. While a new version is being indexed, students keep seeing the old one. A failed re-ingestion never exposes partial chunks.

**Q8. How does workspace deletion work without transactions?**
In a careful order: remove documents from retrieval first (abort on failure), then file bytes, files, messages, conversations, the workspace, and finally best-effort RAG session deletion. A crash midway can leave orphaned private records, but never searchable content whose records were deleted.

**Q9. How are expired revocations cleaned up?**
A TTL index on `revokedsessions.expiresAt` with `expireAfterSeconds: 0`. Each record expires one hour after the token it revokes would have expired. MongoDB's background task deletes it.

**Q10. How do you prevent injection in vector database queries?**
Filters are built only from `qdrant-client` typed objects (`Filter`, `FieldCondition`, `MatchValue`, `MatchAny`), never by joining strings. The workspace id comes from the verified token and is checked against a strict pattern.

**Q11. Why cache the MongoDB connection on `globalThis`?**
In development, Next.js reloads modules, and serverless-style route handlers run often. Without caching, each reload or request could open a new connection and exhaust the server's connection limit. The cache keeps one connection (with the driver's pool) and retries after a failure.

**Q12. What is a known consistency limitation?**
MongoDB and the backend session store keep two separate histories. The backend saves a turn before Next.js finishes persisting the answer, and restoration only re-seeds a missing session. After a cancel or crash the two can differ until the backend session expires (T4AB-03, shared between the teams). See [Chat and streaming §6](../technical/CHAT_AND_STREAMING.md#6-two-conversation-histories).

## 10. References

- [Database design](../technical/DATABASE_DESIGN.md): every collection, field and the 12 indexes
- [File ingestion](../technical/FILE_INGESTION.md): idempotency, retry and recovery of stuck files
- [Chat and streaming](../technical/CHAT_AND_STREAMING.md): message persistence and the two histories
- [Known limitations](../../KNOWN_LIMITATIONS.md)
- Internal verification records (not published): processing recovery (Task 18), question persistence (Task 19), YouTube duplicate prevention (Task 13), final regression and index check (Task 21), history divergence finding (T4AB-03)
- Related subjects: [01 DSA](01_Data_Structures_and_Algorithms.md), [04 OS](04_Operating_Systems.md)
