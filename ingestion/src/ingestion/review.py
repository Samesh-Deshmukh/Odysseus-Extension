from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from ingestion.config import load_config
from ingestion.staging import Staging


def review_action(staging: Staging, triple_id, action, reviewed_at,
                  subject=None, predicate=None, object_=None, note=None) -> None:
    if action == "approve":
        staging.set_triple_status(triple_id, "approved", note=note, reviewed_at=reviewed_at)
    elif action == "reject":
        staging.set_triple_status(triple_id, "rejected", note=note, reviewed_at=reviewed_at)
    elif action == "correct":
        staging.update_triple(triple_id, subject, predicate, object_)
        staging.set_triple_status(triple_id, "approved", note=note, reviewed_at=reviewed_at)
    else:
        raise ValueError(f"unknown review action: {action}")


def format_triple(row) -> str:
    return (
        f"{row['id']:>5} | {row['subject']} -[{row['predicate']}]-> {row['object']}"
        f"  (conf={row['confidence']}, {row['extractor_model']})"
        f"  [doc={row['doc_id']}#chunk={row['chunk_id']}]"
    )


def _now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _cmd_review(args) -> int:
    cfg = load_config(Path(args.config) if args.config else None)
    staging = Staging(cfg.db_path)
    if args.approve:
        review_action(staging, args.approve, "approve", _now(), note=args.note)
        print(f"approved {args.approve}")
    elif args.reject:
        review_action(staging, args.reject, "reject", _now(), note=args.note)
        print(f"rejected {args.reject}")
    elif args.correct:
        review_action(staging, args.correct, "correct", _now(),
                      subject=args.subject, predicate=args.predicate,
                      object_=args.object, note=args.note)
        print(f"corrected + approved {args.correct}")
    else:
        rows = staging.list_triples("staged")
        for row in rows:
            print(format_triple(row))
        print(f"\n{len(rows)} staged triple(s).")
    staging.close()
    return 0


def add_review_parser(subparsers) -> None:
    p = subparsers.add_parser("review", help="review staged triples")
    p.add_argument("--config", default=None)
    p.add_argument("--list", action="store_true", help="list staged triples (default)")
    p.add_argument("--approve", type=int)
    p.add_argument("--reject", type=int)
    p.add_argument("--correct", type=int)
    p.add_argument("--subject")
    p.add_argument("--predicate")
    p.add_argument("--object")
    p.add_argument("--note")
    p.set_defaults(func=_cmd_review)
