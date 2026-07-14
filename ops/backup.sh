#!/usr/bin/env bash
#
# backup.sh — Odysseus brain-host data backup (Module 0, DoD #5).
#
# Creates a timestamped, transaction-consistent snapshot of the Odysseus
# `data/` directory: every SQLite database is copied with the online
# `.backup` API (no server downtime, no torn snapshot), everything else is
# archived as-is. Includes a `--restore-test` mode that extracts an archive
# and runs `PRAGMA integrity_check` to prove the archive is actually usable.
#
# This talks to nothing over the network and imports no Odysseus code — it
# only reads files on disk. Safe to run while the brain is serving.
#
# Usage:
#   ./backup.sh                 # create a backup, prune to last KEEP
#   ./backup.sh --restore-test  # verify the newest archive is restorable
#   ./backup.sh --restore-test <archive.tar.gz>   # verify a specific archive
#   ./backup.sh --list          # list existing archives
#   ./backup.sh --help
#
# Config (env vars, with defaults):
#   ODYSSEUS_DATA_DIR    source data dir   (default: <repo>/../odysseus/data)
#   ODYSSEUS_BACKUP_DIR  archive dest dir  (default: $HOME/odysseus-backups)
#   ODYSSEUS_BACKUP_KEEP archives to keep  (default: 7)

set -euo pipefail

# --- resolve defaults ---------------------------------------------------------
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# ops/ lives in the extension repo; the odysseus clone is a sibling of the repo.
DEFAULT_DATA_DIR="$(cd -- "$SCRIPT_DIR/../.." && pwd)/odysseus/data"

DATA_DIR="${ODYSSEUS_DATA_DIR:-$DEFAULT_DATA_DIR}"
BACKUP_DIR="${ODYSSEUS_BACKUP_DIR:-$HOME/odysseus-backups}"
KEEP="${ODYSSEUS_BACKUP_KEEP:-7}"

log()  { printf '  %s\n' "$*"; }
step() { printf '\n▸ %s\n' "$*"; }
die()  { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

command -v sqlite3 >/dev/null 2>&1 || die "sqlite3 CLI not found on PATH"

# Is $1 a real SQLite database file?
is_sqlite() {
  [ -f "$1" ] || return 1
  sqlite3 "$1" 'PRAGMA schema_version;' >/dev/null 2>&1
}

# --- create a backup ----------------------------------------------------------
do_backup() {
  [ -d "$DATA_DIR" ] || die "data dir not found: $DATA_DIR"
  mkdir -p "$BACKUP_DIR"

  local ts stage archive
  ts="$(date +%Y%m%d-%H%M%S)"
  stage="$(mktemp -d "${TMPDIR:-/tmp}/odysseus-backup.XXXXXX")"
  archive="$BACKUP_DIR/odysseus-data-$ts.tar.gz"
  trap 'rm -rf "$stage"' RETURN

  step "Backing up $DATA_DIR"

  # 1. Copy the whole tree (captures every non-DB file and all subdirs).
  cp -a "$DATA_DIR/." "$stage/"

  # 2. Overwrite every SQLite DB with a consistent online snapshot, so a
  #    write landing mid-copy can never leave a torn database in the archive.
  local db rel count=0
  while IFS= read -r -d '' db; do
    is_sqlite "$db" || continue
    rel="${db#"$DATA_DIR"/}"
    rm -f "$stage/$rel" "$stage/$rel-wal" "$stage/$rel-shm"
    sqlite3 "$db" ".backup '$stage/$rel'"
    log "snapshot: $rel"
    count=$((count + 1))
  done < <(find "$DATA_DIR" \( -name '*.db' -o -name '*.sqlite3' -o -name '*.sqlite' \) -type f -print0)
  log "$count database(s) snapshotted consistently"

  # 3. Archive the staged copy.
  tar -czf "$archive" -C "$stage" .
  log "wrote $(du -h "$archive" | cut -f1)  →  $archive"

  # 4. Prune to the newest $KEEP archives.
  prune

  step "Backup complete"
  log "$archive"
  printf '\nVerify it with:  %s --restore-test\n' "$0"
}

# --- prune old archives -------------------------------------------------------
prune() {
  local -a all
  mapfile -t all < <(ls -1 "$BACKUP_DIR"/odysseus-data-*.tar.gz 2>/dev/null | sort)
  local n="${#all[@]}"
  if [ "$n" -gt "$KEEP" ]; then
    local remove=$((n - KEEP)) i
    for ((i = 0; i < remove; i++)); do
      rm -f "${all[$i]}"
      log "pruned old: $(basename "${all[$i]}")"
    done
  fi
}

# --- restore-test an archive --------------------------------------------------
do_restore_test() {
  local archive="${1:-}"
  if [ -z "$archive" ]; then
    archive="$(ls -1 "$BACKUP_DIR"/odysseus-data-*.tar.gz 2>/dev/null | sort | tail -1)"
    [ -n "$archive" ] || die "no archives found in $BACKUP_DIR"
  fi
  [ -f "$archive" ] || die "archive not found: $archive"

  local test_dir
  test_dir="$(mktemp -d "${TMPDIR:-/tmp}/odysseus-restore.XXXXXX")"
  trap 'rm -rf "$test_dir"' RETURN

  step "Restore-test: $archive"

  tar -xzf "$archive" -C "$test_dir"
  log "extracted OK"

  # Key markers must be present.
  local ok=1 marker
  for marker in app.db settings.json; do
    if [ -e "$test_dir/$marker" ]; then
      log "present: $marker"
    else
      log "MISSING: $marker"; ok=0
    fi
  done

  # Every DB in the archive must pass integrity_check.
  local db rel result dbcount=0
  while IFS= read -r -d '' db; do
    is_sqlite "$db" || continue
    rel="${db#"$test_dir"/}"
    result="$(sqlite3 "$db" 'PRAGMA integrity_check;' 2>&1 | head -1)"
    if [ "$result" = "ok" ]; then
      log "integrity ok: $rel"
    else
      log "integrity FAIL ($result): $rel"; ok=0
    fi
    dbcount=$((dbcount + 1))
  done < <(find "$test_dir" \( -name '*.db' -o -name '*.sqlite3' -o -name '*.sqlite' \) -type f -print0)
  log "$dbcount database(s) checked"

  if [ "$ok" -eq 1 ]; then
    step "RESTORE-TEST PASSED — archive is usable ✔"
  else
    step "RESTORE-TEST FAILED — see markers above"
    exit 1
  fi
}

# --- list ---------------------------------------------------------------------
do_list() {
  step "Archives in $BACKUP_DIR"
  if ls -1 "$BACKUP_DIR"/odysseus-data-*.tar.gz >/dev/null 2>&1; then
    ls -lh "$BACKUP_DIR"/odysseus-data-*.tar.gz | awk '{print "  "$5"\t"$9}'
  else
    log "(none yet)"
  fi
}

usage() { sed -n '2,30p' "$0" | sed 's/^# \{0,1\}//'; }

# --- dispatch -----------------------------------------------------------------
case "${1:-}" in
  ""|backup)      do_backup ;;
  --restore-test) do_restore_test "${2:-}" ;;
  --list)         do_list ;;
  -h|--help)      usage ;;
  *)              die "unknown option: $1  (try --help)" ;;
esac