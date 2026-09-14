"""Visa-sponsorship classification from real posting text (the F-1 edge).

Reference lists tag sponsorship by hand; we detect it from each job description.
The classifier is deliberately phrase-anchored (whole expressions employers
actually write), not keyword soup — a wrong "no sponsorship" flag steers someone
away from a real opportunity, so precision beats recall here.

Values (strictest wins):
  citizens-only   — U.S. citizenship / clearance / ITAR-style "U.S. persons" only
  no-sponsorship  — the employer says it will not sponsor a work visa
  offers          — the employer explicitly says it sponsors
  unknown         — the text says nothing conclusive (most postings)
"""

from __future__ import annotations

import re
from html import unescape

# Bump when the classification rules change. Stored per record; enrichment
# re-reads a posting whose stored verdict came from an older version, so
# classifier improvements propagate to the whole live list instead of only to
# roles discovered after the change.
VERSION = 4

# ITAR / export control and security clearances require citizenship (or at
# minimum a green card), which excludes F-1/OPT candidates the same way.
_CITIZENS_RE = re.compile(
    r"("
    r"(?:u\.?s\.?|united states)\s+citizen(?:ship)?\s+(?:is\s+)?(?:required|only|mandatory)"
    r"|must\s+be\s+(?:a\s+|an\s+)?(?:u\.?s\.?|united states)\s+citizen"
    r"|citizenship\s*:\s*(?:u\.?s\.?|united states|required)"
    r"|only\s+(?:u\.?s\.?|united states)\s+citizens"
    r"|(?:u\.?s\.?|united states)\s+citizens?\s+(?:or|and)\s+(?:lawful\s+)?(?:permanent\s+residents?|green\s?card)"
    r"|(?:subject\s+to|governed\s+by|must\s+(?:meet|comply\s+with))\s+itar\b"
    r"|\bitar\s+(?:requirements?|regulations?|restrictions?)\s+(?:apply|are\s+required)"
    r"|export.{0,20}(?:control|compliance).{0,60}u\.?s\.?\s+person"
    r"|u\.?s\.?\s+persons?\s+(?:status\s+)?(?:is\s+)?required"
    r"|(?:need|require|must\s+(?:have|hold|possess))[^.!?;]{0,40}"
    r"(?:security|government|ts/?sci|top[\s-]?secret|secret)\s+clearance"
    r"|(?:ability|eligible|required)\s+to\s+(?:obtain|maintain)[^.!?;]{0,25}"
    r"(?:security|government|ts/?sci|top[\s-]?secret|secret)\s+clearance"
    r"|(?:active|current|existing)\s+(?:security|government|ts/?sci|"
    r"top[\s-]?secret|secret)\s+clearance"
    r"|(?:security|government|ts/?sci|top[\s-]?secret|secret)\s+clearance\s+"
    r"(?:is\s+)?(?:required|mandatory)"
    r")",
    re.IGNORECASE,
)

_NO_SPONSOR_RE = re.compile(
    r"("
    r"(?:unable|not\s+able|not\s+available)\s+to\s+(?:sponsor|offer|provide|support)[^.]{0,60}?(?:sponsorship|visa|\.|,|;|$)"
    r"|(?:can\s*not|cannot|will\s+not|won'?t|do(?:es)?\s+not|don'?t)\s+(?:currently\s+|now\s+)?"
    r"(?:sponsor|offer\s+(?:visa\s+|immigration\s+|work[\s-]?visa\s+)?sponsorship|provide\s+(?:visa\s+|immigration\s+)?sponsorship)"
    r"|sponsorship\s+(?:is\s+)?(?:not|un)\s*(?:available|offered|provided|possible|supported)"
    r"|no\s+(?:visa|immigration|work[\s-]?visa|h-?1b)\s+sponsorship"
    r"|\bno\s+(?:(?:visa|immigration|work[\s-]?visa|h-?1b)\s+)?sponsorship\b"
    r"|\boffer(?:s|ed|ing)?\s+no\s+(?:visa\s+|immigration\s+)?sponsorship\b"
    r"|\bsponsorship\s*:\s*(?:none|no|not\s+available)\b"
    r"|\b(?:must|should)\s+not\s+require[^.!?;]{0,30}sponsorship\b"
    r"|\brequir(?:e|es|ing)[^.!?;]{0,25}(?:visa\s+)?sponsorship"
    r"[^.!?;]{0,40}(?:will\s+not|won'?t|cannot|can'?t)\s+be\s+considered\b"
    r"|not\s+eligible\s+for\s+(?:visa\s+|immigration\s+)?sponsorship"
    r"|without\s+(?:the\s+need\s+for\s+|requiring\s+|need\s+of\s+)?(?:visa\s+)?sponsorship"
    r"|without\s+(?:company\s+)?sponsorship\s+(?:now\s+or\s+in\s+the\s+future|at\s+any\s+time)?"
    r"|unable\s+to\s+sponsor"
    r"|does\s+not\s+sponsor"
    r"|not\s+(?:be\s+)?provid(?:e|ing)\s+(?:visa\s+|immigration\s+)?sponsorship"
    r")",
    re.IGNORECASE,
)

