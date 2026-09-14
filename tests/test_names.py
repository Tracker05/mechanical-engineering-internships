"""Employer display names: fix known slug artifacts, never invent a company."""

import json

from intern_engine import names, paths


def _reset(monkeypatch, tmp_path, mapping):
    path = tmp_path / "company_names.json"
    path.write_text(json.dumps(mapping), encoding="utf-8")
    monkeypatch.setattr(paths, "COMPANY_NAMES_PATH", str(path))
    monkeypatch.setattr(names, "_overrides", None)


def test_dot_slug_artifact_becomes_a_real_domain(monkeypatch, tmp_path):
    _reset(monkeypatch, tmp_path, {})
    assert names.display("Pony Dot Ai") == "Pony.ai"
    assert names.display("Retool Dot Com") == "Retool.com"


def test_known_ats_account_number_is_fixed_only_by_override(monkeypatch, tmp_path):
    _reset(monkeypatch, tmp_path, {"charlesriveranalytics90": "Charles River Analytics"})
    assert names.display("Charlesriveranalytics90") == "Charles River Analytics"


def test_a_real_number_in_a_spaced_name_is_kept(monkeypatch, tmp_path):
    # "Studio 397" is the company's actual name — only unspaced slug-derived
    # names get the account-number treatment.
    _reset(monkeypatch, tmp_path, {})
    assert names.display("Studio 397") == "Studio 397"
    assert names.display("Section 32") == "Section 32"


def test_numeric_brands_are_preserved_even_without_spaces(monkeypatch, tmp_path):
    _reset(monkeypatch, tmp_path, {})
    for brand in ("blend360", "KnowBe4", "Point72", "Trading212"):
        assert names.display(brand) == brand


def test_override_by_slug_wins(monkeypatch, tmp_path):
    _reset(monkeypatch, tmp_path, {"beaconsoftware": "Beacon Software"})
    assert names.display("Beaconsoftware", "beaconsoftware") == "Beacon Software"


def test_override_by_name_when_slug_absent(monkeypatch, tmp_path):
    _reset(monkeypatch, tmp_path, {"beaconsoftware": "Beacon Software"})
    assert names.display("BeaconSoftware") == "Beacon Software"


def test_ordinary_names_are_left_alone(monkeypatch, tmp_path):
    _reset(monkeypatch, tmp_path, {})
    for raw in ("Stripe", "TransMarket Group", "iHerb", "SharkNinja",
                "Two Sigma", "AT&T", "Booz Allen Hamilton"):
        assert names.display(raw) == raw


def test_missing_override_file_is_not_fatal(monkeypatch, tmp_path):
    monkeypatch.setattr(paths, "COMPANY_NAMES_PATH", str(tmp_path / "nope.json"))
    monkeypatch.setattr(names, "_overrides", None)
    assert names.display("Stripe") == "Stripe"


def test_empty_name_passes_through(monkeypatch, tmp_path):
    _reset(monkeypatch, tmp_path, {})
    assert names.display("") == ""
