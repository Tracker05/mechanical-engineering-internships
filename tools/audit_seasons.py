"""Audit date-inferred cycles against each posting's own text.

For every OPEN role whose cycle was inferred from its posting date, fetch the
posting text (list payload where the ATS ships it, detail endpoint otherwise)
and compare with the cycle the text states, if any:

  CONFIRMED  text states the cycle we inferred      -> un-mark (it's stated now)
  MOVED      text states another tracked cycle      -> rebucket + un-mark
  OFF-CYCLE  text states a cycle we don't track     -> close + record the verdict
             (deleting would let the role re-enter via inference next run;
             a kept off-cycle label is sticky-dropped by the pipeline instead)
  NO-SIGNAL  text states nothing explicit           -> keep the inference + ~

Read-only by default; --apply rewrites data/jobs.json. The engine performs this
same check for every NEW role at first enrichment (see enrich.py) and stored
seasons are sticky (see pipeline._keep_matching), so one audit pass brings the
backlog in line and it stays in line.

    python tools/audit_seasons.py           # report only
    python tools/audit_seasons.py --apply   # report + repair the store
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from dataclasses import dataclass

import httpx

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from intern_engine import config, enrich, filters, models, paths, sponsorship, store  # noqa: E402
from intern_engine.models import Job  # noqa: E402
from intern_engine.net import HostLimiter, Net  # noqa: E402
from intern_engine.pipeline import CONNECTORS, USER_AGENT  # noqa: E402

_MIN_FETCH_COVERAGE = 0.80


@dataclass(frozen=True)
class TextResult:
    """Outcome of obtaining posting text; absence is never overloaded."""

    status: str  # OK | NO-TEXT | FETCH-FAILED
    text: str = ""
    error: str = ""


def _record_to_job(record: dict) -> Job:
    return Job(
        id=record["id"], source=record.get("source", ""),
        company=record.get("company", ""), company_slug=record.get("company_slug", ""),
        title=record.get("title", ""), location=record.get("location", ""),
        url=record.get("url", ""), posted_at=record.get("posted_at"),
    )


async def _texts_for(jobs: list[Job], companies: list[dict]) -> dict[str, TextResult]:
    """Job id -> typed retrieval result, never an ambiguous missing string."""
    by_key = {(c["ats"], c["slug"]): c for c in companies}
    texts: dict[str, TextResult] = {}
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(20.0, connect=10.0),
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
    ) as client:
        net = Net(client, HostLimiter(8))
        list_sourced: dict[tuple[str, str], list[Job]] = {}
        for job in jobs:
            fetcher = enrich._FETCHERS.get(job.source)  # noqa: SLF001 — same package's tool
            if fetcher is not None:
                try:
                    text = await fetcher(job, net) or ""
                    texts[job.id] = TextResult("OK" if text.strip() else "NO-TEXT", text)
                except Exception as exc:  # noqa: BLE001 — audit one role, not none
                    print(f"  (fetch failed: {job.company} — {type(exc).__name__})")
                    texts[job.id] = TextResult(
                        "FETCH-FAILED", error=type(exc).__name__
                    )
            else:
                list_sourced.setdefault((job.source, job.company_slug), []).append(job)

        for key, wanted in list_sourced.items():
            company = by_key.get(key)
            if company is None:
                for job in wanted:
                    texts[job.id] = TextResult("FETCH-FAILED", error="company-not-found")
                continue
            try:
                # Connectors return a Fetch (jobs + whether the snapshot was
                # complete); Fetch.of also accepts the bare list older ones
                # returned, so this reads either shape.
                fetched = models.Fetch.of(await CONNECTORS[key[0]](company, net))
            except Exception as exc:  # noqa: BLE001
                print(f"  (list fetch failed: {key[1]} — {type(exc).__name__})")
                for job in wanted:
                    texts[job.id] = TextResult(
                        "FETCH-FAILED", error=type(exc).__name__
                    )
                continue
            descriptions = {j.id: j.description or "" for j in fetched.jobs}
            for job in wanted:
                text = descriptions.get(job.id, "")
                texts[job.id] = TextResult("OK" if text.strip() else "NO-TEXT", text)
    for job in jobs:
        texts.setdefault(job.id, TextResult("FETCH-FAILED", error="no-result"))
    return texts


def main() -> None:
    apply_fixes = "--apply" in sys.argv
    cfg = config.load_config()
    cycles = config.cycles(cfg)

    data = store.load(paths.JOBS_PATH)
    inferred = [r for r in data.values() if r.get("is_open") and r.get("season_inferred")]
    with open(paths.COMPANIES_PATH, encoding="utf-8") as f:
        companies = json.load(f)
    print(f"Auditing {len(inferred)} open inferred roles against posting text…")

    jobs = [_record_to_job(r) for r in inferred]
    texts = asyncio.run(_texts_for(jobs, companies))

    verdicts: dict[str, list] = {
        "CONFIRMED": [], "MOVED": [], "OFF-CYCLE": [],
        "NO-SIGNAL": [], "NO-TEXT": [], "FETCH-FAILED": [],
    }
    for record in inferred:
        result = texts[record["id"]]
        if result.status == "FETCH-FAILED":
            verdicts["FETCH-FAILED"].append((record, result.error or None))
            continue
        if result.status == "NO-TEXT":
            verdicts["NO-TEXT"].append((record, None))
            continue
        text = sponsorship.strip_html(result.text)
        stated = filters.seasons_from_text(text)
        if not stated:
            verdicts["NO-SIGNAL"].append((record, None))
        elif record.get("season") in stated:
            verdicts["CONFIRMED"].append((record, stated))
        elif stated[0] in cycles:
            verdicts["MOVED"].append((record, stated))
        else:
            verdicts["OFF-CYCLE"].append((record, stated))

    fetch_ok = len(inferred) - len(verdicts["FETCH-FAILED"])
    coverage = fetch_ok / len(inferred) if inferred else 1.0

    for verdict, rows in verdicts.items():
        print(f"\n{verdict} ({len(rows)})")
        for record, stated in rows:
            was = record.get("season")
            labels = ", ".join(stated) if isinstance(stated, list) else stated
            note = f"{was} -> {labels}" if labels and was not in (stated or []) \
                else (labels or was)
            print(f"  {record.get('company','')[:26]:<26} | {note:<26} | "
                  f"{record.get('title','')[:56]}")

    print(f"\nFetch coverage: {fetch_ok}/{len(inferred)} ({coverage:.1%})")
    if coverage < _MIN_FETCH_COVERAGE:
        print(f"Audit aborted: coverage is below {_MIN_FETCH_COVERAGE:.0%}; "
              "failed retrievals are not season evidence.")
        raise SystemExit(2)

    if not apply_fixes:
        print("\nDry run — pass --apply to repair the store.")
        return

    ts = store.now_iso()
    for record, stated in verdicts["CONFIRMED"]:
        rec = data[record["id"]]
        primary = rec.get("season") if rec.get("season") in stated else stated[0]
        rec.update(season=primary, seasons=stated, season_inferred=False,
                   season_audited_at=ts, season_audit_verdict="confirmed")
    for record, stated in verdicts["MOVED"]:
        data[record["id"]].update(
            season=stated[0], seasons=stated, season_inferred=False,
            season_audited_at=ts, season_audit_verdict="moved",
        )
    for record, stated in verdicts["OFF-CYCLE"]:
        rec = data[record["id"]]
        rec.update(season=stated[0], seasons=stated, season_inferred=False,
                   is_open=False, closed_at=ts, closed_reason="out-of-scope",
                   enriched_at=ts, season_audited_at=ts,
                   season_audit_verdict="off-cycle")
    store.save(paths.JOBS_PATH, data)
    print(f"\nApplied: {len(verdicts['CONFIRMED'])} confirmed, "
          f"{len(verdicts['MOVED'])} moved, {len(verdicts['OFF-CYCLE'])} closed off-cycle. "
          f"Store saved.")


if __name__ == "__main__":
    main()
