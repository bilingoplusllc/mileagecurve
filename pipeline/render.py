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
from datetime import date, datetime
from pathlib import Path

import analyze
import charts
import pages
import names
import search
import narrative

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "mileagecurve.db"
GENS = ROOT / "data" / "generations.clean.json"
DIST = ROOT / "dist"

GA_ID = "G-WHE70YWW82"  # GA4, свойство MileageCurve в аккаунте BiLingoPlus
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


def odo_digits(n) -> str:
    """Число как ячейки одометра. ПРАВИЛО ОДНОГО МЕСТА: только настоящие
    показания одометра (медиана пробега при отказе) — НИКОГДА счётчики жалоб
    и проценты: статистика не показание одометра, и размывание видов чисел
    было бы фабрикацией рода. Без анимации; медиана уже округлена
    names.round_miles. Деградирует до обычных цифр без CSS."""
    if n is None:
        return "&mdash;"
    return ('<span class="odo-w">' + "".join(
        f'<i>{ch}</i>' if ch == "," else f"<b>{ch}</b>" for ch in f"{int(n):,}")
        + "</span>")


def fmt(n) -> str:
    return f"{int(n):,}".replace(",", ",") if n is not None else "—"



# ---------------------------------------------------------------- prose from data
def lead_paragraph(s: dict, gen: dict) -> str:
    """Вводный блок, выведенный ИЗ ЧИСЕЛ. Текст только английский — сайт для рынка США."""
    sh = s["shape"]
    name = f'{names.display(s["make"])} {names.display(s["model"])}'
    out = [f'Owners filed <strong>{fmt(s["complaints_total"])}</strong> complaints with NHTSA '
           f'about the {s["year_start"]}–{s["year_end"]} {name}, and '
           f'<strong>{fmt(s["complaints_with_miles"])}</strong> of them record the mileage at '
           f'which the failure happened. That is enough to show not just <em>what</em> fails, '
           f'but <em>when</em>.']

    if sh.get("kind") == "bimodal":
        out.append(f'This generation has two distinct failure patterns rather than one, which is '
                   f'the most useful thing on this page. {sh["note"]} Two different problems share '
                   f'one name in the complaint data — and an average of the two describes neither.')
    elif sh.get("kind") == "early":
        out.append(f'{sh["note"]} Failures clustered that early usually indicate a design or '
                   f'manufacturing problem rather than wear.')
    elif sh.get("kind") == "late":
        out.append(f'{sh["note"]} The car generally reaches substantial mileage before trouble '
                   f'starts.')
    elif sh.get("median"):
        out.append(f'{sh["note"]} The median is {fmt(sh["median"])} miles.')

    top = [x for x in s["systems"] if x.get("median_miles")][:3]
    if top:
        bits = [f'{narrative.plain(x["system"])} ({x["share"]}% of complaints, typically around '
                f'{fmt(names.round_miles(x["median_miles"]))} miles)' for x in top]
        out.append("The most-reported areas are " + ", ".join(bits) + ".")

    if s["recalls_count"]:
        sev = (f' {s["severe_advisories"]} of them carry a severe NHTSA advisory.'
               if s["severe_advisories"] else "")
        out.append(f'{s["recalls_count"]} recall campaign'
                   f'{"s" if s["recalls_count"] != 1 else ""} cover this generation.{sev}')

    # Семья запросов «is it reliable?»: слово «reliable» появляется ТОЛЬКО
    # в кавычках как вопрос читателя, никогда как наш вердикт (D-007).
    out.append('If you arrived asking &ldquo;is it reliable?&rdquo; &mdash; this page answers '
               'the version of that question the data can support: which problems owners '
               'reported, and at what mileage.')

    if gen.get("mixed_years"):
        yrs = ", ".join(str(y) for y in gen["mixed_years"])
        out.append(f'<mark>Note: in {yrs}, both this generation and the previous one were sold '
                   f'at the same time, and NHTSA complaints are not separated by body.</mark>')

    return "".join(f"<p>{p}</p>" for p in out)


