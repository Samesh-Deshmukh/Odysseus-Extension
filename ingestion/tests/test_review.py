from ingestion.review import format_triple, review_action
from ingestion.staging import Staging


def _seed(st):
    doc_id = st.upsert_document("/v/a.md", "obsidian", "A", "c", "m", "h")
    ch = st.add_chunk(doc_id, 0, 0, 5, "hello")
    return st.add_triple(doc_id, ch, "A", "references", "MQTT", 1.0, "naive-v1", "t")


def test_approve(tmp_path):
    st = Staging(tmp_path / "s.db")
    tid = _seed(st)
    review_action(st, tid, "approve", reviewed_at="2026-07-12T00:00:00Z")
    assert st.list_triples("staged") == []
    assert len(st.list_triples("approved")) == 1


def test_reject(tmp_path):
    st = Staging(tmp_path / "s.db")
    tid = _seed(st)
    review_action(st, tid, "reject", reviewed_at="2026-07-12T00:00:00Z", note="wrong")
    rejected = st.list_triples("rejected")
    assert len(rejected) == 1
    assert rejected[0]["note"] == "wrong"


def test_correct_then_approve(tmp_path):
    st = Staging(tmp_path / "s.db")
    tid = _seed(st)
    review_action(
        st, tid, "correct", reviewed_at="2026-07-12T00:00:00Z",
        subject="A", predicate="uses", object_="MQTT",
    )
    approved = st.list_triples("approved")
    assert len(approved) == 1
    assert approved[0]["predicate"] == "uses"


def test_format_triple_is_one_line(tmp_path):
    st = Staging(tmp_path / "s.db")
    _seed(st)
    row = st.list_triples("staged")[0]
    line = format_triple(row)
    assert "references" in line and "MQTT" in line
    assert "\n" not in line
