## MileageCurve — final implementation spec (direction: **newsroom**, grafted)

All line numbers are `D:\BiLingoPlus\web-properties\mileagecurve\pipeline\render.py` and `…\charts.py` as they stand today. Ship in this order; steps 1–4 are the verdict flip.

### Facts I verified in the repo before writing this (use these, not the numbers in the four direction docs)

| Claim in the directions | Truth in the repo |
|---|---|
| `.demo h2{max-width:22ch}` | **False.** `render.py:479` is `max-width:30ch`, and `render.py:478` already ships `.demo h2,#makes{border-top:none;padding-top:0;margin-top:0}`. Newsroom is the only direction that quoted this correctly. |
| Corrupted About number = 180,000 / 200,000 / 240,000 | **All three wrong.** Recovered from git: `git show 7c131d6:pipeline/render.py` line 436 = **`fails at 140,000`**. |
| The em-dash corruptions are random | **They are mechanical.** `git diff 0b08d13 8fdb261 -- pipeline/render.py` shows one bad pass replaced every literal `14`→`—` and `13`→`–`. Originals recovered: `transparent 14px`, `padding:12px 14px`, `/* ---------- 13. ad slots`, `/* ---------- 14. provenance`. |
| Site totals 1,483,921 / 982,140 (newsroom) or 2,116,934 / 1,108,272 (firstfive) | **Both wrong.** DB `meta`: complaints **2,116,532**, recalls **217,256**; `COUNT(*) WHERE miles IS NOT NULL` = **1,108,224**. 318 generations, 28 makes. **Never hardcode these — they already arrive as `stats[...]`.** |
| Prius rail snapshot "14 recalls" (newsroom) | **Wrong**, `recalls_count` = **12**. Complaints 5,725 / with mileage 3,988 are right. |
| `.idx-make` has zero producers | **Confirmed** — `grep -o 'class="idx-make"' -r dist` = 0. |
| `.k-med` has no CSS rule | **Confirmed** — `charts.py:123` emits it, no rule anywhere in `CSS`. |
| `--bar` #7e938e on `--warn` | **2.89:1** (recomputed). `#758a85` = **3.25:1** on `--warn`, 3.66:1 on white, 3.10:1 against `--bar-hi`. |
| newsroom's log geometry | **All correct.** lx(1000)=115.7, lx(3500)=324.8, lx(10000)=500.0 exactly, lx(12000)=530.43 → `--edge-pct:53.04%`, axis columns 11.569×6 + 15.293×2 = **100.000%**. |

---

## STEP 1 — Repairs and build gates. Nothing else ships before this. (risk: zero, impact: removes four live "unmaintained site" tells)

**File: `render.py`, line 339–340** (inside `.tw`)

```css
    linear-gradient(to right,var(--shadow),transparent 14px),
    linear-gradient(to left,var(--shadow),transparent 14px);
```

**File: `render.py`, line 383**

```css
ul.rel a{display:block;padding:12px 14px;line-height:1.35;font-size:var(--f-sm);
```

**File: `render.py`, line 391 and 402** (comment headers, restore the numbering)

```css
/* ---------- 13. ad slots ---------------------------------------------------
/* ---------- 14. provenance strip and footer -------------------------------- */
```

**File: `render.py`, line 940** — restore the value from git, do not guess:

```python
         "fails at 140,000 is a car that served its owner well. The same complaint count describes "
```

**File: `render.py`, DELETE line 389** — `.idx-make{padding-top:var(--s-3);border-top:1px solid var(--line)}`. Zero producers; it ships in the `<style>` of all 330 pages.

**File: `charts.py`, new rule to add in step 5's CSS** — `.legend .k-med,.brk-row .k-med{width:3px;height:14px;border-radius:1px;background:var(--ink)}`. A median mark is a tick, not a swatch. (Today the Median legend entry is a 14×10 invisible gap on all 318 pages.)

**File: `render.py`, `main()`** — insert immediately after the `models`/`con` setup, before the render loop:

```python
    # --- build gates ---------------------------------------------------------
    # Run on the RENDERED strings, not on the source. The 2026-08 corruption pass
    # rewrote every literal "14" as an em dash and every "13" as an en dash, which
    # is invisible to a Python syntax check and silently voided three declarations
    # on 318 pages. This is the check that would have caught it.
    _css_out = strip_comments(css=CSS)
    assert "—" not in _css_out and "–" not in _css_out, "dash where a CSS length belongs"
    assert "position:absolute" not in _css_out and "float:" not in _css_out
    assert _css_out.count("position:") == 0, "house rule: nothing on this site is positioned"
```

and at the end of `main()`, after `dist/` is written:

```python
    import re as _re
    bad = []
    for f in DIST.rglob("*.html"):
        t = f.read_text(encoding="utf-8")
        if _re.search(r"[—–](?=[\dp])|\d[—–]px", t):
            bad.append(f"{f}: dash-where-a-length-belongs")
        if _re.search(r"[А-Яа-яЁё]", t):
            bad.append(f"{f}: Cyrillic in shipped output")
    if bad:
        raise SystemExit("BUILD GATE FAILED:\n" + "\n".join(bad[:20]))
```

The Cyrillic half of that gate is the house rule from `read-the-rendered-output` — `strip_comments()` is the only thing keeping the Russian CSS comments out of the shipped HTML and nothing currently asserts it worked.

**Visible change:** table scroll cues appear on every page; the 16 "Other generations" chips go from ~22px tall (a failed 44px tap target) to 45px; the About page stops reading "fails at—0,000".

---

## STEP 2 — Tokens. One commit, one paste. (risk: low, impact: **highest single change on the page**)

**File: `render.py`, replace lines 115–156 in full.**

```css
:root{
  color-scheme:light dark;

  /* Serif for words, sans for numbers. Costs zero requests under the
     no-external-fonts constraint. RULE: Georgia has OLD-STYLE (descending)
     figures, so no numeric string may ever enter a serif element. .h1-years,
     .verdict and every figure are explicitly sans for this reason. */
  --serif:Georgia,"Times New Roman",Times,"Noto Serif",serif;
  --sans:system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;

  --bg:#fbfbfa; --surface:#ffffff;
  --ink:#181c1b;          /* 16.9:1 on --bg */
  --muted:#5a6360;        /*  6.0:1 on --bg */
  --line:#d5dbd9;
  --line-strong:#adb8b4;
  --track:#eef1f0; --warn:#f6f1e6;

  --accent:#0f6e5e; --accent-ink:#0b5347;
  --peak:#a8401f;

  /* --bar WAS #7e938e, which measures 2.89:1 against the cream --warn zone the
     strips now paint bars over — under the 3:1 floor for non-text graphics.
     #758a85: 3.25:1 on --warn, 3.66:1 on --surface, 3.10:1 against --bar-hi. */
  --bar:#758a85; --bar-hi:#0b4238;
  --tick:#ffffff;         /* median mark, drawn ONLY inside a bar.
                             3.66:1 on --bar, 11.35:1 on --bar-hi */

  --danger-bg:#8c2f0e; --danger-fg:#ffffff; --danger-ring:#8c2f0e;
  --shadow:rgba(20,30,28,.13);   /* kept for ONE job: the .tw scroll cue */

  --f-2xs:12px; --f-xs:13px; --f-sm:15px; --f-md:17px;
  --f-lg:21px; --f-xl:26px; --f-2xl:34px; --f-3xl:44px;
  --s-1:4px; --s-2:8px; --s-3:16px; --s-4:24px; --s-5:32px; --s-6:48px; --s-7:64px;
  --measure:68ch;

  --radius:2px;           /* WAS 10px. The single loudest template tell. */
  --rule:3px;             /* masthead rule and exhibit top rule */
  --rail:300px;

  --sys-cols:minmax(8em,13em) minmax(0,1fr) 104px;
  --plot-span:2/3;
  --strip-h:26px;
  --edge-pct:53.04%;      /* = lx(12,000)/10 — verified */
  --hist-h:clamp(220px,26vw,320px);
}
@media(prefers-color-scheme:dark){:root{
  --bg:#111413; --surface:#191d1c;
  --ink:#e6eae8; --muted:#9aa5a1;
  --line:#2f3634; --line-strong:#4a5451;
  --track:#232827; --warn:#2a2419;
  --accent:#4fc0aa; --accent-ink:#7ad6c4; --peak:#f0a882;
  --bar:#667672; --bar-hi:#7fe0c8;
  --tick:#111413;
  --danger-bg:transparent; --danger-fg:#f0a882; --danger-ring:#f0a882;
  --shadow:rgba(0,0,0,.55);
}}
```

