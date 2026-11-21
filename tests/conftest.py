"""Session-wide test isolation, applied before any test module is collected.

pytest always imports conftest.py before any test file in its directory,
which is exactly the guarantee this needs: several test files import
something that transitively imports web_backend.database (directly, or
via scripts.backup_db), and that module binds its `engine` to whatever
DATABASE_URL is set at the moment of its *first* import in the process —
imports are cached, so only the first one matters. Setting it here,
once, centrally, means it's no longer a race between test files over
which one happens to sort first alphabetically (a previous version of
this suite got this wrong: tests/test_backup_db.py sorts before
tests/test_web_backend_auth.py, imports scripts.backup_db, which imports
web_backend.database — so without a guard *there*, every other file's
own DATABASE_URL override was silently a no-op, and a full test run was
writing test fixture data straight into the real dev database).

PBKDF2_ITERATIONS is dropped here too for the same reason it's dropped
in the files that used to set it individually: the production default
(600,000 rounds) is deliberately slow, and tests care about hash/verify
correctness, not paying that real-world cost on every signup.

UPLOAD_DIR has the exact same hazard as DATABASE_URL did: it's a
module-level constant resolved at import time in
web_backend.routers.hospital_router, and was hardcoded to the project's
real datasets/uploads/ directory with no override at all — confirmed by
finding dozens of test-fixture files (wound.png, evil.png under
hospital IDs that only exist from test runs) actually sitting in that
real directory on disk. Centralizing it here fixes it the same way.
"""

import logging
import os
import shutil
import tempfile

_TEST_DB_DIR = tempfile.mkdtemp(prefix="securederm_test_")
_TEST_UPLOAD_DIR = tempfile.mkdtemp(prefix="securederm_test_uploads_")
_TEST_AUDIT_DIR = tempfile.mkdtemp(prefix="securederm_test_audit_")
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_TEST_DB_DIR, 'test.db')}"
os.environ.setdefault("PBKDF2_ITERATIONS", "1000")
os.environ["UPLOAD_DIR"] = _TEST_UPLOAD_DIR
# The aggregator persists its global model to checkpoints/ after each round;
# tests must never write into (or restore from) the real checkpoints dir.
os.environ["AGGREGATOR_PERSIST"] = "false"
# The audit trail writes JSON lines to logs/audit.log; keep tests out of it.
os.environ["AUDIT_LOG_PATH"] = os.path.join(_TEST_AUDIT_DIR, "audit.log")


def pytest_sessionfinish(session, exitstatus):
    """Remove the scratch directories created above.

    Nothing ever deleted them, so every run left a database, an uploads tree
    and an audit log behind in the system temp directory. Hundreds of runs add
    up to hundreds of megabytes, which on a nearly full disk makes unrelated
    tests fail with "No space left on device".

    The database engine and the audit log handler hold their files open, and
    Windows will not delete an open file, so release both first.
    """
    try:
        from web_backend.database import engine

        engine.dispose()
    except Exception:  # never let cleanup fail the run
        pass
    audit_logger = logging.getLogger("securederm.audit")
    for handler in list(audit_logger.handlers):
        audit_logger.removeHandler(handler)
        handler.close()
    for directory in (_TEST_DB_DIR, _TEST_UPLOAD_DIR, _TEST_AUDIT_DIR):
        shutil.rmtree(directory, ignore_errors=True)
