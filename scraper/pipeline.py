# pipeline.py - run the whole Extract + Load step: scrape -> clean -> load (dbt does the Transform)
#
#   python -m scraper.pipeline              # normal run
#   python -m scraper.pipeline --save-csv   # also keep a CSV copy in data/samples/
import argparse
import logging
import time

from scraper.clean import clean
from scraper.load import load
from scraper.scrape import fetch_all, save_sample, to_dataframe

logger = logging.getLogger("pipeline")


def run(save_csv: bool = False) -> None:
    started = time.monotonic()

    raw_df = to_dataframe(fetch_all())
    if save_csv:
        save_sample(raw_df)

    clean_df = clean(raw_df)
    results = load(clean_df)

    logger.info("Pipeline finished in %.0f s: %s", time.monotonic() - started, results)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(name)s | %(levelname)s | %(message)s")
    parser = argparse.ArgumentParser(description="Fetch, clean and load CPCB AQI data")
    parser.add_argument("--save-csv", action="store_true", help="also save the raw snapshot as CSV")
    run(save_csv=parser.parse_args().save_csv)
