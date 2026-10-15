# db_connection.py - returns a SQLAlchemy engine for the DB chosen by DB_TYPE in .env
#
# Every other file asks THIS file for a connection, so switching databases is a one-line
# change in .env (DB_TYPE=postgres | snowflake) - no code changes, no data migration.
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import URL, Engine

SUPPORTED_DB_TYPES = ("postgres", "snowflake")


def _require(name: str) -> str:
    """Read a required environment variable or fail with a clear message."""
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Environment variable {name} is missing. Add it to your .env file.")
    return value


def get_db_type() -> str:
    load_dotenv()
    db_type = os.getenv("DB_TYPE", "postgres").strip().lower()
    if db_type not in SUPPORTED_DB_TYPES:
        raise ValueError(f"DB_TYPE must be one of {SUPPORTED_DB_TYPES}, got {db_type!r}")
    return db_type


def get_engine(db_type: str | None = None) -> Engine:
    """Return an engine for `db_type` (defaults to DB_TYPE from the environment)."""
    load_dotenv()
    db_type = (db_type or get_db_type()).lower()

    if db_type == "postgres":
        url = URL.create(
            "postgresql+psycopg2",
            username=_require("POSTGRES_USER"),
            password=_require("POSTGRES_PASSWORD"),   # URL.create escapes special characters for us
            host=_require("POSTGRES_HOST"),
            port=int(os.getenv("POSTGRES_PORT", "5432")),
            database=_require("POSTGRES_DB"),
            query={"sslmode": os.getenv("POSTGRES_SSLMODE", "require")},
        )
        # pool_pre_ping: Neon suspends idle databases, so test connections before using them
        return create_engine(url, pool_pre_ping=True)

    if db_type == "snowflake":
        # Imported here so the Postgres-only setup does not need the Snowflake package to load
        from snowflake.sqlalchemy import URL as SnowflakeURL

        url = SnowflakeURL(
            account=_require("SNOWFLAKE_ACCOUNT"),
            user=_require("SNOWFLAKE_USER"),
            password=_require("SNOWFLAKE_PASSWORD"),
            database=_require("SNOWFLAKE_DATABASE"),
            schema=os.getenv("SNOWFLAKE_SCHEMA", "RAW"),
            warehouse=_require("SNOWFLAKE_WAREHOUSE"),
            role=_require("SNOWFLAKE_ROLE"),
        )
        return create_engine(url)

    raise ValueError(f"Unsupported db_type {db_type!r}")


if __name__ == "__main__":
    # Quick connection test: python -m scraper.db_connection
    from sqlalchemy import text

    engine = get_engine()
    with engine.connect() as conn:
        print(f"Connected to {get_db_type()}: {conn.execute(text('select current_timestamp')).scalar()}")
