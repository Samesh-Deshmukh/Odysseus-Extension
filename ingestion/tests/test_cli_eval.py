import json

from ingestion.cli import main


def _write_gold(path):
    path.write_text(
        json.dumps({
            "doc": "d", "chunk_text": "JANET uses MQTT.", "char_start": 0,
            "expected_triples": [{"subject": "JANET", "predicate": "uses", "object": "MQTT"}],
        }) + "\n"
    )


def test_eval_command_runs_with_naive_extractor(tmp_path, capsys):
    # Use the naive extractor so no network is needed. The naive extractor emits
    # wikilink/tag triples, so this gold chunk (prose) yields a measurable score
    # without hitting an LLM — we only assert the command wires up and prints.
    gold = tmp_path / "gold.jsonl"
    _write_gold(gold)
    toml = tmp_path / "ingestion.toml"
    toml.write_text('extractor = "naive"\n')

    rc = main(["eval", "--config", str(toml), "--gold", str(gold)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "precision=" in out
    assert "recall=" in out
    assert "f1=" in out


def test_eval_command_missing_gold_returns_2(tmp_path, capsys):
    toml = tmp_path / "ingestion.toml"
    toml.write_text('extractor = "naive"\n')
    rc = main(["eval", "--config", str(toml), "--gold", str(tmp_path / "nope.jsonl")])
    assert rc == 2
