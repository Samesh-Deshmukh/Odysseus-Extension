import json

import httpx

from ingestion.llm_extractor import EXTRACTOR_MODEL, LlmExtractor
from ingestion.textpipe import Chunk


def _completion(triples: list[dict]) -> dict:
    """Shape a llama.cpp /v1/chat/completions response whose message content
    is a JSON string matching our schema."""
    return {"choices": [{"message": {"content": json.dumps({"triples": triples})}}]}


def _extractor(handler, model_label="") -> LlmExtractor:
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return LlmExtractor("http://127.0.0.1:8081/v1", model_label=model_label,
                        timeout=5.0, client=client)


def test_model_tag_includes_label():
    ex = _extractor(lambda r: httpx.Response(200, json=_completion([])), model_label="qwen3-14b")
    assert ex.model == "llm-v1:qwen3-14b"
    assert EXTRACTOR_MODEL == "llm-v1"


def test_model_tag_without_label():
    ex = _extractor(lambda r: httpx.Response(200, json=_completion([])))
    assert ex.model == "llm-v1"


def test_extracts_triples_and_locates_evidence_span():
    text = "intro. JANET uses MQTT here. tail."
    chunk = Chunk(ordinal=0, char_start=100, char_end=100 + len(text), text=text)

    def handler(request):
        return httpx.Response(200, json=_completion([
            {"subject": "JANET", "predicate": "uses", "object": "MQTT",
             "evidence": "JANET uses MQTT", "confidence": 0.95},
        ]))

    ex = _extractor(handler)
    out = ex.extract("Arch", chunk)
    assert len(out) == 1
    t = out[0]
    assert (t.subject, t.predicate, t.object) == ("JANET", "uses", "MQTT")
    assert t.confidence == 0.95
    # Evidence "JANET uses MQTT" starts at index 7 in the chunk text.
    assert t.char_start == 100 + text.index("JANET uses MQTT")
    assert t.char_end == t.char_start + len("JANET uses MQTT")
    assert ex.evidence_misses == 0


def test_evidence_not_found_falls_back_to_chunk_span_and_counts_miss():
    text = "JANET talks to the broker."
    chunk = Chunk(ordinal=0, char_start=0, char_end=len(text), text=text)

    def handler(request):
        return httpx.Response(200, json=_completion([
            {"subject": "JANET", "predicate": "uses", "object": "MQTT",
             "evidence": "PARAPHRASED NOT IN TEXT", "confidence": 0.5},
        ]))

    ex = _extractor(handler)
    out = ex.extract("Arch", chunk)
    assert len(out) == 1
    assert (out[0].char_start, out[0].char_end) == (0, len(text))
    assert ex.evidence_misses == 1


def test_confidence_is_clamped():
    text = "JANET uses MQTT."
    chunk = Chunk(ordinal=0, char_start=0, char_end=len(text), text=text)

    def handler(request):
        return httpx.Response(200, json=_completion([
            {"subject": "JANET", "predicate": "uses", "object": "MQTT",
             "evidence": "JANET uses MQTT", "confidence": 1.7},
        ]))

    ex = _extractor(handler)
    out = ex.extract("Arch", chunk)
    assert out[0].confidence == 1.0


def test_off_ontology_predicate_is_dropped():
    text = "JANET frobnicates MQTT."
    chunk = Chunk(ordinal=0, char_start=0, char_end=len(text), text=text)

    def handler(request):
        return httpx.Response(200, json=_completion([
            {"subject": "JANET", "predicate": "frobnicates", "object": "MQTT",
             "evidence": "JANET frobnicates MQTT", "confidence": 0.9},
        ]))

    ex = _extractor(handler)
    out = ex.extract("Arch", chunk)
    assert out == []


def test_http_error_retries_once_then_returns_empty():
    text = "JANET uses MQTT."
    chunk = Chunk(ordinal=0, char_start=0, char_end=len(text), text=text)
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(500, text="server boom")

    ex = _extractor(handler)
    out = ex.extract("Arch", chunk)
    assert out == []
    assert calls["n"] == 2  # initial try + one retry


def test_malformed_json_content_returns_empty():
    text = "JANET uses MQTT."
    chunk = Chunk(ordinal=0, char_start=0, char_end=len(text), text=text)

    def handler(request):
        return httpx.Response(200, json={"choices": [{"message": {"content": "not json {"}}]})

    ex = _extractor(handler)
    assert ex.extract("Arch", chunk) == []


def test_request_sends_temperature_zero_and_json_schema():
    text = "JANET uses MQTT."
    chunk = Chunk(ordinal=0, char_start=0, char_end=len(text), text=text)
    captured = {}

    def handler(request):
        captured["body"] = json.loads(request.content)
        captured["path"] = request.url.path
        return httpx.Response(200, json=_completion([]))

    ex = _extractor(handler)
    ex.extract("Arch", chunk)
    body = captured["body"]
    assert captured["path"] == "/v1/chat/completions"
    assert body["temperature"] == 0
    assert body["response_format"]["type"] == "json_schema"
    assert body["response_format"]["json_schema"]["strict"] is True
    # The document text is delivered to the model.
    assert "JANET uses MQTT." in json.dumps(body["messages"])
