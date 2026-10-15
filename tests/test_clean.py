# test_clean.py - unit tests for scraper/clean.py (no network, no database). Run: pytest -q
import pandas as pd
import pytest

from scraper.clean import OUTPUT_COLUMNS, clean, parse_ist_to_utc


def make_row(**overrides) -> dict:
    """One valid API record (all strings, like the real API). Override any field per test."""
    row = {
        "country": "India", "state": "Delhi", "city": "Delhi", "station": "Anand Vihar, Delhi - DPCC",
        "last_update": "14-10-2026 22:00:00", "latitude": "28.6469", "longitude": "77.3164",
        "pollutant_id": "PM2.5", "min_value": "120", "max_value": "310", "avg_value": "245",
        "fetched_at_utc": "2026-10-14T17:30:00+00:00",
    }
    row.update(overrides)
    return row


def run_clean(*rows: dict) -> pd.DataFrame:
    return clean(pd.DataFrame(list(rows)))


def test_ist_is_converted_to_utc():
    utc, ist = parse_ist_to_utc(pd.Series(["14-10-2026 22:00:00"]))
    assert ist[0] == pd.Timestamp("2026-10-14 22:00:00")
    assert utc[0] == pd.Timestamp("2026-10-14 16:30:00")     # IST = UTC + 5:30


def test_output_has_expected_columns_and_types():
    df = run_clean(make_row())
    assert list(df.columns) == OUTPUT_COLUMNS
    assert df.loc[0, "avg_value"] == 245.0
    assert pd.api.types.is_datetime64_any_dtype(df["reading_time_utc"])


def test_na_values_are_dropped():
    df = run_clean(make_row(), make_row(pollutant_id="NO2", avg_value="NA"))
    assert len(df) == 1


def test_out_of_range_values_are_dropped():
    df = run_clean(make_row(avg_value="-5"), make_row(pollutant_id="NO2", avg_value="999"))
    assert df.empty


def test_bad_timestamp_is_dropped():
    df = run_clean(make_row(last_update="not a date"))
    assert df.empty


def test_future_readings_are_dropped():
    df = run_clean(make_row(last_update="15-10-2026 22:00:00"))   # a day after fetched_at
    assert df.empty


def test_duplicates_on_natural_key_are_removed():
    df = run_clean(make_row(avg_value="200"), make_row(avg_value="245"))
    assert len(df) == 1
    assert df.loc[0, "avg_value"] == 245.0      # keep the last one


def test_text_is_trimmed_and_pollutant_upper_cased():
    df = run_clean(make_row(city="  Delhi ", pollutant_id=" ozone "))
    assert df.loc[0, "city"] == "Delhi"
    assert df.loc[0, "pollutant_id"] == "OZONE"


@pytest.mark.parametrize("value", ["0", "500"])
def test_range_boundaries_are_kept(value):
    assert len(run_clean(make_row(avg_value=value))) == 1
