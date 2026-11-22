# 01 — Data Structures and Algorithms (DSA)

| Item | Value |
|---|---|
| Date | 2026-11-22 |
| Subject | Data Structures and Algorithms |
| Relevance | Strong: retrieval ranking, chunking, hashing, queues, pagination and bounded caches |
| Main code | `app/services/bm25_index.py`, `app/services/hybrid_retriever.py`, `app/services/chunking.py`, `app/services/vector_store.py`, `app/core/auth.py`, `app/services/conversation.py`, `team4c/lib/rateLimit.ts`, `team4c/components/chat/OfflineQueue.ts`, `team4c/app/api/workspaces/[id]/conversations/route.ts` |
| Build | Final integrated build (local demo) |
| Owners | Team 4B (retrieval, ranking, conversation memory), Team 4A (chunking), Team 4C (integration layer: replay cache; application: rate limiter, offline queue, pagination) |
| Status labels | Verified, Implemented, Not verified, Open, Not implemented (see [README](README.md)) |

---

## 1. Introduction

EduCopilot answers a student's question using only the material in their workspace. To do that, it has to find the few most useful passages among thousands of chunks, quickly and fairly. That is a DSA problem: **ranking, merging ranked lists, splitting text, removing duplicates and keeping memory bounded**.

Most of the DSA work is in the backend retrieval pipeline. The frontend adds practical structures: a sliding-window rate limiter with LRU eviction, a FIFO offline queue and keyset pagination.

The project uses well-known algorithms and libraries (Okapi BM25 from `rank_bm25`, nearest-neighbour search inside Qdrant) and combines them with its own code. It does **not** implement its own trees, heaps, HNSW index or dynamic-programming algorithms.

## 2. Core concepts

| Concept | Data structure / algorithm | Where | Owner | Status |
|---|---|---|---|---|
| Keyword retrieval | Okapi BM25 over token lists | `app/services/bm25_index.py` `BM25Index` | Team 4B | Implemented |
| Vector similarity search | Nearest-neighbour search, cosine distance (index provided by Qdrant) | `VectorStoreManager.search_tenant` in `app/services/vector_store.py` | Teams 4A/4B, with Team 4C workspace scoping | Implemented |
| Rank merging | Reciprocal Rank Fusion with a hash map | `reciprocal_rank_fusion` in `app/services/hybrid_retriever.py` | Team 4B | Implemented |
| Hybrid retrieval | Concurrent keyword + vector search, fusion, threshold, top-k | `HybridRetriever.retrieve_scoped`, `HybridRetriever._rank` | Teams 4A/4B, with Team 4C workspace scoping | Verified (citations on grounded answers, Task 21); answer quality **Open** (T4AB-02) |
| Context expansion | Sliding window over chunk indexes | `HybridRetriever._rank` (`window_size`) | Team 4B | Implemented |
| Link traversal | One-hop graph expansion over Markdown links | `HybridRetriever._rank` (OKF block) | Team 4B | Implemented (older OKF data only, see §4.5) |
| Chunking | Line scanner + heading stack + greedy packing | `contextual_chunks`, `_blocks` in `app/services/chunking.py` | Team 4A | Implemented |
| Deduplication | SHA-256 content hash + unique index | `File.contentSha256`, `workspace_content_sha256_unique` | Team 4C | Verified (Tasks 8, 13) |
| Deterministic ids | `uuid5` over workspace id + chunk id | `VectorStoreManager.upsert_tenant_batch` | Teams 4A/4B, with Team 4C workspace scoping | Implemented |
| Rate limiting | Sliding window of timestamps in a `Map`, LRU eviction | `createRateLimiter` in `team4c/lib/rateLimit.ts` | Team 4C | Implemented |
| Offline messages | FIFO queue | `flushOfflineQueue` in `team4c/components/chat/OfflineQueue.ts` | Team 4C | Implemented |
| Pagination | Keyset (cursor) pagination, `limit + 1` | `GET /api/workspaces/[id]/conversations` | Team 4C | Verified (Task 16) |
| Replay protection | Bounded hash map of token ids with expiry | `ReplayCache` in `app/core/auth.py` | Team 4C (integration layer) | Verified (service-token interoperability test: second use rejected) |
| Bounded history | Fixed number of turns plus a capped rolling summary | `ConversationManager.summarize_if_needed` in `app/services/conversation.py` | Team 4B | Implemented |

