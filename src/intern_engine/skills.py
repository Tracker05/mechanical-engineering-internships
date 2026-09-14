"""Skill tags + pay extraction from posting text (runs inside enrichment).

Same philosophy as sponsorship.py: precision over recall. The vocabulary is a
curated list of CAD, simulation, and shop-floor tools mechanical students actually filter by — whole-word matches
only, so "Go" needs the word Go (not "goal") and bare "C"/"R" are excluded as
too noisy. Pay is extracted only from explicit money-with-period phrases
("$45/hr", "$120,000 per year"), never inferred.
"""

from __future__ import annotations

import re

# Canonical display name -> match pattern. Order = display priority when a
# posting matches more than MAX_SKILLS. Languages first (the strongest filter
# signal), then ML, then infra/web.
#
# Patterns are case-insensitive by default. Names that are also ordinary
# English words ("react quickly", "reducing rust", "a swift response") match
# case-SENSITIVELY on the capitalized form instead — prose writes them
# lowercase, tech stacks write them capitalized. (?-i:...) scopes that per
# pattern (Python 3.11+).
_VOCAB: list[tuple[str, str]] = [
    # --- CAD (the strongest filter signal for a mechanical student) ---------
    ("SolidWorks", r"solid\s*works"),
    ("CATIA", r"catia"),
    ("Siemens NX", r"siemens\s*nx|unigraphics|\bnx\s*cad\b"),
    ("Creo", r"creo|pro\s*/\s*e\b|pro[\s-]?engineer"),
    ("Inventor", r"(?-i:Inventor)|autodesk\s+inventor"),
    ("Fusion 360", r"fusion\s*360"),
    ("AutoCAD", r"auto\s*cad"),
    ("Onshape", r"onshape"),
    ("Solid Edge", r"solid\s*edge"),
    ("Revit", r"revit"),
    ("GD&T", r"gd&t|geometric\s+dimensioning"),
    ("Tolerance Analysis", r"tolerance\s+(?:analysis|stack[\s-]?up)|stack[\s-]?up\s+analysis"),
    # --- simulation & analysis ---------------------------------------------
    ("ANSYS", r"ansys"),
    ("Abaqus", r"abaqus"),
    ("Nastran", r"nastran|patran"),
    ("COMSOL", r"comsol"),
    ("HyperMesh", r"hyper\s*mesh|altair|hyper\s*works"),
    ("LS-DYNA", r"ls[\s-]?dyna"),
    ("STAR-CCM+", r"star[\s-]?ccm\+?"),
    ("Fluent", r"ansys\s+fluent|\bfluent\s+(?:cfd|simulation)"),
    ("OpenFOAM", r"open\s*foam"),
    ("Adams", r"(?-i:Adams)\s*(?:msc|simulation|multibody)?|msc\s+adams"),
    ("FEA", r"\bfea\b|finite\s+element"),
    ("CFD", r"\bcfd\b|computational\s+fluid\s+dynamics"),
    # --- analysis & code ----------------------------------------------------
    ("MATLAB", r"matlab"),
    ("Simulink", r"simulink"),
    ("Python", r"python"),
    ("C++", r"c\+\+"),
    ("LabVIEW", r"lab\s*view"),
    ("Excel", r"(?-i:Excel)|microsoft\s+excel"),
    ("ROS", r"ros\s*2|robot\s+operating\s+system"),
    ("PLC", r"\bplc\b|ladder\s+logic|allen[\s-]?bradley"),
    # --- manufacturing processes -------------------------------------------
    ("CNC", r"\bcnc\b|computer\s+numerical\s+control"),
    ("Machining", r"machining|milling|lathe|turning\s+center"),
    ("Additive Manufacturing", r"additive\s+manufacturing|3d\s+printing|\bsls\b|\bsla\b|\bfdm\b"),
    ("Injection Molding", r"injection\s+mold(?:ing)?"),
    ("Sheet Metal", r"sheet\s+metal"),
    ("Welding", r"welding|weldment|\btig\b|\bmig\b"),
    ("Casting", r"casting|forging|foundry"),
    ("Composites", r"composites?|carbon\s+fiber|layup"),
    ("Mastercam", r"master\s*cam"),
    ("Hydraulics", r"hydraulic(?:s)?|pneumatic(?:s)?"),
    # --- quality & process methodology --------------------------------------
    ("Six Sigma", r"six\s+sigma|green\s+belt|black\s+belt"),
    ("Lean", r"lean\s+(?:manufacturing|manufactur|principles|six)|kaizen|\b5s\b"),
    ("FMEA", r"\bfmea\b|\bdfmea\b|\bpfmea\b|failure\s+mode"),
    ("DFM", r"\bdfm\b|\bdfma\b|design\s+for\s+manufactur"),
    ("SPC", r"\bspc\b|statistical\s+process\s+control"),
    ("Design of Experiments", r"design\s+of\s+experiments|\bdoe\b"),
    ("CMM", r"\bcmm\b|coordinate\s+measuring"),
    ("Metrology", r"metrology|\bgr&r\b"),
    ("Instron", r"instron|tensile\s+test"),
    # --- PLM / documentation ------------------------------------------------
    ("Teamcenter", r"team\s*center"),
    ("Windchill", r"windchill"),
    ("PLM/PDM", r"\bplm\b|\bpdm\b|product\s+lifecycle\s+management"),
    ("ASME Y14.5", r"asme\s*y14\.?5"),
    ("Git", r"\bgit\b|github|gitlab"),
]

