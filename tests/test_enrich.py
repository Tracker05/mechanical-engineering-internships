"""Enrichment behavior: free descriptions classify inline, stored verdicts are
carried over without refetching, and detail fetches backfill what they can."""

import asyncio

from intern_engine import enrich, sponsorship
from intern_engine.models import Job


class FakeNet:
    def __init__(self, payload):
        self.payload = payload
        self.calls = 0

    async def get_json(self, url, **kwargs):
        self.calls += 1
        return self.payload

    async def post_json(self, url, **kwargs):
        self.calls += 1
        return self.payload


def _job(jid="lever:acme:1", source="lever", description=None, url="https://x", slug="acme"):
    return Job(id=jid, source=source, company="Acme", company_slug=slug,
               title="SWE Intern", location="NY", url=url, description=description)


def _run(coro):
    return asyncio.run(coro)


class TestEnrich:
    def test_inline_description_classifies_without_fetch(self):
        net = FakeNet({})
        job = _job(description="We are unable to sponsor visas for this role.")
        enriched, fetched = _run(enrich.enrich_jobs([job], {}, net))
        assert job.sponsorship == "no-sponsorship"
        assert enriched == {job.id}
        assert fetched == 0 and net.calls == 0

    def test_stored_verdict_carried_over_no_refetch(self):
        net = FakeNet({})
        job = _job(jid="greenhouse:acme:9", source="greenhouse")
        existing = {"greenhouse:acme:9": {
            "sponsorship": "citizens-only", "enriched_at": "x", "skills": ["Python"],
            "classifier_v": sponsorship.VERSION,
        }}
        enriched, fetched = _run(enrich.enrich_jobs([job], existing, net))
        assert job.sponsorship == "citizens-only"
        assert enriched == set() and net.calls == 0

    def test_fresh_inline_description_replaces_stale_stored_evidence(self):
        net = FakeNet({})
        job = _job(description="We cannot sponsor work visas. Python required.")
        existing = {job.id: {
            "sponsorship": "offers", "enriched_at": "x", "skills": ["Rust"],
            "classifier_v": sponsorship.VERSION,
        }}
        enriched, fetched = _run(enrich.enrich_jobs([job], existing, net))
        assert job.sponsorship == "no-sponsorship"
        assert job.skills == ["Python"]
        assert enriched == {job.id}
        assert fetched == 0 and net.calls == 0

    def test_settled_record_without_skills_backfills_from_fresh_evidence(self):
        # Records that predate skill tags get one fresh fetch. Its current text
        # is also the best available sponsorship evidence and must not be frozen.
        net = FakeNet({"content": "Uses Python daily. Visa sponsorship is available."})
        job = _job(jid="greenhouse:acme:9", source="greenhouse")
        existing = {"greenhouse:acme:9": {
            "sponsorship": "citizens-only", "enriched_at": "x",
            "classifier_v": sponsorship.VERSION,
        }}
        enriched, fetched = _run(enrich.enrich_jobs([job], existing, net))
        assert job.sponsorship == "offers"
        assert job.skills == ["Python"]
        assert enriched == {job.id} and fetched == 1

    def test_stale_classifier_version_forces_reclassification(self):
        # A record classified by an OLDER ruleset is re-read once, so classifier
        # improvements reach the whole live list — not just roles found after
        # the change. Without this, enrichment was one-time and permanent.
        net = FakeNet({"content": "Visa sponsorship is available for this role."})
        job = _job(jid="greenhouse:acme:9", source="greenhouse")
        existing = {"greenhouse:acme:9": {
            "sponsorship": "unknown", "enriched_at": "x", "skills": [],
            "classifier_v": sponsorship.VERSION - 1,
        }}
        enriched, fetched = _run(enrich.enrich_jobs([job], existing, net))
        assert job.sponsorship == "offers"   # re-derived under the new rules
        assert enriched == {job.id} and fetched == 1

    def test_record_with_no_classifier_version_is_reclassified(self):
        net = FakeNet({"content": "Visa sponsorship is available for this role."})
        job = _job(jid="greenhouse:acme:9", source="greenhouse")
        existing = {"greenhouse:acme:9": {
            "sponsorship": "unknown", "enriched_at": "x", "skills": [],
        }}
        enriched, fetched = _run(enrich.enrich_jobs([job], existing, net))
        assert job.sponsorship == "offers"
        assert fetched == 1

    def test_empty_detail_response_is_retried_not_settled(self):
        # A 200 whose body has no text is absence of evidence. Stamping it
        # enriched_at froze an "unknown" verdict forever off an empty page.
        net = FakeNet({"content": ""})
        job = _job(jid="greenhouse:acme:9", source="greenhouse")
        enriched, fetched = _run(enrich.enrich_jobs([job], {}, net))
        assert enriched == set()   # no stamp -> retried next run
        assert fetched == 1

    def test_greenhouse_detail_fetch(self):
        net = FakeNet({"content": "U.S. citizenship is required for this position."})
        job = _job(jid="greenhouse:acme:42", source="greenhouse")
        enriched, fetched = _run(enrich.enrich_jobs([job], {}, net))
        assert job.sponsorship == "citizens-only"
        assert enriched == {job.id} and fetched == 1

    def test_workday_detail_backfills_posted_date(self):
        net = FakeNet({"jobPostingInfo": {
            "jobDescription": "No visa sponsorship for this role.",
            "startDate": "2026-06-20",
        }})
        job = _job(
            jid="workday:acme:/job/NY/SWE_R1", source="workday",
            url="https://acme.wd5.myworkdayjobs.com/Careers/job/NY/SWE-Intern_R1",
        )
        assert job.posted_at is None
        _run(enrich.enrich_jobs([job], {}, net))
        assert job.sponsorship == "no-sponsorship"
        assert job.posted_at == "2026-06-20T00:00:00Z"

    def test_failed_fetch_stays_unknown_and_retryable(self):
        class ExplodingNet(FakeNet):
            async def get_json(self, url, **kwargs):
                raise RuntimeError("board deleted")

        job = _job(jid="greenhouse:acme:7", source="greenhouse")
        enriched, _fetched = _run(enrich.enrich_jobs([job], {}, ExplodingNet({}))
                                  )
        assert job.sponsorship == "unknown"
        assert enriched == set()  # no enriched_at stamp -> retried next run

    def test_source_without_fetcher_still_classified(self):
        net = FakeNet({})
        job = _job(jid="rippling:acme:1", source="rippling")
        enriched, _ = _run(enrich.enrich_jobs([job], {}, net))
        assert job.sponsorship == "unknown"
        assert enriched == {job.id}  # settled: rippling has no text to fetch
        assert net.calls == 0

    def test_text_stated_cycle_replaces_inferred(self):
        net = FakeNet({})
        job = _job(description=(
            "Join our Fall 2026 co-op program in Boston. "
            "No visa sponsorship for this role."
        ))
        job.season, job.season_inferred = "Summer 2027", True
        _run(enrich.enrich_jobs([job], {}, net))
        assert job.season == "Fall 2026"
        assert job.season_inferred is False  # the company stated it -> not a guess

    def test_text_can_promote_an_inferred_role_into_multiple_cycles(self):
        net = FakeNet({})
        job = _job(description=(
            "This internship is open for Fall 2026 and Summer 2027. "
            "No visa sponsorship is available."
        ))
        job.season, job.season_inferred = "Not stated", True
        _run(enrich.enrich_jobs([job], {}, net))
        assert job.season == "Fall 2026"
        assert job.seasons == ["Fall 2026", "Summer 2027"]
        assert job.season_inferred is False

    def test_text_without_cycle_statement_keeps_inference(self):
        net = FakeNet({})
        job = _job(description="A great internship. Python required.")
        job.season, job.season_inferred = "Summer 2027", True
        _run(enrich.enrich_jobs([job], {}, net))
        assert job.season == "Summer 2027"
        assert job.season_inferred is True  # still an inference, still marked ~

    def test_title_stated_cycle_never_overridden_by_text(self):
        net = FakeNet({})
        job = _job(description="This internship runs Fall 2026 through December.")
        job.season, job.season_inferred = "Summer 2027", False  # year was in the title
        _run(enrich.enrich_jobs([job], {}, net))
        assert job.season == "Summer 2027"
