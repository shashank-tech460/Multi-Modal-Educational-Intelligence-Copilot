# Challenges and Solutions

Real problems found during the project, how they were investigated, and how they were fixed. These come from the project's verification reports. Each one makes a strong "tell me about a bug you fixed" story.

Use the **STAR** format when speaking: *Situation, Task, Action, Result*.

---

## 1. Logout did not really log you out (race condition)

- **Symptom:** in a browser test, after clicking Logout, the API still returned data and the workspace page still opened.
- **Investigation:** the problem was reproduced deterministically. A session-refresh request (`/api/auth/session`) that was **already in flight** when Logout was clicked came back **after** logout and **re-set the old cookie**. Because Auth.js JWT sessions are **stateless**, the old token was still valid.
- **Fix:** each sign-in now gets a random **session id (`sid`)** inside the JWT. Logout records the `sid` as **revoked** (in MongoDB with a TTL index). The JWT callback rejects revoked sessions, so a re-set stale cookie is useless. Later, tokens without a `sid` were also rejected, because they could never be revoked.
- **Lesson:** stateless tokens need a **revocation strategy**. Concurrency bugs need deterministic reproduction.

## 2. Logout during a database outage (two rounds)

- **Round 1:** with MongoDB made unreachable (through a local fault proxy), the revocation check **failed open**: a stale logged-out cookie counted as signed in. **Fix:** revocations are also kept **in process memory**, which is checked first.
- **Round 2 (found in the final regression):** a logout made *during* the outage was **never written** to MongoDB. After recovery, another instance, or the same one after a restart, accepted the logged-out session. **Fix:** revocations that failed to persist are **queued and written** as soon as the database is back.
- **Lesson:** test failure modes, not just happy paths, and think about **multiple instances and restarts**.

## 3. "Invalid email or password" for a correct password

- **Case A (database outage):** a database error escaped the authorizer, and Auth.js reported it as a credentials failure. **Fix:** a distinct `service_unavailable` code and the message "Sign-in is temporarily unavailable". It is the same for every email, so it reveals nothing about which accounts exist.
- **Case B (first login after a dev-server restart):** several parallel session requests on a cold server each minted a **new CSRF cookie**, so the token sent with the login no longer matched. Fixed on the client side, with a neutral message and retry for CSRF failures.
- **Lesson:** misleading error messages waste users' time. Map each failure to an honest message.

## 4. Students briefly saw answers that were then withdrawn

- **Symptom:** the backend streamed the model's raw text as it was generated. If verification then rejected the answer, the student had already seen it, and a refresh showed "not enough context" instead.
- **Fix:** **verify first, then stream.** The backend holds the model's output until the decline, support and citation checks pass, then streams the verified answer. An optional, clearly labelled **draft** preview shows progress without being saved.
- **Lesson:** in AI products, **what the user sees must be what you stand behind**.

## 5. Refusals that still carried citations

- **Symptom:** answers such as "no information was found about this" (in Hindi), a bare "no", or the question echoed back still showed **7–8 citation chips**, which made them look grounded.
- **Fix:** decline and echo detection (English and Hindi; a whole answer or its leading sentence). Declines lose their citations and become the standard "not enough context" answer. The chat route also drops citations whenever retrieval returned nothing.
- **Lesson:** citations are a **trust signal**. A wrong citation is worse than none.

## 6. Ownership vs isolation across two services

- **Challenge:** the backend holds every student's chunks. How can it know which workspace a request may read?
- **Solution:** the Next.js server checks ownership in MongoDB, then signs a **5-minute ES256 token** with that `workspace_id`. The backend trusts **only** the token: the algorithm is pinned, `aud`/`scope` are checked, and each `jti` is single use. Every query filters by the token's workspace, plus a final scope check in code.
- **Verification:** 118 out of 118 live cross-user checks passed.
- **Lesson:** **never trust the client**, not even your own frontend's request body.

## 7. The backend could not download uploaded files

- **Symptom:** PDF ingestion failed with 401. The backend fetches the `file_url` server-to-server, **without a browser cookie**, but the file route required a session.
- **Fix:** a **capability URL**: an HS256 token in the query string, valid for **10 minutes** and bound to that exact workspace and file. It works like a presigned URL in object storage. The backend also fetches only from **allowlisted origins**.
- **Lesson:** design auth for **machine-to-machine** paths, not only for browsers.

## 8. Duplicate uploads and race conditions

- **Symptom:** uploading the same PDF twice created two copies, with duplicate citation chips and crowded retrieval.
- **Fix:** SHA-256 of the content plus a **unique partial index** `{workspaceId, contentSha256}`, so even two simultaneous uploads cannot both win. The same approach was used for YouTube (`youtubeVideoId`) and for upload retries (idempotency key). Questions are stored once using `{conversationId, clientMessageId}`.
- **Lesson:** enforce uniqueness in the **database**, not just in application code.

## 9. Files stuck in "processing" forever

- **Challenge:** ingestion runs inside the upload request. If the server dies mid-way, nothing ever marks the file as failed, and there is no job queue.
- **Fix:** a **lease**: the attempt renews a timestamp every 30 s, and after 6 minutes without renewal the file is "abandoned". One atomic `updateMany` marks such files as failed (Retry then works). Every status write is **conditional on still owning the lease**, so a late result cannot overwrite a newer retry.
- **Lesson:** distributed systems need **leases and fencing** to recover from crashes safely.

## 10. Citations showed meaningless file names

- **Symptom:** citation chips showed names like `839acd8e...pdf` instead of "OS-Unit3.pdf".
- **Root cause:** the backend's `document_title` was the **storage name**, not the student's file name.
- **Fix:** the display name always comes from MongoDB (`File.originalName`), looked up by `document_id` within the authorised workspace.
- **Lesson:** each service should be the source of truth for its **own** data.

## 11. YouTube network errors reported as "no captions"

- **Symptom:** when YouTube was unreachable, students were told the video "may be private or have no captions".
- **Root cause:** errors were classified by exception **class name**, and proxy, SSL and chunked-encoding errors fell through to "no text".
- **Fix:** a transport-failure classifier, so network errors become retryable failures with an accurate message. The frontend also stopped showing a green "Material added" toast for a YouTube link that failed.

## 12. Embedded Qdrant is single-process

- **Symptom:** backend tests produced dozens of errors when run on a machine where the demo backend was running.
- **Root cause:** embedded Qdrant **locks its folder** for one process, and its client is not thread-safe.
- **Handling:** all embedded Qdrant calls are serialised, and tests run in isolation (798 passed). For production, the recommendation is a separate Qdrant server.

## 13. Accessibility issues found by automated checks

- Identical "Delete" buttons on every material card → `aria-label="Delete {file name}"`.
- An `aria-label` on a plain `div` → `role="region"`.
- A chat area that keyboard users could not scroll → focusable region with a label.
- **Lesson:** tools like axe-core catch real barriers early.

---

## Open challenges (be honest about these)

- Some follow-up questions return the **identical answer**, and the tutor sometimes **declines** when the material does contain the answer. These were investigated, with evidence and proposals handed to the RAG owners.
- The backend session and the MongoDB history can **diverge**.
- The system is a **single-host** design; it was not deployed to production.
