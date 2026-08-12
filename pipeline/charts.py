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
import math

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


def _yaxis(mx: int) -> str:
    """Пять подписей сверху вниз, ровно по линиям сетки y=0/25/50/75/100.

    Честно потому, что histogram() масштабирует самый высокий столбик ровно
    в 100 единиц. Без этой шкалы у графика не было величины: высота была,
    а сколько именно — нигде.
    """
    steps = [int(mx * k / 4 + 0.5) for k in (4, 3, 2, 1, 0)]
    return ('<div class="yax" aria-hidden="true">'
            + "".join(f"<span>{fmt(v)}</span>" for v in steps) + "</div>")


def ruler(shape: dict) -> str:
    """Пятичисловая сводка на ТОЙ ЖЕ линейной оси x_of(), что и столбики.

    Плоский правый хвост сам по себе не сообщает ничего; линейка превращает
    его в сведения, не трогая кодировку гистограммы. Медиана — два совпадающих
    штриха: тёмный во всю высоту строки, чтобы читаться на фоне, и светлый
    внутри коробки, чтобы читаться как вырез в тёмной заливке.
    """
    if not shape.get("median"):
        return ""
    a, b = x_of(shape["p10"]), x_of(shape["p90"])
    c, d = x_of(shape["p25"]), x_of(shape["p75"])
    m = x_of(shape["median"])
    return (f'<svg class="ruler" viewBox="0 0 1000 18" preserveAspectRatio="none" '
            f'aria-hidden="true">'
            f'<rect class="rtrack" x="0" y="8" width="{PLOT_W}" height="2"/>'
            f'<rect class="whisk" x="{a:.1f}" y="6" width="{max(b - a, 2):.1f}" height="6"/>'
            f'<rect class="box" x="{c:.1f}" y="2" width="{max(d - c, 2):.1f}" height="14"/>'
            f'<line class="rmed" x1="{m:.1f}" y1="0" x2="{m:.1f}" y2="18" '
            f'vector-effect="non-scaling-stroke"/>'
            f'<line class="rmed-in" x1="{m:.1f}" y1="3" x2="{m:.1f}" y2="15" '
            f'vector-effect="non-scaling-stroke"/></svg>')


def histogram(hist: dict, shape: dict, total: int, label: str, uid: str = "h",
              kicker: str = "", title: str = "", foot: str = "") -> str:
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

    # Выноска к самому высокому столбику. grid-column — ЕДИНСТВЕННЫЙ строчный
    # стиль во всей сборке, и он задаёт место в потоке, а не position.
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


LOG_MIN = 500.0            # левая привязка пропорциональной оси, мили
LOG_MAX = 200_000.0
_LSPAN = math.log10(LOG_MAX / LOG_MIN)      # 2,60206 десятичных порядка
STRIP_H = 26
EDGE_X = 530.4             # lx(DEFECT_EDGE), проверено


def lx(miles: float) -> float:
    """Мили → X в системе 0..1000, пропорционально, с привязкой к 500 милям.

    ТОЛЬКО ДЛЯ ПОЛОЖЕНИЙ. Никогда не применять к отметке, у которой ШИРИНА или
    ПЛОЩАДЬ кодирует количество или плотность. Равные корзины на сжатой оси —
    ровно та кодировка, что однажды уже сфабриковала здесь главный вывод;
    гистограмма остаётся на x_of() и линейной навсегда.

    И ещё: полотно и строка подписей обязаны делить ОДНУ конечную константу.
    lx() занимает все 0..1000, поэтому колонки axis_row_log() дают 100,000%.
    x_of() занимает PLOT_W=948, поэтому колонки axis_row() дают 94,8%. Не смешивать.
    """
    m = min(max(float(miles), LOG_MIN), LOG_MAX)
    return (math.log10(m) - math.log10(LOG_MIN)) / _LSPAN * 1000.0


def axis_row_log() -> str:
    """Правый край колонки k — это деление k, поэтому подпись, прижатая вправо,
    попадает точно на свою линию сетки. Ширины — последовательные разности lx()
    и в сумме дают ровно 100,000%. Первая ячейка — пара, чтобы «500» встало
    вx=0 без второго перекрывающего элемента и без всякого позиционирования."""
    return ('<div class="sys-axis"><span class="lbl" aria-hidden="true"></span>'
            '<div class="ticks" aria-hidden="true">'
            '<span class="pair"><i>500</i><i>1k</i></span>'
            '<span>2k</span><span>5k</span><span>10k</span><span>20k</span>'
            '<span>50k</span><span>100k</span><span>200k</span></div></div>')


def system_strips(systems: list[dict], limit: int = 7,
                  kicker: str = "", title: str = "", foot: str = "") -> str:
    """Средние половины сообщений на пропорциональной шкале пробега.

    Здесь и живёт настоящая находка сайта: у Prius 2010–2015 гидроконтур тормозов
    имеет медиану 3 500 миль (средняя половина 1 000–7 500), а тормоза в целом —
    87 000 (34 000–128 000). Средние половины НЕ пересекаются: это две разные
    поломки под одним словом. В общей гистограмме этого не видно, а здесь видно.

    Строки ОТБИРАЮТСЯ по числу сообщений (топ-N), а затем СОРТИРУЮТСЯ по медиане
    по возрастанию: разделение на две группы создаётся порядком строк раньше,
    чем читатель дойдёт до слов. Оба конца интервала печатаются под медианой —
    на сжатой оси ширина полосы кодирует ОТНОШЕНИЕ, а не число миль, и напечатанные
    концы не дают ширине остаться единственным источником для читателя.
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
        # Метка «интервал уходит левее шкалы»: p25 ниже привязки в 500 миль.
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

    body = ('<div class="sys-head" aria-hidden="true"><span class="hd">System</span>'
            '<span class="band"><span class="band-a"><b>0&#8211;12,000 mi</b> '
            '<i>factory-defect window</i></span>'
            '<span class="band-b"><b>12,000 mi and beyond</b> '
            '<i>wear and service life</i></span></span>'
            '<span class="hd hd-r">Median</span></div>'
            f'<ol class="sys">{"".join(items)}</ol>{axis_row_log()}')

    sub = ('Bar spans the middle half of reports; the notch inside each bar is the median. '
           'Miles at failure on a proportional scale &mdash; equal distances are '
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
