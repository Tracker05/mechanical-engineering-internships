from datetime import UTC, datetime

from intern_engine import filters, sponsorship

CYCLES = ["Summer 2027", "Fall 2026"]


class TestInternship:
    def test_matches_intern(self):
        assert filters.is_internship("Software Engineer Intern")
        assert filters.is_internship("Data Co-op")

    def test_rejects_substring_false_positive(self):
        # "internal" / "international" must not count as internships
        assert not filters.is_internship("Internal Tools Engineer")
        assert not filters.is_internship("International Operations")

    def test_rejects_senior(self):
        assert not filters.is_internship("Senior Software Intern")

    def test_cooperative_education_is_a_coop_program(self):
        assert filters.is_internship("Cooperative Education Software Developer")


class TestMechanical:
    def test_keeps_core_mechanical(self):
        assert filters.is_mechanical("Mechanical Engineering Intern")
        assert filters.is_mechanical("Mechanical Design Engineer Intern")
        assert filters.is_mechanical("Manufacturing Engineering Co-op")

    def test_drops_software_and_non_technical(self):
        assert not filters.is_mechanical("Software Engineer Intern")
        assert not filters.is_mechanical("Machine Learning Intern")
        assert not filters.is_mechanical("Technical Recruiting Intern")

    def test_drops_phd(self):
        assert not filters.is_mechanical("PhD Mechanical Engineering Intern")

    def test_drops_other_engineering_disciplines(self):
        # Adjacent majors are their own lists.
        assert not filters.is_mechanical("Electrical Engineering Intern")
        assert not filters.is_mechanical("Chemical Engineering Co-op")
        assert not filters.is_mechanical("Civil Engineering Internship")

    def test_verified_mechanical_role_families_are_kept(self):
        for title in (
            "Thermal Engineering Intern",
            "HVAC Design Intern",
            "Vehicle Dynamics Intern",
            "Powertrain Calibration Intern",
            "Propulsion Engineering Intern",
            "CFD Engineering Intern",
            "Stress Analysis Engineering Intern",
            "Robotics Engineering Intern",
            "Mechatronics Co-op",
            "Quality Engineering Intern",
            "Metallurgical Engineering Co-op",
            "Additive Manufacturing Intern",
            "Tooling Engineer Intern",
        ):
            assert filters.is_mechanical(title), title

    def test_mechanical_first_titles_survive_a_software_mention(self):
        # A mechanical identity outranks an incidental software word, the way
        # the upstream list let "Embedded Software / Hardware Intern" through.
        assert filters.is_mechanical(
            "Mechanical Engineering Intern - Simulation Software"
        )
        assert filters.is_mechanical(
            "Engineering Intern (Electrical / Mechanical / GNC / Software)"
        )
        assert not filters.is_mechanical(
            "Robotics - Software Development Engineer Intern"
        )

    def test_generic_engineering_titles_are_configurable(self):
        # A discipline-free "Engineering Intern" is in by default, out when
        # include_general_engineering is false.
        assert filters.is_mechanical("Engineering Intern")
        assert not filters.is_mechanical("Engineering Intern", include_general=False)
        # ...but a named mechanical discipline is kept either way.
        assert filters.is_mechanical(
            "Mechanical Engineering Intern", include_general=False
        )

    def test_is_tech_alias_still_resolves(self):
        assert filters.is_tech is filters.is_mechanical


