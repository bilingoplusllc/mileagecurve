MILEAGECURVE GRAPHICS ENRICHMENT — FINAL IMPLEMENTATION SPEC
=============================================================

Ship list derived from the three judges' intersection: the CDF staircase (must-ship 3/3), odometer digits (3/3), marker-consistency system (2/3, scored ≥7 by all), hub rulers (2/3, ≥7 by all), recall timeline (8 / 7.5 / 8, no rejections), severity stat row (must-ship j1, no rejection), homepage curve pair (must-ship j2, ≥7 all). Every must_reject honoured — see REJECTED at the end.

**Token doctrine (applies to every item):** `--peak` orange means exactly two things sitewide — "you" (the reader's own odometer marker) and "federal hazard flag" (NHTSA do_not_drive/park_outside, existing `.alert`/`.note` uses). It is NEVER a data-series colour. Data series separate by lightness: `--bar` vs `--bar-hi` (the house rule already written at the token block, render.py ~line 137). All Python comments in Russian; CSS/JS comments are stripped by the existing `strip_comments()` before shipping, so Russian comments inside the `CSS` constant and `ODO_JS` are safe — the Cyrillic build gate at render.py ~1890 checks rendered output.

---

ITEM 1 — The Mileage Curve: cumulative staircase in "Where your car sits" + one-orange-means-you marker system
(merges explainer:1 [9.5/8.5/9] + chart-editor:0 + first-screen:0 + explainer:2; the site's namesake chart, all 318 generation pages)

**Files:** `pipeline\charts.py` (new function `cumulative()`), `pipeline\render.py` (insertion in `render_generation` ~line 1271, `ODO_JS` extension, CSS additions), `charts.system_strips()` (one optional legend row).

**charts.py — add after `bins_table()`:**

```python
def cumulative(hist: dict, shape: dict, total: int, label: str, uid: str = "c",
               kicker: str = "", title: str = "", level: str = "h3") -> str:
    """Кумулятивная лестница: доля сообщений с пробегом не выше X.

    Прямоугольники на ЛИНЕЙНОЙ оси x_of() — самая строгая безопасная геометрия
    под preserveAspectRatio="none". Ступень растёт ТОЛЬКО на границе корзины и
    ровно на её счёт: сглаживание и интерполяция запрещены — они заявляют
    разрешение, которого в данных нет (история с неравными корзинами).
    Кумулята инвариантна к ширине корзины, поэтому этот график не может
    воспроизвести ту фабрикацию. Ось Y — «% of reports», никогда «% of cars».
    Якорные линии 60/90/120k рисуются ТОЛЬКО когда якорь совпадает с границей
    корзины (при ширине 20 000 отметка 90 000 стоит посреди корзины, и линия
    пересекала бы ступень не на напечатанном проценте)."""
    bins = hist["bins"]
    if not bins or not total:
        return ""
    ov = hist.get("overflow") or {}
    step = PLOT_W / len(bins)
    run = 0
    rects = []
    edge_at = {}                      # правая граница корзины -> точная кумулята
    for i, b in enumerate(bins):
        run += b["count"]
        h = run / total * 100.0
        edge_at[b["hi"]] = h
        rects.append(f'<rect class="stp" x="{i * step:.2f}" y="{100 - h:.2f}" '
                     f'width="{step:.2f}" height="{h:.2f}"/>')
    top = run / total * 100.0

    # Шлюз честности: нарисованная лестница обязана проходить через
    # напечатанные якорные проценты (допуск 1 п.п. на целочисленное округление).
    anchors = []
    for a, pct in sorted((shape.get("cum_pct") or {}).items()):
        if a % hist["width"] == 0 and a in edge_at:
            if abs(round(edge_at[a]) - pct) > 1:
                raise SystemExit(f"CDF gate: {label}: drawn {edge_at[a]:.1f}% at "
                                 f"{a} mi vs printed {pct}%")
            anchors.append((a, pct))

    parts = [f'<svg class="cdf" viewBox="0 0 1000 100" preserveAspectRatio="none" '
             f'role="img" aria-labelledby="{uid}t {uid}d">',
             f'<title id="{uid}t">Cumulative share of reports by mileage, {esc(label)}</title>',
             f'<desc id="{uid}d">Of {fmt(total)} reports that record mileage, the share filed '
             f'at or below each odometer reading, rising in steps at each '
             f'{fmt(hist["width"])}-mile bin edge. '
             + " ".join(f"{pct} percent at or below {fmt(a)} miles." for a, pct in anchors)
             + (f" Median {fmt(shape['median'])} miles." if shape.get("median") else "")
             + '</desc>']
    for gy in (25, 50, 75):
        parts.append(f'<line class="grid" x1="0" y1="{gy}" x2="1000" y2="{gy}" '
                     f'vector-effect="non-scaling-stroke"/>')
    parts.extend(rects)
    for a, _ in anchors:
        parts.append(f'<line class="anch" x1="{x_of(a):.1f}" y1="0" '
                     f'x2="{x_of(a):.1f}" y2="100" vector-effect="non-scaling-stroke"/>')
    if shape.get("median"):
        m = x_of(shape["median"])
        parts.append(f'<line class="med" x1="{m:.1f}" y1="0" x2="{m:.1f}" y2="100" '
                     f'vector-effect="non-scaling-stroke"/>')
    parts.append('<line class="you" x1="0" y1="0" x2="0" y2="100" '
                 'vector-effect="non-scaling-stroke"/>')
    parts.append('<line class="base" x1="0" y1="100" x2="1000" y2="100" '
                 'vector-effect="non-scaling-stroke"/></svg>')

    yax = ('<div class="yax" aria-hidden="true">'
           + "".join(f"<span>{v}%</span>" for v in (100, 75, 50, 25, 0)) + "</div>")
    legend = ["".join(f'<li><span class="k k-anch"></span>{fmt(a)} mi &mdash; {pct}% of '
                      f'reports at or below</li>' for a, pct in anchors)]
    if shape.get("median"):
        legend.append('<li><span class="k k-med"></span>Median &mdash; the staircase '
                      'crosses the 50% line here</li>')
    legend.append('<li><span class="k k-you"></span>Your odometer &mdash; appears after '
                  'you enter it below</li>')
    ov_note = (f'<p>The staircase tops out at {top:.0f}%: the remaining {ov["pct"]}% of '
               f'reports ({fmt(ov["count"])}) came above {fmt(DOMAIN)} miles.</p>'
               if ov.get("count") else "")
    sub = (f'Cumulative share of the {fmt(total)} reports that record mileage &mdash; '
           f'of them, how many were filed at or below each odometer reading. '
           f'<strong>That describes reports, not your odds.</strong>')
    return (f'<figure class="fig cdffig">'
            f'<p class="fig-kicker">{kicker}</p>'
            f'<{level} class="fig-title">{title}</{level}>'
            f'<p class="fig-sub">{sub}</p>'
            f'<p class="you-lbl" hidden></p>'
            f'<div class="plot">{yax}<div class="pane">{"".join(parts)}{axis_row()}</div></div>'
            f'<ul class="brk-row">{"".join(legend)}</ul>'
            f'<div class="fig-foot">{ov_note}'
            f'<p>Steps rise only at bin edges, by exact counted shares &mdash; nothing is '
            f'smoothed or interpolated. Linear axis, same as Figure 1.</p>'
            f'<p>Source: NHTSA Office of Defects Investigation, public domain.</p>'
            f'</div></figure>')
```

**charts.py — `system_strips()`:** add parameter `you_key: bool = False`; when true, append after `{axis_row_log()}` inside `body`:

```python
    you = ('<ul class="brk-row"><li><span class="k k-you"></span>Your odometer &mdash; '
           'appears after you enter it in &ldquo;Where your car sits&rdquo;</li></ul>'
           if you_key else "")
    # ... f'<ol class="sys">{"".join(items)}</ol>{axis_row_log()}{you}'
```

(The homepage demo call stays `you_key=False` — it has no odometer input; promising a control that is not on the page would be a lie.)

**render.py — `render_generation`,** inside the `if withm and cum:` block, replace the `.sub` line and insert the figure between it and the form:

```python
        B.append('<p class="sub">Failure reports by the odometer reading they were filed '
                 'at. Pick the anchor nearest your car &mdash; or type the exact mileage: '
                 'your marker lands on this curve and on the timing chart above.</p>')
        if s["histogram"]:
            B.append(charts.cumulative(
                s["histogram"], sh, s["complaints_with_miles"], f"{make} {model} {years}",
                kicker=f'Figure 3 &middot; {esc(make)} {esc(model)} {years} &middot; '
                       f'{fmt(s["complaints_with_miles"])} reports with mileage',
                title="Share of reports at or below each mileage", level="h3"))
```

And pass `you_key=True` in the existing Figure-2 call: `charts.system_strips(s["systems"], kicker=..., title=..., you_key=True)`.

**render.py — `ODO_JS`,** inside the submit handler, immediately after the existing `figure.sysfig` block (after line ~1121):

```js
    var cfig = document.querySelector('figure.cdffig');
    if (cfig) {
      var xc = (Math.min(v, 200000) / 200000 * 948).toFixed(1);
      var yc = cfig.querySelector('svg.cdf .you');
      if (yc) { yc.setAttribute('x1', xc); yc.setAttribute('x2', xc); }
      cfig.classList.add('has-you');
      var cl = cfig.querySelector('.you-lbl');
      if (cl) {
        var pc = pctAt(v);
        cl.textContent = 'Your car: ' + fmt(v) + ' mi' + (pc === null ? ''
          : ' — ' + pc + '% of mileage-tagged reports came at or below this');
        cl.hidden = false;
      }
    }
```

Note the linear map `min(v,200000)/200000*948` replicates `x_of()` exactly, and `pctAt()` already reads the step flat at the containing bin — no interpolation anywhere, matching the drawn geometry (the `odo-data` blob at render.py ~1314–1327 already ships `[bin_hi, cum_pct]`; zero new data).

**render.py — CSS additions** (append as section 17; comments stripped at ship time):

```css
/* ---------- 17. кумулятивная лестница ---------------------------------- */
svg.cdf{width:100%;height:150px}
.cdffig .yax{height:150px}
.cdf .stp{fill:var(--bar)}
.cdf .grid{stroke:var(--line);stroke-width:1;stroke-dasharray:2 4}
.cdf .base{stroke:var(--line-strong);stroke-width:1}
.cdf .anch{stroke:var(--line-strong);stroke-width:1;stroke-dasharray:2 3}
.cdf .med{stroke:var(--ink);stroke-width:2;stroke-dasharray:3 3}
.cdf .you{stroke:var(--peak);stroke-width:2;display:none}
.cdffig.has-you .cdf .you{display:inline}
.brk-row .k-you{width:3px;height:14px;border-radius:1px;background:var(--peak)}
.brk-row .k-anch{width:3px;height:14px;border-radius:1px;background:var(--line-strong)}
```

**Visibly changes:** every generation page's "Where your car sits" opens with a filled monotone green staircase — the literal mileage curve — with the median line crossing the steps at the 50% gridline, anchor lines tied to the prose anchors, and a live orange "you" line after input. ~3.5 KB/page.
**Browser check:** on /toyota-prius-2010-2015/ type 91000 and submit — one orange line must appear on Figure 2 AND on the new Figure 3 at the same mileage, and the Figure 3 median line must visibly cross the staircase exactly at the 50% gridline. Then check a 20k-bin page (e.g. an F-150 generation) — there must be NO anchor line at 90k, only at 60k/120k.

---

ITEM 2 — Hub ruler field: five-number strips on one shared linear axis (28 make hubs)
(first-screen:2 [7.5/8/8.5] merged with chart-editor:3's censoring treatment)

**Files:** `pipeline\render.py` (index entries ~line 1801), `pipeline\charts.py` (new `hub_ruler()`), `pipeline\pages.py` (`make_hub`), CSS.

**render.py ~1801 — pass percentiles through the index entry:**

```python
            index.append({"url": f"/{out.name}/", "make": m["make"], "model": m["model"],
                          "y0": g["year_start"], "y1": g["year_end"],
                          "n": s["complaints_with_miles"], "shape": s["shape"].get("kind"),
                          "median": s["shape"].get("median"),
                          # Хабу нужны ПРОБЕГИ, а не счётчики: позиции соизмеримы
                          # между поколениями, длины-счётчики — нет (D-007).
                          "p10": s["shape"].get("p10"), "p25": s["shape"].get("p25"),
                          "p75": s["shape"].get("p75"), "p90": s["shape"].get("p90")})
```

**charts.py — add:**

```python
def hub_ruler(p: dict, young_edge: int, floor: int = 150) -> str:
    """Линейка поколения для хаба: та же грамматика, что ruler(), та же линейная
    ось x_of() 0–200k — НЕ lx(): строки хаба обязаны быть соизмеримы позицией.
    Кодируются ТОЛЬКО пробеги. Правое цензурирование: молодой парк физически
    не может дать больших пробегов, поэтому поколения с y1 >= young_edge
    получают полый бокс, а мало данных (< floor) — честный текст вместо формы."""
    if p.get("n", 0) < floor or not all(p.get(k) for k in ("p10", "p25", "median", "p75", "p90")):
        return '<span class="hr-none">too few reports to chart</span>'
    a, b = x_of(p["p10"]), x_of(p["p90"])
    c, d = x_of(p["p25"]), x_of(p["p75"])
    m = x_of(p["median"])
    cens = " cens" if p.get("y1", 0) >= young_edge else ""
    return (f'<svg class="hruler{cens}" viewBox="0 0 1000 14" '
            f'preserveAspectRatio="none" aria-hidden="true">'
            f'<rect class="rtrack" x="0" y="6" width="{PLOT_W}" height="2"/>'
            f'<rect class="whisk" x="{a:.1f}" y="5" width="{max(b - a, 2):.1f}" height="4"/>'
            f'<rect class="box" x="{c:.1f}" y="2" width="{max(d - c, 2):.1f}" height="10"/>'
            f'<line class="rmed" x1="{m:.1f}" y1="0" x2="{m:.1f}" y2="14" '
            f'vector-effect="non-scaling-stroke"/>'
            f'<line class="rmed-in" x1="{m:.1f}" y1="3" x2="{m:.1f}" y2="11" '
            f'vector-effect="non-scaling-stroke"/></svg>')
```

**pages.py — `make_hub`:** add `import charts` and `from datetime import date` at top; after the `.sub` line append the load-bearing caption (the judges called it non-optional):

```python
    young_edge = date.today().year - 4
    B.append('<p class="meta">Each strip places that generation&rsquo;s mileage-tagged '
             'reports on a linear 0&#8211;200,000-mile scale: whisker = middle 80%, '
             'box = middle half, line = median. &#8224; marks recent generations &mdash; '
             'their fleets are young, so their reports can only have come at low mileages. '
             'Compare generations of similar age.</p>')
```

Rows go single-column so every strip shares one axis (`gr` class), and each model block gets one axis row:

```python
        B.append(f'<div class="gen-key gk1" aria-hidden="true">{key}</div>')
        B.append('<ul class="gens gr">')
        for p in rows:
            med = p.get("median")
            med_txt = f"{names.round_miles(med):,}" if med else "&mdash;"
            dag = "&#8224;" if p.get("y1", 0) >= young_edge else ""
            B.append(f'<li><a href="{p["url"]}">'
                     f'<span class="gy">{p["y0"]}&#8211;{p["y1"]}{dag}</span>'
                     f'<span class="gn">{fmt(p["n"])}</span>'
                     f'<span class="gm">{med_txt}</span>'
                     f'{charts.hub_ruler(p, young_edge)}</a></li>')
        B.append("</ul>")
        B.append(f'<div class="hub-ax">{charts.axis_row()}</div>')
```

**CSS additions:**

```css
/* ---------- 18. линейки на хабе марки ----------------------------------- */
ul.gens.gr,.gen-key.gk1{grid-template-columns:1fr}
ul.gens.gr svg.hruler,ul.gens.gr .hr-none{grid-column:1/-1;grid-row:2}
svg.hruler{width:100%;height:14px;margin:1px 0 7px}
.hr-none{font-size:var(--f-2xs);color:var(--muted);margin:1px 0 7px}
.hruler .rtrack{fill:var(--line)}
.hruler .whisk{fill:var(--bar)}
.hruler .box{fill:var(--bar-hi)}
.hruler .rmed{stroke:var(--ink);stroke-width:2}
.hruler .rmed-in{stroke:var(--surface);stroke-width:2}
.hruler.cens .box{fill:var(--surface);stroke:var(--bar);stroke-width:1.5;
  vector-effect:non-scaling-stroke}
.hruler.cens .whisk{fill:var(--track)}
.hub-ax{margin:-4px 0 var(--s-4)}
```

**Visibly changes:** the flattest page type becomes small multiples — running the eye down /toyota/ shows each model's failure-mileage geography shift between generations; censored (young) generations read as hollow boxes with a dagger.
**Browser check:** on /toyota/ verify a recent generation (y1 ≥ current−4) renders a hollow box + dagger, that `vector-effect` in CSS actually pins the hollow box's stroke at every window width (this is the one untested-in-house CSS use), and that a sub-150-report row shows "too few reports to chart" instead of a strip.

---

ITEM 3 — Odometer-digit treatment of the headline median (CSS-only automotive identity)
(chart-editor:4 / first-screen:4 converged [8/7/8, 8/7/8]; the ENTIRE tasteful automotive-identity budget)

**Files:** `pipeline\render.py` only (helper + two call sites + CSS).

**render.py — helper near `fmt()`:**

```python
def odo_digits(n) -> str:
    """Число как ячейки одометра. ПРАВИЛО ОДНОГО МЕСТА: только настоящие
    показания одометра (медиана пробега при отказе) — НИКОГДА счётчики жалоб
    и проценты: статистика — не показание одометра, и размывание видов чисел
    было бы фабрикацией рода. Без анимации, без десятых — медиана уже
    округлена names.round_miles. Деградирует до обычных цифр без CSS."""
    if n is None:
        return "&mdash;"
    return ('<span class="odo-w">' + "".join(
        f'<i>{ch}</i>' if ch == "," else f"<b>{ch}</b>" for ch in f"{int(n):,}")
        + "</span>")
```

**Two call sites in `render_generation`:** the `snap-top` median cell (~line 1167) and the rail `snap` median (~line 1456):

```python
        snap_cells.append(f'<div><dt>Median of reported failures</dt>'
                          f'<dd>{odo_digits(names.round_miles(sh["median"]))} mi</dd></div>')
# ...
        f'<div><dt>Median of reported failures</dt><dd>'
        f'{odo_digits(names.round_miles(med)) if med else "&mdash;"}</dd></div>',
```

**CSS (flat — no inner shadow, judge 2's kitsch caution honoured):**

```css
/* ---------- 19. одометр: только настоящие пробеги ----------------------- */
.odo-w{display:inline-flex;gap:2px;align-items:baseline}
.odo-w b{font-family:var(--sans);font-weight:600;font-variant-numeric:tabular-nums;
  background:var(--bar-hi);color:var(--bg);padding:1px 5px 2px;border-radius:2px;
  line-height:1.25}
.odo-w i{font-style:normal;color:var(--muted)}
```

(Dark theme is automatic: `--bar-hi` flips to light green, `--bg` to near-black — dark digits on light drums, both ≥ 4.5:1. Homepage stats and all counts stay plain type — they are not odometer readings.)

**Visibly changes:** the answer box's median reads as an odometer — the one number on the page that literally is one.
**Browser check:** toggle dark mode and print preview — digits must stay legible in both (print maps `--bar-hi` to #252525, `--bg` to #fff: white-on-dark still, fine), and the `mi` suffix must sit on the same baseline.

---

ITEM 4 — Recall timeline spine, with `--peak` ticks carrying the federal hazard flags (all generation pages with ≥3 dated campaigns)
(first-screen:3 [8/7.5/8]; absorbs the do-not-drive salience job of the REJECTED MUTCD diamond, per judge 2's stated remedy: "ship the signal, not the sign")

**Files:** `pipeline\charts.py` (new `recall_timeline()`), `pipeline\render.py` (recalls section ~line 1372 + summary date prefix + CSS).

**charts.py — add:**

```python
def recall_timeline(recalls: list[dict], y0: int, y1: int, this_year: int) -> str:
    """Лента кампаний: положение = официальная дата подачи, и ТОЛЬКО оно.
    Все штрихи одной высоты и ширины — ничто не кодирует величину. Оранжевым —
    исключительно федеральные флаги do_not_drive / park_outside (булевы поля
    самой NHTSA), не наша оценка тяжести. Наложение штрихов в плотный год —
    само сообщение; авторитетный список лежит сразу под лентой.
    НЕ РАСШИРЯТЬ на обычные отзывы или счётчики — редкость и есть сигнал."""
    pts = []
    for r in recalls:
        d = str(r.get("report_date") or "")
        if len(d) >= 7 and d[:4].isdigit() and d[5:7].isdigit():
            pts.append((int(d[:4]) + (int(d[5:7]) - 1) / 12.0,
                        bool(r.get("do_not_drive") or r.get("park_outside"))))
    if len(pts) < 3:
        return ""
    t0 = min(y0, int(min(t for t, _ in pts)))
    t1 = max(this_year + 1, y1 + 1, int(max(t for t, _ in pts)) + 1)
    span = t1 - t0
    # Шаг подписей: 5–8 равных целогодовых интервалов, конец оси добивается
    # до кратности шага — тогда строка подписей это равные flex-ячейки.
    step_y = next(k for k in (1, 2, 3, 5, 10) if span <= 8 * k)
    if span % step_y:
        t1 += step_y - span % step_y
        span = t1 - t0

    def X(t: float) -> float:
        return (t - t0) / span * 1000.0

    zone = (f'<rect class="zone" x="{X(y0):.1f}" y="0" '
            f'width="{X(y1 + 1) - X(y0):.1f}" height="28"/>')
    ticks = "".join(f'<line class="{"t-a" if sev else "t"}" x1="{X(t):.1f}" y1="0" '
                    f'x2="{X(t):.1f}" y2="28" vector-effect="non-scaling-stroke"/>'
                    for t, sev in sorted(pts))
    labels = [t0 + step_y * i for i in range(span // step_y + 1)]
    cells = (f'<span class="pair"><i>{labels[0]}</i><i>{labels[1]}</i></span>'
             + "".join(f"<span>{y}</span>" for y in labels[2:]))
    key = ['<li><span class="k k-zone"></span>Production years</li>',
           '<li><span class="k k-t"></span>Campaign (position = NHTSA filing date)</li>']
    if any(sev for _, sev in pts):
        key.append('<li><span class="k k-ta"></span>Campaign NHTSA flagged do-not-drive '
                   'or park-outside at the time</li>')
    return ('<div class="rtl-wrap" aria-hidden="true">'
            '<svg class="rtl" viewBox="0 0 1000 28" preserveAspectRatio="none">'
            f'{zone}{ticks}'
            '<line class="base" x1="0" y1="28" x2="1000" y2="28" '
            'vector-effect="non-scaling-stroke"/></svg>'
            f'<div class="rtl-x">{cells}</div>'
            f'<ul class="brk-row">{"".join(key)}</ul></div>')
```

**render.py — recalls section:** after the `meta` paragraph (~line 1371), before `<ol class="rcl">`:

```python
        tl = charts.recall_timeline(s["recalls"], s["year_start"], s["year_end"],
                                    int(SNAPSHOT[:4]))
        if tl:
            B.append(tl)
```

And cross-reference list↔timeline: in the campaign loop, before `badges`:

```python
            try:
                r_dt = datetime.strptime(r["report_date"], "%Y-%m-%d").strftime("%b %Y")
            except (TypeError, ValueError):
                r_dt = ""
```

then prepend to the summary line: `f'<span class="rcl-line">{f"<span class=&quot;rcl-dt&quot;>{r_dt}</span> &middot; " if r_dt else ""}<b>{yrs}</b> &middot; {esc(comp)}{badges}</span>'` (build the fragment in a variable to keep quoting sane).

**CSS additions:**

```css
/* ---------- 20. лента отзывных кампаний --------------------------------- */
.rtl-wrap{margin:0 0 var(--s-4)}
svg.rtl{width:100%;height:28px}
.rtl .zone{fill:var(--warn)}
.rtl .t{stroke:var(--accent);stroke-width:2}
.rtl .t-a{stroke:var(--peak);stroke-width:2}
.rtl .base{stroke:var(--line-strong);stroke-width:1}
.rtl-x{display:flex;margin-top:4px;font-size:var(--f-2xs);color:var(--muted);
  font-variant-numeric:tabular-nums}
.rtl-x span{flex:1 1 0;min-width:0;text-align:right;white-space:nowrap}
.rtl-x .pair{display:flex;justify-content:space-between}
.rtl-x i{font-style:normal}
.brk-row .k-zone{background:var(--warn);box-shadow:inset 0 0 0 1px var(--line-strong)}
.brk-row .k-t{width:3px;height:14px;background:var(--accent)}
.brk-row .k-ta{width:3px;height:14px;background:var(--peak)}
.rcl-dt{color:var(--muted);font-weight:400;font-variant-numeric:tabular-nums}
```

**Visibly changes:** "launch-era wave vs still landing in 2025" becomes one glance; ticks outside the cream production zone show post-production campaigns; a do-not-drive campaign is the only orange thing in the section.
**Browser check:** on a page whose recalls extend past production (Prius 2010–2015), confirm ticks land outside the cream zone and the year labels' right edges align with round-year boundaries at 360px and 1180px (flex-cell math is the fragile part).

---

ITEM 5 — Severity stat row: typographic, decisively NOT a chart (all generation pages with any severity flag)
(explainer:3 [9/5.5/8]; the refusal is the deliverable — it permanently forecloses severity bars)

**File:** `pipeline\narrative.py` — replace the body of `severity_narrative()` (line 223); it is already wired into `full_analysis` under "Reported severity", so no render.py change:

```python
def severity_narrative(s: dict) -> str:
    """Ряд из четырёх ячеек ОДНИМ кеглем — и никогда график. Флаги пересекаются
    (одна жалоба несёт несколько), разброс 100×+: линейная длина прячет смерти,
    логарифм у нас запрещён, стек двойным счётом лжёт о частях целого,
    пиктограммы выдумывают единицу. Позиция и одинаковый кегль — единственные
    каналы, в которых нечего завысить."""
    sev = s["severity"]
    total = s["complaints_total"]
    if not total or not any(sev.values()):
        return ""
    pct = (sev["crashes"] or 0) / total * 100
    cells = [("Crashes", f'{fmt(sev["crashes"])} ({pct:.1f}%)'),
             ("Fires", fmt(sev["fires"])),
             ("Injury reports", fmt(sev["injured"])),
             ("Fatality reports", fmt(sev["deaths"]))]
    row = "".join(f'<div><dt>{k}</dt><dd>{v}</dd></div>' for k, v in cells)
    out = [_p(f"What owners reported alongside the failure itself, out of {fmt(total)} "
              f"complaints against this generation:"),
           f'<dl class="pct">{row}</dl>',
           _p("These flags are self-reported by complainants and unverified by NHTSA; one "
              "report can carry several flags, so the counts overlap and do not sum to a "
              "total. They are not adjusted for how many of these vehicles are on the road. "
              "No chart is drawn here on purpose: overlapping counts spanning very "
              "different magnitudes cannot be honestly encoded as lengths.")]
    return "".join(out)
```

(Reuses the existing `dl.pct` grid — zero new CSS. Same numeral size in every cell, no red, no icons, ever.)

**Visibly changes:** "were there fires?" becomes scannable in one fixation instead of buried mid-sentence.
**Browser check:** a page with deaths > 0 — confirm the Deaths cell is typographically identical to the Crashes cell (no accidental emphasis via `.mid`), and that `.pct` wraps to 2×2 at 360px without overflow.

---

ITEM 6 — Homepage curve pair: two generations, one axis (homepage, Figure 2)
(first-screen:1 [8/9/7]; token collision resolved per judge 3 — series in `--bar`/`--bar-hi`, never `--peak`)

**Files:** `pipeline\charts.py` (`cdf_pair()` + `_cdf_path()`), `pipeline\render.py` (`main()` demo block ~1829 + `render_index` after the strips demo).

**charts.py:**

```python
def _cdf_path(hist: dict, total: int) -> str:
    """Ступенчатый путь ТОЛЬКО из H/V-команд — переживает любое растяжение X."""
    bins = hist["bins"]
    step = PLOT_W / len(bins)
    run = bins[0]["count"]
    d = [f"M0 {100 - run / total * 100:.2f}"]
    for i, b in enumerate(bins[1:], 1):
        run += b["count"]
        d.append(f"H{i * step:.2f}V{100 - run / total * 100:.2f}")
    d.append(f"H{PLOT_W:.1f}")
    return "".join(d)


def cdf_pair(a: dict, b: dict, kicker: str = "", title: str = "",
             foot: str = "", level: str = "h2") -> str:
    """Две лестницы на одной линейной оси. КАЖДАЯ нормирована на СВОЁ число
    сообщений — разница объёмов жалоб не может ничего исказить: это и есть
    кодировка, которую D-007 требует вместо столбиков-счётчиков. Серии
    различаются СВЕТЛОТОЙ (--bar / --bar-hi); --peak зарезервирован за «вы»."""
    if not (a.get("hist", {}).get("bins") and b.get("hist", {}).get("bins")
            and a.get("total") and b.get("total")):
        return ""
    grid = "".join(f'<line class="grid" x1="0" y1="{gy}" x2="1000" y2="{gy}" '
                   f'vector-effect="non-scaling-stroke"/>' for gy in (25, 50, 75))
    yax = ('<div class="yax" aria-hidden="true">'
           + "".join(f"<span>{v}%</span>" for v in (100, 75, 50, 25, 0)) + "</div>")
    legend = (f'<ul class="brk-row">'
              f'<li><span class="k k-bar"></span>{esc(a["label"])} &mdash; '
              f'{fmt(a["total"])} reports with mileage</li>'
              f'<li><span class="k k-hi"></span>{esc(b["label"])} &mdash; '
              f'{fmt(b["total"])} reports with mileage</li></ul>')
    sub = ('Share of each generation&rsquo;s <em>own</em> mileage-tagged reports filed at '
           'or below each mileage, on a linear 0&#8211;200,000-mile axis. Shares of '
           'reports, not failure rates &mdash; and not a ranking.')
    return (f'<figure class="fig cdfp-fig">'
            f'<p class="fig-kicker">{kicker}</p>'
            f'<{level} class="fig-title">{title}</{level}>'
            f'<p class="fig-sub">{sub}</p>'
            f'<div class="plot">{yax}<div class="pane">'
            f'<svg class="cdfp" viewBox="0 0 1000 100" preserveAspectRatio="none" '
            f'aria-hidden="true">{grid}'
            f'<path class="c-a" d="{_cdf_path(a["hist"], a["total"])}" '
            f'vector-effect="non-scaling-stroke"/>'
            f'<path class="c-b" d="{_cdf_path(b["hist"], b["total"])}" '
            f'vector-effect="non-scaling-stroke"/>'
            f'<line class="base" x1="0" y1="100" x2="1000" y2="100" '
            f'vector-effect="non-scaling-stroke"/></svg>{axis_row()}</div></div>'
            f'{legend}<div class="fig-foot">{foot}'
            f'<p>Source: NHTSA Office of Defects Investigation, public domain.</p>'
            f'</div></figure>')
```

**render.py — `main()` demo block:** also fetch gen 2 and attach the pair (keep inside the existing try/except so a data refresh that breaks it degrades to no figure, not a wrong one — this answers judge 3's staleness concern):

```python
        d2 = analyze.generation_stats(con, "TOYOTA", "PRIUS", 2004, 2009)
        if demo and d2["histogram"] and d["histogram"]:
            demo["pair"] = {
                "a": {"hist": d2["histogram"], "total": d2["complaints_with_miles"],
                      "label": "Prius 2004\u20132009", "median": d2["shape"].get("median")},
                "b": {"hist": d["histogram"], "total": d["complaints_with_miles"],
                      "label": "Prius 2010\u20132015", "median": d["shape"].get("median")}}
```

**render.py — `render_index`,** immediately after the `charts.system_strips(demo...)` append:

```python
    if demo and demo.get("pair"):
        pr = demo["pair"]
        foot = ""
        if pr["a"]["median"] and pr["b"]["median"]:
            foot = (f'<p>Half of the {esc(pr["b"]["label"])} reports arrive by '
                    f'<b>{fmt(names.round_miles(pr["b"]["median"]))} miles</b>; the '
                    f'{esc(pr["a"]["label"])} takes '
                    f'<b>{fmt(names.round_miles(pr["a"]["median"]))}</b>. Same nameplate, '
                    f'different curve &mdash; that is what every page here shows.</p>')
        B.append(charts.cdf_pair(
            pr["a"], pr["b"],
            kicker="Figure 2 &middot; Toyota Prius, two generations",
            title="Same model name, different mileage curve",
            foot=foot, level="h2"))
```

**CSS additions:**

```css
/* ---------- 21. пара кривых на главной ----------------------------------- */
svg.cdfp{width:100%;height:180px}
.cdfp-fig .yax{height:180px}
.cdfp .grid{stroke:var(--line);stroke-width:1;stroke-dasharray:2 4}
.cdfp .base{stroke:var(--line-strong);stroke-width:1}
.cdfp .c-a{stroke:var(--bar);stroke-width:2;fill:none}
.cdfp .c-b{stroke:var(--bar-hi);stroke-width:2;fill:none}
.cdfp-fig .fig-foot b{font-family:var(--sans);font-variant-numeric:tabular-nums}
```

**Visibly changes:** the homepage demonstrates the whole product category in one image — the dark Gen-3 curve wall 40,000 miles left of the grey Gen-2 curve — and seeds the compare-page visual language.
**Browser check:** narrow the window from 1400px to 360px — the two stroked step paths must keep 2px strokes with verticals staying vertical (this is the first stroked-path-under-`none` on the site; if any diagonal artifact appears at any width, fall back to two overlaid rect staircases like Item 1).

---

BUILD/VERIFY GATES (whole round)
- `python pipeline\render.py --only "TOYOTA PRIUS"` first — the CDF gate in `cumulative()` and the Cyrillic/dash gates must pass; then full build.
- Per house lessons: drive the deployed pages in a real browser (verify-in-the-browser-not-the-build), and check the five browser items above at 360/768/1180px. No horizontal scroll at 360px on any new figure.
- Grep shipped HTML for `position:absolute` (must stay zero hits) and for `<text` inside any new SVG (must be zero).

REJECTED — do not re-propose
- **chart-editor:2, by-model-year count bars (any variant, incl. nested coverage rects):** unanimous must_reject. Length encoding raw complaint counts across model years that differ in sales mix AND years-on-road exposure is D-007's mechanism relocated inside one table; a 16× bar makes the confound the pre-attentive headline on a site whose founding failure was fabrication-by-bar-geometry. The by-year table stays numbers-only, permanently.
- **automotive-identity:0, body-style silhouettes:** judge-2 must_reject — 40×16 two-tone car glyphs read as clipart in a serif data newsroom, the exact kitsch three audits stripped; plus a standing build-break tax on every data refresh. Consequence: the curated `data\body_styles.proposed.json` (99 keys, verified) is consumed by NOTHING in this spec — per the prune rule it should be deleted, unless the owner explicitly keeps it as future compare-page metadata.
- **automotive-identity:1, milepost chips:** judge-2 must_reject — road-sign cosplay; the single odometer treatment (Item 3) is the entire number-costume budget, and its one-place-one-meaning rule (mileage medians only, never counts/percentages) is adopted verbatim.
- **automotive-identity:2 as drawn (MUTCD diamond icon):** judge-2 must_reject of the form, not the signal. The signal ships via Item 4's `--peak` timeline ticks plus the already-existing `.alert` "do not drive"/"park outside" badges and `.alert-strip`. No hazard icons, no octagons, ever; never scaled by crash/fire/death counts.
- **Standing WOULD-NOT rejections re-affirmed:** cross-generation/model/make COUNT bars anywhere (hub gets mileage positions only); log-scale magnitude encodings (`lx()` stays position-only per its docstring); smoothed/interpolated/kernel curves (steps only, rising at bin edges by exact counts); severity bars, icon arrays, donuts, stacked strips (Item 5 is the ceiling); mean-miles-by-year trend lines (fleet-age artifact dressed as a reliability trajectory); gauges/dials for any percentage (invented denominator by form); per-system pictograms in Figure 2; animated odometer rolls; masthead rebrand to a car mark.
- **Deferred, not rejected** (re-proposable in a later round): explainer:0 log-axis reading key for Figure 2 (8.5/6/8.5 — judge 2: "wrong round to prioritize"; revisit as a compact single-row version) and automotive-identity:3 platform-code plate chip (7/6.5/7 — note `platform_code` already prints in the `.sub` at render.py ~1146; the chip is styling only).