# MileageCurve — implementation punch list (one sitting)

**Nothing here is a hard AdSense blocker.** I checked: the application needs original content, working navigation, and a privacy policy — all present. What items 1–6 fix are the things a *reviewer actually opens* (policy pages, a sampled generation page, a clicked link) and the things that are factually false. They come first on that basis.

Line numbers below were re-read from disk today; several audit findings had drifted 4–10 lines and are corrected here.

---

## COMMIT A — "truth on the page" (no DB rebuild; full re-render at the end)

### A1. Screen owner quotes for third-party PII, and stop the privacy page asserting NHTSA already did it
*Merges findings 25 + the "Data about vehicles" half of 3/23.*

`pipeline/render.py`, quote loop at **1021–1037**. Add at module level, next to the other regexes:

```python
# NHTSA redacts the filer, not people the filer typed into the narrative.
_QUOTE_REJECT = re.compile(
    r"\b(?:\+?1[-. ])?(?:\(\d{3}\)\s?|\d{3}[-. ])\d{3}[-. ]\d{4}\b"  # phone
    r"|\[x{2,}\]"                                                    # [Xxx] redaction token
    r"|freedom of information act"
    r"|\b(?:mr|mrs|ms|dr)\.?\s+[A-Z][a-z]+",
    re.I)
```

In the loop, after `txt = names.sentence_case(...)` at **1025**, strip the NHTSA prefix and reject:

```python
            txt = re.sub(r"^tl\*\s*", "", txt, flags=re.I).strip()
            key = txt[:80].lower()
            if not txt or key in seen or _QUOTE_REJECT.search(txt):
                continue
```

The candidate pool is far larger than the 4 shown (`shown >= 4` break at 1036), so rejecting costs nothing.

`pipeline/render.py:1314–1318`, replace the "Data about vehicles" paragraph:

```python
         "<h2>Data about vehicles</h2>"
         "<p>The vehicle data shown here comes from public NHTSA records. NHTSA removes the "
         "identity of the person who filed, but complaint narratives are free text and can name "
         "other people or businesses. Quotes published here are screened for names, phone numbers "
         "and addresses before they appear. Nothing on this site is keyed to an individual, an "
         "address or a vehicle identification number. If a quote still carries identifying "
         f'detail, <a href="mailto:{CONTACT}">tell us</a> and it comes down.</p>',
```

**Visible change:** `/kia-sorento-2016-2020/` no longer publishes "district manager, barry zoll from Kia motors america 732-372-8295"; `/hyundai-elantra-2017-2020/` loses the dealer street address and phone; `/acura-mdx-2007-2013/` loses the FOIA boilerplate pull-quote; the 13 `[Xxx]` quotes are replaced by the next clean candidate.

**Verify in a browser:** those four URLs, plus one page that had exactly 4 quotes before, to confirm it still shows 4 and not 2.

---

### A2. Sibling nav links to 179 pages that were never built
*Finding 16. Highest reader impact in the set.*

`pipeline/render.py:1366–1381` — the build loop passes the **full** `gens` list as siblings while skipping thin generations. Replace with:

```python
        gens = m["generations"]
        st = {id(g): analyze.generation_stats(con, m["make"], m["model"],
                                              int(g["year_start"]), int(g["year_end"]))
              for g in gens}
        live = [g for g in gens if st[id(g)]["complaints_with_miles"] >= MIN_WITH_MILES]
        skipped += len(gens) - len(live)
        for g in live:
            s = st[id(g)]
            out = DIST / slug(m["make"], m["model"], g["year_start"], g["year_end"])
            out.mkdir(parents=True, exist_ok=True)
            (out / "index.html").write_text(
                render_generation(s, g, m, live), encoding="utf-8")   # live, not gens
            index.append({...})          # unchanged
            built += 1
            if args.limit and built >= args.limit:
                break
```

`siblings` is consumed at exactly one place (`render.py:1047`, `rel = [g for g in siblings if g is not gen]`) and identity comparison still holds because `live` holds the same dict objects. No extra queries — `generation_stats` still runs once per generation.

Then add the gate, in `main()` alongside the existing `problems` loop at **1455**, scoped to full builds only (`--limit`/`--only` will always dangle):

```python
    if not args.limit and not args.only:
        for f in sorted(DIST.rglob("*.html")):
            body = re.sub(r"<style>.*?</style>", "", f.read_text(encoding="utf-8"), flags=re.S)
            for href in set(re.findall(r'href="(/[^"#?]*)"', body)):
                tgt = (DIST / href.strip("/") / "index.html") if href.endswith("/") \
                      else (DIST / href.lstrip("/"))
                if not tgt.exists():
                    problems.append(f"{f.relative_to(DIST)}: битая ссылка {href}")
```

