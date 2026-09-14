import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from intern_engine import paths  # noqa: E402

# Every path a generator writes to. Anything added here is automatically
# sandboxed for the whole suite.
_WRITABLE = (
    "README_PATH", "CSV_PATH", "STATS_PATH", "HISTORY_PATH", "JOBS_PATH",
    "HEALTH_PATH", "MAIL_STATE_PATH", "OUTBOX_PATH", "OBSERVED_PATH",
    "DOCS_DIR", "API_DIR", "DASHBOARD_PATH", "FEED_PATH", "RADAR_ICS_PATH",
)


@pytest.fixture(autouse=True)
def _sandbox_outputs(tmp_path, monkeypatch):
    """Point every output path at a temp dir, for every test.

    A test once redirected README_PATH and CSV_PATH but not DOCS_DIR, so
    running the suite overwrote the real published docs/internships.csv with a
    fixture full of "Acme" rows — a green test run silently corrupting a live
    artifact. Opt-in sandboxing is the wrong default: this makes writing
    outside tmp_path impossible unless a test deliberately un-patches a path.

    Read-only inputs (config, companies, h1b, blocklist) are untouched — tests
    legitimately read the real ones.
    """
    out = tmp_path / "out"
    (out / "api").mkdir(parents=True, exist_ok=True)
    for name in _WRITABLE:
        original = getattr(paths, name, None)
        if original is None:
            continue
        if name == "DOCS_DIR":
            monkeypatch.setattr(paths, name, str(out))
        elif name == "API_DIR":
            monkeypatch.setattr(paths, name, str(out / "api"))
        else:
            monkeypatch.setattr(paths, name, str(out / os.path.basename(original)))
