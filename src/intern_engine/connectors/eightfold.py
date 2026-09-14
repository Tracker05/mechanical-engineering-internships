"""Eightfold AI career sites (Netflix, American Express, Micron, ...).

One public JSON endpoint per tenant: /api/apply/v2/jobs on the company's own
careers host. The search payload carries each job's description and a real
creation timestamp, so sponsorship classification and posted dates are free —
no per-job detail requests.

Company entry shape:
    {"name": "Netflix", "slug": "netflix", "ats": "eightfold",
     "host": "explore.jobs.netflix.net", "domain": "netflix.com"}
"""

from __future__ import annotations

from datetime import UTC, datetime

from ..models import (
    INCOMPLETE_CAPPED,
    INCOMPLETE_MALFORMED,
    Fetch,
    Job,
    clean_listing,
    source_board_key,
)
from ..net import Net

_PAGE = 100
_MAX = 300  # safety cap; "intern" on one tenant never legitimately needs more

_BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Accept": "application/json",
}


def _posted(unix_ts) -> str | None:
    try:
        ts = int(unix_ts)
    except (TypeError, ValueError):
        return None
    if ts <= 0:
        return None
    return datetime.fromtimestamp(ts, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _location(position: dict) -> str:
    locations = position.get("locations")
    if isinstance(locations, list) and locations:
        return "; ".join(str(x).replace(",", ", ") for x in locations[:4])
    return str(position.get("location") or "—").replace(",", ", ") or "—"


async def fetch(company: dict, net: Net) -> Fetch:
    slug = company["slug"]
    host = company["host"]
    url = f"https://{host}/api/apply/v2/jobs"

    jobs: list[Job] = []
    complete = False
    incomplete_reason: str | None = None
    start = 0
    while start < _MAX:
        params = {
            "domain": company.get("domain", ""),
            "query": "intern",
            "num": _PAGE,
            "start": start,
            "sort_by": "timestamp",
        }
        data = await net.get_json(url, params=params, headers=_BROWSER_HEADERS)
        positions = clean_listing(data, "positions")
        if positions is None:
            incomplete_reason = INCOMPLETE_MALFORMED
            break  # malformed 200 / error envelope: not an empty tenant
        for p in positions:
            external = p.get("id") or p.get("ats_job_id") or p.get("display_job_id")
            job_url = p.get("canonicalPositionUrl") or f"https://{host}/careers"
            jobs.append(
                Job(
                    id=f"eightfold:{slug}:{external}",
                    source="eightfold",
                    company=company["name"],
                    company_slug=slug,
                    title=(p.get("name") or "").strip(),
                    location=_location(p),
                    url=job_url,
                    posted_at=_posted(p.get("t_create")),
                    description=p.get("job_description") or None,
                    board_key=source_board_key(company, "eightfold", slug),
                )
            )
        start += _PAGE
        if len(positions) < _PAGE:
            complete = True  # a short page is the end of the list
            break
        # A FULL page only proves the end when the server's own total says so.
        # `int(data.get("count") or 0)` used to make a missing count read as 0,
        # so `start >= 0` was trivially true and a truncated response looked
        # complete — which is what lets a capped page close live roles.
        total = data.get("count")
        if isinstance(total, int) and start >= total:
            complete = True
            break
    if not complete and incomplete_reason is None:
        incomplete_reason = INCOMPLETE_CAPPED
    return Fetch(jobs, complete=complete, incomplete_reason=incomplete_reason)