Add to the print block (line 422): `--radius:0;--rule:2px;--tick:#ffffff;`.

**DELETED / REJECTED, explicitly:**
- `--radius:10px` — gone from cards, chips, ads, tables, inputs, make cards, `.pct`, `.qpop` in one token. This is non-negotiable; three of the four directions kept or extended it.
- **No** `--e1..--e3` elevation scale, **no** `box-shadow` on cards/chips/stats, **no** `--r-pill`, **no** dark plinth masthead, **no** log-scaled make density bar, **no** two-tone wordmark, **no** always-visible grey `.ad` slab. All four were named as anti-patterns.
- `opacity` as an encoding channel: `.hist .over{opacity:.55}` (line 264) and `.brk-row .k-over{opacity:.55}` (line 287) are replaced in step 5 by a real ramp step.

**Visible change:** every square corner on the site at once. This is the change most likely to make the owner say "different, not better" on its own — which is why it must ship in the same pass as step 3.

---

## STEP 3 — Masthead, headings, section rhythm, the house rule. (risk: low, impact: sets the register before a number is read)

**File: `render.py`, replace lines 192–207.** HTML in `page_shell` (line 587–591) becomes:

```html
<header class="site">
  <a class="brand" href="/"><svg width="14" height="16" viewBox="0 0 14 16"
     aria-hidden="true" focusable="false"><rect x="0" y="1" width="3" height="14"
     fill="currentColor"/><rect x="5.5" y="6" width="3" height="9" fill="currentColor"
     opacity=".62"/><rect x="11" y="10" width="3" height="5" fill="currentColor"
     opacity=".38"/></svg>MileageCurve</a>
  <span class="tag">What breaks, and at what mileage</span>
  <nav aria-label="Main"><a href="/"{cur('home')}>All vehicles</a>
  <a href="/methodology/"{cur('method')}>Methodology</a>
  <a href="/about/"{cur('about')}>About</a><a href="/privacy/"{cur('privacy')}>Privacy</a></nav>
</header>
```

with, above `page_shell`:

```python
def _cur(key: str, active: str) -> str:
    return ' aria-current="page"' if key and key == active else ""
```

and `page_shell(..., nav_key: str = "")`, `cur = lambda k: _cur(k, nav_key)`. Pass `nav_key="home"` from `render_index`, `"method"` from `render_methodology`, etc.

```css
header.site{display:grid;grid-template-columns:auto minmax(0,1fr);align-items:end;
  gap:2px var(--s-4);padding:var(--s-3) 0 10px;margin-bottom:var(--s-5);
  border-bottom:var(--rule) solid var(--ink)}
header.site .brand{grid-column:1;grid-row:1;display:flex;align-items:center;gap:8px;
  font-family:var(--serif);font-weight:700;font-size:24px;letter-spacing:-.02em;
  line-height:1;color:var(--ink);text-decoration:none}
header.site .brand svg{color:var(--accent);flex:none}
header.site .tag{grid-column:1;grid-row:2;font-size:var(--f-2xs);letter-spacing:.1em;
  text-transform:uppercase;color:var(--muted);max-width:none}
header.site nav{grid-column:2;grid-row:1/span 2;align-self:end;display:flex;
  flex-wrap:wrap;justify-content:flex-end;gap:var(--s-2) var(--s-4);
  font-size:var(--f-2xs);letter-spacing:.08em;text-transform:uppercase}
header.site nav a{color:var(--muted);text-decoration:none;padding-bottom:2px;
  border-bottom:2px solid transparent}
header.site nav a:hover{color:var(--ink);border-bottom-color:var(--accent)}
header.site nav a[aria-current="page"]{color:var(--ink);border-bottom-color:var(--accent)}
@media(max-width:560px){
  header.site{grid-template-columns:minmax(0,1fr);padding-bottom:8px}
  header.site nav{grid-column:1;grid-row:3;justify-content:flex-start;margin-top:8px}
}
```

**DELETE** the `@media(max-width:560px){header.site .tag{display:none}}` rule at line 205 — below 560px the tagline *is* the masthead.

**File: `render.py`, replace lines 216–233.**

```css
/* HOUSE RULE: an element that carries a border must NEVER carry a max-width —
   the border is only as wide as the element, which is what produced the 260px
   stub rule. Constrain the column, never the bordered box. */
h1{font-family:var(--serif);font-weight:700;
  font-size:clamp(28px,4.6vw,var(--f-2xl));line-height:1.12;letter-spacing:-.018em;
  margin:0 0 var(--s-2);max-width:22ch}
.h1-years{font-family:var(--sans);font-weight:400;font-size:.72em;color:var(--muted);
  letter-spacing:0;font-variant-numeric:tabular-nums;white-space:nowrap}
.kick{font-family:var(--sans);font-size:var(--f-2xs);letter-spacing:.1em;
  text-transform:uppercase;color:var(--accent-ink);margin:0 0 var(--s-2);max-width:none}
.sub{color:var(--muted);font-size:var(--f-sm);margin:0 0 var(--s-3)}
h2{font-family:var(--serif);font-weight:400;font-size:var(--f-xl);line-height:1.22;
  letter-spacing:-.012em;margin:var(--s-6) 0 var(--s-3);padding-top:var(--s-3);
  border-top:1px solid var(--line-strong);max-width:none}
h3{font-family:var(--serif);font-weight:700;font-size:var(--f-lg);line-height:1.3;
  letter-spacing:-.008em;margin:var(--s-5) 0 var(--s-2);max-width:none}
:is(h1,h2,h3)+*{margin-top:0}
:is(h1,h2,h3)[id]{scroll-margin-top:var(--s-4)}
.verdict{font-family:var(--sans);font-size:var(--f-lg);line-height:1.45;
  margin:0 0 var(--s-5);max-width:var(--measure)}
blockquote.quote p{font-family:var(--serif);font-size:var(--f-md);line-height:1.5}
```

`h2` keeps its rule **on the element**. I am explicitly rejecting system's `sec()` wrapper: `pages.py:54,91,96,104,116,120,127,131,135,138` and the inline `<h2>`s in `render_methodology/about/privacy` are not routed through it, so ~35 pages would silently go flat.

**DELETE, line 478–479, both declarations:**
```css
.demo h2,#makes{border-top:none;padding-top:0;margin-top:0}
.demo h2{max-width:30ch}
```
`.demo` disappears entirely in step 6 (it becomes `figure.fig`), and `#makes` now takes the normal ruled `h2` — which is the rhythm the change is claiming. Leaving the exemption in place while relying on `h2{border-top}` for rhythm would give the homepage the only two unruled headings on the site.

**DELETE, line 440 and 474:** `border-bottom:1px solid var(--line)` from `.hero` and from `.demo`. These are the two stacked hairlines of defect #1/#8. Separation now comes from the exhibit's own 3px ink top rule.

**DELETE the border from `.prov`, line 404** (`border-top:1px solid var(--line)`) — it sits 48px above `footer{border-top}` and is defect #8. `.prov` keeps its top margin; the footer keeps its rule, promoted to `2px solid var(--ink)`.

**Visible change:** a masthead with presence, serif editorial voice, one rule per section instead of two-to-three, and ~140px of dead vertical space recovered on the homepage.

---

## STEP 4 — `figure.fig`: charts become captioned objects. (risk: medium, impact: this is the brief's stated highest-value fix)

**File: `render.py`, new CSS block replacing `figure.chart{margin:0 0 var(--s-4);padding:0}` (line 259).**

```css
figure.fig{margin:var(--s-6) 0;padding:var(--s-4) var(--s-4) var(--s-3);
  background:var(--surface);border:1px solid var(--line);
  border-top:var(--rule) solid var(--ink);border-radius:0;max-width:none}
figure.fig>:first-child{margin-top:0}
.fig-kicker{font-family:var(--sans);font-size:var(--f-2xs);letter-spacing:.1em;
  text-transform:uppercase;color:var(--muted);margin:0 0 var(--s-1);
  max-width:none;font-variant-numeric:tabular-nums}
.fig-title{font-family:var(--serif);font-weight:400;font-size:var(--f-xl);
  line-height:1.2;letter-spacing:-.012em;margin:0 0 var(--s-2);
  padding:0;border:0;max-width:26ch}
.fig-sub{font-family:var(--sans);font-size:var(--f-xs);line-height:1.45;
  color:var(--muted);margin:0 0 var(--s-3);max-width:62ch}
.fig-foot{margin-top:var(--s-4);padding-top:var(--s-3);
  border-top:1px solid var(--line);font-size:var(--f-xs);color:var(--muted)}
.fig-foot p{margin:0 0 var(--s-2);max-width:var(--measure)}
.fig-foot p:last-child{margin-bottom:0}
.fig-foot details.nums{margin-top:var(--s-2)}
.fig-cols p{max-width:44ch}
.fig-cols b{font-family:var(--sans);font-weight:700;color:var(--ink);
  font-variant-numeric:tabular-nums}
@media(min-width:1180px){
  .fig-cols{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:0 var(--s-6)}
  .fig-cols p{margin-bottom:0}
}
@media(max-width:479px){figure.fig{padding:var(--s-3);margin:var(--s-5) 0}}
```

