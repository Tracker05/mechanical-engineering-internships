"""Amazon Jobs search API: public JSON, one fixed endpoint (not per-tenant).

The search payload includes each job's description and qualifications, so
sponsorship classification needs no extra requests.
"""

from __future__ import annotations

from datetime import datetime

from ..models import (
    INCOMPLETE_CAPPED,
    INCOMPLETE_MALFORMED,
    Fetch,
    Job,
    clean_listing,
    source_board_key,
)
from ..net import Net

# US state/territory codes, for expanding Amazon's "US, MA, Westboro" strings.
_STATES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
    "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota",
    "MS": "Mississippi", "MO": "Missouri", "MT": "Montana", "NE": "Nebraska",
    "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey",
    "NM": "New Mexico", "NY": "New York", "NC": "North Carolina",
    "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon",
    "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
    "VT": "Vermont", "VA": "Virginia", "WA": "Washington",
    "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
    "DC": "District of Columbia", "PR": "Puerto Rico",
}


_COUNTRIES = {
    "CA": "Canada", "MX": "Mexico", "BR": "Brazil", "IN": "India",
    "GB": "United Kingdom", "UK": "United Kingdom", "IE": "Ireland",
    "DE": "Germany", "FR": "France", "ES": "Spain", "IT": "Italy",
    "NL": "Netherlands", "BE": "Belgium", "LU": "Luxembourg", "PL": "Poland",
    "RO": "Romania", "CZ": "Czech Republic", "AT": "Austria", "CH": "Switzerland",
    "SE": "Sweden", "DK": "Denmark", "NO": "Norway", "FI": "Finland",
    "PT": "Portugal", "GR": "Greece", "TR": "Turkey", "IL": "Israel",
    "AE": "United Arab Emirates", "SA": "Saudi Arabia", "EG": "Egypt",
    "ZA": "South Africa", "NG": "Nigeria", "KE": "Kenya", "AU": "Australia",
    "NZ": "New Zealand", "JP": "Japan", "CN": "China", "HK": "Hong Kong",
    "TW": "Taiwan", "KR": "Korea", "SG": "Singapore", "MY": "Malaysia",
    "ID": "Indonesia", "PH": "Philippines", "VN": "Vietnam", "TH": "Thailand",
    "AR": "Argentina", "CL": "Chile", "CO": "Colombia", "PE": "Peru",
    "CR": "Costa Rica", "JO": "Jordan", "LB": "Lebanon",
}


def _location(job: dict) -> str:
    """Amazon's location, preferring the STRUCTURED fields.

    `normalized_location` is unreliable: a Massachusetts role in Westboro comes
    back as "Westboro, Wisconsin, USA" — a real posting mislabelled into the
    wrong state. `city`/`state` carry the truth ("Westboro", "MA").

    The country half matters just as much, because Amazon's search is
    WORLDWIDE. Emitting "Toronto, ON, CA" or "Bangalore, KA, IN" hands the
    region filter two US state-code lookalikes (California, Indiana), and
    defaulting a missing country to US invents a fact. So a US shape is only
    produced when the country is actually US; everything else is named as a
    country, and an unrecognized code degrades to a token that cannot be read
    as a US state rather than guessing.
    """
    city = (job.get("city") or "").strip()
    state = (job.get("state") or "").strip()
    country = (job.get("country_code") or "").strip().upper()
    is_us = country in ("US", "USA") or (not country and state.upper() in _STATES)

    if city and is_us and state:
        return f"{city}, {_STATES.get(state.upper(), state)}, USA"
    if city and country and not is_us:
        # Known country -> name it (the region filter's foreign-country veto
        # keys off names). Unknown -> say only that it isn't the US, because a
        # bare two-letter code collides with a dozen US state codes.
        return f"{city}, {_COUNTRIES.get(country, 'International')}"
    for key in ("normalized_location", "location"):
        text = (job.get(key) or "").strip()
        if text:
            return text
    return "—"

URL = "https://www.amazon.jobs/en/search.json"

_PAGE_SIZE = 100
_MAX_JOBS = 1000  # Amazon's intern count is worldwide and spikes hard in season


def _posted(text: str | None) -> str | None:
    if not text:
        return None
    for fmt in ("%B %d, %Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text.strip(), fmt).strftime("%Y-%m-%dT00:00:00Z")
        except ValueError:
            continue
    return None


async def fetch(company: dict, net: Net) -> Fetch:
    jobs: list[Job] = []
    complete = False
    incomplete_reason: str | None = None
    for offset in range(0, _MAX_JOBS, _PAGE_SIZE):
        params = {"base_query": "intern", "result_limit": _PAGE_SIZE,
                  "offset": offset, "sort": "recent"}
        data = await net.get_json(URL, params=params)
        results = clean_listing(data, "jobs")
        if results is None:
            incomplete_reason = INCOMPLETE_MALFORMED
            break  # malformed 200 / error envelope: leave the snapshot incomplete
        for j in results:
            path = j.get("job_path") or ""
            description = " ".join(
                str(j.get(k) or "")
                for k in ("description", "basic_qualifications", "preferred_qualifications")
            )
            jobs.append(
                Job(
                    id=f"amazon:amazon:{j.get('id_icims') or path}",
                    source="amazon",
                    company="Amazon",
                    company_slug="amazon",
                    title=(j.get("title") or "").strip(),
                    location=_location(j),
                    url=("https://www.amazon.jobs" + path) if path else "https://www.amazon.jobs",
                    posted_at=_posted(j.get("posted_date")),
                    description=description.strip() or None,
                    board_key=source_board_key(company, "amazon", "amazon"),
                )
            )
        # `hits` is the server's total for the query — the only way to tell a
        # short last page apart from a page cap that hid the rest.
        hits = data.get("hits")
        if len(results) < _PAGE_SIZE or (
            isinstance(hits, int) and offset + len(results) >= hits
        ):
            complete = True
            break
    if not complete and incomplete_reason is None:
        incomplete_reason = INCOMPLETE_CAPPED
    return Fetch(jobs, complete=complete, incomplete_reason=incomplete_reason)
