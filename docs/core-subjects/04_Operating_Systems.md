# 04 — Operating Systems (OS)

| Item | Value |
|---|---|
| Date | 2026-11-22 |
| Subject | Operating Systems: concurrency, synchronisation, processes, file systems and resource limits |
| Relevance | Strong: the backend is an async server that also uses threads, locks, semaphores, subprocesses and durable files |
| Main code | `app/services/local_qdrant.py`, `app/core/auth.py`, `app/services/ingest_store.py`, `app/services/ollama.py`, `app/services/hybrid_retriever.py`, `app/api/ingest_v1.py`, `app/services/source_fetch.py`, `app/main.py`, `team4c/lib/processingRecovery.ts`, `team4c/lib/questionPersistence.ts`, `team4c/lib/ingestion.ts` |
| Build | Final integrated build (local demo) |
| Owners | Team 4C integration layer (locks, ingest store, fetcher), Team 4B (Ollama client, retrieval), Team 4C application (leases and deadlines) |
| Status labels | Verified, Implemented, Not verified, Open, Not implemented (see [README](README.md)) |

---

## 1. Introduction

Operating-systems ideas appear wherever a program has to share resources safely: several requests touching the same data at once, slow work that must not block everything else, crashes in the middle of a write, and limited CPU and memory.

The EduCopilot backend is a **FastAPI** application running on one **asyncio event loop**. Some libraries it uses (embedded Qdrant, Redis client calls, file I/O) are **blocking**, so they run in a **thread pool**. That mix creates real OS problems, and the code solves them with the classic tools: locks, semaphores, timeouts, cancellation, leases, `fsync` and atomic rename.

The project does not implement OS internals such as a scheduler, virtual memory or a file system. It **uses** operating-system services correctly in application code.

## 2. Core concepts

| Concept | Where | Owner | Status |
|---|---|---|---|
| Mutual exclusion (locks) | `SerializedQdrantClient` (`threading.RLock`), `ReplayCache` (`threading.Lock`), `IngestStore` (`threading.RLock`), `OllamaChat` (`asyncio.Lock`) | `SerializedQdrantClient`: Integration layer (individual ownership not explicitly specified); `ReplayCache`, `IngestStore`: Team 4C (integration layer); `OllamaChat`: Team 4B | Implemented; the Qdrant race fix was reproduced and fixed during integration (documented in `local_qdrant.py`) |
| RLock vs Lock | `SerializedQdrantClient`, `IngestStore` use `RLock`; `ReplayCache` uses `Lock` | `SerializedQdrantClient`: Integration layer (individual ownership not explicitly specified); `IngestStore`, `ReplayCache`: Team 4C (integration layer) | Implemented |
| Asyncio event loop | All FastAPI routes; `async def` handlers | Teams 4A/4B; Team 4C (integration layer) | Implemented |
| Thread pool | `run_in_threadpool` in `app/api/canonical_query.py`, `app/api/ingest_v1.py`, `app/services/hybrid_retriever.py`, `app/main.py` | Teams 4A/4B; Team 4C (integration layer) | Implemented |
| Concurrent tasks | `asyncio.gather(semantic(), keyword())` in `HybridRetriever._rank` | Team 4B | Implemented |
| Semaphore | `_semaphore(state)` in `app/api/ingest_v1.py` (`ingest_fetch_concurrency`, default 2) | Team 4C (integration layer) | Implemented |
| Timeouts and deadlines | `OllamaChat.stream_messages` (one deadline for lock wait + every chunk), `asyncio.timeout` in `fetch_to_spool`, 5-minute ingest deadline in `team4c/lib/ingestion.ts` | Team 4B / Team 4C (integration layer and application) | Implemented |
| Cancellation | `AbortController` / `request.signal` (frontend), `asyncio.CancelledError` (Ollama client), Stop generation | Team 4C / Team 4B | Verified (Stop generation, Task 12) |
| Leases and heartbeats | `processingRecovery.ts` (6 min / 30 s), `questionPersistence.ts` (2 min / 30 s) | Team 4C | Implemented (Task 18); Verified (Task 19) |
| File-system durability | `IngestStore._atomic_write`, `fetch_to_spool` (`O_EXCL`, `fsync`, `os.replace` / `os.rename`) | Team 4C (integration layer) | Implemented |
| Subprocess management | `OllamaChat.prepare` / `close` (`subprocess.Popen`, `terminate`, `wait`, `kill`) | Team 4B | Implemented |
| Single-process constraint | Embedded Qdrant file lock; in-process locks, rate limits and replay cache | Teams 4A/4B; Team 4C | **Open** design limit (T4AB-04) |
| Memory bounds | Corpus cap, batch cap, replay-cache capacity, rate-limiter key cap, history cap, streamed hashing | All | Implemented |