## 3. Where it sits in the request flow

```
Question ──► /api/chat (Next.js) ──► POST /api/v1/query/stream (FastAPI)
                                        │
                                        ├─ RetrievalScope(workspace, document_ids, generations)
                                        ├─ HybridRetriever.retrieve_scoped
                                        │     ├─ semantic(): embed query → Qdrant nearest neighbours
                                        │     ├─ keyword():  BM25Index(searchable).search(query)
                                        │     ├─ reciprocal_rank_fusion([semantic, keyword])
                                        │     ├─ filter score ≥ threshold, take top_k
                                        │     └─ expand: neighbour window + one-hop links
                                        └─ LLM generation over the selected context
```

Code defaults (`app/core/config.py`, `_context` in `app/api/canonical_query.py`): `search_mode` = hybrid, `top_k` = 5, `score_threshold` = 0.5 (`SCORE_THRESHOLD_DEFAULT`), `window_size` = 3, and up to `top_k_max` = 50 candidates per search. Team 4C only sends `document_ids` (or `null` for the whole workspace) in `retrieval_config`, so these server-side values apply.

**Demo configuration differs:** the demo launcher used to run the integrated product sets `SCORE_THRESHOLD_DEFAULT=0.25`. The launcher script was kept outside the code repository. It overrides no other retrieval value. §4.3 explains what the two thresholds mean.

## 4. Project implementation, step by step

### 4.1 BM25 keyword retrieval

**What it is:** BM25 scores a document higher when it contains the query words often (term frequency), when those words are rare in the whole collection (inverse document frequency), and it corrects for document length.

**How the project does it (`BM25Index`):**

1. `tokenize(text)` lowercases with `casefold()` and extracts words with the regular expression `\w+`.
2. The constructor tokenises every chunk once and builds `BM25Okapi(self.tokens)` from the `rank_bm25` library.
3. `search(query, top_k)`:
   - computes a BM25 score for every chunk;
   - keeps only chunks that share **at least one word** with the query (set intersection). In very small collections, Okapi IDF can be zero or negative, so raw scores alone are not trusted;
   - sorts by `(-score, chunk_id)` so ties always break the same way (deterministic results);
   - replaces the raw score with a **rank score** `1 / (rank + 1)`.

**Complexity:** building the index is O(total tokens). Scoring a query is O(number of chunks × query terms). The project rebuilds the index **per query** from the workspace's chunks (`BM25Index(searchable)` inside `_rank`), which is simple and always up to date, but costs time proportional to the corpus on each question. The corpus is capped by `retrieval_corpus_cap` (default 10,000 chunks).

### 4.2 Vector similarity search

**What it is:** each chunk is turned into a vector (an embedding). Similar meanings give vectors that point in similar directions. The search returns the chunks whose vectors are closest to the query vector.

**How the project does it:**

1. The query is embedded by `Embedder.encode` (`app/services/embedder.py`), which calls `embed()` in `app/api/ingestion.py`.
2. `semantic()` inside `_rank` first checks that the collection's vector size equals `settings.vector_size` and that its distance is `Cosine`. If not, it refuses to search.
3. `VectorStoreManager.search_tenant` asks Qdrant for the nearest neighbours, using a typed filter built by `tenant_filter(scope)` (workspace, optional document ids, active generations).
4. Scores are clamped to [0, 1] and results outside the scope are dropped again.

**Who implements the index:** Qdrant. It maintains the approximate nearest-neighbour (ANN) index. The project does **not** implement HNSW or any other ANN structure.

### 4.3 Reciprocal Rank Fusion (RRF)

BM25 scores and cosine scores are on different scales, so they cannot simply be added. RRF ignores the raw scores and uses only **positions** in each list.

```python
# app/services/hybrid_retriever.py (abridged)
def reciprocal_rank_fusion(rankings, k=60):
    scores, chunks = {}, {}
    for ranking in rankings:
        seen = set()
        for rank, chunk in enumerate(ranking, 1):
            key = chunk.chunk_id
            if key in seen:
                continue
            seen.add(key)
            chunks[key] = chunk
            scores[key] = scores.get(key, 0) + 1 / (k + rank)
    maximum = len(rankings) / (k + 1)
    return [replace(chunks[key], score=score / maximum)
            for key, score in sorted(scores.items(), key=lambda item: (-item[1], item[0]))]
```

