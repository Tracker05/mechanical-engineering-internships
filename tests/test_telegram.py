"""Telegram push: message shaping and the outbox contract."""

from __future__ import annotations

from intern_engine import telegram


def _rec(**extra):
    rec = {"id": "greenhouse:acme:1", "company": "Acme", "title": "SWE Intern",
           "location": "Austin, TX", "url": "https://x/1", "season": "Summer 2027",
           "is_open": True, "sponsorship": "unknown", "skills": ["Python", "Go"]}
    rec.update(extra)
    return rec


class TestMessageShaping:
    def test_links_the_title_and_bolds_the_employer(self):
        out = telegram.build_messages([_rec()])[0]
        assert "<b>Acme</b>" in out
        assert '<a href="https://x/1">SWE Intern</a>' in out

    def test_marks_remote_roles(self):
        out = telegram.build_messages([_rec(location="Remote - US")])[0]
        assert "🆁" in out

    def test_a_role_without_a_url_still_renders(self):
        # The footer always carries a dashboard link, so check the ROLE line.
        role_line = telegram._role_line(_rec(url=""))
        assert "SWE Intern" in role_line
        assert "<a href" not in role_line

    def test_escapes_html_in_employer_text(self):
        # Titles are third-party text; an unescaped < would break parse_mode.
        out = telegram.build_messages([_rec(title="C++ <Dev> Intern")])[0]
        assert "&lt;Dev&gt;" in out
        assert "<Dev>" not in out

    def test_not_stated_cycle_is_omitted_rather_than_printed(self):
        out = telegram.build_messages([_rec(season="Not stated")])[0]
        assert "Not stated" not in out

    def test_long_lists_split_under_the_size_cap(self):
        msgs = telegram.build_messages([_rec(id=str(i), title="Software Engineering Intern " * 6)
                                        for i in range(40)])
        assert len(msgs) > 1
        assert all(len(m) <= 4096 for m in msgs)

    def test_untrusted_fields_cannot_break_the_hard_telegram_limit(self):
        huge = _rec(company="C" * 10_000, title="T" * 10_000,
                    url="https://example.com/" + "x" * 10_000,
                    salary="$" * 10_000, skills=["s" * 10_000] * 4)
        assert all(len(m) <= 4096 for m in telegram.build_messages([huge]))

    def test_header_counts_and_footer_links_once(self):
        msgs = telegram.build_messages([_rec(), _rec(id="2")])
        assert "2 new internships" in msgs[0]
        assert sum("Open the dashboard" in m for m in msgs) == 1

    def test_no_roles_no_messages(self):
        assert telegram.build_messages([]) == []


class TestOutboxContract:
    """Mirrors notify.send_new_roles so the queue drains correctly."""

    def test_unconfigured_settles_everything_rather_than_accumulating(self, monkeypatch):
        monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
        monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
        assert telegram.send_new_roles({}, ["a", "b"]) == ["a", "b"]

    def test_ids_missing_from_the_store_are_settled(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "1")
        assert telegram.send_new_roles({}, ["gone"]) == ["gone"]

    def test_closed_roles_are_settled_without_sending(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "1")
        store = {"a": _rec(is_open=False)}
        assert telegram.send_new_roles(store, ["a"]) == ["a"]

    def test_a_send_failure_keeps_the_role_queued(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "1")

        def boom(*a, **k):
            raise RuntimeError("network down")

        monkeypatch.setattr(telegram.httpx, "post", boom)
        # Nothing announced -> nothing settled -> the outbox keeps it.
        assert telegram.send_new_roles({"a": _rec()}, ["a"]) == []

    def test_a_successful_send_settles_the_role(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "1")
        sent = []

        class Resp:
            def raise_for_status(self): pass

        monkeypatch.setattr(telegram.httpx, "post",
                            lambda url, **k: (sent.append(k["json"]), Resp())[1])
        assert telegram.send_new_roles({"a": _rec()}, ["a"]) == ["a"]
        assert sent[0]["parse_mode"] == "HTML"
        assert sent[0]["disable_web_page_preview"] is True


