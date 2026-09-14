"""Workable jobs API (apply.workable.com): public, no auth.

POST v3 endpoint with a JSON body; paginated via a `nextPage` token. We search
"intern" server-side so big accounts stay cheap. Descriptions live behind the
v2 detail endpoint — the enrichment stage fetches those per matched role.
"""

from __future__ import annotations

from ..models import (
    INCOMPLETE_CAPPED,
    INCOMPLETE_MALFORMED,
    INCOMPLETE_STALLED,
    Fetch,
    Job,
    clean_listing,
    source_board_key,
)
from ..net import Net

URL = "https://apply.workable.com/api/v3/accounts/{slug}/jobs"

_MAX_PAGES = 3


def _render_location(loc) -> str:
    if not isinstance(loc, dict):
        return ""
    country = str(loc.get("country") or "").strip()
    code = str(loc.get("countryCode") or loc.get("country_code") or "").strip().upper()
    if code in {"US", "USA"}:
        country = "United States"
    elif not country and code:
        country = f"International ({code})"
    return ", ".join(
        str(p).strip()
        for p in (loc.get("city"), loc.get("region"), country)
        if p
    )


def _location(job: dict) -> str:
    values: list[str] = []
    for loc in [job.get("location"), *(job.get("locations") or [])]:
        text = _render_location(loc)
        if text and text not in values:
            values.append(text)
    text = "; ".join(values)
    workplace = str(job.get("workplace") or "").lower()
    if workplace == "hybrid":
        text = f"{text} (Hybrid)" if text else "Hybrid"
    elif job.get("remote") or workplace == "remote":
        text = f"{text} (Remote)" if text else "Remote"
    return text or "—"


async def fetch(company: dict, net: Net) -> Fetch:
    slug = company["slug"]

    jobs: list[Job] = []
    complete = False
    incomplete_reason: str | None = None
    token = None
    seen_tokens: set[str] = set()
    for _ in range(_MAX_PAGES):
        body: dict = {"query": "intern", "location": [], "department": [],
                      "worktype": [], "remote": []}
        if token:
            body["token"] = token
        # Workable's current anonymous endpoint returns a provider-wide 429
        # instructing bulk users to request its XML feed. Replaying that same
        # response with exponential/Retry-After sleeps across every account
        # held the whole sweep open for minutes. Fail this board immediately;
        # health quarantine protects its stored roles until access recovers.
        data = await net.post_json(
            URL.format(slug=slug), json=body, retries=0,
        )
        listing = clean_listing(data, "results")
        if listing is None:
            incomplete_reason = INCOMPLETE_MALFORMED
            break  # malformed 200 / error envelope: not an empty account
        for j in listing:
            shortcode = j.get("shortcode")
            jobs.append(
                Job(
                    id=f"workable:{slug}:{shortcode}",
                    source="workable",
                    company=company["name"],
                    company_slug=slug,
                    title=(j.get("title") or "").strip(),
                    location=_location(j),
                    url=f"https://apply.workable.com/{slug}/j/{shortcode}/",
                    posted_at=j.get("published"),
                    board_key=source_board_key(company, "workable", slug),
                )
            )
        token = data.get("nextPage")
        if not token:
            complete = True  # no next page: we read the whole account
            break
        token_key = str(token)
        if token_key in seen_tokens:
            incomplete_reason = INCOMPLETE_STALLED
            break
        seen_tokens.add(token_key)
    if not complete and incomplete_reason is None:
        incomplete_reason = INCOMPLETE_CAPPED
    return Fetch(jobs, complete=complete, incomplete_reason=incomplete_reason)
