"""Persistent job state, stored as a single human-diffable JSON file.

Why JSON and not SQLite for this repo: the file is committed back to the repo by
GitHub Actions each run, so a text file gives clean diffs ("3 jobs added") and
zero binary/database-persistence headaches. The store is a dict keyed by job id.

Lifecycle work that happens here:
  - first-seen tracking: the moment WE first saw a job (powers "🆕" + sorting)
  - open/closed tracking: a job not seen in a successful fetch is marked closed,
    with a closed_at timestamp (powers the "recently closed" section)
  - retention: long-closed records are purged so the file never grows unbounded
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta

from .models import DATE_PRECISION


def now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class StateCorrupt(RuntimeError):
    """The store exists but couldn't be read as a job store.

    Deliberately fatal. Swallowing this and starting from `{}` is the worst
    possible failure mode: every job reads as brand new (re-alerting the whole
    list), every first_seen_at resets, the closed-role history vanishes — and
    the very next `save` writes the empty result over the only copy of the
    evidence. Better to stop the run with the file intact.
    """


_REQUIRED_RECORD_FIELDS = {
    "id", "source", "company", "company_slug", "title", "location", "url",
    "is_open", "first_seen_at", "last_seen_at",
}


def _timestamp_is_aware(value: object) -> bool:
    if not isinstance(value, str) or not value:
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None


def _validate_record(jid: str, record: dict) -> None:
    missing = sorted(_REQUIRED_RECORD_FIELDS - record.keys())
    if missing:
        raise StateCorrupt(f"{jid}: missing required fields {', '.join(missing)}")
    if record.get("id") != jid:
        raise StateCorrupt(f"{jid}: record id does not match its key")
    for field in ("id", "source", "company", "company_slug", "title", "location", "url"):
        if not isinstance(record.get(field), str) or not record[field].strip():
            raise StateCorrupt(f"{jid}: {field} must be a non-empty string")
    if not record["url"].startswith(("https://", "http://")):
        raise StateCorrupt(f"{jid}: url must be HTTP(S)")
    if not isinstance(record.get("is_open"), bool):
        raise StateCorrupt(f"{jid}: is_open must be boolean")
    for field in ("first_seen_at", "last_seen_at"):
        if not _timestamp_is_aware(record.get(field)):
            raise StateCorrupt(f"{jid}: {field} must be a timezone-aware timestamp")
    if not record["is_open"] and not _timestamp_is_aware(record.get("closed_at")):
        raise StateCorrupt(f"{jid}: a closed record requires closed_at")
    if record["is_open"] and record.get("closed_at"):
        raise StateCorrupt(f"{jid}: an open record cannot carry closed_at")
    for field in ("seasons", "skills", "aliases"):
        value = record.get(field)
        if value is not None and (
            not isinstance(value, list) or not all(isinstance(v, str) for v in value)
        ):
            raise StateCorrupt(f"{jid}: {field} must be a list of strings")
    for field in ("canonical_id", "requisition_id", "board_key"):
        if record.get(field) is not None and not isinstance(record[field], str):
            raise StateCorrupt(f"{jid}: {field} must be a string")


def _validate_store(data: object) -> dict:
    if not isinstance(data, dict):
        raise StateCorrupt(f"store is a {type(data).__name__}, expected an object")
    if not all(isinstance(k, str) and isinstance(v, dict) for k, v in data.items()):
        raise StateCorrupt("store has invalid record entries")
    for jid, record in data.items():
        _validate_record(jid, record)
    return data


def load(path: str) -> dict:
    """The job store, or {} when it genuinely doesn't exist yet.

    Raises StateCorrupt if the file exists but isn't a readable job store.
    """
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        raise StateCorrupt(f"{path} is unreadable: {exc}") from exc
    try:
        return _validate_store(data)
    except StateCorrupt as exc:
        raise StateCorrupt(f"{path}: {exc}") from exc


def save(path: str, data: dict) -> None:
    """Write the store atomically.

    Write-to-temp + os.replace means a crash (or a cancelled Actions run) mid
    write leaves the previous store fully intact rather than a truncated file
    that the next run would have to reject.
    """
    _validate_store(data)
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        # sort_keys keeps the file order stable so git diffs stay small.
        json.dump(data, f, indent=2, ensure_ascii=False, sort_keys=True)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)  # atomic on POSIX and Windows


# Fields we refresh on every run for jobs we've seen before.
# NOTE: posted_at is deliberately NOT here — we freeze the published date the
# first time we see a role so the "Posted" column never shifts on later runs
# (the report behaves like a ladder: old roles sink, new ones land on top).
# The one exception is precision: a HIGHER-precision date for the same role
# (the Workday detail page correcting a "days ago" approximation) replaces a
# lower one — see the DATE_PRECISION comparison in upsert.
# sponsorship/salary/enriched_at are handled specially below: a settled verdict
# must never be clobbered by a run that didn't re-enrich.
_REFRESH_FIELDS = (
    "title", "location", "url",
    "season", "season_inferred", "seasons", "category", "company", "source",
    "company_slug",
)


def upsert(existing: dict, jobs: list[dict], complete_keys: set[str],
           enriched_ids: set[str] | None = None,
           seen_ids: set[str] | None = None,
           classifier_version: int | None = None) -> list[str]:
    """Merge freshly-fetched jobs into the existing store.

    Returns ids that should be announced: never-before-seen roles plus roles
    that genuinely reopened after having been closed.

    A role leaves the list for one of two reasons, and they need different
    evidence:

    `complete_keys` is the set of "<source>:<slug>" whose fetch returned the
    company's COMPLETE list this run (see models.Fetch). A job is closed only
    after it's missing from TWO consecutive complete snapshots — so neither a
    network blip, nor a result cap that hid page 2, nor a one-run ATS indexing
    gap can mark a live role "taken down".

    `seen_ids` is every job a successful fetch returned, in scope or not. A
    stored role that came back but no longer passes our filters (wrong country,
    off-cycle, not a mechanical internship) is closed as out-of-scope no matter how
    complete the snapshot was: that verdict is ours to make, and it needs no
    evidence from the employer.

    `enriched_ids` are jobs whose sponsorship verdict came from posting text
    THIS run; those get an enriched_at stamp so enrichment never repeats.
    """
    ts = now_iso()
    enriched_ids = enriched_ids or set()
    fetched_ids = seen_ids or set()  # everything a fetch returned, kept or not
    kept_ids: set[str] = set()       # the subset that passed our filters
    new_ids: list[str] = []

    for job in jobs:
        jid = job["id"]
        kept_ids.add(jid)
        if jid in existing:
            record = existing[jid]
            reopened = not record.get("is_open") or bool(record.get("closed_at"))
            reopen_reason = record.get("closed_reason")
            for key in _REFRESH_FIELDS:
                if key in job:
                    record[key] = job[key]
            for key in ("board_key", "canonical_id", "requisition_id"):
                if job.get(key):
                    record[key] = job[key]
            if job.get("aliases"):
                aliases = set(record.get("aliases") or [])
                aliases.update(job["aliases"])
                aliases.discard(jid)
                record["aliases"] = sorted(aliases)
            # posted_at: fill blanks, and upgrade precision — never downgrade.
            # An exact/detail-page date replaces a "days ago" approximation for
            # the same role, but a fresh approximation can't shift a real date.
            if job.get("posted_at"):
                old_rank = DATE_PRECISION.get(record.get("posted_at_source"), 0)
                new_rank = DATE_PRECISION.get(job.get("posted_at_source"), 0)
                if not record.get("posted_at") or new_rank > old_rank:
                    record["posted_at"] = job["posted_at"]
                    record["posted_at_source"] = job.get("posted_at_source")
            if job.get("salary"):
                record["salary"] = job["salary"]
            if job.get("skills") is not None:
                record["skills"] = job["skills"]
            # A verdict from fresh text this run always lands — including a
            # downgrade to "unknown", which is how a re-versioned classifier
            # retracts an old false positive. Otherwise unknown never clobbers.
            if jid in enriched_ids or job.get("sponsorship", "unknown") != "unknown":
                record["sponsorship"] = job.get("sponsorship", "unknown")
            if record.get("closed_at"):
                del record["closed_at"]  # the role came back
                record.pop("closed_reason", None)
            record.pop("missing_streak", None)  # seen again -> closure disarmed
            record["last_seen_at"] = ts
            record["is_open"] = True
            # Only an employer-backed disappearance and later return is a new
            # event worth announcing. Policy tombstones can reopen because a
            # stale title/location was corrected in this same run; announcing
            # those replays an old role to every subscriber.
            if reopened and reopen_reason == "gone-from-feed":
                new_ids.append(jid)
        else:
            record = dict(job)
            record["first_seen_at"] = ts
            record["last_seen_at"] = ts
            record["is_open"] = True
            existing[jid] = record
            new_ids.append(jid)
        if jid in enriched_ids:
            existing[jid]["enriched_at"] = ts
            if classifier_version is not None:
                existing[jid]["classifier_v"] = classifier_version

    for jid, record in existing.items():
        if not record.get("is_open") or jid in kept_ids:
            continue
        company_key = record.get("board_key") or (
            f"{record.get('source')}:{record.get('company_slug')}"
        )
        if jid in fetched_ids:
            # The employer still lists it; WE decided it doesn't belong. Our
            # own verdict is deterministic — no second opinion needed.
            reason = "out-of-scope"
        elif company_key in complete_keys:
            # Missing from a complete read. ATS search indexes have transient
            # gaps — a role mid-edit can vanish from one query and be back the
            # next — so a single miss only ARMS the closure; the second
            # consecutive complete miss fires it. Reappearing in between
            # disarms (the kept loop above clears the streak). Costs at most
            # one extra run (~an hour) of a genuinely dead role staying listed,
            # in exchange for never closing a live one on an index blip.
            streak = int(record.get("missing_streak") or 0) + 1
            if streak < 2:
                record["missing_streak"] = streak
                continue
            reason = "gone-from-feed"
        else:
            continue  # no evidence either way — leave it open
        record.pop("missing_streak", None)
        record["is_open"] = False
        record["closed_at"] = ts
        record["closed_reason"] = reason

    return new_ids


def purge(existing: dict, keep_closed_days: int = 120) -> int:
    """Drop records that closed more than `keep_closed_days` ago.

    Keeps the store (and its git diffs) bounded while preserving enough closed
    history for the "recently closed" section and lifetime analytics. 120 days
    on purpose: the trends chart spans 16 weeks (112 days), and the old 60-day
    purge was quietly deleting a third of the history that chart claimed to
    show.
    """
    cutoff = (datetime.now(UTC) - timedelta(days=keep_closed_days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    stale = [
        jid for jid, record in existing.items()
        if not record.get("is_open") and (record.get("closed_at") or record.get("last_seen_at") or "") < cutoff
    ]
    for jid in stale:
        del existing[jid]
    return len(stale)
