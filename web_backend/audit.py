"""
Privacy audit trail.

Records *who did what to which data, and when* as JSON lines — logins,
uploads, erasures, password changes, predictions — so a hospital can see the
access history of its own account and an operator can investigate misuse.

Deliberately stores no patient data and no free text from users: only the
hospital id, an action name and a few short, structured fields. Failed
logins record a hash of the email, never the address itself.
"""

import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path

from config.settings import LOGS_DIR

AUDIT_LOG_PATH = Path(os.getenv("AUDIT_LOG_PATH", str(LOGS_DIR / "audit.log")))
_MAX_BYTES = 5 * 1024 * 1024
_BACKUPS = 5

_logger = logging.getLogger("securederm.audit")
_logger.setLevel(logging.INFO)
_logger.propagate = False   # keep audit events out of the general application log


def _ensure_handler() -> None:
    wanted = str(AUDIT_LOG_PATH)
    for handler in _logger.handlers:
        if getattr(handler, "baseFilename", None) == os.path.abspath(wanted):
            return
    for handler in list(_logger.handlers):
        _logger.removeHandler(handler)
        handler.close()
    AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        wanted, maxBytes=_MAX_BYTES, backupCount=_BACKUPS, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter("%(message)s"))
    _logger.addHandler(handler)
    try:
        os.chmod(wanted, 0o600)   # no-op where POSIX modes don't apply
    except OSError:
        pass


def hash_identifier(value: str) -> str:
    """Short stable fingerprint so repeated attempts can be correlated
    without writing the identifier (e.g. an email address) itself."""
    return hashlib.sha256(value.strip().lower().encode()).hexdigest()[:12]


def audit(action: str, hospital_id: int | None = None, **fields) -> None:
    """Append one event. Never raises: auditing must not break a request."""
    try:
        _ensure_handler()
        event = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "action": action,
            "hospital_id": hospital_id,
            **{k: v for k, v in fields.items() if v is not None},
        }
        _logger.info(json.dumps(event, separators=(",", ":")))
    except Exception:
        logging.getLogger("web_backend").exception("Could not write audit event")


def read_events(hospital_id: int, limit: int = 100) -> list[dict]:
    """The most recent events for one hospital, newest first."""
    paths = [AUDIT_LOG_PATH] + [
        AUDIT_LOG_PATH.with_name(f"{AUDIT_LOG_PATH.name}.{i}") for i in range(1, _BACKUPS + 1)
    ]
    events: list[dict] = []
    for path in paths:   # newest file first
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in reversed(lines):
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if event.get("hospital_id") == hospital_id:
                events.append(event)
                if len(events) >= limit:
                    return events
    return events