**Visible change:** `/acura-mdx-2001-2006/` no longer offers "MDX 2022–2025"; 179 dead links across 158 pages disappear. Page count stays 353.

---

### A3. Injury and fatality figures are counts of PEOPLE printed as counts of COMPLAINTS
*Finding 31. Wrong on 315 of 318 pages, in the harm-inflating direction.*

`pipeline/analyze.py:169`:

```python
        "SELECT SUM(crash), SUM(fire), SUM(injured > 0), SUM(deaths > 0) FROM complaints "
```

`crash`/`fire` are already 0/1 flags; `injured`/`deaths` are person counts. The surrounding sentence at `narrative.py:236` is explicitly about complaints, so counting complaints is the right side to change.

Also relabel the CLI print at `analyze.py:232–233` — "пострадавших/погибших" becomes "жалоб с пострадавшими / с погибшими", or it now lies in the console instead of on the page.

**Visible change:** `/ford-explorer-1995-2001/` goes from "1,473 reported an injury; 177 reported a fatality" to 864 / 132. Prius: 280→212, 5→3.

---

### A4. Same quantity printed as 49% and 48% on the same page
*Finding 33. Four pages, two-line fix, cheapest thing on the site for a critic to screenshot.*

`pipeline/analyze.py:121–122`, add the precomputed late figure next to the existing `early_pct`:

```python
        "early_share": round(early, 3), "early_pct": early_pct,
        "late_share": round(late, 3), "late_pct": int(round(late * 100)),
```

`pipeline/narrative.py` — replace all four re-computations:
- **259** `{sh['early_share'] * 100:.0f}%` → `{sh['early_pct']}%`
- **262** `{sh['late_share'] * 100:.0f}%` → `{sh['late_pct']}%`
- **267** `{sh['early_share'] * 100:.0f}%` → `{sh['early_pct']}%`
- **273** `{sh['late_share'] * 100:.0f}%` → `{sh['late_pct']}%`

Same bug in `analyze.py:109` — `f"{late:.0%} of failures occur beyond 100,000 miles"` re-rounds the raw float; change to `f"{int(round(late * 100))}% of failures..."` (or hoist `late_pct` above the classifier and use it).

Root cause of both: `round(x, 3)` then `:.0f` is round-half-even on a `.5` value. The comment at `analyze.py:86` shows this was fixed once already in `analyze.py` and reintroduced in `narrative.py`.

**Visible change:** Prius reads 49% in all three places instead of 49 / 49 / 48. Elantra 29, Mazda3 31, Altima 45 likewise.

---

## COMMIT B — DO NOT DRIVE (requires a **DB rebuild** before re-render)

### B1. Parser + recall-table ordering + truncation note
*Merges findings 1 + 37 — same 25-row slice is the cause of both.*

`pipeline/build_db.py:97–98`:

```python
def yn(s: str) -> int:
    return 1 if s.strip().upper().startswith("Y") else 0
```

The NHTSA file writes `Yes`/`No`, so `== "Y"` stored 0 for all 217,256 rows. Field 27 = do-not-drive (2,126 Yes), field 28 = park-outside (1,271 Yes); column order was already correct.

Gate it so this cannot return silently — after the recall load in `build_db.py`:

```python
    dnd, po = con.execute("SELECT SUM(do_not_drive), SUM(park_outside) FROM recalls").fetchone()
    if not dnd or not po:
        raise SystemExit(f"шлюз: в отзывах нет тяжёлых предупреждений (dnd={dnd}, po={po})")
```

`pipeline/render.py:1011` — the 25-row slice would hide most badges. Sort severe first (stable, so date order survives within each group):

```python
        rows = sorted(s["recalls"], key=lambda r: not (r["do_not_drive"] or r["park_outside"]))
        for r in rows[:25]:
```

And after `B.append("</tbody></table></div>")` at **1019**:

```python
        if s["recalls_count"] > 25:
            B.append('<p class="meta">Showing 25 of '
                     f'{fmt(s["recalls_count"])} campaigns — severe advisories first, then most '
                     'recent. The full list is at '
                     '<a href="https://www.nhtsa.gov/recalls">NHTSA</a>.</p>')
```

`.meta` already exists at `render.py:406`.