class TestSeason:
    def test_explicit_cycle(self):
        assert filters.detect_season("SWE Intern, Summer 2027", CYCLES) == "Summer 2027"
        assert filters.detect_season("Fall 2026 Data Intern", CYCLES) == "Fall 2026"

    def test_year_only_maps_to_cycle(self):
        assert filters.detect_season("2027 Software Engineer Intern", CYCLES) == "Summer 2027"

    def test_undated_is_dropped(self):
        assert filters.detect_season("Software Engineer Intern", CYCLES) is None

    def test_off_cycle_is_dropped(self):
        assert filters.detect_season("Summer 2026 Intern", CYCLES) is None
        assert filters.detect_season("Fall 2027 Intern", CYCLES) is None

    def test_apostrophe_short_year(self):
        assert filters.detect_season("SWE Intern - Summer '27", CYCLES) == "Summer 2027"
        assert filters.detect_season("Fall '26 Data Intern", CYCLES) == "Fall 2026"

    def test_graduation_year_in_title_is_not_a_cycle(self):
        # "Class of 2027" names the student, not the internship term.
        assert filters.detect_season("Software Intern (Class of 2027)", CYCLES) is None
        assert filters.detect_season("SWE Intern - Graduating 2027", CYCLES) is None

    def test_stated_cycle_wins_over_graduation_year(self):
        assert filters.detect_season(
            "Summer 2027 SWE Intern (Class of 2028)", CYCLES
        ) == "Summer 2027"

    def test_is_cycle_label(self):
        assert filters.is_cycle_label("Summer 2026")
        assert filters.is_cycle_label("Fall 2027")
        assert not filters.is_cycle_label("Unspecified")
        assert not filters.is_cycle_label("")
        assert not filters.is_cycle_label(None)

    def test_multiple_bare_years_do_not_invent_a_cycle(self):
        assert filters.detect_season(
            "Quant Developer / Quant Research Intern - 2026/2027", CYCLES
        ) is None
        assert filters.detect_season(
            "2026-2027 Information Technology - Software Engineer - Intern", CYCLES
        ) is None

    def test_title_month_and_range_use_the_start_month(self):
        cycles = ("Winter 2027", "Summer 2026", "Fall 2026", "Summer 2027")
        assert filters.detect_season(
            "Intern - Web Developer (Start in January 2027)", cycles
        ) == "Winter 2027"
        assert filters.detect_season(
            "Software Engineering Internship (July - Dec 2026)", cycles
        ) == "Summer 2026"

    def test_month_evidence_prevents_bare_year_fallback(self):
        assert filters.detect_season(
            "Intern - Web Developer (Start in January 2027)", CYCLES
        ) is None
        assert filters.detect_season(
            "Software Engineering Internship (July - Dec 2026)", CYCLES
        ) is None

    def test_term_words_are_matched_as_words(self):
        assert filters.detect_season(
            "2027 Software Intern - Springfield Platform", ("Summer 2027",)
        ) == "Summer 2027"

    def test_more_graduation_title_variants_are_not_cycles(self):
        assert filters.detect_season(
            "Software Intern - Class Year 2027", CYCLES
        ) is None
        assert filters.detect_season(
            "Software Intern - Expected Graduation May 2027", CYCLES
        ) is None

    def test_two_terms_can_share_one_year_without_losing_the_tracked_cycle(self):
        title = "Software Engineering Intern [Fall/Winter 2026]"
        assert filters.detect_seasons(title, CYCLES) == ["Fall 2026"]
        assert filters.detect_season(title, CYCLES) == "Fall 2026"


