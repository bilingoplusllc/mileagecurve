"""
Генератор статических страниц. Только стандартная библиотека — D-009.

Собирает страницу поколения по формуле PLAYBOOK §1: данные + разбор на одной странице,
минимум 3 уникальных структурированных факта, нумерованные источники, дата снимка.

Запуск:  python pipeline/render.py [--limit N] [--only "FORD FUSION"]
Выход:   dist/
"""
from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import sqlite3
from datetime import date
from pathlib import Path

import analyze
import narrative

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "mileagecurve.db"
GENS = ROOT / "data" / "generations.clean.json"
DIST = ROOT / "dist"

SITE = "MileageCurve"
TAGLINE = "What breaks, and at what mileage"
OWNER = "BiLingoPlus LLC"
CONTACT = "hello@mileagecurve.com"
DOMAIN = "https://mileagecurve.com"

MIN_WITH_MILES = 100  # уровни A и B из reports/coverage.md


def esc(s) -> str:
    return html.escape(str(s), quote=True)


def slug(*parts: str) -> str:
    s = "-".join(str(p) for p in parts).lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return re.sub(r"-+", "-", s).strip("-")


def fmt(n) -> str:
    return f"{int(n):,}".replace(",", ",") if n is not None else "—"


# ---------------------------------------------------------------- histogram SVG
def histogram_svg(bins: list[dict], shape: dict) -> str:
    """Гистограмма пробегов до отказа. Главный дифференциатор — рисуем аккуратно."""
    w, h, pad_l, pad_b, pad_t = 720, 260, 44, 46, 14
    plot_w, plot_h = w - pad_l - 12, h - pad_b - pad_t
    mx = max((b["count"] for b in bins), default=1) or 1
    bw = plot_w / len(bins)

    parts = [
        f'<svg viewBox="0 0 {w} {h}" class="hist" role="img" '
        f'aria-label="Распределение пробегов до отказа">'
    ]
    # горизонтальная сетка
    for i in range(1, 5):
        y = pad_t + plot_h * i / 4
        parts.append(f'<line x1="{pad_l}" y1="{y:.1f}" x2="{w - 12}" y2="{y:.1f}" class="grid"/>')

    for i, b in enumerate(bins):
        bh = (b["count"] / mx) * plot_h
        x = pad_l + i * bw
        y = pad_t + plot_h - bh
        # выделяем корзины, формирующие сигнал
        cls = "bar"
        if shape.get("kind") == "bimodal" and (b["hi"] <= 12_000 or b["lo"] >= 100_000):
            cls = "bar peak"
        elif shape.get("kind") == "early" and b["hi"] <= 12_000:
            cls = "bar peak"
        elif shape.get("kind") == "late" and b["lo"] >= 100_000:
            cls = "bar peak"
        title = f'{b["label"]}: {fmt(b["count"])} жалоб ({b["pct"]}%)'
        parts.append(
            f'<g><title>{esc(title)}</title>'
            f'<rect x="{x + 1.5:.1f}" y="{y:.1f}" width="{bw - 3:.1f}" height="{max(bh, 1):.1f}" class="{cls}"/></g>')
        if i % 2 == 0:
            parts.append(
                f'<text x="{x + bw / 2:.1f}" y="{h - pad_b + 16}" class="xl">{esc(b["label"])}</text>')

    parts.append(f'<text x="{pad_l - 8}" y="{pad_t + 4}" class="yl">{fmt(mx)}</text>')
    parts.append(f'<text x="{pad_l - 8}" y="{pad_t + plot_h}" class="yl">0</text>')
    parts.append("</svg>")
    return "".join(parts)