Add `figure.fig,.sys-head,.sys-axis,.band,.stats,ul.makes,.makes-key,.gen-grid,.rail,.cal,.plot`
to the `max-width:none` list at **line 172**, and add `.fig-kicker,.fig-title,.fig-sub` there too. Keep `figure.chart` in the list (still emitted as the inner class).

**File: `charts.py`, `system_strips()` — full replacement of lines 132–165.** Note `pick=` does **not** exist and must not be introduced; row selection stays top-N-by-count so the reader sees the population the claim came from.

```python
import math

LOG_MIN = 500.0            # left anchor of the proportional axis, miles
LOG_MAX = 200_000.0
_LSPAN = math.log10(LOG_MAX / LOG_MIN)      # 2.60206 decades
STRIP_H = 26
EDGE_X = 530.4             # lx(DEFECT_EDGE) — verified

def lx(miles: float) -> float:
    """Miles -> X in a 0..1000 viewBox, base-10 proportional, anchored at 500.

    POSITIONS ONLY. Never use this for a mark whose WIDTH or AREA encodes a
    count or a density. Equal-width bins on a compressed axis is exactly the
    encoding that fabricated this site's headline claim once already; the
    histogram keeps x_of() and stays linear, permanently.

    Also: the plot rect and the axis row must share ONE end constant. lx()
    spans the full 0..1000 box, so axis_row_log()'s columns sum to 100.000%.
    x_of() spans PLOT_W=948, so axis_row()'s columns sum to 94.8%. Do not mix.
    """
    m = min(max(float(miles), LOG_MIN), LOG_MAX)
    return (math.log10(m) - math.log10(LOG_MIN)) / _LSPAN * 1000.0


def axis_row_log() -> str:
    """Column k's RIGHT edge is tick k, so a right-aligned label lands exactly
    on its gridline. Widths are the successive differences of lx() and sum to
    exactly 100.000%. Cell 1 is a flex pair so '500' can sit at x=0 without a
    second overlapping grid item and without any positioning."""
    return ('<div class="sys-axis"><span class="lbl" aria-hidden="true"></span>'
            '<div class="ticks" aria-hidden="true">'
            '<span class="pair"><i>500</i><i>1k</i></span>'
            '<span>2k</span><span>5k</span><span>10k</span><span>20k</span>'
            '<span>50k</span><span>100k</span><span>200k</span></div></div>')


def system_strips(systems: list[dict], limit: int = 7,
                  kicker: str = "", title: str = "", foot: str = "") -> str:
    """Middle-half-of-reports strips on a proportional mileage axis.

    Rows are SELECTED by complaint count (top N most-reported) and then SORTED
    BY MEDIAN ASCENDING for display, so the two-cluster finding is produced by
    layout order before a word is read. Both interval endpoints are printed in
    text under every median: on a compressed axis the bar width encodes a RATIO,
    not a mile span, and the printed endpoints are what stop the width from
    being the reader's only source for the interval.
    """
    rows = [x for x in systems if x.get("median_miles")][:limit]
    if len(rows) < 2:
        return ""
    rows = sorted(rows, key=lambda x: x["median_miles"])

    GRID = "".join(f"M{lx(t):.1f} 0V{STRIP_H}"
                   for t in (1000, 2000, 5000, 10000, 20000, 50000, 100000))
    items = []
    for x in rows:
        p25 = x.get("p25_miles", x["median_miles"])
        p75 = x.get("p75_miles", x["median_miles"])
        x0, x1 = lx(p25), lx(p75)
        w = max(x1 - x0, 10.0)
        if x0 + w > 1000.0:
            x0 = 1000.0 - w
        mpos = min(max(lx(x["median_miles"]), x0 + 1.0), x0 + w - 1.0)
        cls = "iqr-hi" if x["median_miles"] <= DEFECT_EDGE else "iqr"
        clip = ('<rect class="clip" x="0" y="6" width="6" height="14"/>'
                if p25 < LOG_MIN else "")
        name = esc(x.get("display_name") or x["system"].title())
        med = fmt(names.round_miles(x["median_miles"]))
        lo, hi = fmt(names.round_miles(p25)), fmt(names.round_miles(p75))
        items.append(
            f'<li><span class="nm">{name}'
            f'<span class="ct">{fmt(x["count"])} reports</span></span>'
            f'<svg class="strip" viewBox="0 0 1000 {STRIP_H}" '
            f'preserveAspectRatio="none" aria-hidden="true">'
            f'<rect class="zone" x="0" y="0" width="{EDGE_X}" height="{STRIP_H}"/>'
            f'<path class="g" d="{GRID}" vector-effect="non-scaling-stroke"/>'
            f'<line class="edge" x1="{EDGE_X}" y1="0" x2="{EDGE_X}" y2="{STRIP_H}" '
            f'vector-effect="non-scaling-stroke"/>'
            f'<rect class="{cls}" x="{x0:.1f}" y="6" width="{w:.1f}" height="14"/>{clip}'
            f'<line class="med" x1="{mpos:.1f}" y1="6" x2="{mpos:.1f}" y2="20" '
            f'vector-effect="non-scaling-stroke"/></svg>'
            f'<span class="mv"><b>{med}</b><span class="rg">{lo}&#8211;{hi}</span></span>'
            f'<span class="vh">{name}: {fmt(x["count"])} reports, median {med} miles, '
            f'middle half {lo} to {hi} miles.</span></li>')

    body = (f'<div class="sys-head" aria-hidden="true"><span class="hd">System</span>'
            f'<span class="band"><span class="band-a"><b>0&#8211;12,000 mi</b> '
            f'<i>factory-defect window</i></span>'
            f'<span class="band-b"><b>12,000 mi and beyond</b> '
            f'<i>wear and service life</i></span></span>'
            f'<span class="hd hd-r">Median</span></div>'
            f'<ol class="sys">{"".join(items)}</ol>{axis_row_log()}')

    sub = ('Bar spans the middle half of reports; the white tick is the median. '
           'Miles at failure on a proportional scale &mdash; each gridline is the '
           'previous one doubled or multiplied by 2&frac12;, so equal distances are '
           'equal ratios, not equal miles.')
    return (f'<figure class="fig sysfig">'
            f'<p class="fig-kicker">{kicker}</p>'
            f'<h3 class="fig-title">{title}</h3>'
            f'<p class="fig-sub">{sub}</p>{body}'
            f'<div class="fig-foot">{foot}'
            f'<p>Ordered by median mileage, earliest first. The first 12,000 miles '
            f'are shaded: that is the boundary this site uses between a manufacturing '
            f'defect and ordinary wear, not a property of the world.</p>'
            f'<p>Source: NHTSA Office of Defects Investigation, public domain.</p>'
            f'</div></figure>')
```

**Verified geometry, Prius demo, `limit=5`** (rows sorted by median): medians 3,000 / 3,500 / 5,000 / 58,847 / 87,000 → x = 299.1 / 324.8 / 384.3 / 795.8 / 861.1. Bars (x0, width): electric brakes 115.7/287.5 · hydraulic 115.7/336.3 · speed control 171.8/426.3 · electrical 543.8/360.9 · brakes overall 704.3/221.2. First three are `iqr-hi` (median ≤ 12,000), last two `iqr`. On the current linear axis the hydraulic bar is 30.8 units; here it is **336.3**, a 10.9× improvement, and its median tick sits 209 units from the bar's left edge instead of 11.9. **Do not repeat newsroom's "252-unit clean channel" line as written** — that gap holds between hydraulic p75 (452.0) and brakes p25 (704.3), but speed control runs to 598.1, so the honest claim is "the two brake rows' middle halves do not overlap", which is what the copy already says.

