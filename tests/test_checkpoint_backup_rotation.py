import sqlite3

from tools.checkpoint_maintenance import maintain_checkpoint_db


def _create_checkpoint_db(path):
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            "CREATE TABLE checkpoints ("
            "thread_id TEXT, checkpoint_ns TEXT, checkpoint_id TEXT, "
            "checkpoint BLOB, metadata BLOB)"
        )
        conn.commit()
    finally:
        conn.close()


def test_checkpoint_backups_are_integrity_checked_and_rotated(tmp_path):
    db_path = tmp_path / "checkpoints.sqlite"
    backup_dir = tmp_path / "backups"
    _create_checkpoint_db(db_path)

    for _ in range(5):
        result = maintain_checkpoint_db(
            db_path,
            backup_dir=backup_dir,
            keep=3,
            vacuum=False,
        )
        assert result["backup"]

    backups = sorted(backup_dir.glob("checkpoints-*.sqlite"))
    assert len(backups) == 3
    assert result["pruned"] >= 1

    for backup in backups:
        conn = sqlite3.connect(backup)
        try:
            assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        finally:
            conn.close()

    assert not (tmp_path / "research").exists()
