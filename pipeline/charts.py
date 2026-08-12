"""
Графики. Только стандартная библиотека, никаких библиотек визуализации — D-009.

ПРАВИЛА, выведенные аудитом 2026-08-12 — нарушать нельзя:

1. Внутри SVG НЕТ элементов <text>. Раньше подписи жили в системе координат
   viewBox 720×260, и при ширине экрана 360 масштаб 0,386 давал шрифт 4,05 пикселя —
   нечитаемо. Теперь подписи это обычные HTML-элементы рядом с графиком, поэтому
   их размер задаётся в настоящих пикселях и не зависит от ширины.

2. preserveAspectRatio="none" плюс фиксированная высота в CSS: растягивается только
   горизонталь. Для прямоугольников это безвредно, для кругов и диагоналей — нет,
   поэтому в этих графиках их нет.

3. Никакого абсолютного позиционирования. Домашнее правило нарушалось трижды.

4. Корзины гистограммы РАВНОМЕРНЫЕ (см. analyze.py). Высота столбика пропорциональна
   плотности отказов, иначе график фабрикует пики шириной корзины.
"""
from __future__ import annotations

import html

import names

DOMAIN = 200_000          # основная область оси X, мили
DEFECT_EDGE = 12_000      # граница окна «заводской брак»
PLOT_W = 948.0            # ширина области столбиков в единицах viewBox
OVER_X = 968.0            # отдельный столбик «200k+»
OVER_W = 32.0


def esc(s) -> str:
    return html.escape(str(s), quote=True)


def fmt(n) -> str:
    return f"{int(n):,}" if n is not None else "—"


def x_of(miles: float) -> float:
    """Мили → координата X. Одна арифметика для гистограммы, полосок и подписей оси."""
    return min(miles, DOMAIN) / DOMAIN * PLOT_W


def axis_row() -> str:
    """Подписи оси — HTML, а не SVG. Восемь делений по 11,85% = 94,8% = 948/1000."""
    marks = [25, 50, 75, 100, 125, 150, 175, 200]
    cells = "".join(
        f'<span{" class=\"q\"" if i % 2 == 0 else ""}>{m}k</span>'
        for i, m in enumerate(marks))
    return f'<div class="xax" aria-hidden="true">{cells}</div>'


def _describe(hist: dict, shape: dict, total: int, label: str) -> str:
    """Текстовое описание графика для скринридера — график обязан быть доступен."""
    bins = hist["bins"]
    top = max(bins, key=lambda b: b["count"]) if bins else None
    parts = [f"Histogram of {fmt(total)} owner-reported failures by mileage, in "
             f"{fmt(hist['width'])}-mile bins from 0 to {fmt(DOMAIN)}."]
    if top and top["count"]:
        parts.append(f"The tallest bin is {fmt(top['lo'])} to {fmt(top['hi'])} miles with "
                     f"{fmt(top['count'])} complaints, {top['pct']} percent of the total.")
    if shape.get("note"):
        parts.append(shape["note"][0].upper() + shape["note"][1:])
    ov = hist.get("overflow") or {}
    if ov.get("count"):
        parts.append(f"A further {fmt(ov['count'])} complaints, {ov['pct']} percent, were "
                     f"reported above {fmt(DOMAIN)} miles and are shown as a separate "
                     f"detached bar.")
    if shape.get("median"):
        parts.append(f"Median mileage at failure is {fmt(shape['median'])}.")
    return " ".join(parts)


def histogram(hist: dict, shape: dict, total: int, label: str, uid: str = "h") -> str:
    """Гистограмма пробегов до отказа. Равномерные корзины, подписи снаружи."""
    bins = hist["bins"]
    ov = hist.get("overflow") or {}
    mx = max([b["count"] for b in bins] + [ov.get("count", 0)]) or 1
    step = PLOT_W / len(bins)
    highlight = shape.get("kind") in ("early", "bimodal")

    parts = [
        f'<svg class="hist" viewBox="0 0 1000 100" preserveAspectRatio="none" '
        f'role="img" aria-labelledby="{uid}t {uid}d">',
        f'<title id="{uid}t">Mileage at failure, {esc(label)}</title>',
        f'<desc id="{uid}d">{esc(_describe(hist, shape, total, label))}</desc>',
    ]
    # окно «заводской брак» — подложка, в потоке координат, не оверлей
    if highlight:
        parts.append(f'<rect class="zone" x="0" y="0" width="{x_of(DEFECT_EDGE):.1f}" height="100"/>')
    for gy in (25, 50, 75):
        parts.append(f'<line class="grid" x1="0" y1="{gy}" x2="1000" y2="{gy}" '
                     f'vector-effect="non-scaling-stroke"/>')

    for i, b in enumerate(bins):
        if not b["count"]:
            continue  # пропуск = ноль; столбик в 1 пиксель читался бы как «немного»
        h = b["count"] / mx * 100
        cls = "bar-hi" if (highlight and b["hi"] <= DEFECT_EDGE) else "bar"
        parts.append(f'<rect class="{cls}" x="{i * step:.2f}" y="{100 - h:.2f}" '
                     f'width="{step:.2f}" height="{h:.2f}"/>')

    if shape.get("median"):
        mx_pos = x_of(shape["median"])
        parts.append(f'<line class="med" x1="{mx_pos:.1f}" y1="0" x2="{mx_pos:.1f}" y2="100" '
                     f'vector-effect="non-scaling-stroke"/>')
    if ov.get("count"):
        h = ov["count"] / mx * 100
        parts.append(f'<rect class="over" x="{OVER_X}" y="{100 - h:.2f}" '
                     f'width="{OVER_W}" height="{h:.2f}"/>')
    parts.append('<line class="base" x1="0" y1="100" x2="1000" y2="100" '
                 'vector-effect="non-scaling-stroke"/>')
    parts.append("</svg>")

    legend = []
    if highlight:
        legend.append(f'<li><span class="k k-hi"></span>First {fmt(DEFECT_EDGE)} miles — '
                      f'{shape.get("early_pct", 0)}% of all failures</li>')
    legend.append('<li><span class="k k-bar"></span>Rest of the range</li>')
    if shape.get("median"):
        legend.append('<li><span class="k k-med"></span>Median</li>')
    if ov.get("count"):
        legend.append(f'<li><span class="k k-over"></span>{fmt(DOMAIN)}+ — {fmt(ov["count"])} '
                      f'complaints ({ov["pct"]}%), plotted separately</li>')

    return (f'<figure class="chart">{"".join(parts)}{axis_row()}'
            f'<ul class="brk-row">{"".join(legend)}</ul></figure>')