## 3. Project implementation, step by step

### 3.1 Mutual exclusion: the embedded Qdrant race

**Problem.** In local mode the backend runs Qdrant *inside* its own process (`QdrantClient(path="data/qdrant")`), backed by a SQLite file and in-memory arrays. That client is not thread-safe. FastAPI runs the synchronous vector-store calls in a thread pool, so two requests at once (two parallel document deletes, or a query during an upsert) reached it from different threads.

**Observed result** (recorded in the docstring of `app/services/local_qdrant.py`): a `DELETE /v1/documents` failed with `sqlite3.OperationalError`, and a sandbox reproduction made 7 of 8 parallel deletes fail while the in-memory index had already dropped the points. The SQLite file and memory disagreed, so deleted chunks could come back after a restart.

**Fix.** `SerializedQdrantClient` wraps the client so that **every method call holds one process-wide lock**. This is a critical section: only one thread at a time can be inside the client. `create_app` in `app/main.py` applies it only to the embedded client. A real Qdrant server (`QDRANT_URL`) handles its own concurrency and is not wrapped. A test covers this (`tests/test_concurrent_vector_writes.py`).

### 3.2 RLock vs Lock

| | `threading.Lock` | `threading.RLock` (re-entrant) |
|---|---|---|
| Same thread acquires twice | **Deadlocks** (it waits for itself) | Allowed; a counter tracks depth |
| Used in | `ReplayCache.use_once` | `SerializedQdrantClient`, `IngestStore` |
| Why | A short, flat critical section that never calls back into itself | Methods may call other locked methods of the same object |

In the current `IngestStore`, each public method (`create_job`, `complete`, `activate`, `recover`, …) takes the lock, and the private helpers it calls (`_load_registry`, `_write_job`, `_save_document`) do not. An `RLock` is a safety margin: if one locked method is ever changed to call another locked method, the same thread can enter again instead of deadlocking itself. In `SerializedQdrantClient`, a wrapped call might end up calling back through the proxy on the same thread. With a plain `Lock` that second acquisition would block forever, and the `RLock` makes it safe.

### 3.3 Event loop and thread pool

FastAPI runs `async def` handlers on one event loop thread. The loop can switch between many requests while each is **waiting** (for the network, Ollama or a timer). If a handler calls something **blocking** directly (for example a SQLite-backed Qdrant search or a synchronous Redis call), the whole loop stops and every other request waits.

The project moves blocking calls off the loop:

```python
# app/api/canonical_query.py (abridged)
generations = await run_in_threadpool(_active_generations, state, workspace)
history = await run_in_threadpool(state.conversations.create_tenant_session, workspace, body.session_id)
```

`run_in_threadpool` (from Starlette) runs the function in a worker thread and lets the loop continue. That is exactly why the Qdrant lock in §3.1 was needed: the thread pool creates real parallelism between threads.

Python's Global Interpreter Lock (GIL) lets only one thread run Python bytecode at a time, but threads still interleave between bytecodes, and native code such as SQLite can release the GIL. Shared objects therefore still need locks.

### 3.4 Concurrent tasks with `asyncio.gather`

In hybrid search, the vector search (which waits for the embedding model and Qdrant) and the BM25 search (CPU work in the thread pool) are independent:

```python
# app/services/hybrid_retriever.py
ranked = reciprocal_rank_fusion(await asyncio.gather(semantic(), keyword()))
```

`asyncio.gather` starts both coroutines and waits for both. The total time is roughly the slower of the two instead of their sum. If one fails, `gather` raises its exception.

### 3.5 Semaphore: limiting concurrent ingestion

