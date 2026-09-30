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
"""

import os
import tempfile

_TEST_DB_DIR = tempfile.mkdtemp(prefix="securederm_test_")
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_TEST_DB_DIR, 'test.db')}"
os.environ.setdefault("PBKDF2_ITERATIONS", "1000")
