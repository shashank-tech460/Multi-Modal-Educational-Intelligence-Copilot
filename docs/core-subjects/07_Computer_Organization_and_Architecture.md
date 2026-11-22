# 07 — Computer Organization and Architecture (COA)

| Item | Value |
|---|---|
| Date | 2026-11-22 |
| Subject | Computer Organization and Architecture |
| Relevance | **Limited.** This is a short document by design. The project is application software and does not work at the hardware level |
| Main code | `app/core/config.py`, `app/api/ingestion.py` (`embed`, `embedding_collection`), `app/services/vector_store.py`, `app/services/hybrid_retriever.py`, `app/services/chunking.py`, `app/services/ollama.py`, `app/services/video_transcriber.py` (older pipeline) |
| Build | Final integrated build (local demo) |
| Owners | Team 4A (embeddings, chunking, transcription), Team 4B (Ollama client), Teams 4A/4B (vector store) |
| Status labels | Verified, Implemented, Not verified, Open, Not implemented (see [README](README.md)) |

---

## 1. Introduction

Computer Organization and Architecture studies how hardware represents data and executes programs: number formats, memory, processors and their performance limits.

EduCopilot does **not** implement any hardware-level component. It has no CPU design, instruction pipeline, cache controller, assembly code or hardware description. The only genuine connections are about **how data is represented** (floating-point vectors, UTF-8 bytes) and **how hardware limits shape design decisions** (CPU-only local inference, memory per vector, quantisation). This document covers only those, and nothing more.

## 2. Core concepts

| Concept | Where | Owner | Status |
|---|---|---|---|
| Floating-point embedding vectors (384 dimensions in the verified configuration) | `vector_size` in `app/core/config.py`; `VectorParams(size=…)` in `app/services/vector_store.py` | Teams 4A/4B | Verified (Task 21 used `all-minilm`, 384 dimensions) |
| Cosine similarity | `distance_metric` (Cosine); the check in `HybridRetriever._rank` (`semantic()`) | Team 4B | Implemented |
| Bytes vs characters (UTF-8) | `clip_bytes` and the byte budget in `app/services/chunking.py` | Team 4A | Implemented |
| CPU-based local inference | Ollama (`app/services/ollama.py`), serialised by an `asyncio.Lock` | Team 4B | Verified (Task 21 ran `llama3:latest` + `all-minilm` locally) |
| CPU and memory constraints on design | Model lock, ingest semaphore, corpus cap, leases sized for slow ingestion | Team 4B / Team 4C (integration layer and application) | Implemented |
| INT8 quantisation | `WhisperModel(..., device="cpu", compute_type="int8")` in `app/services/video_transcriber.py` | Team 4A | Implemented, **outside the integrated product** (MP4 pipeline) |

## 3. Project implementation, step by step

### 3.1 Embeddings are arrays of floating-point numbers

An embedding model turns a chunk of text into a fixed-length vector of real numbers. In the configuration verified in Task 21, the embedding model is `all-minilm` and each vector has **384 dimensions** (`vector_size` default 384 in `app/core/config.py`). The local collection name also ends in `_384`, because `embedding_collection` in `app/api/ingestion.py` appends the vector size.

- Qdrant stores vectors as 32-bit floats unless another data type is configured. The project's `VectorParams(size=…, distance=…)` does not set one, so the default applies.
- Memory per vector at 32 bits: 384 × 4 bytes = **1,536 bytes**. For the 10,000-chunk retrieval cap, that is about 15 MB of vector data, before Qdrant's index overhead.
- The dimension is **configurable**. The repository's `.env.example` also documents a remote `Qwen3-Embedding-8B` option with `VECTOR_SIZE=4096` (served from a separate GPU notebook via `EMBED_API_URL`). At 4096 dimensions each vector is 16 KiB, about 10.7 times more memory and transfer per vector. That option is **not** the configuration used in the Task 21 verification (status: Not verified in the integrated regression).
- The code refuses to mix sizes: `semantic()` checks that the collection's vector size equals `settings.vector_size`, and collection names include the size, so a 384-dimension query is never compared with 4096-dimension vectors.

