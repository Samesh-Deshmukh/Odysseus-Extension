# Odysseus instance — how mine is configured

The short "how my instance is configured" note required by Module 0 (adopt & verify).
Captures the operational facts about *this* brain host so they aren't re-discovered later.
**No secrets live here** — tokens/keys stay in `.env` and in the backups under `~/odysseus-backups`.

_Last verified: 2026-07-07._

## Host & run

- **App root (live):** `/home/samesh/Projects/odyssey/odysseus` — this is the running instance's
  cwd (verified via `/proc/<pid>/cwd`), **not** a separate `~/odysseus` checkout. An old Cookbook
  crash log references `~/odysseus/venv`; that path is stale history, ignore it.
- **Run (user systemd service, non-Docker):**
  ```bash
  systemctl --user start odysseus     # start   (status/stop: systemctl --user status|stop odysseus)
  journalctl --user -u odysseus -f    # follow logs
  ```
  Manual fallback (foreground dev run):
  ```bash
  cd /home/samesh/Projects/odyssey/odysseus
  python -m uvicorn app:app --host 127.0.0.1 --port 7000
  ```
- **Venv:** `/home/samesh/Projects/odyssey/odysseus/venv` (Python 3.14).
- **UI:** http://localhost:7000
- **Data dir:** `/home/samesh/Projects/odyssey/odysseus/data`. **Vector store is NOT embedded** —
  Odysseus's `get_chroma_client()` is HTTP-only and needs a **ChromaDB server at `localhost:8100`**
  (plus an embedding endpoint). See the "Brain RAG prerequisites" section below for the server + nomic
  endpoint setup discovered during the Module 1 DoD run. (The earlier "Chroma is native, no separate
  service" note was wrong.)

## Models (LLM backend)

- **Provider:** local **Ollama** at `http://127.0.0.1:11434` (`.env` sets `LLM_HOST=localhost`).
- **Served model:** `gemma4:latest` — 8B, Q4_K_M, capabilities: completion + tools + thinking.
  - ⚠️ **Below the spec target.** master-spec / extension CLAUDE.md call for a **12–14B @ Q4**
    workhorse; the 16 GB RTX 5060 Ti has headroom for it (only ~1.2 GB used at idle). Upgrade the
    served model when convenient.
- **Cookbook:** no active serve task. One historical task (`serve-f23a229f`, `pip realesrgan`)
  is in **crashed** state — `KeyError: '__version__'` building `basicsr` on Python 3.14.
  **Intentionally not fixed:** Real-ESRGAN is optional image upscaling, off the brain's critical
  path, and `basicsr`/`realesrgan` are unmaintained. Dismiss the task in the Cookbook UI when
  convenient. Revisit only if image upscaling is actually wanted.

## MCP servers (running, verified)

Spawned by the app from `mcp_servers/`:
- `memory_server.py` ✅
- `rag_server.py` ✅
- `email_server.py`, `image_gen_server.py`

## Claude Code integration (build partner)

- Scope-gated token installed; skill bundle unpacked to `~/.claude/skills/odysseus/`.
- Env this session expects: `ODYSSEUS_URL=http://localhost:7000`, `ODYSSEUS_API_TOKEN=ody_a_…`
  (value **not** stored here — mint in Settings → Integrations → Add Claude Agent).
- **Granted scopes:** chat, memory r/w, documents r/w, todos r/w, calendar r/w, email:read,
  email:draft, cookbook:read, cookbook:launch. (`email:send` is **off** — sending requires
  explicit re-enable.)
- Health check: `python3 ~/.claude/skills/odysseus/scripts/odysseus_api.py capabilities`

## Backups

- **Script:** `odysseus-extension/ops/backup.sh` (this repo).
- **Archives:** `~/odysseus-backups/odysseus-data-<timestamp>.tar.gz` (kept: last 7).
  Lives **outside** the repo because archives contain secrets (`.app_key`, `auth.json`).
- **Method:** online `sqlite3 .backup` of every DB (consistent, no downtime) + tar.gz of the rest.
- **Run:** `./backup.sh` — **Restore-test:** `./backup.sh --restore-test` (runs
  `PRAGMA integrity_check` on every DB in the archive).

## Module 0 — Definition of Done status

| # | Item | Status |
|---|------|--------|
| 1 | Fresh chat ← **local** model | ✅ confirmed in UI (backend also proven: Ollama `gemma4` returned output) |
| 2 | Test doc → personal-docs RAG → retrieved | ✅ confirmed in UI |
| 3 | Memory MCP stores + recalls a fact | ✅ verified via `/api/codex/memory` (stored, listed, deleted) |
| 4 | Claude Code calls a tool via scoped token | ✅ verified (`capabilities`, memory, documents, cookbook) |
| 5 | `data/` backup, restore-tested | ✅ verified (`backup.sh` + `--restore-test` passed) |

**Module 0 complete.** Next: Module 1 — Ingestion & Data Layer.

## Module 1 — Slice 1 (ingestion skeleton) status

Service: `ingestion/` (uv project, 33 tests). Config: `ingestion/ingestion.toml` (gitignored;
points at the Obsidian vault). Creds via `ODYSSEUS_USER`/`ODYSSEUS_PASSWORD` env vars.

| # | Item | Status |
|---|------|--------|
| 1 | Vault `.md` walked + staged with provenance | ✅ 83 files, 192 triples (56 references, 136 related_to), 0 failed |
| 2 | Triples visible via `review --list` | ✅ verified |
| 3 | Review approve/reject/correct works | ✅ verified (approve/reject/correct all move status) |
| 4 | Files uploaded to Odysseus RAG (`ingest` with creds) | ✅ 83/83 uploaded, failed=0 (210 chunks indexed) |
| 5 | Semantic search returns vault hits (e.g. MQTT) | ✅ "MQTT"/"home automation"/"voice assistant" all return vault chunks |

**Module 1 Slice 1 DoD: COMPLETE (5/5).**

Triples are wikilink/tag-based (Obsidian `[[links]]` + `#tags`); prose-only terms like "MQTT" are
served by Odysseus RAG semantic search (#5), not the naive-v1 graph extractor.
Next after DoD: Slice 2 (12–14B model + schema-constrained extractor + eval set).

### ⚠️ Brain RAG prerequisites discovered during the DoD run (correct the earlier "native Chroma" note)
This Odysseus build's `get_chroma_client()` is **HTTP-only** — it REQUIRES a ChromaDB server at
`localhost:8100` (`CHROMADB_HOST`/`CHROMADB_PORT`); there is **no embedded/PersistentClient fallback**.
The earlier "Chroma is native here, no separate service" claim was wrong. RAG/vector-memory/tool-index
were all degraded because no Chroma server was running.

To get the DoD green, two things were set up (both must persist for RAG to keep working):
1. **ChromaDB server on :8100** — currently started as an *isolated `uv` process* (the odysseus venv has
   chromadb 1.5.9 **client-only**; the server CLI needs `chromadb_rust_bindings`). Command used:
   `uv run --no-project --python 3.12 --with chromadb chroma run --host 127.0.0.1 --port 8100 --path .../odysseus/data/chroma`.
   **This is NOT durable** — it dies with the session/reboot. TODO: make Chroma a managed service
   (systemd unit, Docker `--restart`, or install the rust bindings + a startup script). Data persists
   under `odysseus/data/chroma` as long as `--path` stays the same.
2. **Embedding endpoint** — set via `POST /api/embeddings/endpoint` to Ollama's OpenAI-compatible
   `http://127.0.0.1:11434/v1/embeddings`, model `nomic-embed-text` (768-dim). This is **persisted in
   Odysseus config** (survives restart) but depends on `nomic-embed-text` staying pulled in Ollama.
   Note: use `127.0.0.1`, not `localhost` (the SSRF guard rejects the `::1` resolution).

Uploaded files are copied into `odysseus/data/personal_uploads/admin/` (per-file upload design).
`/api/rag/stats` may report "not available" even when uploads/search work — it reads a stale startup
reference, not the live singleton; trust an actual upload/query over that endpoint.