"""Skill-tag and pay extraction: precision-first, like the sponsorship tests."""

from intern_engine import skills


def test_extract_basic_stack():
    text = ("Requirements: strong SolidWorks and CATIA skills, experience with "
            "ANSYS or Abaqus, familiarity with GD&T and MATLAB. CNC machining "
            "exposure required.")
    got = skills.extract(text)
    assert "SolidWorks" in got
    assert "CATIA" in got
    assert "ANSYS" in got
    assert "Abaqus" in got
    assert "GD&T" in got
    assert "MATLAB" in got
    assert "CNC" in got


def test_extract_whole_words_only():
    # None of these mention a real skill: "go" the verb, "Spring 2027" the
    # season, "spark" the marketing verb, "javascript" absent.
    text = ("Go above and beyond in our Spring 2027 program. Spark your "
            "creativity! We cast a wide net and forge strong partnerships.")
    assert skills.extract(text) == []


def test_english_words_are_not_mistaken_for_stacks():
    # Real false positives from live postings: ordinary prose was tagging
    # roles with React/Rust/Swift/Angular. Names that are also English words
    # only match capitalized, which is how tech stacks are actually written.
    prose = (
        "You will be an inventor of new ideas, excel at teamwork, adams "
        "notwithstanding, and help us create lean, fluent communication. "
        "We go to market fast."
    )
    assert skills.extract(prose) == []


def test_capitalized_tool_names_still_match():
    # "Inventor", "Excel", and "Adams" are ordinary English words in prose, so
    # they only match capitalized — the way tool names are actually written.
    text = ("Experience with Autodesk Inventor, MSC Adams and Excel modeling.")
    found = skills.extract(text)
    for want in ("Inventor", "Adams", "Excel"):
        assert want in found, f"{want} missing from {found}"


def test_fea_and_cfd_acronyms_resolve():
    assert "FEA" in skills.extract("Hands-on FEA experience required.")
    assert "CFD" in skills.extract("You will run CFD studies on intake ducts.")
    got = skills.extract("Finite element and computational fluid dynamics work.")
    assert "FEA" in got and "CFD" in got


def test_extract_cap_and_order():
    text = ("SolidWorks CATIA Creo AutoCAD ANSYS Abaqus COMSOL MATLAB Simulink "
            "CNC welding")
    got = skills.extract(text)
    assert len(got) == skills.MAX_SKILLS
    assert got[0] == "SolidWorks"  # canonical order (CAD first), not text order  # canonical order, not text order


def test_extract_additional_common_skills():
    text = ("Support injection molding and sheet metal tooling, run Six Sigma "
            "and FMEA studies, and maintain drawings in Teamcenter.")
    found = skills.extract(text)
    for want in ("Injection Molding", "Sheet Metal", "Six Sigma", "FMEA", "Teamcenter"):
        assert want in found, f"{want} missing from {found}"


def test_title_mentioned_skill_ranks_first():
    found = skills.extract(
        "SolidWorks, ANSYS, and MATLAB are required.", "ANSYS Simulation Intern"
    )
    assert found[0] == "ANSYS"


def test_extract_empty():
    assert skills.extract(None) == []
    assert skills.extract("") == []


def test_pay_hourly_range():
    assert skills.extract_pay("The pay range is $41.50 - $55 per hour.") == "$41.5–$55/hr"


def test_pay_hourly_single():
    assert skills.extract_pay("Interns earn $45/hr plus housing.") == "$45/hr"


def test_pay_annual_range():
    text = "Base salary: $120,000 - $140,000 per year depending on level."
    assert skills.extract_pay(text) == "$120k–$140k/yr"


def test_pay_hourly_beats_annual():
    text = "Pay is $50/hour ($104,000 annualized)."
    assert skills.extract_pay(text) == "$50/hr"


def test_pay_rejects_nonsense():
    # No period marker, out-of-range values, or bare dollar figures: no pay.
    assert skills.extract_pay("We raised $5,000,000 last year.") is None
    assert skills.extract_pay("A $5 gift card per hour of user testing") is None
    assert skills.extract_pay("Millions of dollars in impact") is None
    assert skills.extract_pay(None) is None


def test_pay_scans_past_invalid_candidates():
    assert skills.extract_pay(
        "$10 per hour; actual intern base pay is $45 per hour."
    ) == "$45/hr"
    assert skills.extract_pay(
        "Typo $80-$40/hr. Correct range: $40-$50/hr."
    ) == "$40\u2013$50/hr"
    assert skills.extract_pay(
        "$999/hr placeholder; actual intern pay is $45/hr."
    ) == "$45/hr"
    assert skills.extract_pay(
        "$600,000 per year executive compensation; intern salary is $80,000/year."
    ) == "$80k/yr"
