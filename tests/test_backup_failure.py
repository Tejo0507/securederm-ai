"""A backup that fails must leave nothing behind that looks like a backup."""

import sys

import pytest

from scripts import backup_db


@pytest.fixture
def not_a_database(tmp_path):
    path = tmp_path / "broken.db"
    path.write_bytes(b"this is not an SQLite file" * 100)
    return path


def test_failed_backup_removes_its_partial_file(not_a_database, tmp_path):
    backup_dir = tmp_path / "backups"

    with pytest.raises(backup_db.sqlite3.Error):
        backup_db.backup_database(not_a_database, backup_dir)

    assert list(backup_dir.iterdir()) == []


def test_command_line_reports_the_failure_without_a_traceback(
    not_a_database, tmp_path, monkeypatch, capsys
):
    monkeypatch.setattr(sys, "argv", [
        "backup_db", "--source", str(not_a_database),
        "--backup-dir", str(tmp_path / "backups"), "--keep", "1",
    ])

    with pytest.raises(SystemExit) as exit_info:
        backup_db.main()

    assert exit_info.value.code == 1
    assert "could not back up" in capsys.readouterr().err
