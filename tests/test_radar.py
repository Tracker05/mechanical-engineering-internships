"""Drop Radar v3: engine-observed + verified windows, no third-party list."""

from datetime import date

import pytest

from intern_engine import radar

TODAY = date(2026, 7, 3)


@pytest.fixture(autouse=True)
def isolate(monkeypatch):
    """Every test drives the caches explicitly — never touch the real data files."""
    monkeypatch.setattr(radar, "_observed_cache", {"companies": {}})
    monkeypatch.setattr(radar, "_known_cache", {})
    yield
    monkeypatch.setattr(radar, "_observed_cache", None)
    monkeypatch.setattr(radar, "_known_cache", None)


def _observed(monkeypatch, companies):
    monkeypatch.setattr(radar, "_observed_cache", {"companies": companies})


def _known(monkeypatch, entries):
    from intern_engine import h1b
    monkeypatch.setattr(radar, "_known_cache",
                        {h1b.normalize(e["name"]): e for e in entries})


STORE = {
    "a": {"company": "Stripe, Inc.", "season": "Summer 2027", "is_open": True,
          "url": "https://stripe/apply"},
    "b": {"company": "NVIDIA", "season": "Fall 2026", "is_open": True,
          "url": "https://nv/fall"},          # wrong cycle: must NOT count as posted
}


def test_verified_observed_prev_cycle_projects_forward(monkeypatch):
    _observed(monkeypatch, {
        "nvidia": {"name": "NVIDIA", "cycles": {"Summer 2026": {"first_posted": "2025-08-24", "count": 5}}},
    })
    row = next(r for r in radar.rows(STORE, "Summer 2027", today=TODAY) if r["company"] == "NVIDIA")
    assert row["source"] == "engine"
    assert row["confidence"] == "verified"
    assert row["expected"] == "2026-08-24"
    assert row["status"] == "waiting"          # only Fall 2026 NVIDIA is open


def test_live_drop_date_is_shown_and_verified(monkeypatch):
    _observed(monkeypatch, {
        "stripe": {"name": "Stripe", "cycles": {"Summer 2027": {"first_posted": "2026-06-30", "count": 1}}},
    })
    row = next(r for r in radar.rows(STORE, "Summer 2027", today=TODAY) if r["company"] == "Stripe")
    assert row["status"] == "open"
    assert row["source"] == "engine"
    assert row["posted_on"] == "2026-06-30"
    assert radar.pretty_expected(row) == "dropped Jun 30"


def test_known_month_window_projects_to_prior_calendar_year(monkeypatch):
    _known(monkeypatch, [{"name": "Meta", "opens": "08", "precision": "month"}])
    row = next(r for r in radar.rows(STORE, "Summer 2027", today=TODAY) if r["company"] == "Meta")
    assert row["source"] == "known"
    assert row["confidence"] == "window"
    assert row["expected"] == "2026-08-01"      # Summer 2027 opens Aug 2026
    assert radar.pretty_last(row) == "~Aug"
    assert radar.pretty_expected(row).startswith("~Aug")


def test_rolling_company_has_no_date(monkeypatch):
    _known(monkeypatch, [{"name": "Microsoft", "opens": None, "precision": "rolling"}])
    row = next(r for r in radar.rows(STORE, "Summer 2027", today=TODAY) if r["company"] == "Microsoft")
    assert row["rolling"] is True
    assert row["expected"] == ""
    assert radar.pretty_last(row) == "rolling"
    assert radar.pretty_expected(row) == "year-round"


def test_observed_beats_known_window(monkeypatch):
    _observed(monkeypatch, {
        "meta": {"name": "Meta", "cycles": {"Summer 2026": {"first_posted": "2025-09-15", "count": 3}}},
    })
    _known(monkeypatch, [{"name": "Meta", "opens": "08", "precision": "month"}])
    row = next(r for r in radar.rows(STORE, "Summer 2027", today=TODAY) if r["company"] == "Meta")
    assert row["source"] == "engine"            # our own data wins over the seed
    assert row["expected"] == "2026-09-15"
    assert row["provenance"] == {
        "type": "engine-projection", "cycle": "Summer 2026",
        "observed_on": "2025-09-15",
    }


def test_live_only_company_with_no_date(monkeypatch):
    store = {"x": {"company": "Anduril", "season": "Summer 2027", "is_open": True, "url": "https://a"}}
    row = next(r for r in radar.rows(store, "Summer 2027", today=TODAY) if r["company"] == "Anduril")
    assert row["status"] == "open"
    assert radar.pretty_expected(row) == "live now"


def test_inferred_open_role_does_not_confirm_the_radar(monkeypatch):
    # A company whose only open role has a GUESSED cycle must not earn a radar
    # row (no false "🎯 verified open now") — it's in the list, not the forecast.
    store = {"x": {"company": "GuessCo", "season": "Summer 2027", "season_inferred": True,
                   "is_open": True, "url": "https://g"}}
    assert radar.rows(store, "Summer 2027", today=TODAY) == []