_OFFERS_RE = re.compile(
    r"("
    r"(?:visa|h-?1b|immigration|work[\s-]?visa)\s+sponsorship\s+(?:is\s+)?(?:available|offered|provided|possible)"
    r"|sponsorship\s+(?:is\s+|may\s+be\s+|can\s+be\s+)?(?:available|offered|provided)"
    r"|(?:will|can|do(?:es)?|happy\s+to|able\s+to)\s+(?:sponsor|provide\s+(?:visa\s+)?sponsorship|offer\s+(?:visa\s+)?sponsorship)"
    r"|open\s+to\s+sponsor"
    r"|we\s+sponsor\s+(?:work\s+)?visas"
    r")",
    re.IGNORECASE,
)

_NEGATION_BEFORE_RE = re.compile(
    r"\b(?:no|not|never|without|does\s+not|doesn'?t|is\s+not|isn'?t)\b"
    r"[^.!?;]{0,30}$",
    re.IGNORECASE,
)
_NEGATION_WITHIN_RE = re.compile(r"\b(?:no|not|never|without)\b", re.IGNORECASE)

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")

# Emoji used in the README / dashboard — same visual language readers already
# know from the big hand-curated lists.
FLAGS = {
    "citizens-only": "\U0001f1fa\U0001f1f8",   # 🇺🇸
    "no-sponsorship": "\U0001f6c2",            # 🛂
}


def strip_html(html: str | None) -> str:
    """Plain text from an HTML blob — good enough for phrase matching.

    Unescape FIRST, then strip tags, then unescape again. Order matters: some
    boards (Greenhouse) return entity-encoded markup — `&lt;p&gt;Fall 2026...`.
    Stripping first finds no `<` to match, and the later unescape then turns
    the entities back into live tags, so the "plain text" handed to the
    classifiers was still full of markup. Every downstream reader (season,
    skills, pay, sponsorship) was matching against angle brackets.
    """
    if not html:
        return ""
    text = html
    # A few boards double-encode fragments. Repeating this bounded pair turns
    # both ``&lt;p&gt;`` and ``&amp;lt;p&amp;gt;`` into prose without leaving live tags.
    for _ in range(3):
        previous = text
        text = _TAG_RE.sub(" ", unescape(text))
        if text == previous:
            break
    return _WS_RE.sub(" ", unescape(text)).strip()


def _has_affirmative(pattern: re.Pattern, text: str) -> bool:
    """True for a rule match that is not negated in its sentence."""
    for match in pattern.finditer(text):
        left = text[max(0, match.start() - 45):match.start()]
        if _NEGATION_BEFORE_RE.search(left):
            continue
        if _NEGATION_WITHIN_RE.search(match.group(0)):
            continue
        return True
    return False


def classify(text: str | None) -> str:
    """Classify one posting's text. Strictest verdict wins.

    citizens-only beats no-sponsorship (it also excludes green-card holders),
    and both beat an "offers" phrase elsewhere in the same posting.
    """
    if not text:
        return "unknown"
    plain = strip_html(text)
    if _has_affirmative(_CITIZENS_RE, plain):
        return "citizens-only"
    if _NO_SPONSOR_RE.search(plain):
        return "no-sponsorship"
    if _has_affirmative(_OFFERS_RE, plain):
        return "offers"
    return "unknown"


def flag(value: str | None) -> str:
    """The emoji shown next to a role title ('' when nothing to warn about)."""
    return FLAGS.get(value or "", "")