Ingestion downloads a file, extracts text, embeds every chunk and writes vectors. It is heavy on CPU, memory and the embedding model. `_semaphore(state)` in `app/api/ingest_v1.py` creates one `asyncio.Semaphore(ingest_fetch_concurrency)` (default **2**, maximum 4) and wraps each ingestion run:

```python
async with _semaphore(state):
    chunks_indexed = await _run(state, store, job, body, spool)   # or _run_youtube(...)
```

A semaphore is a counter. At most two ingestions run at once, and the third waits until one finishes. A mutex is a semaphore with a count of 1. Separately, the ingest store refuses new jobs once `ingest_queue_max` (default 20) are open (`QueueFull` → HTTP 429).

### 3.6 Model access: an async lock plus a deadline

A local LLM on a CPU handles one generation at a time efficiently. `OllamaChat` (`app/services/ollama.py`) serialises model calls with an **`asyncio.Lock`**: an async lock suspends the waiting coroutine instead of blocking a thread.

`stream_messages` uses **one deadline** for the whole operation:

1. `deadline = loop.time() + timeout`.
2. Waiting for the lock: `asyncio.wait_for(self.lock.acquire(), timeout=remaining())`.
3. Each streamed line: `asyncio.wait_for(lines.__anext__(), timeout=remaining())`.
4. On timeout or error the HTTP stream is closed and the lock is released in `finally`.

Time spent in the queue counts against the same deadline, so a request never waits forever behind a long one, and a stuck stream cannot hold the lock indefinitely.

### 3.7 Timeouts and cancellation elsewhere

| Where | Mechanism |
|---|---|
| Backend PDF download (`fetch_to_spool`) | `async with asyncio.timeout(total)` plus `httpx.Timeout(total, connect=…)` |
| Next.js → backend ingestion (`team4c/lib/ingestion.ts`) | `AbortController` with a `setTimeout` of `TEAM_A_INGEST_TIMEOUT_MS` (5 minutes) that aborts the request |
| Next.js → backend query (`team4c/services/teamB/client.ts`) | The browser request's `request.signal` is passed to `fetch()`, so closing the tab or pressing Stop cancels the backend call |
| Ollama start-up task (`OllamaChat.close`) | `self.task.cancel()` then `asyncio.gather(self.task, return_exceptions=True)`; `prepare()` handles `asyncio.CancelledError` |

Cancellation in asyncio raises `CancelledError` **inside** the task at its next `await`, so `finally` blocks still run and locks are released. Stop generation was verified end to end in Task 12.

### 3.8 Leases and heartbeats (failure detection)

A process cannot announce its own crash. EduCopilot uses **leases**: a time-limited claim that the owner must keep renewing.

| Lease | TTL | Heartbeat | Protects |
|---|---|---|---|
| File processing (`team4c/lib/processingRecovery.ts`) | 6 min (`LEASE_TTL_MS`) | 30 s (`HEARTBEAT_INTERVAL_MS`, `setInterval`) | A file stuck in "processing" after a restart is recovered to "failed" |
| Question generation (`team4c/lib/questionPersistence.ts`) | 2 min (`GENERATION_LEASE_TTL_MS`) | 30 s (`GENERATION_HEARTBEAT_MS`) | A question whose server died mid-answer becomes retryable |

**Why the file lease (6 min) is longer than the ingest deadline (5 min):** the request is aborted at 5 minutes. By the time a lease can expire (at least 6 minutes after the last renewal), the old attempt's request has certainly stopped. A recovery or retry can then never run in parallel with a still-working old attempt. The 1-minute difference is `FENCE_MARGIN_MS`. Fencing with an attempt id (see [03 DBMS §3.6](03_Database_Management_Systems.md#36-compare-and-set-writes-leases-and-fencing)) covers the remaining edge cases.

### 3.9 File-system durability

The OS keeps written data in memory (the page cache) and writes it to disk later. A power cut can lose it, and a crash during a write can leave a half-written file.

`IngestStore._atomic_write` and `fetch_to_spool` use the standard safe sequence:

1. **Exclusive create** of a new temp file: `os.open(temp, O_WRONLY | O_CREAT | O_EXCL, 0o600)`. `O_EXCL` fails if the file already exists, and `0o600` makes it readable only by the owner.
2. Write and `flush()` (Python buffer → OS).
3. **`os.fsync(fd)`** (OS cache → disk).
4. **`os.replace(temp, target)`** (atomic rename over the target). `fetch_to_spool` uses `os.rename`, which on Windows refuses to overwrite, so an existing spool file is never replaced.
5. On any failure the temp file is deleted. `recover()` removes leftovers after a crash.

`_replace` retries `os.replace` up to five times with a short sleep, because on Windows a virus scanner can briefly hold the target file open.

### 3.10 Subprocess management

When Ollama is not running locally and auto-start is enabled, `OllamaChat.prepare` starts it as a child process:

```python
self.process = subprocess.Popen([executable, 'serve'], env=env, stdin=subprocess.DEVNULL,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, ...)
```

It then polls Ollama's `/api/tags` until ready or until `ollama_startup_timeout_seconds` passes. On shutdown, `close()` sends `terminate()` (a polite stop), waits up to 5 seconds using `asyncio.to_thread(self.process.wait, …)` so the event loop is not blocked, and calls `kill()` if the process has not exited. This is the classic graceful-then-forced shutdown, which avoids leaving orphan processes.

### 3.11 Single-process constraint

Several components assume **one backend process**:

- Embedded Qdrant takes a lock on its storage folder. A second process using the same folder fails ("already accessed by another instance"). This is why running pytest next to the demo backend causes errors (T4AB-04).
- The in-process locks, the replay cache, the frontend rate limiters and the in-memory revocation cache exist per process.
- The `.env.example` comment for `QDRANT_LOCAL_PATH` says to use only one app worker.

