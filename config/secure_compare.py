"""Constant-time comparison of secrets that arrive over HTTP.

``secrets.compare_digest`` accepts ``str`` only when both sides are ASCII and
raises ``TypeError`` otherwise. Header values and JSON strings are attacker
controlled, so a token such as ``"tök"`` would turn an ordinary
"wrong credential" answer into an unhandled 500. Comparing the UTF-8 bytes
keeps the comparison constant-time and makes any mismatch a plain ``False``.
"""

import secrets


def constant_time_equals(expected: str | None, supplied: str | None) -> bool:
    """True when both values are present and identical; never raises."""
    if expected is None or supplied is None:
        return False
    return secrets.compare_digest(
        expected.encode("utf-8", "surrogatepass"),
        supplied.encode("utf-8", "surrogatepass"),
    )
