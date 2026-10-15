# PROGRESS

## Current position
**All phases built (2026-10-14).** Claude wrote the full project in one session because of a resume
deadline (2026-10-15). Mentor mode was paused for this. Next: deploy (GitHub Actions + Streamlit Cloud),
then **study the code** so I can explain every part in interviews (see "Study plan" below).

## Phase 0: Setup & foundations ✅
- Tools checked (Python 3.11.9, Git 2.45.2, VS Code), folder structure, .venv, requirements.txt
- .gitignore, .env.example, .env, git init, repo https://github.com/Himanshu552003/aqi-pipeline
- Neon Postgres (Singapore, PostgreSQL 18, db neondb). Connection test passed (SSL)

## Phase 1: Data source & scraping ✅
- Main source: data.gov.in API (CPCB "Real time Air Quality Index from various locations",
  resource 3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69, GODL-India licence: attribution required)
- Scrape: Wikipedia "List of cities in India by population" -> dbt seed (scraper/scrape_population.py)
- scrape.py: pagination (100/page: bigger pages time out), retries + exponential backoff, no retry on 4xx,
  User-Agent, rate limiting, API key never logged

## Phase 2: Raw layer in PostgreSQL ✅
- sql/create_raw_tables.sql: raw.aqi_readings (PK station + pollutant + reading_time_utc) + stage table
- clean.py: cast types, drop NA / out-of-range / future rows, IST -> UTC, de-dup
- load.py: stage + MERGE (idempotent upsert), verified: 2nd load inserts 0 rows
- db_connection.py: DB_TYPE switch -> SQLAlchemy engine

## Phase 3: Snowflake + dual-load: code written, NOT tested (trial not started)
- LOAD_TARGETS=postgres,snowflake enables dual-load; sql/snowflake_setup.sql ready
- SQLAlchemy pinned to 2.0.x because snowflake-sqlalchemy breaks on 2.1

## Phase 4: dbt ✅ (on Postgres): 2 seeds, 8 models, 33 tests all pass
- staging: stg_aqi_readings, stg_city_population
- analytics: fct_station_aqi (incremental), fct_city_aqi_hourly, fct_city_aqi_daily, city_latest_aqi,
  city_ranking_24h, city_hour_of_day_profile, aqi_category_distribution
- macros: aqi_category, round_float (adapter.dispatch), generate_schema_name; custom test value_between
- run with: python run_dbt.py build

## Phase 5: Automation: workflow written, needs GitHub Secrets + first run
- .github/workflows/hourly_pipeline.yml (cron 17 * * * *): pytest -> pipeline -> dbt build -> freshness

## Phase 6: Dashboard ✅ (charts tested with fake data; needs real data for a visual check)
- dashboard/app.py: KPIs, map, 24h ranking, trends, hour-of-day heatmap, category distribution,
  cache TTL 10 min + auto-refresh fragment

## Phase 7: Deploy & resume: TODO
- [ ] Push to GitHub, add secrets, run the workflow manually
- [ ] Deploy on Streamlit Cloud, put the link in README
- [ ] Screenshot -> docs/dashboard.png
- [ ] After a few weeks: fill "Key insights" in README
- [ ] Snowflake trial (Phase 3 testing) + 2-minute demo video while it is live

## Data facts
- ~3,800 rows per snapshot (station x pollutant), long format; all fields strings; 'NA' for missing
- Values are CPCB sub-indices (0-500); station AQI = max sub-index (valid if >= 3 pollutants incl. PM)
- last_update = 'DD-MM-YYYY HH:MM:SS' in IST, no tz marker
- API is unreliable: 502 / timeouts for 1+ hour on 2026-10-14 evening

## Study plan (to understand what Claude wrote) - do in this order
1. scraper/scrape.py (HTTP, pagination, retries)  2. clean.py (pandas validation, timezones)
3. load.py + sql/create_raw_tables.sql (MERGE, idempotency)  4. db_connection.py (SQLAlchemy, env vars)
5. dbt: stg_aqi_readings -> fct_station_aqi -> other analytics models -> macros -> tests
6. hourly_pipeline.yml (cron, secrets)  7. dashboard/app.py (caching, charts)

## Concepts learned
- PATH, virtual environments, dependencies, pinning versions
- Environment variables, .env vs .env.example, .gitignore
- git vs GitHub; leaked secret => rotate it (deleting the file is not enough)
- Conventional Commits (feat:, fix:, chore:)
- Managed cloud databases, connection strings, sslmode=require
- API vs scraping, robots.txt, open data licences (attribution), pagination, long vs wide format
- (to study) retries/backoff, idempotency/upsert/MERGE, ELT, dbt models/refs/materializations/tests,
  incremental models, cross-database macros, cron, CI/CD secrets, caching/TTL

## Notes
- User level: comfortable with Python (pandas, functions, requests), SQL (joins, window functions), Git basics, command line.
- Project root is `aqi/` (acts as `aqi-pipeline/` from CLAUDE.md).
- Do NOT start Snowflake trial until ready to test Phase 3.
