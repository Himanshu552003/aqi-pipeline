# clean.py - light validation (types, nulls, value ranges, timezones) before loading into the raw layer
#
# The raw API data is all strings, in "long" format (one row per station x pollutant),
# with last_update as 'DD-MM-YYYY HH:MM:SS' in Indian Standard Time and no timezone marker.
# Heavy business logic (AQI calculation, city ranking...) lives in dbt, not here.
import logging

import pandas as pd

logger = logging.getLogger(__name__)

SOURCE_TIME_FORMAT = "%d-%m-%Y %H:%M:%S"
SOURCE_TIMEZONE = "Asia/Kolkata"
MAX_INDEX_VALUE = 500          # CPCB sub-indices are capped at 500
KEY_COLUMNS = ["station", "pollutant_id", "reading_time_utc"]

# Order of columns in raw.aqi_readings (loaded_at_utc is added by load.py)
OUTPUT_COLUMNS = [
    "station", "pollutant_id", "reading_time_utc", "reading_time_ist",
    "country", "state", "city", "latitude", "longitude",
    "min_value", "max_value", "avg_value", "fetched_at_utc",
]


def parse_ist_to_utc(series: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Parse 'DD-MM-YYYY HH:MM:SS' IST strings. Returns (utc, ist) as timezone-naive timestamps.

    We store naive timestamps with the zone in the column NAME (_utc / _ist) because naive
    TIMESTAMP behaves the same way in Postgres and Snowflake (portable SQL).
    """
    ist_naive = pd.to_datetime(series, format=SOURCE_TIME_FORMAT, errors="coerce")
    utc_naive = ist_naive.dt.tz_localize(SOURCE_TIMEZONE).dt.tz_convert("UTC").dt.tz_localize(None)
    return utc_naive, ist_naive


def clean(df: pd.DataFrame) -> pd.DataFrame:
    """Validate and type-cast one API snapshot. Returns a DataFrame with OUTPUT_COLUMNS."""
    rows_in = len(df)
    df = df.copy()

    # 1. Trim whitespace in every text column
    text_cols = ["country", "state", "city", "station", "pollutant_id", "last_update"]
    for col in text_cols:
        df[col] = df[col].astype("string").str.strip()
    df["pollutant_id"] = df["pollutant_id"].str.upper()

    # 2. Cast numbers. The API sends strings and uses 'NA' for missing -> errors="coerce" makes them NaN
    for col in ["latitude", "longitude", "min_value", "max_value", "avg_value"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # 3. Timestamps: source time is IST, we keep both IST (for humans) and UTC (for storage/joins)
    df["reading_time_utc"], df["reading_time_ist"] = parse_ist_to_utc(df["last_update"])
    df["fetched_at_utc"] = pd.to_datetime(df["fetched_at_utc"], utc=True).dt.tz_localize(None)

    # 4. Drop rows we cannot use: no key or no measured value
    required = ["station", "pollutant_id", "reading_time_utc", "avg_value"]
    missing = df[required].isna().any(axis=1)
    if missing.any():
        logger.warning("Dropping %d rows with missing station / pollutant / time / avg_value", missing.sum())
    df = df[~missing]

    # 5. Range checks: an index cannot be negative or above 500
    out_of_range = (df["avg_value"] < 0) | (df["avg_value"] > MAX_INDEX_VALUE)
    if out_of_range.any():
        logger.warning("Dropping %d rows with avg_value outside 0-%d", out_of_range.sum(), MAX_INDEX_VALUE)
    df = df[~out_of_range]

    # 6. Readings from the future are a data error (allow 1 hour of clock difference)
    future = df["reading_time_utc"] > df["fetched_at_utc"] + pd.Timedelta(hours=1)
    if future.any():
        logger.warning("Dropping %d rows with a reading time in the future", future.sum())
    df = df[~future]

    # 7. Sanity check (warn only): min <= avg <= max
    inconsistent = (df["min_value"] > df["avg_value"]) | (df["avg_value"] > df["max_value"])
    if inconsistent.any():
        logger.warning("%d rows have avg_value outside [min_value, max_value] (kept)", inconsistent.sum())

    # 8. Remove duplicates on the natural key, so the load never conflicts with itself
    dupes = df.duplicated(subset=KEY_COLUMNS, keep="last")
    if dupes.any():
        logger.warning("Dropping %d duplicate rows (same station + pollutant + time)", dupes.sum())
    df = df[~dupes]

    logger.info("Cleaned %d -> %d rows", rows_in, len(df))
    return df[OUTPUT_COLUMNS].reset_index(drop=True)
