"""Discord alerts: every new role reaches the channel, or none pretends to."""

import intern_engine.notify as notify


def _store(n):
    return {
        f"gh:acme:{i}": {
            "id": f"gh:acme:{i}", "company": f"Co{i}", "title": "SWE Intern",
            "season": "Summer 2027", "location": "NY", "url": f"https://x/{i}",
            "is_open": True, "sponsorship": "unknown",
        }
        for i in range(n)
    }


class FakePost:
    """Captures every webhook POST instead of sending it."""

    def __init__(self, fail_at=None):
        self.payloads = []
        self.fail_at = fail_at

    def __call__(self, url, json=None, timeout=None):
        if self.fail_at is not None and len(self.payloads) == self.fail_at:
            raise RuntimeError("discord 500")
        self.payloads.append(json)
        return self

    def raise_for_status(self):
        return None


def _send(monkeypatch, store, ids, fake):
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord/webhook")
    monkeypatch.setattr(notify.httpx, "post", fake)
    monkeypatch.setattr(notify, "_cycle_colors", lambda: {})
    return notify.send_new_roles(store, ids)


def test_no_webhook_clears_the_queue_instead_of_growing_it(monkeypatch):
    # Nothing to deliver to, so these ids will never be announceable — holding
    # them would grow the outbox forever.
    monkeypatch.delenv("DISCORD_WEBHOOK_URL", raising=False)
    assert notify.send_new_roles(_store(3), ["gh:acme:0"]) == ["gh:acme:0"]


def test_small_batch_is_one_message(monkeypatch):
    store = _store(4)
    fake = FakePost()
    done = _send(monkeypatch, store, list(store), fake)
    assert len(fake.payloads) == 1
    assert len(fake.payloads[0]["embeds"]) == 4
    assert sorted(done) == sorted(store)


def test_large_batch_is_chunked_so_nothing_is_dropped(monkeypatch):
    # Discord caps a message at 10 embeds. A single message meant role 11+ of a
    # big drop day silently never reached the channel.
    store = _store(25)
    fake = FakePost()
    done = _send(monkeypatch, store, list(store), fake)
    assert len(fake.payloads) == 3
    assert [len(p["embeds"]) for p in fake.payloads] == [10, 10, 5]
    assert len(done) == 25
    assert "25 new internships spotted" in fake.payloads[0]["content"]


def test_overflow_is_held_for_the_next_run_not_dropped(monkeypatch):
    store = _store(120)
    fake = FakePost()
    done = _send(monkeypatch, store, list(store), fake)
    cap = notify._MAX_EMBEDS * notify._MAX_MESSAGES
    assert sum(len(p["embeds"]) for p in fake.payloads) == cap
    # The ones we didn't announce stay out of `done`, so they stay queued.
    assert len(done) == cap
    assert f"{120 - cap} in the next batch" in fake.payloads[0]["content"]


def test_failed_chunk_leaves_its_roles_queued(monkeypatch):
    store = _store(25)
    fake = FakePost(fail_at=1)  # second chunk explodes
    done = _send(monkeypatch, store, list(store), fake)
    assert len(fake.payloads) == 1
    # Only the 10 that actually landed are reported as handled; draining the
    # rest is exactly how a partial failure used to lose roles.
    assert len(done) == 10


def test_closed_roles_are_settled_without_being_announced(monkeypatch):
    store = _store(3)
    store["gh:acme:1"]["is_open"] = False
    fake = FakePost()
    done = _send(monkeypatch, store, list(store), fake)
    assert len(fake.payloads[0]["embeds"]) == 2
    # The closed one will never be announceable — it leaves the queue anyway.
    assert "gh:acme:1" in done
    assert len(done) == 3


def test_ids_missing_from_the_store_do_not_wedge_the_queue(monkeypatch):
    fake = FakePost()
    done = _send(monkeypatch, _store(1), ["gh:acme:0", "gone:1"], fake)
    assert "gone:1" in done


def _triplicate():
    """One job, three real requisitions — the GDIT case from 2026-08-07."""
    return {
        f"wd:gdit:{r}": {
            "id": f"wd:gdit:{r}", "company": "GDIT",
            "title": "Summer 2027 Software Developer Internship",
            "season": "Summer 2027", "location": "USA MD Annapolis Junction",
            "url": f"https://x/{r}", "is_open": True, "sponsorship": "unknown",
            "first_seen_at": "2026-08-07T10:45:44Z",
        }
        for r in ("RQ225450", "RQ225456", "RQ225469")
    }


def test_three_identical_requisitions_post_one_embed(monkeypatch):
    # The reported bug: "each post is posted thrice".
    store = _triplicate()
    fake = FakePost()
    _send(monkeypatch, store, list(store), fake)
    assert len(fake.payloads) == 1
    assert len(fake.payloads[0]["embeds"]) == 1
    assert "3 openings" in fake.payloads[0]["embeds"][0]["description"]


def test_the_headline_still_counts_every_opening(monkeypatch):
    # Folding the embeds must not shrink the count — three jobs really did open.
    store = _triplicate()
    fake = FakePost()
    _send(monkeypatch, store, list(store), fake)
    assert "3 new internships spotted" in fake.payloads[0]["content"]


def test_one_embed_settles_all_the_ids_it_stands_for(monkeypatch):
    # Otherwise the two absorbed ids stay queued forever, and every later run
    # tries to announce a role that has already gone out.
    store = _triplicate()
    fake = FakePost()
    done = _send(monkeypatch, store, list(store), fake)
    assert sorted(done) == sorted(store)


def test_a_failed_send_still_leaves_every_grouped_id_queued(monkeypatch):
    store = _triplicate()
    fake = FakePost(fail_at=0)
    assert _send(monkeypatch, store, list(store), fake) == []
