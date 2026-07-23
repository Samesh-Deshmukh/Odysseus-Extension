from ingestion.eval import EvalReport, GoldChunk, load_gold, normalize_triple, score
from ingestion.triples import Triple


def test_normalize_lowercases_and_collapses_whitespace():
    assert normalize_triple("  JANET ", "uses", "M Q  TT") == ("janet", "uses", "m q tt")


def test_score_perfect_match():
    gold = [GoldChunk(doc="d", chunk_text="JANET uses MQTT.", char_start=0,
                      expected_triples=[("JANET", "uses", "MQTT")])]

    def extract(title, chunk):
        return [Triple("JANET", "uses", "MQTT", 1.0, 0, 5)]

    report = score(extract, gold)
    assert isinstance(report, EvalReport)
    assert report.true_pos == 1
    assert report.precision == 1.0
    assert report.recall == 1.0
    assert report.f1 == 1.0
    assert report.false_pos == []
    assert report.false_neg == []


def test_score_counts_false_pos_and_false_neg():
    gold = [GoldChunk(doc="d", chunk_text="x", char_start=0,
                      expected_triples=[("JANET", "uses", "MQTT"),
                                        ("JANET", "part_of", "Odyssey")])]

    def extract(title, chunk):
        # one correct (case-insensitive), one spurious; misses the part_of triple
        return [Triple("janet", "uses", "mqtt", 0.9, 0, 1),
                Triple("JANET", "uses", "HTTP", 0.5, 0, 1)]

    report = score(extract, gold)
    assert report.true_pos == 1
    assert ("janet", "uses", "http") in report.false_pos
    assert ("janet", "part_of", "odyssey") in report.false_neg
    assert report.precision == 0.5           # 1 TP / (1 TP + 1 FP)
    assert report.recall == 0.5              # 1 TP / (1 TP + 1 FN)
    assert abs(report.f1 - 0.5) < 1e-9


def test_score_zero_predictions_zero_precision_not_crash():
    gold = [GoldChunk(doc="d", chunk_text="x", char_start=0,
                      expected_triples=[("A", "uses", "B")])]

    report = score(lambda t, c: [], gold)
    assert report.precision == 0.0
    assert report.recall == 0.0
    assert report.f1 == 0.0
    assert report.false_neg == [("a", "uses", "b")]


def test_load_gold_parses_jsonl(tmp_path):
    p = tmp_path / "gold.jsonl"
    p.write_text(
        '{"doc":"a","chunk_text":"JANET uses MQTT.","char_start":10,'
        '"expected_triples":[{"subject":"JANET","predicate":"uses","object":"MQTT"}]}\n'
        '\n'  # blank line tolerated
        '{"doc":"b","chunk_text":"no triples here","char_start":0,"expected_triples":[]}\n'
    )
    gold = load_gold(p)
    assert len(gold) == 2
    assert gold[0].doc == "a"
    assert gold[0].char_start == 10
    assert gold[0].expected_triples == [("JANET", "uses", "MQTT")]
    assert gold[1].expected_triples == []


def test_score_builds_chunk_from_gold_char_start():
    captured = {}
    gold = [GoldChunk(doc="d", chunk_text="hello world", char_start=42, expected_triples=[])]

    def extract(title, chunk):
        captured["char_start"] = chunk.char_start
        captured["char_end"] = chunk.char_end
        captured["text"] = chunk.text
        return []

    score(extract, gold)
    assert captured["char_start"] == 42
    assert captured["char_end"] == 42 + len("hello world")
    assert captured["text"] == "hello world"
