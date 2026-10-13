# PROGRESS

## Current position
**Phase 0 complete → next: Phase 1, Step 1 (evaluate AQI data sources)**

## Phase 0: Setup & foundations
- [x] Step 1: Tools checked (Python 3.11.9, Git 2.45.2, VS Code 1.141, git identity set)
- [x] Step 2: Folder structure, virtual env (.venv), requirements.txt
- [x] Step 3: .gitignore, .env.example, .env, git init, first commit pushed to https://github.com/Himanshu552003/aqi-pipeline
- [x] Step 4: Neon Postgres (Singapore, PostgreSQL 18, db neondb). Connection test passed (SSL)

## Next up
Phase 1 Step 1: compare AQI sources (CPCB / data.gov.in API vs scraping), check robots.txt & terms.

## Concepts learned
- PATH
- Virtual environments, dependencies, pinning versions
- Environment variables, .env vs .env.example, .gitignore
- git vs GitHub; leaked secret => rotate it (deleting the file is not enough)
- Conventional Commits (feat:, fix:, chore:)
- Managed cloud databases, connection strings, sslmode=require

## Notes
- User level: comfortable with Python (pandas, functions, requests), SQL (joins, window functions), Git basics, command line.
- Project root is `project 1/` (acts as `aqi-pipeline/` from CLAUDE.md).
- Do NOT start Snowflake trial until Phase 3.