Step by step:

1. For each list, a chunk at position `rank` earns `1 / (60 + rank)`.
2. A dictionary (`scores`) adds up the contributions. A chunk found by both searches gets two contributions.
3. A `set` (`seen`) ignores a chunk that appears twice in the same list.
4. The total is divided by the best possible score (`len(rankings) / (k + 1)`), so a chunk that is first in both lists gets exactly 1.0.
5. Sorting by `(-score, chunk_id)` gives a deterministic order.

**Complexity:** O(n) to accumulate plus O(n log n) to sort, where n is the number of distinct chunks.

**What the threshold means after normalisation.** With two lists, a chunk found by only **one** search at rank `r` scores (1/(60 + r)) ÷ (2/61) = 61 / (2 × (60 + r)):

| Rank in its only list | Normalised score |
|---|---|
| 1 | 0.50 |
| 2 | ≈ 0.49 |
| 50 (deepest possible, `top_k_max`) | ≈ 0.28 |

- **Code default, `score_threshold` = 0.5:** a chunk found by only one search passes only if it is ranked **first** there. Every other chunk needs support from both searches.
- **Demo configuration, `SCORE_THRESHOLD_DEFAULT=0.25`:** every single-search result passes, because even rank 50 scores about 0.28. The threshold then filters little, and `top_k` (5) decides how many chunks are selected.

Both cases follow directly from the code. Whether either threshold contributes to the insufficient-context declines tracked as T4AB-02 has **not** been verified.

### 4.4 Hybrid retrieval and sliding-window expansion

`HybridRetriever._rank` runs the two searches **concurrently** with `asyncio.gather(semantic(), keyword())`, fuses them, keeps candidates with `score >= score_threshold`, and takes the first `top_k`.

Then it expands the context with neighbouring chunks:

- every chunk stores its position in the document as `metadata["index"]` (set in `app/api/ingest_v1.py`);
- for each selected hit, chunks of the **same document** with `abs(neighbor - index) <= window_size` are added once (a `seen` set prevents duplicates).

This is a sliding window over positions: if the best match is chunk 12 and `window_size` is 3, chunks 9 to 15 can be added. The LLM then sees the sentences around the match, not an isolated fragment.

**Complexity:** the expansion loops over the searchable corpus for each selected hit: O(top_k × corpus). That is acceptable because `top_k` is small (default 5).

### 4.5 One-hop Markdown link traversal

For chunks that come from an OKF Markdown bundle (`okf_bundle` and `okf_path` metadata), `_rank` reads Markdown links `[text](target.md)` in the hit, resolves them with `posixpath.normpath`, and adds chunks from the linked file in the **same bundle**. It is a graph traversal of depth one:

- external links (anything containing `:`) and non-`.md` targets are ignored;
- paths that resolve outside the bundle (`../`) are refused;
- nothing is fetched from the network.

**Scope note:** only the older OKF ingestion (`app/api/okf.py`, `app/services/okf.py`) creates chunks with this metadata. Chunks from the integrated `/v1/ingest` (PDF and YouTube) do not have it, so in the integrated product this step finds nothing to follow.

### 4.6 Document chunking with a heading stack

`contextual_chunks` in `app/services/chunking.py` splits text into chunks that fit the embedding model's budget **without losing or duplicating text**.

1. `_blocks(text)` scans lines once and groups them into blocks: heading, blank, list, table, paragraph and fenced code. Headings inside code fences are ignored.
2. A **heading stack** tracks the current section path. When a heading of level `n` arrives, every heading of level ≥ `n` is popped, then the new one is pushed. The result is a path such as `Unit 2 > Deadlocks > Prevention`.
3. Blocks are packed **greedily** into the current chunk while they fit (`fits()` checks characters and UTF-8 bytes). A heading change or overflow starts a new chunk.
4. A block that is too big on its own is split at the last sentence end, then the last line break, then the last space. Splitting by character is the last resort.
5. Each chunk keeps its exact `start`/`end` character offsets. The text sent to the embedding model is prefixed with the title and heading path, but the stored source text is unchanged.

Complexity: one linear pass over the text, with a small extra cost when a large block must be split.

### 4.7 SHA-256 deduplication and deterministic ids

