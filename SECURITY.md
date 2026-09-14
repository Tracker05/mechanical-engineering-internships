# Security Policy

## Reporting a vulnerability

Please **don't** open a public issue for a security problem.

Use GitHub's [private vulnerability reporting](../../security/advisories/new)
(Security → Report a vulnerability). If that isn't available to you, email
shahzain.zeza@gmail.com with "SECURITY" in the subject.

I'll acknowledge within 72 hours and tell you what I plan to do. This is a
personal project maintained by one student, not a company with an on-call
rotation — but anything affecting subscriber data gets same-day attention.

## What's in scope

- Anything exposing the email subscriber list or unsubscribe tokens, or letting
  someone unsubscribe another person.
- Note: signup is **single opt-in** today, so subscribing someone else's address
  is a known limitation rather than a finding — see PRIVACY.md. Reports about
  the *rate* at which that can be done (bulk abuse) are still in scope.
- Injection into generated artifacts (`README.md`, `docs/index.html`, the CSV,
  the Atom feed, the JSON API) via attacker-controlled job posting text.
- Anything that lets a third party alter what this repo publishes.
- Leaked credentials in the repo or in Actions logs.

## What's out of scope

- Content of third-party job postings themselves.
- Rate limits or availability of the ATS APIs we read.
- Reports from automated scanners with no demonstrated impact.
- The public Supabase publishable key — it's public by design and gated by
  row-level security (see `db/schema.sql`).

## Design notes relevant to security

- **No secrets in the repo.** All credentials are GitHub Actions secrets. Every
  integration no-ops silently when its env vars are unset.
- **The subscriber list is never public.** RLS allows anonymous `INSERT` only;
  no anonymous `SELECT`. Unsubscribing goes through a `security definer` RPC
  keyed on a per-subscriber secret token.
- **`data/mail_state.json` is committed**, so it stores only *hashes* of
  addresses that failed delivery, never addresses.
- **Unsubscribe requires a click**, not a page load, so mail security scanners
  that fetch every link can't unsubscribe people.
- **The CSV is neutralized** against spreadsheet formula injection (`=`, `+`,
  `-`, `@` prefixes), because job titles are third-party text.
- **All HTML output is escaped** at render time.
- **GitHub Actions are pinned to commit SHAs**, not mutable tags.