# ---------------------------------------------------------------- page
CSS = """
/* ===========================================================================
   MileageCurve — complete stylesheet. Replaces the current CSS block entirely.
   Vanilla CSS. No external requests, no JS, no framework, no build step.

   HOUSE RULE, enforced: this file contains ZERO `position:absolute` and zero
   `float`. Every composition — bars, legends, scroll cues, the visually-hidden
   helper — is in normal flow. Grep this block for "absolute": no hits.
   =========================================================================== */

/* ---------- 1. tokens ------------------------------------------------------
   Light is the base. Dark redefines only what changes. Every contrast figure
   below is measured, not guessed.                                          */
:root{
  color-scheme:light dark;

  /* Засечки для слов, гротеск для чисел. Внешних запросов не появляется —
     обе гарнитуры системные. ПРАВИЛО: у Georgia минускульные цифры (часть
     из них уходит ниже строки), поэтому ни одна строка с числом не должна
     попадать в элемент с засечками. .h1-years, .verdict и все цифры —
     явно гротеском именно по этой причине. */
  --serif:Georgia,"Times New Roman",Times,"Noto Serif",serif;
  --sans:system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;

  --bg:#fbfbfa; --surface:#ffffff;
  --ink:#181c1b;          /* 16.9:1 on --bg */
  --muted:#5a6360;        /*  6.0:1 on --bg */
  --line:#d5dbd9;         /*  1.40:1 on --surface — hairlines are now visible */
  --line-strong:#adb8b4;  /*  2.05:1 on --surface — structural edges */
  --track:#eef1f0; --warn:#f6f1e6;

  --accent:#0f6e5e; --accent-ink:#0b5347;   /* links 8.6:1 on --bg */
  --peak:#a8401f;                            /* 6.1:1 on --surface */

  /* chart ink: separated in LIGHTNESS, not hue, so the encoding survives
     greyscale, print and every colour-vision deficiency.
     --bar был #7e938e — 2.89:1 на кремовой зоне --warn, ниже порога 3:1
     для нетекстовой графики. #758a85: 3.25:1 на --warn, 3.66:1 на белом. */
  --bar:#758a85; --bar-hi:#0b4238;
  --tick:#ffffff;         /* метка медианы — рисуется ТОЛЬКО внутри полосы */

  /* severe advisories. Never `opacity` on a text-bearing element. */
  --danger-bg:#8c2f0e; --danger-fg:#ffffff; --danger-ring:#8c2f0e;  /* 8.3:1 */

  --shadow:rgba(20,30,28,.13);   /* остаётся ради одной работы: подсказка прокрутки */

  --f-2xs:12px; --f-xs:13px; --f-sm:15px; --f-md:17px;
  --f-lg:21px; --f-xl:26px; --f-2xl:34px; --f-3xl:44px;
  --s-1:4px; --s-2:8px; --s-3:16px; --s-4:24px; --s-5:32px; --s-6:48px; --s-7:64px;
  --measure:68ch;   /* ~578px at 17px — 66-70 characters */

  /* Было 10px. Самый громкий признак шаблона на странице: скруглённые
     карточки, поля ввода и таблицы читаются как готовая тема, а не как
     свёрстанное издание. */
  --radius:2px;
  --rule:3px;             /* линия под шапкой и над экспонатом */
}
@media(prefers-color-scheme:dark){:root{
  --bg:#111413; --surface:#191d1c;
  --ink:#e6eae8;          /* 15.3:1 */
  --muted:#9aa5a1;        /*  7.3:1 */
  --line:#2f3634;         /*  1.38:1 on --surface */
  --line-strong:#4a5451;  /*  2.21:1 on --surface */
  --track:#232827; --warn:#2a2419;

  --accent:#4fc0aa; --accent-ink:#7ad6c4; --peak:#f0a882;
  --bar:#667672; --bar-hi:#7fe0c8;        /* 3.5:1 between them */
  --tick:#111413;

  --danger-bg:transparent; --danger-fg:#f0a882; --danger-ring:#f0a882;  /* 8.7:1 */
  --shadow:rgba(0,0,0,.55);
}}

/* ---------- 2. base ------------------------------------------------------- */
*,*::before,*::after{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--ink);
  font:var(--f-md)/1.55 system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
img,svg{display:block;max-width:100%}

.wrap{max-width:880px;margin:0 auto;padding:var(--s-4) var(--s-4) var(--s-7)}
@media(max-width:479px){.wrap{padding-left:var(--s-3);padding-right:var(--s-3)}}

/* Reading measure is decoupled from the container: text narrows, figures stay
   wide. One shared left edge for prose and figures — nothing is centred, so
   nothing can look adrift. */
p,li,dd,blockquote,.note,.meta,.sub{max-width:var(--measure)}
.tw,figure.chart,figure.fig,ol.sys,.ad,ul.rel,.pct,.prov,table,
.sys-head,.sys-axis,.band,ul.makes,.creds,.qpop,
.fig-kicker,.fig-title,.fig-sub{max-width:none}

p{margin:0 0 var(--s-5)}            /* 32px gap >….4px leading */
p:last-child{margin-bottom:0}
ul,ol{margin:0 0 var(--s-5);padding-left:var(--s-4)}
li{margin:0 0 var(--s-2)}
strong{font-weight:600}
a{color:var(--accent-ink);text-underline-offset:2px;text-decoration-thickness:1px}
a:hover{text-decoration-thickness:2px}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px;border-radius:3px}

/* visually hidden — no `position`, so it cannot escape flow */
.vh{display:block;width:1px;height:1px;padding:0;border:0;overflow:hidden;
  white-space:nowrap;clip-path:inset(50%)}
.skip{display:inline-block;width:1px;height:1px;overflow:hidden;
  white-space:nowrap;clip-path:inset(50%)}
.skip:focus-visible{width:auto;height:auto;overflow:visible;clip-path:none;
  padding:var(--s-2) var(--s-3);margin-bottom:var(--s-2);background:var(--surface);
  border:1px solid var(--accent);border-radius:var(--radius);text-decoration:none}

/* ---------- 3. header, nav, breadcrumbs ----------------------------------- */
/* Шапка издания: марка с подзаголовком слева, рубрики справа, всё это
   отбито жирной линией. Раньше здесь стояли имя и четыре серые ссылки
   без веса — страница начиналась ни с чего. */
header.site{display:grid;grid-template-columns:auto minmax(0,1fr);align-items:end;
  gap:2px var(--s-4);padding:var(--s-3) 0 10px;margin-bottom:var(--s-5);
  border-bottom:var(--rule) solid var(--ink)}
header.site .brand{grid-column:1;grid-row:1;display:flex;align-items:center;gap:8px;
  font-family:var(--serif);font-weight:700;font-size:24px;letter-spacing:-.02em;
  line-height:1;color:var(--ink);text-decoration:none}
header.site .brand svg{color:var(--accent);flex:none}
header.site .masthead-tag{grid-column:1;grid-row:2;font-size:var(--f-2xs);letter-spacing:.1em;
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

.crumbs{display:flex;flex-wrap:wrap;gap:var(--s-1) var(--s-2);list-style:none;
  padding:0;margin:0 0 var(--s-2);font-size:var(--f-xs);color:var(--muted)}
.crumbs li{margin:0}
.crumbs a{color:var(--muted)}
.crumbs li+li::before{content:"›";margin-right:var(--s-2);color:var(--line-strong)}

/* ---------- 4. page title, dateline, headings ----------------------------- */
/* ДОМАШНЕЕ ПРАВИЛО: элемент с границей НИКОГДА не получает max-width — граница
   ровно такой же ширины, как элемент, и именно это дало культю в 260px.
   Ограничивать нужно колонку, а не сам блок с линией. */
h1{font-family:var(--serif);font-size:clamp(28px,4.6vw,var(--f-2xl));line-height:1.12;
  letter-spacing:-.018em;font-weight:700;margin:0 0 var(--s-2);max-width:22ch}
/* Цифры — всегда гротеском: у Georgia минускульные цифры, и «2010–2015»
   в засечках прыгает по базовой линии. */
.h1-years{font-family:var(--sans);font-weight:400;font-size:.72em;color:var(--muted);
  letter-spacing:0;font-variant-numeric:tabular-nums;white-space:nowrap}
.sub{color:var(--muted);font-size:var(--f-sm);margin:0 0 var(--s-3)}

.dateline{display:flex;flex-wrap:wrap;align-items:baseline;gap:var(--s-1) var(--s-3);
  font-size:var(--f-xs);color:var(--muted);margin:0 0 var(--s-4);
  padding-bottom:var(--s-3);border-bottom:1px solid var(--line);max-width:none}
.dateline b{font-weight:600;color:var(--ink)}
.dateline a{color:var(--muted)}
.dateline span+span::before{content:"·";margin-right:var(--s-3);color:var(--line-strong)}

h2{font-family:var(--serif);font-weight:400;font-size:var(--f-xl);line-height:1.22;
  letter-spacing:-.012em;margin:var(--s-6) 0 var(--s-3);padding-top:var(--s-3);
  border-top:1px solid var(--line-strong);max-width:none}
h3{font-family:var(--serif);font-weight:700;font-size:var(--f-lg);line-height:1.3;
  letter-spacing:-.008em;margin:var(--s-5) 0 var(--s-2);max-width:none}
:is(h1,h2,h3)+*{margin-top:0}
:is(h1,h2,h3)[id]{scroll-margin-top:var(--s-4)}

/* ---------- 5. cards ------------------------------------------------------ */
.card{background:var(--surface);border:1px solid var(--line);
  border-radius:var(--radius);padding:var(--s-4) var(--s-5);margin:var(--s-4) 0}
.card>:first-child{margin-top:0}
.card>:last-child{margin-bottom:0}
.finding{border-left:3px solid var(--ink)}

.verdict{font-size:var(--f-lg);line-height:1.4;margin:0 0 var(--s-4);
  max-width:var(--measure)}

.note{background:var(--warn);border-left:3px solid var(--peak);
  border-radius:0;padding:var(--s-3) var(--s-4);
  margin:var(--s-4) 0;font-size:var(--f-sm)}
.note>:last-child{margin-bottom:0}
mark{background:var(--warn);color:inherit;padding:0 3px;border-radius:2px;
  -webkit-box-decoration-break:clone;box-decoration-break:clone}

/* ---------- 6. histogram figure -------------------------------------------
   The SVG carries geometry only — no <text>. All labels are HTML siblings, so
   they are true CSS px at every viewport instead of scaling to 4px at 360.
   viewBox is 0 0 1000 100 with preserveAspectRatio="none": y is fixed by the
   CSS height, x stretches. Rectangles are immune to x-stretch; strokes are
   pinned with vector-effect. Never put a diagonal or a circle in here.      */
figure.chart{margin:0 0 var(--s-4);padding:0}

/* График как экспонат: рубрика, заголовок, пояснение, полотно, примечание.
   Раньше графики лежали россыпью в тексте и читались как остатки, хотя они
   и есть предмет сайта. Верхняя линия в 3px — та же, что под шапкой. */
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
/* У графика была высота, но не было величины: сколько именно жалоб в самом
   высоком столбике — не сказано нигде. Колонка слева даёт пять подписей ровно
   по линиям сетки; это честно, потому что высокий столбик масштабируется
   ровно в 100 единиц. */
figure.fig .plot{display:grid;grid-template-columns:auto minmax(0,1fr);gap:0 var(--s-2)}
figure.fig .pane{min-width:0}
.yax{display:flex;flex-direction:column;justify-content:space-between;
  height:clamp(220px,26vw,320px);font-size:var(--f-2xs);line-height:1;text-align:right;
  color:var(--muted);font-variant-numeric:tabular-nums}
.yax span{white-space:nowrap}
svg.hist{width:100%;height:clamp(220px,26vw,320px)}
.hist .zone{fill:var(--warn)}
.hist .bar{fill:var(--bar)}
.hist .bar-hi{fill:var(--bar-hi)}
/* Прозрачность как канал кодировки запрещена: она не переживает печать
   и читается как «менее достоверно», хотя означает другое. Но замена на
   --line-strong дала 2,05:1 на белом и 2,17:1 в тёмной теме — ниже порога
   3:1 для значимой графики. Столбик «200 000+» это те же данные, просто
   за пределами шкалы, поэтому заливка та же, а отделяет его обводка. */
.hist .over{fill:var(--bar);stroke:var(--ink);stroke-width:1;
  vector-effect:non-scaling-stroke}
.hist .grid{stroke:var(--line);stroke-width:1;stroke-dasharray:2 4;
  vector-effect:non-scaling-stroke}
.hist .base{stroke:var(--line-strong);stroke-width:1;vector-effect:non-scaling-stroke}
.hist .med{stroke:var(--ink);stroke-width:2;stroke-dasharray:3 3;
  vector-effect:non-scaling-stroke}

.cal{display:grid;grid-template-columns:repeat(8,11.85%);margin:0 0 var(--s-2)}
.cal span{font-size:var(--f-xs);line-height:1.35;color:var(--ink);
  border-left:2px solid var(--peak);padding:2px 0 2px 8px;max-width:none}

/* Линейка распределения на той же линейной оси: плоский правый хвост сам
   по себе не сообщает ничего, а пять чисел на нём — сообщают. */
svg.ruler{width:100%;height:18px;margin-top:6px}
.ruler .rtrack{fill:var(--line)}
.ruler .whisk{fill:var(--bar)}
.ruler .box{fill:var(--bar-hi)}
.ruler .rmed{stroke:var(--ink);stroke-width:2}
.ruler .rmed-in{stroke:var(--surface);stroke-width:2}

/* x axis: 8 tracks of 11.85% mirror the 948/1000 plot area, so a right-aligned
   label in track k sits exactly on the k x 25,000-mile boundary. The remaining
   5.2% is the gap plus the detached 200k+ bar, labelled in the legend below. */
.xax{display:grid;grid-template-columns:repeat(8,11.85%);margin:6px 0 0;
  font-size:var(--f-2xs);line-height:1.2;color:var(--muted);
  font-variant-numeric:tabular-nums}
.xax span{text-align:right;white-space:nowrap}
@media(max-width:479px){.xax .q{visibility:hidden}}  /* 8 labels -> 4 */

/* legend: names what each ink means, in words. Text is the only fully
   colour-blind-safe channel, so it carries the encoding and hue reinforces. */
.brk-row{display:flex;flex-wrap:wrap;gap:var(--s-2) var(--s-4);list-style:none;
  padding:0;margin:var(--s-3) 0 0;font-size:var(--f-xs);color:var(--ink)}
.brk-row li{display:flex;align-items:center;gap:var(--s-2);margin:0;max-width:none}
.brk-row .k{display:block;flex:none;width:14px;height:10px;border-radius:1px}
.brk-row .k-hi{background:var(--bar-hi)}
.brk-row .k-bar{background:var(--bar)}
.brk-row .k-over{background:var(--bar);box-shadow:inset 0 0 0 1px var(--ink)}
/* Медиана на графике — это штрих, а не заливка. Правила для .k-med не было
   вовсе, поэтому в легенде на всех 318 страницах перед словом Median зияла
   пустота: образец выводился, но был невидим. */
.brk-row .k-med{width:3px;height:14px;border-radius:1px;background:var(--ink)}

/* percentiles: five facts as five cells, not one run-on sentence.
   auto-fit needs no media query — 5 columns at desktop, 3 at 360px. */
/* Процентили — примечание к гистограмме, а не отдельный виджет в рамке
   со скруглениями рядом с ней. Ряд чисел по левому краю, внутри экспоната. */
.fig-foot .pct{display:grid;grid-template-columns:repeat(auto-fit,minmax(84px,1fr));
  gap:0;margin:0 0 var(--s-3);background:none;border:0;border-radius:0;
  border-top:1px solid var(--line-strong);overflow:visible;max-width:none}
.fig-foot .pct>div{background:none;text-align:left;
  padding:var(--s-2) var(--s-3) var(--s-2) 0;border-right:1px solid var(--line)}
.fig-foot .pct>div:last-child{border-right:0}
.pct{display:grid;grid-template-columns:repeat(auto-fit,minmax(92px,1fr));gap:1px;
  margin:var(--s-3) 0 0;background:var(--line);border:1px solid var(--line);
  overflow:hidden}
.pct>div{background:var(--surface);padding:var(--s-2) var(--s-2) 10px;text-align:center}
.pct dt{font-size:var(--f-2xs);letter-spacing:.08em;text-transform:uppercase;
  color:var(--muted)}
.pct dd{margin:2px 0 0;max-width:none;font-size:var(--f-lg);line-height:1.1;
  letter-spacing:-.02em;font-variant-numeric:tabular-nums;color:var(--ink)}
.pct .mid dd{font-weight:700}
.pct .mid dt{color:var(--ink)}

.meta{font-size:var(--f-xs);color:var(--muted);margin:0 0 var(--s-2);
  max-width:var(--measure)}

details.nums{margin-top:var(--s-3)}
details.nums summary{cursor:pointer;color:var(--muted);font-size:var(--f-xs);
  padding:var(--s-1) 0}
details.nums summary:hover{color:var(--ink)}

/* ---------- 7. system timing strips ---------------------------------------
   Ось ПРОПОРЦИОНАЛЬНАЯ (десятичный логарифм от 500 миль), а не линейная.
   На линейной шкале 0–200 000 медианы 3 000 и 3 500 превращались в кляксы
   у левого края, и главная находка сайта была не видна. Логарифм применён
   ТОЛЬКО к положению отметок; ширина полосы кодирует отношение, поэтому оба
   конца интервала печатаются словами рядом. Гистограмма остаётся линейной
   навсегда — неравные корзины уже однажды сфабриковали здесь вывод.        */
figure.sysfig{--sys-cols:minmax(8em,13em) minmax(0,1fr) 104px;--plot-span:2/3;
  --strip-h:26px;--edge-pct:53.04%}

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
/* Перенос, а не обрезка. Ширина полосы зависит от КОНТЕЙНЕРА, а не от окна:
   на странице поколения полотно ~408px, на главной ~800px, поэтому порогом
   по ширине окна эту подпись не спасти — при 885px её резало. */
.band>span{padding:3px 6px 4px 0;min-width:0;overflow:visible;
  white-space:normal;line-height:1.25}
.band-a{background:var(--warn);padding-left:4px}
.band b{font-weight:600;color:var(--ink);font-variant-numeric:tabular-nums}
.band i{display:block;font-style:normal;letter-spacing:.05em;text-transform:uppercase}

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

/* ---------- 8. tables ------------------------------------------------------
   The four gradients are a pure-CSS horizontal scroll cue: the two `local`
   layers are surface-coloured masks pinned to the content, the two `scroll`
   layers are shadows pinned to the box. When the table is fully visible the
   masks cover the shadows; when it can scroll, the shadow shows. No JS.     */
.tw{overflow-x:auto;margin:var(--s-3) 0;background:var(--surface);
  border:1px solid var(--line-strong);border-radius:var(--radius);
  background-image:
    linear-gradient(to right,var(--surface),transparent 28px),
    linear-gradient(to left,var(--surface),transparent 28px),
    linear-gradient(to right,var(--shadow),transparent 14px),
    linear-gradient(to left,var(--shadow),transparent 14px);
  background-position:0 0,100% 0,0 0,100% 0;
  background-repeat:no-repeat;
  background-size:36px 100%,36px 100%,14px 100%,14px 100%;
  background-attachment:local,local,scroll,scroll}

table{border-collapse:collapse;width:100%;font-size:var(--f-sm)}
caption{text-align:left;font-size:var(--f-xs);color:var(--muted);
  padding:var(--s-2) var(--s-3) 0}
/* Утопленная шапка, зебра, табличные цифры и вес на первой числовой колонке —
   той, которую сравнивают. Наведение подкрашено тёплым, чтобы читалось как
   ВЫДЕЛЕНИЕ, а не как ещё одна ступень зебры. */
thead th{text-align:left;vertical-align:bottom;font-size:var(--f-2xs);font-weight:600;
  letter-spacing:.08em;text-transform:uppercase;color:var(--muted);
  background:var(--track);white-space:normal;padding:10px var(--s-3);
  border-bottom:1px solid var(--line-strong)}
thead th.num{text-align:right}
td,tbody th{text-align:left;vertical-align:top;font-weight:400;
  padding:10px var(--s-3);border-bottom:1px solid var(--line);color:var(--ink)}
tbody tr:nth-child(even)>*{background:var(--track)}
tbody tr:last-child>*{border-bottom:0}
tbody tr:hover>*{background:var(--warn)}
.num{text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums;
  letter-spacing:-.01em}
tbody td.num:first-of-type{font-weight:600}
.sys-name{min-width:10ch}

/* ---------- 9. quotes ----------------------------------------------------- */
blockquote.quote{margin:var(--s-4) 0;padding:0 0 0 var(--s-3);
  border-left:2px solid var(--line-strong);font-size:var(--f-sm);color:var(--ink)}
blockquote.quote p{margin:0;max-width:var(--measure)}
blockquote.quote cite{display:block;margin-top:var(--s-2);font-style:normal;
  font-size:var(--f-xs);color:var(--muted)}
blockquote.quote cite a{color:var(--muted)}

/* ---------- 10. tags and advisories --------------------------------------- */
/* Один знак, три оттенка. Скругления в 999px — типовая мебель готовых тем. */
.tag,.badge,.alert{display:inline-block;margin:0 var(--s-1) 2px 0;padding:2px 9px;
  border-radius:var(--radius);font-size:var(--f-2xs);line-height:1.5;font-weight:600;
  white-space:nowrap;vertical-align:baseline;background:var(--track);
  color:var(--muted);box-shadow:inset 0 0 0 1px var(--line)}
.tag-weak{background:transparent;box-shadow:inset 0 0 0 1px var(--line-strong)}
.alert{background:var(--danger-bg);color:var(--danger-fg);
  box-shadow:inset 0 0 0 1px var(--danger-ring)}

/* ---------- 11. link chips (related generations, index) -------------------- */
ul.rel{list-style:none;padding:0;margin:var(--s-3) 0 var(--s-4);
  display:flex;flex-wrap:wrap;gap:10px}
ul.rel li{margin:0;max-width:none}
ul.rel a{display:block;padding:12px 14px;line-height:1.35;font-size:var(--f-sm);
  color:var(--ink);text-decoration:none;background:var(--surface);
  border:1px solid var(--line-strong);border-radius:var(--radius)}   /* 45px tall */
ul.rel a:hover{background:var(--track);border-color:var(--accent)}

/* ---------- 12. index page ------------------------------------------------- */

/* ---------- 13. ad slots ---------------------------------------------------
   Место резервируется заранее, поэтому вставка блока ничего не сдвигает.
   ПРАВИЛО РАЗМЕЩЕНИЯ: рекламное место — всегда ПОСЛЕДНИЙ узел раздела и
   непосредственный сосед сверху для <h2>. Реклама завершает раздел; она
   никогда его не открывает, не отрывает заголовок от текста, не встаёт
   между h1 и первым графиком и не лезет внутрь карточки, фигуры или таблицы.
   Только ручные места: автоматические блоки AdSense вставляют неучтённые
   единицы и ломают то самое обещание нулевого сдвига.
   Заливка убрана: две серые плиты в 290px с подписью «Advertisement» и
   пустотой внутри читаются как битые картинки — и человеком, и рецензентом. */
.ad{display:flex;flex-direction:column;align-items:center;justify-content:center;
  gap:var(--s-2);min-height:316px;margin:var(--s-6) 0;padding:var(--s-2) 0;
  background:none;border-top:1px solid var(--line);border-bottom:1px solid var(--line);
  border-radius:0;overflow:hidden;max-width:none}
.ad-label{font-size:var(--f-2xs);line-height:20px;letter-spacing:.12em;
  text-transform:uppercase;font-weight:600;color:var(--muted)}
.ad>ins,.ad>iframe,.ad>div{display:block;max-width:100%}
@media(max-width:479px){.ad{min-height:286px;margin:var(--s-5) 0}}

/* ---------- 13b. боковая колонка страницы поколения ------------------------
   Липкость намеренно НЕ включена: любой предок, получивший overflow, тихо
   превращает sticky в static — без ошибки и без видимого признака.
   Включать отдельным шагом, вместе с проверкой предков.                     */
.gen-grid{display:block}
.rail{display:none}
@media(min-width:1180px){
  .wrap.gen{max-width:1180px}
  .gen-grid{display:grid;grid-template-columns:minmax(0,1fr) 300px;
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
  .rail-vin{font-size:var(--f-xs);line-height:1.45;padding:var(--s-3);
    background:var(--warn);margin:0 0 var(--s-5);max-width:none}
  .rail-vin b{display:block;font-size:var(--f-2xs);letter-spacing:.06em;
    text-transform:uppercase;color:var(--muted);margin-bottom:2px}
}

/* ---------- 13c. первый экран страницы поколения ---------------------------
   Ответ раньше объяснения: четыре числа и два действия. На ≥1180px блок
   скрыт — те же числа несёт боковая колонка. */
.alert-strip{background:var(--danger-bg);color:var(--danger-fg);font-weight:600;
  font-size:var(--f-sm);line-height:1.4;padding:10px var(--s-3);margin:0 0 var(--s-3);
  box-shadow:inset 0 0 0 1px var(--danger-ring);border-radius:var(--radius);
  max-width:none}
.snap-top{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));
  gap:0 var(--s-4);margin:0 0 var(--s-3);padding:2px var(--s-3) var(--s-2);
  background:var(--surface);border:1px solid var(--line);
  border-top:var(--rule) solid var(--ink);max-width:none}
.snap-top>div{padding:var(--s-2) 0 6px;border-bottom:1px solid var(--line)}
.snap-top>div:nth-last-child(-n+2){border-bottom:0;padding-bottom:2px}
.snap-top dt{font-size:var(--f-2xs);letter-spacing:.06em;text-transform:uppercase;
  color:var(--muted)}
.snap-top dd{margin:2px 0 0;max-width:none;font-size:var(--f-md);font-weight:700;
  letter-spacing:-.01em;font-variant-numeric:tabular-nums}
.btn-row{display:flex;flex-wrap:wrap;gap:var(--s-2);margin:0 0 var(--s-4);
  max-width:none}
.btn{display:inline-block;padding:10px 14px;border:2px solid var(--accent);
  border-radius:var(--radius);font-size:var(--f-sm);font-weight:600;
  text-decoration:none;background:var(--accent);color:var(--bg)}
.btn:hover{background:var(--accent-ink);border-color:var(--accent-ink)}
.btn-ghost{background:var(--surface);color:var(--ink);border-color:var(--line-strong)}
.warn-note{background:var(--warn);border-left:3px solid var(--accent);padding:10px var(--s-3);margin:0 0 var(--s-3);font-size:.94em}
.btn-ghost:hover{background:var(--track);color:var(--ink);border-color:var(--accent)}
@media(min-width:1180px){.snap-top,.snap-btns{display:none}}
@media(max-width:379px){.snap-top{grid-template-columns:1fr}
  .snap-top>div:nth-last-child(-n+2){border-bottom:1px solid var(--line)}
  .snap-top>div:last-child{border-bottom:0}}

/* ---------- 13d. чек-лист перед покупкой ----------------------------------- */
ol.check{margin:0;padding-left:1.4em}
ol.check li{margin:0 0 var(--s-3);max-width:var(--measure);line-height:1.5}
ol.check li:last-child{margin-bottom:0}
ol.check li.chk-alert{list-style:none;margin-left:-1.4em;padding:var(--s-2) var(--s-3);
  background:var(--warn);border-left:3px solid var(--peak)}
ol.check li.chk-alert strong{color:var(--peak)}

/* ---------- 17. кумулятивная лестница --------------------------------------
   График, в честь которого сайт назван: доля сообщений не выше каждого
   пробега. Ступени только на границах корзин, ничего не сглаживается. */
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

/* ---------- 18. линейки на хабе марки --------------------------------------
   Малые кратные: одна линейная ось на все поколения. Полый бокс = молодой
   парк, его сообщения физически не могли прийти на больших пробегах. */
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

/* ---------- 19. одометр: только настоящие пробеги --------------------------
   Правило одного места: ячейки-барабаны получают ИСКЛЮЧИТЕЛЬНО показания
   одометра (медиана пробега), никогда счётчики и проценты. */
.odo-w{display:inline-flex;gap:2px;align-items:baseline}
.odo-w b{font-family:var(--sans);font-weight:600;font-variant-numeric:tabular-nums;
  background:var(--bar-hi);color:var(--bg);padding:1px 5px 2px;border-radius:2px;
  line-height:1.25}
.odo-w i{font-style:normal;color:var(--muted)}

/* ---------- 20. лента отзывных кампаний ------------------------------------
   Положение штриха = дата подачи, и только оно. Оранжевым — исключительно
   федеральные флаги do-not-drive / park-outside, не наша оценка тяжести. */
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

/* ---------- 21. пара кривых на главной -------------------------------------
   Каждая лестница нормирована на СВОЁ число сообщений — объём жалоб не может
   ничего исказить. Серии различаются светлотой; --peak только для «вы». */
svg.cdfp{width:100%;height:180px}
.cdfp-fig .yax{height:180px}
.cdfp .grid{stroke:var(--line);stroke-width:1;stroke-dasharray:2 4}
.cdfp .base{stroke:var(--line-strong);stroke-width:1}
.cdfp .c-a{stroke:var(--bar);stroke-width:2;fill:none}
.cdfp .c-b{stroke:var(--bar-hi);stroke-width:2;fill:none}
.cdfp-fig .fig-foot b{font-family:var(--sans);font-variant-numeric:tabular-nums}

/* ---------- 13f. «где ваша машина» ------------------------------------------
   Три статических якоря пробега — то, что видит робот и читатель без JS.
   JS пересчитывает те же группы под точный пробег и ставит маркер на полоски
   Figure 2 (строго вертикальный отрезок — preserveAspectRatio его не гнёт). */
.odo-f{display:flex;gap:var(--s-2);margin:0 0 var(--s-4);max-width:420px}
.odo-f input{flex:1 1 auto;min-width:0;font:inherit;font-size:var(--f-sm);
  padding:10px var(--s-3);border:2px solid var(--line-strong);
  border-radius:var(--radius);background:var(--surface);color:var(--ink);
  font-variant-numeric:tabular-nums}
.odo-f input:focus-visible{border-color:var(--accent)}
.odo-f input::placeholder{color:var(--muted)}
.odo-f button{flex:none;font:inherit;font-weight:600;padding:10px var(--s-4);
  border:2px solid var(--accent);border-radius:var(--radius);
  background:var(--accent);color:var(--bg);cursor:pointer}
.odo-f button:hover{background:var(--accent-ink);border-color:var(--accent-ink)}
.odo-a{margin:0 0 var(--s-4);padding:var(--s-3) var(--s-4);
  background:var(--surface);border:1px solid var(--line);max-width:none}
.odo-a h3{margin:0 0 var(--s-1)}
.odo-a>p{max-width:var(--measure);margin:0 0 var(--s-2);font-size:var(--f-sm)}
.odo-h{font-size:var(--f-2xs);letter-spacing:.06em;text-transform:uppercase;
  color:var(--muted);margin:var(--s-3) 0 2px;max-width:none}
.odo-l{list-style:none;margin:0;padding:0}
.odo-l li{margin:0;padding:6px 0;border-bottom:1px solid var(--line);
  font-size:var(--f-sm);max-width:var(--measure);font-variant-numeric:tabular-nums}
.odo-l li:last-child{border-bottom:0}
.strip .you{stroke:var(--peak);stroke-width:2;display:none}
.sysfig.has-you .strip .you{display:inline}
.you-lbl{font-size:var(--f-xs);font-weight:600;color:var(--peak);
  margin:0 0 var(--s-2);max-width:none}

/* ---------- 13e. отзывы раскрывающимися записями ---------------------------
   Родная details/summary: ни строчки JS, работает с клавиатуры из коробки. */
ol.rcl{list-style:none;margin:var(--s-3) 0 var(--s-4);padding:0;
  border-top:1px solid var(--line-strong);max-width:none}
ol.rcl li{margin:0;max-width:none;border-bottom:1px solid var(--line)}
.rcl-item summary{cursor:pointer;padding:12px 0;color:var(--ink)}
.rcl-item summary:hover .rcl-line{color:var(--accent-ink)}
.rcl-line{font-size:var(--f-sm);font-weight:600}
.rcl-line b{font-variant-numeric:tabular-nums}
.rcl-what{display:block;font-size:var(--f-xs);color:var(--muted);margin-top:2px;
  max-width:68ch}
.rcl-body{padding:0 0 var(--s-3) 1.1em}
.rcl-body p{font-size:var(--f-sm);max-width:var(--measure);margin:0 0 var(--s-2)}
.rcl-body p:last-child{margin-bottom:0}
.rcl-body .meta{margin-top:var(--s-2)}

/* ---------- 14. provenance strip and footer -------------------------------- */
.prov{display:flex;flex-wrap:wrap;gap:var(--s-2) var(--s-3);
  margin:var(--s-6) 0 0;font-size:var(--f-xs);color:var(--muted)}
.prov a{color:var(--accent-ink)}

footer{margin-top:var(--s-6);padding-top:var(--s-4);
  border-top:2px solid var(--ink);color:var(--muted);font-size:var(--f-xs)}
footer p{margin:0 0 var(--s-2);max-width:var(--measure)}
footer a{color:var(--muted)}
/* /terms/ и /contact/ генерировались, но не были связаны ниоткуда —
   частая и совершенно избежная причина отказа рекламной сети. */
.foot-nav{display:flex;flex-wrap:wrap;gap:var(--s-2) var(--s-4);
  margin:0 0 var(--s-3);font-size:var(--f-sm)}
.foot-nav a{color:var(--ink);text-decoration:none;
  border-bottom:1px solid var(--line-strong);padding-bottom:1px}
.foot-nav a:hover{border-bottom-color:var(--accent)}

/* ---------- 15. motion ------------------------------------------------------ */
@media(prefers-reduced-motion:no-preference){
  ul.rel a,tbody tr,header.site nav a,.jump a,.foot-nav a{
    transition:background-color .12s ease,border-color .12s ease,color .12s ease}
}

/* ---------- 16. print -------------------------------------------------------
   Someone comparing two cars in a dealership forecourt is a real user.     */
@media print{
  :root{--bg:#fff;--surface:#fff;--ink:#000;--muted:#3f3f3f;
    --line:#c2c2c2;--line-strong:#767676;--track:#eeeeee;--warn:#f2f2f2;
    --accent:#000;--accent-ink:#000;--peak:#000;
    --bar:#b8b8b8;--bar-hi:#252525;--tick:#fff;
    --danger-bg:transparent;--danger-fg:#000;--danger-ring:#000;--shadow:transparent}
  body{background:#fff;font-size:10.5pt}
  .gen-grid{display:block}
  .rail,.ad,ul.rel,header.site nav,.skip,.crumbs{display:none}
  .tw{overflow:visible;background-image:none}
  .card,.tw,figure.fig,figure.chart,blockquote.quote,ol.sys li,.pct{break-inside:avoid}
  h2,h3,.fig-title{break-after:avoid}
  details.nums>*{display:block}
  a[href^="http"]::after{content:" (" attr(href) ")";font-size:8pt;color:#555}
}


/* ---------- главная: герой, поиск, марки ------------------------------------
   Всё в потоке. Выпадающий список результатов — обычный блок под формой,
   не оверлей: страница под ним сдвигается, и это честнее, чем перекрытие. */
/* Линии у героя нет: отбивку даёт верхняя 3px-линия следующего экспоната.
   Раньше здесь стояли две черты подряд — своя у героя и своя у заголовка. */
.hero{padding:var(--s-4) 0 var(--s-6);border-bottom:0}
.kick{font-family:var(--sans);font-size:var(--f-2xs);letter-spacing:.1em;
  text-transform:uppercase;color:var(--accent-ink);margin:0 0 var(--s-2);max-width:none}
.hero h1{font-size:clamp(30px,5.2vw,var(--f-3xl));line-height:1.06;
  letter-spacing:-.024em;margin:0 0 var(--s-3);max-width:17ch}
.lede{font-family:var(--sans);font-size:var(--f-lg);line-height:1.45;
  color:var(--muted);margin:0 0 var(--s-4);max-width:46ch}
.lede strong{color:var(--ink);font-weight:600;font-variant-numeric:tabular-nums}

/* Три числа как доводы. Точные и неокруглённые: 2,116,532 — это довод. */
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));
  gap:0;margin:var(--s-5) 0 0;border-top:var(--rule) solid var(--ink);max-width:none}
.stats>div{padding:var(--s-3) var(--s-3) var(--s-3) 0;border-right:1px solid var(--line)}
.stats>div:last-child{border-right:0;padding-right:0}
.stats dt{font-size:var(--f-2xs);letter-spacing:.08em;text-transform:uppercase;
  color:var(--muted)}
.stats dd{margin:var(--s-1) 0 0;max-width:none;font-weight:600;line-height:1;
  font-size:clamp(24px,4.4vw,var(--f-2xl));letter-spacing:-.03em;
  font-variant-numeric:tabular-nums}

/* Граница поля в 2px чернилами — то, что говорит «это главный орган
   управления», без тени и без градиента. */
.qbox{display:flex;gap:var(--s-2);max-width:520px}
.qbox input{flex:1 1 auto;min-width:0;font:inherit;font-size:var(--f-md);
  padding:15px var(--s-3);border:2px solid var(--ink);border-radius:var(--radius);
  background:var(--surface);color:var(--ink)}
/* Ни outline:none, ни собственного кольца: кольцо на --track давало 1,10:1,
   то есть было невидимо, а в тёмной теме граница при фокусе ещё и тускнела.
   Работает глобальное правило :focus-visible. */
.qbox input:focus-visible{border-color:var(--accent)}
.qbox input::placeholder{color:var(--muted)}
.qbox button{flex:none;font:inherit;font-weight:600;padding:15px var(--s-4);
  border:2px solid var(--accent);border-radius:var(--radius);background:var(--accent);
  color:var(--bg);cursor:pointer;white-space:nowrap}
.qbox button:hover{background:var(--accent-ink);border-color:var(--accent-ink)}
.qhint{font-size:var(--f-xs);color:var(--muted);margin:var(--s-2) 0 0;
  font-variant-numeric:tabular-nums}

.qr{max-width:520px;margin:var(--s-2) 0 0}
.qr[hidden]{display:none}
.qr-list{list-style:none;margin:0;padding:0;border:1px solid var(--line-strong);
  border-radius:var(--radius);background:var(--surface);overflow:hidden}
.qr-list li{margin:0;border-bottom:1px solid var(--line)}
.qr-list li:last-child{border-bottom:none}
.qr-list a{display:block;padding:12px var(--s-3);text-decoration:none;color:var(--ink)}
.qr-list a:hover,.qr-list a:focus-visible{background:var(--track)}
.qr-car{font-weight:600}
.qr-yr{color:var(--muted);font-variant-numeric:tabular-nums}
.qr-n{display:block;font-size:var(--f-xs);color:var(--muted);
  font-variant-numeric:tabular-nums;margin-top:2px}
.qr-none{padding:12px var(--s-3);border:1px dashed var(--line-strong);
  border-radius:var(--radius);color:var(--muted);font-size:var(--f-sm);margin:0}

.cta{font-weight:600}

/* Указатель марок строками, а не карточками. Строка «3 generations · 2,278
   complaints» переносилась в одних плитках и не переносилась в других —
   ряд выходил рваным. Теперь это два поля фиксированной ширины, и каждая
   строка ровно одна. Различие дают числа, а не рамки. */
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
/* Шапку надо повторить над КАЖДОЙ колонкой, а сколько их — решает auto-fill,
   и в CSS это число недоступно. Кладём заведомо больше ячеек, лишние ряды
   схлопываем в нулевую высоту и обрезаем: над каждой колонкой ровно одна. */
.makes-key{display:grid;grid-template-columns:repeat(auto-fill,minmax(232px,1fr));
  gap:0 var(--s-5);margin:var(--s-3) 0 0;max-width:none;
  grid-template-rows:auto;grid-auto-rows:0;overflow:hidden}
.makes-key>span{display:grid;grid-template-columns:minmax(0,1fr) 2.4em 5.4em;
  gap:var(--s-2);font-size:var(--f-2xs);letter-spacing:.08em;
  text-transform:uppercase;color:var(--muted)}
.makes-key i{font-style:normal;text-align:right}

/* Хаб марки: поколения строками с числами, тот же язык, что и указатель марок. */
ul.gens{list-style:none;margin:0 0 var(--s-5);padding:0;
  display:grid;grid-template-columns:repeat(auto-fill,minmax(268px,1fr));
  gap:0 var(--s-5);border-top:1px solid var(--line-strong);max-width:none}
ul.gens li{margin:0;max-width:none;border-bottom:1px solid var(--line)}
ul.gens a{display:grid;grid-template-columns:minmax(0,1fr) 4.6em 5.4em;
  align-items:baseline;gap:var(--s-2);padding:10px 0;
  text-decoration:none;color:var(--ink)}
ul.gens a:hover .gy{text-decoration:underline;text-decoration-thickness:2px;
  text-underline-offset:2px;color:var(--accent-ink)}
.gy{font-size:var(--f-sm);font-weight:600;font-variant-numeric:tabular-nums;
  white-space:nowrap}
.gn,.gm{font-size:var(--f-2xs);color:var(--muted);text-align:right;
  white-space:nowrap;font-variant-numeric:tabular-nums}
.gm{color:var(--ink)}
.gen-key{display:grid;grid-template-columns:repeat(auto-fill,minmax(268px,1fr));
  gap:0 var(--s-5);margin:var(--s-3) 0 0;max-width:none;
  grid-template-rows:auto;grid-auto-rows:0;overflow:hidden}
.gen-key>span{display:grid;grid-template-columns:minmax(0,1fr) 4.6em 5.4em;
  gap:var(--s-2);font-size:var(--f-2xs);letter-spacing:.08em;
  text-transform:uppercase;color:var(--muted)}
.gen-key i{font-style:normal;text-align:right}
@media(max-width:479px){ul.gens,.gen-key{grid-template-columns:1fr}}

@media(max-width:479px){
  .qbox{flex-direction:column}
  .qbox button{width:100%}
  ul.makes,.makes-key{grid-template-columns:1fr}
}

/* Широкая колонка главной. Абзацы держит своя мера (68ch), поэтому шире
   расходятся только сетка марок и график — то есть ровно то, чему ширина
   нужна. Ниже 1180px разницы нет и правило не действует. */
@media(min-width:1180px){
  .wrap.wide{max-width:1160px}
  /* Правая колонка больше не карточка в рамке: разница высот перестала быть
     видимой коробкой, которая обрывается раньше соседней. Более высокий столбец
     теперь справа по построению — поле, подпись и шесть строк. */
  .wrap.wide .hero{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,400px);
    gap:var(--s-6);align-items:start}
  .wrap.wide .hero-say{grid-column:1}
  .wrap.wide .hero h1{max-width:20ch}
  .wrap.wide .hero .stats{grid-column:1;grid-row:2}
  .wrap.wide .hero-find{grid-column:2;grid-row:1/span 2;margin:0;padding:0;
    border:0;background:none}
  .wrap.wide .qbox,.wrap.wide .qr{max-width:none}
}
.hero-find{margin:var(--s-5) 0 0}

/* «Most reported» — строки в линейку, а не плашки-таблетки: таблетки это
   типовая мебель готовых тем. */
.qpop-h{font-size:var(--f-2xs);letter-spacing:.08em;text-transform:uppercase;
  color:var(--muted);margin:var(--s-4) 0 0;max-width:none}
.qpop{list-style:none;margin:0;padding:0;border-top:1px solid var(--line-strong)}
.qpop li{margin:0;max-width:none;border-bottom:1px solid var(--line)}
.qpop a{display:flex;justify-content:space-between;align-items:baseline;gap:var(--s-2);
  padding:10px 0;font-size:var(--f-sm);color:var(--ink);text-decoration:none}
.qpop a:hover{color:var(--accent-ink);text-decoration:underline}
.qpop a span{color:var(--muted);font-variant-numeric:tabular-nums;
  font-size:var(--f-2xs);white-space:nowrap}
"""