Exact SVG for one row (hydraulic circuit):

```html
<svg class="strip" viewBox="0 0 1000 26" preserveAspectRatio="none" aria-hidden="true">
  <rect class="zone" x="0" y="0" width="530.4" height="26"/>
  <path class="g" d="M115.7 0V26M231.4 0V26M384.3 0V26M500.0 0V26M615.7 0V26M768.6 0V26M884.3 0V26" vector-effect="non-scaling-stroke"/>
  <line class="edge" x1="530.4" y1="0" x2="530.4" y2="26" vector-effect="non-scaling-stroke"/>
  <rect class="iqr-hi" x="115.7" y="6" width="336.3" height="14"/>
  <line class="med" x1="324.8" y1="6" x2="324.8" y2="20" vector-effect="non-scaling-stroke"/>
</svg>
```

Every mark is a rect or a strictly vertical segment, so `preserveAspectRatio="none"` cannot deform anything. The gridline path contains **only M and V commands** — no H, no diagonals, no curves, no circles. Paint order zone → gridlines → 12k edge → bar → median, so the bar covers the rules it crosses. The median is stroked in `--tick` and drawn only within the bar's own y-range, so it is never white-on-background: 3.66:1 on `--bar`, 11.35:1 on `--bar-hi`.

**CSS — replace lines 307–327 in full:**

```css
figure.sysfig{--sys-cols:minmax(8em,13em) minmax(0,1fr) 104px;--plot-span:2/3}

.sys-head,.sys-axis{display:grid;grid-template-columns:var(--sys-cols);
  gap:0 var(--s-3);align-items:end}
.sys-head{margin-top:var(--s-3)}
.sys-head .hd{font-family:var(--sans);font-size:var(--f-2xs);letter-spacing:.08em;
  text-transform:uppercase;color:var(--muted);padding-bottom:4px;
  border-bottom:1px solid var(--line-strong)}
.sys-head .hd-r{text-align:right}
.band{grid-column:var(--plot-span);display:grid;
  grid-template-columns:var(--edge-pct) calc(100% - var(--edge-pct));
  font-size:var(--f-2xs);color:var(--muted);border-bottom:1px solid var(--line-strong)}
.band>span{padding:3px 6px 4px 0;min-width:0;overflow:hidden;
  text-overflow:ellipsis;white-space:nowrap}
.band-a{background:var(--warn);padding-left:4px}
.band b{font-weight:600;color:var(--ink);font-variant-numeric:tabular-nums}
.band i{font-style:normal;letter-spacing:.05em;text-transform:uppercase}

ol.sys{list-style:none;margin:0;padding:0}
ol.sys li{display:grid;grid-template-columns:var(--sys-cols);gap:0 var(--s-3);
  align-items:stretch;margin:0;padding:0;max-width:none;
  border-bottom:1px solid var(--line)}
ol.sys li:last-child{border-bottom:0}
ol.sys .nm{grid-column:1;align-self:center;font-size:var(--f-sm);line-height:1.25;
  padding:6px 0}
ol.sys .ct{display:block;font-size:var(--f-2xs);color:var(--muted);
  font-variant-numeric:tabular-nums;margin-top:1px}
ol.sys .mv{grid-column:3;align-self:center;text-align:right;padding:6px 0;
  font-variant-numeric:tabular-nums}
ol.sys .mv b{display:block;font-size:var(--f-sm);font-weight:700;letter-spacing:-.01em}
ol.sys .rg{display:block;font-size:var(--f-2xs);color:var(--muted);white-space:nowrap}

svg.strip{grid-column:var(--plot-span);width:100%;height:100%;
  min-height:var(--strip-h);display:block}
.strip .zone{fill:var(--warn)}
.strip .g{stroke:var(--line);stroke-width:1;fill:none}
.strip .edge{stroke:var(--line-strong);stroke-width:1;stroke-dasharray:3 3}
.strip .iqr{fill:var(--bar)}
.strip .iqr-hi{fill:var(--bar-hi)}
.strip .clip{fill:var(--surface)}
.strip .med{stroke:var(--tick);stroke-width:2}

.ticks{grid-column:var(--plot-span);display:grid;
  grid-template-columns:11.569% 11.569% 15.293% 11.569% 11.569% 15.293% 11.569% 11.569%;
  margin-top:6px;font-size:var(--f-2xs);line-height:1.2;color:var(--muted);
  font-variant-numeric:tabular-nums;letter-spacing:-.01em}
.ticks span{text-align:right;white-space:nowrap;min-width:0}
.ticks .pair{display:flex;justify-content:space-between}
.ticks i{font-style:normal}

@media(max-width:700px){
  figure.sysfig{--sys-cols:minmax(0,1fr) 104px;--plot-span:1/-1}
  .sys-head{grid-template-columns:100%}
  .sys-head .hd,.sys-axis .lbl{display:none}
  ol.sys .nm{grid-column:1;grid-row:1}
  ol.sys .mv{grid-column:2;grid-row:1}
  ol.sys svg.strip{grid-row:2;height:var(--strip-h);margin-bottom:8px}
  .ticks .pair i:first-child{display:none}
  .band i{display:none}
}
```

**DELETED:** `.strip .track{fill:var(--track)}` and the `<rect class="track" width="1000">` element. This also resolves the 1000-vs-948 mismatch firstfive caught — the rule is now written into `lx()`'s docstring so it survives edits.