class TestRegion:
    def test_us_match(self):
        assert filters.region_ok("San Francisco, CA", want_us=True, want_canada=False)
        assert filters.region_ok("New York, United States", want_us=True, want_canada=False)

    def test_canada_excluded_when_us_only(self):
        assert not filters.region_ok("Toronto, Ontario, Canada", want_us=True, want_canada=False)
        assert filters.region_ok("Toronto, Ontario, Canada", want_us=False, want_canada=True)

    def test_country_code_prefix_not_us(self):
        # "DE-Berlin" is Germany, not the Delaware state code
        assert not filters.region_ok("DE-Berlin-Trion", want_us=True, want_canada=False)

    def test_named_foreign_country_beats_state_code_lookalike(self):
        # "IN - Bangalore, India" is India, not Indiana
        assert not filters.is_united_states("IN - Bangalore, India")
        assert not filters.is_united_states("Munich, Germany")
        assert not filters.is_united_states("CA - Sydney, Australia")

    def test_explicit_us_token_wins_for_multi_country_strings(self):
        assert filters.is_united_states("New York, USA; Bangalore, India")

    def test_multi_location_order_never_hides_a_valid_us_option(self):
        forward = "Austin, TX; London, United Kingdom"
        reverse = "London, United Kingdom; Austin, TX"
        assert filters.is_united_states(forward)
        assert filters.is_united_states(reverse)
        assert filters.region_ok(forward, want_us=True, want_canada=False)

    def test_state_code_with_spaced_suffix_still_us(self):
        assert filters.is_united_states("Dallas, TX - Headquarters")

    def test_other_americas_are_not_us(self):
        assert not filters.is_united_states("Remote - Latin America")
        assert not filters.is_united_states("South America")
        # "North America" remains US-eligible (US-inclusive remote regions).
        assert filters.is_united_states("Remote (North America)")

    def test_canada_vetoes_state_code_lookalike(self):
        # The Magna leak: "Milton, Ontario, CA" read the trailing CA as
        # California. A province name / "Canada" beats a bare state code…
        assert not filters.is_united_states("Milton, Ontario, CA")
        assert not filters.is_united_states("Toronto, ON, Canada")
        # …but a full US state name still wins ("Ontario, California" is a
        # real US city), and explicit US tokens are untouched.
        assert filters.is_united_states("Ontario, California")
        assert filters.is_united_states("Ontario, CA")
        assert filters.is_united_states("Ontario, California, United States")

    def test_city_names_containing_usa_are_not_us(self):
        # The Medtronic leak: "usa" was matched as a SUBSTRING, so every city
        # spelling those three letters in a row read as the United States and
        # foreign roles landed in a US-only list.
        assert not filters.is_united_states("Lausanne, Vaud, Switzerland")
        assert not filters.is_united_states("Jerusalem, Israel")
        assert not filters.is_united_states("Busan, South Korea")
        assert not filters.is_united_states("Syracuse, Sicily, Italy")
        # …while the same letters as a real token still count, and a US city
        # that merely contains them keeps its state code.
        assert filters.is_united_states("Sausalito, CA")
        assert filters.is_united_states("Syracuse, New York")

    def test_us_country_token_spellings(self):
        for loc in ("United States", "United States of America", "USA",
                    "U.S.A.", "U.S.", "Remote - US", "New York, NY, USA"):
            assert filters.is_united_states(loc), loc

    def test_more_foreign_countries_are_excluded(self):
        for loc in ("London, England", "Edinburgh, Scotland", "Kyiv, Ukraine",
                    "Vilnius, Lithuania", "Zagreb, Croatia", "Amman, Jordan",
                    "Quito, Ecuador", "Kathmandu, Nepal"):
            assert not filters.is_united_states(loc), loc

    def test_new_england_is_not_read_as_foreign(self):
        # "England" hides inside "New England" — a US region.
        assert filters.is_united_states("Cambridge, MA (New England)")

    def test_foreign_country_names_can_be_us_city_components(self):
        for loc in (
            "Lebanon, NH",
            "Lebanon, New Hampshire",
            "Mexico, MO",
            "Poland, OH",
            "Peru, IN",
            "Panama City, FL",
            "China, ME",
            "India, TX",
            "Canadian, TX",
        ):
            assert filters.is_united_states(loc), loc
            assert not filters.is_canada(loc), loc

    def test_georgia_country_needs_us_corroboration(self):
        assert not filters.is_united_states("Tbilisi, Georgia")
        assert filters.is_united_states("Atlanta, Georgia")
        assert filters.is_united_states("Tbilisi, Georgia, USA")

    def test_structured_state_codes_are_case_insensitive(self):
        assert filters.is_united_states("Austin, tx")
        assert filters.is_united_states("San Francisco, ca")


