"""The engine's own posted-date memory: earliest-wins, monotonic, per cycle."""

import pytest

from intern_engine import observe, paths


def test_records_earliest_real_date_per_company_and_cycle():
    store = {
        "1": {"company": "NVIDIA", "season": "Summer 2027", "posted_at": "2026-09-10T00:00:00Z"},
        "2": {"company": "NVIDIA", "season": "Summer 2027", "posted_at": "2026-09-03T12:00:00Z"},
        "3": {"company": "NVIDIA", "season": "Fall 2026", "posted_at": "2026-03-01T00:00:00Z"},
    }
    out = observe.update_from_store(store, {"companies": {}})
    cycles = out["companies"]["nvidia"]["cycles"]
    assert cycles["Summer 2027"]["first_posted"] == "2026-09-03"   # earliest wins
    assert cycles["Summer 2027"]["count"] == 2
    assert cycles["Fall 2026"]["first_posted"] == "2026-03-01"


def test_count_is_distinct_roles_not_runs():
    # The radar bug: count was bumped once per role per RUN, so an hourly
    # schedule inflated it forever (Amazon showed 1,197 "roles" for one cycle).
    # Re-running over an unchanged store must not move the number.
    store = {
        "gh:nvidia:1": {"company": "NVIDIA", "season": "Summer 2027",
                        "posted_at": "2026-09-03T00:00:00Z"},
        "gh:nvidia:2": {"company": "NVIDIA", "season": "Summer 2027",
                        "posted_at": "2026-09-10T00:00:00Z"},
    }
    out = {"companies": {}}
    for _ in range(10):
        out = observe.update_from_store(store, out)
    cycle = out["companies"]["nvidia"]["cycles"]["Summer 2027"]
    assert cycle["count"] == 2
    assert cycle["role_ids"] == ["gh:nvidia:1", "gh:nvidia:2"]  # auditable


def test_alias_migration_does_not_double_count_one_requisition():
    observed = {"companies": {"acme": {"name": "Acme", "cycles": {
        "Summer 2027": {
            "first_posted": "2026-06-01", "count": 1,
            "role_ids": ["greenhouse:old-board:1"],
        },
    }}}}
    store = {"greenhouse:new-board:2": {
        "company": "Acme", "season": "Summer 2027",
        "posted_at": "2026-06-02T00:00:00Z",
        "aliases": ["greenhouse:old-board:1"],
    }}

    out = observe.update_from_store(store, observed, ["Summer 2027"])

    cycle = out["companies"]["acme"]["cycles"]["Summer 2027"]
    assert cycle["first_posted"] == "2026-06-01"
    assert cycle["role_ids"] == ["greenhouse:new-board:2"]
    assert cycle["count"] == 1


def test_legacy_inflated_count_is_replaced_by_real_ids():
    prior = {"companies": {"amazon": {"name": "Amazon", "cycles": {
        "Fall 2026": {"first_posted": "2026-03-25", "count": 1197},
    }}}}
    store = {"amazon:amazon:1": {"company": "Amazon", "season": "Fall 2026",
                                 "posted_at": "2026-03-25T00:00:00Z"}}
    out = observe.update_from_store(store, prior)
    cycle = out["companies"]["amazon"]["cycles"]["Fall 2026"]
    assert cycle["count"] == 1
    assert cycle["first_posted"] == "2026-03-25"  # the real date survives


def test_multi_cycle_roles_contribute_to_every_stated_cycle():
    # Deepgram states Fall 2026 AND Summer 2027. Reading only the primary
    # season lost its Fall history — next cycle's Fall forecast had no idea
    # the company had ever dropped in Fall.
    store = {"ashby:deepgram:1": {
        "company": "Deepgram", "season": "Summer 2027",
        "seasons": ["Summer 2027", "Fall 2026"],
        "posted_at": "2026-07-17T00:00:00Z",
    }}
    out = observe.update_from_store(store, {"companies": {}},
                                    ["Summer 2027", "Fall 2026"])
    cycles = out["companies"]["deepgram"]["cycles"]
    assert set(cycles) == {"Summer 2027", "Fall 2026"}
    assert cycles["Fall 2026"]["first_posted"] == "2026-07-17"


