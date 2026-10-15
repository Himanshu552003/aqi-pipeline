# test_scrape.py - tests for pagination and retry logic, with the HTTP calls faked (no network)
import pytest
import requests

from scraper import scrape


class FakeResponse:
    def __init__(self, status_code: int, payload: dict | None = None):
        self.status_code = status_code
        self._payload = payload or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} error")

    def json(self):
        return self._payload


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    """Skip real waiting so the tests run instantly."""
    monkeypatch.setattr(scrape.time, "sleep", lambda seconds: None)
    monkeypatch.setenv("DATA_GOV_API_KEY", "test-key")


def test_fetch_all_follows_pagination(monkeypatch):
    pages = {0: [{"id": 1}, {"id": 2}], 2: [{"id": 3}]}
    offsets_called = []

    def fake_get(url, params, headers, timeout):
        offsets_called.append(params["offset"])
        return FakeResponse(200, {"total": "3", "records": pages[params["offset"]]})

    monkeypatch.setattr(scrape.requests, "get", fake_get)
    records = scrape.fetch_all()

    assert [r["id"] for r in records] == [1, 2, 3]
    assert offsets_called == [0, 2]        # offset moves by the rows actually received


def test_exact_duplicates_are_removed():
    records = [{"id": 1}, {"id": 2}, {"id": 1}]
    assert scrape.drop_exact_duplicates(records) == [{"id": 1}, {"id": 2}]


def test_inconsistent_snapshot_is_fetched_again(monkeypatch):
    # 1st snapshot: the source refreshed mid-fetch, so page 2 repeats a row and row 3 is missed.
    # 2nd snapshot: clean.
    snapshots = iter([
        {0: [{"id": 1}, {"id": 2}], 2: [{"id": 2}]},
        {0: [{"id": 1}, {"id": 2}], 2: [{"id": 3}]},
    ])
    current = {}

    def fake_get(url, params, headers, timeout):
        if params["offset"] == 0:
            current.update(next(snapshots))
        return FakeResponse(200, {"total": "3", "records": current[params["offset"]]})

    monkeypatch.setattr(scrape.requests, "get", fake_get)
    records = scrape.fetch_all()
    assert [r["id"] for r in records] == [1, 2, 3]


def test_fetch_page_retries_server_errors(monkeypatch):
    responses = iter([FakeResponse(502), FakeResponse(503), FakeResponse(200, {"records": []})])
    monkeypatch.setattr(scrape.requests, "get", lambda *a, **k: next(responses))
    assert scrape.fetch_page(0, "key") == {"records": []}


def test_fetch_page_does_not_retry_client_errors(monkeypatch):
    calls = []

    def fake_get(*args, **kwargs):
        calls.append(1)
        return FakeResponse(403)

    monkeypatch.setattr(scrape.requests, "get", fake_get)
    with pytest.raises(RuntimeError, match="403"):
        scrape.fetch_page(0, "key")
    assert len(calls) == 1


def test_fetch_page_gives_up_after_max_retries(monkeypatch):
    monkeypatch.setattr(scrape.requests, "get", lambda *a, **k: FakeResponse(502))
    with pytest.raises(RuntimeError, match="Giving up"):
        scrape.fetch_page(0, "key")
