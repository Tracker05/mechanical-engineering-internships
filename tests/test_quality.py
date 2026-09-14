import json

import pytest

from intern_engine import paths, quality


def _point_at(monkeypatch, tmp_path, value):
    path = tmp_path / "blocklist.json"
    if isinstance(value, str):
        path.write_text(value, encoding="utf-8")
    else:
        path.write_text(json.dumps(value), encoding="utf-8")
    monkeypatch.setattr(paths, "BLOCKLIST_PATH", str(path))


def test_load_blocklist_normalizes_valid_entries(monkeypatch, tmp_path):
    _point_at(monkeypatch, tmp_path, {
        "companies": [" Acme Staffing ", "EXAMPLE"],
        "name_contains": [" Recruiting ", "Agency"],
    })
    assert quality.load_blocklist() == {
        "companies": {"acme staffing", "example"},
        "name_contains": ["recruiting", "agency"],
    }


@pytest.mark.parametrize("value", [
    "{truncated",
    [],
    {"companies": "Acme"},
    {"name_contains": [""]},
    {"companies": [7]},
])
def test_load_blocklist_rejects_corrupt_or_unsafe_schema(
    monkeypatch, tmp_path, value
):
    _point_at(monkeypatch, tmp_path, value)
    with pytest.raises(quality.BlocklistError):
        quality.load_blocklist()


def test_missing_blocklist_fails_closed(monkeypatch, tmp_path):
    monkeypatch.setattr(paths, "BLOCKLIST_PATH", str(tmp_path / "missing.json"))
    with pytest.raises(quality.BlocklistError):
        quality.load_blocklist()


def test_empty_substring_can_never_block_every_company():
    assert not quality.is_blocked("Acme", {"companies": set(), "name_contains": [""]})
