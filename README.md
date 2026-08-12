# MileageCurve

**What breaks, and at what mileage.** A reference for US vehicle reliability built from NHTSA
Office of Defects Investigation data — organised by model *generation*, not model year.

Most reliability sites tell you how many complaints a car has. This one tells you **when** the
failures happen: the distribution of mileage-at-failure, per system, per generation. That shape
is the point — a manufacturing defect and ordinary wear look completely different, and averages
hide the difference.

Published by BiLingoPlus LLC. Data is public domain; methodology is open; the underlying
aggregates are downloadable.

---

## How it works

Everything is deterministic Python from the standard library. No frameworks, no `node_modules`,
no external packages — the site has to keep building unattended for years, and every dependency
is something that eventually breaks a nightly run.

```
pipeline/fetch_nhtsa.py          download ODI flat files (complaints, recalls, investigations)
pipeline/build_db.py             load them into SQLite
pipeline/top_models.py           select the models the corpus covers
pipeline/normalize_generations.py  clean the curated generation map
pipeline/analyze.py              compute per-generation statistics
pipeline/coverage_check.py       report how many pages meet the quality bar
pipeline/render.py               generate the static site into dist/
```

Run the whole chain:

```bash
python pipeline/fetch_nhtsa.py
python pipeline/build_db.py
python pipeline/render.py
```

`data/generations.clean.json` is the one curated asset in the repository: the model-year → generation
map with platform codes and documented defects, verified against public sources and audited for
overlaps, gaps and unsupported claims.

## Data sources

All from [NHTSA's Office of Defects Investigation](https://www.nhtsa.gov/nhtsa-datasets-and-apis),
United States government work, public domain:

- **Complaints** (`FLAT_CMPL`) — 2.2M owner reports; field 18 carries mileage at failure.
- **Recalls** (`FLAT_RCL_POST_2010`) — campaigns since 2010, including the `DO_NOT_DRIVE` and
  `PARK_OUTSIDE` severe advisories.
- **Investigations** (`FLAT_INV`).

## What the numbers do and do not mean

Complaint counts reflect what owners chose to report. They are **not** a failure rate per vehicle
sold: no free, model-level production figure exists, and the obvious proxy — the affected-vehicle
count on recall campaigns — was tested and rejected (it overstates by a median factor of 7.6 because
most campaigns span several model years). So this site does not rank cars against each other. It
describes what happens to a given car, and when.

## Licence

Code: MIT. Generated aggregates: CC BY 4.0 — attribute to MileageCurve and link back.
Source data is public domain.
