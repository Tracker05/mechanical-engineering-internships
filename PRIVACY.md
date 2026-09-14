# Privacy

Short version: the only personal data this project holds is an email address,
only if you typed it into the subscribe box, and you can delete it in one click.

## The dashboard

The dashboard is a static file served by GitHub Pages. It sets no cookies, loads
no third-party scripts, and runs no analytics. I don't know who visits it.

**Saved roles** (the ★ button) are stored in your browser's `localStorage`.
They never leave your device — not to me, not to anyone. Clearing site data
removes them. That's also why they don't sync across devices: there's no account
because there's no server holding your list.

## Email alerts

If you subscribe:

**What's stored** — your email address, a random unsubscribe token, and the
timestamp you signed up. Nothing else. No name, no school, no IP, no resume.

**Where** — a Supabase (Postgres) database. Row-level security allows anonymous
`INSERT` only; the list cannot be read by the public key that the dashboard
ships. The schema and policies are in [`db/schema.sql`](db/schema.sql) so you
can check that claim rather than trust it.

**What it's used for** — one daily digest of new internships, when there are
new internships. Nothing else. Never sold, never shared, never used to market
anything.

**Who else sees it** — [Brevo](https://www.brevo.com/) delivers the mail, so
they process your address as part of sending. That's the entire third-party
surface.

**Unsubscribing** — every email carries an unsubscribe link, plus the standard
`List-Unsubscribe` header so your mail client shows its own unsubscribe button.
The link opens a page with a single confirm button; that button deletes your
row immediately. The confirm step exists because corporate mail scanners fetch
every link in an incoming message, and a page that unsubscribed on load meant
those scanners silently removed people who never opened the email. No
re-engagement sequence, no win-back email, no "are you sure you want to leave"
beyond that one click.

**Retention** — until you unsubscribe. Then it's gone; I don't keep a
suppression list.

**Known limitation — single opt-in.** Signup does not currently send a
confirmation email, so in principle someone could type *your* address into the
form. If a digest arrives that you didn't ask for, the unsubscribe link in it
removes the address immediately and permanently — one confirm click and
it's gone; no follow-up. Double opt-in is the correct fix and is planned; until it ships,
this is the honest description of what the form does.

**Committed state** — the repo commits `data/mail_state.json` so scheduled runs
share delivery state. It contains counts, a cursor, and SHA-256 *hashes* of
addresses whose last delivery failed. Never plaintext addresses.

## Job data

Everything about jobs comes from employers' public job boards. No personal data
of any applicant is involved at any point. I don't republish full posting
descriptions — only classifications derived from them (cycle, sponsorship
verdict, skill tags, pay when stated).

## Requests

Email shahzain.zeza@gmail.com to ask what's stored about you or to have it
deleted. Since the only thing stored is your email address, the unsubscribe link
already does the deletion — but ask if you'd rather I confirm it.

## Changes

Material changes to this document will be noted in the repo's commit history,
which is public and permanent.
