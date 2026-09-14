"""Employer display names.

Most company names in the registry are derived from an ATS slug, because that
is all the board API gives us. That derivation leaves artifacts a person would
never write: `pony-dot-ai` becomes "Pony Dot Ai", `charlesriveranalytics90`
keeps its account number, `beaconsoftware` never regains its space.

Two layers, deliberately in this order:

1. `data/company_names.json` — an explicit slug/name -> display-name map. The
   only thing that can fix a name no algorithm could recover ("Beaconsoftware"
   -> "Beacon Software"); adding one is a one-line PR.
2. The known generic slug artifact "Dot Ai" -> ".ai".

Anything else is left exactly as the employer's board reports it. A wrong
"correction" is worse than an ugly name: it makes the row look like a different
company.
"""

from __future__ import annotations

import json
import re

from . import paths

_DOT_RE = re.compile(r"\s+Dot\s+(Ai|Io|Co|Com|Sh|Dev|App|Xyz)\b", re.IGNORECASE)

_overrides: dict[str, str] | None = None


def _load_overrides() -> dict[str, str]:
    global _overrides
    if _overrides is None:
        try:
            with open(paths.COMPANY_NAMES_PATH, encoding="utf-8") as f:
                raw = json.load(f)
            _overrides = {str(k).strip().lower(): str(v) for k, v in raw.items()}
        except (OSError, ValueError, AttributeError):
            _overrides = {}
    return _overrides


def display(name: str, slug: str | None = None) -> str:
    """The name to show a human, from the raw registry name (+ optional slug)."""
    raw = (name or "").strip()
    if not raw:
        return raw
    overrides = _load_overrides()
    for key in ((slug or "").strip().lower(), raw.lower()):
        if key and key in overrides:
            return overrides[key]
    return _DOT_RE.sub(lambda m: "." + m.group(1).lower(), raw)
