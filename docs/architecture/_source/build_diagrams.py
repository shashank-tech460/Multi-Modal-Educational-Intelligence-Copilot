"""Builds the six EduCopilot architecture diagrams (documentation + 16:9 presentation SVGs).

Usage:  python build_diagrams.py            (writes SVGs into ../<diagram-folder>/)
PNG files are rendered from these SVGs with a headless browser (see ../README.md).

All facts come from the verified final integrated build and this portfolio's technical documents.
"""
from __future__ import annotations

import os
import sys

from diagramkit import Canvas, INK, MUTED, documentation_svg, presentation_svg

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.dirname(HERE)

DIAGRAMS = []


def diagram(folder, name, title, subtitle, tagline, notes, legend_extra):
    def wrap(fn):
        DIAGRAMS.append(dict(folder=folder, name=name, title=title, subtitle=subtitle, tagline=tagline,
                             notes=notes, legend_extra=legend_extra, draw=fn))
        return fn
    return wrap


FLOW = [("badge", "Numbered step in the flow"), ("flow", "Request or data flow")]


# ===================================================================== P1 complete system
@diagram("complete-system", "complete-system-architecture",
         "Complete System Architecture",
         "How a student's request moves through the Team 4C Next.js application, the joint FastAPI backend and the data and model services",
         "Two application services · Team 4C application and integration layer · joint Team 4A/4B backend",
         ["Local demo ports: Next.js 3000, FastAPI 8001, Ollama 11434. Qdrant runs embedded inside the backend process (no separate server).",
          "The browser never calls the backend. Next.js checks the session and workspace ownership, then signs a 5-minute ES256 token naming one workspace.",
          "The backend trusts only the token's workspace_id: every query filters Qdrant, the ingest registry and conversation memory by it.",
          "The Next.js app keeps two logical backend clients (Team A ingestion, Team B query; separate URLs and token audiences). In the integrated demo both point to the same FastAPI process.",
          "Only Next.js reads or writes MongoDB. The FastAPI backend has no MongoDB dependency.",
          "In local/demo storage mode the backend uses in-process FakeRedis and embedded Qdrant; servers for them are used only in external storage mode. The demo ran over HTTP on localhost.",
          "Team 4A / 4B labels follow the original team responsibilities; per-file authorship inside the joint backend is not recorded.",
          "Hardened for a controlled single host; not deployed to production."],
         FLOW + [("both", "Double arrowhead: request and response")])