# ---------------------------------------------------------------- prose from data
def lead_paragraph(s: dict, gen: dict) -> str:
    """Описательный текст, выведенный ИЗ ЧИСЕЛ. Не наполнитель — факты о выборке."""
    sh = s["shape"]
    name = f'{s["make"].title()} {s["model"].title()}'
    n = fmt(s["complaints_with_miles"])
    out = [f'Владельцы подали <strong>{fmt(s["complaints_total"])}</strong> жалоб в NHTSA '
           f'на {name} {s["year_start"]}–{s["year_end"]}, и в <strong>{n}</strong> из них указан '
           f'пробег, на котором отказ произошёл. Это позволяет увидеть не только <em>что</em> ломается, '
           f'но и <em>когда</em>.']

    if sh.get("kind") == "bimodal":
        out.append(f'Картина здесь двойная, и это главное, что стоит знать: {sh["note"]} '
                   f'Две разные поломки под одним названием — одна заводская, другая от износа.')
    elif sh.get("kind") == "early":
        out.append(f'{sh["note"]} Ранние отказы обычно означают конструктивный или производственный '
                   f'дефект, а не износ.')
    elif sh.get("kind") == "late":
        out.append(f'{sh["note"]} Это картина износа: машина доезжает до серьёзного пробега прежде, '
                   f'чем начинаются проблемы.')
    elif sh.get("median"):
        out.append(f'{sh["note"]} Медиана — {fmt(sh["median"])} миль.')

    top = [x for x in s["systems"] if x.get("median_miles")][:3]
    if top:
        bits = [f'{x["system"].lower()} ({x["share"]}% жалоб, обычно около {fmt(x["median_miles"])} миль)'
                for x in top]
        out.append("Чаще всего жалуются на " + ", ".join(bits) + ".")

    if s["recalls_count"]:
        sev = (f' Из них {s["severe_advisories"]} сопровождались тяжёлым предупреждением NHTSA.'
               if s["severe_advisories"] else "")
        out.append(f'По этому поколению зарегистрировано {s["recalls_count"]} отзывных кампаний.{sev}')

    if gen.get("mixed_years"):
        yrs = ", ".join(str(y) for y in gen["mixed_years"])
        out.append(f'<mark>Важно: в {yrs} модельном году одновременно продавались обе версии, '
                   f'и жалобы NHTSA по кузовам не разделены.</mark>')

    return "".join(f"<p>{p}</p>" for p in out)


# ---------------------------------------------------------------- page
CSS = """
:root{--bg:#fbfbfa;--surface:#fff;--ink:#1a1d1c;--muted:#5d6663;--line:#e2e6e4;
--accent:#0f6e5e;--accent-ink:#0b5347;--peak:#c2542b;--warn:#f5efe0;--track:#eef1f0}
@media(prefers-color-scheme:dark){:root{--bg:#111413;--surface:#191d1c;--ink:#e6eae8;
--muted:#9aa5a1;--line:#2a302e;--accent:#4fc0aa;--accent-ink:#7ad6c4;--peak:#e08862;
--warn:#2b2519;--track:#232827}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.65 -apple-system,"Segoe UI",Roboto,Arial,sans-serif}
.wrap{max-width:860px;margin:0 auto;padding:28px 20px 80px}
a{color:var(--accent-ink)}
header.site{border-bottom:1px solid var(--line);margin-bottom:32px;padding-bottom:14px;
display:flex;justify-content:space-between;align-items:baseline;gap:16px;flex-wrap:wrap}
header.site .brand{font-weight:700;font-size:18px;letter-spacing:-.01em;text-decoration:none;color:var(--ink)}
header.site .tag{color:var(--muted);font-size:13.5px}
h1{font-size:clamp(25px,4vw,33px);line-height:1.2;margin:0 0 4px;letter-spacing:-.02em}
.sub{color:var(--muted);margin:0 0 26px;font-size:15px}
h2{font-size:20px;margin:38px 0 10px;letter-spacing:-.01em}
h3{font-size:16px;margin:22px 0 6px}
.card{background:var(--surface);border:1px solid var(--line);border-radius:11px;padding:18px 20px;margin:16px 0}
.finding{border-left:3px solid var(--accent);background:var(--surface)}
mark{background:var(--warn);color:inherit;padding:1px 4px;border-radius:3px}
svg.hist{width:100%;height:auto;display:block;margin:6px 0 2px}
.hist .bar{fill:var(--accent);opacity:.82}
.hist .bar.peak{fill:var(--peak);opacity:.95}
.hist .grid{stroke:var(--line);stroke-width:1}
.hist .xl{fill:var(--muted);font-size:10.5px;text-anchor:middle}
.hist .yl{fill:var(--muted);font-size:10.5px;text-anchor:end}
table{border-collapse:collapse;width:100%;font-size:14.5px}
.tw{overflow-x:auto;border:1px solid var(--line);border-radius:11px;background:var(--surface);margin:14px 0}
th{text-align:left;font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);
padding:11px 14px;border-bottom:1px solid var(--line);white-space:nowrap;font-weight:600}
td{padding:10px 14px;border-bottom:1px solid var(--line);vertical-align:top}
tr:last-child td{border-bottom:none}
.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.bar-cell{position:relative;min-width:120px}
.bar-cell i{position:absolute;left:0;top:50%;transform:translateY(-50%);height:6px;
border-radius:3px;background:var(--accent);opacity:.35}
.quote{border-left:2px solid var(--line);padding:2px 0 2px 14px;margin:12px 0;color:var(--muted);font-size:14.5px}
.quote b{color:var(--ink);font-weight:600}
.pill{display:inline-block;font-size:11px;padding:2px 9px;border-radius:99px;
background:var(--track);color:var(--muted);margin-right:6px}
.pill.danger{background:var(--peak);color:#fff;opacity:.9}
ul.rel{list-style:none;padding:0;display:flex;flex-wrap:wrap;gap:8px}
ul.rel a{display:inline-block;padding:6px 12px;border:1px solid var(--line);border-radius:8px;
text-decoration:none;background:var(--surface);font-size:14px}
footer{margin-top:56px;padding-top:18px;border-top:1px solid var(--line);color:var(--muted);font-size:13px}
footer a{color:var(--muted)}
.meta{font-size:12.5px;color:var(--muted);margin-top:8px}
"""


