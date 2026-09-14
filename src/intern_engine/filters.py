"""All the text classification: is it an internship? is it mechanical? which season?

These are deliberately simple, central, and easy to tune. As we see real data
we widen/narrow these patterns here, in one place.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

# --- internship detection (whole words, never substrings) --------------------
_INTERN_RE = re.compile(
    r"\b(intern|interns|internship|co[\s-]?op|cooperative\s+education)\b",
    re.IGNORECASE,
)
_SENIOR_RE = re.compile(
    r"\b(senior|sr|staff|principal|manager|director|\blead\b|vp|head)\b",
    re.IGNORECASE,
)

# --- mechanical-engineering role detection -----------------------------------
# We keep ONLY mechanical and mechanical-adjacent engineering roles. A role must
# match an INCLUDE term and must NOT match an EXCLUDE term. The exclude list
# removes software/data/CS roles and non-technical roles (recruiting, sales,
# marketing, ...). A bare "engineer" is handled separately (see _GENERIC_ENG_RE)
# because for a mechanical student a plain "Engineering Intern" at a
# manufacturer is usually worth seeing, while for a software student it is not.
_INCLUDE_RE = re.compile(
    r"\b("
    # core identity
    r"mechanical|mech\s*e|mechatronic|mechatronics|robotic|robotics|"
    # design & CAD
    r"design engineer|design engineering|mechanical design|machine design|"
    r"product design engineer|cad|drafting|drafter|drafts(?:man|person)|"
    r"tolerance analysis|gd&t|"
    # manufacturing & process
    r"manufacturing|production engineer|production engineering|"
    r"process engineer|process engineering|industrial engineer|"
    r"industrial engineering|tooling|fixture|machining|cnc|"
    r"injection molding|additive manufacturing|3d printing|sheet metal|"
    r"welding|weldment|casting|forging|foundry|fabrication|assembly engineer|"
    r"lean manufacturing|six sigma|plant engineer|facilities engineer|"
    r"maintenance engineer|reliability engineer|"
    # thermal & fluids
    r"thermal|thermodynamic|thermodynamics|heat transfer|hvac|refrigeration|"
    r"cryogenic|cryogenics|fluid|fluids|hydraulic|hydraulics|pneumatic|"
    r"pneumatics|aerodynamic|aerodynamics|cfd|computational fluid|combustion|"
    r"turbomachinery|turbine|piping|pressure vessel|"
    # structures, materials, mechanics
    r"structural|stress analysis|fea|finite element|durability|fatigue|"
    r"vibration|acoustics|materials engineer|materials engineering|"
    r"metallurgy|metallurgical|composites|tribology|kinematics|"
    r"applied mechanics|solid mechanics|"
    # automotive & mobility
    r"automotive|vehicle|powertrain|drivetrain|chassis|suspension|"
    r"brake|braking|transmission|motorsport|motorsports|"
    r"electric vehicle|battery engineer|battery engineering|"
    # aerospace & defense
    r"aerospace|aeronautical|astronautical|propulsion|avionics|"
    r"flight test|spacecraft|launch vehicle|"
    # energy & power
    r"renewable energy|solar engineer|solar engineering|wind energy|"
    r"wind turbine|nuclear engineer|nuclear engineering|power generation|"
    r"energy engineer|energy engineering|"
    # test, quality, R&D
    r"test engineer|test engineering|validation engineer|"
    r"quality engineer|quality engineering|metrology|calibration|"
    r"inspection engineer|failure analysis|"
    r"controls engineer|motion control|actuator|"
    r"biomechanic|biomechanics|medical device|"
    r"r&d engineer|research and development engineer"
    r")\b",
    re.IGNORECASE,
)

# A plain "Engineering Intern" / "Engineer Intern" with no discipline named.
# At a manufacturer these are overwhelmingly mechanical-ish rotational roles,
# so they are included by default and tagged "General Engineering". Set
# `include_general_engineering: false` in data/config.json to drop them.
_GENERIC_ENG_RE = re.compile(
    r"\b(?:engineer|engineering)\b",
    re.IGNORECASE,
)

# Non-technical intent always wins, including titles that merely mention a
# mechanical product ("Automotive Sales Intern"). "Product design" is NOT
# excluded here the way it is for a software list — "Product Design Engineer"
# is a real mechanical role — but the art-school senses of design still are.
_NON_TECH_EXCLUDE_RE = re.compile(
    r"\b("
    r"recruit|recruiting|recruiter|sales|account executive|account manager|"
    r"account management|marketing|marketer|unpaid|"
    r"legal|counsel|accounting|finance intern|human resources|"
    r"people operations|people team|"
    r"talent acquisition|talent management|talent partner|talent sourcing|"
    r"talent operations|talent development|"
    r"communications|business development|"
    r"product designer|ux design|ui design|graphic design|industrial design|"
    r"product manager|product management|"
    r"phd|ph\.d|doctoral"
    r")\b",
    re.IGNORECASE,
)

# Software / data / CS disciplines are a separate major. An explicit mechanical
# identity is allowed to coexist with them ("Mechanical Engineering Intern -
# Simulation Software"), the same way the original list let "Embedded Software /
# Hardware Intern" through.
_SOFTWARE_EXCLUDE_RE = re.compile(
    r"\b("
    r"software|developer|swe|full[\s-]?stack|front[\s-]?end|back[\s-]?end|"
    r"web developer|web engineer|ios|android|devops|devsecops|sre|"
    r"site reliability|compiler|operating system|database|"
    r"cyber|cybersecurity|appsec|application security|information security|"
    r"infosec|"
    r"data science|data scientist|data engineer|data analyst|"
    r"analytics engineer|"
    r"machine learning|deep learning|nlp|artificial intelligence|"
    r"\bai\b|\bml\b|ai/ml|\bllm\b|llms|generative ai|computer vision|"
    r"platform engineer|platform engineering|infrastructure engineer|"
    r"applied scientist|research scientist|"
    r"quantitative (?:developer|research|researcher|trading|trader|analyst)|"
    r"quant (?:developer|research|researcher|trading|trader|analyst)|"
    r"computer science|programming|firmware|embedded|"
    r"cloud engineer|cloud engineering|\bcloud\b|\bit\b|"
    r"security engineer|engineering infrastructure|infrastructure|"
    r"\bsaas\b|\bapi\b|research engineer"
    r")\b",
    re.IGNORECASE,
)
# Other engineering majors. Excluded unless the title ALSO carries an explicit
# mechanical identity ("Engineering Intern (Electrical / Mechanical / GNC)").
_OTHER_DISCIPLINE_RE = re.compile(
    r"\b("
    r"civil engineer|civil engineering|geotechnical|surveying|"
    r"chemical engineer|chemical engineering|chemistry|chemist|"
    r"petroleum|environmental engineer|environmental engineering|"
    r"electrical engineer|electrical engineering|\bfpga\b|\basic\b|"
    r"\bpcb\b|analog design|photonics|silicon|semiconductor|vlsi|\brtl\b|"
    r"architecture intern|architectural|"
    r"bioinformatics|biochemistry|genomics"
    r")\b",
    re.IGNORECASE,
)
_MECH_FIRST_RE = re.compile(
    r"\b(?:mechanical|mech\s*e|mechatronic|mechatronics|"
    r"manufacturing|aerospace|aeronautical|propulsion|thermal|hvac|"
    r"automotive|powertrain|chassis|suspension|cad|fea|cfd|"
    r"design engineer|materials engineer|"
    r"structural|vehicle)\b",
    re.IGNORECASE,
)

# --- season detection --------------------------------------------------------
_YEAR_RE = re.compile(r"\b(20\d\d)\b")
# "Summer '27" / "SWE Intern '27": two-digit years behind an apostrophe.
_SHORT_YEAR_RE = re.compile(r"['’](\d{2})\b")
# A graduation year in a title ("Class of 2027", "Graduating 2027") names the
# student, not the internship cycle — those years must not bucket the role.
_TITLE_MONTH_NAMES = {
    "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3,
    "april": 4, "apr": 4, "may": 5, "june": 6, "jun": 6, "july": 7, "jul": 7,
    "august": 8, "aug": 8, "september": 9, "sept": 9, "sep": 9,
    "october": 10, "oct": 10, "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}
_TITLE_MONTH_PATTERN = "|".join(
    sorted(_TITLE_MONTH_NAMES, key=len, reverse=True)
)
_TITLE_GRAD_RE = re.compile(
    r"\b(?:"
    r"class\s+(?:of|year)\s+['’]?(?:20)?\d{2}"
    r"|(?:expected\s+(?:to\s+)?)?graduat(?:e|es|ed|ing|ion)"
    r"(?:\s+(?:date|year))?(?:\s+(?:in|by|on))?\s*:?\s*"
    r"(?:(?:" + _TITLE_MONTH_PATTERN + r"|summer|fall|autumn|winter|spring)\s+)?"
    r"['’]?(?:20)?\d{2}"
    r")\b",
    re.IGNORECASE,
)
_TITLE_MONTH_RE = re.compile(
    r"\b(" + _TITLE_MONTH_PATTERN + r")\.?\s+"
    r"(?:\d{1,2}(?:st|nd|rd|th)?,?\s+)?(20\d\d)\b",
    re.IGNORECASE,
)
_TITLE_RANGE_RE = re.compile(
    r"\b(" + _TITLE_MONTH_PATTERN + r")\.?"
    r"(?:\s+\d{1,2}(?:st|nd|rd|th)?)?(?:,?\s+(20\d\d))?\s*"
    r"(?:-|–|—|to|through|thru|until)\s*"
    r"(" + _TITLE_MONTH_PATTERN + r")\.?"
    r"(?:\s+\d{1,2}(?:st|nd|rd|th)?)?,?\s+(20\d\d)\b",
    re.IGNORECASE,
)
_TITLE_MONTH_TERM = {
    1: "Winter", 2: "Winter", 3: "Spring", 4: "Spring",
    5: "Summer", 6: "Summer", 7: "Summer", 8: "Summer",
    9: "Fall", 10: "Fall", 11: "Fall", 12: "Winter",
}


def is_internship(title: str) -> bool:
    if not title:
        return False
    return bool(_INTERN_RE.search(title)) and not _SENIOR_RE.search(title)


def is_mechanical(title: str, *, include_general: bool = True) -> bool:
    """Keep mechanical & mechanical-adjacent roles; reject software/CS/non-tech.

    `include_general` controls the plain "Engineering Intern" case: titles that
    say engineering but name no discipline at all. They are real openings a
    mechanical student should see, but they are also the noisiest bucket, so
    the caller can turn them off.
    """
    if not title:
        return False
    if _NON_TECH_EXCLUDE_RE.search(title):
        return False
    included = bool(_INCLUDE_RE.search(title))
    if not included and include_general:
        # Discipline-free "Engineering Intern": allowed only when nothing in the
        # title points at another major.
        included = bool(
            _GENERIC_ENG_RE.search(title)
            and not _SOFTWARE_EXCLUDE_RE.search(title)
        )
    if not included:
        return False
    if _SOFTWARE_EXCLUDE_RE.search(title) and not _MECH_FIRST_RE.search(title):
        return False
    if _OTHER_DISCIPLINE_RE.search(title) and not _MECH_FIRST_RE.search(title):
        return False
    return True


# Back-compat alias: the pipeline, tools, and tests call this name.
is_tech = is_mechanical


_CYCLE_RE = re.compile(r"(Summer|Fall|Spring|Winter)\s+(\d{4})", re.IGNORECASE)

_COOP_RE = re.compile(r"\bco[\s-]?op\b", re.IGNORECASE)
# "Remote Sensing" is a field of study (satellites), not a work mode — a
# "Remote Sensing Software Intern" in Pasadena is an on-site job.
_REMOTE_RE = re.compile(r"\bremote\b(?!\s+sensing)", re.IGNORECASE)


def program_type(title: str) -> str:
    """"Internship", "Co-op", or "Internship / Co-op" — the title's own words.

    Reddit feedback was blunt about this: co-ops run on different calendars and
    credit requirements, and burying them under the same label as summer
    internships made both harder to trust.

    A title saying BOTH ("Software Engineer Intern/Co-Op") is genuinely open to
    either, so it gets its own value rather than being filed under one and
    hidden from students filtering for the other.
    """
    coop = bool(_COOP_RE.search(title or ""))
    intern = bool(re.search(r"\bintern(?:ship)?s?\b", title or "", re.IGNORECASE))
    if coop and intern:
        return "Internship / Co-op"
    return "Co-op" if coop else "Internship"


def is_remote(location: str, title: str = "") -> bool:
    """True when the posting itself says remote — in the location OR the title.

    Employers put it in either place: VetsEZ writes "Full Stack Developer Intern
    (Remote Opportunity)" with a city in the location field, so reading only the
    location marked genuinely remote roles as on-site. Still no inference beyond
    the employer's own words.
    """
    return bool(_REMOTE_RE.search(location or "")) or bool(_REMOTE_RE.search(title or ""))


def is_cycle_label(value) -> bool:
    """True for a well-formed "<Term> <Year>" label (tracked or not)."""
    return bool(value) and bool(_CYCLE_RE.fullmatch(str(value).strip()))


_TERM_WORD_RE = re.compile(r"\b(summer|fall|autumn|winter|spring)\b", re.IGNORECASE)
_SHARED_TERM_YEAR_RE = re.compile(
    r"\b(summer|fall|autumn|winter|spring)\s*(?:/|&|and|or)\s*"
    r"(summer|fall|autumn|winter|spring)\s+(20\d\d)\b",
    re.IGNORECASE,
)
# How far apart a term and its year may sit and still be read as one label.
# "Summer Intern 2027" is 7 characters apart; anything much wider stops being
# one phrase and starts being two unrelated facts.
_TERM_YEAR_GAP = 24


def detect_seasons(title: str, cycles=("Summer 2027", "Fall 2026")) -> list[str]:
    """EVERY tracked cycle the title states, in `cycles` order.

    Deepgram posts "Software Engineering Internship (Fall 2026/Summer 2027)" —
    one requisition genuinely hiring for two cycles. A single-value season field
    can only keep one, so the other silently vanished from its own cycle's
    section. This collects the full set; `detect_season` still picks the primary.

    Term and year do NOT have to be adjacent. An earlier version only matched
    "<Term> <Year>" verbatim, so "Summer Intern 2027" — which `detect_season`
    reads correctly — came back empty here, and a genuine dual-cycle title like
    "Summer 2027 / Fall Intern 2026" lost its Fall half. Still evidence-only:
    a year must be present, and nothing is inferred from a posting date.
    """
    if not title:
        return []
    scannable = _TITLE_GRAD_RE.sub(" ", title)  # graduation years name the student
    terms = [(m.start(), m.end(),
              "Fall" if m.group(1).lower() == "autumn" else m.group(1).capitalize())
             for m in _TERM_WORD_RE.finditer(scannable)]

    stated: set[str] = set()
    for match in _SHARED_TERM_YEAR_RE.finditer(scannable):
        year = match.group(3)
        for raw_term in match.group(1), match.group(2):
            term = "Fall" if raw_term.lower() == "autumn" else raw_term.capitalize()
            stated.add(f"{term} {year}")
    years = [(m.start(), m.end(), m.group(1)) for m in _YEAR_RE.finditer(scannable)]
    years += [(m.start(), m.end(), f"20{m.group(1)}")
              for m in _SHORT_YEAR_RE.finditer(scannable)]
    for y_start, y_end, year in years:
        near = [t for t in terms
                if (t[0] - y_end <= _TERM_YEAR_GAP and t[0] >= y_end)
                or (y_start - t[1] <= _TERM_YEAR_GAP and y_start >= t[1])]
        if near:
            # Closest term wins, so "Fall 2026/Summer 2027" pairs correctly.
            term = min(near, key=lambda t: min(abs(t[0] - y_end), abs(y_start - t[1])))[2]
            stated.add(f"{term} {year}")
        elif len(terms) == 1:
            stated.add(f"{terms[0][2]} {year}")  # one term governs the whole title

    found = []
    for label in cycles:
        m = _CYCLE_RE.match(label.strip())
        if m and f"{m.group(1).capitalize()} {m.group(2)}" in stated:
            found.append(label)
    return found


def _title_month_labels(scannable: str) -> list[str]:
    """Cycle labels explicitly established by title months, strongest first."""
    labels: list[str] = []
    ranges = list(_TITLE_RANGE_RE.finditer(scannable))
    if ranges:
        for match in ranges:
            month = _TITLE_MONTH_NAMES[match.group(1).lower().rstrip(".")]
            year = match.group(2) or match.group(4)
            label = f"{_TITLE_MONTH_TERM[month]} {year}"
            if label not in labels:
                labels.append(label)
        return labels

    for match in _TITLE_MONTH_RE.finditer(scannable):
        month = _TITLE_MONTH_NAMES[match.group(1).lower().rstrip(".")]
        label = f"{_TITLE_MONTH_TERM[month]} {match.group(2)}"
        if label not in labels:
            labels.append(label)
    return labels


def states_explicit_year(title: str) -> bool:
    """True when the title names a year (graduation years don't count).

    Used as a hard stop: when detect_season refused a year-stating title, that
    year is off-cycle — the role must not be rescued by a sticky stored season
    or a posting-date inference ("Summer 2026 Intern" stays out, period).
    """
    if not title:
        return False
    scannable = _TITLE_GRAD_RE.sub(" ", title)
    return bool(_YEAR_RE.search(scannable) or _SHORT_YEAR_RE.search(scannable))


def detect_season(title: str, cycles=("Summer 2027", "Fall 2026"), *_ignored) -> str | None:
    """Bucket a title into a cycle ONLY if the year is explicit in the title.

    This is strict on purpose: a role must actually state its year (e.g. "2027"
    or "Fall 2026"). Titles with no year fall through to `infer_season`, which
    reasons from the posting date instead and marks the result as inferred —
    a stated year always wins over an inference.

    Examples (cycles = Summer 2027, Fall 2026):
      "Software Engineer Intern, Summer 2027"  -> "Summer 2027"
      "2027 Software Engineer Intern"          -> "Summer 2027"  (year explicit)
      "Fall 2026 Data Science Intern"          -> "Fall 2026"
      "Software Engineer Intern"               -> None  (no year -> drop)
      "Summer 2026 Intern"                     -> None  (past -> drop)
      "Fall 2027 Intern"                       -> None  (cycle not tracked)
    """
    # An exact "<Term> <Year>" phrase for a tracked cycle wins outright.
    # Without this, "Fall 2026 / Summer 2028 Intern" was dropped: the year scan
    # found {2026, 2028} but the term scan picked "Summer" (checked first), and
    # neither Summer 2026 nor Summer 2028 is tracked — even though the title
    # literally states a tracked cycle.
    stated = detect_seasons(title, cycles)
    if stated:
        return stated[0]

    if not title:
        return None
    parsed = []  # (term, year, label)
    for label in cycles:
        m = _CYCLE_RE.match(label.strip())
        if m:
            parsed.append((m.group(1).capitalize(), m.group(2), label))

    scannable = _TITLE_GRAD_RE.sub(" ", title)  # drop graduation-year phrases

    # A start month is stronger than a bare year. This keeps "January 2027"
    # out of Summer 2027 and reads a July-December program from July, the term
    # in which the internship actually starts.
    month_labels = _title_month_labels(scannable)
    if month_labels:
        if len(month_labels) != 1:
            return None
        return month_labels[0] if month_labels[0] in cycles else None

    years = set(_YEAR_RE.findall(scannable))
    years |= {f"20{d}" for d in _SHORT_YEAR_RE.findall(scannable)}
    if not years:
        return None  # no explicit year in the title -> drop

    # Multiple unpaired years ("2026/2027") do not say which cycle this
    # requisition belongs to. Likewise, a term word that failed explicit
    # term/year pairing is conflicting evidence rather than a bare-year title.
    if len(years) != 1 or _TERM_WORD_RE.search(scannable):
        return None

    year = next(iter(years))
    same_year = [label for _term, cycle_year, label in parsed if cycle_year == year]
    return same_year[0] if len(same_year) == 1 else None


# For yearless titles: the month a term's recruiting rolls over to next year.
# Posting month <= rollover -> that term THIS year is still the plausible target;
# after it -> companies are hiring for the term NEXT year. ("Summer Intern"
# posted in March means this summer; posted in July it means next summer.)
_TERM_ROLLOVER_MONTH = {"Summer": 4, "Fall": 8, "Spring": 2, "Winter": 10}


NOT_STATED = "Not stated"
"""Bucket for a real, recent role whose cycle nobody has actually stated.

Not a cycle and never rendered as one. It exists so these roles can stay on
the list — they're genuine early drops — without the list claiming to know
something it doesn't.
"""


def cycle_unstated_ok(title: str, posted_at: str | None,
                      max_age_days: int = 45,
                      now: datetime | None = None) -> bool:
    """May a role with NO stated cycle stay on the list?

    This used to be `infer_season`, which GUESSED a cycle from the posting
    month — defaulting to Summer for any yearless title. Measured against the
    live list, that guess was indefensible: of 60 roles carrying it, the
    posting text confirmed 0, said nothing for 43, and flatly contradicted it
    for the 3 that were checkable (Toshiba's postings open with "Fall 2026
    Internship" and were all filed under Summer 2027). A label that is never
    right when you can check it is not a label, so the guess is gone.

    What survives is the useful half: the RECENCY test. A recently-posted tech
    internship is worth showing even when nobody named its cycle — it just gets
    shown as `NOT_STATED` instead of wearing a fabricated one. Stale evergreen
    listings still fall off.
    """
    if states_explicit_year(title):
        # The title names a year and detect_season refused it — an explicit
        # OFF-cycle role ("Summer 2026 Intern"). It doesn't belong here.
        return False
    if not posted_at:
        return False  # no date -> can't establish recency
    try:
        posted = datetime.strptime(posted_at[:10], "%Y-%m-%d").replace(tzinfo=UTC)
    except ValueError:
        return False
    now = now or datetime.now(UTC)
    age_days = (now - posted).days
    return -1 <= age_days <= max_age_days  # -1 tolerates feed timezone skew


# --- season stated in posting TEXT (verifies date-inferred cycles) ------------
_TEXT_CYCLE_RE = re.compile(
    r"\b(?P<term_first>summer|fall|autumn|winter|spring)\b"
    r"(?P<gap_first>[^.!?;\n]{0,40}?)\b(?P<year_after>20\d\d)\b",
    re.IGNORECASE,
)
_TEXT_YEAR_CYCLE_RE = re.compile(
    r"\b(?P<year_before>20\d\d)\b(?P<gap_second>[^.!?;\n]{0,40}?)"
    r"\b(?P<term_after>summer|fall|autumn|winter|spring)\b"
    r"(?!\s+(?:of\s+)?20\d\d\b)",
    re.IGNORECASE,
)
_TEXT_SHARED_CYCLE_RE = re.compile(
    r"\b(summer|fall|autumn|winter|spring)\s*(?:/|&|and|or)\s*"
    r"(summer|fall|autumn|winter|spring)\s+(20\d\d)\b",
    re.IGNORECASE,
)
# "start date July 2026" / "June 8, 2027 through August 2027": a month+year is
# as good as a stated term once mapped through the calendar.
_TEXT_MONTH_RE = re.compile(
    r"\b(january|february|march|april|may|june|july|august|september|october|"
    r"november|december|jan|feb|mar|apr|jun|jul|aug|sept?|oct|nov|dec)\.?\s+"
    r"(?:\d{1,2}(?:st|nd|rd|th)?,?\s+)?(20\d\d)\b",
    re.I,
)
_MONTH_NUM = {
    "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3,
    "april": 4, "apr": 4, "may": 5, "june": 6, "jun": 6, "july": 7, "jul": 7,
    "august": 8, "aug": 8, "september": 9, "sept": 9, "sep": 9,
    "october": 10, "oct": 10, "november": 11, "nov": 11, "december": 12, "dec": 12,
}
_MONTH_TERM = {1: "Winter", 2: "Winter", 3: "Spring", 4: "Spring",
               5: "Summer", 6: "Summer", 7: "Summer", 8: "Summer",
               9: "Fall", 10: "Fall", 11: "Fall", 12: "Winter"}
_INTERNISH_RE = re.compile(
    r"\b(intern(?:ship)?s?|co[\s-]?op|start\s+date|program|term|semester)\b", re.I
)
# A date in these contexts describes the candidate or the company, not the
# internship cycle ("graduating in December 2027", "founded in November 2014").
# Same-sentence only: a period/!/?/; between the keyword and the date resets it.
_GRAD_WORD_RE = re.compile(
    r"\b(?:graduat\w*|class\s+of|commencement)\b", re.IGNORECASE
)
_GRAD_AFTER_RE = re.compile(
    r"^\s*(?:graduates?|graduation|class\b|commencement)\b", re.IGNORECASE
)
_GRAD_BEFORE_RE = re.compile(
    r"\b(?:graduat\w*|class\s+of|commencement)\b[^.!?;]{0,45}$",
    re.IGNORECASE,
)
_STUDENT_WINDOW_RE = re.compile(
    r"\b(?:degree|diploma|enroll\w*|students?|candidates?)\b[^.!?;]{0,80}"
    r"\b(?:between|from|through|until|by|completion)\b[^.!?;]{0,35}$",
    re.IGNORECASE,
)
_DEGREE_DATE_RE = re.compile(
    r"\b(?:degree|diploma)\b[^.!?;]{0,35}\b(?:in|by)\b[^.!?;]{0,20}$",
    re.IGNORECASE,
)
_COMPANY_DATE_RE = re.compile(
    r"\b(?:founded|established)(?:\s+(?:in|on))?\s*$", re.IGNORECASE
)


# "Expected program dates are September 14 – December 4, 2026": one program,
# two months. The START month names the cycle (a Sept–Dec program is a Fall
# program, not a Winter one), so a range is read from its first month and the
# year is taken from whichever end states it.
_TEXT_RANGE_RE = re.compile(
    r"\b(" + "|".join(_MONTH_NUM) + r")\.?\s*(?:\d{1,2}(?:st|nd|rd|th)?)?"
    r"\s*(?:-|–|—|to|through|thru|until)\s*"
    r"(" + "|".join(_MONTH_NUM) + r")\.?\s*(?:\d{1,2}(?:st|nd|rd|th)?)?,?\s*(20\d\d)",
    re.I,
)


def _non_cycle_context(text: str, match: re.Match) -> bool:
    """Whether a matched date describes a student/company, not the role."""
    sentence_start = max(
        text.rfind(".", 0, match.start()),
        text.rfind("!", 0, match.start()),
        text.rfind("?", 0, match.start()),
        text.rfind(";", 0, match.start()),
        text.rfind("\n", 0, match.start()),
    ) + 1
    ends = [
        pos
        for marker in ".!?;\n"
        if (pos := text.find(marker, match.end())) >= 0
    ]
    sentence_end = min(ends) if ends else len(text)
    left = text[sentence_start:match.start()]
    right = text[match.end():sentence_end]

    if _GRAD_WORD_RE.search(match.group(0)):
        return True
    if _GRAD_BEFORE_RE.search(left) or _GRAD_AFTER_RE.search(right):
        return True
    if _STUDENT_WINDOW_RE.search(left) or _DEGREE_DATE_RE.search(left):
        return True
    return bool(_COMPANY_DATE_RE.search(left))


def seasons_from_text(
    text: str, near: int = 90, now: datetime | None = None
) -> list[str]:
    """Every cycle established by the strongest posting-text evidence tier.

    Explicit terms outrank program ranges, which outrank lone month mentions.
    Multiple genuine term/year statements are preserved instead of being
    mistaken for a conflict.
    """
    if not text:
        return []
    now = now or datetime.now(UTC)
    year_lo, year_hi = now.year, now.year + 2

    def counted(match: re.Match, year: int) -> bool:
        if not (year_lo <= year <= year_hi):
            return False
        lo = max(0, match.start() - near)
        if not _INTERNISH_RE.search(text[lo:match.end() + near]):
            return False
        return not _non_cycle_context(text, match)

    def append_unique(labels: list[str], label: str) -> None:
        if label not in labels:
            labels.append(label)

    # Tier 1: the employer names a term and year, with a small grammatical gap.
    stated: list[str] = []
    for match in _TEXT_SHARED_CYCLE_RE.finditer(text):
        year_text = match.group(3)
        if not counted(match, int(year_text)):
            continue
        for raw_term in match.group(1), match.group(2):
            canonical = "Fall" if raw_term.lower() == "autumn" else raw_term.capitalize()
            append_unique(stated, f"{canonical} {year_text}")
    term_matches = list(_TEXT_CYCLE_RE.finditer(text))
    term_matches += list(_TEXT_YEAR_CYCLE_RE.finditer(text))
    for match in sorted(term_matches, key=lambda item: item.start()):
        groups = match.groupdict()
        term = groups.get("term_first") or groups.get("term_after")
        year_text = groups.get("year_after") or groups.get("year_before")
        gap = groups.get("gap_first") or groups.get("gap_second") or ""
        if _TERM_WORD_RE.search(gap):  # never pair across a second term
            continue
        canonical = "Fall" if term.lower() == "autumn" else term.capitalize()
        if counted(match, int(year_text)):
            append_unique(stated, f"{canonical} {year_text}")
    if stated:
        return stated

    # Tier 2: a program date range, keyed to the month it starts in.
    ranges: list[str] = []
    for match in _TEXT_RANGE_RE.finditer(text):
        term = _MONTH_TERM[_MONTH_NUM[match.group(1).lower().rstrip(".")]]
        year_text = match.group(3)
        if counted(match, int(year_text)):
            append_unique(ranges, f"{term} {year_text}")
    if ranges:
        return ranges

    # Tier 3: a bare month and year.
    months: list[str] = []
    for match in _TEXT_MONTH_RE.finditer(text):
        term = _MONTH_TERM[_MONTH_NUM[match.group(1).lower().rstrip(".")]]
        year_text = match.group(2)
        if counted(match, int(year_text)):
            append_unique(months, f"{term} {year_text}")
    return months


def season_from_text(
    text: str, near: int = 90, now: datetime | None = None
) -> str | None:
    """The sole cycle a posting's text establishes, otherwise ``None``."""
    labels = seasons_from_text(text, near=near, now=now)
    return labels[0] if len(labels) == 1 else None


# --- location: US / Canada detection -----------------------------------------
# Full state/province names are matched case-insensitively; the 2-letter codes
# are matched case-SENSITIVELY (uppercase) so "OR"/"IN" don't match the words
# "or"/"in" inside a city name.
_US_STATES = [
    "alabama", "alaska", "arizona", "arkansas", "california", "colorado",
    "connecticut", "delaware", "florida", "georgia", "hawaii", "idaho",
    "illinois", "indiana", "iowa", "kansas", "kentucky", "louisiana", "maine",
    "maryland", "massachusetts", "michigan", "minnesota", "mississippi",
    "missouri", "montana", "nebraska", "nevada", "new hampshire", "new jersey",
    "new mexico", "new york", "north carolina", "north dakota", "ohio",
    "oklahoma", "oregon", "pennsylvania", "rhode island", "south carolina",
    "south dakota", "tennessee", "texas", "utah", "vermont", "virginia",
    "washington", "west virginia", "wisconsin", "wyoming",
    "district of columbia",
]
_CA_PROVINCES = [
    "ontario", "quebec", "british columbia", "alberta", "manitoba",
    "saskatchewan", "nova scotia", "new brunswick", "newfoundland", "labrador",
    "prince edward island", "yukon", "northwest territories", "nunavut",
]
_US_CODES = [
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID",
    "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS",
    "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK",
    "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV",
    "WI", "WY", "DC", "US", "USA",
]
_CA_CODES = ["ON", "QC", "BC", "AB", "MB", "SK", "NS", "NB", "NL", "PE", "YT", "NT", "NU"]

# US country tokens. These MUST be matched as whole tokens, never as substrings:
# "usa" hides inside Lausanne, Jerusalem, Busan, Sausalito and dozens of other
# real ATS locations, and a substring test made every one of them read as the
# US. The lookarounds (rather than \b) are what let "U.S." keep its periods.
_US_COUNTRY_RE = re.compile(
    r"(?<![a-z0-9])(?:"
    r"united\s+states(?:\s+of\s+america)?"
    r"|u\.\s?s\.?\s?a\.?"
    r"|u\.\s?s\.?"
    r"|usa"
    r"|america"
    r")(?![a-z0-9])",
    re.IGNORECASE,
)
# "Latin America" / "South America" must not read as the US ("america" token).
_AMERICA_NOT_US_RE = re.compile(r"\b(?:south|latin|central)\s+america")

# Countries that appear in ATS location strings and must never read as US, even
# when a state-code lookalike sits next to them ("IN - Bangalore, India" is not
# Indiana). An explicit US token still wins for multi-country strings.
# NOTE on omissions: "georgia" is a US state as well as a country, and
# "england" hides inside "New England" — both are handled below rather than
# listed here, so a US location never loses to a name collision.
_NON_US_COUNTRIES = (
    "india", "united kingdom", "great britain", "scotland", "wales",
    "northern ireland", "ireland", "germany", "france", "poland",
    "netherlands", "spain", "italy", "portugal", "romania", "hungary",
    "bulgaria", "croatia", "serbia", "slovenia", "bosnia", "albania",
    "montenegro", "macedonia", "ukraine", "belarus", "russia", "moldova",
    "lithuania", "latvia", "estonia", "luxembourg", "iceland", "cyprus",
    "malta", "czech", "slovakia", "sweden", "switzerland", "belgium",
    "austria", "denmark", "norway", "finland", "greece", "turkey", "israel",
    "united arab emirates", "saudi arabia", "qatar", "kuwait", "bahrain",
    "oman", "jordan", "lebanon", "iraq", "iran", "afghanistan", "egypt",
    "morocco", "tunisia", "algeria", "nigeria", "ghana", "senegal",
    "ethiopia", "kenya", "tanzania", "uganda", "zimbabwe", "botswana",
    "namibia", "south africa", "brazil", "mexico", "argentina", "colombia",
    "chile", "peru", "bolivia", "paraguay", "uruguay", "venezuela",
    "ecuador", "panama", "costa rica", "guatemala", "honduras", "nicaragua",
    "el salvador", "belize", "dominican republic", "jamaica", "trinidad",
    "japan", "china", "singapore", "korea", "taiwan", "hong kong", "macau",
    "philippines", "indonesia", "vietnam", "thailand", "cambodia",
    "myanmar", "malaysia", "pakistan", "bangladesh", "sri lanka", "nepal",
    "mongolia", "kazakhstan", "uzbekistan", "azerbaijan", "armenia",
    "australia", "new zealand", "fiji",
)
_NON_US_RE = re.compile(
    r"\b(" + "|".join(re.escape(c) for c in _NON_US_COUNTRIES) + r")\b"
    # "England" is a foreign country only when it isn't "New England".
    r"|(?<!new\s)\bengland\b"
)

_US_NAME_RE = re.compile(
    r"\b(" + "|".join(re.escape(n) for n in _US_STATES) + r")\b", re.IGNORECASE
)
_CA_NAME_RE = re.compile(
    r"\b(" + "|".join(re.escape(n) for n in _CA_PROVINCES) + r")\b", re.IGNORECASE
)
# case-sensitive; (?!-) avoids matching country-style prefixes like "DE-Berlin"
# (Germany) as the US state code DE (Delaware).
_US_CODE_RE = re.compile(r"\b(" + "|".join(_US_CODES) + r")\b(?!-)")
_CA_CODE_RE = re.compile(r"\b(" + "|".join(_CA_CODES) + r")\b(?!-)")

_LOCATION_PART_RE = re.compile(r"[,;|]+")
_LOCATION_OPTION_RE = re.compile(r"[;|]+")
_GEORGIA_COUNTRY_CITIES = {
    "tbilisi", "batumi", "kutaisi", "rustavi", "gori", "zugdidi",
}


def _location_parts(location: str) -> list[str]:
    return [part.strip() for part in _LOCATION_PART_RE.split(location) if part.strip()]


def _structured_signal(
    parts: list[str], names: list[str], codes: list[str]
) -> tuple[int, str, str] | None:
    """Rightmost state/province component as ``(index, kind, value)``."""
    by_length = sorted(names, key=len, reverse=True)
    for index in range(len(parts) - 1, -1, -1):
        low = parts[index].lower().strip()
        for name in by_length:
            if re.fullmatch(
                rf"{re.escape(name)}(?:\s+(?:[-–—(]).*)?", low, re.IGNORECASE
            ) or re.search(
                rf"(?:^|\s[-–—]\s){re.escape(name)}$", low, re.IGNORECASE
            ):
                return index, "name", name
        for code in codes:
            # A structured component accepts lowercase ("Austin, tx"), but a
            # country-style prefix such as "DE-Berlin" deliberately does not.
            if re.fullmatch(
                rf"{re.escape(code)}(?:\s+(?:[-–—(]).*)?", parts[index], re.IGNORECASE
            ):
                return index, "code", code
    return None


def _matching_part_indexes(parts: list[str], pattern: re.Pattern) -> list[int]:
    return [index for index, part in enumerate(parts) if pattern.search(part.lower())]


def is_united_states(location: str) -> bool:
    if not location:
        return False
    # Several connectors preserve every advertised location by joining
    # alternatives with semicolons.  Evaluate each option independently:
    # otherwise a foreign country in the last option can veto a valid US
    # option (and reversing the employer's list changes the answer).
    options = [part.strip() for part in _LOCATION_OPTION_RE.split(location)
               if part.strip()]
    if len(options) > 1:
        return any(is_united_states(option) for option in options)
    low = location.lower()
    stripped = _AMERICA_NOT_US_RE.sub(" ", low)
    if _US_COUNTRY_RE.search(stripped):
        return True
    parts = _location_parts(location)
    us_signal = _structured_signal(parts, _US_STATES, _US_CODES)
    ca_signal = _structured_signal(parts, _CA_PROVINCES, _CA_CODES)
    foreign_indexes = _matching_part_indexes(parts, _NON_US_RE)
    canada_indexes = [
        index for index, part in enumerate(parts)
        if re.search(r"\bcanada\b", part, re.IGNORECASE)
    ]

    if us_signal:
        index, kind, value = us_signal
        # A named country to the right is an actual country qualifier:
        # "IN - Bangalore, India" and "CA - Sydney, Australia" are foreign.
        if any(country_index > index for country_index in foreign_indexes):
            return False
        if any(country_index > index for country_index in canada_indexes):
            return False
        if value == "georgia" and any(
            city in parts[0].lower() for city in _GEORGIA_COUNTRY_CITIES
        ):
            return False
        if kind == "code" and (ca_signal or canada_indexes):
            # "Milton, Ontario, CA" is Canada; a province outranks the
            # California-looking suffix. A full state name remains decisive,
            # so "Ontario, California" stays correctly American.
            # Ontario, California is commonly abbreviated "Ontario, CA".
            # It is a two-component US city/state location; the Canadian form
            # carries another city/province component ("Milton, Ontario, CA")
            # or an explicit Canada qualifier.
            if (
                value == "CA" and len(parts) == 2
                and parts[0].strip().casefold() == "ontario"
                and not canada_indexes
            ):
                return True
            return False
        return True

    if foreign_indexes:
        return False
    if _US_NAME_RE.search(low):
        return True
    if re.search(r"\b(?:canada|canadian)\b", low) or _CA_NAME_RE.search(low):
        return False
    if _US_CODE_RE.search(location):
        return True
    return False


def is_canada(location: str) -> bool:
    if not location:
        return False
    options = [part.strip() for part in _LOCATION_OPTION_RE.split(location)
               if part.strip()]
    if len(options) > 1:
        return any(is_canada(option) for option in options)
    if is_united_states(location):
        return False
    low = location.lower()
    if re.search(r"\b(?:canada|canadian)\b", low):
        return True
    if _CA_NAME_RE.search(low):
        return True
    if _CA_CODE_RE.search(location):
        return True
    return False


def is_us_or_canada(location: str) -> bool:
    return is_united_states(location) or is_canada(location)


def region_ok(location: str, want_us: bool, want_canada: bool) -> bool:
    """True if the location matches one of the wanted regions.

    Conservative: a bare "Remote" with no country mentioned matches nothing.
    """
    if want_us and is_united_states(location):
        return True
    if want_canada and is_canada(location):
        return True
    return False


# --- category tagging (first match wins; order = specific before generic) -----
_CATEGORY_PATTERNS = [
    (
        "Automotive & Mobility",
        re.compile(
            r"\b(automotive|vehicle|powertrain|drivetrain|chassis|suspension|"
            r"brake|braking|transmission|motorsport|motorsports|"
            r"electric vehicle|engine)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "Aerospace & Defense",
        re.compile(
            r"\b(aerospace|aeronautical|astronautical|propulsion|avionics|"
            r"flight test|spacecraft|launch vehicle|aerodynamic|aerodynamics|"
            r"turbomachinery)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "Robotics & Controls",
        re.compile(
            r"\b(robotic|robotics|mechatronic|mechatronics|controls engineer|"
            r"motion control|actuator|automation engineer)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "Manufacturing & Process",
        re.compile(
            r"\b(manufacturing|production engineer|production engineering|"
            r"process engineer|process engineering|industrial engineer|"
            r"industrial engineering|tooling|fixture|machining|cnc|"
            r"injection molding|additive manufacturing|3d printing|sheet metal|"
            r"welding|weldment|casting|forging|foundry|fabrication|"
            r"lean manufacturing|six sigma|plant engineer|facilities engineer|"
            r"maintenance engineer|assembly engineer)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "Energy & Power",
        re.compile(
            r"\b(renewable energy|solar|wind energy|wind turbine|nuclear|"
            r"power generation|energy engineer|energy engineering|"
            r"battery engineer|battery engineering)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "Thermal & Fluids",
        re.compile(
            r"\b(thermal|thermodynamic|thermodynamics|heat transfer|hvac|"
            r"refrigeration|cryogenic|cryogenics|fluid|fluids|hydraulic|"
            r"hydraulics|pneumatic|pneumatics|cfd|computational fluid|"
            r"combustion|turbine|piping|pressure vessel)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "Structures & Materials",
        re.compile(
            r"\b(structural|stress analysis|fea|finite element|durability|"
            r"fatigue|vibration|acoustics|materials|metallurgy|metallurgical|"
            r"composites|tribology|solid mechanics|applied mechanics)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "Test & Quality",
        re.compile(
            r"\b(test engineer|test engineering|validation engineer|"
            r"quality engineer|quality engineering|metrology|calibration|"
            r"inspection engineer|failure analysis|reliability engineer)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "Design & CAD",
        re.compile(
            r"\b(design engineer|design engineering|mechanical design|"
            r"machine design|product design|cad|drafting|drafter|"
            r"tolerance analysis|gd&t|mechanical)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "Biomedical",
        re.compile(
            r"\b(biomechanic|biomechanics|medical device|biomedical)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "General Engineering",
        re.compile(r"\b(engineer|engineering)\b", re.IGNORECASE),
    ),
]


def categorize(title: str) -> str:
    if not title:
        return "Other"
    for name, pattern in _CATEGORY_PATTERNS:
        if pattern.search(title):
            return name
    return "Other"
