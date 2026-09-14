"""Per-company circuit breaker: stop hammering boards that keep failing.

Public datasets inevitably contain renamed slugs and retired boards. Without a
breaker every dead endpoint costs retries on every run, forever. Instead we
track consecutive failures per company and quarantine repeat offenders with an
exponential backoff window:

    3 fails -> skip for 6h, 4 -> 12h, 5 -> 24h, 6 -> 48h, 7+ -> 72h (cap)

A quarantined company is still retried once its window expires, so boards that
come back (rate-limit storms, Workday bot walls) recover on their own — and one
success resets the count to zero. State lives in data/health.json, committed by
CI, so the breaker's decisions are auditable in git history like everything else.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta

from . import paths, registry

_THRESHOLD = 3          # consecutive failures before quarantine kicks in
_BASE_HOURS = 6         # first quarantine window
_CAP_HOURS = 72         # never back off longer than this — boards do come back


class HealthStateCorrupt(RuntimeError):
    """The circuit-breaker state exists but is not safe to overwrite."""


def key(company: dict) -> str:
    return registry.board_key(company)


def _aware_timestamp(value: object) -> bool:
    if not isinstance(value, str) or not value:
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None


def _validate(data: object) -> dict:
    if not isinstance(data, dict):
        raise HealthStateCorrupt(
            f"health state is a {type(data).__name__}, expected an object"
        )
    for board, entry in data.items():
        if not isinstance(board, str) or not board or not isinstance(entry, dict):
            raise HealthStateCorrupt("health state has an invalid board entry")
        failures = entry.get("consecutive_failures")
        if isinstance(failures, bool) or not isinstance(failures, int) or failures < 1:
            raise HealthStateCorrupt(f"{board}: invalid consecutive_failures")
        if not _aware_timestamp(entry.get("last_attempt_at")):
            raise HealthStateCorrupt(f"{board}: invalid last_attempt_at")
        if not isinstance(entry.get("last_error"), str):
            raise HealthStateCorrupt(f"{board}: invalid last_error")
    return data


def load() -> dict:
    if not os.path.exists(paths.HEALTH_PATH):
        return {}
    try:
        with open(paths.HEALTH_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        raise HealthStateCorrupt(f"{paths.HEALTH_PATH} is unreadable: {exc}") from exc
    return _validate(data)


def save(data: dict) -> None:
    _validate(data)
    os.makedirs(os.path.dirname(paths.HEALTH_PATH), exist_ok=True)
    tmp = f"{paths.HEALTH_PATH}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, sort_keys=True)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, paths.HEALTH_PATH)


def _window_hours(failures: int) -> float:
    return min(_BASE_HOURS * 2 ** (failures - _THRESHOLD), _CAP_HOURS)


def is_quarantined(entry: dict | None, now: datetime) -> bool:
    if not entry:
        return False
    failures = entry.get("consecutive_failures", 0)
    if failures < _THRESHOLD:
        return False
    last = entry.get("last_attempt_at")
    if not last:
        return False
    try:
        last_dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        return False
    if last_dt.tzinfo is None:
        return False
    return now < last_dt + timedelta(hours=_window_hours(failures))


def partition(companies: list[dict], data: dict, now: datetime | None = None) -> tuple[list[dict], list[dict]]:
    """Split into (companies to fetch, companies sitting out this run)."""
    now = now or datetime.now(UTC)
    active, benched = [], []
    for company in companies:
        (benched if is_quarantined(data.get(key(company)), now) else active).append(company)
    return active, benched


def migrate_legacy_keys(companies: list[dict], data: dict) -> int:
    """Move pre-site-aware ``ats:slug`` entries to board-specific keys."""
    changed = 0
    for company in companies:
        legacy = f"{company.get('ats')}:{company.get('slug')}"
        current = key(company)
        if legacy == current or legacy not in data or current in data:
            continue
        data[current] = dict(data[legacy])
        # Remove only when no other configured board still needs the legacy key.
        if sum(1 for c in companies if f"{c.get('ats')}:{c.get('slug')}" == legacy) == 1:
            data.pop(legacy, None)
        changed += 1
    return changed


def record(data: dict, company: dict, error: str | None, now: datetime | None = None) -> None:
    """Update one company's entry after a fetch attempt."""
    now = now or datetime.now(UTC)
    ts = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    k = key(company)
    entry = data.get(k) or {}
    entry["last_attempt_at"] = ts
    if error is None:
        # Recovered or healthy: drop the entry entirely to keep the file small.
        data.pop(k, None)
    else:
        previous = entry.get("consecutive_failures", 0)
        if isinstance(previous, bool) or not isinstance(previous, int):
            raise HealthStateCorrupt(f"{k}: invalid consecutive_failures")
        entry["consecutive_failures"] = previous + 1
        entry["last_error"] = error[:200]
        data[k] = entry
