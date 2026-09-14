"""Identical openings collapse into one entry — and nothing else does.

The bug this guards: on 2026-08-07 GDIT opened RQ225450/RQ225456/RQ225469 —
three real requisitions for one job — and the site, the feed and the Telegram
push each printed the same line three times. The fix must fold the display
WITHOUT ever losing a requisition, so these tests check both halves.
"""

from __future__ import annotations

from intern_engine import grouping


def _rec(jid, **extra):
    rec = {
        "id": jid, "company": "GDIT",
        "title": "Summer 2027 Software Developer Internship",
        "location": "USA MD Annapolis Junction", "url": f"https://x/{jid}",
        "season": "Summer 2027", "is_open": True,
        "first_seen_at": "2026-08-07T10:45:44Z",
    }
    rec.update(extra)
    return rec


class TestGrouping:
    def test_three_identical_requisitions_become_one_entry(self):
        rows = grouping.group([_rec("a"), _rec("b"), _rec("c")])
        assert len(rows) == 1
        assert rows[0]["openings"] == 3

    def test_every_requisition_id_is_retained(self):
        # The whole promise: fold the ROW, never drop the opening. These ids
        # settle the outbox and the mailer's sent list.
        rows = grouping.group([_rec("a"), _rec("b"), _rec("c")])
        assert sorted(rows[0]["opening_ids"]) == ["a", "b", "c"]

    def test_every_apply_link_stays_reachable(self):
        rows = grouping.group([_rec("a"), _rec("b"), _rec("c")])
        assert rows[0]["url"] == "https://x/a"
        assert sorted(rows[0]["opening_urls"]) == ["https://x/b", "https://x/c"]

    def test_an_ordinary_role_is_untouched_apart_from_the_count(self):
        rows = grouping.group([_rec("a")])
        assert rows[0]["openings"] == 1
        assert rows[0]["opening_urls"] == []

    def test_the_representative_is_the_earliest_seen_member(self):
        # Stability matters: saved roles are keyed by id in the reader's
        # browser, so a row must not change identity when a sibling appears.
        rows = grouping.group([
            _rec("newer", first_seen_at="2026-08-07T10:00:00Z"),
            _rec("older", first_seen_at="2026-08-01T10:00:00Z"),
        ])
        assert rows[0]["id"] == "older"

    def test_a_new_sibling_still_marks_the_group_new(self):
        rows = grouping.group([
            _rec("older", first_seen_at="2026-08-01T10:00:00Z"),
            _rec("fresh", first_seen_at="2026-08-07T10:00:00Z"),
        ])
        assert rows[0]["opening_newest"] == "2026-08-07T10:00:00Z"


class TestWhatMustNeverGroup:
    def test_different_locations_stay_separate(self):
        rows = grouping.group([_rec("a"), _rec("b", location="Austin, TX")])
        assert len(rows) == 2

    def test_remote_and_onsite_at_one_place_are_two_different_offers(self):
        rows = grouping.group([
            _rec("a", location="Austin, TX"),
            _rec("b", location="Austin, TX (Remote)"),
        ])
        assert len(rows) == 2

    def test_different_cycles_stay_separate(self):
        rows = grouping.group([_rec("a"), _rec("b", season="Fall 2026")])
        assert len(rows) == 2

    def test_a_closed_requisition_never_folds_into_a_live_one(self):
        # The feed and the README's closed table show both. Folding them would
        # make a live row claim an opening nobody can apply to.
        rows = grouping.group([_rec("a"), _rec("b", is_open=False)])
        assert len(rows) == 2
        assert [r["openings"] for r in rows] == [1, 1]

    def test_different_employers_stay_separate(self):
        rows = grouping.group([_rec("a"), _rec("b", company="Copart")])
        assert len(rows) == 2


class TestOrdering:
    def test_input_order_is_preserved(self):
        # Callers sort before grouping (newest first); grouping must not
        # silently reshuffle the page.
        rows = grouping.group([
            _rec("a", company="Zeta"), _rec("b", company="Alpha"), _rec("c", company="Zeta"),
        ])
        assert [r["company"] for r in rows] == ["Zeta", "Alpha"]
