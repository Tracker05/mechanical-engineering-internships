"""Workday (enterprise tier) — the biggest ATS in intern hiring.

Per-tenant POST API behind bot management. Two public URL shapes exist and we
support both:
  subdomain:  https://{tenant}.{wd}.myworkdayjobs.com/{site}
  path-style: https://{wd}.myworkdaysite.com/recruiting/{tenant}/{site}
The CXS JSON API lives under /wday/cxs/{tenant}/{site} on either host.

The API caps each page at 20 postings, so we paginate — big tech tenants list
far more than 20 intern roles at peak season. Dates are relative text
("Posted 6 Days Ago"); we resolve precise ones here and the enrichment stage
backfills exact dates from the job detail endpoint.

Cloud IPs are blocked more than home IPs, so the pipeline routes this connector
through an optional proxy (WORKDAY_PROXY) when one is configured.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

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

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Accept": "application/json",
}

_DAYS_AGO = re.compile(r"(\d+)\s*\+?\s*days?\s+ago", re.IGNORECASE)

# A requisition id as Workday writes it: letters/digits/dashes, at least one
# digit, no whitespace. Deliberately narrow — this is only ever accepted after
# the externalPath cross-check below agrees with it.
_REQ_ID = re.compile(r"^(?=[A-Za-z0-9-]*\d)[A-Za-z0-9][A-Za-z0-9-]{1,31}$")

_PAGE_SIZE = 20   # hard server-side cap per request
_MAX_JOBS = 200   # per search term; big tenants list hundreds of "intern" hits
# Workday's searchText is literal enough that "intern" misses "Co-Op Engineer".
# Our own classifier accepts co-ops, so we have to ask for them explicitly.
_SEARCH_TERMS = ("intern", "co-op")


def _resolve_posted(text: str | None) -> str | None:
    if not text:
        return None
    lowered = text.lower()
    if "today" in lowered:
        days = 0
    elif "yesterday" in lowered:
        days = 1
    elif "30+" in lowered:
        return None  # too vague to be a real date
    else:
        match = _DAYS_AGO.search(lowered)
        if not match or int(match.group(1)) >= 30:
            return None
        days = int(match.group(1))
    return (datetime.now(UTC) - timedelta(days=days)).strftime("%Y-%m-%dT00:00:00Z")


def _requisition_id(posting: dict, path: str) -> str | None:
    """The tenant's own requisition number, or None if we can't prove one.

    One tenant may run several career sites, and a requisition posted to more
    than one gets a DIFFERENT externalPath on each: Tencent's R107752 is
    `..._R107752` on OA_Huoshui_Platform and `..._R107752-1` on Tencent_Careers.
    Both resolve to jobReqId R107752 with a byte-identical description, so the
    path alone makes one job look like two.

    `bulletFields` carries the real number, but it is a free-form display slot —
    some tenants put a location or a job family in it. So it is only trusted
    when the externalPath independently agrees: the path must end in that same
    token, optionally followed by Workday's `-N` per-site uniquifier. When both
    say R107752, that is not a guess.
    """
    bullets = posting.get("bulletFields")
    if not isinstance(bullets, list):
        return None
    for bullet in bullets:
        if not isinstance(bullet, str):
            continue
        candidate = bullet.strip()
        if not _REQ_ID.match(candidate):
            continue
        tail = path.rsplit("_", 1)[-1] if "_" in path else ""
        if tail == candidate or re.fullmatch(rf"{re.escape(candidate)}-\d+", tail):
            return candidate
    return None


def _urls(company: dict) -> tuple[str, str]:
    """(cxs jobs endpoint, public base URL) for either Workday host shape."""
    tenant, site = company["slug"], company["site"]
    host = company.get("host")  # set for path-style tenants by discovery
    if host:
        return (
            f"https://{host}/wday/cxs/{tenant}/{site}/jobs",
            f"https://{host}/recruiting/{tenant}/{site}",
        )
    sub_host = f"{tenant}.{company['wd']}.myworkdayjobs.com"
    return (
        f"https://{sub_host}/wday/cxs/{tenant}/{site}/jobs",
        f"https://{sub_host}/{site}",
    )


async def fetch(company: dict, net: Net) -> Fetch:
    tenant = company["slug"]
    api_url, base = _urls(company)

    jobs: dict[str, Job] = {}  # keyed by job id: the two searches overlap
    incomplete_reason: str | None = None
    for term in _SEARCH_TERMS:
        exhausted = False
        trusted_total: int | None = None
        seen_pages: set[tuple[str, ...]] = set()
        for offset in range(0, _MAX_JOBS, _PAGE_SIZE):
            body = {"appliedFacets": {}, "limit": _PAGE_SIZE, "offset": offset,
                    "searchText": term}
            data = await net.post_json(api_url, json=body, headers=HEADERS)
            postings = clean_listing(data, "jobPostings")
            if postings is None:
                incomplete_reason = INCOMPLETE_MALFORMED
                break  # malformed 200 / error envelope: leave the fetch partial
            signature = tuple(
                str(posting.get("externalPath") or posting.get("title") or "")
                for posting in postings
            )
            if postings and signature in seen_pages:
                # Some tenants ignore offset and repeat page one forever. Do
                # not burn all ten requests or call that repeated page a cap;
                # it is explicit pagination failure and unsafe for closure.
                incomplete_reason = INCOMPLETE_STALLED
                break
            seen_pages.add(signature)
            total = data.get("total") if isinstance(data, dict) else None
            if (
                trusted_total is None
                and isinstance(total, int)
                and not isinstance(total, bool)
                and total > 0
                and total >= offset + len(postings)
            ):
                # Workday sometimes emits `0` on later full pages. Retain the
                # first credible count instead of treating that transient zero
                # as proof that the search is exhausted.
                trusted_total = total
            for posting in postings:
                path = posting.get("externalPath") or ""
                posted = _resolve_posted(posting.get("postedOn"))
                location = (posting.get("locationsText") or "—").strip() or "—"
                requisition = _requisition_id(posting, path)
                # Scoped by TENANT because Workday req numbers are only unique
                # inside one tenant, and by LOCATION because a requisition
                # advertised in two cities is two openings — merging those
                # would delete a real place someone could work.
                canonical = (
                    f"{tenant}:{requisition}:{re.sub(r'[^a-z0-9]+', ' ', location.lower()).strip()}"
                    if requisition else None
                )
                job = Job(
                    id=f"workday:{tenant}:{path or posting.get('title')}",
                    source="workday",
                    company=company["name"],
                    company_slug=tenant,
                    title=(posting.get("title") or "").strip(),
                    location=location,
                    url=(base + path) if path else base,
                    posted_at=posted,
                    # "Posted 6 Days Ago" arithmetic, not a real date. Labeled
                    # so the detail page's true date can supersede it later.
                    posted_at_source="relative_derived" if posted else None,
                    board_key=source_board_key(company, "workday", tenant),
                    canonical_id=canonical,
                    requisition_id=requisition,
                )
                jobs.setdefault(job.id, job)
            if len(postings) < _PAGE_SIZE:
                exhausted = True  # we reached the end of this term's results
                break
            if trusted_total is not None and offset + len(postings) >= trusted_total:
                exhausted = True
                break
        if not exhausted:
            incomplete_reason = incomplete_reason or INCOMPLETE_CAPPED
    return Fetch(
        list(jobs.values()),
        complete=incomplete_reason is None,
        incomplete_reason=incomplete_reason,
    )