class TestMultiCycle:
    """One requisition can genuinely hire for two cycles."""

    CYCLES = ("Summer 2027", "Fall 2026")

    def test_both_stated_cycles_are_returned(self):
        # The Deepgram case: stored as Summer 2027 only, so the Fall 2026
        # section never showed a role that literally says Fall 2026.
        title = "Software Engineering Internship (Fall 2026/Summer 2027)"
        assert filters.detect_seasons(title, self.CYCLES) == [
            "Summer 2027", "Fall 2026",
        ]

    def test_single_cycle_returns_one(self):
        assert filters.detect_seasons(
            "SWE Intern, Summer 2027", self.CYCLES) == ["Summer 2027"]

    def test_untracked_cycles_are_not_returned(self):
        assert filters.detect_seasons("Intern, Spring 2028", self.CYCLES) == []

    def test_yearless_title_returns_nothing(self):
        # detect_seasons never infers — that's infer_season's job.
        assert filters.detect_seasons("Software Engineer Intern", self.CYCLES) == []

    def test_tracked_cycle_survives_an_untracked_neighbour(self):
        # "Fall 2026 / Summer 2028": the year scan found {2026, 2028} and the
        # term scan picked Summer, so nothing matched and a title literally
        # stating a tracked cycle was dropped as off-cycle.
        assert filters.detect_season(
            "Fall 2026 / Summer 2028 Software Intern", self.CYCLES) == "Fall 2026"



class TestProgramType:
    def test_coop_titles(self):
        for title in ("Software Co-op", "Engineering CO-OP (Fall)",
                      "Data Coop Student"):
            assert filters.program_type(title) == "Co-op", title

    def test_internship_titles(self):
        for title in ("Software Engineer Intern", "SWE Internship Summer 2027"):
            assert filters.program_type(title) == "Internship", title

    def test_titles_offering_both_are_labelled_both(self):
        # Real titles: filing these under one label hid them from students
        # filtering for the other, even though the employer offers either.
        for title in ("Software Engineer Intern/Co-Op - Fall 2026",
                      "Robotics - Software Development Engineer Intern/Co-op",
                      "Backend Co op Intern"):
            assert filters.program_type(title) == "Internship / Co-op", title

    def test_cooperative_is_not_a_coop(self):
        # "Cooperative" the adjective must not read as the co-op program type.
        assert filters.program_type("Cooperative Robotics Intern") == "Internship"


class TestRemote:
    def test_remote_locations(self):
        for loc in ("Remote", "Remote - US", "Austin, TX (Remote)", "US Remote"):
            assert filters.is_remote(loc), loc

    def test_onsite_locations(self):
        for loc in ("New York, NY", "Austin, TX", "", "Seattle, Washington"):
            assert not filters.is_remote(loc), loc

    def test_remote_sensing_is_a_field_of_study_not_a_work_mode(self):
        assert not filters.is_remote("Pasadena, CA", "Remote Sensing Software Intern")
        assert filters.is_remote("Pasadena, CA", "Software Intern (Remote)")


class TestCategory:
    def test_categories(self):
        assert filters.categorize("Powertrain Engineering Intern") == "Automotive & Mobility"
        assert filters.categorize("Propulsion Intern") == "Aerospace & Defense"
        assert filters.categorize("Manufacturing Engineering Intern") == "Manufacturing & Process"
        assert filters.categorize("HVAC Design Intern") == "Thermal & Fluids"
        assert filters.categorize("Mechanical Design Engineer Intern") == "Design & CAD"
        assert filters.categorize("Engineering Intern") == "General Engineering"


