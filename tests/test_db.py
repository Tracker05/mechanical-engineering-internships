from pathlib import Path

from intern_engine import db


class _Query:
    def __init__(self, client, kind, name):
        self.client = client
        self.kind = kind
        self.name = name

    def execute(self):
        if self.kind == "rpc" and self.client.fail_rpc:
            raise RuntimeError("transaction failed")
        return self


class _Client:
    def __init__(self, fail_rpc=False):
        self.events = []
        self.fail_rpc = fail_rpc

    def table(self, name):
        self.events.append(("table", name))
        return _Query(self, "table", name)

    def rpc(self, name, args):
        self.events.append(("rpc", name, args))
        return _Query(self, "rpc", name)


def _registry():
    return [{
        "name": "Acme",
        "ats": "workday",
        "slug": "acme",
        "tenant": "acme",
        "site": "Campus",
        "wd": "wd5",
    }]


def _store():
    return {"job-1": {
        "id": "job-1",
        "source": "workday",
        "company": "Acme",
        "company_slug": "acme",
        "board_key": "workday:acme:campus",
        "title": "Software Intern",
        "location": "Austin, TX",
        "url": "https://example.test/job-1",
        "is_open": True,
        "canonical_id": "canonical-1",
        "requisition_id": "REQ-1",
        "aliases": ["old-job-1"],
    }}


def test_one_rpc_replaces_the_complete_site_aware_mirror(monkeypatch):
    monkeypatch.setattr(db.registry, "load", _registry)
    client = _Client()
    monkeypatch.setattr(db, "_client", lambda: client)

    assert db.sync(_store(), {"fetched_at": "2026-08-06T20:00:00Z"}) is True
    assert len(client.events) == 1
    _, name, payload = client.events[0]
    company = payload["p_companies"][0]
    job = payload["p_jobs"][0]

    assert name == "replace_mirror_snapshot"
    assert company["key"] == "workday:acme:campus"
    assert job["company_key"] == company["key"]
    assert job["canonical_id"] == "canonical-1"
    assert job["aliases"] == ["old-job-1"]
    assert "snapshot_id" not in company
    assert "snapshot_id" not in job
    assert payload["p_run"]["fetched_at"] == "2026-08-06T20:00:00Z"


def test_failed_transaction_is_reported_without_fallback_table_mutations(monkeypatch):
    monkeypatch.setattr(db.registry, "load", _registry)
    client = _Client(fail_rpc=True)
    monkeypatch.setattr(db, "_client", lambda: client)

    assert db.sync(_store(), {}) is False
    assert [event[0] for event in client.events] == ["rpc"]


def test_schema_defines_a_serialized_transactional_replacement_rpc():
    schema = Path("db/schema.sql").read_text(encoding="utf-8")

    assert "function public.replace_mirror_snapshot(" in schema
    assert "pg_advisory_xact_lock" in schema
    assert "create temporary table intern_engine_mirror_companies" in schema
    assert "create temporary table intern_engine_mirror_jobs" in schema
    assert "create or replace function public.finalize_mirror_snapshot" not in schema

    stale_guard = schema.index("incoming_fetched_at < latest_fetched_at")
    first_live_mutation = schema.index("insert into public.companies")
    assert stale_guard < first_live_mutation
    assert "where completed_run.fetched_at = metric.fetched_at" in schema


def test_casefolded_email_migration_reconciles_duplicates_atomically():
    schema = Path("db/schema.sql").read_text(encoding="utf-8")
    start = schema.index("-- Convert the legacy case-sensitive address key")
    end = schema.index("commit;", start)
    migration = schema[start:end]

    assert "begin;" in migration
    assert "lock table public.email_subscribers in access exclusive mode" in migration
    assert "(confirmed_at is not null) desc" in migration
    assert "min(confirmed_at) as confirmed_at" in migration
    assert migration.index("delete from public.email_subscribers") < migration.index(
        "create unique index email_subscribers_email_ci_idx"
    )
