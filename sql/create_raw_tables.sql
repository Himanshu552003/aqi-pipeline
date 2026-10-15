-- create_raw_tables.sql - raw layer tables. Portable SQL: runs unchanged on PostgreSQL and Snowflake.
-- Safe to run many times (IF NOT EXISTS). load.py runs it before every load.
-- (Statements are split on semicolons by load.py, so do not use semicolons inside comments.)

CREATE SCHEMA IF NOT EXISTS raw;

-- One row per station x pollutant x reading time (long format, exactly as the API delivers it).
-- Natural key = station + pollutant_id + reading_time_utc. Postgres enforces the primary key,
-- Snowflake only documents it, so idempotency comes from the MERGE in load.py, not from the key.
CREATE TABLE IF NOT EXISTS raw.aqi_readings (
    station            VARCHAR(255)     NOT NULL,
    pollutant_id       VARCHAR(20)      NOT NULL,
    reading_time_utc   TIMESTAMP        NOT NULL,
    reading_time_ist   TIMESTAMP        NOT NULL,
    country            VARCHAR(100),
    state              VARCHAR(100),
    city               VARCHAR(100),
    latitude           DOUBLE PRECISION,
    longitude          DOUBLE PRECISION,
    min_value          DOUBLE PRECISION,
    max_value          DOUBLE PRECISION,
    avg_value          DOUBLE PRECISION NOT NULL,
    fetched_at_utc     TIMESTAMP        NOT NULL,
    loaded_at_utc      TIMESTAMP        NOT NULL,
    PRIMARY KEY (station, pollutant_id, reading_time_utc)
);

-- Landing table: each run empties it, bulk-inserts the new snapshot, then MERGEs into aqi_readings.
CREATE TABLE IF NOT EXISTS raw.aqi_readings_stage (
    station            VARCHAR(255),
    pollutant_id       VARCHAR(20),
    reading_time_utc   TIMESTAMP,
    reading_time_ist   TIMESTAMP,
    country            VARCHAR(100),
    state              VARCHAR(100),
    city               VARCHAR(100),
    latitude           DOUBLE PRECISION,
    longitude          DOUBLE PRECISION,
    min_value          DOUBLE PRECISION,
    max_value          DOUBLE PRECISION,
    avg_value          DOUBLE PRECISION,
    fetched_at_utc     TIMESTAMP,
    loaded_at_utc      TIMESTAMP
);
