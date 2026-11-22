# 02 — Object-Oriented Programming (OOPS)

| Item | Value |
|---|---|
| Date | 2026-11-22 |
| Subject | Object-Oriented Programming and design patterns |
| Relevance | Strong in the Python backend; the TypeScript frontend is mainly functional (React hooks) with OOP used for domain objects and errors |
| Main code | `app/services/vector_store.py`, `app/services/local_qdrant.py`, `app/services/hybrid_retriever.py`, `app/services/conversation.py`, `app/services/ingest_store.py`, `app/core/auth.py`, `app/core/errors.py`, `app/models/canonical.py`, `team4c/services/teamA/index.ts`, `team4c/services/teamB/index.ts`, `team4c/lib/questionPersistence.ts`, `team4c/models/*.ts` |
| Build | Final integrated build (local demo) |
| Owners | Teams 4A/4B, Team 4C integration layer and Team 4C application (labelled per item) |
| Status labels | Verified, Implemented, Not verified, Open, Not implemented (see [README](README.md)) |

---

## 1. Introduction

Object-oriented programming groups **data and the operations on that data** into objects, hides internal details, and lets different objects be used through the same interface.

In EduCopilot, OOP is used where it helps most:

- **Service objects** in the backend (`VectorStoreManager`, `HybridRetriever`, `ConversationManager`, `IngestStore`, `ServiceJwtVerifier`) each own one responsibility and hide their internal state.
- **Immutable value objects** (frozen dataclasses, frozen Pydantic models) carry data safely between functions and threads.
- **Design patterns** (Proxy, Factory, Strategy, dependency injection) solve concrete problems: thread safety, access control, switching between mock and real services, and testability.

The frontend is written mostly as **functional React components and hooks**, not class components. OOP there appears in domain classes (`QuestionAttempt`), error subclasses and Mongoose schemas. The only React class component is `PanelErrorBoundary`, because React error boundaries can only be written as classes.

## 2. Core concepts

| Concept | Where | Owner | Status |
|---|---|---|---|
| Classes and encapsulation | `VectorStoreManager`, `HybridRetriever`, `ConversationManager`, `IngestStore`, `ServiceJwtVerifier`, `ReplayCache` | Teams 4A/4B; Team 4C (integration layer) | Implemented |
| Immutable value objects | `@dataclass(frozen=True, slots=True)` `RetrievalScope`, `ChunkPayload`; `@dataclass(frozen=True)` `ContextChunk`, `ServicePrincipal`, `SourceRef`, `FetchResult`, `CleanupTask` | Teams 4A/4B; Team 4C (integration layer) | Implemented |
| Proxy pattern (thread safety) | `SerializedQdrantClient` in `app/services/local_qdrant.py` | Integration layer (individual ownership not explicitly specified) | Implemented |
| Proxy pattern (access control) | `_LegacyClientGuard`, `_GuardedMethod` in `app/services/vector_store.py` | Teams 4A/4B, with Team 4C workspace scoping | Verified (workspace isolation, Task 5) |
| Factory | `getTeamAService()`, `getTeamBService()`; `build_service_jwt_verifier()`; `require_service_principal(audience)` | Team 4C (application and integration layer) | Implemented |
| Strategy | Mock vs real Team A/B clients behind `TeamAService`/`TeamBService` interfaces; `SearchMode` (hybrid, semantic, keyword) | Team 4C / Team 4B | Implemented |
| Dependency injection | Constructor arguments (`store`, `embedder`, `settings`, `client`, `clock`); FastAPI `Depends` | Teams 4A/4B; Team 4C (integration layer) | Implemented |
| Polymorphism | Same interface, different implementations (mock/real services, search modes, exception subclasses) | All | Implemented |
| Exception hierarchies | `IngestStoreError` and subclasses; `ApiError`; `VectorStoreUnavailable`; `ChunkValidationError`; TypeScript `OwnershipError`, `TeamBQueryError`, `RateLimitedSignin` | All | Implemented |
| Data models with validation | Pydantic (`Closed` and subclasses in `app/models/canonical.py`, `_Record` subclasses in `ingest_store.py`); Mongoose schemas in `team4c/models/` | `canonical.py`: Integration layer (individual ownership not explicitly specified); `ingest_store.py`: Team 4C (integration layer); Mongoose: Team 4C (application) | Implemented |
| State-machine objects | `QuestionAttempt` (`team4c/lib/questionPersistence.ts`); job states in `IngestStore` | Team 4C (application / integration layer) | Verified (Task 19) / Implemented |