Scaling out would need a Qdrant server, a shared Redis, a shared replay cache and a shared rate-limit store. Horizontal scaling is listed as **not supported** in [Known limitations §1](../../KNOWN_LIMITATIONS.md#1-deployment-status).

### 3.12 Memory bounds

| Bound | Where | Default |
|---|---|---|
| Chunks loaded for one query | `retrieval_corpus_cap` (`HybridRetriever`, `tenant_corpus`) | 10,000 |
| Points per batch write | `upsert_tenant_batch` (`islice(chunks, cap + 1)`) | 1,000 |
| Replay cache entries | `ReplayCache` | 100,000 |
| Rate-limiter keys per limiter | `createRateLimiter` | 10,000 |
| In-memory revocations | `team4c/lib/sessionRevocation.ts` | 50,000 |
| Session turns | `conversation_max_turns` + summary cap | 6 turns, 2,000 characters |
| File hashing and downloads | Streamed in blocks (1 MB in `_sha256_file`); size checked while streaming | PDF fetch limit `media_max_bytes` (25 MiB default) |

`islice(chunks, cap + 1)` reads at most one item more than the cap. If the caller sends a huge iterator, the server never materialises it all.

## 4. Alternatives and design trade-offs

| Decision | Alternative | Trade-off |
|---|---|---|
| One lock around embedded Qdrant | A Qdrant server | No extra service for the demo; every vector call is serialised |
| `asyncio.Lock` for the model | Let Ollama queue requests itself | A predictable single queue with one deadline; no parallel generations |
| Thread pool for blocking libraries | Async-native drivers everywhere | Works with existing sync libraries; needs locks for shared state |
| Semaphore of 2 for ingestion | Unlimited, or a separate worker process | Protects CPU and memory; a third upload waits |
| Leases with heartbeats | Status flags only | Distinguishes "slow" from "dead"; more writes (every 30 s) |
| fsync on every registry write | Rely on the OS cache | Crash-safe; slower writes (acceptable for small JSON files) |
| Auto-start Ollama as a child process | Require a pre-started server | Easier local demo; the backend must manage another process's lifecycle |

## 5. Limitations and concepts not implemented

| Item | Status |
|---|---|
| CPU scheduling algorithms, paging, virtual memory, kernel or driver code | **Not implemented** (the project only uses OS services) |
| Multiple backend processes or instances | **Not implemented** (single-process constraint, §3.11) |
| Tests colliding with a running backend on the Qdrant folder lock | **Open** (T4AB-04) |
| A revocation still queued in memory when the process stops is lost | **Open** (documented in `team4c/lib/sessionRevocation.ts`) |
| Live crash test of processing recovery | **Not verified** (Task 18: unit and race tests only) |
| Parallel LLM generations | **Not implemented** (serialised by design) |

## 6. Interview questions

**Q1. Why did the project need a lock around Qdrant if FastAPI is async?**
Async code runs on one thread, but blocking calls are sent to a thread pool with `run_in_threadpool`. Several threads then called the embedded, non-thread-safe Qdrant client at the same time, and parallel deletes failed and left memory and disk inconsistent. `SerializedQdrantClient` makes each call hold one `RLock`.

**Q2. What is the difference between `Lock` and `RLock`? Where is each used?**
A `Lock` deadlocks if the same thread acquires it twice. An `RLock` counts acquisitions by its owner. `IngestStore` and the Qdrant proxy use `RLock` so that a locked call which re-enters the same object on the same thread cannot deadlock. `ReplayCache` uses a plain `Lock` because its critical section is short and never re-enters.

**Q3. What happens if you call a blocking function directly inside an `async def` route?**
The event loop thread is blocked, so every other request stops until the call returns. The project uses `run_in_threadpool` for Qdrant, Redis and ingest-store calls.

**Q4. How does the project limit concurrent ingestion?**
An `asyncio.Semaphore` with `ingest_fetch_concurrency` permits (default 2) wraps each ingestion run. Extra requests wait. Separately, more than 20 open jobs (`ingest_queue_max`) are refused with 429.

**Q5. Why does the model lock's wait count against the request deadline?**
Otherwise a request could wait a long time for the lock and then get its full timeout again for generation. `stream_messages` computes one absolute deadline and uses the remaining time for the lock wait and for every chunk, so the total time is bounded.

**Q6. What is a lease, and why is the file-processing lease 6 minutes when the deadline is 5?**
A lease is a claim that expires unless renewed. A live request renews it every 30 seconds; a dead process stops. Making the lease longer than the 5-minute request deadline ensures the old request has been aborted before anyone can take over, so two attempts never run at once.

**Q7. How do you make a file write crash-safe?**
Write to a new temp file created with `O_EXCL`, flush, `fsync`, then `os.replace` over the target. Rename is atomic, so readers see the complete old file or the complete new one. Leftover temp files are removed on recovery.

**Q8. How does the backend shut down the Ollama child process?**
`terminate()`, then wait up to 5 seconds in a worker thread (`asyncio.to_thread`) so the loop is not blocked, then `kill()` if it is still running. The start-up task is cancelled and awaited first.

**Q9. How does cancellation flow when a student presses Stop?**
The browser aborts its `/api/chat` request. The route passes `request.signal` to the `fetch()` that streams from the backend, so that request is aborted too. Generation stops end to end, and the question is stored as "stopped" with any verified partial text (Tasks 12 and 19).

**Q10. Why can this backend not simply run four workers?**
Embedded Qdrant locks its storage folder for one process. The replay cache, locks and rate limits are per process, so with four workers a token could be replayed on another worker. Scaling out needs a Qdrant server and shared stores (for example Redis) first.

**Q11. How does the system bound memory against large or malicious input?**
Caps everywhere: corpus (10,000 chunks), batch writes (1,000, read with `islice` so a huge iterator is never fully loaded), replay cache (100,000), limiter keys (10,000), revocation cache (50,000), session turns, and streamed downloads with a byte limit checked while reading.

## 7. References

- [File ingestion §7](../technical/FILE_INGESTION.md#7-recovering-files-stuck-in-processing): recovering files stuck in "processing"
- [Chat and streaming](../technical/CHAT_AND_STREAMING.md): stop, failure and persistence states
- [Setup §5](../guides/SETUP.md#5-troubleshooting-from-project-experience): troubleshooting, including the Qdrant folder lock
- [Known limitations](../../KNOWN_LIMITATIONS.md)
- Internal verification records (not published): stop generation (Task 12), processing recovery (Task 18), question persistence (Task 19), test/Qdrant lock finding (T4AB-04)
- Related subjects: [03 DBMS](03_Database_Management_Systems.md), [07 COA](07_Computer_Organization_and_Architecture.md)