def page_shell(title: str, desc: str, body: str, canonical: str) -> str:
    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{esc(canonical)}">
<style>{CSS}</style>
</head><body><div class="wrap">
<header class="site">
  <a class="brand" href="/">{SITE}</a>
  <span class="tag">{TAGLINE}</span>
</header>
{body}
<footer>
  <p>Data: <a href="https://www.nhtsa.gov/nhtsa-datasets-and-apis">NHTSA Office of Defects Investigation</a>,
  public domain. Snapshot {date.today().isoformat()}.
  <a href="/methodology/">Methodology</a> · <a href="/about/">About</a> ·
  <a href="mailto:{CONTACT}">{CONTACT}</a></p>
  <p>{OWNER}. Complaint counts reflect what owners reported to NHTSA and are not a measure of
  failure rate per vehicle sold.</p>
</footer>
</div></body></html>"""


def render_generation(s: dict, gen: dict, model_entry: dict, siblings: list[dict]) -> str:
    make, model = s["make"].title(), s["model"].title()
    years = f'{s["year_start"]}–{s["year_end"]}'
    title = f"{make} {model} {years} — what breaks and at what mileage"
    desc = (f'{fmt(s["complaints_with_miles"])} NHTSA complaints with mileage for the '
            f'{years} {make} {model}: failure-mileage distribution, systems, recalls.')

    B = [f"<h1>{esc(f'{make} {model}')} <span style='font-weight:400;color:var(--muted)'>{years}</span></h1>"]
    plat = gen.get("platform_code")
    B.append(f'<p class="sub">{esc(gen.get("gen_label","")) }'
             + (f' · {esc(plat)}' if plat else "")
             + f' · {fmt(s["complaints_total"])} complaints, {fmt(s["complaints_with_miles"])} with mileage</p>')

    B.append(f'<div class="card finding">{lead_paragraph(s, gen)}</div>')

    if s["histogram"]:
        B.append("<h2>When failures happen</h2>")
        B.append('<div class="card">')
        B.append(histogram_svg(s["histogram"], s["shape"]))
        sh = s["shape"]
        B.append(f'<p class="meta">10% отказов до {fmt(sh["p10"])} миль · '
                 f'четверть до {fmt(sh["p25"])} · медиана {fmt(sh["median"])} · '
                 f'три четверти до {fmt(sh["p75"])} · 90% до {fmt(sh["p90"])}. '
                 f'Выборка: {fmt(s["complaints_with_miles"])} жалоб с указанным пробегом.</p>')
        B.append("</div>")

    # системы
    B.append("<h2>What fails, and when</h2>")
    B.append('<div class="tw"><table><tr><th>System</th><th class="num">Complaints</th>'
             '<th class="num">Share</th><th class="num">Typical mileage</th>'
             '<th class="num">Middle half</th></tr>')
    mxs = max((x["count"] for x in s["systems"]), default=1)
    for x in s["systems"][:10]:
        med = fmt(x["median_miles"]) if x.get("median_miles") else "—"
        rng = (f'{fmt(x["p25_miles"])}–{fmt(x["p75_miles"])}'
               if x.get("p25_miles") else "—")
        wpct = x["count"] / mxs * 100
        B.append(f'<tr><td class="bar-cell"><i style="width:{wpct:.0f}%"></i>'
                 f'<span style="position:relative">{esc(x["system"].title())}</span></td>'
                 f'<td class="num">{fmt(x["count"])}</td><td class="num">{x["share"]}%</td>'
                 f'<td class="num">{med}</td><td class="num">{rng}</td></tr>')
    B.append("</table></div>")

    # по годам
    if len(s["by_year"]) > 1:
        B.append("<h2>By model year</h2>")
        B.append('<div class="tw"><table><tr><th>Year</th><th class="num">Complaints</th>'
                 '<th class="num">With mileage</th></tr>')
        for y in s["by_year"]:
            mixed = " <span class='pill'>mixed</span>" if y["year"] in (gen.get("mixed_years") or []) else ""
            B.append(f'<tr><td>{y["year"]}{mixed}</td><td class="num">{fmt(y["complaints"])}</td>'
                     f'<td class="num">{fmt(y["with_miles"])}</td></tr>')
        B.append("</table></div>")

    # содержательный разбор, выведенный из данных (narrative.py)
    for heading, block in narrative.full_analysis(s, gen):
        B.append(f"<h2>{esc(heading)}</h2>")
        B.append(block)

    # известные дефекты
    issues = gen.get("known_issues") or []
    if issues:
        B.append("<h2>Documented problems</h2>")
        for it in issues:
            weak = ' <span class="pill">forum-sourced</span>' if it.get("source_strength") == "weak" else ""
            yrs = f' <span class="pill">{esc(it["affected_years"])}</span>' if it.get("affected_years") else ""
            B.append(f'<div class="card"><h3>{esc(it.get("component","—"))}{yrs}{weak}</h3>'
                     f'<p>{esc(it.get("description",""))}</p></div>')

    # отзывы
    if s["recalls"]:
        B.append(f'<h2>Recalls ({s["recalls_count"]})</h2>')
        B.append('<div class="tw"><table><tr><th>Campaign</th><th>Date</th><th>Component</th></tr>')
        for r in s["recalls"][:25]:
            flags = ""
            if r["do_not_drive"]:
                flags += ' <span class="pill danger">do not drive</span>'
            if r["park_outside"]:
                flags += ' <span class="pill danger">park outside</span>'
            B.append(f'<tr><td>{esc(r["campaign"])}{flags}</td><td>{esc(r["report_date"] or "—")}</td>'
                     f'<td>{esc((r["component"] or "—").title())}</td></tr>')
        B.append("</table></div>")

    # цитаты
    if s["quotes"]:
        B.append("<h2>What owners reported</h2>")
        for q in s["quotes"][:4]:
            B.append(f'<div class="quote"><b>{q["year"]} · {fmt(q["miles"])} miles · '
                     f'{esc((q["system"] or "").title())}</b><br>{esc(q["text"])}…</div>')

    # соседние поколения — внутренние ссылки, ~3 на 1000 слов (PLAYBOOK §7)
    rel = [g for g in siblings if g is not gen]
    if rel:
        B.append("<h2>Other generations</h2><ul class='rel'>")
        for g in rel:
            u = f'/{slug(s["make"], s["model"], g["year_start"], g["year_end"])}/'
            B.append(f'<li><a href="{u}">{make} {model} {g["year_start"]}–{g["year_end"]}</a></li>')
        B.append("</ul>")

    canonical = f'{DOMAIN}/{slug(s["make"], s["model"], s["year_start"], s["year_end"])}/'
    return page_shell(title, desc, "\n".join(B), canonical)


# ---------------------------------------------------------------- institutional pages
SHAPE_LABEL = {
    "bimodal": "two separate failure populations",
    "early": "failures concentrated early",
    "late": "failures concentrated late",
    "spread": "failures spread across the mileage range",
    "insufficient": "limited data",
}


def render_index(index: list[dict], stats: dict) -> str:
    by_make: dict[str, list[dict]] = {}
    for p in index:
        by_make.setdefault(p["make"].title(), []).append(p)

    B = ["<h1>What breaks, and at what mileage</h1>",
         '<p class="sub">Vehicle reliability from '
         f'{fmt(stats["complaints"])} owner complaints filed with NHTSA — organised by model '
         "generation, and showing <em>when</em> failures happen rather than just how many.</p>"]

    B.append('<div class="card finding"><p>Most reliability sites count complaints. '
             "The count tells you a car has a problem; it does not tell you whether that problem "
             "arrives at 3,000 miles or 130,000 — and those are completely different cars to own. "
             f"Of {fmt(stats['complaints'])} complaints in this dataset, "
             f"<strong>{fmt(stats['with_miles'])}</strong> record the mileage at which the failure "
             "occurred, which is enough to show the distribution.</p>"
             "<p>Sometimes that distribution has two peaks. A manufacturing defect that shows up "
             "at delivery and ordinary wear a hundred thousand miles later are two separate "
             "problems that share one name in a complaint database. An average hides that. "
             f"On this site, <strong>{stats['bimodal']} generations</strong> show it plainly.</p></div>")

    B.append(f"<h2>{len(index)} generations covered</h2>")
    for make in sorted(by_make):
        pages = sorted(by_make[make], key=lambda p: (p["model"], p["y0"]))
        B.append(f"<h3>{esc(make)}</h3><ul class='rel'>")
        for p in pages:
            B.append(f'<li><a href="{p["url"]}">{esc(p["model"].title())} {p["y0"]}–{p["y1"]}</a></li>')
        B.append("</ul>")

    return page_shell(f"{SITE} — {TAGLINE}",
                      "US vehicle reliability by model generation: when failures happen, from "
                      "NHTSA owner complaints.", "\n".join(B), DOMAIN + "/")


def render_methodology(stats: dict) -> str:
    B = ["<h1>Methodology</h1>",
         '<p class="sub">Where the numbers come from, how they are computed, and what they '
         "cannot tell you.</p>",

         "<h2>Sources</h2><p>Everything here derives from the "
         '<a href="https://www.nhtsa.gov/nhtsa-datasets-and-apis">NHTSA Office of Defects '
         "Investigation</a> flat files, which are United States government work and in the public "
         "domain. Three sets are used:</p>",
         "<div class='tw'><table>"
         "<tr><th>File</th><th>What it provides</th><th class='num'>Records</th></tr>"
         f"<tr><td>FLAT_CMPL</td><td>Owner complaints. Field 18 carries mileage at failure.</td>"
         f"<td class='num'>{fmt(stats['complaints'])}</td></tr>"
         f"<tr><td>FLAT_RCL_POST_2010</td><td>Recall campaigns since 2010, including the "
         f"DO&nbsp;NOT&nbsp;DRIVE and PARK&nbsp;OUTSIDE severe advisories.</td>"
         f"<td class='num'>{fmt(stats['recalls'])}</td></tr>"
         "<tr><td>FLAT_INV</td><td>Defect investigations.</td><td class='num'>—</td></tr>"
         "</table></div>",

         "<h2>How pages are grouped</h2>"
         "<p>Pages cover a model <strong>generation</strong>, not a model year. Generation is how "
         "a vehicle is actually engineered and how buyers think about it, and grouping this way "
         "avoids thousands of near-empty pages. The generation map was compiled from public "
         "references and audited for overlaps, gaps and boundary errors before use.</p>"
         "<p>Where a manufacturer sold an old and a new generation in the same model year — the "
         "2007 Silverado, the 2014–15 Rogue, the 2024 Traverse — NHTSA records do not separate "
         "them. Those years are assigned to the newer generation and flagged on the page as "
         "<em>mixed</em>. Where NHTSA does file the carryover separately (Malibu Classic, for "
         "instance), no ambiguity arises.</p>",

         "<h2>What is computed</h2>"
         "<p>For each generation: the distribution of mileage-at-failure across all complaints "
         "that record one; the same distribution per vehicle system; complaint counts by model "
         "year; recall campaigns; and reported crashes, fires, injuries and fatalities. Mileage "
         "values above 500,000 or at or below zero are discarded as data-entry errors. A "
         "distribution is only drawn when at least 30 complaints carry mileage, and a page is "
         f"only published at {MIN_WITH_MILES} or more.</p>"
         "<p>The shape label — early, late, spread, or two separate populations — is derived "
         "mechanically from the share of failures below 12,000 miles, above 100,000, and in "
         "between. No judgement is applied.</p>",

         "<h2>What these numbers are not</h2>"
         "<div class='card'><p><strong>They are not a failure rate.</strong> Complaint counts "
         "reflect what owners chose to report, not how often a part fails per vehicle sold. "
         "Converting to a rate needs production volume by model and year, and no free, "
         "authoritative source for that exists. The obvious substitute — the affected-vehicle "
         "count published with recall campaigns — was tested against known US sales figures and "
         "rejected: it overstates by a median factor of 7.6, because most campaigns span several "
         "model years while the affected count is given for the campaign as a whole.</p>"
         "<p>So this site does not rank vehicles against each other. It describes what happens to "
         "a given vehicle, and when. Popular models accumulate more complaints simply by being "
         "common, and a larger number here is not by itself evidence of a worse car.</p></div>",

         "<h2>Reproducibility</h2>"
         "<p>The full pipeline is public at "
         f'<a href="https://github.com/bilingoplusllc/mileagecurve">github.com/bilingoplusllc/mileagecurve</a>. '
         "It is plain Python with no external dependencies: download the source files, build the "
         "database, render the site. Anyone can reproduce every figure on this site from the "
         "original government data.</p>"
         f"<p>Data snapshot: {date.today().isoformat()}. Rebuilt monthly, as NHTSA publishes.</p>"]

    return page_shell(f"Methodology — {SITE}",
                      "Sources, computation, and limitations of the MileageCurve reliability data.",
                      "\n".join(B), DOMAIN + "/methodology/")


def render_about() -> str:
    B = ["<h1>About</h1>",
         f'<p class="sub">{SITE} is published by {OWNER}.</p>',

         "<div class='card finding'><p>This site exists because of a gap in how vehicle "
         "reliability is usually reported. Complaint databases tell you <em>how many</em> people "
         "had a problem. They rarely tell you <em>when</em> — and for someone deciding whether to "
         "buy a used car, or whether to repair the one they have, timing is most of the answer.</p>"
         "<p>A transmission that fails at 36,000 miles is a design problem you will meet. One that "
         "fails at 140,000 is a car that served its owner well. The same complaint count describes "
         "both.</p></div>",

         "<h2>Editorial approach</h2>"
         "<p>Figures are computed from public government data by an automated pipeline that runs "
         "monthly. Written material is reviewed before publication. Claims about specific defects "
         "are included only where they are documented; where a claim rests mainly on owner forums "
         "rather than manufacturer or regulator material, the page says so.</p>"
         "<p>Author credit belongs to the organisation. There are no invented expert personas on "
         "this site.</p>",

         "<h2>Corrections</h2>"
         f'<p>If something here is wrong, write to <a href="mailto:{CONTACT}">{CONTACT}</a> and '
         "point at the page. Corrections are made against the source data and noted in the "
         "repository history, which is public.</p>",

         "<h2>Independence</h2>"
         "<p>This site is not affiliated with NHTSA, with any vehicle manufacturer, dealer, "
         "insurer or repair chain. It carries display advertising; advertisers have no input into "
         "what is published.</p>",

         "<h2>Contact</h2>"
         f'<p>{OWNER} · <a href="mailto:{CONTACT}">{CONTACT}</a></p>']

    return page_shell(f"About — {SITE}", f"About {SITE}, published by {OWNER}.",
                      "\n".join(B), DOMAIN + "/about/")


def render_privacy() -> str:
    B = ["<h1>Privacy</h1>",
         '<p class="sub">What this site collects, and what it does not.</p>',
         "<h2>What we collect</h2>"
         "<p>This site is a set of static pages. It has no accounts, no logins, no comment "
         "system and no newsletter, and it never asks you for personal information.</p>"
         "<p>Aggregate traffic measurement (page views, referrer, approximate country, device "
         "type) is used to understand which pages are useful. Nothing on this site is used to "
         "identify you personally.</p>",
         "<h2>Advertising</h2>"
         "<p>This site carries third-party display advertising. Advertising partners may set "
         "cookies or use similar technology to serve and measure ads, including personalised ads "
         "where you have consented to that. Visitors in the European Economic Area and the United "
         "Kingdom are shown a consent choice before any non-essential cookie is set, and that "
         "choice can be changed at any time.</p>"
         '<p>You can opt out of personalised advertising from Google at '
         '<a href="https://adssettings.google.com">adssettings.google.com</a>, and from many other '
         'vendors at <a href="https://optout.aboutads.info">optout.aboutads.info</a>.</p>',
         "<h2>Data about vehicles</h2>"
         "<p>The vehicle data shown here comes from public NHTSA records. Those records are "
         "published by the United States government with personal details already removed, and "
         "nothing on this site is keyed to an individual, an address or a vehicle identification "
         "number.</p>",
         "<h2>Contact</h2>"
         f'<p>Questions about this policy: <a href="mailto:{CONTACT}">{CONTACT}</a> ({OWNER}).</p>'
         f"<p>Last updated {date.today().isoformat()}.</p>"]
    return page_shell(f"Privacy — {SITE}", "Privacy policy for MileageCurve.",
                      "\n".join(B), DOMAIN + "/privacy/")


def write_page(path: Path, content: str) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "index.html").write_text(content, encoding="utf-8")


def render_sitemap(index: list[dict]) -> str:
    today = date.today().isoformat()
    urls = ["/", "/methodology/", "/about/", "/privacy/"] + [p["url"] for p in index]
    body = "".join(
        f"<url><loc>{DOMAIN}{u}</loc><lastmod>{today}</lastmod></url>" for u in urls)
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{body}</urlset>'


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int)
    ap.add_argument("--only", help="подстрока «МАРКА МОДЕЛЬ»")
    args = ap.parse_args()

    models = json.loads(GENS.read_text(encoding="utf-8"))
    con = sqlite3.connect(DB)

    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir(parents=True)

    built = skipped = 0
    index: list[dict] = []

    for m in models:
        label = f'{m["make"]} {m["model"]}'
        if args.only and args.only.upper() not in label.upper():
            continue
        gens = m["generations"]
        for g in gens:
            s = analyze.generation_stats(con, m["make"], m["model"],
                                         int(g["year_start"]), int(g["year_end"]))
            if s["complaints_with_miles"] < MIN_WITH_MILES:
                skipped += 1
                continue
            out = DIST / slug(m["make"], m["model"], g["year_start"], g["year_end"])
            out.mkdir(parents=True, exist_ok=True)
            (out / "index.html").write_text(render_generation(s, g, m, gens), encoding="utf-8")
            index.append({"url": f"/{out.name}/", "make": m["make"], "model": m["model"],
                          "y0": g["year_start"], "y1": g["year_end"],
                          "n": s["complaints_with_miles"], "shape": s["shape"].get("kind")})
            built += 1
            if args.limit and built >= args.limit:
                break
        if args.limit and built >= args.limit:
            break

    (ROOT / "data" / "page_index.json").write_text(
        json.dumps(index, indent=1, ensure_ascii=False), encoding="utf-8")

    # --- институциональная оболочка (PLAYBOOK §8) ---
    meta = dict(con.execute("SELECT key, value FROM meta").fetchall())
    with_miles = con.execute(
        "SELECT COUNT(*) FROM complaints WHERE miles IS NOT NULL").fetchone()[0]
    stats = {
        "complaints": int(meta.get("complaints", 0)),
        "recalls": int(meta.get("recalls", 0)),
        "with_miles": with_miles,
        "bimodal": sum(1 for p in index if p["shape"] == "bimodal"),
    }

    write_page(DIST, render_index(index, stats))
    write_page(DIST / "methodology", render_methodology(stats))
    write_page(DIST / "about", render_about())
    write_page(DIST / "privacy", render_privacy())

    (DIST / "sitemap.xml").write_text(render_sitemap(index), encoding="utf-8")
    (DIST / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\n\nSitemap: {DOMAIN}/sitemap.xml\n", encoding="utf-8")
    # ads.txt заполняется после одобрения AdSense — идентификатор издателя туда же
    (DIST / "ads.txt").write_text(
        "# AdSense publisher line goes here once the account is approved\n", encoding="utf-8")

    # Открытые данные: выгрузка агрегатов — ссылочная приманка (PLAYBOOK §7)
    (DIST / "data").mkdir(exist_ok=True)
    (DIST / "data" / "generations.json").write_text(
        GENS.read_text(encoding="utf-8"), encoding="utf-8")

    print(f"страниц поколений: {built}  | пропущено (мало данных): {skipped}")
    print(f"плюс: главная, methodology, about, privacy, sitemap.xml, robots.txt, открытые данные")
    print(f"→ {DIST}")
    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
