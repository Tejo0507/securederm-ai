"""
Back up the SQLite database (safely, even while the server is running).

Uses sqlite3's online backup API rather than a plain file copy: WAL mode
(enabled by web_backend.database) means the live database can have
uncommitted data sitting in a separate -wal file, so a naive `cp
securederm.db backup.db` can silently produce a backup missing recent
writes, or in the worst case an inconsistent one. Connection.backup()
goes through SQLite itself and always produces a consistent snapshot.

Usage:
    python -m scripts.backup_db
    python -m scripts.backup_db --keep 14   # prune older backups, keep the 14 newest
    python -m scripts.backup_db --source /path/to/other.db
"""

import argparse
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from web_backend.database import DB_PATH

BACKUP_DIR = Path(__file__).resolve().parent.parent / "backups"


def _restrict(path: Path, mode: int) -> None:
    try:
        os.chmod(path, mode)
    except OSError:
        pass  # filesystems without POSIX permissions


def backup_database(source_path: Path, backup_dir: Path) -> Path:
    if not source_path.exists():
        raise FileNotFoundError(f"No database found at {source_path}")

    backup_dir.mkdir(parents=True, exist_ok=True)
    _restrict(backup_dir, 0o700)
    # Microsecond precision so two backups run in quick succession (e.g. a
    # script calling this twice in a test, or a tight manual retry) don't
    # collide on the same filename and silently overwrite one another.
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    dest_path = backup_dir / f"{source_path.stem}_{timestamp}{source_path.suffix}"

    source_conn = sqlite3.connect(str(source_path))
    try:
        dest_conn = sqlite3.connect(str(dest_path))
        try:
            # The snapshot holds emails and password hashes: owner-only,
            # applied before any data is written into it (no-op on Windows).
            _restrict(dest_path, 0o600)
            source_conn.backup(dest_conn)
        finally:
            dest_conn.close()
    finally:
        source_conn.close()

    return dest_path


def prune_old_backups(backup_dir: Path, stem: str, keep: int) -> list[Path]:
    """Delete all but the `keep` most recent backups for this database
    (matched by filename stem, so backing up two different databases into
    the same directory doesn't prune each other's history)."""
    existing = sorted(
        backup_dir.glob(f"{stem}_*"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    to_delete = existing[keep:]
    for path in to_delete:
        path.unlink()
    return to_delete


def main() -> None:
    parser = argparse.ArgumentParser(description="Back up the SecureDerm AI SQLite database.")
    parser.add_argument(
        "--source", type=Path, default=DB_PATH, help="Path to the database file to back up."
    )
    parser.add_argument(
        "--backup-dir", type=Path, default=BACKUP_DIR, help="Directory to write backups into."
    )
    parser.add_argument(
        "--keep",
        type=int,
        default=None,
        help="If set, delete older backups beyond this many most-recent ones.",
    )
    args = parser.parse_args()

    try:
        dest = backup_database(args.source, args.backup_dir)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    size_kb = dest.stat().st_size / 1024
    print(f"Backed up {args.source} -> {dest} ({size_kb:.1f} KB)")

    if args.keep is not None:
        deleted = prune_old_backups(args.backup_dir, args.source.stem, args.keep)
        for path in deleted:
            print(f"Pruned old backup: {path.name}")


if __name__ == "__main__":
    main()
