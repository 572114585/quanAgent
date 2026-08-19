"""Offline checkpoint backup helper.

This module deliberately never scans or modifies ``workspace/state/research``.
It backs up the SQLite file first. Root checkpoints are intentionally never
deleted: LangGraph's DeltaChannel values (including ``messages``) are rebuilt
by walking the parent checkpoint chain, so deleting older roots can leave an
orphaned ``ToolMessage`` without its preceding assistant ``tool_calls``.
"""
from __future__ import annotations

import argparse
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

def _backup_database(db: Path, backup_dir: Path) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    target = backup_dir / f"checkpoints-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}.sqlite"
    source = sqlite3.connect(str(db))
    destination = sqlite3.connect(str(target))
    try:
        source.backup(destination)
    finally:
        destination.close()
        source.close()
    return target


def compact_thread(conn: sqlite3.Connection, thread_id: str, *, keep: int = 3) -> int:
    """Return without deleting root checkpoints.

    ``keep`` used to be applied directly to root checkpoints. That is unsafe
    for LangGraph's current SQLite saver because root rows form a linked delta
    history rather than independent full snapshots. A future compactor must
    first materialize a complete checkpoint through the graph/checkpointer API;
    deleting rows here cannot do that safely.
    """
    return 0


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
        return {"database": str(db), "backup": None, "threads": 0, "removed": 0}
    backup = _backup_database(db, Path(backup_dir) if backup_dir else db.parent / "backups")
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
    return {"database": str(db), "backup": str(backup), "threads": len(thread_ids), "removed": removed}


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