# Цитата отбрасывается целиком, а не чистится: кандидатов заведомо больше,
# чем показываемые четыре, поэтому отказ ничего не стоит, а частичная зачистка
# оставила бы обрывок вроде «позвонил в  по поводу».
QUOTE_REJECT = re.compile(
    r"\b(?:\+?1[-. ])?(?:\(\d{3}\)\s?|\d{3}[-. ])\d{3}[-. ]\d{4}\b"   # телефон
    r"|\b1[-. ]?8\d{2}[-. ]?\d{3}[-. ]?\d{4}\b"                       # бесплатный номер
    r"|\[x{2,}\]"                                                     # метка редактирования NHTSA
    r"|freedom of information act"
    r"|\b(?:mr|mrs|ms|dr)\.\s+[A-Z][a-z]+"                            # «mr. Sutton»
    r"|\b\d{2,6}\s+[a-z][a-z. ]{2,24}\b(?:blvd|street|st|ave|avenue|road|rd|drive|dr|lane|ln|hwy)\b",
    re.I)

# Даты должны говорить о ДАННЫХ, а не о том, когда запустили сборку.
# «NHTSA data through 13 August 2026» при свежайшей жалобе от 9 августа —
# завышение на четыре дня, которое росло бы с каждой пересборкой без новых
# данных. А политики заявляли правку при каждом деплое, что уничтожает
# единственный смысл этого поля.
def _snapshot_date() -> str:
    """Когда данные были скачаны — из манифеста загрузки, не из часов."""
    try:
        mf = json.loads((ROOT / "data" / "manifest.json").read_text(encoding="utf-8"))
        vals = [v.get("fetched_utc", "")[:10] for v in mf.values() if v.get("fetched_utc")]
        if vals:
            return min(vals)
    except Exception:
        pass
    return date.today().isoformat()