def system_strips(systems: list[dict], limit: int = 7) -> str:
    """Полоски «когда отказывает каждая система» на той же оси, что и гистограмма.

    Здесь и живёт настоящая находка сайта: у Prius 2010–2015 гидроконтур тормозов
    имеет медиану 3 500 миль (средняя половина 1 000–7 500), а тормоза в целом —
    87 000 (34 000–128 000). Средние половины НЕ пересекаются: это две разные
    поломки под одним словом. В общей гистограмме этого не видно, а здесь видно.
    """
    rows = [x for x in systems if x.get("median_miles")][:limit]
    if len(rows) < 2:
        return ""

    items = []
    for x in rows:
        p25, p75 = x.get("p25_miles", x["median_miles"]), x.get("p75_miles", x["median_miles"])
        x0, x1 = x_of(p25), x_of(p75)
        w = max(x1 - x0, 6.0)          # минимальная видимая ширина
        mpos = x_of(x["median_miles"])
        cls = "iqr-hi" if x["median_miles"] <= DEFECT_EDGE else "iqr"
        name = esc(x.get("display_name") or x["system"].title())
        items.append(
            f'<li><span class="nm">{name}</span>'
            f'<svg class="strip" viewBox="0 0 1000 16" preserveAspectRatio="none" aria-hidden="true">'
            f'<rect class="track" x="0" y="6" width="1000" height="4"/>'
            f'<rect class="{cls}" x="{x0:.1f}" y="2" width="{w:.1f}" height="12"/>'
            f'<line class="med" x1="{mpos:.1f}" y1="0" x2="{mpos:.1f}" y2="16" '
            f'vector-effect="non-scaling-stroke"/></svg>'
            f'<span class="mv">{fmt(names.round_miles(x["median_miles"]))}</span>'
            # Округление одинаковое в заголовке и в подписи для чтеца экрана:
            # иначе рядом стоят «59,000» и «median 58,847 miles» — на одну и ту же величину.
            f'<span class="vh">median {fmt(names.round_miles(x["median_miles"]))} miles, '
            f'middle half {fmt(names.round_miles(p25))} to {fmt(names.round_miles(p75))}</span></li>')

    return (f'<ol class="sys">{"".join(items)}</ol>{axis_row()}')


def percentiles(shape: dict) -> str:
    if not shape.get("median"):
        return ""
    cells = [("10%", shape["p10"]), ("25%", shape["p25"]),
             ("Median", shape["median"], True), ("75%", shape["p75"]), ("90%", shape["p90"])]
    out = []
    for c in cells:
        mid = ' class="mid"' if len(c) > 2 else ""
        out.append(f'<div{mid}><dt>{c[0]}</dt><dd>{fmt(c[1])}</dd></div>')
    return f'<dl class="pct">{"".join(out)}</dl>'


def bins_table(hist: dict) -> str:
    """Числа под графиком — для тех, кто хочет проверить, и для скринридеров."""
    rows = []
    for b in hist["bins"]:
        if not b["count"]:
            continue
        rows.append(f'<tr><td>{fmt(b["lo"])}–{fmt(b["hi"])}</td>'
                    f'<td class="num">{fmt(b["count"])}</td><td class="num">{b["pct"]}%</td></tr>')
    ov = hist.get("overflow") or {}
    if ov.get("count"):
        rows.append(f'<tr><td>{fmt(ov["lo"])}+</td><td class="num">{fmt(ov["count"])}</td>'
                    f'<td class="num">{ov["pct"]}%</td></tr>')
    return (f'<details class="nums"><summary>Show the numbers</summary>'
            f'<div class="tw" tabindex="0" role="region" aria-label="Complaints by mileage bin">'
            f'<table><caption class="vh">Complaints by mileage bin</caption><thead><tr>'
            f'<th scope="col">Mileage</th><th scope="col" class="num">Complaints</th>'
            f'<th scope="col" class="num">Share</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div></details>')
