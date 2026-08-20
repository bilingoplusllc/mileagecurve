"""
Структурные страницы: хабы по маркам, 404, контакты, условия.

Хабы решают две задачи сразу. Продуктовую: 318 страниц поколений сейчас висят
листьями на одном корне, и человеку, пришедшему за своей машиной, некуда идти.
И проверочную: и асессоры Google, и рецензенты рекламных сетей смотрят на наличие
иерархии — сайт без структуры читается как свалка.

404 и контакты — прямые блокеры при подаче в AdSense: сейчас любой несуществующий
адрес отдаёт главную с кодом 200, а публичного способа связаться нет.

Только стандартная библиотека — D-009.
"""
from __future__ import annotations

import html
import charts
import names

from datetime import date

# Дата правки политики, а не дата сборки: иначе поле заявляет
# пересмотр при каждом деплое и теряет весь смысл.
POLICY_UPDATED = "2026-08-13"

SITE = "MileageCurve"
OWNER = "BiLingoPlus LLC"
CONTACT = "hello@mileagecurve.com"
DOMAIN = "https://mileagecurve.com"


def esc(s) -> str:
    return html.escape(str(s), quote=True)


def fmt(n) -> str:
    return f"{int(n):,}" if n is not None else "—"


def make_hub(make_raw: str, pages: list[dict], shell) -> str:
    """Страница марки: все её поколения, сгруппированные по модели."""
    make = names.display(make_raw)
    by_model: dict[str, list[dict]] = {}
    for p in pages:
        by_model.setdefault(names.display(p["model"]), []).append(p)

    total = sum(p["n"] for p in pages)
    gens = len(pages)
    models = len(by_model)

    B = [f'<ol class="crumbs"><li><a href="/">Home</a></li><li>{esc(make)}</li></ol>',
         f'<h1>{esc(make)}</h1>',
         f'<p class="sub">{gens} generation{"s" if gens != 1 else ""} across {models} '
         f'model{"s" if models != 1 else ""}, built from {fmt(total)} complaints that record '
         f'mileage at failure.</p>']

    # Хаб — малые кратные: линейка каждого поколения на ОДНОЙ линейной оси
    # 0–200k, кодируются только пробеги (позиции соизмеримы, счётчики — нет).
    # Молодой парк физически не набрал больших пробегов — полый бокс и крест.
    young_edge = date.today().year - 4
    B.append('<p class="meta">Each strip places that generation&rsquo;s mileage-tagged '
             'reports on a linear 0&#8211;200,000-mile scale: whisker = middle 80%, '
             'box = middle half, line = median. &#8224; marks recent generations &mdash; '
             'their fleets are young, so their reports can only have come at low mileages. '
             'Compare generations of similar age.</p>')
    for model in sorted(by_model):
        rows = sorted(by_model[model], key=lambda p: p["y0"])
        B.append(f'<h2>{esc(model)}</h2>')
        key = ('<span><span>Generation</span><i>Reports</i><i>Median</i></span>')
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

    B.append('<p class="prov">Every page here is generated from the NHTSA Office of Defects '
             f'Investigation dataset. <a href="/methodology/">How this is built</a> · '
             f'<a href="/">All makes</a></p>')

    return shell(f"{make} reliability by generation — {SITE}",
                 f"When failures happen on {gens} {make} generations, from "
                 f"{fmt(total)} NHTSA complaints that record mileage.",
                 "\n".join(B), f"{DOMAIN}/{_slug(make_raw)}/")


def _slug(s: str) -> str:
    import re
    s = re.sub(r"[^a-z0-9]+", "-", str(s).lower())
    return re.sub(r"-+", "-", s).strip("-")


def render_404(shell) -> str:
    B = ['<h1>Page not found</h1>',
         '<p class="sub">That address does not match anything on this site.</p>',
         '<div class="card"><p>If you were looking for a specific vehicle, start from the '
         '<a href="/">list of makes</a> — every generation covered here is linked from there.</p>'
         '<p>If you followed a link from somewhere else and it should work, '
         f'<a href="mailto:{CONTACT}">tell us</a> and we will fix it.</p></div>']
    # Ни индексации, ни канонического адреса: канонический вёл на /404.html,
    # который редиректом возвращает на /404 — замкнутая петля для робота.
    return shell(f"Page not found — {SITE}", "That address does not match anything on this site.",
                 "\n".join(B), "", robots="noindex")


def render_contact(shell) -> str:
    B = ['<h1>Contact</h1>',
         '<p class="sub">One address, read by a person.</p>',
         f'<div class="card"><p><a href="mailto:{CONTACT}">{CONTACT}</a></p>'
         f'<p>{OWNER}, a Wyoming limited liability company.</p></div>',
         '<h2>Corrections</h2>',
         '<p>If a figure on this site is wrong, say which page and what you expected. Corrections '
         'are made against the source data, and the change is visible in the '
         '<a href="https://github.com/bilingoplusllc/mileagecurve">public repository</a> '
         'history — there is no version of this site that only we can see.</p>',
         '<h2>What we cannot help with</h2>',
         '<p>We are not the regulator and not the manufacturer. To report a safety defect on your '
         'own vehicle, file directly with '
         '<a href="https://www.nhtsa.gov/report-a-safety-problem">NHTSA</a> — that is the record '
         'this site is built from, so filing there is also what makes the data better. For a '
         'recall on a specific car, check the VIN with '
         '<a href="https://www.nhtsa.gov/recalls">NHTSA\'s lookup</a>; it is free and takes under '
         'a minute.</p>',
         '<h2>Reuse and press</h2>',
         '<p>The generated aggregates are published under CC BY 4.0 — attribute to '
         f'{SITE} and link back. The full pipeline is public, so any figure here can be '
         'reproduced from the original government data. If you are writing something and need a '
         'cut of the data we do not publish, ask.</p>']
    return shell(f"Contact — {SITE}", f"How to reach {OWNER} about {SITE}.",
                 "\n".join(B), f"{DOMAIN}/contact/")