SNAPSHOT = _snapshot_date()
# Заполняется в main() из самой свежей жалобы в базе: покрытие можно
# обещать по последней ЗАПИСИ, а не по дате запуска сборки.
DATA_THROUGH = ""
POLICY_UPDATED = "2026-08-13"   # менять ТОЛЬКО когда правится текст политики

# Один переключатель на весь рекламный стек. До подачи в AdSense сайт НЕ несёт
# рекламы, не ставит своих кук и не имеет окна согласия — а политика утверждала
# обратное всеми тремя пунктами сразу. Ставить True в том же коммите, где
# появится идентификатор издателя в ads.txt.
ADS_LIVE = False
AD_DISCLOSURE = ("<p>This site carries third-party display advertising. Advertisers have no "
                 "input into what is published.</p>") if ADS_LIVE else ""
# Подпись «Advertisement» над пустой коробкой читается как битая картинка.
# Резерв высоты остаётся — это и есть обещание отсутствия сдвига макета.
AD_LABEL = '<span class="ad-label">Advertisement</span>' if ADS_LIVE else ""
ADS_TXT = "google.com, pub-XXXXXXXXXXXXXXXX, DIRECT, f08c47fec0942fa0\n"  # вместе с ADS_LIVE

JUMP_SECTIONS = (("lifespan", "How many miles?"), ("buy", "Before you buy"),
                 ("fails", "What fails, and when"), ("mileage", "Where your car sits"),
                 ("years", "By model year"), ("recalls", "Recalls"),
                 ("owners", "What owners reported"))


def _jump(parts: list[str]) -> str:
    """Оглавление собирается по тем разделам, которые на странице ЕСТЬ.

    У машины без отзывов раздела «Recalls» нет, и жёсткий список вёл бы
    в пустоту — на части страниц из 318.
    """
    page = "\n".join(parts)
    items = [f'<li><a href="#{k}">{t}</a></li>'
             for k, t in JUMP_SECTIONS if f'id="{k}"' in page]
    if len(items) < 2:
        return ""
    return ('<nav class="jump" aria-label="On this page">'
            '<p class="jump-h">On this page</p><ul>' + "".join(items) + "</ul></nav>")


def _cur(key: str, active: str) -> str:
    """aria-current на текущем разделе: читателю и чтецу экрана видно, где он."""
    return ' aria-current="page"' if key and key == active else ""


def strip_comments(css: str = "", js: str = "") -> str:
    """Убирает комментарии из CSS/JS перед отгрузкой.

    Комментарии — для того, кто правит исходник, а не для читателя страницы.
    В HTML они только весят и, если написаны по-русски, нарушают языковой шлюз
    сборки: сайт англоязычный, а в исходном коде страницы виден русский текст.
    """
    import re as _re
    blank = _re.compile(r"\n{3,}")
    block = _re.compile(r"/\*.*?\*/", _re.S)
    if css:
        return blank.sub("\n\n", block.sub("", css)).strip()
    if js:
        # Строковые литералы не трогаем: строчный комментарий ищем только там,
        # где строка с него начинается. Иначе '//' внутри URL съест полстроки.
        kept = [ln for ln in js.splitlines() if not ln.lstrip().startswith("//")]
        return blank.sub("\n\n", block.sub("", "\n".join(kept))).strip()
    return ""


