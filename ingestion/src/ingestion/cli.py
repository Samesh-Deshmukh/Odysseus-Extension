from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

from ingestion.config import load_config
from ingestion.orchestrator import ingest
from ingestion.rag_client import RagClient
from ingestion.staging import Staging


def _now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _cmd_ingest(args) -> int:
    cfg = load_config(Path(args.config) if args.config else None)
    staging = Staging(cfg.db_path)
    rag = None
    if not args.no_rag:
        rag = RagClient(cfg.odysseus_url, cfg.odysseus_user, cfg.odysseus_password)
        if not rag.health():
            print(f"[ingest] Odysseus not reachable at {cfg.odysseus_url}; use --no-rag to stage only.")
            return 2
        rag.login()
    stats = ingest(cfg, staging, rag, extracted_at=_now())
    print(
        f"seen={stats.files_seen} ingested={stats.files_ingested} "
        f"skipped={stats.files_skipped} failed={stats.files_failed} "
        f"triples_staged={stats.triples_staged}"
    )
    staging.close()
    return 0


def _cmd_status(args) -> int:
    cfg = load_config(Path(args.config) if args.config else None)
    staging = Staging(cfg.db_path)
    docs = staging.conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    for status in ("staged", "approved", "rejected", "promoted"):
        n = staging.conn.execute("SELECT COUNT(*) FROM triples WHERE status=?", (status,)).fetchone()[0]
        print(f"{status}: {n}")
    print(f"documents: {docs}")
    staging.close()
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="ingestion")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_ing = sub.add_parser("ingest", help="walk roots, stage triples, upload to RAG")
    p_ing.add_argument("--config", default=None)
    p_ing.add_argument("--no-rag", action="store_true", help="stage only; skip Odysseus upload")
    p_ing.set_defaults(func=_cmd_ingest)

    p_st = sub.add_parser("status", help="print document + triple counts")
    p_st.add_argument("--config", default=None)
    p_st.set_defaults(func=_cmd_status)

    # review subcommand is added in Task 8.
    try:
        from ingestion.review import add_review_parser
        add_review_parser(sub)
    except ImportError:
        pass

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
