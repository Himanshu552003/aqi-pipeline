# Setup & Run Instructions

Step-by-step guide to run this project from a fresh clone, put it on GitHub with hourly automation,
and deploy the dashboard. Commands are for **Windows PowerShell** (Mac/Linux differences are noted).

| Part | Time | Needed for |
|---|---|---|
| 1–7: Local setup and first run | ~20 min | Everything |
| 8–9: GitHub + hourly automation | ~10 min | Data history building up by itself |
| 10: Streamlit Cloud | ~10 min | Public dashboard link for the resume |
| 11: Snowflake | ~20 min | Optional, only during the 30-day trial |

---

## 1. Prerequisites

Install these tools:
- **Python 3.11** (`python --version`)
- **Git** (`git --version`)
- VS Code (optional)

Create these free accounts:
| Account | Why | Link |
|---|---|---|
| data.gov.in | API key for the CPCB air quality data | https://data.gov.in → Sign up → *My Account* → copy the **API key** |
| Neon | Hosted PostgreSQL (free tier) | https://neon.tech → New project → copy the connection details |
| GitHub | Code + hourly automation (Actions) | https://github.com |
| Streamlit Community Cloud | Hosts the dashboard for free | https://share.streamlit.io (log in with GitHub) |

## 2. Get the code and create a virtual environment

```powershell
git clone https://github.com/Himanshu552003/aqi-pipeline.git
cd aqi-pipeline
python -m venv .venv
.venv\Scripts\Activate.ps1          # Mac/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

> If PowerShell blocks `Activate.ps1`, run once: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

## 3. Configure your secrets in `.env`

```powershell
copy .env.example .env               # Mac/Linux: cp .env.example .env
```

Open `.env` and fill in:
- `DATA_GOV_API_KEY`: your data.gov.in key
- `POSTGRES_HOST`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`: from Neon's connection details. In Neon, the host looks like `ep-xxxx.ap-southeast-1.aws.neon.tech` and the database is usually `neondb`.
- Leave `DB_TYPE=postgres` and `LOAD_TARGETS=postgres`.

`.env` is in `.gitignore` and must **never** be committed. Check with `git status`: `.env` must not appear.

## 4. Check the database connection

```powershell
python -m scraper.db_connection
```
Expected: `Connected to postgres: 2026-...`

## 5. Run the unit tests

```powershell
pytest -q
```
Expected: `17 passed`. These tests use no network and no database.

## 6. Run the pipeline once (Extract + Load)

```powershell
python -m scraper.pipeline --save-csv
```

What happens:
1. It downloads every page of the latest CPCB snapshot (~3,800 rows, ~1–2 min).
2. It cleans and validates the data.
3. It MERGEs the data into `raw.aqi_readings`. The tables are created on the first run.
4. `--save-csv` also keeps a copy in `data/samples/`.

Run it a second time: the log should say `0 rows inserted/updated` (or only the stations that updated). That shows the load is **idempotent**.

> **The data.gov.in API is sometimes slow or down** (502 errors / timeouts). The scraper retries with backoff. If it still fails, try again later. The hourly GitHub job simply catches up on its next run.

## 7. Transform with dbt, then open the dashboard

```powershell
python run_dbt.py build                 # loads seeds, builds all models, runs all data tests
python run_dbt.py docs generate         # builds the documentation site with the lineage graph
python run_dbt.py docs serve            # opens it at http://localhost:8080 (Ctrl+C to stop)
streamlit run dashboard/app.py          # opens the dashboard at http://localhost:8501
```

