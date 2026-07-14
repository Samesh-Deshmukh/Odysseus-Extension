from ingestion.staging import Staging


def _seed_triple(st):
    doc_id = st.upsert_document(
        path="/vault/a.md", source_type="obsidian", title="A",
        created="2026-01-01", modified="2026-01-02", hash="h1",
    )
    chunk_id = st.add_chunk(doc_id, ordinal=0, char_start=0, char_end=10, text="hello mqtt")
    triple_id = st.add_triple(
        doc_id, chunk_id, subject="A", predicate="references", object_="MQTT",
        char_start=0, char_end=10,
        confidence=1.0, extractor_model="naive-v1", extracted_at="2026-01-02T00:00:00Z",
    )
    return doc_id, chunk_id, triple_id


def test_document_upsert_and_hash(tmp_path):
    st = Staging(tmp_path / "s.db")
    doc_id = st.upsert_document("/vault/a.md", "obsidian", "A", "c", "m", "h1")
    assert st.get_document_hash("/vault/a.md") == "h1"
    # Upsert same path updates hash, keeps one row / same id.
    doc_id2 = st.upsert_document("/vault/a.md", "obsidian", "A", "c", "m2", "h2")
    assert doc_id2 == doc_id
    assert st.get_document_hash("/vault/a.md") == "h2"
    assert st.get_document_hash("/vault/missing.md") is None


def test_triple_lands_staged_with_provenance(tmp_path):
    st = Staging(tmp_path / "s.db")
    _doc, chunk_id, triple_id = _seed_triple(st)
    rows = st.list_triples("staged")
    assert len(rows) == 1
    r = rows[0]
    assert r["subject"] == "A" and r["predicate"] == "references" and r["object"] == "MQTT"
    assert r["status"] == "staged"
    assert r["chunk_id"] == chunk_id
    assert r["confidence"] == 1.0
    assert r["extractor_model"] == "naive-v1"
    assert r["char_start"] == 0
    assert r["char_end"] == 10


def test_status_transitions_and_correction(tmp_path):
    st = Staging(tmp_path / "s.db")
    _doc, _chunk, triple_id = _seed_triple(st)

    st.update_triple(triple_id, subject="A", predicate="references", object_="MQTT broker")
    st.set_triple_status(triple_id, "approved", note="ok", reviewed_at="2026-01-03T00:00:00Z")

    assert st.list_triples("staged") == []
    approved = st.list_triples("approved")
    assert len(approved) == 1
    assert approved[0]["object"] == "MQTT broker"
    assert approved[0]["note"] == "ok"


def test_mark_rag_uploaded(tmp_path):
    st = Staging(tmp_path / "s.db")
    doc_id = st.upsert_document("/vault/a.md", "obsidian", "A", "c", "m", "h1")
    st.mark_rag_uploaded(doc_id)
    cur = st.conn.execute("SELECT rag_uploaded FROM documents WHERE id=?", (doc_id,))
    assert cur.fetchone()[0] == 1
