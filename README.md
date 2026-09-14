<div align="center">

# 🔧 Summer 2027 Mechanical Engineering Internships

**A self-updating engine that tracks mechanical engineering internships so you don't have to.**

</div>

> **First run pending.** This file is generated automatically. Once the
> `update` workflow runs (every 30 minutes, or trigger it by hand from the
> Actions tab), this placeholder is replaced with the live list.

## Scope

|            |                                                                                                                                              |
| ---------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| **Roles**  | Mechanical Design, Manufacturing, Thermal/Fluids, Automotive, Aerospace, Robotics & Controls, Structures & Materials, Energy, Test & Quality   |
| **Region** | United States                                                                                                                                |
| **Cycles** | Summer 2027 and Fall 2026                                                                                                                    |

## Setup

1. **Actions** → Settings → Actions → General → allow all actions.
2. **Pages** → Settings → Pages → Source: *Deploy from a branch*, branch `main`, folder `/docs`.
3. Actions tab → **update** → *Run workflow* to do the first harvest.

Email alerts stay off until you add your own `supabase_url` and
`supabase_publishable_key` to `data/config.json`. Everything else — the README
table, dashboard, RSS feed, CSV, and JSON API — works without it.

## Tuning

Every knob lives in `data/config.json`:

| Key | What it does |
| --- | --- |
| `cycles` | Which terms to publish, in order. Becomes the section headings. |
| `role_scope` | `"mechanical"` (default) or `"all"` to drop the discipline filter entirely. |
| `include_general_engineering` | Keep discipline-free "Engineering Intern" titles. `true` by default; set `false` for a stricter list. |
| `regions` | `["US"]`, `["US", "Canada"]`, or `["Global"]`. |
| `max_age_days` | How old a posting can be before it's dropped. |
| `max_per_company` | Cap on rows from one employer. |
| `section_limits` | Max rows rendered per cycle section. |

Adding an employer is one line in `data/companies.json` — see [CONTRIBUTING.md](CONTRIBUTING.md).

---

Forked from [zshah101/Automated-List-Of-Summer-2027-and-Fall-2026-Tech-Internships](https://github.com/zshah101/Automated-List-Of-Summer-2027-and-Fall-2026-Tech-Internships) (MIT licence, retained) and retargeted from software engineering to mechanical engineering. See [MECHANICAL-CHANGES.md](MECHANICAL-CHANGES.md) for exactly what was modified.
