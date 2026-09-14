import pytest

from intern_engine import config, paths


def test_missing_config_uses_validated_safe_defaults(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "CONFIG_PATH", str(tmp_path / "missing.json"))
    cfg = config.load_config()
    assert cfg["regions"] == ["US"]
    assert cfg["role_scope"] == "mechanical"
    assert cfg["default_cycle"] in cfg["cycles"]


def test_malformed_existing_config_is_fatal(tmp_path, monkeypatch):
    path = tmp_path / "config.json"
    path.write_text('{"regions":', encoding="utf-8")
    monkeypatch.setattr(paths, "CONFIG_PATH", str(path))
    with pytest.raises(config.ConfigError, match="unreadable"):
        config.load_config()


@pytest.mark.parametrize(
    "raw, message",
    [
        ({"regions": []}, "regions must contain"),
        ({"regions": ["Mars"]}, "unsupported regions"),
        ({"cycles": ["2027 Summer"]}, "cycles must use labels"),
        ({"default_cycle": "Spring 2030"}, "default_cycle"),
        ({"include_international": "yes"}, "true or false"),
        ({"max_age_days": True}, "must be an integer"),
    ],
)
def test_scope_configuration_rejects_unsafe_shapes(raw, message):
    with pytest.raises(config.ConfigError, match=message):
        config.validate_config(raw)


def test_empty_regions_fail_closed_even_for_unvalidated_callers():
    assert config.restrict_region({"regions": []}) is True

