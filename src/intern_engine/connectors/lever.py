"""Lever postings API: public, no auth. Returns a bare JSON list.

The list payload already carries the full posting text (description + lists +
additional) and a structured salary range, so sponsorship classification and
pay info cost zero extra requests here.
"""

from __future__ import annotations

from datetime import UTC, datetime

from ..models import Fetch, Job, clean_list, source_board_key
from ..net import Net

URL = "https://api.lever.co/v0/postings/{slug}?mode=json"


def _epoch_ms_to_iso(ms) -> str | None:
    if not ms:
        return None
    try:
        return datetime.fromtimestamp(ms / 1000, tz=UTC).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
    except (ValueError, OSError, TypeError):
        return None


def _description(posting: dict) -> str:
    """All the text an applicant would read, flattened for classification."""
    parts = [posting.get("descriptionPlain") or "", posting.get("additionalPlain") or ""]
    for block in posting.get("lists") or []:
        if isinstance(block, dict):
            parts.append(f"{block.get('text') or ''} {block.get('content') or ''}")
    return " ".join(p for p in parts if p)


def _salary(posting: dict) -> str | None:
    rng = posting.get("salaryRange")
    if isinstance(rng, dict) and rng.get("min") and rng.get("max"):
        currency = rng.get("currency") or "USD"
        interval = (rng.get("interval") or "").replace("-", " ").lower()
        # Compact the display: "per hour wage" -> "/hr", "per year salary" ->
        # "/yr", and a min==max band is one number, not "15–15".
        if "hour" in interval:
            unit = "/hr"
        elif "year" in interval or "annum" in interval:
            unit = "/yr"
        elif "month" in interval:
            unit = "/mo"
        else:
            unit = f" / {interval}" if interval else ""
        lo, hi = int(rng["min"]), int(rng["max"])
        band = f"{lo:,}" if lo == hi else f"{lo:,}–{hi:,}"
        return f"{band} {currency}{unit}"
    return None


async def fetch(company: dict, net: Net) -> Fetch:
    slug = company["slug"]
    postings = clean_list(await net.get_json(URL.format(slug=slug)))
    ok = postings is not None

    jobs = []
    for posting in (postings or []):
        categories = posting.get("categories") or {}
        jobs.append(
            Job(
                id=f"lever:{slug}:{posting.get('id')}",
                source="lever",
                company=company["name"],
                company_slug=slug,
                title=(posting.get("text") or "").strip(),
                location=(categories.get("location") or "—").strip() or "—",
                url=posting.get("hostedUrl") or posting.get("applyUrl") or "",
                posted_at=_epoch_ms_to_iso(posting.get("createdAt")),
                salary=_salary(posting),
                description=_description(posting) or None,
                board_key=source_board_key(company, "lever", slug),
            )
        )
    return Fetch.board(jobs, ok)
