"""USCIS index builds validate before replacing the live artifact."""

from __future__ import annotations

import json
import sys

import pytest

import tools.build_h1b as build_h1b

HEADER = "Employer,Fiscal Year,Initial Approval,Continuing Approval\n"


def test_header_only_export_cannot_overwrite_live_index(monkeypatch, tmp_path):
    source = tmp_path / "empty.csv"
    source.write_text(HEADER, encoding="utf-8")
    target = tmp_path / "h1b.json"
    target.write_text('{"known":"good"}', encoding="utf-8")
    monkeypatch.setattr(build_h1b.paths, "H1B_PATH", str(target))
    monkeypatch.setattr(sys, "argv", ["build_h1b.py", str(source)])
    with pytest.raises(ValueError, match="no data rows"):
        build_h1b.main()
    assert target.read_text(encoding="utf-8") == '{"known":"good"}'


def test_valid_export_is_atomically_replaced(monkeypatch, tmp_path):
    source = tmp_path / "valid.csv"
    source.write_text(HEADER + "Acme,2025,2,3\n", encoding="utf-8")
    target = tmp_path / "h1b.json"
    target.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(build_h1b.paths, "H1B_PATH", str(target))
    monkeypatch.setattr(sys, "argv", ["build_h1b.py", str(source)])
    build_h1b.main()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["fiscal_years"] == [2025]
    assert payload["employers"]["acme"] == 5
    assert not (tmp_path / "h1b.json.tmp").exists()