**Visible change:** 61 generation pages gain red `do not drive` / `park outside` badges (kia-sportage-2017-2022 has 47 such campaigns, kia-sorento-2016-2020 has 35). 23 pages — including `/ford-explorer-2020-2025/` (62 campaigns) and both F-150 generations — stop claiming 55 and showing 25 with no note. `.alert` CSS at render.py:534/538 stops being dead.

**Sequence:** run `build_db.py` before `render.py` here. Everything else in this list re-renders from the existing DB.

---

## COMMIT C — policy and disclosure copy

### C1. Stop asserting an ad stack, a CMP and an analytics product that do not exist
*Merges findings 3, 23, 24, and the footer/terms half of each — one underlying cause: copy written for the post-AdSense site, shipped on the pre-AdSense site.*

Add one constant at the top of `render.py` and use it everywhere the ad stack is described, so copy, `ads.txt` and the ad label can never drift apart:

```python
ADS_LIVE = False   # → True on the same commit as the AdSense publisher id
AD_DISCLOSURE = ("<p>This site carries third-party display advertising. Advertisers have no "
                 "input into what is published.</p>") if ADS_LIVE else ""
```

**`render.py:888–889`** (footer, all 353 pages) — replace the literal paragraph with `{AD_DISCLOSURE}`.

**`pages.py:142–144`** (`/terms/` → "Third parties") — present tense → future:

```python
         '<p>This site links to external sites, including manufacturer and regulator pages, and '
         'will carry third-party display advertising. We do not control that content and are not '
         'responsible for it.</p>',
```

**`render.py:1301–1303`** ("What we collect") — there is no analytics beacon on any page:

```python
         "<p>The hosting provider keeps standard server request logs (page requested, referrer, "
         "approximate location, browser type) for security and to see which pages are used. "
         "There is no analytics script on this site and nothing here is used to identify you.</p>",
```

**`render.py:1305–1313`** ("Advertising") — the false present tense:

```python
         "<h2>Advertising</h2>"
         "<p>This site does not yet carry advertising and sets no cookies of its own. When "
         "advertising is added, partners may set cookies or use similar technology to serve and "
         "measure ads. Visitors in the European Economic Area and the United Kingdom will be "
         "shown a consent choice before any non-essential cookie is set, and that choice will be "
         "changeable at any time. This page will be updated on the day that happens.</p>"
```

Then add a US-state section with a stable anchor (the audience is 100% American and there is currently nothing for them):

```python
         '<h2 id="us-state-rights">US state privacy rights</h2>'
         "<p>Residents of California, Colorado, Connecticut, Virginia and other states with "
         "comprehensive privacy laws have rights to access, correct and delete personal "
         "information, and to opt out of its sale or of targeted advertising. This site does not "
         "sell or share personal information today and runs no advertising. When advertising is "
         "added, personalised ads count as sharing or targeted advertising under those laws, and "
         "an opt-out will be published here before any ad is served. To exercise a right or ask "
         f'what is held, write to <a href="mailto:{CONTACT}">{CONTACT}</a>.</p>',
```

Add `<a href="/privacy/#us-state-rights">Your privacy choices</a>` to the footer nav at `render.py:882–884`.

**Do NOT write "this site honours Global Privacy Control signals."** GPC honouring is an ad-partner configuration, and claiming it before a partner is configured recreates exactly the defect this item fixes.

**Architectural decision to make now, not at go-live:** every Google-certified CMP is an external script. Constraint D-009 (zero external requests) and personalised EEA/UK ads are mutually exclusive. Either D-009 gets a documented, scoped exception for the CMP, or EEA/UK traffic is served non-personalised. Write the answer into `MEMORY.md` this sitting — it changes what the policy text should say a month from now.

**Visible change:** `/privacy/`, `/terms/` and the footer of all 353 pages stop describing a stack that isn't installed; a reviewer who reads the policy and opens devtools finds them consistent.

---

### C2. Russian editorial text in the shipped open-data file, and the gate that structurally can't see it
*Merges findings 2 + 39 — identical.*

`pipeline/normalize_generations.py:139–141`, replace the note with the English the site already uses on-page:

```python
    "Both the outgoing and incoming generation were sold in this model year; "
    "NHTSA records do not separate them."
```

The field is never rendered (generation pages emit `<span class="tag">mixed</span>` at `render.py:1000`), so nothing on-page changes — but it ships verbatim. Belt and braces at the copy site, `render.py:1446–1447`:

```python
    _gens = json.loads(GENS.read_text(encoding="utf-8"))
    for _m in _gens:
        for _g in _m.get("generations", []):
            _g.pop("mixed_year_note", None)   # внутренняя заметка, не для публикации
    (DIST / "data" / "generations.json").write_text(
        json.dumps(_gens, ensure_ascii=False, indent=1), encoding="utf-8")
```

