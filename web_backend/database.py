import logging
import os

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, declarative_base
from pathlib import Path

_logger = logging.getLogger("web_backend.database")

DB_PATH = Path(__file__).resolve().parent.parent / "securederm.db"
# Overridable so tests (and any future deployment) can point at an isolated
# database instead of writing through to the shared dev/demo file.
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DB_PATH}")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


@event.listens_for(Engine, "connect")
def _set_sqlite_pragmas(dbapi_connection, connection_record) -> None:
    """SQLite defaults that matter for data integrity and concurrency:

    - foreign_keys is OFF by default per-connection in SQLite, so the
      ForeignKey columns on Dataset/MLModel were declared but silently
      never enforced — a row could reference a hospital_id that doesn't
      exist. Every new connection now turns it on explicitly.
    - journal_mode=WAL lets readers and a writer work concurrently
      instead of the default rollback-journal mode, which takes an
      exclusive lock for the whole duration of a write — relevant once
      this runs as a real, possibly multi-worker server rather than a
      single dev process.
    """
    if not DATABASE_URL.startswith("sqlite"):
        return
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def run_migrations() -> None:
    """Add columns that newer code expects but an existing database file
    (created by an older version of this app) won't have yet.

    Base.metadata.create_all() only creates missing *tables* — it never
    alters an existing one, so a fresh column added to a model silently
    becomes a startup crash ("no such column") against any database that
    predates it. This is a deliberately minimal stand-in for a real
    migration tool (Alembic) proportional to how small this schema is;
    each entry is (table, column, ddl_type, backfill_sql | None).
    """
    if not DATABASE_URL.startswith("sqlite"):
        return  # pragma-based introspection below is SQLite-specific

    column_migrations = [
        (
            "hospitals",
            "email_verified",
            "BOOLEAN NOT NULL DEFAULT 0",
            # Accounts created before verification existed predate the
            # requirement — grandfather them in rather than locking out
            # every existing hospital the next time this file is opened.
            "UPDATE hospitals SET email_verified = 1",
        ),
        ("hospitals", "email_verification_token_hash", "VARCHAR(128)", None),
        ("hospitals", "email_verification_expires_at", "DATETIME", None),
    ]

    with engine.begin() as conn:
        existing_tables = conn.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).scalars().all()
        if "hospitals" not in existing_tables:
            return  # fresh database — create_all() will define it correctly

        existing_columns = {
            row[1]
            for row in conn.exec_driver_sql("PRAGMA table_info(hospitals)").fetchall()
        }
        for table, column, ddl_type, backfill_sql in column_migrations:
            if column in existing_columns:
                continue
            _logger.warning("Migrating database: adding %s.%s", table, column)
            conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {column} {ddl_type}")
            if backfill_sql:
                conn.exec_driver_sql(backfill_sql)

        # Foreign-key / lookup columns that were queried on (Dataset.hospital_id
        # in list_datasets, MLModel.created_by, Hospital.email_verification_token_hash
        # in verify-email) but never indexed — fine at today's row counts, a full
        # table scan waiting to happen once there's real data. CREATE INDEX
        # IF NOT EXISTS is natively idempotent, unlike ALTER TABLE ADD COLUMN.
        index_migrations = [
            ("ix_datasets_hospital_id", "datasets", "hospital_id"),
            ("ix_ml_models_created_by", "ml_models", "created_by"),
            (
                "ix_hospitals_email_verification_token_hash",
                "hospitals",
                "email_verification_token_hash",
            ),
        ]
        for index_name, table, column in index_migrations:
            if table not in existing_tables:
                continue
            conn.exec_driver_sql(
                f"CREATE INDEX IF NOT EXISTS {index_name} ON {table} ({column})"
            )