- **Uploads (Team 4C):** the SHA-256 of an uploaded PDF is stored in `File.contentSha256`. The partial unique index `workspace_content_sha256_unique` on `(workspaceId, contentSha256)` (`team4c/models/File.ts`) means the same bytes can exist only once per workspace. A second upload reuses the existing material ("Already in this workspace"). YouTube uses the same idea with a normalised video id and the index `workspace_youtube_video_id_unique` (Task 13).
- **Backend spool (Team 4C integration layer):** `fetch_to_spool` in `app/services/source_fetch.py` and `_sha256_file` in `app/services/ingest_store.py` hash files in streamed blocks, so large files are never loaded into memory at once.
- **Vector points (Teams 4A/4B, with Team 4C workspace scoping):** the integrated product writes with `upsert_tenant_batch`, which uses `uuid5(NAMESPACE_URL, f"{workspace_id}\x1f{chunk_id}")` as the Qdrant point id (the older `upsert_batch` uses `uuid5(NAMESPACE_URL, chunk_id)`). The same input always gives the same point id, so re-sending a chunk overwrites it instead of creating a duplicate (idempotent upsert). Including the workspace id means identical content in two workspaces never collides.
- **Collection names:** `embedding_collection` in `app/api/ingestion.py` hashes the embedding model name and chunking profile, so changing the model or chunk settings automatically uses a new collection, and vectors of different sizes are never mixed.

### 4.8 Sliding-window rate limiter with LRU eviction

`createRateLimiter` in `team4c/lib/rateLimit.ts` stores `Map<key, number[]>`: a list of request timestamps per key.

```ts
// team4c/lib/rateLimit.ts (abridged)
const recent = (hits.get(key) ?? []).filter((t) => now - t < windowMs);
if (recent.length >= limit) { hits.set(key, recent); return secondsToWait; }
recent.push(now);
hits.delete(key);           // re-insert so the Map stays in least-recently-used order
hits.set(key, recent);
if (hits.size > maxKeys) {  // evict the least recently used key
  const oldest = hits.keys().next().value;
  if (oldest !== undefined) hits.delete(oldest);
}
```

- **Sliding window:** only timestamps inside the last `windowMs` count, so there is no burst at a fixed window boundary.
- **LRU:** a JavaScript `Map` iterates in insertion order. Deleting and re-inserting a key moves it to the end, so the first key is always the least recently used. Eviction is O(1).
- **Memory bound:** at most `maxKeys` keys (default 10,000) per limiter. Each limiter has its **own** store, so flooding one limiter cannot evict another's counters (Task 2, `team4c/lib/authRateLimit.ts`).

Used by `/api/chat` (default 20 per minute per user), `/api/network-check`, and sign-in/sign-up (see [08_Information_Security.md](08_Information_Security.md)).

### 4.9 FIFO offline queue

When the browser is offline, chat messages are kept in `chat.offlineQueue` in the Zustand store (`team4c/store/appStore.ts`). `flushOfflineQueue` in `team4c/components/chat/OfflineQueue.ts` sends them **in strict first-in, first-out order** when the connection returns. If one fails, it and everything after it stay queued, so the order is never broken. A guard (`isFlushing`) prevents two flushes from running at once. The queue is in memory only: it does not survive a page reload (a deliberate choice explained in the file).

### 4.10 Keyset pagination

The conversation sidebar loads conversations 30 at a time (`DEFAULT_PAGE_SIZE = 30`, `MAX_PAGE_SIZE = 50`).

```ts
// team4c/app/api/workspaces/[id]/conversations/route.ts (abridged)
if (cursor) {
  query.$or = [
    { updatedAt: { $lt: cursor.updatedAt } },
    { updatedAt: cursor.updatedAt, _id: { $lt: new Types.ObjectId(cursor.id) } },
  ];
}
const conversations = await ConversationModel.find(query)
  .sort({ updatedAt: -1, _id: -1 })
  .limit(limit + 1);
const hasMore = conversations.length > limit;
```

1. The cursor is the last row's `(updatedAt, _id)`.
2. The next page asks for rows strictly "after" that pair in the sort order. `_id` breaks ties when two conversations have the same `updatedAt`.
3. Fetching `limit + 1` rows tells the server whether another page exists without a separate count query.

Unlike `skip(n)`, the database does not have to walk past the first `n` rows, and new conversations added while scrolling do not shift pages and cause duplicates or gaps.

### 4.11 Replay cache (bounded hash map)

`ReplayCache` in `app/core/auth.py` remembers each service token's id (`jti`) until it expires:

1. `use_once(token_id, expires_at, now)` takes a lock, then looks up the id in a dictionary: O(1).
2. If the id is present and not expired, the token is a replay and is rejected.
3. When the dictionary reaches its capacity (default 100,000), expired entries are removed. If it is still full, the service **fails closed** with 503 instead of forgetting ids that are still valid.

### 4.12 Bounded conversation history

`ConversationHistory` keeps at most 51 turns (Pydantic `max_length=51`). `ConversationManager.summarize_if_needed` keeps only the last `conversation_max_turns` turns (default 6) and moves older ones into an **extractive summary** (`User: … | Assistant: …`, each side cut to 240 characters). The summary is cut to `conversation_summary_max_chars` (default 2,000) by keeping its **end**, so the most recent context survives. Memory per session is bounded no matter how long the conversation runs.

## 5. Alternatives and design trade-offs

| Decision | Alternative | Why the project's choice | Trade-off |
|---|---|---|---|
| Hybrid BM25 + vectors | Vectors only | BM25 catches exact terms (names, codes, rare words) that embeddings can miss; vectors catch paraphrases | Two searches per query; fusion needs tuning |
| RRF | Weighted sum of normalised scores | No score calibration needed; robust to different scales | Throws away score magnitude; at the 0.5 code default, single-list hits must rank first; at the 0.25 demo setting they all pass (§4.3) |
| BM25 rebuilt per query | Persistent inverted index | Always consistent with the current workspace and active generations; no index to keep in sync | O(corpus) work per query; corpus cap needed |
| Qdrant ANN index | Brute-force cosine in numpy | Scales and filters by payload | External dependency; embedded mode is single-process |
| Keyset pagination | `skip`/`limit` offset pagination | Stable pages, no deep-skip cost | Cannot jump to "page 7" directly |
| In-memory sliding window | Token bucket, or Redis-backed limiter | Simple, exact per window, no extra service | Per process only; resets on restart |
| `uuid5` point ids | Random UUIDs | Idempotent re-upserts | Chunk ids must be unique within a workspace (`app/api/ingest_v1.py` makes them unique per generation) |
| Extractive summary | LLM-written summary | No extra model call, deterministic | Loses meaning; only 240 characters per side are kept |

## 6. Limitations and concepts not implemented

| Item | Status |
|---|---|
| Custom ANN index (HNSW, IVF), custom trees, heaps, tries | **Not implemented** (Qdrant provides the ANN index) |
| Dynamic programming algorithms | **Not implemented** |
| Re-ranking with a cross-encoder model | **Not implemented** (`LayaDecision` in `app/services/laya_decision.py` is an optional older selector; the canonical query path does not pass a `decision`) |
| BM25 tokenisation for Indic scripts: `\w+` splits some Devanagari words incorrectly | **Open** (T4AB-06, pytest xfail) |
| Intermittent "not enough context" declines | **Open** (T4AB-02; retrieval is Team 4B's area; shared investigation with Team 4C's support check) |
| Persistent BM25 index | **Not implemented** (rebuilt per query) |
| Offline queue survives reload | **Not implemented** (by design) |
| Compound index matching the sidebar sort `(workspaceId, updatedAt, _id)` | **Not implemented**: only `workspaceId_1` exists (`team4c/lib/requiredIndexes.ts`), so MongoDB sorts the workspace's conversations in memory. Fine at demo scale; Not verified at large scale |

## 7. Interview questions

**Q1. Why does the project use both BM25 and vector search?**
BM25 is good at exact words: a course code, a person's name or a rare technical term. Embeddings are good at meaning: "deadlock avoidance" matches a passage about "Banker's algorithm" even without shared words. `HybridRetriever._rank` runs both at the same time with `asyncio.gather` and merges them with RRF. The cost is two searches per question and one more thing to tune.

**Q2. How does Reciprocal Rank Fusion work, and why `k = 60`?**
Each list gives a chunk `1 / (k + rank)`. The contributions are added in a dictionary and normalised so a chunk first in both lists gets 1.0. Using positions instead of raw scores avoids comparing BM25 numbers with cosine similarities. `k = 60` is the common default from the RRF literature; it softens the gap between ranks 1 and 2. The project does not tune it.