## 3. Project implementation, step by step

### 3.1 Classes and encapsulation

Each backend service class owns a resource and exposes only the operations callers need.

| Class | Hides | Public operations (examples) |
|---|---|---|
| `VectorStoreManager` (`app/services/vector_store.py`) | The raw Qdrant client, retry logic, payload validation | `upsert_batch`, `search_tenant`, `tenant_corpus`, `delete_tenant_document` |
| `HybridRetriever` (`app/services/hybrid_retriever.py`) | How keyword and vector results are fused and expanded | `retrieve_scoped`, `retrieve` |
| `ConversationManager` (`app/services/conversation.py`) | Redis keys, TTLs, optimistic locking | `create_tenant_session`, `seed_tenant_session`, `append_turn`, `get_history` |
| `IngestStore` (`app/services/ingest_store.py`) | File layout, atomic writes, the lock | `create_job`, `mark_spooled`, `start_processing`, `complete`, `fail`, `activate` |
| `ServiceJwtVerifier` (`app/core/auth.py`) | Public keys (`_keys`), replay cache (`_replay`), clock | `verify(token, audience)` |

Python has no `private` keyword. The project uses the leading-underscore convention (`_keys`, `_lock`, `_with_retry`) and, in the guards (§3.3), actively **refuses** access to underscore attributes so the protected object cannot be reached.

### 3.2 Frozen dataclasses (immutable value objects)

`RetrievalScope` describes exactly which data a query may see:

```python
# app/services/vector_store.py (abridged)
@dataclass(frozen=True, slots=True)
class RetrievalScope:
    workspace_id: str
    document_ids: tuple[str, ...] | None = None
    generations: tuple[tuple[str, int], ...] | None = None

    def __post_init__(self) -> None:
        _check_workspace_id(self.workspace_id)   # validated once, at construction
        ...

    def allows(self, result: RetrievalResult) -> bool:
        ...
```

- `frozen=True`: after construction nobody can change `workspace_id`, so a scope checked once stays correct everywhere it is passed, including across threads.
- `slots=True`: no per-instance `__dict__`, so less memory and no accidental extra attributes.
- `__post_init__` validates the input. An invalid scope cannot exist.
- `document_ids` and `generations` are **tuples** (immutable), not lists.

The same idea appears in `ServicePrincipal` (the verified token identity), `ChunkPayload`, `ContextChunk`, `SourceRef` and `FetchResult`. Pydantic models in the ingest store use `ConfigDict(frozen=True)`, and updates are made with `model_copy(update=...)`, which returns a new object.

### 3.3 Proxy pattern

A proxy is an object that stands in front of another object, has the same interface, and adds behaviour.

**(a) Thread-safety proxy: `SerializedQdrantClient`** (`app/services/local_qdrant.py`, Integration layer (individual ownership not explicitly specified))

The embedded Qdrant client is not safe when several threads use it at once. Instead of changing every caller, the client is wrapped:

```python
# app/services/local_qdrant.py (abridged)
class SerializedQdrantClient:
    def __init__(self, client):
        self._inner = client
        self._lock = threading.RLock()

    def __getattr__(self, name):
        attribute = getattr(self._inner, name)
        if name.startswith("_") or not callable(attribute):
            return attribute

        @functools.wraps(attribute)
        def locked(*args, **kwargs):
            with self._lock:
                return attribute(*args, **kwargs)
        return locked
```

`__getattr__` runs for any attribute not defined on the proxy, so every client method (`search`, `upsert`, `delete`, …) is forwarded automatically and runs while holding the lock. `create_app` in `app/main.py` applies it only to embedded clients. See [04 Operating Systems](04_Operating_Systems.md) for the concurrency side.

**(b) Access-control proxy: `_LegacyClientGuard` and `_GuardedMethod`** (`app/services/vector_store.py`)

