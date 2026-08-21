"""Offline checkpoint backup helper.

This module deliberately never scans or modifies ``workspace/state/research``.
It backs up the SQLite file first. Root checkpoints are intentionally never
deleted: LangGraph's DeltaChannel values (including ``messages``) are rebuilt
by walking the parent checkpoint chain, so deleting older roots can leave an
orphaned ``ToolMessage`` without its preceding assistant ``tool_calls``.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


def _backup_database(db: Path, backup_dir: Path) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    target = backup_dir / f"checkpoints-{datetime.now(timezone.utc):%Y%m%dT%H%M%S%fZ}.sqlite"
    source = sqlite3.connect(str(db))
    destination = sqlite3.connect(str(target))
    try:
        source.backup(destination)
        integrity = destination.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise sqlite3.DatabaseError(
                f"backup integrity check failed for {target}: {integrity}"
            )
    except Exception:
        destination.close()
        source.close()
        target.unlink(missing_ok=True)
        raise
    else:
        destination.close()
        source.close()
    return target


def _prune_backups(backup_dir: Path, *, keep: int) -> int:
    """Keep the newest checkpoint backups and remove only older snapshots."""
    keep = max(1, keep)
    backups = sorted(backup_dir.glob("checkpoints-*.sqlite"), key=lambda path: path.name)
    stale = backups[:-keep]
    for path in stale:
        path.unlink()
    return len(stale)


def _text(value: object) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", "ignore").lower()
    return str(value or "").lower()


def _completed_namespace(rows: list[sqlite3.Row]) -> bool:
    """Accept only an explicitly completed namespace with no interrupt trace.

    Checkpoints are delta chains, so absence of a pending marker is not proof
    of completion.  A maintenance caller must therefore preserve a completed
    status in metadata (the format used by our explicit subgraph lifecycle).
    Unknown LangGraph namespaces remain untouched by design.
    """
    metadata = " ".join(_text(row["metadata"]) for row in rows)
    payload = " ".join(_text(row["checkpoint"]) for row in rows)
    if "interrupt" in metadata or "interrupt" in payload:
        return False
    return any(marker in metadata for marker in ('"status":"completed"', '"status": "completed"', "status=completed"))


def compact_thread(conn: sqlite3.Connection, thread_id: str, *, keep: int = 3) -> int:
    """Delete only confirmed-complete, non-root child namespaces.

    Root history is never compacted.  Every selected child namespace is backed
    up first by :func:`maintain_checkpoint_db`, has an explicit completed marker
    and no pending interrupt.  Its associated writes are deleted in the same
    transaction before the checkpoints.
    """
    namespaces = [
        row[0] for row in conn.execute(
            "SELECT DISTINCT checkpoint_ns FROM checkpoints WHERE thread_id=? AND checkpoint_ns<>''",
            (thread_id,),
        )
    ]
    removed = 0
    for namespace in namespaces:
        rows = list(conn.execute(
            "SELECT checkpoint_id, checkpoint, metadata FROM checkpoints WHERE thread_id=? AND checkpoint_ns=?",
            (thread_id, namespace),
        ))
        if not rows or not _completed_namespace(rows):
            continue
        # `writes` is part of LangGraph's SQLite schema.  Guard it for old DBs.
        if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='writes'").fetchone():
            conn.execute("DELETE FROM writes WHERE thread_id=? AND checkpoint_ns=?", (thread_id, namespace))
        conn.execute("DELETE FROM checkpoints WHERE thread_id=? AND checkpoint_ns=?", (thread_id, namespace))
        removed += len(rows)
    return removed


def maintain_checkpoint_db(
    db_path: str | Path,
    *,
    backup_dir: str | Path | None = None,
    thread_id: str | None = None,
    keep: int = 3,
    vacuum: bool = True,
) -> dict[str, object]:
    db = Path(db_path)
    if not db.exists():
        return {
            "database": str(db),
            "backup": None,
            "threads": 0,
            "removed": 0,
            "pruned": 0,
        }
    resolved_backup_dir = Path(backup_dir) if backup_dir else db.parent / "backups"
    backup = _backup_database(db, resolved_backup_dir)
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    try:
        thread_ids = [thread_id] if thread_id else [
            row[0] for row in conn.execute(
                "SELECT DISTINCT thread_id FROM checkpoints WHERE checkpoint_ns=''"
            )
        ]
        removed = sum(compact_thread(conn, tid, keep=keep) for tid in thread_ids)
        conn.commit()
        if vacuum:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            conn.execute("VACUUM")
            conn.commit()
    finally:
        conn.close()
    pruned = _prune_backups(resolved_backup_dir, keep=max(1, keep))
    return {
        "database": str(db),
        "backup": str(backup),
        "threads": len(thread_ids),
        "removed": removed,
        "pruned": pruned,
    }


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compact completed Agent checkpoints")
    parser.add_argument("--db", default="workspace/state/checkpoints.sqlite")
    parser.add_argument("--backup-dir")
    parser.add_argument("--thread-id")
    parser.add_argument("--keep", type=int, default=3)
    parser.add_argument("--no-vacuum", action="store_true")
    args = parser.parse_args(argv)
    print(json.dumps(maintain_checkpoint_db(
        args.db,
        backup_dir=args.backup_dir,
        thread_id=args.thread_id,
        keep=max(1, args.keep),
        vacuum=not args.no_vacuum,
    ), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
