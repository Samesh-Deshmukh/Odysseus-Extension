from pathlib import Path

from ingestion.walker import file_hash, walk


def _make_tree(base: Path):
    (base / "notes").mkdir(parents=True)
    (base / "notes" / "keep.md").write_text("# keep")
    (base / "notes" / "skip.txt").write_text("nope")
    (base / ".git").mkdir()
    (base / ".git" / "config.md").write_text("# junk")
    (base / "node_modules").mkdir()
    (base / "node_modules" / "readme.md").write_text("# dep")


def test_walk_filters_extensions_and_ignores(tmp_path):
    _make_tree(tmp_path)
    ignore = ["**/.git/**", "**/node_modules/**"]
    found = sorted(p.name for p in walk([tmp_path], ignore, {".md"}))
    assert found == ["keep.md"]


def test_file_hash_changes_with_content(tmp_path):
    f = tmp_path / "a.md"
    f.write_text("one")
    h1 = file_hash(f)
    f.write_text("two")
    assert file_hash(f) != h1
    assert len(h1) == 64