def p1(c: Canvas):
    # student and MongoDB (left)
    c.box(40, 95, 220, 110, "Student", "Web browser", kind="ext")
    c.cylinder(40, 690, 220, 130, "MongoDB", "users · workspaces · conversations · messages · files · revokedsessions")

    # Next.js application
    c.group(300, 40, 420, 600, "Next.js application  ·  :3000", "app", "Team 4C")
    c.box(330, 100, 180, 90, "React 19 UI", "chat · materials · video player · history", kind="app")
    c.box(530, 100, 170, 90, "Service-token signer", "ES256 · 5-minute tokens", kind="auth")
    c.box(330, 220, 370, 100, "Server route handlers",
          "/api/workspaces · /files · /chat · /conversations · /local-storage", kind="app")
    c.box(330, 350, 180, 100, "Auth.js", "credentials · bcrypt · JWT cookie · sid revocation", kind="auth")
    c.box(530, 350, 170, 100, "Ownership checks", "Workspace → Conversation / File · 404", kind="auth")
    c.cylinder(330, 480, 180, 130, "Local upload folder", "PDF bytes per workspace")
    c.box(530, 480, 170, 130, "Chat stream adapter", "Vercel AI SDK UI stream · citation mapping", kind="app")
    c.arrow([(420, 190), (420, 220)])
    c.arrow([(615, 220), (615, 190)])
    c.arrow([(420, 320), (420, 350)])
    c.arrow([(615, 320), (615, 350)])
    c.arrow([(615, 450), (615, 480)])
    c.arrow([(330, 300), (316, 300), (316, 545), (330, 545)])

    # FastAPI backend
    c.group(860, 40, 700, 600, "FastAPI backend  ·  :8001  ·  one process", "neutral")
    c.group(870, 72, 680, 232, "Team 4C integration layer", "auth", dashed=True, label_size=13)
    c.box(885, 100, 650, 66, "Service-token verifier",
          "ES256 · kid in JWKS · iss · aud · scope · lifetime ≤ 300 s · single-use jti · production allowlist",
          kind="auth", body_size=12)
    c.box(885, 200, 310, 92, "Ingestion API", "POST /v1/ingest · jobs · DELETE /v1/documents/{id} · PDF fetch + pypdf pages · generations",
          kind="auth", body_size=12)
    c.box(1235, 200, 300, 92, "Query API", "POST /api/v1/query · POST /api/v1/query/stream (NDJSON) · sessions",
          kind="auth", body_size=12)
    c.arrow([(1040, 166), (1040, 200)])
    c.arrow([(1385, 166), (1385, 200)])
    c.group(870, 318, 680, 150, "Joint Team 4A/4B capabilities", "core", dashed=True, label_size=13, label_x=1056)
    c.box(885, 346, 315, 108, "Ingestion core  (Team 4A)",
          "YouTube caption processor · structure-aware chunker · embedding calls", kind="core", body_size=12)
    c.box(1235, 346, 300, 108, "Retrieval and generation  (Team 4B)",
          "BM25 + vector search · RRF (k = 60) · prompt with JSON output · conversation memory", kind="core", body_size=12)
    c.arrow([(1040, 292), (1040, 346)])
    c.arrow([(1385, 292), (1385, 346)])
    c.group(870, 480, 680, 148, "In-process stores", "neutral", dashed=True, label_size=13, label_x=1152)
    c.cylinder(885, 504, 145, 116, "Ingest registry", "JSON on disk · jobs · active generation", body_size=11.5)
    c.cylinder(1080, 504, 260, 116, "Qdrant (embedded)", "cosine · 384-d vectors · payload: workspace_id, document_id, page / timestamps, generation", body_size=11.5)
    c.box(1370, 504, 165, 116, "Conversation memory", "FakeRedis in-process (local mode) · 30-min TTL", kind="store", body_size=11.5)
    c.arrow([(957, 454), (957, 504)])
    c.arrow([(1140, 454), (1140, 504)])
    c.arrow([(1290, 454), (1290, 504)])
    c.arrow([(1452, 454), (1452, 504)])

    # external
    c.box(870, 700, 190, 110, "YouTube", "timed captions · video title", kind="ext")
    c.box(1120, 700, 430, 110, "Ollama  ·  :11434", "llama3:latest — answer generation\nall-minilm — embeddings (384-d)", kind="ext")
    c.arrow([(1045, 454), (1045, 700)])
    c.arrow([(1065, 454), (1065, 660), (1180, 660), (1180, 700)])
    c.arrow([(1355, 454), (1355, 700)])

    # numbered flows
    c.arrow([(260, 145), (330, 145)], both=True)
    c.badge(295, 125, 1)
    c.label(268, 172, "HTTP", size=11.5)
    c.arrow([(330, 270), (150, 270), (150, 690)], both=True)
    c.badge(150, 420, 2)
    c.label(166, 450, "Mongoose", size=11.5)
    c.label(166, 466, "app data", size=11.5)
    c.arrow([(700, 145), (885, 145)], both=True)
    c.badge(790, 112, 3)
    c.label(727, 162, "ES256 JWT · JSON / NDJSON", size=11)
    c.arrow([(885, 252), (700, 252)])
    c.badge(790, 232, 4)
    c.label(714, 272, "GET PDF (capability URL)", size=11)
    c.badge(1045, 680, 5)
    c.label(990, 650, "captions", size=11.5, anchor="end")
    c.badge(1122, 645, 6)
    c.label(1196, 690, "embed", size=11.5)
    c.badge(1355, 672, 7)
    c.label(1372, 650, "embed query · generate answer", size=11.5)


# ===================================================================== P2 ingestion
@diagram("ingestion", "ingestion-architecture",
         "PDF and YouTube Ingestion Architecture",
         "Two separate input paths that join one common backend pipeline, from upload to searchable, citable chunks",
         "Separate PDF and YouTube paths · common chunk → embed → index → activate pipeline",
         ["Ingestion is synchronous: POST /v1/ingest returns 200 only after the chunks are indexed and the new generation is activated. The upload request waits up to 5 minutes.",
          "Generations: each ingestion gets a new generation number. A failed attempt leaves the previous generation active; partial chunks are never searchable.",
          "Chunk limits: at most 1,200 characters, and the embedding text must fit a 512-token budget counted as bytes (about 496 bytes). The byte budget is usually the tighter limit.",
          "Pages without a text layer (scanned PDFs) produce no text; OCR is not on this path. MP4 uploads are rejected. YouTube videos without captions cannot be ingested.",
          "A processing lease (renewed every 30 s, expires after 6 min) lets the app recover files left in 'processing' after a crash."],
         FLOW)
