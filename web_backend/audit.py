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
import threading
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
_handler_lock = threading.Lock()


def _has_handler_for(wanted: str) -> bool:
    return any(
        getattr(handler, "baseFilename", None) == os.path.abspath(wanted)
        for handler in _logger.handlers
    )


def _ensure_handler() -> None:
    wanted = str(AUDIT_LOG_PATH)
    if _has_handler_for(wanted):       # the common case: no lock needed
        return
    # Request handlers run in several threads. Without the lock two first-time
    # callers both see "no handler" and both install one, and from then on every
    # event is written twice.
    with _handler_lock:
        if _has_handler_for(wanted):
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


def read_account_events(
    hospital,
    limit: int = 100,
    actions: set[str] | None = None,
    since: datetime | None = None,
) -> list[dict]:
    """`read_events` for one account, never reaching back before it existed.

    Events are keyed by hospital id, and SQLite gives a deleted account's id
    to the next signup, so without this a new account would list (and
    export) its predecessor's logins, predictions and deletion.
    """
    created = getattr(hospital, "created_at", None)
    if created is not None:
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        # Event times have whole seconds; keep the account's own first ones.
        created = created.replace(microsecond=0)
        if since is not None and since.tzinfo is None:
            since = since.replace(tzinfo=timezone.utc)
        since = created if since is None else max(since, created)
    return read_events(hospital.id, limit, actions=actions, since=since)


def read_events(
    hospital_id: int,
    limit: int = 100,
    actions: set[str] | None = None,
    since: datetime | None = None,
) -> list[dict]:
    """The most recent events for one hospital, newest first.

    `actions` keeps only events with one of those action names; `since` keeps
    only events at or after that moment (a naive value is read as UTC).
    """
    if since is not None and since.tzinfo is None:
        since = since.replace(tzinfo=timezone.utc)
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
            if since is not None:
                try:
                    when = datetime.fromisoformat(event["ts"])
                except (KeyError, TypeError, ValueError):
                    continue
                if when < since:
                    return events   # log is chronological: everything left is older
            if event.get("hospital_id") != hospital_id:
                continue
            if actions is not None and event.get("action") not in actions:
                continue
            events.append(event)
            if len(events) >= limit:
                return events
    return events
