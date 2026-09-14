"""Validated, site-aware company-registry persistence and identity."""

from __future__ import annotations

import json
import os
from collections import defaultdict

from . import paths


class RegistryCorrupt(RuntimeError):
    """The company registry exists but is unsafe to replace or consume."""


_SUPPORTED_ATS = {
    "amazon", "ashby", "breezy", "eightfold", "greenhouse", "lever",
    "oracle", "recruitee", "rippling", "smartrecruiters", "workable", "workday",
}


def board_key(company: dict) -> str:
    """Stable identity for one independently fetched board.

    Workday tenants and Oracle hosts may expose multiple sites.  Treating all of
    them as one board lets a complete response from site A close a role that
    belongs to site B.
    """
    explicit = company.get("board_key")
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip()
    ats = str(company.get("ats") or "").strip().lower()
    slug = str(company.get("slug") or "").strip()
    if ats == "smartrecruiters":
        slug = slug.casefold()
    site = str(company.get("site") or "").strip()
    return f"{ats}:{slug}:{site.casefold()}" if site else f"{ats}:{slug}"


def migrate_store_board_keys(records: dict, companies: list[dict]) -> int:
    """Backfill lifecycle identity when registry ownership is unambiguous.

    Site-aware keys were introduced after the store already contained roles.
    A disappeared legacy Workday/Oracle role will never be fetched again, so
    relying on a connector refresh makes it immortal. Ambiguous tenants remain
    untouched/protected until a later fetch attributes them to a site.
    """
    candidates: dict[tuple[str, str], set[str]] = defaultdict(set)
    for company in companies:
        source = str(company.get("ats") or "").strip().lower()
        slug = str(company.get("slug") or "").strip()
        if source == "smartrecruiters":
            slug = slug.casefold()
        if source and slug:
            candidates[(source, slug)].add(board_key(company))

    changed = 0
    for record in records.values():
        source = str(record.get("source") or "").strip().lower()
        slug = str(record.get("company_slug") or "").strip()
        if source == "smartrecruiters":
            slug = slug.casefold()
        matches = candidates.get((source, slug), set())
        if len(matches) != 1:
            continue
        resolved = next(iter(matches))
        if record.get("board_key") != resolved:
            record["board_key"] = resolved
            changed += 1
    return changed


def validate_company(company: object, index: int | None = None) -> dict:
    label = f"record {index}" if index is not None else "company"
    if not isinstance(company, dict):
        raise RegistryCorrupt(f"{label} must be an object")
    for field in ("name", "slug", "ats"):
        if not isinstance(company.get(field), str) or not company[field].strip():
            raise RegistryCorrupt(f"{label}: {field} must be a non-empty string")
    if company["ats"] not in _SUPPORTED_ATS:
        raise RegistryCorrupt(f"{label}: unsupported ATS {company['ats']!r}")
    if company["ats"] == "workday":
        if not isinstance(company.get("site"), str) or not company["site"].strip():
            raise RegistryCorrupt(f"{label}: Workday record requires site")
        if not company.get("host") and not company.get("wd"):
            raise RegistryCorrupt(f"{label}: Workday record requires wd or host")
    if company["ats"] == "oracle":
        for field in ("host", "site"):
            if not isinstance(company.get(field), str) or not company[field].strip():
                raise RegistryCorrupt(f"{label}: Oracle record requires {field}")
    normalized = dict(company)
    normalized["name"] = normalized["name"].strip()
    normalized["slug"] = normalized["slug"].strip()
    normalized["ats"] = normalized["ats"].strip().lower()
    return normalized


def validate(data: object) -> list[dict]:
    if not isinstance(data, list):
        raise RegistryCorrupt(f"registry must be a list, got {type(data).__name__}")
    companies = [validate_company(company, i) for i, company in enumerate(data)]
    keys = [board_key(company) for company in companies]
    if len(keys) != len(set(keys)):
        duplicates = sorted(key for key in set(keys) if keys.count(key) > 1)
        raise RegistryCorrupt(f"duplicate board identities: {', '.join(duplicates[:5])}")
    return companies


def load(path: str | None = None, *, missing_ok: bool = False) -> list[dict]:
    target = path or paths.COMPANIES_PATH
    if not os.path.exists(target):
        if missing_ok:
            return []
        raise RegistryCorrupt(f"registry does not exist: {target}")
    try:
        with open(target, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        raise RegistryCorrupt(f"{target} is unreadable: {exc}") from exc
    return validate(data)


def save(companies: list[dict], path: str | None = None) -> None:
    target = path or paths.COMPANIES_PATH
    normalized = validate(companies)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    tmp = f"{target}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(normalized, f, indent=2, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, target)