def page_shell(title: str, desc: str, body: str, canonical: str,
               script: str = "", wide: bool = False, gen: bool = False,
               nav_key: str = "", robots: str = "", crumbs=None) -> str:
    # Скрипт подключается только там, где он нужен (поиск на главной).
    # Страницы поколений остаются полностью статичными.
    tail = f"<script>{strip_comments(js=script)}</script>" if script else ""
    # Широкая колонка — только для главной. Замер 2026-08-12: при окне 1425px
    # сетка из 28 марок стояла в три колонки внутри 832px, а по краям пустовало
    # по 297px. Текст остаётся в своей мере (68ch) — шире идут только сетка и график.
    cls = " wide" if wide else (" gen" if gen else "")
    # Страница 404 не должна ни индексироваться, ни объявлять канонический адрес:
    # /404 отдавала код 200 с телом «не найдено» и канонический вёл на /404.html,
    # который редиректом возвращает на /404.
    robots_tag = f'<meta name="robots" content="{robots}">' if robots else         '<meta name="robots" content="max-image-preview:large">'
    canon = (f'<link rel="canonical" href="{esc(canonical)}">'
             f'<meta property="og:url" content="{esc(canonical)}">') if canonical else ""
    ld = ""
    if crumbs:
        items = [{"@type": "ListItem", "position": i, "name": n,
                  **({"item": DOMAIN + u} if u else {})}
                 for i, (n, u) in enumerate(crumbs, 1)]
        ld = ('<script type="application/ld+json">'
              + json.dumps({"@context": "https://schema.org", "@type": "BreadcrumbList",
                            "itemListElement": items},
                           ensure_ascii=False, separators=(",", ":"))
              + "</script>")
    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
{robots_tag}{canon}
<meta property="og:type" content="website">
<meta property="og:site_name" content="{SITE}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3E%3Crect width='16' height='16' fill='%230f6e5e'/%3E%3Crect x='3' y='4' width='2.4' height='8' fill='%23fff'/%3E%3Crect x='6.6' y='8' width='2.4' height='4' fill='%23fff' opacity='.7'/%3E%3Crect x='10.2' y='9.5' width='2.4' height='2.5' fill='%23fff' opacity='.5'/%3E%3C/svg%3E">
{ld}
<script async src="https://www.googletagmanager.com/gtag/js?id={GA_ID}"></script>
<script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}gtag('consent','default',{{'ad_storage':'denied','ad_user_data':'denied','ad_personalization':'denied','analytics_storage':'granted'}});gtag('consent','default',{{'ad_storage':'denied','ad_user_data':'denied','ad_personalization':'denied','analytics_storage':'denied','region':["AT","BE","BG","HR","CY","CZ","DK","EE","FI","FR","DE","GR","HU","IE","IT","LV","LT","LU","MT","NL","PL","PT","RO","SK","SI","ES","SE","IS","LI","NO","GB","CH"]}});gtag('js',new Date());gtag('config','{GA_ID}');</script>
<style>{strip_comments(css=CSS)}</style>
</head><body>
<a class="skip" href="#main">Skip to content</a>
<div class="wrap{cls}">
<header class="site">
  <a class="brand" href="/"><svg width="14" height="16" viewBox="0 0 14 16" aria-hidden="true"
   focusable="false"><rect x="0" y="1" width="3" height="14" fill="currentColor"/><rect x="5.5"
   y="6" width="3" height="9" fill="currentColor" opacity=".62"/><rect x="11" y="10" width="3"
   height="5" fill="currentColor" opacity=".38"/></svg>{SITE}</a>
  <span class="masthead-tag">{TAGLINE}</span>
  <nav aria-label="Main"><a href="/vehicles/"{_cur("home", nav_key)}>All vehicles</a><a
  href="/methodology/"{_cur("method", nav_key)}>Methodology</a><a
  href="/about/"{_cur("about", nav_key)}>About</a><a
  href="/privacy/"{_cur("privacy", nav_key)}>Privacy</a></nav>
</header>
<main id="main">
{body}
</main>
<footer>
  <nav class="foot-nav" aria-label="Site">
    <a href="/vehicles/">All vehicles</a><a href="/methodology/">Methodology</a><a href="/about/">About</a>
    <a href="/privacy/">Privacy</a><a href="/terms/">Terms</a>
    <a href="/contact/">Contact</a><a href="/privacy/#us-state-rights">Your privacy choices</a><a href="mailto:{CONTACT}">{CONTACT}</a></nav>
  <p>Data: <a href="https://www.nhtsa.gov/nhtsa-datasets-and-apis">NHTSA Office of Defects
  Investigation</a>, public domain. Snapshot {SNAPSHOT}.</p>
  <p>Published by {OWNER}. Complaint counts reflect what owners reported to NHTSA and are
  not a measure of failure rate per vehicle sold.</p>
  {AD_DISCLOSURE}
