"""Ashby job board API: public, no auth.

`includeCompensation=true` adds pay tiers, and each posting ships its full
description — so salary and sponsorship classification are free for Ashby.
"""

from __future__ import annotations

from ..models import Fetch, Job, clean_listing, source_board_key
from ..net import Net

URL = "https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true"


def _salary(posting: dict) -> str | None:
    comp = posting.get("compensation")
    if isinstance(comp, dict):
        summary = comp.get("compensationTierSummary") or comp.get("scrapeableCompensationSalarySummary")
        if summary:
            return str(summary).strip()
    return None


async def fetch(company: dict, net: Net) -> Fetch:
    slug = company["slug"]
    data = await net.get_json(URL.format(slug=slug))
    listing = clean_listing(data, "jobs")

    jobs = []
    for posting in (listing or []):
        if posting.get("isListed") is False:
            continue
        job_url = posting.get("jobUrl") or posting.get("applyUrl") or ""
        external = job_url.rstrip("/").rsplit("/", 1)[-1] if job_url else posting.get("title")
        jobs.append(
            Job(
                id=f"ashby:{slug}:{external}",
                source="ashby",
                company=company["name"],
                company_slug=slug,
                title=(posting.get("title") or "").strip(),
                location=(posting.get("location") or "—").strip() or "—",
                url=job_url,
                posted_at=posting.get("publishedAt"),
                salary=_salary(posting),
                description=posting.get("descriptionPlain") or posting.get("descriptionHtml"),
                board_key=source_board_key(company, "ashby", slug),
            )
        )
    return Fetch.board(jobs, isinstance(listing, list))
