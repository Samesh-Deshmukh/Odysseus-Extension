from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY,
    path TEXT UNIQUE NOT NULL,
    source_type TEXT,
    title TEXT,
    created TEXT,
    modified TEXT,
    hash TEXT,
    indexed_at TEXT,
    rag_uploaded INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS chunks (
    id INTEGER PRIMARY KEY,
    doc_id INTEGER NOT NULL REFERENCES documents(id),
    ordinal INTEGER NOT NULL,
    char_start INTEGER NOT NULL,
    char_end INTEGER NOT NULL,
    text TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS triples (
    id INTEGER PRIMARY KEY,
    doc_id INTEGER NOT NULL REFERENCES documents(id),
    chunk_id INTEGER NOT NULL REFERENCES chunks(id),
    subject TEXT NOT NULL,
    predicate TEXT NOT NULL,
    object TEXT NOT NULL,
    confidence REAL,
    extractor_model TEXT,
    extracted_at TEXT,
    status TEXT NOT NULL DEFAULT 'staged',
    reviewed_at TEXT,
    note TEXT
);
"""


class Staging:
    def __init__(self, db_path: Path):
        self.conn = sqlite3.connect(str(db_path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.init_schema()

    def init_schema(self) -> None:
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def upsert_document(self, path, source_type, title, created, modified, hash) -> int:
        cur = self.conn.execute(
            """
            INSERT INTO documents (path, source_type, title, created, modified, hash)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(path) DO UPDATE SET
                source_type=excluded.source_type, title=excluded.title,
                created=excluded.created, modified=excluded.modified, hash=excluded.hash
            """,
            (path, source_type, title, created, modified, hash),
        )
        self.conn.commit()
        if cur.lastrowid:
            row = self.conn.execute("SELECT id FROM documents WHERE path=?", (path,)).fetchone()
            return row["id"]
        return self.conn.execute("SELECT id FROM documents WHERE path=?", (path,)).fetchone()["id"]

    def get_document_hash(self, path) -> str | None:
        row = self.conn.execute("SELECT hash FROM documents WHERE path=?", (path,)).fetchone()
        return row["hash"] if row else None

    def mark_rag_uploaded(self, doc_id) -> None:
        self.conn.execute("UPDATE documents SET rag_uploaded=1 WHERE id=?", (doc_id,))
        self.conn.commit()

    def add_chunk(self, doc_id, ordinal, char_start, char_end, text) -> int:
        cur = self.conn.execute(
            "INSERT INTO chunks (doc_id, ordinal, char_start, char_end, text) VALUES (?,?,?,?,?)",
            (doc_id, ordinal, char_start, char_end, text),
        )
        self.conn.commit()
        return cur.lastrowid

    def add_triple(self, doc_id, chunk_id, subject, predicate, object_,
                   confidence, extractor_model, extracted_at) -> int:
        cur = self.conn.execute(
            """
            INSERT INTO triples
                (doc_id, chunk_id, subject, predicate, object,
                 confidence, extractor_model, extracted_at, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'staged')
            """,
            (doc_id, chunk_id, subject, predicate, object_,
             confidence, extractor_model, extracted_at),
        )
        self.conn.commit()
        return cur.lastrowid

    def list_triples(self, status="staged") -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM triples WHERE status=? ORDER BY id", (status,)
        ).fetchall()

    def set_triple_status(self, triple_id, status, note=None, reviewed_at=None) -> None:
        self.conn.execute(
            "UPDATE triples SET status=?, note=?, reviewed_at=? WHERE id=?",
            (status, note, reviewed_at, triple_id),
        )
        self.conn.commit()

    def update_triple(self, triple_id, subject, predicate, object_) -> None:
        self.conn.execute(
            "UPDATE triples SET subject=?, predicate=?, object=? WHERE id=?",
            (subject, predicate, object_, triple_id),
        )
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()
