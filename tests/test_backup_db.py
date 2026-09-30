"""Tests for scripts/backup_db.py.

DATABASE_URL/PBKDF2_ITERATIONS test isolation is set centrally in
conftest.py, before this file (or anything it imports) is ever
collected — see that file for why it has to be centralized rather than
each test file guarding its own import.
"""

import sqlite3

import pytest

from scripts.backup_db import backup_database, prune_old_backups


@pytest.fixture
def source_db(tmp_path):
    path = tmp_path / "source.db"
    con = sqlite3.connect(str(path))
    con.execute("CREATE TABLE hospitals (id INTEGER PRIMARY KEY, name TEXT)")
    con.execute("INSERT INTO hospitals (name) VALUES ('Test Hospital')")
    con.commit()
    con.close()
    return path


class TestBackupDatabase:
    def test_backup_creates_a_valid_copy(self, source_db, tmp_path):
        backup_dir = tmp_path / "backups"
        dest = backup_database(source_db, backup_dir)

        assert dest.exists()
        con = sqlite3.connect(str(dest))
        rows = con.execute("SELECT name FROM hospitals").fetchall()
        assert rows == [("Test Hospital",)]
        assert con.execute("PRAGMA integrity_check").fetchone() == ("ok",)

    def test_backup_is_independent_of_source(self, source_db, tmp_path):
        # A real online backup, not the same file / a hardlink — further
        # writes to the source must not appear in an already-taken backup.
        backup_dir = tmp_path / "backups"
        dest = backup_database(source_db, backup_dir)

        con = sqlite3.connect(str(source_db))
        con.execute("INSERT INTO hospitals (name) VALUES ('Added After Backup')")
        con.commit()
        con.close()

        backup_con = sqlite3.connect(str(dest))
        names = [r[0] for r in backup_con.execute("SELECT name FROM hospitals")]
        assert "Added After Backup" not in names

    def test_backup_missing_source_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            backup_database(tmp_path / "does_not_exist.db", tmp_path / "backups")


class TestPruneOldBackups:
    def test_prune_keeps_only_the_newest_n(self, source_db, tmp_path):
        backup_dir = tmp_path / "backups"
        paths = [backup_database(source_db, backup_dir) for _ in range(5)]

        deleted = prune_old_backups(backup_dir, source_db.stem, keep=2)

        remaining = sorted(backup_dir.glob(f"{source_db.stem}_*"))
        assert len(remaining) == 2
        assert len(deleted) == 3
        # The two newest (last created) must be the ones that survived.
        assert set(remaining) == set(paths[-2:])

    def test_prune_does_not_touch_other_databases(self, tmp_path):
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        (backup_dir / "other_db_20260101T000000Z.db").touch()

        deleted = prune_old_backups(backup_dir, "securederm", keep=0)

        assert deleted == []
        assert (backup_dir / "other_db_20260101T000000Z.db").exists()