Workspace data lives in `tenant_*` collections. Older code paths use `store._client`, which is a guard. Before forwarding a call, `_GuardedMethod.__call__` runs `_refuse_tenant_target`, which raises `ChunkValidationError` if the call names a `tenant_*` collection. Private attributes are not forwarded, so the unguarded client cannot be reached through the wrapper. Only the explicit `*tenant*` methods, which require a `RetrievalScope`, can touch workspace data.

### 3.4 Factory and Strategy patterns

**Factory + Strategy for external services (Team 4C):**

```ts
// team4c/services/teamA/index.ts
export function getTeamAService(): TeamAService {
  return process.env.USE_MOCK_TEAM_A === "false" ? realTeamA : mockTeamA;
}
```

- `TeamAService` (in `team4c/types/teamA.ts`) is the interface.
- `realTeamA` (`client.ts`) calls the backend with a service JWT; `mockTeamA` (`mock.ts`) simulates it for development and tests.
- Route handlers call only `getTeamAService()`. They never import a concrete client. Switching strategies is an environment change, not a code change.
- The function reads the variable on **every call**, not once at import time, a lesson recorded in the file from an earlier bug with `MONGODB_URI`.
- An unset flag falls back to the **mock** (safe default in development). Production refuses mocks (`team4c/lib/productionEnv.ts`).

`getTeamBService()` in `team4c/services/teamB/index.ts` follows the same pattern for querying.

**Factory functions in the backend (Team 4C integration layer):**

- `build_service_jwt_verifier(settings)` returns a configured `ServiceJwtVerifier`, or `None` when keys are missing or invalid. `None` means "fail closed": protected routes answer 503.
- `require_service_principal(audience)` returns a new FastAPI dependency function bound to one audience. It is a closure used as a factory.

**Strategy for search:** `SearchMode` (`HYBRID`, `SEMANTIC`, `KEYWORD` in `app/models/schemas.py`) selects which ranking `HybridRetriever._rank` uses. `retrieve` and `retrieve_scoped` also pass different `vector_search` functions into the same `_rank` method, which is the Strategy pattern done with first-class functions.

### 3.5 Dependency injection

Objects receive their dependencies instead of creating them:

```python
class HybridRetriever:
    def __init__(self, store, embedder, settings): ...

class ConversationManager:
    def __init__(self, client=None, settings=None): ...

class IngestStore:
    def __init__(self, root, *, clock=time.time): ...

class ServiceJwtVerifier:
    def __init__(self, keys, issuer, *, ..., clock=time.time): ...
```

- `create_app(settings, vector_client, redis_client, ingest_store)` in `app/main.py` builds the object graph. Tests pass an in-memory Qdrant client and `FakeRedis` instead of real servers.
- Injecting a `clock` lets tests control time, for example to make a token expire or a lease run out without waiting.
- FastAPI's `Depends(...)` injects the verified `ServicePrincipal` into route handlers.

### 3.6 Polymorphism

- **Interface polymorphism:** `mockTeamA` and `realTeamA` both satisfy `TeamAService`. Callers do not know which one they hold.
- **Duck typing:** `SerializedQdrantClient` and `_LegacyClientGuard` behave like a Qdrant client because they forward its methods.
- **Exception polymorphism:** `except IngestStoreError` catches `JobConflict`, `QueueFull`, `InvalidTransition` and `StoreCorrupt`. A handler can be general or specific.

### 3.7 Exception hierarchies

| Hierarchy | Purpose |
|---|---|
| `IngestStoreError` → `JobConflict`, `QueueFull`, `InvalidTransition`, `StoreCorrupt` (`app/services/ingest_store.py`) | Each failure maps to a different API response (409 conflict, queue full, programming error, corrupt record) |
| `ApiError(Exception)` (`app/core/errors.py`) | Carries `status`, `code`, `reason` and `headers`. The constructor refuses unknown codes. `reason` is logged but never sent to the client |
| `VectorStoreUnavailable(RuntimeError)`, `ChunkValidationError(ValueError)` (`app/services/vector_store.py`) | Hide raw Qdrant/network errors (which can contain host details) behind generic, safe messages |
| `FetchError`, `SourceNotAllowed(ValueError)` (`app/services/source_fetch.py`) | Distinguish "refused before any request" from "download failed" |
| TypeScript: `OwnershipError`, `DocumentDeletionError`, `TeamASubmitError`, `TeamBQueryError`, `TeamBStreamProtocolError` (all `extends Error`); `RateLimitedSignin`, `ServiceUnavailableSignin` (`extends CredentialsSignin`) | Let routes map failures to specific HTTP responses and student messages |