class TestCycleUnstatedOk:
    """Recency gate for roles nobody stated a cycle for.

    This replaced `infer_season`, which guessed a cycle (defaulting to Summer)
    from the posting month. Measured against the live list that guess was
    confirmed by the posting text 0 times out of 60 and contradicted every
    time it was checkable, so the guess is gone. Only the recency test — the
    part that was actually sound — remains.
    """

    NOW = datetime(2026, 7, 15, tzinfo=UTC)

    def _ok(self, title, posted, **kw):
        return filters.cycle_unstated_ok(title, posted, now=self.NOW, **kw)

    def test_recent_yearless_role_is_kept(self):
        assert self._ok("Software Engineer Intern", "2026-07-10")

    def test_term_word_alone_does_not_invent_a_cycle(self):
        # "Summer Intern" names a term but no year. It used to become
        # "Summer 2027"; now it is simply kept as cycle-unstated.
        assert self._ok("Summer Intern - Backend", "2026-07-01")
        assert self._ok("Fall Software Intern", "2026-07-01")

    def test_stale_posting_is_dropped(self):
        # 60 days old with a 45-day trust window -> evergreen sludge.
        assert not self._ok("Software Engineer Intern", "2026-05-01")

    def test_wider_window_accepts_older(self):
        assert self._ok("Software Engineer Intern", "2026-05-01", max_age_days=90)

    def test_no_posted_date_is_dropped(self):
        assert not self._ok("Software Engineer Intern", None)

    def test_explicit_offcycle_year_is_refused(self):
        # "Summer 2026 Intern" was refused by detect_season for a reason — it
        # must not sneak back in through the unstated lane.
        assert not self._ok("Summer 2026 Intern: Cyber Security", "2026-07-10")
        assert not self._ok("Fall 2027 Software Intern", "2026-07-10")

    def test_explicit_year_never_reaches_this_gate(self):
        # Belt and suspenders: detect_season handles dated titles first.
        assert filters.detect_season("Software Intern Summer 2027", CYCLES) == "Summer 2027"

    def test_not_stated_is_not_a_cycle_label(self):
        # Anything treating it as a cycle would re-introduce the fake claim.
        assert not filters.is_cycle_label(filters.NOT_STATED)
        assert filters.NOT_STATED not in CYCLES


class TestMechanicalScopeExclusions:
    def test_non_technical_roles_with_engineering_bait_excluded(self):
        assert not filters.is_mechanical("Digital Marketer Intern - Engineering Team")
        assert not filters.is_mechanical("Account Management Intern, Automotive")
        assert not filters.is_mechanical("Unpaid Engineering Intern")

    def test_real_mechanical_titles_still_pass(self):
        assert filters.is_mechanical("Design Engineer Intern")
        assert filters.is_mechanical("Test Engineer Intern, Durability")


