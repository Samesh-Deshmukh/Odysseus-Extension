from ingestion.textpipe import Chunk
from ingestion.triples import EXTRACTOR_MODEL, Triple, extract_triples


def test_wikilinks_become_reference_triples():
    text = "See [[MQTT]] and [[ESP32|the board]] for details."
    chunk = Chunk(ordinal=0, char_start=100, char_end=100 + len(text), text=text)
    triples = extract_triples("Architecture", chunk)
    refs = [(t.subject, t.predicate, t.object) for t in triples if t.predicate == "references"]
    assert ("Architecture", "references", "MQTT") in refs
    assert ("Architecture", "references", "ESP32") in refs


def test_tags_become_related_triples():
    text = "topic notes #networking and #home-automation"
    chunk = Chunk(ordinal=0, char_start=0, char_end=len(text), text=text)
    triples = extract_triples("Notes", chunk)
    tags = [t.object for t in triples if t.predicate == "related_to"]
    assert "networking" in tags
    assert "home-automation" in tags


def test_span_is_absolute_and_confidence_and_model():
    text = "x [[MQTT]]"
    chunk = Chunk(ordinal=0, char_start=50, char_end=50 + len(text), text=text)
    (t,) = [t for t in extract_triples("Doc", chunk) if t.object == "MQTT"]
    assert isinstance(t, Triple)
    assert t.confidence == 1.0
    assert t.char_start == 50 + text.index("[[")
    assert EXTRACTOR_MODEL == "naive-v1"


def test_no_triples_from_plain_text():
    text = "just some prose with no links or tags"
    chunk = Chunk(ordinal=0, char_start=0, char_end=len(text), text=text)
    assert extract_triples("Doc", chunk) == []
