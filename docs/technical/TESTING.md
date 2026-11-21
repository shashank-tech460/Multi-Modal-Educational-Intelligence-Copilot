# Testing and Quality

This document reports **real results only**. Each suite is reported **separately**, because combining them into one "pass rate" would hide the exceptions.

---

## 1. Final results (re-run on the final integrated snapshot, 21 Nov 2026)

The checks below were run on a clean export of the final integrated commit, in a separate folder, with freshly installed dependencies.

| Test category | Result | Details | Limitations |
|---|---|---|---|
| Backend tests | **798 passed, 5 skipped, 8 xfailed, 0 failed** | `pytest -q`, about 84 s | Skips and expected failures explained in §2 |
| TypeScript type check | **Clean** (exit code 0) | `npx tsc --noEmit --incremental false` | — |
| ESLint | **12 problems** (9 errors, 3 warnings) | `npx eslint` | Pre-existing, mostly in test files (§4) |
| Frontend unit + component | **1,634 of 1,635 passed** | `npx vitest run`, 119 files | One timing-sensitive failure (see below) |
| Production build | **Succeeded** | `npx next build`, 21 routes compiled | — |
| Browser end-to-end, live demo, AI benchmark | **Not re-run** | Need the full local stack | Only earlier recorded results exist (§3) |

### About the one frontend failure

In the full run, one test in the conversation-sidebar **rename** suite ("compatibility: renaming a conversation on an older page...") failed. Run on its own, the same file passed **3 out of 3 times** (20/20 tests each time). It looks **timing-sensitive under full-suite load**: the full run executes many jsdom test files in parallel. This is recorded as an **intermittent result, not a clean full-suite pass**. Earlier project records show a 1,635/1,635 full run, but that did not repeat on this run.

### Environment of the re-run

Windows 11, Python 3.11, Node.js 22.17 (one dependency warned that it prefers Node ≥ 22.19), dependencies installed with `npm ci`.

---

## 2. Skipped and expected failures (backend)

| Kind | Count | Reason |
|---|---|---|
| Skipped | 4 | Interoperability tests that need token and key files produced by a separate interop script (they passed when run with those inputs) |
| Skipped | 1 | A conditional skip inside a production-hardening test (that case is covered by another test) |
| xfail | 8 | **Known defects**, recorded on purpose as non-strict expected failures: Indic-script PDF text extraction (4) and BM25 tokenisation of Indic words (4). If they are fixed, they will show up as "XPASS" instead of silently changing |

---

## 3. Not re-run for this portfolio

These need the full local stack (MongoDB, Ollama with models, both services, the launcher), which is outside this repository:

| Not re-run | Last recorded result (from project reports, 20 Nov 2026) |
|---|---|
| 30-step browser workflow, desktop 1440×900 | 30 / 30 |
| 30-step browser workflow, mobile 390×844 | 29 / 30. The failed step was a backend "not enough context" decline (an open answer-quality issue) |
| Repository Playwright specs | Desktop: accessibility 5/5 and several workflow specs passed. One spec had an outdated selector, and one failed on an identical follow-up answer from the backend. Mobile: 10/14 (some specs are desktop-only) |
| Workspace isolation (live) | 118 / 118 checks |
| Database index check | 12 / 12 on an isolated test database; the live database was not re-checked |
| AI answer-quality benchmark | Run during the project; results fed the answer-quality handover |

These are **recorded results, not re-verified now**.

---

## 4. Known test and quality issues

| Issue | Type |
|---|---|
| 9 ESLint errors: `no-explicit-any` in two test files | Test code |
| 3 ESLint warnings: two unused variables, one React Compiler warning about the virtualiser library | Minor |
| Rename test intermittent in the full Vitest run | Test timing |
| Browser specs: some desktop-only, one outdated selector after the rename feature was added, hard-coded `localhost:3000` base URL | Test code |
| Backend tests fail with Qdrant lock errors if run next to a running backend using the same local Qdrant folder | Environment; isolated runs pass |
| Mongoose deprecation warning during tests | Cosmetic |

---

## 5. Testing approach

### Unit testing
Small pieces in isolation: validation rules, rate limiter, cursor encoding, citation mapping, token minting, stream-event parsing, Zustand stores, the follow-up detector and decline detector (backend).

*Example:* the decline detector is tested with answers like "Not mentioned." and Hindi declines, and with a partial answer that only *later* mentions a gap (which must keep its citations).

### Component testing
React components rendered in **jsdom** with **React Testing Library**, tested the way a user interacts: typing, clicking, keyboard navigation, and accessible names.

*Example:* the chat panel shows a "Stop generating" button while streaming, and the question is saved as stopped.

### Integration testing (backend)
FastAPI routes through a test client with real modules but in-memory stores (embedded `:memory:` Qdrant, FakeRedis) and fake models:
- **service auth:** wrong algorithm, wrong audience, expired token, replayed `jti`, missing keys (must be 503);
- **workspace isolation:** a token for workspace A must never return workspace B's chunks or sessions;
- **ingestion:** generations, activation, cleanup, allowlisted origins, YouTube timestamps;
- **streaming:** event order, verification before deltas, draft events never saved;
- **production hardening:** allowlist returns 404 for legacy routes; unsafe settings stop startup.

### Property-based testing
**Hypothesis** (used in Team 4A/4B's backend tests) generates many random inputs to check invariants. For example, RRF output is deduplicated, every score is between 0 and 1, and results come out sorted. Other checks: invalid chunk payloads are never written, and conversation memory stays ordered, bounded and isolated.

### API testing
Route handlers are tested with mocked database and backend clients for every status code: 401, 404 for non-owners, 409 duplicates, 429 rate limits.

### Browser (end-to-end) testing
**Playwright** drives a real browser against the running stack: sign-up → workspace → upload → ask → citation opens the page / seeks the video → logout. Accessibility is checked with **axe-core**.

### Build validation
`tsc --noEmit` (types) and `next build` (production compile) catch errors that tests might miss.

### Security testing
Mostly automated negative tests (above), plus **live fault-injection checks** recorded in the project reports. For example, MongoDB was made unreachable during login and logout to verify that the app fails safely. No external penetration test was done.

---

## 6. Local results vs production verification

All results here are from **local** runs. **No production deployment was tested**, because none exists. See [Deployment](../guides/DEPLOYMENT.md).
