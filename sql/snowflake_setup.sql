-- snowflake_setup.sql - one-time Snowflake setup (run in a Snowsight worksheet as ACCOUNTADMIN).
-- Only needed when you start the Snowflake trial (Phase 3). Replace the password before running.
-- Cost control: X-Small warehouse (the smallest) that suspends after 60 seconds of no queries,
-- so you only pay credits for the few seconds the hourly pipeline actually runs.

USE ROLE ACCOUNTADMIN;

CREATE WAREHOUSE IF NOT EXISTS AQI_WH
    WAREHOUSE_SIZE = 'XSMALL'
    AUTO_SUSPEND = 60
    AUTO_RESUME = TRUE
    INITIALLY_SUSPENDED = TRUE;

CREATE DATABASE IF NOT EXISTS AQI_DB;
CREATE SCHEMA IF NOT EXISTS AQI_DB.RAW;
CREATE SCHEMA IF NOT EXISTS AQI_DB.STAGING;
CREATE SCHEMA IF NOT EXISTS AQI_DB.ANALYTICS;

CREATE ROLE IF NOT EXISTS AQI_ROLE;
GRANT USAGE ON WAREHOUSE AQI_WH TO ROLE AQI_ROLE;
GRANT ALL ON DATABASE AQI_DB TO ROLE AQI_ROLE;
GRANT ALL ON ALL SCHEMAS IN DATABASE AQI_DB TO ROLE AQI_ROLE;
GRANT ALL ON FUTURE SCHEMAS IN DATABASE AQI_DB TO ROLE AQI_ROLE;

-- A service user for the pipeline (not a person, so no MFA prompt)
CREATE USER IF NOT EXISTS AQI_USER
    PASSWORD = 'CHANGE_ME_to_a_long_random_password'
    TYPE = LEGACY_SERVICE
    DEFAULT_ROLE = AQI_ROLE
    DEFAULT_WAREHOUSE = AQI_WH;
GRANT ROLE AQI_ROLE TO USER AQI_USER;

-- Safety net: stop the warehouse if the month uses more than 5 credits
CREATE RESOURCE MONITOR IF NOT EXISTS AQI_MONITOR WITH CREDIT_QUOTA = 5
    TRIGGERS ON 80 PERCENT DO NOTIFY
             ON 100 PERCENT DO SUSPEND;
ALTER WAREHOUSE AQI_WH SET RESOURCE_MONITOR = AQI_MONITOR;
