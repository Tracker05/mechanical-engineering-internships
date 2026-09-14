"""Recruitee offers API ({slug}.recruitee.com/api/offers/): public, no auth.

Offers include their full description HTML, so sponsorship classification is
free for this source.
"""

from __future__ import annotations

from ..models import Fetch, Job, clean_listing, source_board_key
from ..net import Net

URL = "https://{slug}.recruitee.com/api/offers/"


def _country(value, code) -> str:
    text = str(value or "").strip()
    token = str(code or "").strip().upper()
    if token in {"US", "USA"}:
        return "United States"
    if token == "GB":
        return "United Kingdom"
    return text or (f"International ({token})" if token else "")


def _one_location(location: dict) -> str:
    name = str(location.get("Name") or location.get("name") or "").strip()
    city = str(location.get("city") or "").strip()
    state = str(location.get("state") or location.get("region") or "").strip()
    country = _country(location.get("country"), location.get("country_code"))
    if city or state:
        return ", ".join(p for p in (city, state, country) if p)
    if name:
        if country and country.lower() not in name.lower():
            return f"{name}, {country}"
        return name
    return country


def _location(offer: dict) -> str:
    rendered: list[str] = []
    locations = offer.get("locations")
    if isinstance(locations, list):
        for item in locations:
            if not isinstance(item, dict):
                continue
            text = _one_location(item)
            if text and text not in rendered:
                rendered.append(text)
    if not rendered:
        text = str(offer.get("location") or "").strip()
        # "Remote job" is a work arrangement, not geographic evidence. Prefer
        # structured city/country when the API supplies it separately.
        if text and text.lower() not in {"remote", "remote job"}:
            rendered.append(text)
        if not rendered:
            parts = [
                str(p).strip()
                for p in (offer.get("city"), offer.get("country"))
                if p
            ]
            if parts:
                rendered.append(", ".join(parts))
    text = "; ".join(p for p in rendered if p)
    remote = bool(offer.get("remote")) or str(offer.get("location") or "").lower() in {
        "remote",
        "remote job",
    }
    hybrid = bool(offer.get("hybrid"))
    if hybrid:
        text = f"{text} (Hybrid)" if text else "Hybrid"
    elif remote:
        text = f"{text} (Remote)" if text else "Remote"
    return text or "—"


async def fetch(company: dict, net: Net) -> Fetch:
    slug = company["slug"]
    data = await net.get_json(URL.format(slug=slug))
    listing = clean_listing(data, "offers")

    jobs = []
    for offer in (listing or []):
        jobs.append(
            Job(
                id=f"recruitee:{slug}:{offer.get('id')}",
                source="recruitee",
                company=company["name"],
                company_slug=slug,
                title=(offer.get("title") or "").strip(),
                location=_location(offer),
                url=offer.get("careers_url") or "",
                posted_at=offer.get("published_at") or offer.get("created_at"),
                description=offer.get("description"),
                board_key=source_board_key(company, "recruitee", slug),
            )
        )
    return Fetch.board(jobs, isinstance(listing, list))
