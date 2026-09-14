# Start here

You do **not** need GitHub, an account, or any setup. This runs on your laptop.

## Run it

Unzip the folder, open a terminal in it, and run:

```
python find-internships.py
```

(On Mac/Linux, if `python` isn't found, use `python3`.)

It will offer to install two libraries the first time. Say yes. Then it checks
about 4,500 employer job boards and opens the results in your browser.

**First run takes a few minutes.** It's polling real career sites, not
downloading a cached list. Some boards timing out is normal.

## What you get

Three views of the same data, all written into the folder:

| File | What it's for |
| --- | --- |
| `docs/index.html` | Dashboard with search, filters, and a save-for-later list. Opens automatically. |
| `README.md` | Plain table, newest roles on top. |
| `data/internships.csv` | Opens in Excel or Google Sheets. Use this to track what you've applied to. |

## Getting fresh results

Run the same command again. Once a day is plenty — most companies post in
batches, not continuously. Each run updates all three files in place.

## If you want to change what it finds

Everything is in `data/config.json`. Open it in any text editor.

**The one worth changing first** is `include_general_engineering`. It's `true`,
which means postings titled just "Engineering Intern" — no discipline named —
show up. At a manufacturer those are usually worth seeing, but it's the noisiest
setting. If the list feels padded, change it to `false`.

Other useful ones:

- `cycles` — currently `["Summer 2027", "Fall 2026"]`. Drop Fall 2026 if you
  only care about summer.
- `max_per_company` — currently `3`. Raise it if you want every opening at a
  company you like.
- `regions` — `["US"]`. Change to `["Global"]` to include international roles.
- `role_scope` — `"mechanical"`. Change to `"all"` to turn off discipline
  filtering entirely.

## Adding a company it's missing

Open `data/config.json`'s neighbour, `data/companies.json`, and add one line:

```json
{ "name": "Honda", "slug": "their-board-slug", "ats": "greenhouse" }
```

The tricky part is `slug` — it has to match their real job board. Go to the
company's careers page and look at the URL. If it's
`job-boards.greenhouse.io/honda`, the slug is `honda` and the ats is
`greenhouse`. Supported ats values: `greenhouse`, `lever`, `ashby`, `workday`,
`smartrecruiters`, `oracle`, `breezy`, `recruitee`, `workable`, `rippling`,
`eightfold`, `amazon`.

A wrong slug fails quietly rather than erroring, so confirm the board URL loads
in your browser first.

## If you later want it to update by itself

That's the only thing the GitHub route adds: a scheduled run every 30 minutes
without you touching it, plus a public web page. Nothing else differs — same
engine, same output. Instructions are in `README.md` if you ever want it.

## Troubleshooting

**"No module named httpx"** — the installer step was skipped. Run
`python -m pip install httpx requests`.

**"Nothing to render yet"** — you ran `run.py render` before any successful
fetch. Run `python find-internships.py` instead.

**Almost no results** — that's likely real. Summer 2027 mechanical postings
start appearing in earnest through the fall. Run it again in a week.
