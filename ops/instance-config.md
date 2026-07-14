# Odysseus instance — how mine is configured

The short "how my instance is configured" note required by Module 0 (adopt & verify).
Captures the operational facts about *this* brain host so they aren't re-discovered later.
**No secrets live here** — tokens/keys stay in `.env` and in the backups under `~/odysseus-backups`.

_Last verified: 2026-07-07._

## Host & run

- **App root (live):** `/home/samesh/Projects/odyssey/odysseus` — this is the running instance's
  cwd (verified via `/proc/<pid>/cwd`), **not** a separate `~/odysseus` checkout. An old Cookbook
  crash log references `~/odysseus/venv`; that path is stale history, ignore it.
- **Run (native, non-Docker):**
  ```bash
  cd /home/samesh/Projects/odyssey/odysseus
  python -m uvicorn app:app --host 127.0.0.1 --port 7000
  ```
- **Venv:** `/home/samesh/Projects/odyssey/odysseus/venv` (Python 3.14).
- **UI:** http://localhost:7000
- **Data dir:** `/home/samesh/Projects/odyssey/odysseus/data` (~2.4 MB). Chroma is native here, so
  no separate vector service. `data/chroma` is currently empty (0 B); RAG data lives under
  `personal_docs/`, `rag/`, and `memory_vectors/`.

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