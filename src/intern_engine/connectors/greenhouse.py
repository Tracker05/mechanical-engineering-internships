"""Greenhouse board API: public, no auth.

The list endpoint now exposes `first_published` (a true publish date), so the
biggest source on the list gets real Posted dates. Descriptions are NOT in the
list payload — the enrichment stage fetches those per matched role.
"""

from __future__ import annotations

from ..models import Fetch, Job, clean_listing, source_board_key
from ..net import Net

URL = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"


async def fetch(company: dict, net: Net) -> Fetch:
    slug = company["slug"]
    data = await net.get_json(URL.format(slug=slug))
    listing = clean_listing(data, "jobs")

    jobs = []
    for posting in (listing or []):
        location = posting.get("location") or {}
        name = location.get("name") if isinstance(location, dict) else None
        canonical = posting.get("internal_job_id")
        requisition = posting.get("requisition_id")
        jobs.append(
            Job(
                id=f"greenhouse:{slug}:{posting.get('id')}",
                source="greenhouse",
                company=company["name"],
                company_slug=slug,
                title=(posting.get("title") or "").strip(),
                location=(name or "").strip() or "—",
                url=posting.get("absolute_url") or "",
                posted_at=posting.get("first_published"),
                board_key=source_board_key(company, "greenhouse", slug),
                canonical_id=str(canonical) if canonical not in (None, "") else None,
                requisition_id=str(requisition) if requisition not in (None, "") else None,
            )
        )
    return Fetch.board(jobs, isinstance(listing, list))
