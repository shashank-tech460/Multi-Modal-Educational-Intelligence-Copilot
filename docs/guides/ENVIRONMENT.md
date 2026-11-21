# Environment Configuration

Configuration **names and purposes** for both services. **No real values are given.** Secrets must never be committed; only empty example templates belong in version control.

---

## 1. Next.js application

| Variable | Secret? | Purpose |
|---|---|---|
| `MONGODB_URI` | **Yes** | MongoDB connection string |
| `AUTH_SECRET` | **Yes** | Signs Auth.js session JWTs and file capability tokens. Production requires a long value |
| `AUTH_URL` | No | Public URL of the app (must be HTTPS in production for HSTS) |
| `AUTH_TRUST_HOST` | No | Lets Auth.js trust the configured host |
| `HSTS_MAX_AGE` | No | Enables the HSTS header (only when `AUTH_URL` is HTTPS) |
| `USE_MOCK_TEAM_A` / `USE_MOCK_TEAM_B` | No | `true` = mock backends (development only; refused in production) |
| `TEAM_A_API_URL` / `TEAM_B_API_URL` | No | Backend base URL for ingestion and query (the same service in the integrated system) |
| `SERVICE_JWT_PRIVATE_KEY` | **Yes** | ES256 (P-256) private key, PKCS8 PEM |
| `SERVICE_JWT_KID` | No | Key id placed in the token header |
| `SERVICE_JWT_ISSUER` | No | Issuer claim the backend expects |
| `SERVICE_JWT_TTL_SECONDS` | No | Token lifetime (default 300) |
| `STORAGE_PROVIDER`, `STORAGE_API_KEY`, `STORAGE_API_SECRET` | Key/secret: **yes** | Reserved for object storage. **Not implemented**; production refuses a non-empty provider |
| `AUTH_LOGIN_EMAIL_LIMIT`, `AUTH_LOGIN_IP_LIMIT`, `AUTH_LOGIN_GLOBAL_LIMIT` | No | Sign-in rate limits (defaults 10 / 30 / 300) |
| `AUTH_SIGNUP_EMAIL_LIMIT`, `AUTH_SIGNUP_IP_LIMIT`, `AUTH_SIGNUP_GLOBAL_LIMIT` | No | Sign-up rate limits (defaults 5 / 10 / 100) |
| `AUTH_TRUSTED_PROXY_HOPS` | No | How many reverse-proxy hops to trust when reading the client address |
| `CHAT_RATE_LIMIT_PER_MINUTE` | No | Chat limit per user (default 20; 0 disables) |

## 2. FastAPI backend

### Core

| Variable | Code default | Verified demo value | Purpose |
|---|---|---|---|
| `ENVIRONMENT` | `development` | development | `production` enables the route allowlist and strict startup checks |
| `STORAGE_MODE` | `local` | `local` | `local` = embedded Qdrant + in-process FakeRedis |
| `QDRANT_LOCAL_PATH` | none (in-memory) | `data/qdrant` | Folder for embedded Qdrant |
| `QDRANT_URL`, `QDRANT_API_KEY` | localhost | — | External Qdrant server (not used in the demo) |
| `REDIS_URL` | localhost | — | External Redis (not used in local mode) |
| `SESSION_TTL_SECONDS` | 1800 | 1800 | Conversation-memory lifetime |

### Models and retrieval

| Variable | Code default | Verified demo value | Purpose |
|---|---|---|---|
| `OLLAMA_URL` | `http://localhost:11434` | same | Ollama server |
| `OLLAMA_MODEL` | `gemma3:1b` | **`llama3:latest`** | Answer model |
| `EMBEDDING_MODEL` | `all-minilm` | **`all-minilm`** | Embedding model |
| `VECTOR_SIZE` | 384 | **384** (measured by the launcher) | Must match the embedding model |
| `OLLAMA_CONTEXT_TOKENS` | 8192 | 8192 | Model context window |
| `OLLAMA_MAX_TOKENS` | 512 | 512 | Maximum answer length |
| `OLLAMA_TIMEOUT_SECONDS` / `RAG_GENERATION_TIMEOUT_SECONDS` | 120 / 120 | 300 / 300 | Timeouts |
| `CHUNK_MAX_CHARS` | 1200 | 1200 | Maximum chunk characters |
| `EMBEDDING_CONTEXT_TOKENS` | 512 | 512 | Embedding input budget |
| `TOP_K_DEFAULT` | 5 | 5 | Chunks returned |
| `TOP_K_MAX` | 50 | 50 | Candidates per search method |
| `SCORE_THRESHOLD_DEFAULT` | 0.5 | **0.25** | Minimum fused score |
| `WINDOW_SIZE_DEFAULT` | 3 | 3 | Neighbour chunks added |
| `MAX_QUERY_LENGTH` | 2000 | 2000 | Question length limit |
| `LAYA_ENABLED` | false | false | Optional re-ranker (off) |

> The backend's committed example environment file still lists **older** model settings (`OLLAMA_MODEL=gemma3:1b`, Qwen3 embeddings with `VECTOR_SIZE=4096`). The table above shows the **verified demo configuration**.

### Integration and security

| Variable | Purpose |
|---|---|
| `SERVICE_JWT_JWKS_FILE` | Path to the **public** key set (JWKS). Missing → every protected route returns 503 |
| `SERVICE_JWT_ISSUER` | Exact issuer to accept |
| `SERVICE_JWT_LEEWAY_SECONDS` | Clock tolerance (default 30) |
| `SERVICE_JWT_MAX_TTL_SECONDS` | Maximum accepted token lifetime (default 300) |
| `SERVICE_JWT_REPLAY_CACHE_SIZE` | Size of the `jti` replay cache |
| `INGEST_ALLOWED_ORIGINS` | Origins the backend may download files from (must equal the frontend origin) |
| `INGEST_YOUTUBE_ENABLED` | Turns on YouTube ingestion (demo: `true`) |
| `INGEST_DATA_DIR` | Folder for the ingest job registry and download spool |
| `MEDIA_MAX_BYTES` | Maximum downloaded file size (demo: 50 MB, aligned with the frontend) |
| `LEGACY_WORKBENCH_ENABLED` | Development only; production ignores it |

## 3. Rules for handling secrets

1. Real `.env` files are **git-ignored**.
2. Generate `AUTH_SECRET` randomly and make it long.
3. The ES256 **private key stays with the Next.js server only**. The backend gets only the **public** JWKS.
4. Error messages and startup checks name variables, **never their values**.
5. In production, use a secret manager instead of files (not yet done; see [Deployment](DEPLOYMENT.md)).
