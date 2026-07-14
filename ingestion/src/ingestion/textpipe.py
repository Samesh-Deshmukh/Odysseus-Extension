from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

_HEADING = re.compile(r"^#\s+(.+)$", re.MULTILINE)


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def extract_text(path: Path) -> tuple[str, dict]:
    path = Path(path)
    text = path.read_text(encoding="utf-8", errors="ignore")
    m = _HEADING.search(text)
    title = m.group(1).strip() if m else path.stem
    source_type = "obsidian" if any((p / ".obsidian").is_dir() for p in path.parents) else "file"
    stat = path.stat()
    meta = {
        "title": title,
        "source_type": source_type,
        "created": _iso(stat.st_ctime),
        "modified": _iso(stat.st_mtime),
    }
    return text, meta


@dataclass
class Chunk:
    ordinal: int
    char_start: int
    char_end: int
    text: str


def chunk_text(text: str, size: int, overlap: int) -> list[Chunk]:
    if not text:
        return []
    chunks: list[Chunk] = []
    i = 0
    n = len(text)
    ordinal = 0
    while i < n:
        j = min(i + size, n)
        chunks.append(Chunk(ordinal=ordinal, char_start=i, char_end=j, text=text[i:j]))
        ordinal += 1
        if j >= n:
            break
        i = j - overlap if j - overlap > i else j
    return chunks
