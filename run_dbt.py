# run_dbt.py - run any dbt command with the settings from .env loaded (dbt itself does not read .env)
#
#   python run_dbt.py build                      # seeds + models + tests on the DB_TYPE target
#   python run_dbt.py build --target snowflake   # same, on Snowflake
#   python run_dbt.py docs generate
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent
DBT_PROJECT_DIR = PROJECT_ROOT / "dbt_project"


def main() -> int:
    load_dotenv(PROJECT_ROOT / ".env")   # in GitHub Actions there is no .env: secrets are already env vars
    os.chdir(DBT_PROJECT_DIR)            # dbt finds dbt_project.yml and profiles.yml here

    from dbt.cli.main import dbtRunner   # imported after load_dotenv so dbt sees the variables

    result = dbtRunner().invoke(sys.argv[1:])
    return 0 if result.success else 1


if __name__ == "__main__":
    sys.exit(main())