A design rule visible in the code: **error messages shown to users are fixed text chosen by code**, never built from exception text (`ERROR_MESSAGES` in `ingest_store.py`, `SAFE_MESSAGES` in `errors.py`). This links OOP to security (see [08 Information Security](08_Information_Security.md)).

### 3.8 Pydantic and Mongoose models

**Pydantic (backend):** in `app/models/canonical.py`, every contract model extends `Closed`:

```python
class Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, str_strip_whitespace=False)

class CanonicalQueryRequest(Closed): ...
class StreamDone(CanonicalQueryResponse): ...   # inheritance between response models
```

`extra="forbid"` rejects unknown fields, so a typo or an unexpected field such as `workspace_id` in a request body fails validation instead of being silently accepted. Inheritance shares this rule across about 20 models.

**Mongoose (frontend):** `team4c/models/` defines schemas for `User`, `Workspace`, `Conversation`, `Message`, `File` and `RevokedSession`. Each schema declares types, required fields, enums (for example `FILE_STATUS_VALUES = ["uploading", "processing", "ready", "failed"]`), references (`ref: "Workspace"`) and indexes. Mongoose turns each schema into a model class with methods such as `findById`, `updateOne` and `deleteMany`. See [03 DBMS](03_Database_Management_Systems.md).

### 3.9 State-machine objects

**`QuestionAttempt` (Team 4C, `team4c/lib/questionPersistence.ts`)** represents one attempt to answer a stored question:

```
generating ──complete()──► answered   (+ one assistant message)
           ──fail()──────► failed
           ──stop()──────► stopped    (partial text kept as partialAnswer)
failed / stopped / expired generating ──retry──► generating (new attemptId)
```

- `readonly` fields `conversationId`, `questionId` and `attemptId` cannot change after construction.
- A `private settled` flag makes each terminal method run **at most once**.
- `ownedFilter()` returns the condition every write must satisfy (`_id`, `generationAttemptId`, `generationState: "generating"`). If a newer attempt took over, the old object's writes match nothing and change nothing.
- A heartbeat renews the lease while the attempt is alive, and `stopHeartbeat` ends it.

**Ingestion jobs (Team 4C integration layer, `IngestStore`):** `queued → processing → ready | failed`. Each method checks the current state and raises `InvalidTransition` for an illegal move, for example `start_processing` on a job that has not been spooled.

## 4. Alternatives and design trade-offs

| Decision | Alternative | Trade-off |
|---|---|---|
| Proxy for locking | Add `with lock:` in every caller | The proxy cannot be forgotten by a new caller; but it serialises **every** call, including reads |
| Guard proxy for tenant collections | Trust callers to use the right method | Defence in depth; slightly more complex code and harder debugging |
| Factory chooses mock vs real | Import the real client everywhere, mock only in tests | Allows full-stack development without the backend; risk of mocks in production, which `productionEnv.ts` blocks |
| Frozen value objects | Mutable dicts | Safe to share and validate once; updates need new objects |
| Constructor injection | Global singletons | Easy testing with fakes; more parameters to pass |
| Functional React + hooks | Class components | Modern React style, simpler state sharing with hooks; error boundaries still need a class (`PanelErrorBoundary`) |
| Fixed error messages | Pass exception text to users | No information leaks; less detail for users (details go to logs) |

## 5. Limitations and concepts not implemented

| Item | Status |
|---|---|
| Class-based React components (apart from `PanelErrorBoundary`) | **Not implemented** (by design: functional components and hooks) |
| Deep inheritance trees or abstract base classes (`abc.ABC`) in the backend | **Not implemented**: the code prefers composition and duck typing |
| Formal interfaces in Python (`typing.Protocol`) for services | **Not implemented**: TypeScript interfaces are used on the frontend side |
| The locking proxy also serialises reads, which limits throughput | **Open** design limit (single-process embedded Qdrant; see [04 OS](04_Operating_Systems.md)) |
| Per-file Team 4A vs Team 4B ownership | Not recorded in git; this document names Team 4A or Team 4B only where [Contributions](../../CONTRIBUTIONS.md) does, otherwise "Teams 4A/4B" |

