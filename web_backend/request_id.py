"""Per-request correlation IDs.

Every response carries an X-Request-ID, and every log line written while the
request is handled includes it, so a user's report ("it failed, id 3f2a…")
can be matched to the exact server-side traceback. A caller-supplied ID is
reused when it looks sane, which lets a reverse proxy's ID flow through.
"""

import contextvars
import logging
import re
import uuid

HEADER_NAME = "X-Request-ID"
_VALID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")   # no spaces or control chars: it goes into logs

_current: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")


def resolve_request_id(supplied: str | None) -> str:
    """The caller's ID if it is well-formed, otherwise a fresh random one."""
    if supplied and _VALID.match(supplied):
        return supplied
    return uuid.uuid4().hex


def set_request_id(value: str) -> None:
    _current.set(value)


def current_request_id() -> str:
    return _current.get()


class RequestIdFilter(logging.Filter):
    """Adds `request_id` to every record so formatters can print it."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = current_request_id()
        return True
