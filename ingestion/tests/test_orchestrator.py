from pathlib import Path

import pytest

from ingestion.config import Config
from ingestion.orchestrator import IngestStats, ingest
from ingestion.staging import Staging


class FakeRag:
    def __init__(self):
        self.uploaded = []

    def upload(self, path):
        self.uploaded.append(Path(path).name)
        return 1


def _cfg(tmp_path, root) -> Config:
    return Config(
        roots=[root], ignore_globs=["**/.git/**"], extensions={".md"},
        db_path=tmp_path / "s.db", chunk_size=1000, chunk_overlap=200,
        odysseus_url="http://x", odysseus_user="u", odysseus_password="p",
        extractor="naive",
    )


def test_ingest_stages_triples_uploads_and_is_incremental(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "arch.md").write_text("# Arch\nJANET uses [[MQTT]] over #networking.")

    cfg = _cfg(tmp_path, vault)
    staging = Staging(cfg.db_path)
    rag = FakeRag()

    stats = ingest(cfg, staging, rag, extracted_at="2026-07-12T00:00:00Z")
    assert isinstance(stats, IngestStats)
    assert stats.files_ingested == 1
    assert stats.triples_staged >= 2  # MQTT reference + networking tag
    assert rag.uploaded == ["arch.md"]

    rows = staging.list_triples("staged")
    objs = {r["object"] for r in rows}
    assert "MQTT" in objs and "networking" in objs
    # Provenance present on every triple.
    for r in rows:
        assert r["extractor_model"] == "naive-v1"
        assert r["chunk_id"] is not None

    # Second run: unchanged file skipped, no new triples, no re-upload.
    rag2 = FakeRag()
    stats2 = ingest(cfg, staging, rag2, extracted_at="2026-07-12T01:00:00Z")
    assert stats2.files_skipped == 1
    assert stats2.files_ingested == 0
    assert rag2.uploaded == []


def test_ingest_survives_a_bad_file(tmp_path, monkeypatch):
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "good.md").write_text("# Good\n[[MQTT]]")
    (vault / "bad.md").write_text("# Bad\n[[ESP32]]")

    cfg = _cfg(tmp_path, vault)
    staging = Staging(cfg.db_path)

    import ingestion.orchestrator as orch
    real_extract = orch.extract_text

    def flaky(path):
        if Path(path).name == "bad.md":
            raise ValueError("boom")
        return real_extract(path)

    monkeypatch.setattr(orch, "extract_text", flaky)
    stats = ingest(cfg, staging, None, extracted_at="2026-07-12T00:00:00Z")
    assert stats.files_failed == 1
    assert stats.files_ingested == 1


class FailOnceRag:
    """Fails upload for a given filename on the first call, succeeds after."""

    def __init__(self, fail_name):
        self.fail_name = fail_name
        self.calls = 0
        self.uploaded = []

    def upload(self, path):
        self.calls += 1
        if Path(path).name == self.fail_name and self.calls == 1:
            raise RuntimeError("upload boom")
        self.uploaded.append(Path(path).name)
        return 1


def test_upload_failure_is_retried_not_skipped(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "arch.md").write_text("# Arch\nJANET uses [[MQTT]].")

    cfg = _cfg(tmp_path, vault)
    staging = Staging(cfg.db_path)

    failing_rag = FailOnceRag(fail_name="arch.md")
    stats1 = ingest(cfg, staging, failing_rag, extracted_at="2026-07-12T00:00:00Z")
    assert stats1.files_failed == 1
    assert stats1.files_ingested == 0

    # Second run with a rag that succeeds: file must be reprocessed, not skipped.
    good_rag = FakeRag()
    stats2 = ingest(cfg, staging, good_rag, extracted_at="2026-07-12T01:00:00Z")
    assert stats2.files_skipped == 0
    assert stats2.files_ingested == 1
    assert good_rag.uploaded == ["arch.md"]