class TestConfigured:
    def test_needs_both_token_and_chat(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
        monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
        assert telegram.configured() is False
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "1")
        assert telegram.configured() is True


class TestPartialDelivery:
    """A failed chunk must not re-send the chunks that already arrived."""

    def _store(self, n=40):
        return {str(i): {"id": str(i), "company": f"Co{i}",
                         "title": "Software Engineering Intern " * 6,
                         "location": "Austin, TX", "url": f"https://x/{i}",
                         "season": "Summer 2027", "is_open": True,
                         "sponsorship": "unknown", "skills": ["Python"]}
                for i in range(n)}

    def test_chunks_carry_their_own_ids(self):
        store = self._store()
        chunks = telegram.build_chunks(list(store.items()))
        assert len(chunks) > 1
        flat = [jid for _t, ids in chunks for jid in ids]
        assert flat == list(store)          # every id, exactly once, in order

    def test_first_chunk_settles_when_the_second_fails(self, monkeypatch):
        # The production bug: ids were settled only after EVERY message landed,
        # so one failed chunk re-sent the ones already delivered.
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "1")
        store = self._store()
        calls = {"n": 0}

        class Resp:
            def raise_for_status(self): pass

        def flaky(url, **k):
            calls["n"] += 1
            if calls["n"] == 2:
                raise RuntimeError("network blip")
            return Resp()

        monkeypatch.setattr(telegram.httpx, "post", flaky)
        chunks = telegram.build_chunks(list(store.items()))
        done = telegram.send_new_roles(store, list(store))
        assert done == chunks[0][1]        # exactly chunk 1, nothing more

    def test_every_chunk_settles_when_all_succeed(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "1")
        store = self._store()

        class Resp:
            def raise_for_status(self): pass

        monkeypatch.setattr(telegram.httpx, "post", lambda url, **k: Resp())
        assert telegram.send_new_roles(store, list(store)) == list(store)


class TestIdenticalOpenings:
    """The reported symptom: "each post is posted thrice".

    GDIT filed RQ225450, RQ225456 and RQ225469 for one job on 2026-08-07. All
    three are real (each returns 200 on its own board), so none may be dropped
    — but one push notification printing the same line three times is noise.
    """

    def _store(self):
        return {
            r: {"id": r, "company": "GDIT",
                "title": "Summer 2027 Software Developer Internship",
                "location": "USA MD Annapolis Junction", "url": f"https://x/{r}",
                "season": "Summer 2027", "is_open": True, "sponsorship": "unknown",
                "first_seen_at": "2026-08-07T10:45:44Z"}
            for r in ("RQ225450", "RQ225456", "RQ225469")
        }

    def _send(self, monkeypatch, store):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "1")
        sent = []

        class Resp:
            def raise_for_status(self): pass

        monkeypatch.setattr(telegram.httpx, "post",
                            lambda url, **k: (sent.append(k["json"]), Resp())[1])
        return telegram.send_new_roles(store, list(store)), sent

    def test_the_role_appears_once_in_the_message(self, monkeypatch):
        _done, sent = self._send(monkeypatch, self._store())
        assert len(sent) == 1
        assert sent[0]["text"].count("Summer 2027 Software Developer Internship") == 1

    def test_the_message_says_how_many_openings(self, monkeypatch):
        _done, sent = self._send(monkeypatch, self._store())
        assert "3 openings" in sent[0]["text"]

    def test_the_header_still_counts_three_new_internships(self, monkeypatch):
        _done, sent = self._send(monkeypatch, self._store())
        assert "3 new internships" in sent[0]["text"]

    def test_all_three_ids_settle_on_the_one_delivery(self, monkeypatch):
        store = self._store()
        done, _sent = self._send(monkeypatch, store)
        assert sorted(done) == sorted(store)

    def test_a_failure_leaves_all_three_queued(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "1")

        def boom(*a, **k):
            raise RuntimeError("telegram 500")

        monkeypatch.setattr(telegram.httpx, "post", boom)
        store = self._store()
        assert telegram.send_new_roles(store, list(store)) == []
