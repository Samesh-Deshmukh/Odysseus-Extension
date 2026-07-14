from __future__ import annotations

import re
from dataclasses import dataclass

from ingestion.textpipe import Chunk

EXTRACTOR_MODEL = "naive-v1"

_WIKILINK = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]*)?\]\]")
_TAG = re.compile(r"(?:(?<=\s)|^)#([A-Za-z][\w\-/]*)")


@dataclass
class Triple:
    subject: str
    predicate: str
    object: str
    confidence: float
    char_start: int
    char_end: int


def extract_triples(doc_title: str, chunk: Chunk) -> list[Triple]:
    triples: list[Triple] = []
    base = chunk.char_start
    for m in _WIKILINK.finditer(chunk.text):
        target = m.group(1).strip()
        if target:
            triples.append(Triple(doc_title, "references", target, 1.0,
                                  base + m.start(), base + m.end()))
    for m in _TAG.finditer(chunk.text):
        tag = m.group(1).strip()
        if tag:
            triples.append(Triple(doc_title, "related_to", tag, 1.0,
                                  base + m.start(), base + m.end()))
    return triples