_COMPILED = [
    (name, re.compile(r"(?<![\w+#])(?:" + pat + r")(?![\w+])", re.IGNORECASE))
    for name, pat in _VOCAB
]
_SIGNAL_RANK = {name: rank for rank, (name, _pattern) in enumerate(_VOCAB)}

MAX_SKILLS = 8

_WS_RE = re.compile(r"\s+")


def sort_by_signal(tags: list[str] | None, title: str | None = None) -> list[str]:
    """Put title-mentioned and high-signal technologies first.

    A technology in the job title is the strongest evidence of relevance. The
    remaining tags follow the curated vocabulary priority (languages and core
    frameworks before broad tooling), keeping README rows concise and useful.
    """
    title = title or ""
    patterns = dict(_COMPILED)
    unique = list(dict.fromkeys(tags or []))
    return sorted(
        unique,
        key=lambda tag: (
            not bool(patterns.get(tag) and patterns[tag].search(title)),
            _SIGNAL_RANK.get(tag, len(_SIGNAL_RANK)),
        ),
    )


def extract(text: str | None, title: str | None = None) -> list[str]:
    """Skill tags found in text, ranked by title match and curated signal."""
    if not text:
        return []
    found = [name for name, pattern in _COMPILED if pattern.search(text)]
    return sort_by_signal(found, title)[:MAX_SKILLS]


# --- pay ----------------------------------------------------------------------
# "$45/hr", "$41.50 - $55 per hour"
_HOURLY_RE = re.compile(
    r"\$\s*(\d{2,3}(?:\.\d{1,2})?)"
    r"(?:\s*(?:-|–|—|to)\s*\$?\s*(\d{2,3}(?:\.\d{1,2})?))?"
    r"\s*(?:/\s*|\bper\s+)(?:hour|hr)\b",
    re.IGNORECASE,
)
# "$120,000 - $140,000 per year / annually / /yr"
_ANNUAL_RE = re.compile(
    r"\$\s*(\d{1,3}(?:,\d{3})+|\d{5,6})"
    r"(?:\s*(?:-|–|—|to)\s*\$?\s*(\d{1,3}(?:,\d{3})+|\d{5,6}))?"
    r"[^$\n]{0,30}?(?:/\s*(?:year|yr)|per\s+(?:year|annum)|annual(?:ly|ized)?|a\s+year)",
    re.IGNORECASE,
)


def _hourly_ok(v: float) -> bool:
    return 12 <= v <= 200


def _annual_ok(v: float) -> bool:
    return 20_000 <= v <= 500_000


def _fmt_hourly(v: float) -> str:
    return f"${v:g}"


def _fmt_annual(v: float) -> str:
    return f"${v / 1000:g}k"


def extract_pay(text: str | None) -> str | None:
    """A compact pay string from explicit wage phrases, or None.

    Hourly beats annual (intern pay is usually quoted hourly; an annual figure
    in the same posting is often the conversion or a full-time band).
    """
    if not text:
        return None
    flat = _WS_RE.sub(" ", text)

    for m in _HOURLY_RE.finditer(flat):
        lo = float(m.group(1))
        hi = float(m.group(2)) if m.group(2) else None
        if _hourly_ok(lo) and (hi is None or (_hourly_ok(hi) and hi >= lo)):
            if hi and hi != lo:
                return f"{_fmt_hourly(lo)}–{_fmt_hourly(hi)}/hr"
            return f"{_fmt_hourly(lo)}/hr"

    for m in _ANNUAL_RE.finditer(flat):
        lo = float(m.group(1).replace(",", ""))
        hi = float(m.group(2).replace(",", "")) if m.group(2) else None
        if _annual_ok(lo) and (hi is None or (_annual_ok(hi) and hi >= lo)):
            if hi and hi != lo:
                return f"{_fmt_annual(lo)}–{_fmt_annual(hi)}/yr"
            return f"{_fmt_annual(lo)}/yr"
    return None
