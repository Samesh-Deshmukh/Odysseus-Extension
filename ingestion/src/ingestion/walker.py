from __future__ import annotations

import fnmatch
import hashlib
from collections.abc import Iterator
from pathlib import Path


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(65536), b""):
            h.update(block)
    return h.hexdigest()


def _ignored(path: Path, ignore_globs: list[str]) -> bool:
    posix = path.as_posix()
    return any(fnmatch.fnmatch(posix, pat) for pat in ignore_globs)


def walk(roots: list[Path], ignore_globs: list[str], extensions: set[str]) -> Iterator[Path]:
    exts = {e.lower() for e in extensions}
    for root in roots:
        root = Path(root).resolve()
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix.lower() not in exts:
                continue
            if _ignored(path, ignore_globs):
                continue
            yield path.resolve()
