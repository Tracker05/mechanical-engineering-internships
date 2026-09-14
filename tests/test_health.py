"""Circuit-breaker behavior: quarantine after repeat failures, self-heal after."""

from datetime import UTC, datetime, timedelta

import pytest

from intern_engine import health, paths

COMPANY = {"ats": "greenhouse", "slug": "deadco", "name": "DeadCo"}
NOW = datetime(2026, 7, 1, 12, 0, tzinfo=UTC)


def _fail_n(data: dict, n: int, now=NOW):
    for _ in range(n):
        health.record(data, COMPANY, "HTTPStatusError: 404", now=now)


class TestBreaker:
    def test_under_threshold_still_fetched(self):
        data: dict = {}
        _fail_n(data, 2)
        active, benched = health.partition([COMPANY], data, now=NOW)
        assert active == [COMPANY] and benched == []

    def test_quarantined_after_threshold(self):
        data: dict = {}
        _fail_n(data, 3)
        active, benched = health.partition([COMPANY], data, now=NOW + timedelta(hours=1))
        assert active == [] and benched == [COMPANY]

    def test_window_expires_and_retries(self):
        data: dict = {}
        _fail_n(data, 3)
        # 3 failures -> 6h window; at 7h the board gets another chance.
        active, _ = health.partition([COMPANY], data, now=NOW + timedelta(hours=7))
        assert active == [COMPANY]

    def test_backoff_grows(self):
        data: dict = {}
        _fail_n(data, 5)
        # 5 failures -> 24h window: still benched at 20h, retried at 25h.
        _, benched = health.partition([COMPANY], data, now=NOW + timedelta(hours=20))
        assert benched == [COMPANY]
        active, _ = health.partition([COMPANY], data, now=NOW + timedelta(hours=25))
        assert active == [COMPANY]

    def test_success_resets_and_shrinks_file(self):
        data: dict = {}
        _fail_n(data, 4)
        health.record(data, COMPANY, None, now=NOW)
        assert data == {}  # healthy companies carry no entry at all

    def test_healthy_company_untracked(self):
        data: dict = {}
        health.record(data, COMPANY, None, now=NOW)
        assert data == {}

    def test_workday_sites_do_not_share_a_circuit_breaker(self):
        campus = {
            "ats": "workday", "slug": "acme", "site": "Campus", "name": "Acme",
        }
        professional = {**campus, "site": "Professional"}
        data = {}
        health.record(data, campus, "timeout", now=NOW)
        assert health.key(campus) != health.key(professional)
        assert health.key(professional) not in data


def test_corrupt_health_state_is_fatal(tmp_path, monkeypatch):
    path = tmp_path / "health.json"
    path.write_text('{"greenhouse:acme": {"consecutive_failures": "three"}}',
                    encoding="utf-8")
    monkeypatch.setattr(paths, "HEALTH_PATH", str(path))
    with pytest.raises(health.HealthStateCorrupt):
        health.load()


def test_legacy_workday_health_is_copied_to_each_site():
    companies = [
        {"ats": "workday", "slug": "acme", "site": site, "name": "Acme"}
        for site in ("Campus", "Professional")
    ]
    entry = {
        "consecutive_failures": 3,
        "last_attempt_at": "2026-08-06T00:00:00Z",
        "last_error": "timeout",
    }
    data = {"workday:acme": entry}
    assert health.migrate_legacy_keys(companies, data) == 2
    assert data["workday:acme:campus"] == entry
    assert data["workday:acme:professional"] == entry
