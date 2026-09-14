import json

import pytest

from intern_engine import registry


def _workday(site="Campus"):
    return {
        "name": f"Acme {site}",
        "ats": "workday",
        "slug": "acme",
        "site": site,
        "wd": "wd5",
    }


def test_multi_site_boards_have_independent_lifecycle_keys():
    campus = _workday("Campus")
    professionals = _workday("Professionals")
    assert registry.board_key(campus) == "workday:acme:campus"
    assert registry.board_key(professionals) == "workday:acme:professionals"
    assert len(registry.validate([campus, professionals])) == 2


def test_smartrecruiters_case_variants_are_duplicate_boards():
    companies = [
        {"name": "Canva", "ats": "smartrecruiters", "slug": "Canva"},
        {"name": "Canva", "ats": "smartrecruiters", "slug": "canva"},
    ]
    with pytest.raises(registry.RegistryCorrupt, match="duplicate board"):
        registry.validate(companies)


@pytest.mark.parametrize(
    "company, message",
    [
        ({"name": "Acme", "ats": "workday", "slug": "acme", "wd": "wd5"},
         "requires site"),
        ({"name": "Acme", "ats": "oracle", "slug": "acme", "host": "h"},
         "requires site"),
        ({"name": "Acme", "ats": "mystery", "slug": "acme"},
         "unsupported ATS"),
    ],
)
def test_required_board_identity_fields_are_enforced(company, message):
    with pytest.raises(registry.RegistryCorrupt, match=message):
        registry.validate([company])


def test_malformed_existing_registry_is_fatal(tmp_path):
    path = tmp_path / "companies.json"
    path.write_text('{"truncated":', encoding="utf-8")
    with pytest.raises(registry.RegistryCorrupt, match="unreadable"):
        registry.load(str(path))


def test_registry_save_is_atomic_and_validated(tmp_path):
    path = tmp_path / "data" / "companies.json"
    registry.save([_workday()], str(path))
    assert registry.load(str(path)) == [_workday()]
    assert not path.with_suffix(".json.tmp").exists()
    assert json.loads(path.read_text(encoding="utf-8"))[0]["site"] == "Campus"


def test_migrates_legacy_store_keys_for_site_and_case_normalization():
    companies = [
        {"name": "Acme", "slug": "acme", "ats": "workday",
         "wd": "acme", "site": "External"},
        {"name": "Bosch", "slug": "BoschGroup", "ats": "smartrecruiters"},
        {"name": "Oracle Co", "slug": "oracle-co", "ats": "oracle",
         "host": "example.oraclecloud.com", "site": "Campus"},
    ]
    records = {
        "wd": {"source": "workday", "company_slug": "acme"},
        "sr": {"source": "smartrecruiters", "company_slug": "BoschGroup"},
        "or": {"source": "oracle", "company_slug": "oracle-co",
               "board_key": "oracle:oracle-co"},
    }

    assert registry.migrate_store_board_keys(records, companies) == 3
    assert records["wd"]["board_key"] == "workday:acme:external"
    assert records["sr"]["board_key"] == "smartrecruiters:boschgroup"
    assert records["or"]["board_key"] == "oracle:oracle-co:campus"


def test_ambiguous_site_migration_stays_protected_until_attributed():
    companies = [_workday("Campus"), _workday("Professionals")]
    records = {"old": {
        "source": "workday", "company_slug": "acme",
        "board_key": "workday:acme",
    }}

    assert registry.migrate_store_board_keys(records, companies) == 0
    assert records["old"]["board_key"] == "workday:acme"
