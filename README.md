# Odysseus-Extension (JANE)

The intelligence layer for **project Odyssey** — codename **JANE** (Just Another Neural Extension).

Turns a self-hosted [Odysseus](https://github.com/odysseus) brain into a personal cognitive system:
ingestion, a knowledge graph, unified retrieval, and memory routing — built as separate
MCP servers/services that talk to the brain over HTTP/MCP (never in-process).

---

## What's here now

**Module 1, Slice 1 — the ingestion service** (`ingestion/`). It walks your notes, extracts
structured data, and makes them searchable in the brain:

- Walks configured source roots (e.g. an Obsidian vault), respecting ignore rules.
- Extracts text, chunks it, and pulls **subject–predicate–object triples** from Obsidian
  `[[wikilinks]]` and `#tags` — each stored with full provenance (source file, chunk, char span).
- Writes everything to a local **SQLite staging store** as `staged` — nothing is trusted until a
  human reviews it.
- Uploads each file to **Odysseus's RAG** so it's semantically searchable in the brain.
- Ships a **review CLI** to approve / reject / correct staged triples.

> The default triple extractor is now a **schema-constrained LLM extractor** (`llm-v1`, local Qwen)
> that calls a local llama.cpp endpoint with a strict JSON schema. The original deterministic
> extractor (`naive-v1`) remains available — no model required — via `extractor = "naive"` in the
> config or the `--naive` flag on `ingest`.

## Prerequisites

- **Python 3.11+** and [`uv`](https://docs.astral.sh/uv/).
- A running **Odysseus brain** (default `http://localhost:7000`; start it with
  `systemctl --user start odysseus`) — only needed for the RAG-upload step. For RAG to work, the brain
  also needs its **ChromaDB server** (on `localhost:8100`) and an **embedding endpoint** configured.
  See `ops/instance-config.md` for the exact setup on this host. You can run ingestion **without** a
  brain using `--no-rag` (stages triples locally only).
- A local **llama.cpp Qwen endpoint** at `http://127.0.0.1:8081/v1` (OpenAI-compatible, must support
  `response_format: json_schema`) — needed for the default LLM extractor. **Not needed** if you run
  with `--naive` / `extractor = "naive"`.

## Installation

```bash
cd ingestion
uv sync                                   # install deps into a local venv
cp ingestion.toml.example ingestion.toml  # then edit: point `roots` at your notes
```

Credentials are **never** put in the TOML — set them as environment variables:

```bash
export ODYSSEUS_URL='http://localhost:7000'   # optional; overrides the toml
export ODYSSEUS_USER='your-odysseus-username'
export ODYSSEUS_PASSWORD='your-odysseus-password'
```

## Usage

Run from `ingestion/`:

```bash
# Stage triples locally only (no brain needed) — good first run:
uv run python -m ingestion.cli ingest --config ingestion.toml --no-rag

# Full run: stage + upload files to Odysseus RAG (needs the brain + creds above):
uv run python -m ingestion.cli ingest --config ingestion.toml

# See counts (documents + triples by status):
uv run python -m ingestion.cli status --config ingestion.toml

# Review the queue:
uv run python -m ingestion.cli review --list --config ingestion.toml
uv run python -m ingestion.cli review --approve <ID> --config ingestion.toml
uv run python -m ingestion.cli review --reject  <ID> --note "why" --config ingestion.toml
uv run python -m ingestion.cli review --correct <ID> --subject S --predicate P --object O --config ingestion.toml

# Stage triples with the deterministic naive extractor (no LLM):
uv run python -m ingestion.cli ingest --config ingestion.toml --no-rag --naive

# Score the configured extractor against a gold set:
uv run python -m ingestion.cli eval --config ingestion.toml --gold eval/gold.jsonl
```

Ingestion is **incremental** (unchanged files are skipped) and **interrupt-safe** (a file is marked
done only after its triples are staged and its upload succeeds), so re-running is cheap and safe.

### Dev loop

```bash
uv run pytest                 # tests
uv run ruff check src tests   # lint
```

## Project status

- ✅ **Module 0** — brain adopted & verified (see `ops/instance-config.md`).
- ✅ **Module 1, Slice 1** — ingestion skeleton (this service).
- ✅ **Module 1, Slice 2** — schema-constrained LLM triple extractor (`llm-v1`, local Qwen) behind an
  extractor factory, with `naive-v1` retained as a no-model fallback; an eval harness
  (precision/recall/F1, `cli eval`) scores the configured extractor against a hand-labeled gold set
  (precision target ≥ 0.80).
- ⏭️ **Next:** Module 2 — the Knowledge Graph (Kùzu): promote approved triples into a graph, entity
  resolution, `neighbors`/`path`/`subgraph` tools. Deferred from Slice 2: cloud verification of
  low-confidence triples (still a required keystone defense, not yet built).

Design source of truth: `../docs/master-spec.md` (Part 5). Live host config: `ops/instance-config.md`.
