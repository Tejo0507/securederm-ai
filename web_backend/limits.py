"""Bounds for client-supplied numbers that end up in SQL.

SQLite integers are 64-bit: binding a larger Python int raises OverflowError,
which would surface as a 500 for what is simply a bad request. Declaring the
bounds on the parameters makes FastAPI answer 422 instead.
"""

MAX_DB_INT = 2**63 - 1          # largest value a SQLite INTEGER can hold
MAX_OFFSET = 10_000_000         # nobody pages ten million rows deep; keeps OFFSET sane