class TestSeasonFromText:
    NOW = datetime(2026, 7, 15, tzinfo=UTC)

    def _stated(self, text, **kw):
        return filters.season_from_text(text, now=self.NOW, **kw)

    def test_stated_coop_term(self):
        assert self._stated(
            "Join our Fall 2026 co-op program in Boston."
        ) == "Fall 2026"

    def test_summer_of_phrasing_and_autumn_alias(self):
        assert self._stated(
            "an internship in the summer of 2027 at our NYC office"
        ) == "Summer 2027"
        assert self._stated(
            "This internship runs autumn 2026 through December."
        ) == "Fall 2026"

    def test_conflicting_mentions_never_override(self):
        # Grad-window boilerplate lists several terms -> no verdict.
        assert self._stated(
            "Internship candidates enrolled between Fall 2026 and Summer 2027 "
            "are encouraged to apply."
        ) is None

    def test_far_away_mention_ignored(self):
        pad = "x " * 200
        assert self._stated(
            f"Our company was named a best employer of Summer 2026. {pad} "
            "This internship is fully remote."
        ) is None

    def test_empty_text(self):
        assert self._stated("") is None

    # --- month+year mentions (mapped through the calendar) -------------------

    def test_start_date_month_maps_to_term(self):
        # The Doctors Without Borders case: "start date July 2026" is Summer
        # 2026, no matter what the posting date suggested.
        assert self._stated(
            "ESTIMATED START DATE: Anticipated start date for July 2026. "
            "DURATION: 6 months."
        ) == "Summer 2026"

    def test_month_with_day_and_range(self):
        assert self._stated(
            "The internship runs June 8, 2027 through August 2027 in Austin."
        ) == "Summer 2027"

    def test_graduation_month_is_not_a_cycle(self):
        # The Fortive case: a graduation window must never bucket the role.
        assert self._stated(
            "Currently pursuing a BS in Computer Science. Graduating "
            "December 2026 or later. Strong understanding of networks."
        ) is None

    def test_company_history_dates_ignored(self):
        # The Nio case: "Founded in November 2014" is company history — killed
        # by both the plausible-year window and the context guard.
        assert self._stated(
            "Founded in November 2014, our internship program pairs you with "
            "senior researchers."
        ) is None

    def test_grad_window_term_mentions_are_guarded(self):
        # The Palantir case: "graduating in Winter 2027 or Spring 2028" is the
        # candidate's timeline, not the internship cycle.
        assert self._stated(
            "Must be planning on graduating in Winter 2027 or Spring 2028. "
            "This should be your final internship before graduating."
        ) is None

    def test_degree_window_month_mentions_are_guarded(self):
        # The Datasite case: a degree window phrased with months.
        assert self._stated(
            "Bachelor's degree in CS, Engineering or Data Science preferrably "
            "between May and August 2026. This is a 10-12 week internship."
        ) is None

    def test_implausible_year_ignored(self):
        assert self._stated(
            "Our internship program has run every summer since May 2019."
        ) is None

    def test_unrelated_degree_or_company_words_do_not_veto_a_real_cycle(self):
        for text, expected in (
            (
                "Students pursuing a degree can join our Summer 2027 internship.",
                "Summer 2027",
            ),
            (
                "Founded in 2010, Acme is hiring for its Summer 2027 internship program.",
                "Summer 2027",
            ),
            (
                "Established in Boston, our Fall 2026 internship starts soon.",
                "Fall 2026",
            ),
        ):
            assert self._stated(text) == expected

    def test_cycle_before_graduation_word_is_still_not_a_cycle(self):
        assert self._stated(
            "Fall 2026 graduates may apply for this internship."
        ) is None
        assert self._stated(
            "December 2026 graduates are eligible for this internship."
        ) is None

    def test_term_and_year_can_surround_internship_words(self):
        assert self._stated(
            "This is a Summer internship for 2027."
        ) == "Summer 2027"
        assert self._stated(
            "Our Fall internship program for 2026 is accepting applications."
        ) == "Fall 2026"

    def test_multiple_real_text_cycles_are_returned_without_guessing_one(self):
        text = "This internship is open for Fall 2026 and Summer 2027."
        assert filters.seasons_from_text(text, now=self.NOW) == [
            "Fall 2026", "Summer 2027"
        ]
        assert self._stated(text) is None

    def test_text_terms_can_share_one_year(self):
        text = "This Fall/Winter 2026 internship supports two start dates."
        assert filters.seasons_from_text(text, now=self.NOW) == [
            "Fall 2026", "Winter 2026"
        ]
        assert self._stated(text) is None


class TestSeasonEvidencePriority:
    """Stated terms outrank month arithmetic (the Toshiba regression).

    Toshiba's postings open with "Fall 2026 Internship:" and later give
    "Expected program dates are September 14 - December 4, 2026". December
    maps to Winter, so the old flat resolver saw {Fall 2026, Winter 2026},
    called it a disagreement, returned None — and all three roles sat under a
    date-inferred "Summer 2027" instead of the Fall 2026 the employer wrote
    in their first line.
    """

    NOW = datetime(2026, 7, 15, tzinfo=UTC)

    def _stated(self, text):
        return filters.season_from_text(text, now=self.NOW)

    TOSHIBA = ("Fall 2026 Internship: This position is located at our HQ in "
               "Durham, NC. Expected program dates are September 14 - "
               "December 4, 2026. Anticipated working hours will be 20-30 "
               "per week for this internship.")

    def test_stated_term_beats_a_conflicting_month(self):
        assert self._stated(self.TOSHIBA) == "Fall 2026"

    def test_date_range_reads_from_its_start_month(self):
        # No stated term: a Sept-Dec program is a Fall program, not a Winter
        # one. Reading the END month was what poisoned the set above.
        text = ("Internship program dates: September 8 - December 12, 2026. "
                "Apply early.")
        assert self._stated(text) == "Fall 2026"

    def test_lone_month_still_works_when_nothing_is_stated(self):
        assert self._stated("This internship starts in June 2027.") == "Summer 2027"

    def test_genuinely_conflicting_stated_terms_still_abstain(self):
        # Two different stated cycles = real ambiguity; abstain rather than
        # pick one. (Multi-cycle titles are handled by detect_seasons.)
        text = ("Summer 2027 internship. We also run a Winter 2027 internship "
                "program on the same team.")
        assert self._stated(text) is None

    def test_no_internship_context_is_ignored(self):
        assert self._stated("The company was founded in Fall 2026.") is None


