from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from ingestion.textpipe import Chunk
from ingestion.triples import Triple


@dataclass
class GoldChunk:
    doc: str
    chunk_text: str
    char_start: int
    expected_triples: list[tuple[str, str, str]]


@dataclass
class EvalReport:
    precision: float
    recall: float
    f1: float
    true_pos: int
    false_pos: list[tuple[str, str, str]]
    false_neg: list[tuple[str, str, str]]


def normalize_triple(subject: str, predicate: str, object_: str) -> tuple[str, str, str]:
    def norm(s: str) -> str:
        return " ".join(str(s).split()).lower()
    return (norm(subject), predicate.strip().lower(), norm(object_))


def load_gold(path: Path) -> list[GoldChunk]:
    out: list[GoldChunk] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)
        expected = [
            (t["subject"], t["predicate"], t["object"]) for t in obj.get("expected_triples", [])
        ]
        out.append(GoldChunk(
            doc=obj["doc"], chunk_text=obj["chunk_text"],
            char_start=int(obj.get("char_start", 0)), expected_triples=expected,
        ))
    return out


def score(extract: Callable[[str, Chunk], list[Triple]], gold: list[GoldChunk]) -> EvalReport:
    tp = 0
    false_pos: list[tuple[str, str, str]] = []
    false_neg: list[tuple[str, str, str]] = []

    for g in gold:
        chunk = Chunk(ordinal=0, char_start=g.char_start,
                      char_end=g.char_start + len(g.chunk_text), text=g.chunk_text)
        expected = {normalize_triple(*t) for t in g.expected_triples}
        predicted = {normalize_triple(t.subject, t.predicate, t.object) for t in extract(g.doc, chunk)}
        tp += len(expected & predicted)
        false_pos.extend(sorted(predicted - expected))
        false_neg.extend(sorted(expected - predicted))

    fp, fn = len(false_pos), len(false_neg)
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return EvalReport(precision, recall, f1, tp, false_pos, false_neg)
