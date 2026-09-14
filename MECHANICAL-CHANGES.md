# What was changed from upstream

This is a fork of
[zshah101/Automated-List-Of-Summer-2027-and-Fall-2026-Tech-Internships](https://github.com/zshah101/Automated-List-Of-Summer-2027-and-Fall-2026-Tech-Internships)
(MIT, licence retained), retargeted from software engineering to mechanical
engineering.

The harvesting layer is untouched. All 12 ATS connectors, the store, the
season/cycle detection, the sponsorship and H-1B logic, the Drop Radar, the
dashboard, and the publish path work exactly as they did upstream. What changed
is the classification layer — the part that decides *which* internships count.

---

## 1. Role classification — `src/intern_engine/filters.py`

Upstream kept software/data/ML/security roles and used a
`_HARDWARE_EXCLUDE_RE` to throw away everything mechanical. That exclude list
was, almost word for word, a list of the roles this fork wants. So it was
inverted.

| Upstream | Here |
| --- | --- |
| `_INCLUDE_RE` — software, developer, SWE, data science, ML, quant, cyber | `_INCLUDE_RE` — mechanical, mechatronics, robotics, manufacturing, process, design/CAD, thermal, fluids, HVAC, aerodynamics, CFD, structural, FEA, materials, metallurgy, composites, automotive, powertrain, chassis, suspension, aerospace, propulsion, energy, test, quality, controls |
| `_HARDWARE_EXCLUDE_RE` — rejected mechanical terms | `_SOFTWARE_EXCLUDE_RE` — rejects software, data, ML/AI, quant, cyber, cloud, embedded, firmware, infrastructure |
| `_SOFTWARE_FIRST_RE` — software identity beats a hardware mention | `_MECH_FIRST_RE` — mechanical identity beats a software mention |
| — | `_OTHER_DISCIPLINE_RE` (new) — electrical, civil, chemical, petroleum, environmental, architectural, bio are their own majors |
| — | `_GENERIC_ENG_RE` (new) — see below |
| `is_tech(title)` | `is_mechanical(title, include_general=True)`; `is_tech` kept as an alias |

### The generic-engineering decision

A title that says "Engineering Intern" and names no discipline is a real
judgment call. At a manufacturer it is usually a rotational role a mechanical
student should see; it is also the noisiest bucket in the list.

It is **included by default** and controlled by `include_general_engineering`
in `data/config.json`. Set it to `false` for a stricter list. Either way, a
title that names another major is still rejected — only genuinely
discipline-free titles are affected.

### Precedence rules worth knowing

- `"Mechanical Engineering Intern - Simulation Software"` → **kept**. The
  mechanical identity outranks the incidental software word.
- `"Robotics - Software Development Engineer Intern"` → **rejected**. Robotics
  deliberately does *not* outrank an explicit software identity, otherwise every
  Amazon Robotics SWE posting lands in the list.
- `"Engineering Intern (Electrical / Mechanical / GNC / Software)"` → **kept**.
  It names mechanical explicitly.

## 2. Categories — `src/intern_engine/filters.py`

| Upstream | Here |
| --- | --- |
| Software, Data & ML/AI, Security, Quant, Hardware | Automotive & Mobility, Aerospace & Defense, Robotics & Controls, Manufacturing & Process, Energy & Power, Thermal & Fluids, Structures & Materials, Test & Quality, Design & CAD, Biomedical, General Engineering |

First match wins, so order matters. Energy & Power sits ahead of Thermal &
Fluids on purpose: without it, "Wind Turbine Structural Analysis Intern" is
tagged Thermal because of the word *turbine*.

## 3. Skill tags — `src/intern_engine/skills.py`

The entire vocabulary was replaced. 56 patterns, ordered by filter value (CAD
first, since that is what a mechanical student actually screens on):

- **CAD** — SolidWorks, CATIA, Siemens NX, Creo, Inventor, Fusion 360, AutoCAD,
  Onshape, Solid Edge, Revit, GD&T, Tolerance Analysis
- **Simulation** — ANSYS, Abaqus, Nastran, COMSOL, HyperMesh, LS-DYNA,
  STAR-CCM+, Fluent, OpenFOAM, Adams, FEA, CFD
- **Analysis & code** — MATLAB, Simulink, Python, C++, LabVIEW, Excel, ROS, PLC
- **Processes** — CNC, Machining, Additive Manufacturing, Injection Molding,
  Sheet Metal, Welding, Casting, Composites, Mastercam, Hydraulics
- **Quality** — Six Sigma, Lean, FMEA, DFM, SPC, Design of Experiments, CMM,
  Metrology, Instron
- **PLM** — Teamcenter, Windchill, PLM/PDM, ASME Y14.5, Git

Upstream's case-sensitivity trick is preserved for names that are also ordinary
English words: `Inventor`, `Adams`, and `Excel` only match capitalized, so
"you will be an inventor of new ideas" does not tag a role with Autodesk
Inventor.

## 4. Configuration — `data/config.json`, `src/intern_engine/config.py`

- `role_scope` is now `"mechanical"` or `"all"` (was `"tech"` or `"all"`).
- `include_general_engineering` added (boolean, default `true`).
- **Supabase credentials removed.** Upstream ships the original author's
  `supabase_url` and publishable key. Left in place, every email signup on this
  fork would write a subscriber into someone else's database. Email alerts are
  off until you add your own project; nothing else depends on it.

## 5. Data reset — `data/`

`data/companies.json` is **kept in full** — all 4,803 employers. These are ATS
boards, not software-specific, and they already include Toyota, Caterpillar,
Cummins, Rivian, GM, Ford, Boeing, Northrop Grumman, Anduril, RTX, Bosch,
BorgWarner, Magna, Michelin, GE Vernova, Flowserve, Emerson, Polaris, and
Baker Hughes.

Everything holding *software roles* was cleared so the first run publishes a
clean list rather than 1,138 closed SWE rows: `jobs.json`, `history.jsonl`,
`observed.json`, `candidates.json`, `stats.json`, `mail_state.json`,
`internships.csv`, and the `docs/api/` outputs.

`known_windows.json` was emptied rather than reseeded. Upstream hand-seeds
typical opening months for marquee tech employers. Inventing equivalent months
for mechanical employers would be fabricated data, so the Drop Radar starts
empty and fills in from real observed posting dates.

`h1b.json` and `health.json` are kept — both are employer-level, not
role-level.

## 6. Tests — `tests/`

25 tests asserted the old domain and were rewritten, not deleted:
`TestTech` → `TestMechanical`, the category assertions, the scope-exclusion
class, the skills vocabulary tests, and fixture titles across
pipeline/readme/publish/dashboard.

**563 passing.**

One test fails: `test_publish.py::test_feed_never_folds_a_closed_requisition_into_a_live_one`.
It fails identically on unmodified upstream — a pre-existing bug in the feed
grouping, not something this fork introduced.

## Measured accuracy

| Check | Result |
| --- | --- |
| Curated mechanical titles kept | 42 / 42 |
| Software and non-technical titles rejected | 32 / 32 |
| Leakage across upstream's 1,138 real stored software titles | 4 (0.4%) |

Three of those four are `Powertrain Controls Software Engineering Intern`,
kept deliberately — powertrain controls at an automaker is a reasonable
mechanical-adjacent role. The fourth names mechanical explicitly.

## Adding employers

One line in `data/companies.json`:

```json
{ "name": "Company Name", "slug": "their-board-slug", "ats": "greenhouse" }
```

Supported `ats` values: `amazon`, `ashby`, `breezy`, `eightfold`, `greenhouse`,
`lever`, `oracle`, `recruitee`, `rippling`, `smartrecruiters`, `workable`,
`workday`.

The slug must match the employer's real board or the fetch silently returns
nothing, so confirm it by opening the board URL before adding. The `discover`
workflow also finds new boards on its own over time.