### 3.2 Cosine similarity as arithmetic

Cosine similarity compares the **direction** of two vectors:

```
cos(a, b) = (a · b) / (|a| × |b|)      a · b = a1·b1 + a2·b2 + … + a384·b384
```

For one comparison at 384 dimensions, that is about 384 multiplications and additions for the dot product, plus the norms. Qdrant performs these calculations (with its own optimised code and ANN index). The project only selects the metric (`DISTANCE_METRIC=Cosine`) and requires it: `semantic()` refuses to search a collection whose distance is not `Cosine`. Floating-point rounding means scores are approximate, so the code clamps them into [0, 1] with `max(0., min(1., r.score))`.

### 3.3 Characters are not bytes

In UTF-8, an English letter takes 1 byte, a Devanagari letter 3 bytes and many emoji 4 bytes. The chunker budgets in **bytes**, not characters:

- `clip_bytes(text, limit)` cuts the UTF-8 encoding to `limit` bytes and drops an incomplete trailing character (`errors="ignore"`), so a multi-byte character is never split into an invalid sequence.
- The embedding budget assumes one UTF-8 byte per token (`embedding_context_tokens - 16`). The comment in `chunking.py` calls this intentionally conservative, not an exact token count.

The frontend applies the same idea to passwords: bcrypt uses only the first 72 **bytes**, so `MAX_PASSWORD_BYTES = 72` is checked as a UTF-8 byte length (`team4c/lib/validation.ts`).

### 3.4 CPU-based local inference and its limits

The verified setup runs the LLM (`llama3:latest`) and the embedding model (`all-minilm`) locally through Ollama. Hardware limits show up directly in the design:

| Hardware limit | Design response in the code |
|---|---|
| Generation on a CPU is slow and memory-heavy; parallel generations compete for the same cores and RAM | `OllamaChat` serialises model calls with one `asyncio.Lock`; queue time counts against the deadline (`stream_messages`) |
| Output length drives compute time | `num_predict` = `ollama_max_tokens` (512 in `.env.example`); `num_ctx` = `ollama_context_tokens` (default 8192) |
| Ingestion (embedding every chunk) is CPU-heavy | At most `ingest_fetch_concurrency` (default 2) ingestions at once |
| Ingestion can take minutes on CPU | The Team 4C file lease (6 min) and 5-minute request deadline are sized so a slow but live ingestion is not mistaken for a crash (`team4c/lib/processingRecovery.ts`) |
| RAM per query | `retrieval_corpus_cap` (10,000 chunks) bounds what is loaded for BM25 |