def p2(c: Canvas):
    xs = [40, 300, 560, 820, 1080, 1340]
    w = 220
    c.text(40, 58, "PDF path", size=14, weight="700", color="#1E3A8A")
    a = [("Student uploads PDF", "XHR upload with byte progress", "ext"),
         ("Files route (Next.js)", "session + ownership · type PDF · ≤ 50 MB · SHA-256 of content", "app"),
         ("Duplicate check", "unique (workspaceId, contentSha256) · duplicate → reuse existing File", "app"),
         ("Store and register", "bytes → local upload folder · File = processing + lease", "app"),
         ("POST /v1/ingest", "file_type pdf · file_url = 10-min capability URL · ES256 token", "auth"),
         ("Fetch and extract", "allowed origin only · size + %PDF- check · pypdf text page by page", "auth")]
    for i, (t, b, k) in enumerate(a):
        c.box(xs[i], 70, w, 120, t, b, kind=k, body_size=12)
    c.text(40, 238, "YouTube path", size=14, weight="700", color="#1E3A8A")
    yb = [("Student adds YouTube link", "link entered in the materials panel", "ext"),
          ("Files route (Next.js)", "session + ownership · extract 11-character video id", "app"),
          ("Duplicate check", "unique (workspaceId, youtubeVideoId) · same video in progress → 409", "app"),
          ("Register (no bytes)", "File type youtube_url = processing + lease", "app"),
          ("POST /v1/ingest", "file_type youtube · file_url = YouTube URL · ES256 token", "auth"),
          ("Fetch captions", "Team 4A caption processor · English preferred, else own track · title via yt-dlp", "core")]
    for i, (t, b, k) in enumerate(yb):
        c.box(xs[i], 250, w, 120, t, b, kind=k, body_size=12)
    for i in range(5):
        x1, x2 = xs[i] + w, xs[i + 1]
        c.arrow([(x1, 130), (x2, 130)])
        c.badge((x1 + x2) / 2, 108, i + 1)
        c.arrow([(x1, 310), (x2, 310)])
        c.badge((x1 + x2) / 2, 288, i + 1)
    c.text(40, 458, "Common ingestion pipeline (FastAPI backend)", size=14, weight="700", color="#064E3B")
    common = [(1340, "Structure-aware chunking", "Team 4A/4B chunker · PDF chunks never cross pages (page_number) · captions → whole segments (start/end seconds)", "core"),
              (1080, "Embeddings", "all-minilm via Ollama · 384-d · length checked against VECTOR_SIZE", "core"),
              (820, "Qdrant upsert", "tenant collection · payload workspace_id, document_id, generation", "store"),
              (560, "Activate generation", "ingest registry marks it active · older generations deleted", "auth"),
              (300, "Response", "200 {state: ready, chunks_indexed} · errors → error envelope", "auth"),
              (40, "File status = ready", "or failed with a student-friendly message and Retry", "app")]
    for x, t, b, k in common:
        if k == "store":
            c.cylinder(x, 470, w, 130, t, b, body_size=12)
        else:
            c.box(x, 470, w, 130, t, b, kind=k, body_size=12)
    # joins into the common pipeline
    c.arrow([(1560, 130), (1585, 130), (1585, 520), (1560, 520)])
    c.arrow([(1450, 370), (1450, 470)])
    c.badge(1585, 330, 6)
    c.badge(1450, 420, 6)
    for i in range(5):
        x1 = common[i][0]
        x2 = common[i + 1][0] + w
        c.arrow([(x1, 535), (x2, 535)])
        c.badge((x1 + x2) / 2, 513, i + 7)
    # lifecycle inset
    c.group(30, 650, 800, 200, "File status lifecycle (MongoDB File.status)", "neutral", dashed=True, label_size=13)
    c.box(60, 712, 150, 52, "uploading", kind="app", title_size=14, mono_title=True)
    c.box(280, 712, 160, 52, "processing", kind="app", title_size=14, mono_title=True)
    c.box(560, 690, 150, 46, "ready", kind="core", title_size=14, mono_title=True)
    c.box(560, 780, 150, 46, "failed", kind="warn", title_size=14, mono_title=True)
    c.arrow([(210, 738), (280, 738)])
    c.arrow([(440, 728), (560, 713)])
    c.arrow([(440, 750), (560, 798)])
    c.arrow([(560, 815), (360, 815), (360, 764)])
    c.label(450, 708, "indexed", size=11)
    c.label(722, 808, "error · timeout · lease expired", size=11)
    c.label(372, 834, "Retry", size=11)
    c.group(870, 650, 700, 200, "Rules on this path", "neutral", dashed=True, label_size=13)
    c.note(890, 700, ["• Synchronous call: the backend answers only after indexing and activation.",
                      "• Re-ingestion is safe: a failed attempt keeps the previous generation active.",
                      "• The backend fetches files only from INGEST_ALLOWED_ORIGINS and never logs the URL.",
                      "• No OCR for scanned pages · MP4 rejected · videos need captions."], size=13, color=INK)


