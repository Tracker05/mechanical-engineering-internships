"""The single normalized job record every connector produces.

Keeping one shape means the pipeline, store, and renderer never care which ATS a
role came from — adding a source touches only its connector.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Fields that exist only during a run and must never be written to the store
# (descriptions are multi-KB blobs; we persist the classification, not the text).
TRANSIENT_FIELDS = ("description",)


# How trustworthy a posted_at is, worst to best. Connectors label what they
# actually got; the store only ever REPLACES a date with a higher-ranked one,
# so a Workday "Posted 6 Days Ago" approximation can be corrected by the
# detail page's real date but a real date can never regress to a guess.
DATE_PRECISION = {None: 0, "unknown": 0, "relative_derived": 1,
                  "date_only": 2, "exact": 3}

# Standard reasons for an incomplete Fetch.  `complete` remains the lifecycle
# switch used by the existing pipeline; the reason lets health/metrics tell a
# deliberately capped but usable response from a malformed HTTP 200.
INCOMPLETE_CAPPED = "result-cap"
INCOMPLETE_MALFORMED = "malformed-response"
INCOMPLETE_STALLED = "pagination-stalled"


def clean_listing(data, key: str) -> list | None:
    """`data[key]` as a validated list of objects, or None when untrustworthy.

    None means MALFORMED, never empty — the callers translate it into an
    incomplete snapshot. Three things disqualify a payload:

      - it isn't an object at all;
      - it carries a truthy error indicator. `{"error": "rate limited",
        "jobs": []}` is an error wearing an empty board's clothes, and reading
        it as "no openings" closes every role the employer has. (Amazon ships
        `"error": null` on healthy responses, so only a truthy value counts.)
      - any list member isn't an object — `[{}]`-style junk is handled a level
        up, but `[1, 2]` means the shape itself changed under us.
    """
    if not isinstance(data, dict):
        return None
    if data.get("error") or data.get("errors"):
        return None
    items = data.get(key)
    if not isinstance(items, list):
        return None
    if any(not isinstance(x, dict) for x in items):
        return None
    return items


def clean_list(value) -> list | None:
    """Same contract as clean_listing, for APIs whose response IS the list."""
    if not isinstance(value, list) or any(not isinstance(x, dict) for x in value):
        return None
    return value


def date_source(posted_at: str | None) -> str | None:
    """Classify a posted_at's precision from its shape.

    A bare date or a midnight timestamp is a DAY, not a moment — several ATS
    only publish the day, and we render midnight for them. Anything with a real
    clock time is exact. Workday is the one source whose midnight value is
    worse than it looks ("Posted 6 Days Ago" arithmetic); its connector labels
    those `relative_derived` explicitly and this helper never overrides a label
    a connector already set.
    """
    if not posted_at:
        return None
    if len(posted_at) <= 10 or "T00:00:00" in posted_at:
        return "date_only"
    return "exact"


def source_board_key(company: dict, source: str, slug: str | None = None) -> str:
    """Stable board identity carried by every normalized job.

    Discovery may provide a richer, site-aware key (important for Workday and
    Oracle tenants that expose more than one career site).  Falling back to the
    historical ``<source>:<slug>`` shape keeps existing registries and stored
    lifecycle keys compatible until that metadata has been backfilled.
    """
    explicit = company.get("board_key")
    if explicit:
        return str(explicit)
    token = slug if slug is not None else company.get("slug")
    return f"{source}:{token or ''}"


@dataclass
class Job:
    id: str               # stable: "<source>:<company_slug>:<external_id>"
    source: str
    company: str
    company_slug: str
    title: str
    location: str
    url: str
    posted_at: str | None = None   # real publish date, or None when unknown
    posted_at_source: str | None = None  # exact | date_only | relative_derived
    season: str = "Unspecified"    # primary cycle label, assigned by the pipeline
    seasons: list[str] | None = None  # ALL tracked cycles the title states, when >1
    season_inferred: bool = False  # True when the cycle came from the posting
                                   # date, not a year stated in the title
    category: str = "Other"
    sponsorship: str = "unknown"   # citizens-only | no-sponsorship | offers | unknown
    salary: str | None = None      # pay text when the ATS exposes it (Ashby/Lever/Breezy)
    skills: list[str] | None = None  # tags extracted from posting text (None = not yet)
    description: str | None = None  # transient: raw posting text, used for classification
    # New identity metadata lives at the end to preserve the positional shape
    # of every pre-existing optional field.
    board_key: str | None = None
    # Some ATSes republish one underlying requisition under multiple posting
    # ids/board aliases.  Preserve their own stable identity as evidence for a
    # safe alias merge; never replace `id` with it without a store migration.
    canonical_id: str | None = None
    requisition_id: str | None = None
    # Posting ids that were proven to represent this same canonical
    # requisition.  Keeping them prevents a board-alias change from looking
    # like a brand-new role (and therefore sending a duplicate alert).
    aliases: list[str] | None = None


@dataclass
class Fetch:
    """One connector's answer for one company, plus how much of it we trust.

    `complete` is the important half. Several ATS APIs cap how many results a
    search returns (Workday/Oracle 100, Amazon/SmartRecruiters/Eightfold 300),
    and a capped response looks exactly like a company that simply has fewer
    roles. Recording a truncated page as the full truth is how a live posting on
    result 101 gets marked "taken down": the store closes anything a *successful*
    fetch didn't return. So a connector that may have been cut off says so here,
    and the pipeline refuses to close that company's roles this run.

    Connectors that read a whole board in one call (Greenhouse, Lever, Ashby,
    Breezy, Recruitee, Rippling) may keep returning a bare list — `of()` treats
    that as a complete snapshot.
    """

    jobs: list[Job] = field(default_factory=list)
    complete: bool = True
    incomplete_reason: str | None = None

    @classmethod
    def of(cls, value) -> Fetch:
        """Normalize a connector's return value into a Fetch.

        Also the last line of defense against junk list members: a payload of
        `[{}]` parses fine and yields a "job" whose external id is None and
        whose title is empty. Those rows are dropped here, and their presence
        poisons completeness — a listing containing garbage members is not a
        trustworthy account of the board, so it must not close anything.
        """
        f = value if isinstance(value, cls) else cls(list(value), complete=True)

        def valid(job: object) -> bool:
            """A row that can safely cross the persistence boundary.

            Connectors consume third-party JSON, so a successful HTTP response
            is not enough evidence that every normalized row is usable.  The
            store quite rightly rejects blank identity/location fields and
            non-HTTP URLs; rejecting them here as malformed snapshot evidence
            prevents one bad member from crashing the whole update after every
            other board has already been fetched.
            """
            if not isinstance(job, Job):
                return False
            required = (
                job.id, job.source, job.company, job.company_slug,
                job.title, job.location, job.url,
            )
            if any(not isinstance(field, str) or not field.strip()
                   for field in required):
                return False
            return (
                job.url.startswith(("https://", "http://"))
                and not job.id.endswith((":None", ":"))
            )

        good = [job for job in f.jobs if valid(job)]
        if len(good) != len(f.jobs):
            return cls(
                good,
                complete=False,
                # Malformed members are a stronger signal than an otherwise
                # expected result cap: health/metrics must surface bad rows.
                incomplete_reason=INCOMPLETE_MALFORMED,
            )
        return f

    @classmethod
    def board(cls, jobs: list[Job], payload_ok: bool) -> Fetch:
        """A whole-board read, complete only if the payload had the right shape.

        A malformed HTTP 200 is the dangerous case: an API that answers `{}` or
        an error object parses fine and yields zero jobs, which is
        indistinguishable from "this employer has no openings" — and would then
        close every role they have. So "complete" requires actually finding the
        list container, not merely surviving the parse.
        """
        return cls(
            jobs,
            complete=bool(payload_ok),
            incomplete_reason=None if payload_ok else INCOMPLETE_MALFORMED,
        )
