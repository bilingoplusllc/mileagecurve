# MileageCurve — design brief for the redesign round

The owner has now said three times that the site "does not look like a professional website."
Two previous rounds fixed *defects* (overflow, tiny text, wasted width) and he is still right.
The problem is not defects any more. It is that the site has no design — only typesetting.

## What the site is

An ad-monetized US reference site. 318 vehicle-generation pages built from NHTSA complaint data,
answering "what breaks on this car, and at what mileage." Revenue is display advertising
(AdSense now → Mediavine → Raptive later). Traffic will arrive from Google search directly
onto generation pages; the homepage is a smaller share but is what a human reviewer,
an ad-network reviewer, and the owner judge the site by.

Live: https://mileagecurve.com — homepage, /toyota-prius-2010-2015/ (generation page),
/toyota/ (make hub).

## Hard constraints — a proposal that breaks these is unusable

- Generator is **pure Python standard library** (decision D-009). No npm, no framework,
  no build step beyond `python render.py`. CSS is one inlined `<style>` block in every page.
- **No external requests at all** — no Google Fonts, no CDN, no icon library, no remote images.
  System font stack only. Any icon must be inline SVG written by hand.
- **No `position:absolute` decorative elements.** House rule, violated three times, each time
  shipping a visible defect on 318 pages. In-flow compositions only.
- Must work at **360px** with no horizontal scroll and no text under 12px.
- Every page is static HTML regenerated monthly. No client-side rendering. Vanilla JS is
  allowed but currently used only for search, and nothing may depend on JS to be readable.
- Ad slots must have reserved space (`.ad` blocks already exist) so ads do not cause layout shift.
- Charts are generated as inline SVG from Python (`charts.py`). Labels are HTML siblings,
  never `<text>` inside SVG — a previous bug rendered 4px labels on mobile.

## What is on the page today

Colours: near-white background, white surfaces, hairline grey borders, near-black ink,
one dark green accent (#0f6e5e) used for links, the Find button, and the highlighted
histogram bars. Nothing else. No elevation, no fills, no imagery, no second accent.

Type: system stack. h1 `clamp(30px,5.2vw,44px)` weight 700. Body 17px. Muted grey for
secondary text. A spacing scale `--s-1..--s-7`. Prose measure 68ch.

Layout: `.wrap` max-width 880px on all pages; homepage gets `.wrap.wide` at ≥1180px → 1160px
with a two-column hero (headline+lede left, search card right) and a 5-column make grid.

## Observed defects — verified in a real browser at 1568×744, not inferred

1. **Hero has a dead zone.** The lede ends, then ~60px of nothing, then a full-width rule,
   then ~80px more nothing, then a *stubby* 260px rule, then the demo heading. Two rules and
   140px of emptiness read as an unfinished page.
2. **The stubby rule is a bug**: `.demo h2{max-width:22ch}` plus the global `h2{border-top}`
   makes the border only 260px wide. The same rule wraps that heading into three short lines
   while ~600px sits empty to its right.
3. **Right hero column is empty below the search card** — roughly 140px of white.
4. **The flagship chart reads as empty.** `system_strips()` plots on a linear 0–200,000 mile
   axis. The three most important values (3,500 / 3,000 / 5,000 miles) render as ~20px blobs
   pinned to the left edge, and roughly 75% of the chart width is blank. The *finding* is
   excellent — hydraulic brake circuit fails at 3,500 miles vs brakes overall at 87,000 —
   but the encoding hides it.
5. **Axis labels collide with the paragraph below** — 17px apart on the homepage demo.
6. **Make cards are ragged and undifferentiated.** "N generations · N complaints" wraps to
   two lines in most cards and one in others, so internal rhythm is uneven. All 28 cards look
   identical whether the make has 149,130 complaints (Ford) or 198 (Lexus).
7. **The header has no presence** — a bold wordmark and four plain grey links.
8. **The footer stacks two rules** with dead space between them.
9. **Generation pages waste 888px of width** at 1568px — content is a 680px column with
   nothing beside it. For an ad-monetized publisher this is also where a sticky rail ad lives.
10. **The generation histogram is 190px tall and ~95% flat**, so it wastes vertical space too,
    even though its shape is the real story.

## What "professional" has to mean here

Not decoration. This is a data-reference site whose credibility *is* the product: the copy
promises open methodology and public source code. It must read like a serious publication
(think a data desk at a newspaper, or a well-made reference tool) — confident type, real
visual hierarchy, purposeful colour, surfaces with weight, charts that carry the finding —
and never like a template, a startup landing page, or a car dealership.

The single highest-value fix is probably that the charts must *look like the point of the site*.
Right now they look like leftovers.
