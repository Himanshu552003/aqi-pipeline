# scrape.py - fetch raw AQI data from the data.gov.in (CPCB) API and return/save it
#
# Source: "Real time Air Quality Index from various locations" (CPCB), published on data.gov.in
# under the Government Open Data License - India (GODL). Attribution is required (see README).
import logging
import os
import time
from datetime import datetime, timezone

import pandas as pd
import requests
from dotenv import load_dotenv

BASE_URL = "https://api.data.gov.in/resource/3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69"
PAGE_SIZE = 100            # bigger pages time out on this API
MAX_RETRIES = 4
REQUEST_TIMEOUT = 90       # seconds; the API is slow and sometimes answers 502 after ~60 s
BACKOFF_SECONDS = 5        # wait 5 s, 10 s, 20 s between retries
PAUSE_BETWEEN_PAGES = 1    # polite rate limiting
MAX_SNAPSHOT_ATTEMPTS = 3  # re-fetch the whole snapshot if the source changed while we were paging
SNAPSHOT_RETRY_WAIT = 120  # seconds to let the source finish its hourly refresh
SAMPLE_DIR = os.path.join("data", "samples")
HEADERS = {
    "User-Agent": "aqi-pipeline/0.1 (learning project; https://github.com/Himanshu552003/aqi-pipeline)"
}

logger = logging.getLogger(__name__)


def get_api_key() -> str:
    """Read the API key from the environment (.env locally, GitHub Secrets in CI)."""
    load_dotenv()
    api_key = os.getenv("DATA_GOV_API_KEY")
    if not api_key:
        raise RuntimeError("DATA_GOV_API_KEY is missing. Add it to your .env file.")
    return api_key


def fetch_page(offset: int, api_key: str) -> dict:
    """Fetch ONE page from the API and return the parsed JSON. Retry on failure."""
    params = {"api-key": api_key, "format": "json", "offset": offset, "limit": PAGE_SIZE}

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(BASE_URL, params=params, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            status = response.status_code
            # 4xx = our mistake (bad key, bad URL): retrying will not help. 429 = "slow down": retry.
            if 400 <= status < 500 and status != 429:
                raise RuntimeError(f"API returned {status} at offset {offset} (check API key / URL). Not retrying.")
            response.raise_for_status()
            return response.json()
        except requests.RequestException as err:
            # Log only the error TYPE: the full message contains the URL, which contains the API key
            logger.warning("Attempt %d/%d failed at offset %d: %s",
                           attempt, MAX_RETRIES, offset, type(err).__name__)
            if attempt < MAX_RETRIES:
                time.sleep(BACKOFF_SECONDS * 2 ** (attempt - 1))

    raise RuntimeError(f"Giving up on offset {offset} after {MAX_RETRIES} attempts") from None


def drop_exact_duplicates(records: list[dict]) -> list[dict]:
    """Remove records that are identical in every field (keeps the first one, keeps order)."""
    seen, unique = set(), []
    for record in records:
        fingerprint = tuple(sorted(record.items()))
        if fingerprint not in seen:
            seen.add(fingerprint)
            unique.append(record)
    return unique


def fetch_pages(api_key: str) -> tuple[list[dict], bool]:
    """Page through the API once. Returns (unique records, was the snapshot consistent?).

    The source refreshes its data every hour. If that happens while we are paging, rows shift
    between pages: some come back twice and others are skipped. We detect it because the
    reported `total` changes, or the pages contain repeated rows.
    """
    records = []
    offset = 0
    first_total = last_total = None

    while True:
        data = fetch_page(offset, api_key)
        page = data.get("records", [])
        last_total = int(data.get("total", 0))

        if first_total is None:
            first_total = last_total
            logger.info("API reports %d records in total", first_total)

        if not page:
            break

        records.extend(page)
        offset += len(page)
        logger.info("Fetched %d/%d records", len(records), first_total)

        if len(records) >= first_total:
            break
        time.sleep(PAUSE_BETWEEN_PAGES)

    unique = drop_exact_duplicates(records)
    consistent = first_total == last_total == len(unique)
    if not consistent:
        logger.warning("Inconsistent snapshot: total changed %s -> %s, %d unique of %d fetched rows "
                       "(the source was probably updating during the fetch)",
                       first_total, last_total, len(unique), len(records))
    return unique, consistent


def fetch_all() -> list[dict]:
    """Fetch one complete, consistent snapshot. Re-fetch if the source changed while we were paging."""
    api_key = get_api_key()
    best: list[dict] = []

    for attempt in range(1, MAX_SNAPSHOT_ATTEMPTS + 1):
        records, consistent = fetch_pages(api_key)
        if len(records) > len(best):
            best = records
        if consistent:
            return records
        if attempt < MAX_SNAPSHOT_ATTEMPTS:
            logger.info("Waiting %d s before re-fetching the snapshot (%d/%d)",
                        SNAPSHOT_RETRY_WAIT, attempt + 1, MAX_SNAPSHOT_ATTEMPTS)
            time.sleep(SNAPSHOT_RETRY_WAIT)

    logger.warning("No consistent snapshot after %d attempts, using the most complete one (%d rows)",
                   MAX_SNAPSHOT_ATTEMPTS, len(best))
    return best


def to_dataframe(records: list[dict], fetched_at: datetime | None = None) -> pd.DataFrame:
    """Turn API records into a DataFrame and stamp when WE fetched them (audit column)."""
    if not records:
        raise RuntimeError("No records fetched, nothing to process")
    fetched_at = fetched_at or datetime.now(timezone.utc)
    df = pd.DataFrame(records)
    df["fetched_at_utc"] = fetched_at.isoformat(timespec="seconds")
    return df


def save_sample(df: pd.DataFrame) -> str:
    """Save a snapshot to data/samples/aqi_sample_<UTC timestamp>.csv and return the path."""
    os.makedirs(SAMPLE_DIR, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%MZ")
    path = os.path.join(SAMPLE_DIR, f"aqi_sample_{stamp}.csv")
    df.to_csv(path, index=False)
    logger.info("Saved %d rows x %d columns to %s", len(df), len(df.columns), path)
    return path


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    save_sample(to_dataframe(fetch_all()))