**Q3. Does the project implement HNSW?**
No. Qdrant builds and searches the nearest-neighbour index. The project's job is to embed text, store vectors with a payload (`workspace_id`, `document_id`, `generation`), and search with a typed filter so that results never leave the student's workspace.

**Q4. What is the time complexity of a query?**
Embedding the query is one model call. Vector search is handled by Qdrant. BM25 is rebuilt from the workspace's chunks on each query, so it is linear in the corpus size (capped at 10,000 chunks). RRF is O(n log n) for sorting. Window expansion is O(top_k × corpus) with a small `top_k`. In practice, LLM generation dominates the total time.

**Q5. Why keyset pagination instead of `skip`?**
With `skip(1000)` the database still walks over 1,000 rows, and if a new conversation is created between page loads, every row shifts and the student sees a duplicate. The route filters on `(updatedAt, _id)` "less than the cursor" and sorts by the same pair, so pages are stable. `_id` breaks ties. Fetching `limit + 1` rows reveals whether there is a next page without a count query.

**Q6. How does the rate limiter stay bounded in memory, and what is LRU about it?**
Each limiter holds a `Map` from key to recent timestamps. Old timestamps are filtered out on every call (sliding window). Each time a key is used it is deleted and re-inserted, which moves it to the end of the Map's insertion order. When the Map has more than `maxKeys` keys, the first key, the least recently used one, is deleted in O(1).

**Q7. How is a duplicate PDF detected?**
The server computes the SHA-256 of the uploaded bytes. A partial unique index on `(workspaceId, contentSha256)` allows each hash only once per workspace. A second upload of the same file finds the existing record and reuses it. The hash is of the content, not the file name, so a renamed copy is still detected.

**Q8. Why use `uuid5` for Qdrant point ids?**
`uuid5` is deterministic: the same input always gives the same UUID. `upsert_tenant_batch` hashes the workspace id together with the chunk id. If an ingestion step is retried, the same points are overwritten instead of duplicated, and two workspaces with identical content never overwrite each other. A random `uuid4` would create a second copy of every chunk on retry.

**Q9. How does the chunker avoid cutting a sentence in half?**
It first groups lines into blocks (paragraphs, lists, tables, code). Blocks are packed while they fit the budget. A block that is too big is split at the last sentence ending inside the budget, then at a line break, then at a space. Character splitting is the last resort. A heading stack keeps the section path so each chunk knows it belongs to, for example, "Unit 2 > Deadlocks".

**Q10. What happens when the replay cache is full?**
It first deletes expired token ids. If it is still full, it refuses the request with 503. Forgetting a still-valid id would let an attacker replay that token, so the code chooses availability loss over a security hole (fail closed).

**Q11. Why is the conversation summary cut from the end?**
`summarize_if_needed` keeps `[-conversation_summary_max_chars:]` of the summary, which is the most recent part. For follow-up questions, recent turns matter more than the first question of the session. The trade-off is that the beginning of a long conversation is eventually forgotten.

**Q12. What is a weakness of the current retrieval design?**
BM25's `\w+` tokeniser splits some Indic-script words incorrectly (T4AB-06). Also, the score threshold behaves very differently in the two configurations (§4.3). At the 0.5 code default, a chunk found by only one search must rank first there to pass. At the 0.25 demo setting, every single-search result passes. Whether either setting contributes to the intermittent declines in T4AB-02 has not been verified. Retrieval and tokenisation are Team 4B's area; the investigation is shared.

## 8. References

- [RAG pipeline](../technical/RAG_PIPELINE.md): end-to-end retrieval walkthrough, including the threshold values
- [BM25, hybrid search and RRF](../learning/BM25_AND_HYBRID_SEARCH.md): beginner explanation of the ranking ideas
- [Vector databases](../learning/VECTOR_DATABASES.md)
- [File ingestion](../technical/FILE_INGESTION.md): duplicate detection and idempotent uploads
- [Known limitations §3](../../KNOWN_LIMITATIONS.md#3-answer-quality-open-owned-by-the-rag-side-shared-investigation): open answer-quality issues (T4AB-02, T4AB-06 in the internal records)
- Internal verification records (not published): YouTube duplicate prevention (Task 13), sidebar pagination (Task 16), service-token interoperability test (replay rejection)
- Related subjects: [03 DBMS](03_Database_Management_Systems.md) (indexes), [04 OS](04_Operating_Systems.md) (concurrency in retrieval), [08 Information Security](08_Information_Security.md) (rate limits)