</footer>
</div>{tail}</body></html>"""


ODO_JS = r"""
(function () {
  var blob = document.getElementById('odo-data');
  var form = document.getElementById('odo-f');
  if (!blob || !form) return;
  var D = JSON.parse(blob.textContent);
  var inp = document.getElementById('odo-i');
  var out = document.getElementById('odo-out');
  var stat = document.getElementById('odo-static');

  function fmt(n) { return n.toLocaleString('en-US'); }
  function lx(m) {
    m = Math.min(Math.max(m, 500), 200000);
    return (Math.log(m / 500) / Math.LN10) / 2.60206 * 1000;
  }
  function pctAt(v) {
    if (!D.bins.length || v > 200000) return null;
    for (var i = 0; i < D.bins.length; i++) if (v < D.bins[i][0]) return D.bins[i][1];
    return D.bins[D.bins.length - 1][1];
  }
  function esc(s) {
    return String(s).replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  }
  function group(title, rows, mode) {
    if (!rows.length) return '';
    var g = '<p class="odo-h">' + title + '</p><ul class="odo-l">';
    for (var j = 0; j < rows.length; j++) {
      var r = rows[j];
      g += '<li>' + esc(r.n) + ' — ' + (mode === 'med'
        ? 'median ' + fmt(r.med) + ' mi'
        : 'middle half ' + fmt(r.p25) + '–' + fmt(r.p75) + ' mi') + '</li>';
    }
    return g + '</ul>';
  }
  form.addEventListener('submit', function (e) {
    e.preventDefault();
    var v = parseInt(String(inp.value).replace(/[^0-9]/g, ''), 10);
    if (!v) { out.hidden = true; stat.hidden = false; return; }
    v = Math.min(v, 400000);
    var earlier = [], win = [], later = [];
    for (var i = 0; i < D.sys.length; i++) {
      var x = D.sys[i];
      if (x.p75 <= v) earlier.push(x);
      else if (x.p25 > v) later.push(x);
      else win.push(x);
    }
    var h = '<div class="odo-a"><h3>At ' + fmt(v) + ' miles</h3>';
    var p = pctAt(v);
    h += (p === null)
      ? '<p><strong>Reports describe the population, not your odds.</strong></p>'
      : '<p>The curve reads ' + p + '% at this point. ' +
        '<strong>That describes reports, not your odds.</strong></p>';
    h += group('Reported earlier than this mileage — ask for repair records', earlier, 'med');
    h += group('In the reporting window', win, 'iqr');
    h += group('Mostly reported later', later, 'iqr');
    out.innerHTML = h + '</div>';
    out.hidden = false; stat.hidden = true;
    var fig = document.querySelector('figure.sysfig');
    if (fig) {
      var xs = lx(v).toFixed(1);
      var lines = fig.querySelectorAll('svg.strip .you');
      for (var k = 0; k < lines.length; k++) {
        lines[k].setAttribute('x1', xs); lines[k].setAttribute('x2', xs);
      }
      fig.classList.add('has-you');
      var lbl = fig.querySelector('.you-lbl');
      if (lbl) {
        lbl.textContent = 'Your car: ' + fmt(v) + ' mi — the orange tick on each bar';
        lbl.hidden = false;
      }
    }
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
          : ' — the curve reads ' + pc + '% at this point');
        cl.hidden = false;
      }
    }
  });
})();
"""


def render_generation(s: dict, gen: dict, model_entry: dict, siblings: list[dict]) -> str:
    make, model = names.display(s["make"]), names.display(s["model"])
    years = f'{s["year_start"]}–{s["year_end"]}'
    head = f"{make} {model} {years}"
    sh = s["shape"]
    # Семья запросов «how many miles does it last» доминирует в Search Console,
    # а старые заголовки её не говорили. Заголовок задаёт вопрос читателя;
    # честный ответ (отчёты, не срок службы) живёт в блоке #lifespan.
    # Замерено по всем 318 реальным head: 48–59 знаков — не режется в выдаче.
    title = (f"{head} — how many miles does it last?" if len(head) <= 28
             else f"{head}: how long does it last?")
    # Описание открывается точным ответом языком отчётов («reports … came by»,
    # никогда «lasts»), несёт «common problems» для второй семьи запросов и
    # обещает recalls только там, где раздел существует (54 страницы без
    # кампаний). Хвосты одной длины, чтобы ветка без отзывов не переполнялась.
    # Замерено: 139–159 знаков на всех 318 страницах, все уникальны.
    _med, _p90 = sh.get("median"), sh.get("p90")
    if _med and _p90:
        _tail = 'the recalls' if s["recalls_count"] else 'a checklist'
        desc = (f'Half of {fmt(s["complaints_with_miles"])} failure reports on the {years} '
                f'{make} {model} came by {fmt(names.round_miles(_med))} miles, 90% by '
                f'{fmt(names.round_miles(_p90))} — plus common problems by system and {_tail}.')
    else:  # страховка: сегодня все 318 страниц имеют median и p90
        desc = (f'{fmt(s["complaints_with_miles"])} NHTSA complaints with mileage for the '
                f'{years} {make} {model}: when each system fails, and what it means '
                f'if you are buying one.')
    slug_self = slug(s["make"], s["model"], s["year_start"], s["year_end"])
    make_slug = slug(s["make"])

    B = [f'<ol class="crumbs"><li><a href="/">Home</a></li>'
         f'<li><a href="/{make_slug}/">{esc(make)}</a></li>'
         f'<li>{esc(model)} {years}</li></ol>']
    B.append(f'<h1>{esc(make)} {esc(model)} <span class="h1-years">{years}</span></h1>')

    plat = gen.get("platform_code")
    bits = [esc(gen.get("gen_label", ""))]
    if plat and plat.split()[0] not in (gen.get("gen_label") or ""):
        bits.append(esc(plat))
    B.append(f'<p class="sub">{" · ".join(b for b in bits if b)}</p>')

    B.append(f'<p class="dateline"><span><b>NHTSA data through {DATA_THROUGH}</b></span>'
             f'<span>{fmt(s["complaints_total"])} complaints, {fmt(s["complaints_with_miles"])} with mileage</span>'
             f'<span><a href="/methodology/">Method</a></span></p>')

    # Первый экран отвечает раньше, чем объясняет: четыре числа и два действия.
    # На ≥1180px этот блок скрыт — там те же числа несёт боковая колонка.
    # Ярлык медианы — строго «Median of reported failures»: блок имеет форму
    # готового ответа для выдачи, и без оговорки в самом ярлыке «median at
    # failure 15,000» читался бы как «ваша машина сломается на 15 тысячах».
    if s.get("severe_advisories"):
        B.append('<p class="alert-strip">A DO NOT DRIVE recall covers part of this generation '
                 '&mdash; check the VIN before driving it home.</p>')
    top_sys = s["systems"][0] if s["systems"] else None
    snap_cells = [f'<div><dt>Reports with mileage</dt><dd>{fmt(s["complaints_with_miles"])}</dd></div>']
    if sh.get("median"):
        snap_cells.append(f'<div><dt>Median of reported failures</dt>'
                          f'<dd>{odo_digits(names.round_miles(sh["median"]))} mi</dd></div>')
    if top_sys:
        _tn = re.sub(r"^the ", "", narrative.plain(top_sys["system"])).capitalize()
        snap_cells.append(f'<div><dt>Most-reported system</dt>'
                          f'<dd>{esc(_tn)} ({top_sys["share"]}%)</dd></div>')
    snap_cells.append(f'<div><dt>Recalls</dt><dd>{s["recalls_count"]}</dd></div>')
    B.append(f'<dl class="snap-top">{"".join(snap_cells)}</dl>')
    B.append('<p class="btn-row snap-btns">'
             '<a class="btn" href="#buy">Before-you-buy checklist &darr;</a>'
             '<a class="btn btn-ghost" href="https://www.nhtsa.gov/recalls">'
             'Check this VIN &mdash; NHTSA &nearr;</a></p>')

    # Однострочный вывод — первое, что читают
    if sh.get("note"):
        note = sh["note"]
        B.append(f'<p class="verdict">On this generation, {note[0].lower() + note[1:]}</p>')

    # ГЛАВНОЕ НА СТРАНИЦЕ — график идёт выше сгиба
    if s["histogram"]:
        # Один составной экспонат вместо графика, таблицы процентилей и двух
        # подписей, лежавших в тексте россыпью.
        top_bin = max(s["histogram"]["bins"], key=lambda b: b["count"], default=None)
        extra = (f'Tallest bin: {fmt(top_bin["count"])} complaints between {fmt(top_bin["lo"])} '
                 f'and {fmt(top_bin["hi"])} miles. ' if top_bin and top_bin["count"] else "")
        hfoot = (charts.percentiles(sh)
                 + f'<p class="meta">{extra}Based on {fmt(s["complaints_with_miles"])} complaints '
                   f'that record mileage. Bin width {fmt(s["histogram"]["width"])} miles.</p>'
                 + charts.bins_table(s["histogram"]))
        B.append(charts.histogram(
            s["histogram"], sh, s["complaints_with_miles"], f"{make} {model} {years}",
            kicker=f'Figure 1 &middot; {esc(make)} {esc(model)} {years} &middot; '
                   f'{fmt(s["complaints_with_miles"])} reports with mileage',
            title="Mileage at failure", foot=hfoot, level="h2"))

    B.append('<p class="note">What this can and cannot tell you: these are complaints owners '
             'chose to file, not a failure rate. Popular models accumulate more of them simply '
             'by being common. <a href="/methodology/">How this is built</a>.</p>')

    B.append(f'<div class="card finding">{lead_paragraph(s, gen)}</div>')

    # Ответ на доминирующий запрос «сколько миль проходит». Одна цитируемая
    # карточка: ответ первым, оговорка о выживаемости — придаточным ВНУТРИ
    # того же предложения (клип сниппета не оторвёт числа от оговорки),
    # доказательство выносливости — вторым абзацем: жалоба на 220 000 миль
    # доказывает, что машина ДОЕХАЛА до 220 000, а не что умерла там.
    if sh.get("median") and sh.get("p90") and s["histogram"]:
        _ovf = s["histogram"]["overflow"]
        B.append(f'<h2 id="lifespan">How many miles does a {years} {esc(make)} '
                 f'{esc(model)} last?</h2>')
        _endure = (f'<p>{fmt(_ovf["count"])} report{"s" if _ovf["count"] != 1 else ""} '
                   f'({_ovf["pct"]:g}%) came in past {fmt(_ovf["lo"])} miles &mdash; each one '
                   f'proof a {esc(model)} reached that mileage, not that it died there.</p>'
                   if _ovf["count"] else "")
        # Цензурирование возрастом. Молодой парк физически не мог дать больших
        # пробегов, поэтому медиана у свежего поколения меряет возраст, а не
        # выносливость. Оговорка стоит ПЕРЕД числами и в том же блоке: клип
        # сниппета не оторвёт её, и глаз читает её раньше цифры.
        _y1 = gen.get("year_end") or 0
        _age = date.today().year - _y1
        if _age <= 2:
            _cap = (f'<p class="warn-note"><strong>Read this first:</strong> the {years} '
                    f'{esc(model)} is still being built or has only just finished, so almost no '
                    f'example has covered high mileage yet. The figures below are bounded by how '
                    f'long these cars have been on the road, not by how long they last. Compare '
                    f'them only with generations of a similar age.</p>')
        elif _age <= 6:
            _cap = (f'<p class="warn-note">The oldest {esc(model)} of this generation is about '
                    f'{_age + 1} years old, so few examples have yet reached high mileage. These '
                    f'figures are still partly a measure of fleet age, not only of durability.</p>')
        else:
            _cap = ""
        B.append(f'<div class="card">{_cap}<p>Half of the failure reports on the {years} '
                 f'{esc(make)} {esc(model)} were filed by '
                 f'<strong>{fmt(names.round_miles(sh["median"]))} miles</strong> and 90% by '
                 f'<strong>{fmt(names.round_miles(sh["p90"]))} miles</strong> &mdash; figures '
                 f'drawn from {fmt(s["complaints_with_miles"])} NHTSA complaints that record '
                 f'an odometer reading, so they time reported failures, not the cars whose '
                 f'owners never filed one.</p>{_endure}</div>')

    # Проверка перед покупкой: персона стоит на площадке с телефоном, у неё
    # три минуты. Раздел «What this means if you are buying one» влит сюда —
    # две покупательские секции на одной странице соревновались бы.
    checks = narrative.checklist_items(s, gen)
    if checks:
        n_iss = len(gen.get("known_issues") or [])
        B.append(f'<h2 id="buy">Before you buy a {years} {esc(model)}: the 3-minute check</h2>')
        src_bits = [f'{fmt(s["complaints_with_miles"])} mileage-tagged complaints']
        if s["recalls_count"]:
            src_bits.append(f'{s["recalls_count"]} recall campaign'
                            f'{"s" if s["recalls_count"] != 1 else ""}')
        if n_iss:
            src_bits.append(f'{n_iss} documented problem area{"s" if n_iss != 1 else ""}')
        B.append(f'<p class="sub">Generated from {", ".join(src_bits)}. '
                 f'Print this page &mdash; the checklist survives print.</p>')
        B.append('<div class="card"><ol class="check">')
        for lead, body, is_alert in checks:
            cls = ' class="chk-alert"' if is_alert else ""
            B.append(f'<li{cls}><strong>{lead}</strong> {body}</li>')
        B.append('</ol></div>')
        guide = narrative.guidance_narrative(s)
        if guide:
            B.append(guide)

    # Системы: полоски + таблица
    B.append('<h2 id="fails">What fails, and when</h2>')
    for x in s["systems"]:
        _n = narrative.plain(x["system"])
        # в прозе «the brakes» нужен артикль, в подписи строки — нет
        x["display_name"] = re.sub(r"^the ", "", _n).capitalize()
    # Пояснение переехало внутрь экспоната (.fig-sub). Раньше оно висело
    # отдельным абзацем, и строка подписей оси налезала на следующий текст.
    strips = charts.system_strips(
        s["systems"],
        kicker=f"Figure 2 &middot; {esc(make)} {esc(model)} {years}",
        title="When each system fails", you_key=True)
    if strips:
        B.append(strips)
    B.append('<div class="tw" tabindex="0" role="region" aria-label="Complaints by system">'
             '<table><caption class="vh">Complaints by vehicle system</caption><thead><tr>'
             '<th scope="col">System</th><th scope="col" class="num">Complaints</th>'
             '<th scope="col" class="num">Share</th><th scope="col" class="num">Median</th>'
             '<th scope="col" class="num">25–75%</th></tr></thead><tbody>')
    for x in s["systems"][:10]:
        med = fmt(names.round_miles(x["median_miles"])) if x.get("median_miles") else "—"
        rng = (f'{fmt(names.round_miles(x["p25_miles"]))}–{fmt(names.round_miles(x["p75_miles"]))}'
               if x.get("p25_miles") else "—")
        B.append(f'<tr><td class="sys-name">{esc(x["display_name"])}</td>'
                 f'<td class="num">{fmt(x["count"])}</td><td class="num">{x["share"]}%</td>'
                 f'<td class="num">{med}</td><td class="num">{rng}</td></tr>')
    B.append("</tbody></table></div>")

    # «Где ваша машина»: три статических якоря пробега + необязательный JS-ввод
    # одометра. Статические якоря — то, что видит робот и читатель без JS;
    # JS лишь пересчитывает те же три группы под точный пробег и ставит маркер
    # на полоски Figure 2. ЗАПРЕЩЕНЫ заголовки-предсказания («Likely already
    # happened»): у большинства машин жалоба так и не подана. Обязательная
    # строка «That describes reports, not your odds» — над группами.
    withm = [x for x in s["systems"] if x.get("median_miles") and x.get("p25_miles")][:7]
    cum = sh.get("cum_pct") or {}
    if withm and cum:
        B.append('<h2 id="mileage">Where your car sits</h2>')
        B.append('<p class="sub">Failure reports by the odometer reading they were filed at. '
                 'Pick the anchor nearest your car &mdash; or type the exact mileage: '
                 'your marker lands on this curve and on the timing chart above.</p>')
        # Лестница пробега — график, в честь которого сайт назван.
        if s["histogram"]:
            B.append(charts.cumulative(
                s["histogram"], sh, s["complaints_with_miles"], f"{make} {model} {years}",
                kicker=f'Figure 3 &middot; {esc(make)} {esc(model)} {years} &middot; '
                       f'{fmt(s["complaints_with_miles"])} reports with mileage',
                title="Share of reports below each mileage", level="h3"))
        B.append('<form class="odo-f" id="odo-f" action="#mileage">'
                 '<label class="vh" for="odo-i">Your odometer, miles</label>'
                 '<input id="odo-i" inputmode="numeric" autocomplete="off" '
                 'placeholder="Your odometer, e.g. 91,000">'
                 '<button type="submit">Go</button></form>')
        B.append('<div id="odo-out" hidden></div>')
        B.append('<div id="odo-static">')
        for anchor in (60_000, 90_000, 120_000):
            pct = cum.get(anchor)
            if pct is None:
                continue
            earlier = [x for x in withm if x["p75_miles"] <= anchor]
            later = [x for x in withm if x["p25_miles"] > anchor]
            window = [x for x in withm if x not in earlier and x not in later]
            grp = []
            if earlier:
                grp.append('<p class="odo-h">Reported earlier than this mileage '
                           '&mdash; ask for repair records</p><ul class="odo-l">' + "".join(
                    f'<li>{esc(x["display_name"])} &mdash; median '
                    f'{fmt(names.round_miles(x["median_miles"]))} mi</li>' for x in earlier)
                    + '</ul>')
            if window:
                grp.append('<p class="odo-h">In the reporting window</p><ul class="odo-l">'
                           + "".join(
                    f'<li>{esc(x["display_name"])} &mdash; middle half '
                    f'{fmt(names.round_miles(x["p25_miles"]))}&#8211;'
                    f'{fmt(names.round_miles(x["p75_miles"]))} mi</li>' for x in window)
                    + '</ul>')
            if later:
                grp.append('<p class="odo-h">Mostly reported later</p><ul class="odo-l">'
                           + "".join(
                    f'<li>{esc(x["display_name"])} &mdash; middle half '
                    f'{fmt(names.round_miles(x["p25_miles"]))}&#8211;'
                    f'{fmt(names.round_miles(x["p75_miles"]))} mi</li>' for x in later)
                    + '</ul>')
            B.append(f'<div class="odo-a"><h3>At {fmt(anchor)} miles</h3>'
                     f'<p>{pct}% of the failure reports on this generation came below '
                     f'this mileage. <strong>That describes reports, not your odds.</strong></p>'
                     + "".join(grp) + '</div>')
        B.append('</div>')
        # Данные для JS: кумулятивные корзины + окна систем. json.dumps не даёт
        # «</script» на этих данных (числа и названия систем).
        odo_bins = []
        if s["histogram"]:
            run = 0
            tot = s["complaints_with_miles"] or 1
            for b_ in s["histogram"]["bins"]:
                run += b_["count"]
                odo_bins.append([b_["hi"], round(run / tot * 100)])
        odo_data = {"bins": odo_bins,
                    "sys": [{"n": x["display_name"],
                             "p25": names.round_miles(x["p25_miles"]),
                             "med": names.round_miles(x["median_miles"]),
                             "p75": names.round_miles(x["p75_miles"])} for x in withm]}
        B.append('<script type="application/json" id="odo-data">'
                 + json.dumps(odo_data, separators=(",", ":")) + '</script>')

    B.append(f'<div class="ad">{AD_LABEL}</div>')

    for heading, block in narrative.full_analysis(s, gen):
        B.append(f"<h2>{esc(heading)}</h2>")
        B.append(block)

    issues = gen.get("known_issues") or []
    if issues:
        B.append("<h2>Documented problems</h2>")
        for it in issues:
            tags = ""
            if it.get("affected_years"):
                tags += f' <span class="tag">{esc(it["affected_years"].replace("-", "–"))}</span>'
            if it.get("source_strength") == "weak":
                tags += ' <span class="tag tag-weak">forum-sourced</span>'
            B.append(f'<div class="card"><h3>{esc(names.display(it.get("component", "—")))}{tags}</h3>'
                     f'<p>{esc(it.get("description", ""))}</p></div>')

    if len(s["by_year"]) > 1:
        B.append('<h2 id="years">By model year</h2>')
        B.append('<div class="tw" tabindex="0" role="region" aria-label="Complaints by model year">'
                 '<table><caption class="vh">Complaints by model year</caption><thead><tr>'
                 '<th scope="col">Year</th><th scope="col" class="num">Complaints</th>'
                 '<th scope="col" class="num">With mileage</th></tr></thead><tbody>')
        for y in s["by_year"]:
            mixed = ' <span class="tag">mixed</span>' if y["year"] in (gen.get("mixed_years") or []) else ""
            B.append(f'<tr><td>{y["year"]}{mixed}</td><td class="num">{fmt(y["complaints"])}</td>'
                     f'<td class="num">{fmt(y["with_miles"])}</td></tr>')
        B.append("</tbody></table></div>")

    if s["recalls"]:
        # Раньше это была таблица «кампания-дата-узел»: сами номера кампаний
        # читателю ни о чём. Теперь каждый отзыв отвечает на три вопроса —
        # что сломано, что может случиться, что починят бесплатно. Текст
        # правительственный, дословный (через sentence_case: он приходит
        # КАПСОМ); телефоны в нём — горячие линии производителей, не PII
        # (проверено по всем 217 256 строкам).
        B.append(f'<h2 id="recalls">Recalls ({s["recalls_count"]}) &mdash; '
                 f'is your car included?</h2>')
        B.append('<p class="meta">Recalls are fixed free of charge at any dealer, for any '
                 'owner. Check a specific vehicle by VIN at '
                 '<a href="https://www.nhtsa.gov/recalls">nhtsa.gov/recalls</a>. '
                 'The text below is NHTSA&rsquo;s own wording.</p>')
        tl = charts.recall_timeline(s["recalls"], s["year_start"], s["year_end"],
                                    int(SNAPSHOT[:4]))
        if tl:
            B.append(tl)
        B.append('<ol class="rcl">')
        for r in s["recalls"][:25]:
            yrs = (str(r["year_min"]) if r["year_min"] == r["year_max"]
                   else f'{r["year_min"]}&#8211;{r["year_max"]}')
            comp = names.display((r["component"] or "—").split(":")[0])
            cq = names.sentence_case((r.get("consequence") or "").strip(), (make, model))
            first = names.truncate_words(re.split(r"(?<=[.!?])\s", cq)[0], 110) if cq else ""
            badges = ""
            if r["do_not_drive"]:
                badges += ' <span class="alert">do not drive</span>'
            if r["park_outside"]:
                badges += ' <span class="alert">park outside</span>'
            open_attr = " open" if r["do_not_drive"] else ""
            try:
                r_dt = datetime.strptime(r["report_date"], "%Y-%m-%d").strftime("%b %Y")
            except (TypeError, ValueError):
                r_dt = ""
            dt_bit = f'<span class="rcl-dt">{r_dt}</span> &middot; ' if r_dt else ""
            body_bits = []
            if r.get("defect"):
                body_bits.append(f'<p><b>The defect.</b> '
                                 f'{esc(names.sentence_case(r["defect"], (make, model)))}</p>')
            if cq:
                body_bits.append(f'<p><b>What can happen.</b> {esc(cq)}</p>')
            if r.get("remedy"):
                body_bits.append(f'<p><b>The free fix.</b> '
                                 f'{esc(names.sentence_case(r["remedy"], (make, model)))}</p>')
            body_bits.append(f'<p class="meta">NHTSA campaign {esc(r["campaign"])}, '
                             f'reported {esc(r["report_date"] or "—")}.</p>')
            B.append(f'<li><details class="rcl-item"{open_attr}><summary>'
                     f'<span class="rcl-line">{dt_bit}<b>{yrs}</b> &middot; {esc(comp)}{badges}</span>'
                     f'<span class="rcl-what">{esc(first)}</span></summary>'
                     f'<div class="rcl-body">{"".join(body_bits)}</div></details></li>')
        B.append('</ol>')
        if s["recalls_count"] > 25:
            B.append(f'<p class="meta">Showing the 25 most recent of {s["recalls_count"]} '
                     f'campaigns.</p>')
        B.append(f'<div class="ad">{AD_LABEL}</div>')

    if s["quotes"]:
        B.append('<h2 id="owners">What owners reported</h2>')
        seen = set()
        shown = 0
        for q in s["quotes"]:
            txt = names.sentence_case((q["text"] or "").strip(), (make, model))
            # NHTSA обезличивает ПОДАВШЕГО, а не тех, кого он вписал в текст.
            # В опубликованных цитатах оказались адрес и телефон автосалона,
            # метки редактирования [xxx] и канцелярская вставка про FOIA.
            txt = re.sub(r"^tl\*\s*", "", txt, flags=re.I).strip()
            key = txt[:80].lower()
            if not txt or key in seen or QUOTE_REJECT.search(txt):
                continue
            seen.add(key)
            miles_bit = (f' · {fmt(names.round_miles(q["miles"]))} miles'
                         if q["miles"] and q["miles"] > 1 else "")
            B.append(f'<blockquote class="quote"><p>{esc(names.truncate_words(txt, 320))}</p>'
                     f'<cite>{q["year"]}{miles_bit} · '
                     f'{esc(re.sub(r"^the ", "", narrative.plain(q["system"] or "")).capitalize())}</cite></blockquote>')
            shown += 1
            if shown >= 4:
                break

    B.append(f'<p class="prov">Built from {fmt(s["complaints_with_miles"])} NHTSA complaints with '
             f'mileage · snapshot {SNAPSHOT} · '
             f'<a href="/data/generations.json">open data</a> · '
             f'<a href="https://github.com/bilingoplusllc/mileagecurve">reproduce this page</a></p>')

    rel = [g for g in siblings if g is not gen]
    if rel:
        B.append("<h2>Other generations</h2><ul class='rel'>")
        for g in rel:
            u = f'/{slug(s["make"], s["model"], g["year_start"], g["year_end"])}/'
            B.append(f'<li><a href="{u}">{esc(model)} {g["year_start"]}–{g["year_end"]}</a></li>')
        B.append("</ul>")

    # Боковая колонка. При окне 1568 текст занимал 680px, а 888 простаивало —
    # для сайта, живущего с рекламы, это ещё и место, где стоит рекламный блок.
    # ПРАВИЛО: над первым рекламным местом всегда стоит редакционный блок.
    # Колонка, открывающаяся баннером 300x600, читается рецензентом сети как
    # рекламная ферма. Липкость (position:sticky) НЕ включаем: в этом коде уже
    # трижды ломалось позиционирование, и включать её нужно отдельным шагом.
    med = sh.get("median") if isinstance(sh, dict) else None
    body = ['<div class="gen-grid"><div class="gen-main">'] + B + [
        '</div>',
        '<aside class="rail" aria-label="Summary and related">',
        '<div class="rail-in">',
        '<dl class="snap">',
        f'<div><dt>Complaints</dt><dd>{fmt(s["complaints_total"])}</dd></div>',
        f'<div><dt>With mileage</dt><dd>{fmt(s["complaints_with_miles"])}</dd></div>',
        f'<div><dt>Median of reported failures</dt><dd>'
        f'{odo_digits(names.round_miles(med)) if med else "&mdash;"}</dd></div>',
        f'<div><dt>Recalls</dt><dd>{s["recalls_count"]}</dd></div>',
        '</dl>',
        # Правило рельса: над рекламным местом всегда редакционные блоки.
        f'<p class="rail-vin"><b>Recall check.</b> '
        + (f'{s["recalls_count"]} campaign'
           f'{"s" if s["recalls_count"] != 1 else ""} cover this generation. '
           if s["recalls_count"] else '')
        + 'Recalls are fixed free, for any owner. '
          '<a href="https://www.nhtsa.gov/recalls">Enter your VIN at NHTSA &nearr;</a></p>',
        _jump(B),
        f'<div class="ad ad-rail">{AD_LABEL}</div>',
        '</div></aside></div>']

    # Крошки машинам: видимый <ol class="crumbs"> есть на 346 страницах,
    # но Google читает не его, а разметку.
    crumbs = [("Home", "/"), (make, f"/{slug(s['make'])}/"), (f"{model} {years}", None)]
    return page_shell(title, desc, "\n".join(body), f"{DOMAIN}/{slug_self}/",
                      script=ODO_JS, gen=True, crumbs=crumbs)


# ---------------------------------------------------------------- institutional pages
SHAPE_LABEL = {
    "bimodal": "two separate failure populations",
    "early": "failures concentrated early",
    "late": "failures concentrated late",
    "spread": "failures spread across the mileage range",
    "insufficient": "limited data",
}


def render_index(index: list[dict], stats: dict, demo: dict | None = None) -> str:
    """Главная. Задача: найти свою машину за секунды и понять идею за один взгляд."""
    by_make: dict[str, list[dict]] = {}
    for p in index:
        by_make.setdefault(p["make"], []).append(p)

    B = ['<div class="hero">',
         '<div class="hero-say">',
         f'<p class="kick">NHTSA complaint analysis &middot; {len(index)} vehicle generations</p>',
         '<h1>Find out what breaks on your car &mdash; and when</h1>',
         # Убрано «That second number is what makes this site possible» — сайт
         # говорил о себе в самой дорогой строке страницы. Теперь строка говорит
         # о том, чего у других нет.
         '<p class="lede">Complaint databases tell you how many owners had a problem. '
         'They almost never tell you at what mileage. This one does.</p>',
         '</div>',
         # Поиск без карточки: у поля своя граница в 2px, и этого достаточно,
         # чтобы читалось как главный орган управления. Рамка вокруг только
         # подчёркивала, что колонка кончается раньше соседней.
         '<div class="hero-find">',
         search.search_markup(len(index))]

    # Под формой — реальные ссылки. Раньше правая колонка на широком экране
    # заканчивалась карточкой, и под ней оставалось ~190px пустоты.
    # Формулировка «most reported», а не «most popular»: данных о посещаемости
    # у нас нет, а число сообщений — есть, и оно про это и говорит.
    # По одной машине на марку. Без этого список — пять Ford подряд: у крупных
    # марок верхние строки занимают их же соседние поколения, и подборка теряет смысл.
    seen_makes: set = set()
    top = []
    for p in sorted(index, key=lambda x: -x["n"]):
        if p["make"] in seen_makes:
            continue
        seen_makes.add(p["make"])
        top.append(p)
        if len(top) == 6:
            break
    B.append('<p class="qpop-h">Most reported vehicles</p><ul class="qpop">')
    for p in top:
        B.append(f'<li><a href="{p["url"]}">{esc(names.display(p["make"]))} '
                 f'{esc(names.display(p["model"]))} <span>{p["y0"]}&#8211;{p["y1"]}</span></a></li>')
    B.append('</ul>')
    B.append('</div>')
    # Цифры вынесены из левой колонки в отдельный элемент героя: на мобильном
    # порядок стал «заголовок → поиск → цифры» — раньше поиск стоял после цифр,
    # и главный орган управления уезжал под сгиб. На широком экране цифры
    # остаются в левой колонке (col1, второй ряд), поиск справа.
    B.append('<dl class="stats">'
             f'<div><dt>Complaints analysed</dt><dd>{fmt(stats["complaints"])}</dd></div>'
             f'<div><dt>With an odometer reading</dt><dd>{fmt(stats["with_miles"])}</dd></div>'
             f'<div><dt>Generations covered</dt><dd>{len(index)}</dd></div>'
             '</dl>')
    B.append('</div>')

    # Лучшая находка сайта — это его пронумерованный экспонат, а не абзац.
    # Из текста ушло «a manufacturing defect that shows up almost immediately»:
    # это утверждение о причине, которого данные не доказывают.
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
            kicker=f'Figure 1 &middot; Toyota Prius 2010&ndash;2015 &middot; '
                   f'{fmt(demo.get("n", 0))} reports',
            title="Counts tell you a car has a problem. Timing tells you which problem.",
            foot=foot, level="h2"))
    # Вторая витрина: одно имя модели — две разные кривые. Показывает категорию
    # продукта целиком и задаёт визуальный язык будущих страниц сравнений.
    if demo and demo.get("pair"):
        pr = demo["pair"]
        pfoot = ""
        if pr["a"]["median"] and pr["b"]["median"]:
            pfoot = (f'<p>Half of the {esc(pr["b"]["label"])} reports arrive by '
                     f'<b>{fmt(names.round_miles(pr["b"]["median"]))} miles</b>; the '
                     f'{esc(pr["a"]["label"])} takes '
                     f'<b>{fmt(names.round_miles(pr["a"]["median"]))}</b>. Same nameplate, '
                     f'different curve &mdash; that is what every page here shows.</p>')
        B.append(charts.cdf_pair(
            pr["a"], pr["b"],
            kicker="Figure 2 &middot; Toyota Prius, two generations",
            title="Same model name, different mileage curve",
            foot=pfoot, level="h2"))

    # Указатель марок, а не 28 одинаковых плиток. Различие дают сами числа
    # в табличной колонке справа — Ford 149,119 против Lexus 198, — а не полоска,
    # чью шкалу пришлось бы защищать.
    B.append(f'<h2 id="makes">Browse {len(index)} generations across {len(by_make)} makes</h2>')
    mkey = '<span><span>Make</span><i>Gens</i><i>Reports</i></span>'
    B.append(f'<div class="makes-key" aria-hidden="true">{mkey * 6}</div>')
    B.append('<ul class="makes">')
    for mk in sorted(by_make, key=lambda m: names.display(m)):
        rows = by_make[mk]
        n = sum(r["n"] for r in rows)
        B.append(f'<li><a href="/{slug(mk)}/"><span class="mk">{esc(names.display(mk))}</span>'
                 f'<span class="mk-g">{len(rows)}</span>'
                 f'<span class="mk-n">{fmt(n)}</span></a></li>')
    B.append('</ul>')

    B.append('<p class="prov">Built from the '
             '<a href="https://www.nhtsa.gov/nhtsa-datasets-and-apis">NHTSA Office of Defects '
             'Investigation</a> dataset, refreshed monthly · '
             '<a href="/methodology/">how it is built</a> · '
             '<a href="/data/generations.json">open data</a> · '
             '<a href="https://github.com/bilingoplusllc/mileagecurve">source</a></p>')

    return page_shell(f"{SITE} — {TAGLINE}",
                      f"When failures happen on {len(index)} US vehicle generations, from "
                      f"{fmt(stats['with_miles'])} NHTSA complaints that record mileage.",
                      "\n".join(B), DOMAIN + "/", script=search.SEARCH_JS, wide=True, nav_key="home")


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
         # Описывался алгоритм, который сняли как раз потому, что он фабриковал
         # вывод: доли окон разной ширины сравнивались как сопоставимые.
         # Классификация давно идёт по ПЛОТНОСТИ, а ярлыка «две популяции»
         # не получает ни одна страница из 318.
         "<p>The shape label — early, late or spread — is derived mechanically from "
         "complaint density (reports per 1,000 miles) in three windows: 0&#8211;12,000, "
         "20,000&#8211;80,000 and 100,000&#8211;200,000 miles. Density, not share, because "
         "windows of different width are not comparable as shares. No judgement is "
         "applied.</p>",

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
         f"<p>Data snapshot: {SNAPSHOT}. Rebuilt monthly, as NHTSA publishes.</p>"]

    return page_shell(f"Methodology — {SITE}",
                      "Sources, computation, and limitations of the MileageCurve reliability data.",
                      "\n".join(B), DOMAIN + "/methodology/", nav_key="method")


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
                      "\n".join(B), DOMAIN + "/about/", nav_key="about")


def render_privacy() -> str:
    B = ["<h1>Privacy</h1>",
         '<p class="sub">What this site collects, and what it does not.</p>',
         "<h2>What we collect</h2>"
         "<p>This site is a set of static pages. It has no accounts, no logins, no comment "
         "system and no newsletter, and it never asks you for personal information.</p>"
         "<p>The hosting provider keeps standard server request logs (page requested, referrer, "
         "approximate location, browser type) for security and to see which pages are used.</p>"
         "<h2>Analytics</h2>"
         "<p>This site uses Google Analytics 4 to count visits and see which pages are read. "
         "It records the page you viewed, where you arrived from, your approximate location "
         "derived from your IP address, and your browser and device type. Google Analytics 4 "
         "does not log or store IP addresses. We never see your name, your email or anything "
         "that identifies you personally, and we do not try to.</p>"
         "<p>Outside the European Economic Area, the United Kingdom and Switzerland, Analytics "
         "sets its own cookies to tell a returning visit from a new one. Inside those regions, "
         "analytics storage is switched off by default, so no analytics cookie is set at all "
         "unless and until you choose otherwise.</p>"
         '<p>You can block Analytics everywhere with Google\'s official '
         '<a href="https://tools.google.com/dlpage/gaoptout">opt-out browser add-on</a>, or by '
         "using any browser setting or extension that blocks it. The site works exactly the "
         "same either way.</p>",
         "<h2>Advertising</h2>"
         "<p>This site does not yet carry advertising and sets no cookies of its own. When "
         "advertising is added, partners may set cookies or use similar technology to serve and "
         "measure ads. Visitors in the European Economic Area and the United Kingdom will be "
         "shown a consent choice before any non-essential cookie is set, and that choice will be "
         "changeable at any time. This page will be updated on the day that happens.</p>"
         '<p>You can opt out of personalised advertising from Google at '
         '<a href="https://adssettings.google.com">adssettings.google.com</a>, and from many other '
         'vendors at <a href="https://optout.aboutads.info">optout.aboutads.info</a>.</p>',
         '<h2 id="us-state-rights">US state privacy rights</h2>'
         "<p>Residents of California, Colorado, Connecticut, Virginia and other states with "
         "comprehensive privacy laws have rights to access, correct and delete personal "
         "information, and to opt out of its sale or of targeted advertising. This site does not "
         "sell or share personal information, and runs no advertising today. When advertising is "
         "added, personalised ads count as sharing or targeted advertising under those laws, and "
         "an opt-out will be published here before any ad is served. To exercise a right or ask "
         f'what is held, write to <a href="mailto:{CONTACT}">{CONTACT}</a>.</p>',
         "<h2>Data about vehicles</h2>"
         "<p>The vehicle data shown here comes from public NHTSA records. NHTSA removes the "
         "identity of the person who filed, but complaint narratives are free text and can name "
         "other people or businesses. Quotes published here are screened for names, phone numbers "
         "and street addresses before they appear. Nothing on this site is keyed to an individual, "
         "an address or a vehicle identification number. If a quote still carries identifying "
         f'detail, <a href="mailto:{CONTACT}">tell us</a> and it comes down.</p>',
         "<h2>Contact</h2>"
         f'<p>Questions about this policy: <a href="mailto:{CONTACT}">{CONTACT}</a> ({OWNER}).</p>'
         f"<p>Last updated {POLICY_UPDATED}.</p>"]
    return page_shell(f"Privacy — {SITE}", "Privacy policy for MileageCurve.",
                      "\n".join(B), DOMAIN + "/privacy/", nav_key="privacy")


def write_page(path: Path, content: str) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "index.html").write_text(content, encoding="utf-8")


def render_sitemap(index: list[dict]) -> str:
    today = date.today().isoformat()
    makes = sorted({p["make"] for p in index})
    urls = (["/", "/vehicles/", "/methodology/", "/about/", "/privacy/", "/contact/", "/terms/"]
            + [f"/{slug(m)}/" for m in makes] + [p["url"] for p in index])
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

    global DATA_THROUGH
    _last = con.execute("SELECT MAX(date_filed) FROM complaints").fetchone()[0]
    DATA_THROUGH = (datetime.strptime(_last, "%Y-%m-%d").strftime("%d %B %Y")
                    if _last else date.today().strftime("%d %B %Y"))

    # Чистим СОДЕРЖИМОЕ, а не сам каталог. В Windows папка, которая служит
    # рабочим каталогом любому процессу, не удаляется, и сборка падала на
    # rmtree, хотя всё содержимое уже было снесено.
    if DIST.exists():
        for item in DIST.iterdir():
            shutil.rmtree(item) if item.is_dir() else item.unlink()
    else:
        DIST.mkdir(parents=True)

    built = skipped = 0
    index: list[dict] = []

    for m in models:
        label = f'{m["make"]} {m["model"]}'
        if args.only and args.only.upper() not in label.upper():
            continue
        gens = m["generations"]
        # Соседние поколения считаем ЗАРАНЕЕ и оставляем только те, что реально
        # соберутся. Раньше блок «Other generations» получал полный список, и
        # 179 ссылок на 158 страницах вели на страницы, которых не существует:
        # тонкие поколения пропускались уже после того, как попали в соседи.
        stats = {id(g): analyze.generation_stats(con, m["make"], m["model"],
                                                 int(g["year_start"]), int(g["year_end"]))
                 for g in gens}
        live = [g for g in gens if stats[id(g)]["complaints_with_miles"] >= MIN_WITH_MILES]
        skipped += len(gens) - len(live)
        for g in live:
            s = stats[id(g)]
            out = DIST / slug(m["make"], m["model"], g["year_start"], g["year_end"])
            out.mkdir(parents=True, exist_ok=True)
            (out / "index.html").write_text(render_generation(s, g, m, live), encoding="utf-8")
            index.append({"url": f"/{out.name}/", "make": m["make"], "model": m["model"],
                          "y0": g["year_start"], "y1": g["year_end"],
                          "n": s["complaints_with_miles"], "shape": s["shape"].get("kind"),
                          # Медиана и квартили нужны хабу марки: линейка поколения
                          # кодирует ТОЛЬКО пробеги — позиции соизмеримы, счётчики нет.
                          "median": s["shape"].get("median"),
                          "p10": s["shape"].get("p10"), "p25": s["shape"].get("p25"),
                          "p75": s["shape"].get("p75"), "p90": s["shape"].get("p90")})
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

    # Демонстрация на реальных данных: показать идею, а не описать её
    demo = None
    try:
        d = analyze.generation_stats(con, "TOYOTA", "PRIUS", 2010, 2015)
        by = {x["system"]: x for x in d["systems"]}
        hyd = by.get("SERVICE BRAKES, HYDRAULIC", {}).get("median_miles")
        svc = by.get("SERVICE BRAKES", {}).get("median_miles")
        if hyd and svc:
            demo = {"systems": d["systems"], "hyd": hyd, "svc": svc,
                    "n": d["complaints_with_miles"],
                    "url": "/toyota-prius-2010-2015/"}
            d2 = analyze.generation_stats(con, "TOYOTA", "PRIUS", 2004, 2009)
            if d2["histogram"] and d["histogram"]:
                demo["pair"] = {
                    "a": {"hist": d2["histogram"], "total": d2["complaints_with_miles"],
                          "label": "Prius 2004–2009",
                          "median": d2["shape"].get("median")},
                    "b": {"hist": d["histogram"], "total": d["complaints_with_miles"],
                          "label": "Prius 2010–2015",
                          "median": d["shape"].get("median")}}
    except Exception:
        demo = None

    write_page(DIST, render_index(index, stats, demo))
    (DIST / "search-index.json").write_text(search.build_index(index), encoding="utf-8")
    write_page(DIST / "methodology", render_methodology(stats))
    write_page(DIST / "about", render_about())
    write_page(DIST / "privacy", render_privacy())
    write_page(DIST / "contact", pages.render_contact(page_shell))
    write_page(DIST / "terms", pages.render_terms(page_shell))
    write_page(DIST / "vehicles", pages.render_vehicles_index(index, page_shell))

    # Хабы по маркам: даёт иерархию вместо 318 листьев на корне
    by_make: dict[str, list[dict]] = {}
    for p in index:
        by_make.setdefault(p["make"], []).append(p)
    for mk, plist in by_make.items():
        write_page(DIST / slug(mk), pages.make_hub(mk, plist, page_shell))

    # Настоящая 404: сейчас любой неизвестный адрес отдаёт главную с кодом 200
    (DIST / "404.html").write_text(pages.render_404(page_shell), encoding="utf-8")
    # Никаких catch-all правил: неизвестный адрес должен отдавать 404.html,
    # а не главную с кодом 200 — это блокер при проверке AdSense.
    (DIST / "_redirects").write_text("/index.html  /  301\n", encoding="utf-8")
    # Защитные заголовки, управляемые из кода (Cloudflare Pages читает _headers).
    # HSTS безопасен: сайт живёт только на https, поддомен www — тоже https.
    (DIST / "_headers").write_text(
        "/*\n"
        "  Strict-Transport-Security: max-age=31536000; includeSubDomains\n"
        "  X-Frame-Options: DENY\n"
        "  X-Content-Type-Options: nosniff\n"
        "  Referrer-Policy: strict-origin-when-cross-origin\n"
        "  Permissions-Policy: camera=(), microphone=(), geolocation=(), "
        "interest-cohort=()\n", encoding="utf-8")

    (DIST / "sitemap.xml").write_text(render_sitemap(index), encoding="utf-8")
    (DIST / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\n\nSitemap: {DOMAIN}/sitemap.xml\n", encoding="utf-8")
    # Пустой ads.txt — это ПОЛОЖИТЕЛЬНОЕ заявление, что ни один продавец рекламы
    # не уполномочен. Отсутствие файла означает «неизвестно, действуйте».
    # До одобрения AdSense файл не выкладывается вовсе.
    if ADS_LIVE:
        (DIST / "ads.txt").write_text(ADS_TXT, encoding="utf-8")

    # Открытые данные: выгрузка агрегатов — ссылочная приманка (PLAYBOOK §7)
    (DIST / "data").mkdir(exist_ok=True)
    (DIST / "data" / "generations.json").write_text(
        GENS.read_text(encoding="utf-8"), encoding="utf-8")

    # --- шлюзы качества отгрузки ------------------------------------------
    # Проверяем ОТРЕНДЕРЕННЫЕ страницы, а не исходник. Коммит 8fdb261, чинивший
    # «испорченные экранирования», сам заменил в CSS литерал 14 на длинное тире:
    # синтаксис Python остался валидным, а три объявления умерли на 318 страницах
    # и никто этого не заметил. Кириллица — правило read-the-rendered-output:
    # strip_comments() единственное, что держит русские комментарии вне вывода.
    problems: list[str] = []
    SHIPPED = (".html", ".json", ".xml", ".txt", ".css", ".js")
    for f in sorted(x for x in DIST.rglob("*") if x.suffix in SHIPPED):
        t = f.read_text(encoding="utf-8")
        rel = f.relative_to(DIST)
        # Проверка на тире осмысленна только в CSS, то есть в HTML.
        if f.suffix == ".html" and re.search(r"[–—](?=px|\d*px)|\d[–—]px|:\s*[–—]", t):
            problems.append(f"{rel}: тире там, где должна быть длина CSS")
        if re.search(r"[Ѐ-ӿ]", t):
            problems.append(f"{rel}: кириллица в отгружаемой странице")
        if re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", t):
            problems.append(f"{rel}: управляющий символ")
        # Внутренние ссылки должны вести на существующие файлы. При частичной
        # сборке проверять нечего — там половины сайта нет по построению.
        if f.suffix == ".html" and not args.limit and not args.only:
            body = re.sub(r"<style>.*?</style>", "", t, flags=re.S)
            for href in sorted(set(re.findall(r'href="(/[^"#?]*)"', body))):
                tgt = (DIST / href.strip("/") / "index.html") if href.endswith("/") \
                    else (DIST / href.lstrip("/"))
                if not tgt.exists():
                    problems.append(f"{rel}: битая ссылка {href}")
    if problems:
        for line in problems[:20]:
            print(f"ШЛЮЗ: {line}")
        raise SystemExit(f"сборка остановлена: проблем {len(problems)}")

    print(f"страниц поколений: {built}  | пропущено (мало данных): {skipped}")
    print(f"плюс: главная, {len(by_make)} хабов по маркам, methodology, about, privacy, contact, terms, 404, sitemap.xml, robots.txt, открытые данные")
    print(f"→ {DIST}")
    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