def test_changed_file_reingest_replaces_not_duplicates(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    target = vault / "arch.md"
    target.write_text("# Arch\nJANET uses [[MQTT]].")

    cfg = _cfg(tmp_path, vault)
    staging = Staging(cfg.db_path)

    ingest(cfg, staging, FakeRag(), extracted_at="2026-07-12T00:00:00Z")
    rows1 = staging.list_triples("staged")
    objs1 = {r["object"] for r in rows1}
    assert "MQTT" in objs1

    # Rewrite with different content — old link gone, new link present.
    target.write_text("# Arch\nJANET uses [[CoAP]].")
    stats2 = ingest(cfg, staging, FakeRag(), extracted_at="2026-07-12T01:00:00Z")
    assert stats2.files_ingested == 1

    rows2 = staging.list_triples("staged")
    objs2 = {r["object"] for r in rows2}
    assert "MQTT" not in objs2
    assert "CoAP" in objs2
    # Total staged triples reflect only the new content, no stale duplicates.
    assert len(rows2) == len(objs2)


def test_overlapping_chunks_dedup_triples(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    # [[MQTT]] appears twice, positioned so each occurrence itself straddles
    # the overlap zone between two adjacent chunks (chunk_size=40, overlap=20)
    # and is therefore re-extracted from both chunks it lands in.
    text = "x" * 25 + "[[MQTT]]" + "x" * 150 + "[[MQTT]]" + "x" * 10
    (vault / "arch.md").write_text(text)

    cfg = _cfg(tmp_path, vault)
    cfg.chunk_size = 40
    cfg.chunk_overlap = 20
    staging = Staging(cfg.db_path)

    ingest(cfg, staging, None, extracted_at="2026-07-12T00:00:00Z")
    rows = staging.list_triples("staged")
    mqtt_refs = [r for r in rows if r["predicate"] == "references" and r["object"] == "MQTT"]
    assert len(mqtt_refs) == 1


def test_no_rag_dry_run_then_rag_uploads(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    target = vault / "arch.md"
    target.write_text("# Arch\nJANET uses [[MQTT]].")

    cfg = _cfg(tmp_path, vault)
    staging = Staging(cfg.db_path)

    # Real ingest: file uploaded, rag_uploaded=1, hash=H1.
    rag1 = FakeRag()
    stats1 = ingest(cfg, staging, rag1, extracted_at="2026-07-12T00:00:00Z")
    assert stats1.files_ingested == 1
    assert rag1.uploaded == ["arch.md"]

    # Content changes to H2.
    target.write_text("# Arch\nJANET uses [[CoAP]].")

    # Dry run (--no-rag): file is re-staged (hash differs), nothing uploaded.
    stats2 = ingest(cfg, staging, None, extracted_at="2026-07-12T01:00:00Z")
    assert stats2.files_ingested == 1
    assert stats2.files_skipped == 0
    _, uploaded_after_dry_run = staging.get_document_state(str(target))
    assert uploaded_after_dry_run == 0

    # Same (now H2) content, real ingest: must NOT be skipped, must upload
    # the new content — the earlier dry run must not have left rag_uploaded
    # stuck at 1 from the original upload.
    rag3 = FakeRag()
    stats3 = ingest(cfg, staging, rag3, extracted_at="2026-07-12T02:00:00Z")
    assert stats3.files_skipped == 0
    assert stats3.files_ingested == 1
    assert rag3.uploaded == ["arch.md"]


def test_ingest_rejects_nonpositive_chunk_size(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "arch.md").write_text("# Arch\n[[MQTT]]")

    cfg = _cfg(tmp_path, vault)
    cfg.chunk_size = 0
    staging = Staging(cfg.db_path)

    with pytest.raises(ValueError):
        ingest(cfg, staging, None, extracted_at="2026-07-12T00:00:00Z")


def test_ingest_uses_injected_extractor_model_tag(tmp_path):
    from ingestion.extractor import ExtractorHandle
    from ingestion.triples import Triple

    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "n.md").write_text("# N\nJANET uses MQTT.")

    cfg = _cfg(tmp_path, vault)
    staging = Staging(cfg.db_path)

    def fake_extract(title, chunk):
        return [Triple("JANET", "uses", "MQTT", 0.9, chunk.char_start, chunk.char_end)]

    handle = ExtractorHandle(model="llm-v1:test", extract=fake_extract)
    stats = ingest(cfg, staging, None, extracted_at="2026-07-19T00:00:00Z", extractor=handle)
    assert stats.triples_staged == 1
    rows = staging.list_triples("staged")
    assert rows[0]["extractor_model"] == "llm-v1:test"
    assert rows[0]["object"] == "MQTT"
