"""H-1B employer matching: precision-first, so most tests are about NOT matching."""

from intern_engine import h1b


def _index(employers):
    return {"fiscal_years": [2022, 2023], "employers": employers}


# --- name normalization -------------------------------------------------------

def test_normalize_strips_legal_suffixes():
    assert h1b.normalize("PALANTIR TECHNOLOGIES INC") == "palantir technologies"
    assert h1b.normalize("Google LLC") == "google"
    assert h1b.normalize("Stripe, Inc.") == "stripe"
    assert h1b.normalize("JPMORGAN CHASE & CO") == "jpmorgan chase"


def test_normalize_takes_dba_brand():
    assert h1b.normalize("0965688 BC LTD DBA PROCOGIA") == "procogia"


def test_normalize_keeps_identity_words():
    # "technologies"/"labs" are identity, not boilerplate — never stripped.
    assert h1b.normalize("Datadog Technologies") == "datadog technologies"


# --- matching -----------------------------------------------------------------

def test_exact_match():
    idx = _index({"nvidia": 851})
    assert h1b.approvals_for("NVIDIA Corp", idx) == 851


def test_alias_match():
    idx = _index({"meta platforms": 4510})
    assert h1b.approvals_for("Meta", idx) == 4510


def test_uncurated_multi_token_prefix_abstains():
    idx = _index({"jpmorgan chase bank": 900, "jpmorgan chase services": 100})
    assert h1b.approvals_for("JPMorgan Chase", idx) is None


def test_curated_alias_can_use_a_single_token_family():
    # A reviewed brand alias may resolve a family; guessed brands may not.
    idx = _index({"google fiber": 7, "google public sector": 9})
    assert h1b.approvals_for("Google", idx) == 9


def test_single_token_prefix_rejects_wide_ambiguity():
    # Four unrelated "Figure ..." companies -> refuse to guess.
    idx = _index({
        "figure ai": 5, "figure eight": 8, "figure markets": 3, "figure lending": 11,
    })
    assert h1b.approvals_for("Figure", idx) is None


def test_generic_and_short_names_never_prefix_match():
    idx = _index({"data systems international": 500, "gm financial": 40})
    assert h1b.approvals_for("Data", idx) is None
    assert h1b.approvals_for("GM!", idx) is None  # too short after cleanup, alias missed
    assert h1b.approvals_for("", idx) is None


def test_no_match_returns_none():
    assert h1b.approvals_for("Anduril", _index({"nvidia": 851})) is None


def test_ambiguous_single_token_brands_never_borrow_an_unrelated_employer():
    idx = _index({
        "abridge ai": 2,
        "abridge info systems": 25,
        "harvey mudd college": 4,
        "harvey nash": 39,
        "leland stanford jr university": 784,
        "brilliant earth": 2,
        "brilliant infotech": 16,
        "foundation medicine": 53,
        "harbor hat": 17,
        "inspire medical systems": 2,
        "inspire resources": 27,
    })
    assert h1b.approvals_for("Abridge", idx) == 2  # curated legal identity
    assert h1b.approvals_for("Inspire", idx) == 2  # curated legal identity
    for company in ("Harvey", "Leland", "Brilliant", "Foundation", "Harbor"):
        assert h1b.approvals_for(company, idx) is None, company


def test_empty_index_returns_none():
    assert h1b.approvals_for("Google", {"employers": {}}) is None


# --- presentation -------------------------------------------------------------

def test_badge_threshold():
    assert h1b.badge(h1b.BADGE_THRESHOLD) == "✓"
    assert h1b.badge(h1b.BADGE_THRESHOLD - 1) == ""
    assert h1b.badge(None) == ""


def test_pretty_count():
    assert h1b.pretty_count(43) == "43"
    assert h1b.pretty_count(1234) == "1.2k"
    assert h1b.pretty_count(6000) == "6k"


class TestBrandToLegalEntity:
    """Real brand->petitioner gaps found by auditing the live company list.

    Each expected number was read out of the committed index, so a change in
    matching that breaks one of these is a measurable regression, not taste.
    """

    def test_brand_resolves_to_its_petitioning_entity(self):
        # We show "Bosch"; USCIS files under "Robert Bosch". Before the alias
        # the prefix only found sub-10 subsidiaries and the badge vanished.
        assert h1b.approvals_for("Bosch") == 188
        assert h1b.approvals_for("Jump Trading") == 57
        assert h1b.approvals_for("IMC Trading") == 13

    def test_alias_can_cover_a_whole_subsidiary_family(self):
        # Magna files under ten "Magna ..." entities; the single-token cap of
        # three (which protects guessed matches) was rejecting all of them.
        assert h1b.approvals_for("Magna International") == 141

    def test_a_city_name_never_borrows_another_employers_record(self):
        # "Chicago Trading Company" normalizes toward "chicago", which would
        # otherwise prefix-match Chicago Mercantile Exchange's 92 approvals.
        assert not h1b.badge(h1b.approvals_for("Chicago Trading Company"))

    def test_absent_from_the_index_stays_absent(self):
        # Defense/clearance employers genuinely aren't in FY2022-23 data. No
        # badge is the correct answer; inventing one would be the bug.
        for name in ("Northrop Grumman", "Anduril", "Beacon Software"):
            assert not h1b.badge(h1b.approvals_for(name)), name

    def test_untrusted_single_token_keeps_its_narrow_cap(self):
        # The `trusted` widening must apply to curated aliases only.
        assert h1b._prefix_match("magna", h1b.load()["employers"]) is None