# ===================================================================== P3 RAG
@diagram("rag-pipeline", "rag-pipeline-architecture",
         "RAG Pipeline Architecture",
         "From a student's question to a verified, cited answer, or an honest refusal, inside one workspace",
         "Hybrid retrieval (BM25 + vectors, RRF) · grounded generation · verification before streaming",
         ["Search mode is always hybrid in EduCopilot. Each search returns up to 50 candidates (TOP_K_MAX).",
          "RRF: score = Σ 1 / (60 + rank) over both rankings, divided by the best possible score (2/61), so scores fall between 0 and 1.",
          "The score threshold is ONE setting (SCORE_THRESHOLD_DEFAULT): the code default is 0.5 and the demo launcher set it to 0.25. They are alternatives, not two filters.",
          "Verification reduces unsupported answers but does not guarantee correctness: the support check is a coarse word-overlap test.",
          "Generation settings: llama3:latest, temperature 0, at most 512 output tokens, 8,192-token context, JSON schema output."],
         FLOW + [("flow", "Branch: verified answer or refusal")])
def p3(c: Canvas):
    c.box(40, 60, 200, 110, "Student question", "≤ 2,000 characters", kind="ext")
    c.box(290, 60, 270, 110, "Follow-up detection", "adds the conversation topic to the search query (English and Hindi); the model still sees the original question", kind="auth", body_size=12)
    c.box(610, 60, 290, 110, "Retrieval scope", "workspace_id from the verified token · selected document_ids · active generation per document", kind="auth", body_size=12)
    c.box(980, 40, 280, 110, "Vector search", "embed query (all-minilm) → Qdrant cosine, workspace filter · up to 50", kind="core", body_size=12)
    c.box(980, 190, 280, 110, "BM25 keyword search", "rank-bm25 over in-scope chunks (≤ 10,000) · \\w+ tokens · up to 50", kind="core", body_size=12)
    c.box(1320, 100, 240, 140, "Reciprocal Rank Fusion", "Σ 1 / (60 + rank) · normalised to 0–1", kind="core")
    c.arrow([(240, 115), (290, 115)]); c.badge(265, 93, 1)
    c.arrow([(560, 115), (610, 115)]); c.badge(585, 93, 2)
    c.arrow([(900, 115), (940, 115), (940, 95), (980, 95)])
    c.arrow([(940, 115), (940, 245), (980, 245)])
    c.badge(940, 170, 3)
    c.arrow([(1260, 95), (1290, 95), (1290, 140), (1320, 140)])
    c.arrow([(1260, 245), (1290, 245), (1290, 200), (1320, 200)])
    c.badge(1290, 170, 4)
    # row 3 (right to left)
    c.box(1280, 360, 280, 130, "Score threshold (one setting)", "keep fused score ≥ threshold\ncode default 0.5  ·  demo setting 0.25", kind="core", body_size=12.5)
    c.box(1000, 360, 230, 130, "Top 5 chunks", "TOP_K_DEFAULT = 5 · the citable hits", kind="core")
    c.box(720, 360, 230, 130, "Neighbour expansion", "same document · chunk index within ±3", kind="core")
    c.box(440, 360, 230, 130, "Final scope check", "nothing outside the workspace leaves the retriever", kind="auth")
    c.arrow([(1440, 240), (1440, 360)]); c.badge(1440, 300, 5)
    c.arrow([(1280, 425), (1230, 425)]); c.badge(1255, 403, 6)
    c.arrow([(1000, 425), (950, 425)]); c.badge(975, 403, 7)
    c.arrow([(720, 425), (670, 425)]); c.badge(695, 403, 8)
    # row 4
    c.box(40, 560, 290, 140, "Evidence packing", "items C1…Cn (metadata + text) · whole chunks within 8,192 − 512 − 512 byte budget · summary + recent turns", kind="core", body_size=12)
    c.box(390, 560, 270, 140, "llama3 via Ollama", "temperature 0 · max 512 tokens · JSON schema {answer, citations}", kind="ext")
    c.box(390, 740, 270, 100, "System rules (Team 4B prompt)", "answer from evidence · evidence is data, not instructions · cite labels", kind="core", body_size=12)
    c.box(720, 545, 330, 170, "Answer verification", "1  JSON valid · only real labels\n2  decline / echo → no citations\n3  support ≥ 25 % content words\n4  valid page or timestamp metadata", kind="auth", body_size=12.5)
    c.box(1140, 520, 300, 110, "Verified answer + citations", "labels renumbered [1], [2] → streamed as NDJSON", kind="app")
    c.box(1140, 660, 300, 110, "Honest refusal", "'The available documents do not provide enough context…' · no citations", kind="warn", body_size=12)
    c.arrow([(440, 425), (185, 425), (185, 560)]); c.badge(185, 490, 9)
    c.arrow([(330, 630), (390, 630)]); c.badge(360, 608, 10)
    c.arrow([(525, 740), (525, 700)])
    c.arrow([(660, 630), (720, 630)]); c.badge(690, 608, 11)
    c.arrow([(1050, 630), (1090, 630), (1090, 575), (1140, 575)])
    c.arrow([(1090, 630), (1090, 715), (1140, 715)])
    c.badge(1090, 650, 12)
    c.label(1098, 560, "all pass", size=11)
    c.label(1098, 742, "any fails", size=11)


