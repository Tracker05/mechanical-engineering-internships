"""Decide whether a failed workflow run deserves an automatic retry.

Lives here rather than inline in YAML for one reason: it has to be testable.
The first version of this check was written as a shell condition inside
retry.yml, gated on `github.event.workflow_run.conclusion == 'cancelled'`, and
it never fired once. GitHub reports the RUN as `failure` while the starved JOB
inside it reports `cancelled` — a distinction no one notices until the thing
silently does nothing during the exact incident it was written for.

A run is retryable only when it never actually executed:

  - at least one job exists (an empty payload proves nothing)
  - every non-skipped job concluded `cancelled`
  - no job ran a single step
  - no job was ever assigned a runner

That combination is the signature of GitHub failing to hand out a machine. A
run that executed steps and failed is a REAL failure — a red publish gate, a
push that never landed — and retrying it would only hide the problem.

Usage:  python tools/classify_failure.py <jobs.json>   # exit 0 = retry
"""

from __future__ import annotations

import json
import sys


def should_retry(jobs_payload: dict) -> tuple[bool, str]:
    """(retry?, human-readable reason) for a run's /jobs API response."""
    jobs = jobs_payload.get("jobs") if isinstance(jobs_payload, dict) else None
    if not isinstance(jobs, list) or not jobs:
        return False, "no job data in payload"

    # Pages has dependent deploy/report jobs that GitHub marks skipped when
    # its build job never acquires a runner. Ignore those while still requiring
    # at least one actual starved job.
    candidates = [job for job in jobs if job.get("conclusion") != "skipped"]
    if not candidates:
        return False, "all jobs were skipped"

    for job in candidates:
        if job.get("conclusion") != "cancelled":
            return False, f"job {job.get('name')!r} concluded {job.get('conclusion')!r}"
        if len(job.get("steps") or []) > 0:
            return False, f"job {job.get('name')!r} executed steps"
        if (job.get("runner_name") or "").strip():
            return False, f"job {job.get('name')!r} had runner {job.get('runner_name')!r}"

    return True, (
        f"{len(candidates)} job(s) cancelled with no steps and no runner"
    )


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: classify_failure.py <jobs.json>", file=sys.stderr)
        sys.exit(2)
    with open(sys.argv[1], encoding="utf-8") as f:
        payload = json.load(f)
    retry, reason = should_retry(payload)
    print(f"{'RETRY' if retry else 'NO RETRY'}: {reason}")
    sys.exit(0 if retry else 1)


if __name__ == "__main__":
    main()