def test_ignores_records_without_posted_date_or_cycle():
    store = {
        "1": {"company": "Foo", "season": "Summer 2027"},                # no posted_at
        "2": {"company": "Bar", "posted_at": "2026-01-01T00:00:00Z"},    # no season
    }
    out = observe.update_from_store(store, {"companies": {}})
    assert out["companies"] == {}


def test_is_monotonic_across_runs():
    prior = {"companies": {
        "stripe": {"name": "Stripe", "cycles": {"Summer 2027": {"first_posted": "2026-06-30", "count": 1}}},
    }}
    # A later run where the role has closed/purged (empty store) must not erase it.
    out = observe.update_from_store({}, prior)
    assert out["companies"]["stripe"]["cycles"]["Summer 2027"]["first_posted"] == "2026-06-30"
    assert out["companies"]["stripe"]["cycles"]["Summer 2027"]["role_ids"] == []
    assert out["companies"]["stripe"]["cycles"]["Summer 2027"]["count"] == 0


def test_normalizes_company_variants_together():
    store = {
        "1": {"company": "Stripe, Inc.", "season": "Summer 2027", "posted_at": "2026-06-30T00:00:00Z"},
        "2": {"company": "Stripe", "season": "Summer 2027", "posted_at": "2026-06-25T00:00:00Z"},
    }
    out = observe.update_from_store(store, {"companies": {}})
    keys = list(out["companies"])
    assert len(keys) == 1
    assert out["companies"][keys[0]]["cycles"]["Summer 2027"]["first_posted"] == "2026-06-25"


CYCLES = ["Summer 2027", "Fall 2026"]


def test_inferred_cycle_is_not_recorded():
    # A date-inferred (guessed) cycle must never become a radar "observation" —
    # it would surface as a 🎯 verified drop date and project fiction forward.
    store = {
        "1": {"company": "GuessCo", "season": "Summer 2027", "season_inferred": True,
              "posted_at": "2026-06-01T00:00:00Z"},
        "2": {"company": "RealCo", "season": "Summer 2027", "season_inferred": False,
              "posted_at": "2026-06-02T00:00:00Z"},
    }
    out = observe.update_from_store(store, {"companies": {}}, CYCLES)
    assert "guessco" not in out["companies"]
    assert out["companies"]["realco"]["cycles"]["Summer 2027"]["first_posted"] == "2026-06-02"


def test_off_tracked_cycle_is_not_recorded():
    # An off-cycle tombstone ("Summer 2026") is real but was never swept in full;
    # recording it would let the radar invent a cadence via prev-cycle projection.
    store = {
        "1": {"company": "OneOff", "season": "Summer 2026", "season_inferred": False,
              "posted_at": "2026-06-18T00:00:00Z"},
        "2": {"company": "Tracked", "season": "Fall 2026", "season_inferred": False,
              "posted_at": "2026-06-18T00:00:00Z"},
    }
    out = observe.update_from_store(store, {"companies": {}}, CYCLES)
    assert "oneoff" not in out["companies"]
    assert "tracked" in out["companies"]


def test_corrupt_observation_history_is_fatal(tmp_path, monkeypatch):
    path = tmp_path / "observed.json"
    path.write_text('{"companies": {"acme": {"cycles": []}}}', encoding="utf-8")
    monkeypatch.setattr(paths, "OBSERVED_PATH", str(path))
    with pytest.raises(observe.ObservedStateCorrupt):
        observe.load()


def test_load_migrates_legacy_counts_without_ids(tmp_path, monkeypatch):
    path = tmp_path / "observed.json"
    path.write_text(
        '{"companies":{"acme":{"name":"Acme","cycles":{'
        '"Fall 2026":{"first_posted":"2026-03-01","count":1197}}}}}',
        encoding="utf-8",
    )
    monkeypatch.setattr(paths, "OBSERVED_PATH", str(path))

    loaded = observe.load()

    cycle = loaded["companies"]["acme"]["cycles"]["Fall 2026"]
    assert cycle["role_ids"] == []
    assert cycle["count"] == 0
