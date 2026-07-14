from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_IGNORE = [
    "**/.git/**", "**/node_modules/**", "**/.venv/**", "**/venv/**",
    "**/__pycache__/**", "**/.obsidian/**", "**/dist/**", "**/build/**",
]
DEFAULT_EXTENSIONS = {".md"}


@dataclass
class Config:
    roots: list[Path] = field(default_factory=list)
    ignore_globs: list[str] = field(default_factory=lambda: list(DEFAULT_IGNORE))
    extensions: set[str] = field(default_factory=lambda: set(DEFAULT_EXTENSIONS))
    db_path: Path = Path("staging.db")
    chunk_size: int = 1000
    chunk_overlap: int = 200
    odysseus_url: str = "http://localhost:7000"
    odysseus_user: str = ""
    odysseus_password: str = ""


def load_config(path: Path | None = None) -> Config:
    data: dict = {}
    if path is not None:
        if not Path(path).exists():
            raise FileNotFoundError(f"config file not found: {path}")
        with open(path, "rb") as f:
            data = tomllib.load(f)

    cfg = Config(
        roots=[Path(p) for p in data.get("roots", [])],
        ignore_globs=data.get("ignore_globs", list(DEFAULT_IGNORE)),
        extensions={e.lower() for e in data.get("extensions", DEFAULT_EXTENSIONS)},
        db_path=Path(data.get("db_path", "staging.db")),
        chunk_size=int(data.get("chunk_size", 1000)),
        chunk_overlap=int(data.get("chunk_overlap", 200)),
        odysseus_url=data.get("odysseus_url", "http://localhost:7000"),
    )
    # Credentials + URL override strictly from the environment.
    cfg.odysseus_url = os.environ.get("ODYSSEUS_URL", cfg.odysseus_url)
    cfg.odysseus_user = os.environ.get("ODYSSEUS_USER", "")
    cfg.odysseus_password = os.environ.get("ODYSSEUS_PASSWORD", "")
    return cfg
