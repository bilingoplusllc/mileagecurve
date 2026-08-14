# MileageCurve — Final Product Roadmap

Ordering rule applied: (user value × SEO reach) ÷ build risk. All specs verified against `pipeline/render.py`, `pipeline/analyze.py`, `pipeline/charts.py`, and `data/mileagecurve.db` today. One correction to a vision claim found during verification: **`analyze.py` does NOT currently fetch recall `consequence` text** — the SELECT at lines ~185–188 fetches only `MIN(defect), MIN(remedy)`. The `consequence` column exists in the db and is 100% populated (217,256/217,256 verified), so the recall feature needs one column added to that query.

---

## 1. Ship this week (3 features, all pure markup/template — no JS, no new pages)

### 1.1 Mobile answer box — the first screen answers before it explains
*(shopper F3 — judges 9 / 8 / 10, the highest-consensus item on the board)*

- **Pages touched:** all 318 generation pages. `render_generation()` in `pipeline/render.py` (the `.snap` dl markup already exists in the rail block, lines ~1135–1142) + the CSS media query block (lines ~577–600).
- **Layout:** directly under `<p class="dateline">`, before the verdict line, render the existing `.snap` definition list in-flow at all widths (desktop keeps the rail copy; hide the in-flow one above 1180px, or vice versa — never both visible). Four rows, real copy (Prius):
  > **Reports with mileage** 3,988 · **Median of reported failures** 15,000 mi · **Most-reported system** Brakes (25%) · **Recalls** 12
  Below it, two in-flow links styled as buttons: **"Before-you-buy checklist ↓"** (anchor `#buy`, feature 1.3) and **"Check this VIN — NHTSA ↗"** (nhtsa.gov/recalls). On the 57 pages with `severe_advisories > 0`, an `.alert` strip ABOVE the box: *"A DO NOT DRIVE recall covers part of this generation — check the VIN before driving it home."*
- **Chart:** none.
- **Pipeline:** ~30 lines in `render_generation()` + one media-query change. Zero maintenance.
- **Guardrail:** the label must be **"Median of reported failures"**, never "Median at failure" bare. This block is featured-snippet-shaped — stripped of the "complaints that record mileage" conditional, "median at failure 15,000 mi" fabricates "your Prius fails at 15k" (the median is dominated by one early brake defect). The conditional lives in the label itself, not a footnote.

### 1.2 Recall flow rebuilt: "Is your car included?"
*(owner F3 — judges 9 / 9.5 / 9; best value-per-effort on the board: it un-throws-away data)*

- **Pages touched:** all 318 generation pages. `generation_stats()` in `pipeline/analyze.py` (add `MIN(consequence)` to the recalls SELECT — see correction above); the recalls section of `render_generation()` in `render.py` (lines ~1073–1090).
- **Layout:** each recall table row becomes a `<details>`. Summary line = year · component · first consequence clause: *"2014 · Hybrid inverter — hybrid system can shut down while driving"*. Expanded = three labeled paragraphs, verbatim government text: **The defect** / **What can happen** / **The free fix** (defect, consequence, remedy). `do_not_drive` rows render with the `open` attribute. The severe banner is the SAME alert strip as feature 1.1 — one element, not two. Standing rail card on every page: *"Recall check — 12 campaigns cover this generation. Recalls are fixed free, for any owner. Enter your VIN at NHTSA ↗"*.
- **Chart:** none. **JS:** none (native `<details>`).
- **Pipeline:** half a day; markup only, plus the one-column query change.
- **Guardrails:** (a) crash/fire framing appears ONLY inside a specific campaign's consequence text — never as new page-top totals; (b) **extend the PII grep build gate to the newly exposed defect/consequence/remedy fields before shipping** — this corpus previously leaked a dealership's address and phone (memory: generated-text-carries-other-peoples-data); (c) label the text as NHTSA's words, no paraphrase.

### 1.3 Before you buy: the 3-minute check
*(shopper F1 — judges 9 / 7 / 9; the 7 is one severable item, amended below)*