**The valuable half is the gate.** Both gates are HTML-only, which is why this survived:

`render.py:1456`:
```python
    SHIPPED = (".html", ".json", ".xml", ".txt", ".css", ".js")
    for f in sorted(p for p in DIST.rglob("*") if p.suffix in SHIPPED):
```
The dash/CSS regex should stay scoped to `.html` inside that loop (it false-positives on prose colons — see "not doing" below); the Cyrillic and control-character checks apply to all of them.

`.github/workflows/build.yml` — the CI gate has the same blind spot: `grep -rlP '[\x{0400}-\x{04FF}]' dist --include='*.html'`. Drop `--include`.

**Visible change:** `curl https://mileagecurve.com/data/generations.json` returns 618 KB with zero Cyrillic. This is [[read-the-rendered-output]] recurring in the one shipped artifact that has no rendered form.

---

### C3. Dates that report the clock instead of the data
*Merges findings 5, 18, 28 — one cause: seven `date.today()` calls doing three different jobs.*

`grep -n 'date.today()' pipeline/*.py` → render.py **886, 917, 1043, 1252, 1321, 1332** and pages.py **126**. Three jobs, three fixes:

**Snapshot / coverage claim** (886, 917, 1043, 1252). Load the real dates once at module init:

```python
_MF = json.loads((ROOT / "data" / "manifest.json").read_text(encoding="utf-8"))
SNAPSHOT = min(v["fetched_utc"] for v in _MF.values())[:10]
```
Use `SNAPSHOT` for "Snapshot {…}" at 886/1043/1252. For the dateline at **917**, the only honest phrasing of a coverage claim is the newest record, not the build date:
```python
DATA_THROUGH = con.execute("SELECT MAX(date_filed) FROM complaints").fetchone()[0]
```
→ `NHTSA data through {datetime.strptime(DATA_THROUGH, "%Y-%m-%d").strftime("%d %B %Y")}`.
Today that changes "12 August 2026" to "09 August 2026" — a 3-day overstatement that grows to a month after any render-only rebuild.

**Policy revision dates** (render.py:1321, pages.py:126). Module constant, bumped by hand when the text changes:
```python
POLICY_UPDATED = "2026-08-13"   # менять ТОЛЬКО когда правится текст политики
```
Both pages currently claim a revision on every deploy, which destroys the one thing that field exists for.

**Sitemap lastmod** (render.py:1332). Today every rebuild tells Google all 352 URLs changed — the fastest way to teach a crawler to ignore the signal. Hash-keyed manifest:

```python
prev = json.loads((ROOT / "data" / "lastmod.json").read_text(encoding="utf-8")) \
       if (ROOT / "data" / "lastmod.json").exists() else {}
new = {}
# after each page write:
h = hashlib.sha256(html.encode("utf-8")).hexdigest()[:16]
rec = prev.get(url)
new[url] = {"hash": h, "date": rec["date"] if rec and rec["hash"] == h else today}
```
`render_sitemap` then emits `new[url]["date"]`; write `new` to `data/lastmod.json` at the end. First build after the change is a no-op (everything gets today); every build after it is honest.

**Visible change:** the dateline stops drifting away from the data; `/privacy/` and `/terms/` stop claiming monthly revisions they never had; sitemap lastmod becomes a real signal on the next NHTSA refresh.

---

## COMMIT D — the remaining data-truth items (text only, zero build risk)

### D1. "a rate roughly 11 times higher" — the one thing the site says it never does
*Finding 32. 61 pages, largest non-heading type, contradicted three times on the same page.*

`pipeline/analyze.py:105–106`:

```python
        note = (f"{early_pct}% of complaints that record mileage fall within the first 12,000 "
                f"miles, against {d_mid:.0f} reports per 1,000 miles between 20,000 and 80,000.")
```

The quantity is complaint density per odometer-mile across two windows, not a rate. The number itself is fine (density falls monotonically past 12k, so 20k–80k is the conservative comparison window) — the word is the defect.

### D2. `/methodology/` documents the algorithm that was removed as the fabrication bug
*Finding 34.* `pipeline/render.py:1225` still says the shape label comes from *shares*; `analyze.py:94–99` classifies on *density*. Rewrite:

```python
    "The shape label — early, late or spread — is derived mechanically from complaint density "
    "(reports per 1,000 miles) in three windows: 0–12,000, 20,000–80,000 and 100,000–200,000 "
    "miles. Density, not share, because windows of different width are not comparable as shares. "
    "No judgement is applied."
```
Drop "two separate populations" from the list — `page_index.json` shape counts are spread 246, early 61, late 11, **bimodal 0**, so the page offers a label no page can show.

### D3. `names.round_miles` bypassed throughout `narrative.py`
*Finding 35. 317 of 318 pages print the same median two ways.*

`narrative.py` has no `import names`. Add it, then wrap lines **85, 89, 101, 107, 112, 116, 276, 281, 291**:
```python
    med = names.round_miles(x["median_miles"])
    ... f"{fmt(names.round_miles(sh['p25']))} and {fmt(names.round_miles(sh['p75']))} miles"
```
**Visible change:** prose "a median of 58,847 miles" becomes "59,000", matching the systems table two inches above it. `names.py:78–81`'s docstring names this exact adjacency as its reason to exist.

### D4. `/about/` promises a forum-sourcing tag that can never fire
*Finding 36. 960 unsourced defect claims.* `source_strength` is absent from all 960 `known_issues` entries in `data/generations.clean.json`, so `render.py:990`'s `tag-weak` path is unreachable and the /about/ sentence is unbacked. Cheapest honest fix — one line under the "Documented problems" heading:

```python
        B.append('<p class="meta">Compiled from manufacturer bulletins, recall filings and owner '
                 'reports. Unlike the figures above, these are editorial summaries, not computed '
                 'from the NHTSA files.</p>')
```
and soften the /about/ sentence at `render.py:~1287` to match what ships. Populating `source_strength` properly is a data project, not this sitting.

### D5. `by_year` carries a MEAN under the key `median_miles`
*Finding 38.* `analyze.py:159` keys `(SELECT AVG(miles) …)` as `"median_miles"`. Currently unrendered, so no page defect — rename it now: `"mean_miles": int(m) if m else None`. One word, and it removes a landmine of exactly the histogram-binning class for whoever next adds a median column to the year table.

---

## COMMIT E — CSS and interaction states (visual; needs a browser check)

*Merges findings 10, 11, 12, 13, 14 — one file, one rebuild, all token-level.*

| # | File:line | Change |
|---|---|---|
| E1 | `render.py:681` | `color:#fff` → `color:var(--bg)` on `.qbox button`. Fixes 2.22:1 (1.73:1 on hover) white-on-mint in dark. Checks out in all four states: 5.94 / 8.66 / 8.34 / 10.80, and the print block (`--bg:#fff`, `--accent:#000`) stays white-on-black. |
| E2 | `render.py:676–677` | Delete `outline:none` and the `box-shadow:0 0 0 3px var(--track)` (the ring is 1.10:1 — invisible). Leave `.qbox input:focus-visible{border-color:var(--accent)}`; the global `:focus-visible` at `render.py:200` then applies. This is the only `outline:none` in the file. Light mode was weak-but-passing (3.05:1 state change); **dark was failing** (1.83:1, and the border got *dimmer* on focus). |
| E3 | `render.py:516` | `tbody tr:nth-child(even)>*{background:var(--track)}`. `--bg` on `--surface` is 1.04:1 in light — the zebra the source comment lists as a feature simply does not render. `--track` measures dE00 3.44, still weaker than the `--warn` hover (5.91) so hover keeps reading as selection. |
| E4 | `render.py:628` | Add `--tick:#fff;` to the print `:root`. It is the only chart token the print block forgets to reset. Live impact is likely zero (modern Firefox and Chrome both force light for printing) — include it because it costs one declaration and the omission is plainly unintentional. |
| E5 | `charts.py:288` | `'the pale tick is the median'` → `'the notch inside each bar is the median'`. In dark, `--tick` is `#111413` — the darkest ink in the palette. Contrast passes; the word is wrong. No CSS change. |

**Must be confirmed in a real browser, not assumed:** E1–E3 at 360px, 768px and 1400px, in **both** schemes, with an actual Tab into the search box. E3 in particular — the `.tw` scroll-cue gradients sit under the even-row cells and I have only verified that on paper.

---

## COMMIT F — search widget (`pipeline/search.py`, homepage only)

*Merges findings 40, 41, 44, 45, 15.*

**F1 (the real one).** `load()` at **43–56** throws away the callback while the index is in flight, and the focus handler at **150** has already parked the no-op in `x.onload`. Queue instead:

