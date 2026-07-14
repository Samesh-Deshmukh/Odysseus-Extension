from __future__ import annotations

from dataclasses import dataclass

from ingestion.config import Config
from ingestion.staging import Staging
from ingestion.textpipe import chunk_text, extract_text
from ingestion.triples import EXTRACTOR_MODEL, extract_triples
from ingestion.walker import file_hash, walk


@dataclass
class IngestStats:
    files_seen: int = 0
    files_ingested: int = 0
    files_skipped: int = 0
    files_failed: int = 0
    triples_staged: int = 0


def ingest(cfg: Config, staging: Staging, rag, extracted_at: str) -> IngestStats:
    # Guard against a misconfigured chunk_size/chunk_overlap hanging the run:
    # chunk_text loops forever if chunk_size <= 0, and both values come from
    # user-editable config rather than code.
    if cfg.chunk_size <= 0:
        raise ValueError(f"chunk_size must be > 0, got {cfg.chunk_size}")
    if not (0 <= cfg.chunk_overlap < cfg.chunk_size):
        raise ValueError(
            f"chunk_overlap must satisfy 0 <= chunk_overlap < chunk_size, "
            f"got chunk_overlap={cfg.chunk_overlap} chunk_size={cfg.chunk_size}"
        )

    stats = IngestStats()
    for path in walk(cfg.roots, cfg.ignore_globs, cfg.extensions):
        stats.files_seen += 1
        spath = str(path)
        try:
            digest = file_hash(path)
            stored_hash, stored_uploaded = staging.get_document_state(spath)
            # Skip only if fully done: hash matches AND (no rag this run OR it was uploaded before)
            if stored_hash == digest and (rag is None or stored_uploaded == 1):
                stats.files_skipped += 1
                continue

            text, meta = extract_text(path)
            doc_id = staging.upsert_document(
                path=spath, source_type=meta["source_type"], title=meta["title"],
                created=meta["created"], modified=meta["modified"], hash="",  # pending until success
            )
            staging.delete_doc_children(doc_id)  # clear stale/duplicate rows on re-ingest

            seen_spo = set()
            for chunk in chunk_text(text, cfg.chunk_size, cfg.chunk_overlap):
                chunk_id = staging.add_chunk(
                    doc_id, chunk.ordinal, chunk.char_start, chunk.char_end, chunk.text
                )
                for t in extract_triples(meta["title"], chunk):
                    key = (t.subject, t.predicate, t.object)
                    if key in seen_spo:  # Fix 4: dedup overlap duplicates within a doc
                        continue
                    seen_spo.add(key)
                    staging.add_triple(
                        doc_id, chunk_id, t.subject, t.predicate, t.object,
                        t.char_start, t.char_end, t.confidence, EXTRACTOR_MODEL, extracted_at,
                    )
                    stats.triples_staged += 1

            if rag is not None:
                rag.upload(path)
                staging.mark_rag_uploaded(doc_id)

            staging.set_document_hash(doc_id, digest, indexed_at=extracted_at)  # LAST: only now is "done"
            stats.files_ingested += 1
        except Exception as exc:  # per-file isolation — never abort the run
            stats.files_failed += 1
            print(f"[ingest] FAILED {path}: {exc}")
    return stats