**File: `render.py`, line 661–665** — the loose `<p class="meta">` before the strips is deleted (its content is now `.fig-sub` inside the figure, which is the fix for defect #5, an axis row 17px above a paragraph):

```python
    strips = charts.system_strips(
        s["systems"],
        kicker=f'Figure 2 &middot; {esc(make)} {esc(model)} {years}',
        title="When each system fails")
    if strips:
        B.append(strips)
```

---

## STEP 5 — Histogram: labelled magnitude, distribution ruler, percentiles as a footnote row. (risk: low–medium)

**File: `charts.py`, `histogram()` — signature and return.** Keep `x_of()` and `axis_row()` untouched; the histogram stays linear with equal bins, forever.

```python
def _yaxis(mx: int) -> str:
    """Five labels, top to bottom, matching the gridlines at y=0/25/50/75/100.
    Honest because histogram() scales the tallest bar to exactly 100 units."""
    steps = [int(mx * k / 4 + 0.5) for k in (4, 3, 2, 1, 0)]
    return ('<div class="yax" aria-hidden="true">'
            + "".join(f"<span>{fmt(v)}</span>" for v in steps) + "</div>")


def ruler(shape: dict) -> str:
    """Five-number summary on the SAME linear x_of() axis as the bars above, so
    it aligns with them. Converts a flat right tail into information without
    touching the histogram's encoding. Median is TWO coincident strokes: --ink
    running the full row height so it reads on the background, and --surface
    inside the box so it reads as a notch cut through the dark fill."""
    if not shape.get("median"):
        return ""
    a, b = x_of(shape["p10"]), x_of(shape["p90"])
    c, d = x_of(shape["p25"]), x_of(shape["p75"])
    m = x_of(shape["median"])
    return (f'<svg class="ruler" viewBox="0 0 1000 18" preserveAspectRatio="none" '
            f'aria-hidden="true">'
            f'<rect class="rtrack" x="0" y="8" width="{PLOT_W}" height="2"/>'
            f'<rect class="whisk" x="{a:.1f}" y="6" width="{max(b-a,2):.1f}" height="6"/>'
            f'<rect class="box" x="{c:.1f}" y="2" width="{max(d-c,2):.1f}" height="14"/>'
            f'<line class="rmed" x1="{m:.1f}" y1="0" x2="{m:.1f}" y2="18" '
            f'vector-effect="non-scaling-stroke"/>'
            f'<line class="rmed-in" x1="{m:.1f}" y1="3" x2="{m:.1f}" y2="15" '
            f'vector-effect="non-scaling-stroke"/></svg>')
```

Inside `histogram()`, after the bars are built, add the peak callout and assemble:

```python
    top = max(bins, key=lambda b: b["count"], default=None)
    callout = ""
    if top and top["count"]:
        col = min(max(int(top["lo"]) // 25_000 + 1, 1), 5)
        callout = (f'<div class="cal" aria-hidden="true">'
                   f'<span style="grid-column:{col}/span 4">{top["pct"]}% of all reports '
                   f'fall between {fmt(top["lo"])} and {fmt(top["hi"])} miles</span></div>')
    sub = (f'Complaints per {fmt(hist["width"])}-mile bin, 0 to {fmt(DOMAIN)} miles, '
           f'equal bins on a linear scale. Tallest bar = {fmt(mx)} complaints.')
    return (f'<figure class="fig histfig">'
            f'<p class="fig-kicker">{kicker}</p>'
            f'<h3 class="fig-title">{title}</h3>'
            f'<p class="fig-sub">{sub}</p>'
            f'<div class="plot">{_yaxis(mx)}'
            f'<div class="pane">{callout}{"".join(parts)}{ruler(shape)}{axis_row()}</div>'
            f'</div>'
            f'<ul class="brk-row">{"".join(legend)}</ul>'
            f'<div class="fig-foot">{foot}'
            f'<p>Source: NHTSA Office of Defects Investigation, public domain. '
            f'Complaint counts reflect what owners reported and are not a measure of '
            f'failure rate per vehicle sold.</p></div></figure>')
```

`grid-column` is the **only** inline style in the build, and it sets flow position, never `position`.

**Verified for the Prius:** mx = 1,333 → y-gutter reads 1,333 / 1,000 / 667 / 333 / 0. Ruler on `x_of()`: p10 500 → 2.4, p25 2,700 → 12.8, median 15,000 → 71.1, p75 86,500 → 410.0, p90 135,000 → 639.9 (whisker x=2.4 w=637.5, box x=12.8 w=397.2). Peak bin 0–5,000 at 33.4% → `grid-column:1/span 4`.

**CSS — replace lines 253–298.**

```css
figure.fig .plot{display:grid;grid-template-columns:auto minmax(0,1fr);gap:0 var(--s-2)}
figure.fig .pane{min-width:0}
.yax{display:flex;flex-direction:column;justify-content:space-between;
  height:var(--hist-h);font-size:var(--f-2xs);line-height:1;text-align:right;
  color:var(--muted);font-variant-numeric:tabular-nums}
.yax span{white-space:nowrap}
svg.hist{width:100%;height:var(--hist-h)}
.hist .zone{fill:var(--warn)}
.hist .bar{fill:var(--bar)}
.hist .bar-hi{fill:var(--bar-hi)}
.hist .over{fill:var(--line-strong)}          /* WAS --bar at opacity:.55 */
.hist .grid{stroke:var(--line);stroke-width:1;stroke-dasharray:2 4;
  vector-effect:non-scaling-stroke}
.hist .base{stroke:var(--line-strong);stroke-width:1;vector-effect:non-scaling-stroke}
.hist .med{stroke:var(--ink);stroke-width:2;stroke-dasharray:3 3;
  vector-effect:non-scaling-stroke}

.cal{display:grid;grid-template-columns:repeat(8,11.85%);margin:0 0 var(--s-2)}
.cal span{font-size:var(--f-xs);line-height:1.35;color:var(--ink);
  border-left:2px solid var(--peak);padding:2px 0 2px 8px;max-width:none}

svg.ruler{width:100%;height:18px;margin-top:6px}
.ruler .rtrack{fill:var(--line)}
.ruler .whisk{fill:var(--bar)}
.ruler .box{fill:var(--bar-hi)}
.ruler .rmed{stroke:var(--ink);stroke-width:2}
.ruler .rmed-in{stroke:var(--surface);stroke-width:2}

.xax{display:grid;grid-template-columns:repeat(8,11.85%);margin:6px 0 0;
  font-size:var(--f-2xs);line-height:1.2;color:var(--muted);
  font-variant-numeric:tabular-nums}
.xax span{text-align:right;white-space:nowrap}
@media(max-width:479px){.xax .q{visibility:hidden}}

.brk-row,.legend{display:flex;flex-wrap:wrap;gap:var(--s-2) var(--s-4);list-style:none;
  padding:0;margin:var(--s-3) 0 0;font-size:var(--f-xs);color:var(--ink)}
.brk-row li,.legend li{display:flex;align-items:center;gap:var(--s-2);margin:0;
  max-width:none}
.brk-row .k,.legend .k{display:block;flex:none;width:14px;height:10px;border-radius:1px}
.brk-row .k-hi,.legend .k-hi{background:var(--bar-hi)}
.brk-row .k-bar,.legend .k-bar{background:var(--bar)}
.brk-row .k-over,.legend .k-over{background:var(--line-strong)}
/* charts.py:123 emits this and no rule has ever existed for it: a blank 14x10
   gap in the Median legend entry on every one of 318 pages. A median mark is a
   tick, not a block. */
.brk-row .k-med,.legend .k-med{width:3px;height:14px;background:var(--ink)}

/* percentiles are the histogram's footnote data — a left-aligned stat row
   inside the exhibit, not a bordered rounded widget beside it */
.fig-foot .pct{display:grid;grid-template-columns:repeat(auto-fit,minmax(84px,1fr));
  gap:0;margin:0 0 var(--s-3);background:none;border:0;border-radius:0;
  border-top:1px solid var(--line-strong);overflow:visible;max-width:none}
.fig-foot .pct>div{background:none;text-align:left;
  padding:var(--s-2) var(--s-3) var(--s-2) 0;border-right:1px solid var(--line)}
.fig-foot .pct>div:last-child{border-right:0}
.pct dt{font-size:var(--f-2xs);letter-spacing:.08em;text-transform:uppercase;
  color:var(--muted)}
.pct dd{margin:2px 0 0;max-width:none;font-size:var(--f-lg);line-height:1.1;
  letter-spacing:-.02em;font-variant-numeric:tabular-nums;color:var(--ink)}
.pct .mid dd{font-weight:700}
.pct .mid dt{color:var(--ink)}
.meta{font-size:var(--f-xs);color:var(--muted);margin:0 0 var(--s-2);
  max-width:var(--measure)}
details.nums{margin-top:var(--s-2)}
details.nums summary{cursor:pointer;color:var(--muted);font-size:var(--f-xs);
  padding:var(--s-1) 0}
details.nums summary:hover{color:var(--ink)}
```

**File: `render.py`, `render_generation` lines 638–647** — the histogram call becomes one composed figure:

```python
    if s["histogram"]:
        top_bin = max(s["histogram"]["bins"], key=lambda b: b["count"], default=None)
        extra = (f'Tallest bin: {fmt(top_bin["count"])} complaints between {fmt(top_bin["lo"])} '
                 f'and {fmt(top_bin["hi"])} miles. ' if top_bin and top_bin["count"] else "")
        foot = (charts.percentiles(sh)
                + f'<p class="meta">{extra}Based on {fmt(s["complaints_with_miles"])} complaints '
                  f'that record mileage. Bin width {fmt(s["histogram"]["width"])} miles.</p>'
                + charts.bins_table(s["histogram"]))
        B.append(charts.histogram(
            s["histogram"], sh, s["complaints_with_miles"], f"{make} {model} {years}",
            kicker=f'Figure 1 &middot; {esc(make)} {esc(model)} {years} &middot; '
                   f'{fmt(s["complaints_with_miles"])} reports with mileage',
            title="Mileage at failure", foot=foot))
```

**REJECTED here, explicitly:** growing the plot to 320px *without* labelling its magnitude (the y-gutter is mandatory, not optional); any log/sqrt/split x under the histogram; `opacity` as an encoding channel.

---

## STEP 6 — Homepage: hero, Figure 1, the make index. (risk: medium)

**File: `render.py`, `render_index()` lines 777–821 — hero.**

```python
    B = ['<div class="hero">',
         '<div class="hero-say">',
         f'<p class="kick">NHTSA complaint analysis &middot; {len(index)} vehicle generations</p>',
         '<h1>Find out what breaks on your car &mdash; and when</h1>',
         '<p class="lede">Complaint databases tell you how many owners had a problem. '
         'They almost never tell you at what mileage. This one does.</p>',
         # Exact, unrounded, straight from the database. 2,116,532 is evidence;
         # "2.1M" is marketing. No testimonials, no "trusted by", no star ratings,
         # no press logos, and NEVER an NHTSA logo or seal — /about/ explicitly
         # disclaims affiliation with NHTSA.
         '<dl class="stats">'
         f'<div><dt>Complaints analysed</dt><dd>{fmt(stats["complaints"])}</dd></div>'
         f'<div><dt>With an odometer reading</dt><dd>{fmt(stats["with_miles"])}</dd></div>'
         f'<div><dt>Generations covered</dt><dd>{len(index)}</dd></div>'
         '</dl>',
         '</div>',
         '<div class="hero-find">',
         search.search_markup()]
    ...
    B.append('<p class="qpop-h">Most reported vehicles</p><ul class="qpop">')
    # unchanged loop
```

**DELETED from the hero copy:** the sentence *"That second number is what makes this site possible."* — the site talking about itself in its most expensive line. **DELETED:** `<h2>Look up a vehicle</h2>` (line 797) and its rule at line 517 — the field already has a visually-hidden `<label for="q">` and a real placeholder. **DELETED:** `.creds` (lines 519–526 CSS, 786–793 markup) — its four facts move into the footer trust row (step 8), and the two big numbers move into `.stats`.

```css
.hero{padding:var(--s-4) 0 var(--s-6);border-bottom:0}
.hero h1{font-size:clamp(30px,5.2vw,var(--f-3xl));line-height:1.06;
  letter-spacing:-.024em;margin:0 0 var(--s-3);max-width:17ch}
.lede{font-family:var(--sans);font-size:var(--f-lg);line-height:1.45;
  color:var(--muted);margin:0 0 var(--s-4);max-width:46ch}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));
  gap:0;margin:var(--s-5) 0 0;border-top:var(--rule) solid var(--ink);max-width:none}
.stats>div{padding:var(--s-3) var(--s-3) var(--s-3) 0;border-right:1px solid var(--line)}
.stats>div:last-child{border-right:0;padding-right:0}
.stats dt{font-size:var(--f-2xs);letter-spacing:.08em;text-transform:uppercase;
  color:var(--muted)}
.stats dd{margin:var(--s-1) 0 0;max-width:none;font-weight:600;line-height:1;
  font-size:clamp(24px,4.4vw,var(--f-2xl));letter-spacing:-.03em;
  font-variant-numeric:tabular-nums}

/* Search field: 2px ink border is what says "primary control" without a shadow
   or a gradient. The card wrapper is DELETED — see below. */
.qbox{display:flex;gap:var(--s-2);max-width:520px}
.qbox input{flex:1 1 auto;min-width:0;font:inherit;font-size:var(--f-md);
  padding:15px var(--s-3);border:2px solid var(--ink);border-radius:var(--radius);
  background:var(--surface);color:var(--ink)}
.qbox input:focus-visible{outline:none;border-color:var(--accent);
  box-shadow:0 0 0 3px var(--track)}
.qbox button{flex:none;font:inherit;font-weight:600;padding:15px var(--s-4);
  border:2px solid var(--accent);border-radius:var(--radius);background:var(--accent);
  color:#fff;cursor:pointer;white-space:nowrap}

/* "Most reported" becomes hairline rows, not pills — pills are template furniture */
.qpop-h{font-size:var(--f-2xs);letter-spacing:.08em;text-transform:uppercase;
  color:var(--muted);margin:var(--s-4) 0 0;max-width:none}
.qpop{list-style:none;margin:0;padding:0;border-top:1px solid var(--line-strong)}
.qpop li{margin:0;max-width:none;border-bottom:1px solid var(--line)}
.qpop a{display:flex;justify-content:space-between;align-items:baseline;gap:var(--s-2);
  padding:10px 0;font-size:var(--f-sm);color:var(--ink);text-decoration:none}
.qpop a:hover{color:var(--accent-ink);text-decoration:underline}
.qpop a span{color:var(--muted);font-variant-numeric:tabular-nums;
  font-size:var(--f-2xs);white-space:nowrap}

@media(min-width:1180px){
  .wrap.wide{max-width:1160px}
  .wrap.wide .hero{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,400px);
    gap:var(--s-6);align-items:start}
  .wrap.wide .hero-say{grid-column:1}
  .wrap.wide .hero h1{max-width:20ch}
  .wrap.wide .hero-find{grid-column:2;grid-row:1;margin:0;padding:0;
    border:0;background:none}
  .wrap.wide .qbox,.wrap.wide .qr{max-width:none}
}
.hero-find{margin:var(--s-5) 0 0}
```

**Defect #3, structurally fixed:** the right column is no longer a bordered card, so residual height difference stops being a *visible box that ends short*. Left column ≈ kick 20 + h1 2 lines ~96 + lede ~60 + stats ~100 ≈ 290px; right column ≈ field 56 + label 28 + 6 hairline rows × 41 ≈ 330px. The taller item is on the right **by construction**, and there is no border to draw attention to the difference. **DELETED:** lines 503–514 (`.wrap.wide .hero-find{...border...background...}`, `.wrap.wide .hero .lede{margin-bottom:0}`, `.wrap.wide .hero h1{max-width:22ch}`).

**The demo becomes Figure 1 (`render_index` lines 824–839).** Do not delete it into a sidebar — the site's best finding is the homepage's numbered exhibit.

```python
    if demo:
        for x in demo["systems"]:
            x["display_name"] = re.sub(r"^the ", "", narrative.plain(x["system"])).capitalize()
        foot = ('<div class="fig-cols">'
                '<p>The hydraulic brake circuit fails at a median of '
                f'<b>{fmt(names.round_miles(demo["hyd"]))} miles</b>. The brakes as a whole '
                f'at <b>{fmt(names.round_miles(demo["svc"]))} miles</b> &mdash; ordinary '
                'service life.</p>'
                '<p>Two different problems, one word in the database, and the middle half '
                'of each does not overlap the other. '
                f'<a class="cta" href="{demo["url"]}">See the full Prius page &rarr;</a></p>'
                '</div>')
        B.append(charts.system_strips(
            demo["systems"], limit=5,
            kicker="Figure 1 &middot; Toyota Prius 2010&ndash;2015 &middot; 3,988 reports",
            title="Counts tell you a car has a problem. Timing tells you which problem.",
            foot=foot))
```

**DELETED:** `<section class="demo">`, the `.demo` and `.demo h2` CSS (474–479), and the two explanatory body paragraphs that ran 1160px wide. Note the copy no longer says *"a manufacturing defect that shows up almost immediately"* — that asserts causation the data does not establish. The 12,000-mile band header says "the boundary this site uses", which is the honest framing.

**The make index (replaces the 28 cards, lines 843–850 and CSS 482–496).**

```python
    B.append('<div class="makes-key" aria-hidden="true"><span><span>Make</span>'
             '<i>Gens</i><i>Reports</i></span></div>')
    B.append('<ul class="makes">')
    for mk in sorted(by_make, key=lambda m: names.display(m)):
        rows = by_make[mk]
        n = sum(r["n"] for r in rows)
        B.append(f'<li><a href="/{slug(mk)}/"><span class="mk">{esc(names.display(mk))}</span>'
                 f'<span class="mk-g">{len(rows)}</span>'
                 f'<span class="mk-n">{fmt(n)}</span></a></li>')
    B.append('</ul>')
```

```css
ul.makes{list-style:none;margin:var(--s-4) 0 var(--s-6);padding:0;
  display:grid;grid-template-columns:repeat(auto-fill,minmax(232px,1fr));
  gap:0 var(--s-5);border-top:1px solid var(--line-strong);max-width:none}
ul.makes li{margin:0;max-width:none;border-bottom:1px solid var(--line)}
ul.makes a{display:grid;grid-template-columns:minmax(0,1fr) 2.4em 5.4em;
  align-items:baseline;gap:var(--s-2);padding:10px 0;
  text-decoration:none;color:var(--ink)}
ul.makes a:hover .mk{text-decoration:underline;text-decoration-thickness:2px;
  text-underline-offset:2px;color:var(--accent-ink)}
.mk{font-size:var(--f-sm);font-weight:600;letter-spacing:-.006em;
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.mk-g,.mk-n{font-size:var(--f-2xs);color:var(--muted);text-align:right;
  white-space:nowrap;font-variant-numeric:tabular-nums}
.mk-n{color:var(--ink)}
.makes-key{display:grid;grid-template-columns:repeat(auto-fill,minmax(232px,1fr));
  gap:0 var(--s-5);margin:var(--s-3) 0 0;max-width:none}
.makes-key>span{display:grid;grid-template-columns:minmax(0,1fr) 2.4em 5.4em;
  gap:var(--s-2);font-size:var(--f-2xs);letter-spacing:.08em;
  text-transform:uppercase;color:var(--muted)}
.makes-key i{font-style:normal;text-align:right}
@media(max-width:479px){ul.makes,.makes-key{grid-template-columns:1fr}}
```

**DELETED:** all card chrome on `.makes a` (border, background, radius, padding box) and the wrapping `"N generations · N complaints"` run — that string is defect #6 and it is now two separately-placed fixed-width fields, so every row is exactly one line. Alphabetical order stays (findability wins); differentiation comes from **the numbers themselves** in a tabular right column — Ford 149,119 against Lexus 198 — not from a bar whose scale has to be defended. **REJECTED:** system's log-scaled density bar (recomputed: it would draw Lexus at 9.3% of Ford's bar when the true ratio is 0.133%, a 70× overstatement — the fabrication bug in a new costume) **and** firstfive's demotion of 16 makes to chips (alphabetical completeness is the index's job).

---

## STEP 7 — Tables. Cheapest credibility-per-declaration change in the set. (risk: very low)

**File: `render.py`, replace lines 346–359** (keep the repaired `.tw` gradients from step 1 and add `--surface-sunken`/`--surface-zebra` inline — no new tokens needed, `--track` and a 50%-mix already exist):

```css
table{border-collapse:collapse;width:100%;font-size:var(--f-sm)}
caption{text-align:left;font-size:var(--f-xs);color:var(--muted);
  padding:var(--s-2) var(--s-3) 0}
thead th{text-align:left;vertical-align:bottom;font-size:var(--f-2xs);font-weight:600;
  letter-spacing:.08em;text-transform:uppercase;color:var(--muted);
  background:var(--track);padding:10px var(--s-3);
  border-bottom:1px solid var(--line-strong)}
thead th.num{text-align:right}
td,tbody th{text-align:left;vertical-align:top;font-weight:400;
  padding:10px var(--s-3);border-bottom:1px solid var(--line);color:var(--ink)}
tbody tr:nth-child(even)>*{background:var(--bg)}
tbody tr:last-child>*{border-bottom:0}
tbody tr:hover>*{background:var(--warn)}
.num{text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums;
  letter-spacing:-.01em}
tbody td.num:first-of-type{font-weight:600}
.sys-name{min-width:10ch}
```

Sunken uppercase `thead`, zebra rows, tabular numerals, weight on the first numeric column (the one people compare), and hover tinted so it reads as **selection** rather than as another zebra step. If the recall and by-year tables end up busier rather than more credible, drop the `nth-child` zebra first — the sunken head and tabular figures carry most of the effect alone.

---

## STEP 8 — Generation-page rail, ad geometry, trust surface. (risk: medium — this is the only structural layout change)

**File: `render.py`, `page_shell` signature (line 560):**

```python
def page_shell(title, desc, body, canonical, script="", wide=False,
               gen=False, nav_key=""):
    cls = " wide" if wide else (" gen" if gen else "")
```

`render_generation` must return `page_shell(..., gen=True)` — newsroom's spec defines `.wrap.gen` and never wires it; that is a real omission and it is fixed here.

**Body order inside `render_generation` (this is the reorder — the chart moves above the card and the caveat):**

```
crumbs / h1 / sub / dateline / verdict
FIGURE 1  (histogram exhibit: callout, y-gutter, plot, ruler, axis, legend, .fig-foot)
.card.finding  (the lead paragraph — moved UP: evidence, then conclusion)
p.note         (the caveat — moved DOWN)
h2#fails "What fails, and when" / FIGURE 2 (sysfig) / systems table / .ad
h2#years / by-year table
h2#recalls / recalls table / .ad
h2#owners / quotes
.prov
h2 Other generations / ul.rel
```

Wrap the body:

```python
    B = ['<div class="gen-grid"><div class="gen-main">'] + B + [
        '</div>',
        '<aside class="rail" aria-label="Summary and related">',
        '<div class="rail-in">',
        # RULE: at least one EDITORIAL block sits above the first rail unit.
        # A rail that opens with a 300x600 is an ad farm to a network reviewer.
        '<dl class="snap">',
        f'<div><dt>Complaints</dt><dd>{fmt(s["complaints_total"])}</dd></div>',
        f'<div><dt>With mileage</dt><dd>{fmt(s["complaints_with_miles"])}</dd></div>',
        f'<div><dt>Median at failure</dt><dd>{fmt(sh["median"]) if sh.get("median") else "—"}</dd></div>',
        f'<div><dt>Recalls</dt><dd>{s["recalls_count"]}</dd></div>',
        '</dl>',
        '<nav class="jump" aria-label="On this page"><p class="jump-h">On this page</p>',
        '<ul><li><a href="#fails">What fails, and when</a></li>',
        '<li><a href="#years">By model year</a></li>',
        '<li><a href="#recalls">Recalls</a></li>',
        '<li><a href="#owners">What owners reported</a></li></ul></nav>',
        '<div class="ad ad-rail"><span class="ad-label">Advertisement</span></div>',
        '</div></aside></div>']
```

Every snapshot number comes from `s` — **do not hardcode**. (newsroom's spec hardcodes `5,725 / 3,988 / 14`; the last one is wrong, `recalls_count` is 12.)

```css
.gen-grid{display:block}
.rail{display:none}
@media(min-width:1180px){
  .wrap.gen{max-width:1180px}
  .gen-grid{display:grid;grid-template-columns:minmax(0,1fr) var(--rail);
    gap:var(--s-7);align-items:start}
  .gen-main{min-width:0}
  .rail{display:block;grid-column:2;min-width:0}
  .rail-in{border-top:var(--rule) solid var(--ink);padding-top:var(--s-3)}
  .snap{margin:0 0 var(--s-5)}
  .snap>div{display:flex;justify-content:space-between;align-items:baseline;
    gap:var(--s-2);padding:7px 0;border-bottom:1px solid var(--line)}
  .snap dt{font-size:var(--f-2xs);letter-spacing:.06em;text-transform:uppercase;
    color:var(--muted)}
  .snap dd{margin:0;max-width:none;font-size:var(--f-sm);font-weight:700;
    font-variant-numeric:tabular-nums}
  .jump-h{font-size:var(--f-2xs);letter-spacing:.08em;text-transform:uppercase;
    color:var(--muted);margin:0 0 var(--s-2);max-width:none}
  .jump ul{list-style:none;margin:0 0 var(--s-5);padding:0;
    border-top:1px solid var(--line)}
  .jump li{margin:0;border-bottom:1px solid var(--line);max-width:none}
  .jump a{display:block;padding:8px 0;font-size:var(--f-sm);color:var(--ink);
    text-decoration:none}
  .jump a:hover{color:var(--accent-ink);text-decoration:underline}
  .ad-rail{min-height:636px;margin:0}
}
/* SHIP STATIC FIRST. position:sticky is a SEPARATE change, after the unit is
   measured, and it must land together with the overflow-ancestor assertion —
   any ancestor acquiring overflow:hidden/auto/clip turns the sticky ad back
   into a static one with no error and no visible symptom. This codebase has
   shipped three positioning defects across 318 pages.
   @media(min-width:1180px){.rail-in{position:sticky;top:var(--s-4)}} */
```

**Ad slots — replace lines 394–400:**

```css
/* PLACEMENT RULE (also written into render_generation's docstring): an
   in-content .ad is ALWAYS the last node of a section and the immediately
   preceding sibling of an <h2>. Ads terminate sections. They never open one,
   never orphan a heading from its body, never sit between the h1 and the first
   figure, and never sit inside a .card, a <figure> or a .tw. Manual placements
   only — no AdSense Auto ads: they insert unreserved units and break the
   zero-CLS promise these reserved boxes exist to make. Let the network's own
   script own any mobile adhesion unit; do not hand-build position:fixed. */
.ad{display:flex;flex-direction:column;align-items:center;justify-content:center;
  gap:var(--s-2);min-height:316px;margin:var(--s-6) 0;padding:var(--s-2) 0;
  background:none;border-top:1px solid var(--line);border-bottom:1px solid var(--line);
  border-radius:0;overflow:hidden;max-width:none}
.ad-label{font-size:var(--f-2xs);line-height:20px;letter-spacing:.12em;
  text-transform:uppercase;font-weight:600;color:var(--muted)}
.ad>ins,.ad>iframe,.ad>div{display:block;max-width:100%}
@media(max-width:479px){.ad{min-height:286px;margin:var(--s-5) 0}}
```

**DELETED:** `background:var(--track)` on `.ad` — two 290px grey slabs labelled "Advertisement" with nothing in them read as broken images to a human and to a network reviewer. The reserved `min-height` stays (that is the CLS guarantee). **The label stays visible** and the box is hairline-ruled instead of filled: I am *not* shipping newsroom's `.ad:has(ins,iframe,div) .ad-label{display:block}` before AdSense confirms an unlabelled reserved slot is acceptable.

**Footer / provenance — replace lines 402–411 and the `page_shell` footer markup:**

```html
<footer>
  <nav class="foot-nav" aria-label="Site">
    <a href="/methodology/">Methodology</a><a href="/about/">About</a>
    <a href="/privacy/">Privacy</a><a href="/terms/">Terms</a>
    <a href="/contact/">Contact</a><a href="mailto:{CONTACT}">{CONTACT}</a></nav>
  <p>Data: <a href="https://www.nhtsa.gov/nhtsa-datasets-and-apis">NHTSA Office of Defects
  Investigation</a>, public domain. Snapshot {date.today().isoformat()}.</p>
  <p>Published by {OWNER}. Complaint counts reflect what owners reported to NHTSA and are
  not a measure of failure rate per vehicle sold.</p>
  <p>This site carries third-party display advertising. Advertisers have no input into
  what is published.</p>
</footer>
```

```css
.prov{display:flex;flex-wrap:wrap;gap:var(--s-2) var(--s-3);
  margin:var(--s-6) 0 0;padding:0;border:0;
  font-size:var(--f-xs);color:var(--muted);max-width:none}
.prov a{color:var(--accent-ink)}
footer{margin-top:var(--s-6);padding-top:var(--s-3);
  border-top:2px solid var(--ink);color:var(--muted);font-size:var(--f-xs)}
.foot-nav{display:flex;flex-wrap:wrap;gap:var(--s-2) var(--s-4);
  margin:0 0 var(--s-3);font-size:var(--f-sm)}
.foot-nav a{color:var(--ink);text-decoration:none;
  border-bottom:1px solid var(--line-strong);padding-bottom:1px}
.foot-nav a:hover{border-bottom-color:var(--accent)}
```

`/terms/` and `/contact/` are generated by `pages.py` (`main()` lines 1084–1085) and linked from **nowhere** today — a common and entirely avoidable ad-network rejection. "Published by BiLingoPlus LLC" is an organisational credit, which is the rule the About page already states; no invented expert persona.

---

## STEP 9 — Chips, tags, print, motion. (risk: very low)

```css
/* One badge, three tones. Old class names kept as aliases so no Python changes.
   No --r-pill: 999px badges are template furniture. */
.tag,.badge,.alert{display:inline-block;margin:0 var(--s-1) 2px 0;padding:2px 9px;
  border-radius:var(--radius);font-size:var(--f-2xs);line-height:1.5;font-weight:600;
  white-space:nowrap;vertical-align:baseline;background:var(--track);
  color:var(--muted);box-shadow:inset 0 0 0 1px var(--line)}
.tag-weak{background:transparent;box-shadow:inset 0 0 0 1px var(--line-strong)}
.alert{background:var(--danger-bg);color:var(--danger-fg);
  box-shadow:inset 0 0 0 1px var(--danger-ring)}

.card{background:var(--surface);border:1px solid var(--line);
  border-radius:var(--radius);padding:var(--s-4) var(--s-5);margin:var(--s-4) 0}
.finding{border-left:3px solid var(--ink)}   /* real border; at radius 2px there
                                                is no miter problem, so the
                                                inset box-shadow hack is DELETED */
.note{background:var(--warn);border-left:3px solid var(--peak);border-radius:0;
  padding:var(--s-3) var(--s-4);margin:var(--s-4) 0;font-size:var(--f-sm)}

@media print{
  .gen-grid{display:block}
  .rail,.ad,ul.rel,header.site nav,.skip,.crumbs{display:none}
  .card,.tw,figure.fig,figure.chart,blockquote.quote,ol.sys li,.pct{break-inside:avoid}
  .tw{overflow:visible;background-image:none}
  h2,h3,.fig-title{break-after:avoid}
}
@media(prefers-reduced-motion:no-preference){
  ul.rel a,tbody tr,header.site nav a,.jump a,.foot-nav a{
    transition:background-color .12s ease,border-color .12s ease,color .12s ease}
}
```

---

## Breakpoint behaviour (pass conditions, to be probed not eyeballed)

- **360–479** (`.wrap` 16px pad, 328px content): strips in 2-row stacked mode (`--plot-span:1/-1`), plot = 328px, narrowest axis column 11.569% × 328 = **37.9px** against a 27px "200k" label — all 8 ticks clear. `.ticks .pair i:first-child{display:none}` drops "500" (the left anchor is still stated in `.fig-sub`). Histogram = 220px (clamp floor); `.xax .q` hidden → 4 labels. `.stats` 2-up; `ul.makes` 1 column; `.ad` 286px. Nothing below 12px. No element wider than 328px except inside `.tw`, which owns its `overflow-x:auto`.
- **480–699**: identical strip behaviour. The stacking breakpoint is **700px, not 560px** — at 560px the 3-column strip layout leaves the plot at 232px, where the narrowest axis column is 26.8px and "200k" collides. This is a deliberate change from today's `@media(max-width:560px)`.
- **700–1179**: strips switch to the 3-column exhibit; plot 459–544px, narrowest column 53–63px. `svg.strip{height:100%}` fills the ~43px row so the 12,000-mile rule and the cream zone run continuously down the chart. Histogram 26vw. Rail hidden; generation page unchanged from today structurally.
- **1180+**: homepage `.wrap.wide` 1160px, hero 1fr/400px, make index 4 columns, `.fig-cols` splits into two 44ch columns. Generation page `.wrap.gen` 1180px, `.gen-grid` = `1fr 300px` with 64px gutter; main column ≈ 780px, prose still capped at 68ch. Strip plot ≈ 408px inside the main column — 47px per narrow axis column, no collision.

---

## Flag list — verify in a real browser before the 318-page run

1. **`svg.strip{height:100%}` in an auto-sized grid row.** Correct per spec and in current Chromium/Gecko/WebKit, but percentage height against an auto row is the one mechanism whose failure mode is uncertain. `min-height:var(--strip-h)` is the guard and must stay; worst case it degrades to a 26px bar in a 43px row — ugly, not broken. **Check at 900px and 1180px.**
2. **`.band>span{white-space:nowrap;overflow:hidden}`** will clip the band-header text at the low end of the 700–900px range. I added `text-overflow:ellipsis`; confirm the cream `.band-a` cell still reads at exactly 700px, and if not, move the `.band i{display:none}` breakpoint up to 780px.
3. **Georgia is absent on Android and most Linux** — the stack falls to Noto Serif / DejaVu Serif with different metrics. Verify the h1 still breaks to two lines at 360px and 1160px (`max-width:17ch` / `20ch` is doing that work). And enforce the rule: **no numeric string in a serif element** — `.h1-years`, `.verdict`, `.fig-cols b`, every `.mv`/`.mk-n`/`dd` is explicitly `--sans`, because Georgia's old-style figures would render "2010–2015" with descenders and read as a rendering bug.
4. **Two x-scales now share a generation page** — linear for the histogram, proportional for the strips. Each figure states its own scale in `.fig-sub` and they are separated by exhibit frames, but this is the design's weakest point. Read `/toyota-prius-2010-2015/` end to end before the full run.
5. **The log axis is the one judgement call.** A bar's width encodes a ratio, not a mile span, so the hydraulic bar (6,500 miles) draws wider than the brakes bar (94,000 miles). Paid for three ways: both endpoints printed under every median in tabular figures, visibly uneven gridlines, and the encoding stated in words. If the owner will not defend it, the fallback is **not** a broken axis — three of twelve Prius systems straddle 20,000 miles (electrical 13,000–113,000, powertrain, airbags) and would ship as bars cut in half across 318 unreviewed pages.
6. **`grid-column:{col}/span 4` inline style on `.cal`.** The only inline style in the build. Confirm it lands over its own bin at 360px and 1180px.
7. **Blast radius.** `page_shell` gains two kwargs and every `render_*`/`pages.py` caller must pass or default them; `charts.histogram` and `charts.system_strips` gain kwargs. Build with `python pipeline/render.py --limit 1 --only "TOYOTA PRIUS"` and open the output before a full run.

**Regeneration gate (house rules, run every time):** the em-dash/Cyrillic grep over all of `dist/` from step 1 → DOM-probe the homepage and `/toyota-prius-2010-2015/` at **360, 480, 700, 900, 1180px** asserting `body.scrollWidth <= clientWidth` and no computed `font-size < 12px` → then **click the real UI**: the search box, every `<details>`, the jump nav, the "Other generations" chips. A syntax-clean build has shipped a dead button on this site before.