class TestStripHtmlOrdering:
    """Entity-encoded markup has to be decoded before tags can be stripped.

    Greenhouse returns `&lt;p&gt;Fall 2026...`. Stripping tags first found no
    `<` to match, and the later unescape turned the entities back into live
    tags — so every classifier downstream (season, skills, pay, sponsorship)
    was reading angle brackets as if they were prose.
    """

    def test_entity_encoded_markup_is_stripped(self):
        raw = "&lt;p&gt;&lt;strong&gt;Fall 2026 Internship:&lt;/strong&gt;Durham, NC.&lt;/p&gt;"
        out = sponsorship.strip_html(raw)
        assert "<" not in out and ">" not in out
        assert out.startswith("Fall 2026 Internship:")

    def test_plain_markup_is_still_stripped(self):
        out = sponsorship.strip_html("<p><b>Summer 2027</b> internship</p>")
        assert out == "Summer 2027 internship"

    def test_season_survives_the_round_trip(self):
        raw = ("&lt;p&gt;&lt;strong&gt;Fall 2026 Internship:&lt;/strong&gt; "
               "Expected program dates are September 14 - December 4, 2026.&lt;/p&gt;")
        text = sponsorship.strip_html(raw)
        assert filters.season_from_text(
            text, now=datetime(2026, 7, 15, tzinfo=UTC)) == "Fall 2026"


class TestDetectSeasonsProximity:
    """Multi-cycle detection must match detect_season's reading of a title."""

    C = ("Summer 2027", "Fall 2026")

    def test_term_and_year_need_not_be_adjacent(self):
        # Regression: an earlier version matched "<Term> <Year>" verbatim, so
        # Five Rings' real "Summer Intern 2027 - Software Developer" came back
        # empty even though detect_season read it correctly.
        assert filters.detect_seasons(
            "Summer Intern 2027 - Software Developer", self.C) == ["Summer 2027"]

    def test_a_split_dual_cycle_title_keeps_both_halves(self):
        assert filters.detect_seasons(
            "Intern, Summer 2027 / Fall Intern 2026", self.C
        ) == ["Summer 2027", "Fall 2026"]

    def test_closest_term_wins_so_pairs_do_not_cross(self):
        assert filters.detect_seasons(
            "Internship (Fall 2026/Summer 2027)", self.C
        ) == ["Summer 2027", "Fall 2026"]

    def test_one_term_governs_a_bare_year(self):
        assert filters.detect_seasons("2027 Summer Internship", self.C) == ["Summer 2027"]

    def test_a_bare_year_with_no_term_states_nothing(self):
        # detect_season may still bucket it; detect_seasons reports only what
        # the title actually SAYS, and "2027 Intern" names no term.
        assert filters.detect_seasons("2027 Software Engineer Intern", self.C) == []

    def test_graduation_years_are_not_cycles(self):
        assert filters.detect_seasons("SWE Intern, Class of 2027", self.C) == []

    def test_untracked_cycles_are_excluded(self):
        for t in ("Summer 2026 Intern", "Fall 2027 Intern"):
            assert filters.detect_seasons(t, self.C) == [], t
