"""Identical openings, shown once — without deleting any of them.

Some employers really do open the same job several times. Copart has eight live
"Software Engineering Intern, Dallas" requisitions; GDIT posted RQ225450,
RQ225456 and RQ225469 the same morning, all "Summer 2027 Software Developer
Internship, Annapolis Junction"; Nokia opened five "AI R&D Engineer Co-op".
Every one of those was checked against the live board and every one is a real,
separately-applicable requisition.

So this is NOT deduplication, and it must never be confused with it. Dedup asks
"are these secretly the same posting?" and deletes the copies — `pipeline._dedup`
does that, conservatively, only for identities the ATS itself proves. This
module asks a presentation question instead: "the employer opened this job three
times, so how do we say that in one line?" Nothing is dropped. The store, the
CSV and the JSON API keep every requisition, because a reader building on the
data wants all three ids and a reader scanning the page does not want to read
the same row three times.

The answer is one entry that says how many openings it stands for and links to
each. That is why "posted thrice" stops without a single real opening
disappearing from the list.

The representative is the EARLIEST-seen member, deliberately. It keeps a group's
identity stable from run to run, which matters in three places that would
otherwise break: saved roles are keyed by id in the reader's browser, alerts
settle against a queued id, and a row that changed id every time a sibling
appeared would look like a brand-new posting.
"""

from __future__ import annotations

import re

# Same normalisation as dedup's presentation key. Two postings only group when
# they describe the same employer, the same job and the same place on the same
# terms — work mode included, so "Austin, TX" and "Austin, TX (Remote)" stay
# apart. They are different offers, not a repeat.
_PUNCT = re.compile(r"[^a-z0-9]+")


def _norm_location(location: str) -> str:
    low = (location or "").lower()
    mode = ""
    if re.search(r"\bremote\b", low):
        mode = " remote"
    elif re.search(r"\bhybrid\b", low):
        mode = " hybrid"
    low = re.sub(r"\(remote\)|\bremote\b|\bhybrid\b|\bon[\s-]?site\b", " ", low)
    return _PUNCT.sub(" ", low).strip() + mode


def key(record: dict) -> tuple[str, str, str, str, bool]:
    """What makes two listings 'the same job, opened twice'.

    The cycle is part of it: a Summer 2027 and a Fall 2026 posting of the same
    title are two different opportunities to a reader deciding where to apply,
    even when every other field matches.

    So is open/closed. Surfaces that show both — the Atom feed, the README's
    recently-closed table — must never fold a dead requisition into a live row
    and quietly make the live one's count wrong.
    """
    return (
        (record.get("company") or "").strip().lower(),
        _PUNCT.sub("", (record.get("title") or "").lower()),
        _norm_location(record.get("location") or ""),
        "|".join(record.get("seasons") or [record.get("season") or ""]),
        bool(record.get("is_open")),
    )


def _first_seen(record: dict) -> str:
    return record.get("first_seen_at") or "9999"


def group(records: list[dict]) -> list[dict]:
    """Collapse identical openings into display records, order preserved.

    Each result is a shallow copy of its group's representative plus:
      ``openings``      how many requisitions it stands for (1 for a normal role)
      ``opening_ids``   every member id, earliest-seen first
      ``opening_urls``  the sibling apply links, so all of them stay reachable
      ``opening_newest`` the most recent first_seen in the group, so a freshly
                        added sibling can still earn the "new" badge on a row
                        whose representative is older

    A single-member group is returned unchanged apart from ``openings`` = 1, so
    callers can render every row through the same path.
    """
    order: list[tuple[str, str, str, str, bool]] = []
    buckets: dict[tuple[str, str, str, str, bool], list[dict]] = {}
    for record in records:
        group_key = key(record)
        if group_key not in buckets:
            buckets[group_key] = []
            order.append(group_key)
        buckets[group_key].append(record)

    out: list[dict] = []
    for group_key in order:
        members = sorted(buckets[group_key], key=lambda r: (_first_seen(r), r.get("id") or ""))
        display = dict(members[0])
        display["openings"] = len(members)
        display["opening_ids"] = [m.get("id") for m in members if m.get("id")]
        display["opening_urls"] = [m.get("url") for m in members[1:] if m.get("url")]
        display["opening_newest"] = max(
            (m.get("first_seen_at") or "" for m in members), default="",
        )
        out.append(display)
    return out


def openings_label(record: dict) -> str:
    """"3 openings", or "" for an ordinary single-requisition role."""
    count = record.get("openings") or 1
    return f"{count} openings" if count > 1 else ""