## 6. Interview questions

**Q1. Where does the project use the Proxy pattern, and why?**
Twice. `SerializedQdrantClient` wraps the embedded Qdrant client and runs every method call while holding one `RLock`, because the embedded client is not thread-safe and FastAPI calls it from a thread pool. `_LegacyClientGuard` wraps the client for older code and refuses any call that names a `tenant_*` collection, so only scope-checked methods can touch workspace data. Both use `__getattr__` to forward calls without listing every method.

**Q2. Why is `RetrievalScope` a frozen dataclass?**
It decides what data a query may see. Validating it once in `__post_init__` and then making it immutable means no later code can widen the scope by mistake, and it is safe to pass between threads. `slots=True` saves memory and blocks accidental attributes.

**Q3. How do you switch between mock and real backends?**
Routes call `getTeamAService()` / `getTeamBService()`, which return either the real client or the mock based on `USE_MOCK_TEAM_A/B`. Both implement the same TypeScript interface (Strategy pattern). The variable is read on every call. In production, `productionEnv.ts` refuses to start unless both flags are `"false"`.

**Q4. Give an example of dependency injection in the project and its benefit.**
`create_app(settings, vector_client, redis_client, ingest_store)` builds the services. Tests inject an in-memory Qdrant client and `FakeRedis`. `ServiceJwtVerifier` and `IngestStore` accept a `clock`, so tests can simulate expiry without sleeping.

**Q5. Why does the frontend not use class components?**
Modern React favours function components with hooks (`useChatStream`, `useActiveConversation`, `useComposerDraft`) for state and side effects. The one exception is `PanelErrorBoundary`, because React only supports error boundaries as class components (`componentDidCatch`).

**Q6. How is encapsulation enforced in Python if there is no `private`?**
By convention (leading underscore) and, where it matters, by code. The guard proxies raise `AttributeError` for underscore attributes, so the hidden client cannot be reached through them.

**Q7. Explain an exception hierarchy in the project.**
`IngestStoreError` is the base, with `JobConflict`, `QueueFull`, `InvalidTransition` and `StoreCorrupt` as subclasses. Routes can catch the specific case to return the right HTTP status, or the base class for a general failure. `ApiError` carries a status and a safe code, and its constructor rejects unknown codes.

**Q8. What is a state-machine object here?**
`QuestionAttempt`. Its states are generating, answered, failed and stopped. Each terminal method (`complete`, `fail`, `stop`) runs at most once and writes only if the database still shows this attempt as the owner (`ownedFilter()`). A superseded attempt therefore cannot overwrite a newer one.

**Q9. Why do Pydantic models use `extra="forbid"`?**
Unknown fields are rejected. A client cannot slip in a field such as `workspace_id` to change behaviour; the workspace must come from the verified token. It also catches contract typos early.

**Q10. What is the drawback of the locking proxy?**
It serialises every call, including reads, so only one Qdrant operation runs at a time inside the process. That is acceptable for a single-node demo and was needed for correctness, but it limits throughput. A Qdrant server (`QDRANT_URL`) is not wrapped and does not have this limit.

## 7. References

- [System architecture](../architecture/SYSTEM_ARCHITECTURE.md): frontend and backend structure
- [Authentication and security §3](../technical/AUTHENTICATION_AND_SECURITY.md#3-authorization-workspace-ownership): workspace ownership
- [Chat and streaming §5](../technical/CHAT_AND_STREAMING.md#5-message-persistence-states): message persistence states
- [Contributions](../../CONTRIBUTIONS.md): who built which part
- Internal verification records (not published): workspace isolation (Task 5), failed/stopped question persistence (Task 19). The original architecture decisions are in the project source (`team4c/docs/decisions.md`)
- Related subjects: [03 DBMS](03_Database_Management_Systems.md), [04 OS](04_Operating_Systems.md), [06 Software Engineering](06_Software_Engineering.md)