```js
  var idx = null, loading = false, pending = [], lastQuery = '', active = -1;
  function load(cb) {
    if (idx) { cb(); return; }
    pending.push(cb);
    if (loading) return;
    loading = true;
    var x = new XMLHttpRequest();
    x.open('GET', '/search-index.json', true);
    x.onload = function () {
      if (x.status && x.status >= 400) { loading = false; pending = []; return; }
      try { idx = JSON.parse(x.responseText); } catch (e) { idx = []; }
      loading = false;
      var q = pending; pending = [];
      for (var i = 0; i < q.length; i++) q[i]();
    };
    x.onerror = function () { loading = false; pending = []; };
    x.send();
  }
```
Reproduced under a DOM shim with a 300 ms fetch: focus, paste "prius", index lands, panel stays empty. It self-heals on the next keystroke, so it only bites pastes/autofill on slow mobile — which is why it will never reproduce on the dev machine. The `x.status` guard matters separately: a 404 today parses as a throw, sets `idx = []`, and `[]` is truthy, pinning the box to "Nothing matches" for the rest of the session with no retry.

**F2.** `search.py:155` — `else if (e.key === 'Escape') { box.value = ''; lastQuery = ''; render([], ''); }`. Escape strands `lastQuery`, so re-entering the identical string in one input event renders nothing. *Do not touch line 161* — the audit misquoted it; it is `box.focus(); render([], '')` and does not clear the value, so adding a clear there would be a behaviour change, not a fix.

**F3.** `search.py:104` and **99** — delete `role="listbox"` and `role="option"`. ARIA makes `option` children-presentational, so the `<a>` is not exposed as a link, yet the keydown handlers move real DOM focus into exactly that link; and an orphan listbox with no `role="combobox"` owner announces nothing when results appear. A plain list of links is honest, and the arrow/Escape handlers query `.qr-list a`, which is untouched.

**F4.** `search.py:182` — hardcoded `318 generations` beside two computed counts. `def search_markup(n: int)` → `f'…{n:,} generations · type a model…'`, called as `search.search_markup(len(index))` at `render.py:1118`. They agree today by coincidence; the next NHTSA rebuild puts two totals within 300px of each other.

**F5.** `search.py:177` — `action="/"` reloads the homepage with the query dropped. `action="/#makes"` at least lands the reader on the makes list (`<h2 id="makes">` exists at `render.py:1167`). Fix the misleading docstring at **11–12** either way.

**Confirm in a browser:** F1 with devtools network throttled to Slow 3G — paste, don't type.

---

## COMMIT G — head/meta (one `page_shell` signature change serves four items)

`render.py:838` — `page_shell(...)` currently emits no robots meta and always emits canonical + `og:url`. Add two optional params:

```python
def page_shell(title, desc, body, canonical, script="", wide=False,
               gen=False, nav_key="", robots="", crumbs=None):
```
Emit `<meta name="robots" content="{robots}">` when set; skip the `<link rel="canonical">` and `og:url` lines when `canonical` is falsy.

- **G1 (finding 4):** `pages.py:94` — pass `canonical=""` and `robots="noindex"` for the 404 page. Today `/404` serves **HTTP 200** with the not-found body and canonicals at `/404.html`, which 308s straight back to `/404`. Also add `/404 /404.html 404` to `dist/_redirects` (written at `render.py:1435`).
- **G2 (finding 27):** `pages.py:35` `make_hub` — when `len(pages) < 4`, pass `robots="noindex,follow"` and exclude the hub from `render_sitemap`. That is 13 hubs; `/lexus/`, `/saturn/` and `/oldsmobile/` are one sentence plus one link. They stay reachable and keep passing equity; 13 near-empty URLs leave the crawl surface. *(For the record: the 318 generation pages are **not** thin — 1,132–2,045 prose words, median 1,700. The hubs are the only thin-content exposure.)*
- **G3 (finding 19a):** add `robots="max-image-preview:large"` as the default and switch `render.py:855` to `content="summary_large_image"`. Two harmless lines. **Skip part (b)** — see below.
- **G4 (finding 42):** pass the existing-but-never-supplied `nav_key` at the four institutional call sites — `render.py:1190` `nav_key="home"`, `:1254` `"method"`, `:1292` `"about"`, `:1322` `"privacy"`. `_cur()` at `render.py:813` and the CSS at `render.py:230` are already written and currently dead; `aria-current="page"` appears on 0 of 353 pages.

---

## COMMIT H — SERP presentation

**H1 (finding 17). BreadcrumbList JSON-LD.** Zero structured data on 353 pages, while 346 already emit a real `<ol class="crumbs">` — Google does not read a bare `<ol>`. Using the `crumbs` param added in Commit G:

```python
    ld = ""
    if crumbs:   # [("Home","/"), ("Toyota","/toyota/"), ("Prius 2010–2015", None)]
        items = [{"@type": "ListItem", "position": i, "name": n,
                  **({"item": DOMAIN + u} if u else {})}
                 for i, (n, u) in enumerate(crumbs, 1)]
        ld = ('<script type="application/ld+json">'
              + json.dumps({"@context": "https://schema.org", "@type": "BreadcrumbList",
                            "itemListElement": items}, ensure_ascii=False, separators=(",", ":"))
              + '</script>')
```
Insert `{ld}` before `</head>`; pass the three labels already built at `render.py:901–903`, two from the make hub. `json` is imported at `render.py:14`; `DOMAIN` in `render.py` is the site URL (note `charts.py` has a *different* `DOMAIN` that is a mileage number — no collision, the patch lives in render.py). **Skip FAQPage** (restricted to gov/health since 2023) **and Dataset** (Dataset Search sends no consumer traffic).

**Changes:** SERP lines go from `mileagecurve.com › toyota-prius-2010-2015` to `MileageCurve › Toyota › Prius 2010–2015` on the main traffic surface.

**H2 (finding 21). h1 → h3 skip on 319 pages.** `charts.py:179` and `:293` hardcode `<h3 class="fig-title">`. Add `level: str = "h3"` to `histogram()` and `system_strips()`, emit `f'<{level} class="fig-title">…</{level}>'`, and pass `level="h2"` at the two lead-exhibit call sites (`render.py:932`, `render.py:1153`). Leave the in-section call at default. **Verified visually neutral:** `.fig-title` (`render.py:304`) resets margin/padding/border and restates family/weight/size/line-height, and class specificity beats element — no CSS change needed.

**H3 (finding 22). 54 titles over 60 chars.** `render.py:870`:

```python
    head = f"{make} {model} {years}"
    title = (f"{head} — what breaks and at what mileage"
             if len(head) <= 26 else f"{head} — common problems by mileage")
```
Tested against all 318 real heads: over-60 titles drop from 54 to 8, worst case 69 → 64 chars, both query terms survive, titles stay unique (make/model/years prefix is unique per page).

---

## COMMIT I — housekeeping (do last, or drop if the sitting runs short)

**I1 (findings 7 + 29 + 30). Gate the ad plumbing on the same `ADS_LIVE`/publisher-id constant from C1.**
- `render.py:1441–1442` — emit `dist/ads.txt` **only** when a publisher id is set. A present file with zero records is a positive declaration that no seller is authorised; an absent file is "unknown, proceed". At approval: `google.com, pub-XXXXXXXXXXXXXXXX, DIRECT, f08c47fec0942fa0`.
- `render.py:976, 1021, 1074` — keep the reserved `.ad` box (min-height 316/636px preserves the zero-CLS reservation) but emit `<span class="ad-label">` only when ads are live. Today 318 pages show 1,268px of boxes labelled ADVERTISEMENT over empty space. *For the record, the placement discipline measured clean: ~12% reserved ad area, first in-flow unit at 3,380px, nothing between h1 and the first figure, zero slots on 404.*
- Fail the build if ad slots are enabled while the id is unset, so the file and the ads can never disagree.

**I2 (findings 9 + 46). Dead CSS, ~900 b × 353 pages.** Delete: `.creds` and `figure.chart` from the `max-width:none` group at **190**, the `figure.chart` rule at **292**, `figure.chart` from the print rule at **638**, `.badge` from **534**, `.lede strong` at **657**, `blockquote.quote cite a` at **530**, and the fully-shadowed bare `.pct` (**395**) / `.pct>div` (**398**) — all 318 `<dl class="pct">` sit inside `.fig-foot`, where `.fig-foot .pct` (**389–393**) overrides every property. **Keep `.alert`** (starts firing after Commit B) and **`.tag-weak`** (live path, D4 explains why it never fires) — mark both conditional in the section comment. Move the six-line histogram comment at **285–290** up to the `figure.fig` block it now describes. Close the two hook-with-no-rule pairs: `histfig` (charts.py:177) and `band-b` (charts.py:283).

Worth stating: on the axes where corruption was expected, none was found — no duplicate properties, no repeated selectors, no control characters, no mangled escapes, every media context reachable, every `var(--x)` defined and every token used.

---

## OFF-BUILD (do these in parallel — no rebuild, no pipeline file)

