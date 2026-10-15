# load.py - load cleaned readings into the raw layer of every target DB (Postgres and/or Snowflake)
#
# Idempotent: running the same snapshot twice never creates duplicates.
#   1. empty the stage table      2. bulk-insert the snapshot into the stage table
#   3. MERGE stage -> raw.aqi_readings on the natural key (station + pollutant + time):
#        new key            -> INSERT
#        key exists, values changed -> UPDATE (the source revised the reading)
#        key exists, same values    -> nothing
# MERGE is standard SQL and works on both PostgreSQL (15+) and Snowflake.
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.engine import Engine

from scraper.db_connection import SUPPORTED_DB_TYPES, get_engine

logger = logging.getLogger(__name__)

CREATE_TABLES_SQL = Path(__file__).resolve().parent.parent / "sql" / "create_raw_tables.sql"
KEY_COLUMNS = ["station", "pollutant_id", "reading_time_utc"]
VALUE_COLUMNS = [
    "reading_time_ist", "country", "state", "city", "latitude", "longitude",
    "min_value", "max_value", "avg_value",
]
ALL_COLUMNS = KEY_COLUMNS + VALUE_COLUMNS + ["fetched_at_utc", "loaded_at_utc"]


def get_load_targets() -> list[str]:
    """LOAD_TARGETS=postgres,snowflake -> ['postgres', 'snowflake']"""
    load_dotenv()
    raw_value = os.getenv("LOAD_TARGETS", "postgres")
    targets = [t.strip().lower() for t in raw_value.split(",") if t.strip()]
    unknown = set(targets) - set(SUPPORTED_DB_TYPES)
    if unknown:
        raise ValueError(f"Unknown LOAD_TARGETS {unknown}; use {SUPPORTED_DB_TYPES}")
    return targets


def ensure_tables(engine: Engine) -> None:
    """Run create_raw_tables.sql (safe to repeat thanks to IF NOT EXISTS)."""
    sql = CREATE_TABLES_SQL.read_text(encoding="utf-8")
    sql = "\n".join(line for line in sql.splitlines() if not line.strip().startswith("--"))
    statements = [s.strip() for s in sql.split(";") if s.strip()]
    with engine.begin() as conn:
        for statement in statements:
            conn.execute(text(statement))


def build_merge_sql() -> str:
    on_clause = " AND ".join(f"t.{c} = s.{c}" for c in KEY_COLUMNS)
    # IS DISTINCT FROM is a NULL-safe "!=" (NULL vs NULL counts as equal) - supported by both DBs
    changed = " OR ".join(f"t.{c} IS DISTINCT FROM s.{c}" for c in VALUE_COLUMNS)
    update_set = ", ".join(f"{c} = s.{c}" for c in VALUE_COLUMNS + ["fetched_at_utc", "loaded_at_utc"])
    insert_cols = ", ".join(ALL_COLUMNS)
    insert_vals = ", ".join(f"s.{c}" for c in ALL_COLUMNS)
    return f"""
        MERGE INTO raw.aqi_readings AS t
        USING raw.aqi_readings_stage AS s
            ON {on_clause}
        WHEN MATCHED AND ({changed}) THEN
            UPDATE SET {update_set}
        WHEN NOT MATCHED THEN
            INSERT ({insert_cols}) VALUES ({insert_vals})
    """


def upsert_readings(engine: Engine, df: pd.DataFrame) -> int:
    """Stage + MERGE one cleaned snapshot. Returns the number of rows inserted or updated."""
    df = df.copy()
    df["loaded_at_utc"] = datetime.now(timezone.utc).replace(tzinfo=None)
    df = df[ALL_COLUMNS]

    with engine.begin() as conn:       # one transaction: all of it succeeds, or none of it
        conn.execute(text("DELETE FROM raw.aqi_readings_stage"))
        # method="multi" sends many rows per INSERT - far fewer network round trips
        df.to_sql("aqi_readings_stage", conn, schema="raw", if_exists="append",
                  index=False, method="multi", chunksize=500)
        result = conn.execute(text(build_merge_sql()))
        changed_rows = result.rowcount
        conn.execute(text("DELETE FROM raw.aqi_readings_stage"))
    return changed_rows


def load(df: pd.DataFrame) -> dict[str, int]:
    """Dual-load: write the snapshot to every target in LOAD_TARGETS.

    Every target is attempted even if one fails, so Postgres keeps its full history
    when Snowflake has a problem (and vice versa). Any failure is raised at the end.
    """
    results, errors = {}, {}
    for target in get_load_targets():
        try:
            engine = get_engine(target)
            ensure_tables(engine)
            results[target] = upsert_readings(engine, df)
            logger.info("[%s] %d rows inserted/updated (snapshot had %d rows)", target, results[target], len(df))
        except Exception as err:   # noqa: BLE001 - we re-raise below after trying the other targets
            logger.error("[%s] load failed: %s", target, type(err).__name__)
            errors[target] = err

    if errors:
        failed = ", ".join(errors)
        raise RuntimeError(f"Load failed for: {failed}") from next(iter(errors.values()))
    return results
