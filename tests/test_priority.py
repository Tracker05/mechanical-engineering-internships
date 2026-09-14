from intern_engine import priority


def test_exact_curated_names_and_safe_aliases_rank():
    assert priority.rank("Stripe, Inc.") == priority.rank("stripe")
    assert priority.rank("JPMorgan Chase & Co.") == priority.rank("jpmorgan")
    assert priority.rank("Meta Platforms, Inc.") == priority.rank("meta")
    assert priority.rank("Circle Internet Financial") == priority.rank("circle")


def test_unrelated_companies_do_not_borrow_a_brand_rank():
    for company in (
        "Circle K",
        "Funding Circle",
        "Cohere Health",
        "Kraken Robotics",
        "Sentry Insurance",
        "Apple Bank",
    ):
        assert priority.rank(company) == priority.UNRANKED, company