**J1 (finding 20). `www.mileagecurve.com` is NXDOMAIN.** `curl https://www.mileagecurve.com/` cannot resolve. Any typed or linked www address dies with a browser DNS error and any www backlink passes nothing. In Netlify: Domain settings → add domain alias `www.mileagecurve.com`, apex stays primary; Netlify issues the cert and 301s. Canonicals already point at the apex, so no page changes. **Cheap now, expensive once links exist — do it before any outreach.**

**J2 (finding 8). Repo contradicts `/terms/`.** `bilingoplusllc/mileagecurve` is public with `license: null` and no LICENSE at root, while `/terms/` claims "The pipeline source is MIT-licensed" and CC BY 4.0 aggregates. Add `LICENSE` (MIT) and a README section stating CC BY 4.0 for the generated aggregates — one commit, no site rebuild, makes an existing sentence true. Separately: 17 of 27 commits on main have Cyrillic subjects, while `/contact/` and `/about/` route readers there specifically so outsiders can read the record. **Switch commit messages to English from here on.**

---

## NOT DOING — and why

- **Finding 6 (make-hub `key * 6` clipping).** The repetition is a deliberate, commented workaround for a real CSS limitation (auto-fill's column count is unreadable from CSS), `aria-hidden="true"` already removes it from the accessibility tree, and the duplicated strings are three generic UI words — not the hidden text Google's spam policy targets. The proposed fix sets `ul.gens{grid-template-columns:1fr}`, collapsing every make hub from a multi-column index to a single column: a visual redesign of a layout that shipped yesterday, justified by Ctrl+F noise. If the single-column form is ever wanted on its own merits, revisit then.
- **Finding 19(b) (hand-rolled PNG encoder for OG cards).** ~35 lines of `zlib`+`struct` raster code plus a text-rendering problem, added to a generator whose entire value is that it is stdlib and boring. The payoff is Discover eligibility on a channel this site has never had. Ship 19(a) (two lines) and accept bare social cards; revisit if Discover ever matters.
- **Finding 43 (replace the CSS-corruption regex with a structural `css_gate`).** The blind spots are real — `var(—s-4)`, `font–size:15px`, NBSP separators and `display:` all pass today — but the CSS is currently clean, zero pages trip anything, and the proposed replacement needs work before adoption (it flags any non-ASCII dash inside a declaration, so a legitimate `content:"—"` fires it, and it splits on `;` regardless of `url()`/quotes). The "corrupt dist left on disk" sub-point is moot in CI: `build.yml` deploys in a later step, so a non-zero `render.py` exit already blocks it. **Do keep the one cheap half:** scope the existing dash regex to `.html` only when widening the file glob in C2, so a future em dash after a colon in an owner quote can't halt the build.
- **Finding 12's severity, 13's severity, 14's impact** — folded into Commit E as one-liners, but none of them is a comprehension failure and none should hold up the sitting.

---

## Sequence

```
1.  Commit A   (A1–A4)  ── render.py, analyze.py, narrative.py, build gate
2.  build_db.py rebuild ── REQUIRED before any further render
3.  Commit B   (B1)
4.  Commit C   (C1–C3)  ── can land together with A/B; all string + manifest work
5.  Commit D   (D1–D5)
    ── FULL 353-PAGE REBUILD HERE, then browser-check A1/A2/B1 on live paths ──
6.  Commit E   (E1–E5)  ── CSS only; rebuild + browser check at 360/768/1400 × light/dark
7.  Commit F   (F1–F5)  ── search.py; rebuild + throttled-network check
8.  Commit G+H (G1–G4, H1–H3) ── one page_shell signature change serves both; rebuild
9.  Commit I   (I1–I2)  ── rebuild, confirm page count still 353
J1/J2 run in parallel at any point — no rebuild, no pipeline file.
```

**Rebuild gates:** the DB rebuild after step 1 is the only one that is not optional-until-later. Steps 4–9 can each re-render from the existing DB. Do **not** run any of these with `--limit`/`--only` once the new dead-link gate is in — it is deliberately scoped to full builds, and a partial build will always dangle.

**Confirm in a real browser, never assume:** E1–E3 (contrast and focus in both schemes), F1 (throttled to Slow 3G, paste rather than type), B1 (the badges actually render red inside the recall table cells, not just in the DOM), G1 (`/404` now returns 404 and not 200 — the `_redirects` change is Netlify-side and cannot be verified from `dist/`).

**One caution carried forward from verification:** the audit's per-page counts were mostly exact, but one finding claimed "I checked all 318 published generations; these are the only two affected" for the recall truncation and the real number is **23**. Re-count from `dist/` after the rebuild rather than trusting any page count in the findings text.