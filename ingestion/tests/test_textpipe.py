from ingestion.textpipe import Chunk, chunk_text, extract_text


def test_chunk_offsets_round_trip():
    text = "abcdefghij" * 30  # 300 chars
    chunks = chunk_text(text, size=100, overlap=20)
    assert len(chunks) >= 3
    for c in chunks:
        assert isinstance(c, Chunk)
        assert text[c.char_start:c.char_end] == c.text
    assert chunks[0].char_start == 0
    assert chunks[-1].char_end == len(text)
    # Overlap: second chunk starts before the first chunk ends.
    assert chunks[1].char_start < chunks[0].char_end


def test_chunk_empty_text():
    assert chunk_text("", size=100, overlap=20) == []


def test_extract_text_title_from_heading(tmp_path):
    f = tmp_path / "note.md"
    f.write_text("# My Note\n\nSome MQTT content.")
    text, meta = extract_text(f)
    assert "MQTT" in text
    assert meta["title"] == "My Note"
    assert meta["source_type"] == "file"
    assert "modified" in meta and meta["modified"]


def test_extract_text_title_fallback_to_stem(tmp_path):
    f = tmp_path / "untitled.md"
    f.write_text("no heading here")
    _text, meta = extract_text(f)
    assert meta["title"] == "untitled"