- **Pages touched:** all 318 generation pages. New `checklist_items()` in `pipeline/narrative.py` (reuses `generation_stats()` output + the gen dict's curated `known_issues`); ~100 lines in `render_generation()`. **Fold the existing "What this means if you are buying one" narrative block into it** — delete it from the narrative-sections loop so two buying sections never compete.
- **Layout:** one section, `id="buy"`, placed after the Figure 1 note + lead card. H2: **"Before you buy a 2010–2015 Prius: the 3-minute check"**. Sub: *"Generated from 3,988 mileage-tagged complaints, 12 recall campaigns and 5 documented problem areas. Print this page — the checklist survives print."* (print CSS at line ~636 already strips nav/ads). Numbered list in a `.card`, one `<strong>` lead-in per item:
  1. *"**Run the VIN at nhtsa.gov/recalls.** 12 campaigns cover this generation; an open recall is a free repair you can make the seller's problem."* — if `do_not_drive`: a red `.alert` item FIRST.
  2. Per early-failing system (162 gens qualify): *"**Ask for brake-hydraulics repair records.** This circuit fails at a median of 3,500 miles — on any car this age it already happened or never will; the question is whether it was fixed under warranty."*
  3. One item per curated known issue with its affected-years tag: *"**Check oil consumption** on 2010–2014 engines (documented problem)."*
  4. **AMENDED (judge-2 must-reject):** the original *"prefer 2012 or later — 2010 drew over 6x any later year"* is dead. Replace with a neutral pointer: *"**Complaint reports are not spread evenly across model years here** — see the by-model-year table below before you settle on a year."* No multiplier, no "avoid", no ranking verb.
  5. Closing: *"Aggregate data describes the population; end with a pre-purchase inspection of this car."*
- **Chart:** none.
- **Guardrail:** no "years to avoid" phrasing anywhere on the page — per-year counts conflate sales volume with exposure years; the H2's "Before you buy" phrasing captures the buying-guide query family without it. Coverage verified: every page has ≥2 checklist seeds, so the section never renders empty.

---

## 2. Ship this month (3 features)

### 2.1 "Where your car sits" — odometer section on every generation page
*(the merged odometer feature — three visions proposed it, judges said ship exactly ONE: owner's copy discipline + growth's static-anchors-first design + shopper's on-chart marker)*

- **Pages touched:** all 318 generation pages. New section after the Figure 2 systems table, `id="mileage"`. ~80 lines in `render_generation()` + ~80 lines inline dependency-free JS (allowed by D-009). Data is already in `generation_stats()` (`shape` percentiles + `systems` p25/median/p75) — no new pipeline stage.
- **Layout, static-first:** Python renders three anchor blocks at **60,000 / 90,000 / 120,000 miles**. Each anchor: one sentence + a two-group list. Real copy (Prius @ 90k):
  > *"At 90,000 miles: 76% of the failure reports on this generation came at or below this mileage. **That describes reports, not your odds.**"*
  > **Reported earlier than this mileage — ask for repair records:** *"Hydraulic brake circuit — median 3,500 mi. Reports this early describe a defect, not wear; if it hasn't happened by now, it likely won't."*
  > **In the reporting window:** *"Brakes — middle half 34,000–128,000 mi"*
  > **Mostly reported later:** *"Engine — middle half 63,000–134,000 mi · Hybrid propulsion — median 98,700 mi"*
- **JS enhancement:** one numeric input ("Your odometer: [ 91,000 ] miles → Go") reading a JSON blob embedded in a `data-` attribute (`{cdf bins, systems:[{name,p25,med,p75}]}`), re-partitioning the same three groups client-side. With JS off, the three static anchors stand alone and are the crawlable SEO surface.
- **Chart spec:** JS drops one vertical marker onto each existing Figure 2 strip: `<line class="you">` at `x = lx(odometer)` using the strip SVG's existing log scale from `charts.lx()`, full strip height, styled via CSS class, hidden until set. **No `<text>` in SVG** — the "Your car: 91,000 mi" label is an HTML span above the figure. (Log axis is fine here: strips are position/interval encodings, not area encodings.)
- **Guardrails:** group headers are "Reported earlier / In the window / Mostly reported later" — never "Likely already happened" (overclaims: most cars never file the complaint) and never "the next likely repairs" (prediction). Every sentence conditional on "owners who reported a failure". The "reports, not your odds" line is mandatory, above the groups.
- **QA:** 5-width DOM probe + press-every-button pass post-deploy (this breaks the fully-static convention; the blob schema is the one thing monthly regen can silently break).

### 2.2 Comparison pages — /compare/, ~120 pages at launch
*(the comparer/growth feature at growth's scope with comparer's honesty rules — judges: comparer version 8/8/6, growth version 8/6/7; judge 3 explicitly rejected the 550-page sizing in favor of ~120)*

- **Pages touched:** ~120 new pages. New pipeline stage `pipeline/compare.py` (pairing, nomination, canonical ordering); `render_comparison()` in `render.py` (~200 lines, reuses table/figure CSS); `system_strips_pair()` in `charts.py` (~60 lines reusing `lx()` and `axis_row_log()`); one-time curated `data/rivalries.json` (~30 model pairs: Camry↔Accord, CR-V↔RAV4, F-150↔Silverado↔Sierra, Civic↔Corolla, Odyssey↔Sienna…), resolved to the max-overlap generation pair; floor 300 complaints-with-miles per side, ≥3-year overlap. Sitemap + search-index one-liners.
- **URL:** canonical alphabetical slug order, reverse never generated: `/compare/honda-accord-2013-2017-vs-toyota-camry-2012-2017/`. **Slug-stability rule required:** pair slugs derive from generation slugs; if a generation's year range shifts in a rebuild, the old pair URL must redirect or persist — otherwise monthly regen silently 404s indexed pages (judge-3 flag).
- **Layout:** H1 *"Honda Accord 2013–2017 vs Toyota Camry 2012–2017"*. Verdict line, template, denominator-free: *"These two break differently. Accord complaints concentrate in the electrical system — 24% of its reports, median 48,000 miles. Camry complaints concentrate in the powertrain — 15% of its reports, median 70,000 miles."* The mandatory "complaints are not a failure rate" `.note` above the fold, same wording as generation pages. **Chart spec:** paired timing strips — for each shared system (union of top 6), two horizontal IQR bars on one log axis (`lx()`), side A solid `var(--bar-hi)`, side B `var(--bar)`; IQR endpoints printed as HTML labels exactly like the existing `system_strips()`; legend is HTML text, **no `<text>` in SVG**. Table: System | Accord share | Accord median (25–75%) | Camry share | Camry median (25–75%), standing footnote: *"Shares are of each car's own complaints: they show where each car's problems cluster, not how often each car has problems."* Then "Recall record": campaigns count, severe advisories, top recalled components, VIN-check link. One owner quote per side, tagged car + miles. Footer links to both generation pages.
- **Guardrails (all judge-2 must-rejects):** NO totals-vs-totals row anywhere — totals appear only in the dateline as provenance; NO side-by-side by-year complaint tables (growth's version of this element is rejected); NO cross-car severity-flag share rows (RAV4 fire 11.5% vs CR-V 0.9% is a rate comparison in disguise — permissible only as narrative anchored to the documented battery-fire campaign); verdict template never contains better/worse/winner.

### 2.3 "Cross-shopping this class?" rivals module
*(comparer F2 — judges 7 / 7 / 7; the honest variant of the related-block idea)*

- **Pages touched:** all generation pages with ≥1 nominated rival (~266 of 318; absent elsewhere, no filler). ~50 lines in `render_generation()`: fold the bare "Other generations" list (lines ~1120–1125) into one H2 **"Where next"** with two sub-lists: "Same car, other years" (existing links) and "Cross-shopping this class?" — max 3 rows.
- **Copy, real row (CR-V 2012–2016 page):** *"**Toyota RAV4 2013–2018** — complaints arrive later (median 21,210 vs 17,412 miles) and cluster in the electrical system rather than the engine. Compare side by side →"*
- **Pipeline:** reads the same nomination list `compare.py` produces for 2.2 — every "Compare →" link resolves by construction. Ships together with or after 2.2, never before.
- **Guardrails:** heading is "Cross-shopping this class?" — **never "Shoppers also checked"** (the site has no telemetry; that heading is fake social proof, house-rule violation). The clause template must always pair the median with the qualitative second clause ("and cluster in…") so a bare number never stands alone as an implied ranking. Medians/IQR/share-of-own-complaints only; raw totals banned.

---

## 3. Explicitly rejected

1. **Segment hubs `/class/…` (comparer)** — a median-sorted cross-rival table is a de facto reliability ranking; the encoding fabricates the finding regardless of the "not a ranking, a clock" caption, and it deliberately lands ranking-intent queries on it (judge 2: score 3, must-reject).
2. **System pages at 745-page scale (owner)** — triples the corpus (353 → ~1,100) and every build gate's blast radius for a 20-min/month operator (judge 3: score 4); revisit only as a ~50-page pilot after the checklist/compare wave proves out.
3. **Symptom-word table as specified (owner)** — naive substring counting fabricates safety counts: Escape engine "fire" = 1,010 by substring vs 331 with word boundaries (misfire/backfire contamination) — the site's fabricated-by-encoding failure mode at scale; blocked until word-boundary matching + per-term exclusions + full lexicon recount audit exist (judge 2 must-reject).
4. **Comparison pages at 550-page scope (comparer sizing)** — 4–5x more index-quality and QA-surface risk than needed to test the query class; the 120-page curated version ships instead (judge 3 must-reject of the sizing, not the feature).
5. **Side-by-side by-year complaint tables on compare pages (growth)** — raw totals from two differently-selling cars in one visual field is the totals-vs-totals D-007 violation (judge 2 must-reject).
6. **Checklist "prefer 2012 or later — 6x" / any "years to avoid" copy (shopper)** — per-year counts conflate sales volume and exposure years; the multiplier is the same confound the owner vision cuts from `years_narrative()` (judge 2 must-reject; replaced by the neutral pointer in 1.3).
7. **Cross-car severity-flag shares as a compared metric** — a rate comparison in disguise; narrative-only, anchored to a documented campaign (judge 2 must-reject).
8. **"Shoppers also checked" block as titled (growth)** — heading claims behavioral data that does not exist (fake social proof) and context-free median chips form a mini-ranking; superseded by 2.3 (judges 1 & 2 must-reject).
9. **Embeddable `/embed/` pages (growth)** — doubles the page count for speculative backlinks and creates an uncontrollable third-party rendering surface (judge 1: score 5). The salvageable half — `data/aggregates.json` and relabeling the misnamed "open data" link (it currently serves the editorial map, not the numbers) — survives as a ~40-line hygiene chore, not a roadmap feature.
10. **Visible freshness delta + sitemap lastmod (growth)** — answers no persona's question (judge 1: score 3, must-reject as product feature). The sitemap-lastmod fix is real honesty debt (all 353 URLs currently stamp today's date every build) — do it as a maintenance ticket outside this slate.
11. **"Likely already happened" group label (shopper odometer variant)** — overclaims; the mechanic ships in 2.1 with corrected labels, this phrasing does not.

---

## 4. Homepage verdict

All four visions agree the hero, search, and Prius demo work; they disagree only about what sits around them. Synthesis, in two steps:

**This week (zero risk, in `render_index()`, `render.py` line ~1165):** on viewports below ~768px, reorder so the search box renders directly under the H1, before the `.stats` dl — the wide-viewport grid already isolates it in its own column, so this is a mobile-only source-order swap. Change the search placeholder to the task: **"e.g. 2013 Escape"**. Nothing else moves.

**When /compare/ ships (2.2):** replace the "Most reported vehicles" `qpop` list — three of four visions independently want it gone (it silently reads as "worst cars" while meaning "best-selling cars", and a wall of discontinued 2000s sedans signals staleness) — with a two-row task block: **"Deciding between two cars? Popular comparisons"** (six curated pair links from rivalries.json: Camry vs Accord, CR-V vs RAV4, F-150 vs Silverado, Civic vs Corolla, Odyssey vs Sienna, Silverado vs Sierra) and **"Already own one? Check open recalls by VIN — free (NHTSA) ↗"**. That gives all three personas a first click above the fold.

**Rejected for the homepage:** the freshness delta beside the hero stats (part of rejected feature 10) and an interactive hero (no vision endorsed it; the static Prius demo with real numbers is the proof, not a toy).

## 5. The one-sentence product

**MileageCurve is the only site that can take a specific car generation and a specific odometer reading and tell you which reported failures typically arrived before that mileage and which come later — system by system, with each recall's free fix attached — because it is the only site that publishes failure timing, not just complaint counts.**

That sentence is honest after the week's ships alone; features 2.1–2.3 make the "specific odometer reading" clause literal instead of implied. What it still cannot claim, by design: anything about failure *rates* or which car is *better* — D-007 is the moat's fence, not a limitation to fix.

**Key file paths:** `D:\BiLingoPlus\web-properties\mileagecurve\pipeline\render.py` (features 1.1–1.3, 2.1, 2.3, homepage), `D:\BiLingoPlus\web-properties\mileagecurve\pipeline\analyze.py` (add `MIN(consequence)` to the recalls SELECT, ~line 186), `D:\BiLingoPlus\web-properties\mileagecurve\pipeline\narrative.py` (new `checklist_items()`, fold buying prose), `D:\BiLingoPlus\web-properties\mileagecurve\pipeline\charts.py` (new `system_strips_pair()`), new `D:\BiLingoPlus\web-properties\mileagecurve\pipeline\compare.py` + `data\rivalries.json` (2.2).