Task 21 recorded a YouTube ingestion taking about 40 seconds during the synchronous "Adding…" step ([File ingestion §4](../technical/FILE_INGESTION.md#4-youtube-flow)). This observation comes from one machine and is not a benchmark.

### 3.5 INT8 quantisation (older pipeline, outside the integrated product)

`VideoTranscriber` in `app/services/video_transcriber.py` loads a faster-whisper model with `device="cpu", compute_type="int8"`. Quantisation stores weights as 8-bit integers instead of 32-bit floats. That cuts weight memory to about a quarter and lets the CPU use faster integer arithmetic, at a small cost in accuracy.

**Scope:** this is part of the MP4 upload pipeline. The integrated product rejects MP4 uploads (`/v1/ingest` answers `422 unsupported_type` for MP4), and YouTube ingestion uses caption tracks, not Whisper. This section is included only as an example of a hardware-motivated choice in the repository.

## 4. Alternatives and design trade-offs

| Decision | Alternative | Trade-off |
|---|---|---|
| 384-dimension embeddings (`all-minilm`) | 4096-dimension embeddings (`Qwen3-Embedding-8B`, documented in `.env.example`) | Small and fast on a CPU, about 10.7× less memory per vector; larger models may capture meaning better but need a GPU service and more storage |
| Local CPU inference | Hosted GPU or API inference | No data leaves the machine and no API cost; slow, one generation at a time |
| Serialise model calls | Run generations in parallel | Predictable latency per request on a CPU; lower throughput |
| Byte-based chunk budgets | Character counts | Safe for multi-byte scripts; slightly smaller chunks for non-Latin text |
| INT8 Whisper (older pipeline) | FP32 or FP16 model | Less memory, faster on CPU; slightly lower accuracy |

## 5. Limitations and concepts not implemented

| Item | Status |
|---|---|
| CPU architecture, instruction sets, pipelining, hazards | **Not implemented** |
| Cache design, cache controllers, memory hierarchy management | **Not implemented** |
| Hardware design, HDL (Verilog/VHDL), digital logic | **Not implemented** |
| Assembly language, SIMD code written by the project | **Not implemented** (vector maths is done inside Qdrant, numpy and the model runtimes) |
| GPU programming (CUDA) by the project | **Not implemented** (the optional remote embedding service is a separate notebook, `scripts/colab_qwen3_embedding_server.ipynb`, not part of the verified integrated configuration) |
| Performance benchmarks of inference latency or memory | **Not verified** (no benchmark report; the AI quality benchmark measures answer quality, not hardware performance) |

## 6. Interview questions

**Q1. What is an embedding at the data level?**
A fixed-length array of floating-point numbers. In the verified configuration it has 384 dimensions (`all-minilm`). Stored as 32-bit floats, one vector takes 1,536 bytes.

**Q2. Why not use a larger embedding model?**
The verified setup runs on a CPU. A 384-dimension model is fast and small. A 4096-dimension option (`Qwen3-Embedding-8B`) is documented in `.env.example` and served from a GPU notebook, but it uses about 10.7 times more memory per vector and was not part of the Task 21 verification.

**Q3. How does cosine similarity relate to hardware?**
It is a dot product divided by two norms: hundreds of floating-point multiply-adds per comparison at 384 dimensions. Qdrant performs this with optimised code and an ANN index, so the project does not compute it itself. Rounding makes scores approximate, and the project clamps them to [0, 1].

**Q4. Why does the chunker count bytes instead of characters?**
UTF-8 uses 1 to 4 bytes per character, and model limits are closer to byte counts than to character counts. `clip_bytes` cuts at a byte limit without splitting a multi-byte character, which matters for Devanagari and emoji.

**Q5. How do CPU limits affect the LLM integration?**
Only one generation runs at a time (`asyncio.Lock`), with a single deadline that includes queue time. Output length is capped with `num_predict`, and ingestion concurrency is limited to 2.

**Q6. What is INT8 quantisation, and does the product use it?**
Storing model weights as 8-bit integers instead of 32-bit floats: about four times less memory and faster CPU arithmetic, with small accuracy loss. It appears only in the older MP4 transcription pipeline (`video_transcriber.py`), which the integrated product does not use.

**Q7. Does the project implement anything at the hardware level?**
No. It does not implement CPU pipelines, caches or hardware design. Its COA connections are data representation and designing around CPU and memory limits.

**Q8. If you had a GPU, what would change?**
Generation and embedding would be faster, so the model lock and the ingestion limit could be relaxed, and a larger embedding model would become practical. This has not been tested in the integrated product.

## 7. References

- [System architecture §H](../architecture/SYSTEM_ARCHITECTURE.md#h-llm-integration): LLM integration
- [Setup §2](../guides/SETUP.md#2-prerequisites): prerequisites (Ollama with `llama3:latest` and `all-minilm`)
- [Vector databases](../learning/VECTOR_DATABASES.md): embeddings and similarity
- Internal verification record (not published): Task 21 final regression (backend configuration used)
- Related subjects: [01 DSA](01_Data_Structures_and_Algorithms.md) (vector search), [04 OS](04_Operating_Systems.md) (locks, semaphores, memory bounds)
