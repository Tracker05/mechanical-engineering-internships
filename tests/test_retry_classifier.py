"""Which failed runs deserve an automatic retry.

Fixtures are REAL /jobs payloads captured from this repo on 2026-08-06:
  starved_runner  — the GitHub allocation failure (run 31126943349)
  real_failure    — the Thursday audit's TypeError crash (run 31096228265)
  successful_run  — a healthy publish (run 31108722998)

The first version of this gate lived inline in retry.yml and checked the RUN's
conclusion for 'cancelled'. GitHub reports the run as 'failure' and only the
starved JOB as 'cancelled', so it never fired during the very incident it was
written for. These tests exist so that can't happen silently again.
"""

from __future__ import annotations

import json
import pathlib

from tools.classify_failure import should_retry

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


def _load(name):
    with open(FIXTURES / name, encoding="utf-8") as f:
        return json.load(f)


class TestRealPayloads:
    def test_starved_runner_is_retried(self):
        retry, reason = should_retry(_load("starved_runner.json"))
        assert retry is True, reason

    def test_a_real_code_failure_is_not_retried(self):
        # The audit crashed with a TypeError. Retrying would just hide it.
        retry, reason = should_retry(_load("real_failure.json"))
        assert retry is False
        assert "concluded" in reason

    def test_a_successful_run_is_not_retried(self):
        retry, _ = should_retry(_load("successful_run.json"))
        assert retry is False


class TestEdgeCases:
    def test_empty_payload_is_not_retried(self):
        # No evidence is not evidence of starvation.
        assert should_retry({})[0] is False
        assert should_retry({"jobs": []})[0] is False
        assert should_retry([])[0] is False

    def test_a_job_that_ran_steps_is_not_retried(self):
        payload = {"jobs": [{"name": "update", "conclusion": "cancelled",
                             "runner_name": "", "steps": [{"name": "Checkout"}]}]}
        assert should_retry(payload)[0] is False

    def test_a_job_with_a_runner_is_not_retried(self):
        # A deliberate mid-run cancellation: a machine was assigned.
        payload = {"jobs": [{"name": "update", "conclusion": "cancelled",
                             "runner_name": "GitHub Actions 5", "steps": []}]}
        assert should_retry(payload)[0] is False

    def test_all_jobs_must_be_starved(self):
        payload = {"jobs": [
            {"name": "a", "conclusion": "cancelled", "runner_name": "", "steps": []},
            {"name": "b", "conclusion": "failure", "runner_name": "gh-1", "steps": [{}]},
        ]}
        assert should_retry(payload)[0] is False

    def test_multiple_starved_jobs_are_retried(self):
        payload = {"jobs": [
            {"name": "a", "conclusion": "cancelled", "runner_name": None, "steps": []},
            {"name": "b", "conclusion": "cancelled", "runner_name": "", "steps": []},
        ]}
        assert should_retry(payload)[0] is True

    def test_pages_skipped_dependents_do_not_hide_a_starved_build(self):
        retry, reason = should_retry({"jobs": [
            {"name": "build", "conclusion": "cancelled",
             "runner_name": "", "steps": []},
            {"name": "deploy", "conclusion": "skipped",
             "runner_name": "", "steps": []},
            {"name": "report-build-status", "conclusion": "skipped",
             "runner_name": "", "steps": []},
        ]})
        assert retry is True
        assert "1 job" in reason

    def test_all_skipped_jobs_are_not_enough_to_retry(self):
        retry, reason = should_retry({"jobs": [
            {"name": "deploy", "conclusion": "skipped", "steps": []},
        ]})
        assert retry is False
        assert reason == "all jobs were skipped"