`run_dbt.py` is a small wrapper. It loads `.env` (dbt can't read it by itself) and runs dbt inside `dbt_project/`. Any dbt command works, for example `python run_dbt.py run --select city_latest_aqi`.

**Optional:** refresh the city population seed from Wikipedia. This runs once, not hourly:
```powershell
python -m scraper.scrape_population
```

> Charts like "hour of day" and "trend" need history. After the first run you only see one hour. Leave the hourly GitHub job running for a few days for meaningful charts.

---

## 8. Push to GitHub

```powershell
git status                              # .env must NOT be listed
git add .
git commit -m "feat: complete AQI pipeline - scraper, dual-load, dbt models, dashboard, CI"
git push
```

## 9. Turn on hourly automation (GitHub Actions)

1. On GitHub, open the repo → **Settings → Secrets and variables → Actions → New repository secret**.
2. Add these secrets with the same values as in your `.env`:

| Secret | Value |
|---|---|
| `DATA_GOV_API_KEY` | your data.gov.in key |
| `POSTGRES_HOST` | Neon host |
| `POSTGRES_PORT` | `5432` |
| `POSTGRES_DB` | e.g. `neondb` |
| `POSTGRES_USER` | Neon user |
| `POSTGRES_PASSWORD` | Neon password |

3. Open the **Actions** tab → *Hourly AQI pipeline* → **Run workflow** to test it now.
4. Every step should turn green: unit tests → extract + load → dbt build → freshness. After that it runs automatically at minute 17 of every hour.

Good to know:
- If a run fails, GitHub emails you. Click the run to see the logs.
- GitHub may delay scheduled runs by a few minutes when it's busy. That's normal.
- **GitHub pauses scheduled workflows after 60 days with no commits.** Push any small change (or click "Enable workflow") to restart it.

## 10. Deploy the dashboard (Streamlit Community Cloud)

1. Go to https://share.streamlit.io → **Create app** → *Deploy a public app from GitHub*.
2. Repository: `Himanshu552003/aqi-pipeline`, branch `main`, main file path: `dashboard/app.py`.
3. **Advanced settings:**
   - Python version **3.11**.
   - In **Secrets**, paste:
     ```toml
     DB_TYPE = "postgres"
     POSTGRES_HOST = "ep-xxxx.ap-southeast-1.aws.neon.tech"
     POSTGRES_PORT = "5432"
     POSTGRES_DB = "neondb"
     POSTGRES_USER = "..."
     POSTGRES_PASSWORD = "..."
     POSTGRES_SSLMODE = "require"
     ```
4. Click **Deploy**. Streamlit Cloud installs `dashboard/requirements.txt` (a light list without dbt).
5. Copy the public URL into `README.md` (*Live dashboard* line) and onto your resume.

> **Better practice:** in Neon, create a second **read-only** role for the dashboard and use it here instead of the main user.

---

## 11. (Optional) Snowflake dual-load, during the 30-day trial only

1. Start the trial at https://signup.snowflake.com. Choose any cloud and a region near India, e.g. AWS Mumbai.
2. In Snowsight, open a worksheet. Paste [sql/snowflake_setup.sql](sql/snowflake_setup.sql), change the password, and **Run All**. It creates:
   - an X-Small warehouse that auto-suspends after 60 seconds
   - the `AQI_DB` database with RAW / STAGING / ANALYTICS schemas
   - a role and a service user
   - a 5-credit monthly safety cap
3. Add to `.env`:
   ```
   SNOWFLAKE_ACCOUNT=<orgname-accountname>   (Snowsight → your name → Account → "Account identifier")
   SNOWFLAKE_USER=AQI_USER
   SNOWFLAKE_PASSWORD=<the password you set>
   SNOWFLAKE_ROLE=AQI_ROLE
   SNOWFLAKE_WAREHOUSE=AQI_WH
   SNOWFLAKE_DATABASE=AQI_DB
   LOAD_TARGETS=postgres,snowflake
   ```
4. Test:
   ```powershell
   $env:DB_TYPE="snowflake"; python -m scraper.db_connection; Remove-Item Env:DB_TYPE
   python -m scraper.pipeline                       # now writes to BOTH databases
   python run_dbt.py build --target snowflake
   ```
5. For GitHub Actions:
   - Add the same 6 `SNOWFLAKE_*` values as secrets.
   - Under **Settings → Secrets and variables → Actions → Variables**, add the variable `LOAD_TARGETS` = `postgres,snowflake`.
6. To show the dashboard from Snowflake:
   - Set `DB_TYPE = "snowflake"` plus the `SNOWFLAKE_*` values in the Streamlit secrets.
   - Uncomment `snowflake-sqlalchemy` in `dashboard/requirements.txt`.
7. **Before the trial ends:**
   - Set `LOAD_TARGETS` back to `postgres` (the GitHub variable and `.env`).
   - Set `DB_TYPE = "postgres"` in the Streamlit secrets.

   Postgres has had the full history all along, so no migration is needed.

> The Snowflake path is written but was not tested against a live account when this project was built. If Snowflake rejects password login for your user (it is phasing out passwords), switch the user to key-pair authentication.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `DATA_GOV_API_KEY is missing` | `.env` not filled in, or you are not in the project root folder |
| `Giving up on offset ... after 4 attempts` | data.gov.in is down or slow. Wait and retry. |
| `API returned 403` | API key is wrong or not activated yet |
| `Environment variable POSTGRES_... is missing` | Fill it in `.env` (locally) or GitHub Secrets (CI) |
| First query slow / connection timeout | Neon suspends idle databases. The first connection wakes it (a few seconds). Retry. |
| dbt: `Could not find profile` | Run dbt through `python run_dbt.py ...`, not plain `dbt`, from the project root |
| Dashboard says "No data yet" | Run steps 6 and 7 first |
| Workflow stopped running | It was paused after 60 days without commits. See step 9. |