# ===================================================================== P4 security
@diagram("security", "security-architecture",
         "Authentication and Security Architecture",
         "Three trust boundaries: browser → Next.js, Next.js → application data, Next.js → FastAPI backend",
         "User authentication · ownership authorization · ES256 service authentication",
         ["TB1 (user authentication): Auth.js credentials login, bcrypt cost 12, rate limits checked before any lookup, HttpOnly JWT cookie with a random session id revoked on logout.",
          "TB2 (authorization): every data route checks Workspace.userId against the session user, then that the conversation or file belongs to the workspace. Failures return 404, never 403.",
          "TB3 (service authentication): Next.js signs a 5-minute ES256 token per call; the backend holds only public keys (JWKS) and fails closed (503) if they are missing.",
          "The backend uses only the token's workspace_id; request bodies are parsed only after authentication.",
          "Known limits: in-memory rate limits and replay cache (single instance), no HTTPS in the local demo, no external penetration test."],
         FLOW + [("boundary", "Trust boundary (TB1–TB3)")])
def p4(c: Canvas):
    c.boundary_line(265, 20, 265, 850, "TB1 · user authentication", 272, 34)
    c.boundary_line(1060, 20, 1060, 850, "TB3 · service authentication", 1067, 34)
    c.box(40, 70, 190, 90, "Student browser", kind="ext")
    c.box(40, 200, 190, 80, "Login form", "email + password + CSRF token", kind="ext")
    c.box(40, 330, 190, 80, "Session cookie", "HttpOnly JWT", kind="ext")
    c.box(40, 450, 190, 80, "API request", "cookie sent with every call", kind="ext")
    c.group(290, 40, 730, 800, "Next.js application  (Team 4C)", "app")
    c.box(320, 80, 320, 85, "Rate limits", "sign-in: 10 / email · 30 / IP per 15 min · 300 / min global · sign-up limits per hour", kind="auth", body_size=12)
    c.box(320, 190, 320, 85, "Credentials authorize", "bcrypt cost 12 · dummy-hash compare for unknown email · one generic error", kind="auth", body_size=12)
    c.box(320, 300, 320, 85, "JWT session (Auth.js)", "signed with AUTH_SECRET · random session id (sid)", kind="auth", body_size=12)
    c.box(320, 410, 320, 85, "Revocation check", "every request: sid checked in memory, then revokedsessions", kind="auth", body_size=12)
    c.box(680, 80, 310, 85, "Route guard (proxy.ts)", "page requests: signed-out → /login with a safe callback URL", kind="app", body_size=12)
    c.box(680, 190, 310, 85, "Route handler", "no session → 401 · input validation", kind="app", body_size=12)
    c.box(680, 300, 310, 110, "Ownership check", "Workspace.userId = session user → conversation / file in that workspace · else 404", kind="auth", body_size=12)
    c.box(680, 450, 310, 110, "Service-token signer", "ES256, private key only here · sub, workspace_id, aud, scope, iss, iat, exp +300 s, jti", kind="auth", body_size=12)
    c.boundary_line(300, 650, 1010, 650, "TB2 · authorization (ownership) before any data access", 310, 674)
    c.cylinder(680, 690, 310, 125, "MongoDB", "users · workspaces · conversations · messages · files · revokedsessions (TTL)", body_size=12)
    c.box(320, 690, 320, 125, "File capability URL", "HS256 · 10 minutes · one workspace + file · backend fetches only from allowed origins", kind="auth", body_size=12)
    c.group(1090, 40, 480, 800, "FastAPI backend", "neutral", "joint Team 4A/4B backend + Team 4C integration layer")
    c.box(1120, 90, 420, 100, "Production route allowlist", "ENVIRONMENT=production: integration routes + /healthz only · docs off · unsafe settings stop startup", kind="auth", body_size=12)
    c.box(1120, 220, 420, 90, "Audiences and scopes", "team4a-ingestion → ingest · team4b-query → query", kind="auth", body_size=12.5)
    c.box(1120, 395, 420, 230, "Service-token verifier",
          "alg ES256 only · no jwk / jku / x5u / x5c / crit headers\nkid must be in the JWKS (public keys)\nsignature · exact iss and aud · scope matches audience\nlifetime ≤ 300 s (30 s leeway) · iat not in future\njti used once (replay cache)\nkeys missing → 503 for every protected route",
          kind="auth", body_size=12.5)
    c.box(1120, 680, 420, 130, "Workspace-scoped data access", "Qdrant payload filter workspace_id (+ document_ids) · final scope check · registry and session keys per workspace", kind="core", body_size=12)
    # flows
    c.arrow([(230, 240), (305, 240), (305, 122), (320, 122)]); c.badge(283, 222, 1)
    c.arrow([(480, 165), (480, 190)]); c.badge(500, 178, 2)
    c.arrow([(480, 275), (480, 300)])
    c.arrow([(320, 360), (230, 360)]); c.badge(283, 342, 3)
    c.arrow([(230, 475), (320, 475)]); c.badge(283, 457, 4)
    c.arrow([(480, 385), (480, 410)])
    c.arrow([(640, 452), (654, 452), (654, 232), (680, 232)]); c.badge(654, 300, 5)
    c.arrow([(835, 275), (835, 300)]); c.badge(855, 288, 6)
    c.arrow([(835, 410), (835, 450)]); c.badge(855, 430, 7)
    c.arrow([(990, 505), (1120, 505)]); c.badge(1040, 485, 8)
    c.arrow([(1330, 625), (1330, 680)]); c.badge(1350, 652, 9)
    c.arrow([(480, 495), (480, 630), (720, 630), (720, 690)])
    c.arrow([(680, 392), (670, 392), (670, 612), (900, 612), (900, 690)])
    c.label(490, 585, "users · revokedsessions", size=11)
    c.label(910, 603, "ownership reads", size=11)