def render_terms(shell) -> str:
    B = ['<h1>Terms</h1>',
         f'<p class="sub">Last updated {POLICY_UPDATED}.</p>',
         '<h2>What this site is</h2>',
         '<p>An information reference compiled from public United States government records. It is '
         'published for general information and is not advice — not mechanical, not financial, and '
         'not legal. Decisions about buying, selling or repairing a vehicle are yours.</p>',
         '<h2>Accuracy</h2>',
         '<p>Figures are computed automatically from the NHTSA Office of Defects Investigation '
         'dataset and refreshed monthly. That dataset records what owners chose to report; it is '
         'not a census of failures and not a failure rate per vehicle sold. Records may be '
         'incomplete, duplicated or mistaken, and our processing may contain errors of its own. '
         'The methodology and its limits are described on the '
         '<a href="/methodology/">methodology page</a>, and the code is public.</p>',
         '<h2>Reuse</h2>',
         '<p>The underlying NHTSA data is a work of the United States government and in the public '
         'domain. Aggregates and text generated by this site are licensed CC BY 4.0: reuse them '
         f'with attribution to {SITE} and a link. The pipeline source is MIT-licensed.</p>',
         '<h2>Third parties</h2>',
         '<p>This site links to external sites, including manufacturer and regulator pages, and '
         'will carry third-party display advertising. We do not control that content and are '
         'not responsible for it.</p>',
         '<h2>Liability</h2>',
         '<p>The site is provided as is, without warranty. To the extent the law allows, '
         f'{OWNER} is not liable for losses arising from use of it.</p>',
         f'<h2>Contact</h2><p><a href="/contact/">Get in touch</a> · {OWNER}.</p>']
    return shell(f"Terms — {SITE}", f"Terms of use for {SITE}.",
                 "\n".join(B), f"{DOMAIN}/terms/")

def render_vehicles_index(index: list[dict], shell) -> str:
    """Полный каталог: каждое поколение получает ссылку с одной страницы.

    Сгруппировано по марке, внутри — по модели и году. Строка несёт годы,
    число отчётов с пробегом и медиану: список, который сам по себе отвечает
    на вопрос «что тут есть», а не только раздаёт ссылки.
    """
    by_make: dict[str, dict[str, list[dict]]] = {}
    for pg in index:
        by_make.setdefault(names.display(pg["make"]), {}) \
               .setdefault(names.display(pg["model"]), []).append(pg)

    total = sum(pg["n"] for pg in index)
    young_edge = date.today().year - 4
    makes = sorted(by_make)

    B = [f'<ol class="crumbs"><li><a href="/">Home</a></li><li>All vehicles</li></ol>',
         "<h1>All vehicles</h1>",
         f'<p class="sub">Every generation covered here &mdash; {len(index)} of them across '
         f'{len(makes)} makes, built from {fmt(total)} complaints that record mileage at '
         f'failure. Median is the mileage by which half the reports on that generation had '
         f'been filed.</p>',
         '<p class="warn-note">Medians fall as generations get newer, and that is age, not '
         'decline. A car built in 2023 has only covered a few thousand miles, so its reports '
         'can only have come at low mileage. &#8224; marks generations too recent to judge. '
         '<strong>Compare generations of similar age, never across the column.</strong></p>']

    # Алфавитный перескок: 40 марок — это длинная страница, и без него
    # телефон листает вслепую.
    jump = "".join(f'<a href="#{_slug(m)}">{esc(m)}</a>' for m in makes)
    B.append(f'<nav class="az" aria-label="Makes">{jump}</nav>')

    for make in makes:
        models = by_make[make]
        gens = sum(len(v) for v in models.values())
        B.append(f'<h2 id="{_slug(make)}"><a href="/{_slug(make)}/">{esc(make)}</a></h2>')
        B.append(f'<p class="meta">{gens} generation{"s" if gens != 1 else ""} across '
                 f'{len(models)} model{"s" if len(models) != 1 else ""}.</p>')
        B.append('<ul class="gens gr">')
        B.append('<li class="gen-key gk1"><span><span>Generation</span>'
                 '<i>Reports</i><i>Median</i></span></li>')
        for model in sorted(models):
            for pg in sorted(models[model], key=lambda x: x["y0"]):
                med = pg.get("median")
                med_txt = f"{names.round_miles(med):,}" if med else "&mdash;"
                dag = "&#8224;" if pg.get("y1", 0) >= young_edge else ""
                B.append(f'<li><a href="{pg["url"]}">'
                         f'<span class="gy">{esc(model)} {pg["y0"]}&#8211;{pg["y1"]}{dag}</span>'
                         f'<span class="gn">{fmt(pg["n"])}</span>'
                         f'<span class="gm">{med_txt}</span></a></li>')
        B.append("</ul>")

    B.append('<p class="prov">Every page here is generated from the NHTSA Office of Defects '
             'Investigation dataset. <a href="/methodology/">How this is built</a></p>')

    return shell(f"All vehicles — every generation covered | {SITE}",
                 f"Complete index of {len(index)} vehicle generations across {len(makes)} makes, "
                 f"with the mileage at which half of all failure reports had been filed.",
                 "\n".join(B), f"{DOMAIN}/vehicles/", nav_key="home")