def test_stated_open_role_still_confirms_the_radar(monkeypatch):
    store = {"x": {"company": "StatedCo", "season": "Summer 2027", "season_inferred": False,
                   "is_open": True, "url": "https://s"}}
    row = next(r for r in radar.rows(store, "Summer 2027", today=TODAY) if r["company"] == "StatedCo")
    assert row["status"] == "open"


def test_waiting_sorts_before_dropped(monkeypatch):
    # Forecast (what's coming) must rank above a role that already closed.
    _observed(monkeypatch, {
        "gonecorp": {"name": "GoneCorp",
                     "cycles": {"Summer 2027": {"first_posted": "2026-05-01", "count": 1}}},
    })
    _known(monkeypatch, [{"name": "Meta", "opens": "08", "precision": "month"}])
    # GoneCorp posted this cycle but is not open now -> "dropped"; Meta -> "waiting".
    companies = [r["company"] for r in radar.rows({}, "Summer 2027", today=TODAY)]
    assert companies.index("Meta") < companies.index("GoneCorp")


def test_posted_rows_sort_before_waiting(monkeypatch):
    _observed(monkeypatch, {
        "stripe": {"name": "Stripe", "cycles": {"Summer 2027": {"first_posted": "2026-06-30", "count": 1}}},
    })
    _known(monkeypatch, [{"name": "Meta", "opens": "08", "precision": "month"}])
    companies = [r["company"] for r in radar.rows(STORE, "Summer 2027", today=TODAY)]
    assert companies.index("Stripe") < companies.index("Meta")


def test_dated_sorts_before_rolling(monkeypatch):
    _known(monkeypatch, [
        {"name": "Meta", "opens": "08", "precision": "month"},
        {"name": "Microsoft", "opens": None, "precision": "rolling"},
    ])
    companies = [r["company"] for r in radar.rows({}, "Summer 2027", today=TODAY)]
    assert companies.index("Meta") < companies.index("Microsoft")


def test_prev_cycle():
    assert radar.prev_cycle("Summer 2027") == "Summer 2026"
    assert radar.prev_cycle("Fall 2026") == "Fall 2025"


def test_window_expected_summer_opens_prior_year():
    assert radar._window_expected("Summer 2027", "08") == date(2026, 8, 1)
    assert radar._window_expected("Fall 2026", "08") == date(2026, 8, 1)


def test_plus_one_year_handles_leap_day():
    assert radar._plus_one_year("2024-02-29") == date(2025, 2, 28)


def test_pretty_expected_countdown(monkeypatch):
    _observed(monkeypatch, {
        "nvidia": {"name": "NVIDIA", "cycles": {"Summer 2026": {"first_posted": "2025-08-24", "count": 5}}},
    })
    row = next(r for r in radar.rows(STORE, "Summer 2027", today=TODAY) if r["company"] == "NVIDIA")
    assert radar.pretty_expected(row) == "~Aug 24"          # 52d out: no countdown
    assert "in ~20d" in radar.pretty_expected(dict(row, days_until=20))
    assert "any day now" in radar.pretty_expected(dict(row, days_until=-3))


def test_empty_everything_returns_no_rows():
    assert radar.rows({}, "Summer 2027", today=TODAY) == []


def test_explicit_alias_merges_jpmorgan_spellings(monkeypatch):
    _observed(monkeypatch, {
        "jpmorganchase": {"name": "JPMorganChase", "cycles": {
            "Summer 2027": {"first_posted": "2026-08-03", "count": 1},
        }},
    })
    _known(monkeypatch, [
        {"name": "JPMorgan Chase", "opens": "03", "precision": "month"},
    ])
    rows = radar.rows({}, "Summer 2027", today=TODAY)
    matches = [r for r in rows if "jpmorgan" in radar.company_key(r["company"])]
    assert len(matches) == 1
    assert matches[0]["company"] == "JPMorgan Chase"
    assert matches[0]["status"] == "dropped"


def test_expired_waiting_window_is_not_actionable():
    assert radar.is_actionable({"status": "waiting", "days_until": -46}) is False
    assert radar.is_actionable({"status": "waiting", "days_until": -45}) is True


class TestElapsedWindow:
    """A window in the past must not read as an imminent drop."""

    def test_long_past_window_says_so(self):
        row = {"status": "waiting", "expected": "2026-02-01", "precision": "month",
               "days_until": -182, "rolling": False}
        assert radar.pretty_expected(row) == "~Feb · window passed, not seen"

    def test_just_inside_the_month_is_still_any_day_now(self):
        # Month precision means the whole month, so a couple of weeks past the
        # 1st is still "about now" — only a real gap changes the wording.
        row = {"status": "waiting", "expected": "2026-08-01", "precision": "month",
               "days_until": -20, "rolling": False}
        assert radar.pretty_expected(row) == "~Aug · any day now"

    def test_upcoming_window_counts_down(self):
        row = {"status": "waiting", "expected": "2026-09-01", "precision": "month",
               "days_until": 30, "rolling": False}
        assert radar.pretty_expected(row) == "~Sep · in ~30d"