# ===================================================================== P5 database
@diagram("database", "database-storage-architecture",
         "Database and Storage Architecture",
         "Where every piece of data lives: MongoDB owned by Next.js, and in-process stores owned by the FastAPI backend",
         "MongoDB (6 collections, 12 indexes) · Qdrant · ingest registry · FakeRedis memory · upload folder",
         ["Only the Next.js server accesses MongoDB, through Mongoose. The FastAPI backend has no MongoDB dependency.",
          "The two sides share identifiers, not databases: File._id = document_id; Workspace._id = workspace_id (token claim); Conversation.ragSessionId = session_id.",
          "In local and demo storage modes the backend uses FakeRedis, a library inside the backend process, for conversation memory. A Redis server (REDIS_URL) is used only in external storage mode; the demo ran in local mode, so no Redis server was deployed.",
          "Qdrant also runs embedded inside the backend process in the demo (a folder on disk).",
          "12 MongoDB indexes are created and checked by the db:indexes script; uniqueness rules (duplicate PDFs, duplicate videos, single question storage) depend on them."],
         [("flow", "Relationship (1 : N unless labelled)")])
def p5(c: Canvas):
    c.group(30, 30, 880, 820, "Next.js application  ·  owner of all MongoDB data (Team 4C)", "app")
    c.group(50, 70, 840, 590, "MongoDB (via Mongoose)", "store", dashed=False, label_size=13)
    c.box(70, 110, 250, 140, "users", "_id · name · email (unique, lowercase) · passwordHash (select: false) · createdAt", kind="store", mono_title=True, body_size=12)
    c.box(370, 110, 230, 140, "workspaces", "_id · userId (index) · name · timestamps", kind="store", mono_title=True, body_size=12)
    c.box(650, 110, 220, 180, "conversations", "_id · workspaceId (index) · title · titleSetManually · ragSessionId (unique, sparse) · sourceScopeDocumentIds", kind="store", mono_title=True, body_size=12)
    c.box(370, 330, 230, 260, "files", "_id · workspaceId · userId (indexes) · originalName · type pdf | video | youtube_url · status · storageUrl · contentSha256 (unique per workspace) · youtubeVideoId (unique per workspace) · uploadIdempotencyKey · processing lease", kind="store", mono_title=True, body_size=12)
    c.box(650, 330, 220, 260, "messages", "_id · conversationId (index) · role · content · citations[] {fileId, type, pageNumber | timestampSeconds} · clientMessageId (unique per conversation) · generationState · replyTo", kind="store", mono_title=True, body_size=12)
    c.box(70, 330, 250, 130, "revokedsessions", "_id = session id (sid) · expiresAt (TTL index) · looked up from the login cookie", kind="store", mono_title=True, body_size=12)
    c.arrow([(320, 180), (370, 180)]); c.label(328, 170, "owns", size=11)
    c.arrow([(600, 180), (650, 180)]); c.label(606, 170, "has", size=11)
    c.arrow([(485, 250), (485, 330)]); c.label(493, 296, "contains", size=11)
    c.arrow([(760, 290), (760, 330)]); c.label(768, 315, "has", size=11)
    c.arrow([(650, 460), (600, 460)]); c.label(604, 450, "cites", size=11)
    c.arrow([(300, 250), (300, 300), (340, 300), (340, 520), (370, 520)]); c.label(250, 296, "uploads", size=11)
    c.note(70, 500, ["Ownership chain checked on", "every request: users → workspaces", "→ conversations / files → messages"], size=12)
    c.note(70, 620, ["12 required indexes (db:indexes script)"], size=12)
    c.cylinder(70, 690, 380, 130, "Local upload folder (disk)", "one sub-folder per workspace · random UUID file names · served to the owner or with a capability token")
    c.box(490, 690, 380, 130, "Auth.js JWT sessions", "stateless: no session table · the browser cookie carries user id + sid · logged-out sids stored in revokedsessions", kind="auth", body_size=12)
    c.box(935, 280, 190, 280, "Shared identifiers", "no shared database\n\nFile._id = document_id\n\nWorkspace._id = workspace_id (token)\n\nConversation .ragSessionId = session_id", kind="neutral", body_size=12)
    c.arrow([(910, 420), (935, 420)], dashed=True)
    c.arrow([(1125, 420), (1150, 420)], dashed=True)
    c.group(1150, 30, 420, 820, "FastAPI backend process", "core", "backend-owned stores, all inside one process")
    c.cylinder(1175, 90, 370, 240, "Qdrant tenant collection (embedded)", "one point per chunk · id document_id:g<generation>:<index> · 384-d vector, cosine · payload: workspace_id, document_id, text, source_type, title, page_number | start_seconds / end_seconds, index, generation, heading path", body_size=12)
    c.cylinder(1175, 360, 370, 170, "Ingest registry (JSON files)", "jobs · documents · generation numbers · active generation per document · keyed by workspace", body_size=12)
    c.box(1175, 560, 370, 190, "Conversation memory", "implementation detail: FakeRedis library inside this process (local / demo storage mode) — not a separately deployed service\na Redis server (REDIS_URL) is used only in external storage mode\nrecent turns + summary · key includes workspace · 30-min TTL", kind="core", body_size=12)
    c.note(1175, 790, ["Every read and write is scoped by the token's workspace_id."], size=12)


