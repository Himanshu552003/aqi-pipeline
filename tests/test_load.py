# test_load.py - tests for the load configuration and the generated MERGE statement (no database)
import pytest

from scraper import load


def test_load_targets_are_parsed(monkeypatch):
    monkeypatch.setenv("LOAD_TARGETS", " Postgres , snowflake ")
    assert load.get_load_targets() == ["postgres", "snowflake"]


def test_unknown_load_target_is_rejected(monkeypatch):
    monkeypatch.setenv("LOAD_TARGETS", "postgres,mysql")
    with pytest.raises(ValueError):
        load.get_load_targets()


def test_merge_matches_on_the_natural_key():
    sql = load.build_merge_sql()
    assert "t.station = s.station AND t.pollutant_id = s.pollutant_id AND t.reading_time_utc = s.reading_time_utc" in sql
    assert "WHEN NOT MATCHED THEN" in sql
    assert "IS DISTINCT FROM" in sql        # only update rows whose values really changed
