"""Company-level quality gate: keep the list free of junk/no-name companies.

Two independent controls:
  - blocklist (data/blocklist.json): exact company names + name substrings to drop
    (e.g. staffing agencies). Always applied.
  - allowlist_only (config): when true, ONLY show recognizable companies (those in
    the priority list). Stricter, lower coverage; off by default.
"""

from __future__ import annotations

import json

from . import paths, priority


class BlocklistError(ValueError):
    """The blocklist is missing, malformed, or unsafe to apply."""


def load_blocklist() -> dict:
    try:
        with open(paths.BLOCKLIST_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        raise BlocklistError(f"Cannot load blocklist: {exc}") from exc
    if not isinstance(data, dict):
        raise BlocklistError("Blocklist must be a JSON object")

    def entries(key: str) -> list[str]:
        raw = data.get(key, [])
        if not isinstance(raw, list) or any(not isinstance(item, str) for item in raw):
            raise BlocklistError(f"Blocklist {key!r} must be a list of strings")
        normalized = [item.strip().lower() for item in raw]
        if any(not item for item in normalized):
            raise BlocklistError(f"Blocklist {key!r} cannot contain blank entries")
        return list(dict.fromkeys(normalized))

    return {
        "companies": set(entries("companies")),
        "name_contains": entries("name_contains"),
    }


def is_blocked(company: str, blocklist: dict) -> bool:
    name = (company or "").lower().strip()
    if not name:
        return True
    if name in blocklist.get("companies", set()):
        return True
    return any(
        token and token in name for token in blocklist.get("name_contains", [])
    )


def is_recognized(company: str) -> bool:
    """True if the company is in the curated priority list (used by allowlist mode)."""
    return priority.rank(company) < priority.UNRANKED