# ===================================================================== P6 end-to-end
@diagram("end-to-end-flow", "question-answer-flow",
         "End-to-End Question and Answer Flow",
         "One question, step by step, from the browser through Next.js, MongoDB, the FastAPI backend and Ollama, and back",
         "Save first · scoped retrieval · grounded generation · verify before streaming · cited answer",
         ["The question is saved (state generating) before the backend is called, so a failure or Stop never loses it; it is later marked answered, failed or stopped.",
          "The backend streams only after verification. Optional unverified 'draft' events (?draft=1) are shown separately and never saved (not drawn).",
          "If verification fails, step 12 carries the standard 'not enough context' answer with no citations.",
          "Citation display names come from MongoDB (File.originalName), never from the model or the backend.",
          "Stop: the browser aborts the fetch, the abort cancels the backend call, and the question is saved as stopped."],
         FLOW + [("return", "Response / stream back")])
def p6(c: Canvas):
    lanes = [("Browser", "student", "ext", 130), ("Next.js /api/chat", "Team 4C · :3000", "app", 470),
             ("MongoDB", "application data", "store", 790), ("FastAPI backend", "integration layer + 4A/4B core · :8001", "core", 1120),
             ("Ollama", "llama3 · all-minilm · :11434", "ext", 1470)]
    for t, sub, k, x in lanes:
        c.box(x - 125, 20, 250, 64, t, sub, kind=k, body_size=11.5)
        c.el.append(f'<line x1="{x}" y1="84" x2="{x}" y2="850" stroke="#CBD5E1" stroke-width="2" stroke-dasharray="6 6"/>')
    X = {t: x for t, _, _, x in lanes}
    B, N, M, F, O = (X["Browser"], X["Next.js /api/chat"], X["MongoDB"], X["FastAPI backend"], X["Ollama"])
    steps = [
        ("msg", B, N, "POST /api/chat  {messages, workspaceId, conversationId}", False),
        ("self", N, None, ["session · rate limit 20/min · question ≤ 2,000 chars"], False),
        ("msg", N, M, "ownership: workspace + conversation", False),
        ("msg", N, M, "save question (generating) · read source scope", False),
        ("msg", N, F, "POST /api/v1/query/stream + ES256 JWT (team4b-query)", False),
        ("self", F, None, ["verify token · follow-up expansion · scope"], False),
        ("msg", F, O, "embed query (all-minilm)", False),
        ("self", F, None, ["BM25 + Qdrant → RRF → top 5 + neighbours"], False),
        ("msg", F, O, "generate: llama3 · C1…Cn · JSON · temp 0", False),
        ("msg", O, F, "{answer, citations}", True),
        ("self", F, None, ["verify labels · declines · support · metadata"], False),
        ("msg", F, N, "NDJSON: delta … done {answer, source_attributions}", True),
        ("msg", N, M, "keep workspace citations · save answer · auto-title", False),
        ("msg", N, B, "AI SDK UI stream: text + data-citations", True),
        ("self", B, None, ["chips: PDF → file#page=N · video → seek"], False),
    ]
    y = 128
    for i, (kind, a, b, text, back) in enumerate(steps, 1):
        if kind == "msg":
            c.arrow([(a, y), (b, y)], dashed=back)
            mid = (a + b) / 2
            c.label(mid, y - 9, text, size=12, anchor="middle")
            bx = a + (16 if b > a else -16)
            c.badge(bx, y - 18 if False else y, i)
        else:
            c.el.append(f'<path d="M{a},{y - 9} L{a + 34},{y - 9} L{a + 34},{y + 9} L{a + 6},{y + 9}" fill="none" '
                        f'stroke="{INK}" stroke-width="1.8" marker-end="url(#arrow_{INK[1:]})"/>')
            c.badge(a - 20, y, i)
            c.label(a + 44, y + 4, text[0], size=12)
        y += 48

# ===================================================================== build
def main() -> int:
    problems = 0
    for d in DIAGRAMS:
        c = Canvas()
        d["draw"](c)
        for w in c.warnings:
            print(f"WARNING [{d['name']}]: {w}")
            problems += 1
        folder = os.path.join(OUT, d["folder"])
        os.makedirs(folder, exist_ok=True)
        doc = documentation_svg(c, d["title"], d["subtitle"], d["notes"], d["legend_extra"])
        pres = presentation_svg(c, d["title"], d["tagline"], d["legend_extra"])
        for suffix, svg in (("", doc), ("-16x9", pres)):
            path = os.path.join(folder, f"{d['name']}{suffix}.svg")
            with open(path, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(svg)
            print("wrote", os.path.relpath(path, OUT))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
