"""
Расчёт содержимого страницы поколения. Детерминированный Python — PLAYBOOK §5.

Из сырых жалоб считает всё, что показывается на странице:
  - гистограмма пробегов до отказа (главный дифференциатор, D-007);
  - разбивка по системам с их собственными пробегами отказа;
  - временная картина: когда жалобы подавались;
  - отзывные кампании поколения, включая тяжёлые предупреждения;
  - представительные цитаты жалоб.

Запуск как модуль:  from analyze import generation_stats
Запуск для проверки: python pipeline/analyze.py FORD FUSION 2010 2012
"""
from __future__ import annotations

import sqlite3
import statistics
import sys
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / "data" / "mileagecurve.db"

# ВАЖНО — исправлено 2026-08-12 после аудита.
#
# Раньше корзины были неравной ширины (5к в начале, 20к и 40к ближе к хвосту), а
# рисовались одинаковой шириной. Это ФАБРИКОВАЛО второй горб: у Prius 2010–2015
# «пик после 100 000 миль» существовал только потому, что корзина 100–120к вдвое
# шире соседних, а 160–200к вчетверо. При равномерных корзинах плотность падает
# монотонно: 159,9 → 19,2 → 14,0 → 13,0 → 7,3 жалоб на 1000 миль.
#
# Теперь корзины РАВНОМЕРНЫЕ, поэтому высота столбика = плотность с точностью до
# множителя, и график не врёт. Хвост за 200к не выбрасывается — он выносится
# отдельным столбиком с подписью.
HIST_DOMAIN = 200_000        # основная область графика
DEFECT_EDGE = 12_000         # граница «заводской брак» против износа

MIN_FOR_HISTOGRAM = 30
MIN_FOR_SYSTEM_STATS = 10


def choose_bin_width(n: int) -> int:
    """Ширина корзины под объём выборки: мало данных — шире корзина, иначе шум."""
    if n >= 1200:
        return 5_000
    if n >= 300:
        return 10_000
    return 20_000


def _quantile(sorted_vals: list[int], q: float) -> int:
    if not sorted_vals:
        return 0
    idx = min(int(len(sorted_vals) * q), len(sorted_vals) - 1)
    return sorted_vals[idx]


def _histogram(vals: list[int]) -> dict:
    """Равномерные корзины. Высота столбика пропорциональна плотности — график честен."""
    w = choose_bin_width(len(vals))
    nb = HIST_DOMAIN // w
    counts = [0] * nb
    over = 0
    for v in vals:
        if v >= HIST_DOMAIN:
            over += 1
        else:
            counts[min(v // w, nb - 1)] += 1
    n = len(vals) or 1
    return {
        "width": w,
        "bins": [{"lo": i * w, "hi": (i + 1) * w, "count": c, "pct": round(c / n * 100, 1)}
                 for i, c in enumerate(counts)],
        "overflow": {"lo": HIST_DOMAIN, "count": over, "pct": round(over / n * 100, 1)},
    }


def _shape(vals: list[int]) -> dict:
    """Определяет форму распределения — это то, чего не публикует ни один конкурент."""
    if len(vals) < MIN_FOR_HISTOGRAM:
        return {"kind": "insufficient", "note": "Too few complaints record mileage to describe the shape."}
    vs = sorted(vals)
    med = statistics.median(vs)
    p10, p25, p75, p90 = (_quantile(vs, q) for q in (0.10, 0.25, 0.75, 0.90))

    early = sum(1 for v in vs if v <= 12_000) / len(vs)
    late = sum(1 for v in vs if v >= 100_000) / len(vs)

    # Классификация по ПЛОТНОСТИ (жалоб на 1000 миль), а не по долям окон разной ширины.
    # Старые пороги сравнивали долю 12-тысячного окна с долей 400-тысячного как
    # сопоставимые величины, поэтому «двугорбым» объявлялось почти любое распределение
    # с длинным правым хвостом. Исправлено 2026-08-12 после аудита; см. MEMORY.md.
    # ВНИМАНИЕ: note попадает прямо на страницу — только по-английски.
    def dens(lo: int, hi: int) -> float:
        return sum(1 for v in vs if lo <= v < hi) / ((hi - lo) / 1000)

    d_early, d_mid, d_late = dens(0, 12_000), dens(20_000, 80_000), dens(100_000, 200_000)

    if d_mid > 0 and d_early >= 3 * d_mid and d_late >= 1.3 * d_mid:
        kind = "bimodal"
        note = (f"failures concentrate at two separate points in the vehicle's life: "
                f"{early:.0%} before 12,000 miles, and a second concentration beyond 100,000.")
    elif d_mid > 0 and d_early >= 3 * d_mid:
        kind = "early"
        note = (f"{early:.0%} of failures fall within the first 12,000 miles — a rate roughly "
                f"{d_early / d_mid:.0f} times higher than during the rest of the car's life.")
    elif d_mid > 0 and d_late >= 1.3 * d_mid:
        kind = "late"
        note = f"{late:.0%} of failures occur beyond 100,000 miles — a wear pattern."
    else:
        kind = "spread"
        note = (f"Failures are spread across the mileage range, with the middle half between "
                f"{p25:,} and {p75:,} miles.")

    density = {"early_per_1k": round(d_early, 1), "mid_per_1k": round(d_mid, 1),
               "late_per_1k": round(d_late, 1)}

    return {
        "kind": kind, "note": note,
        "p10": p10, "p25": p25, "median": int(med), "p75": p75, "p90": p90,
        "early_share": round(early, 3), "late_share": round(late, 3),
        "density": density,
    }


def generation_stats(con: sqlite3.Connection, make: str, model: str,
                     year_start: int, year_end: int) -> dict:
    """Полный набор данных для одной страницы поколения."""
    args = (make.upper(), model.upper(), year_start, year_end)

    total = con.execute(
        "SELECT COUNT(*) FROM complaints WHERE make=? AND model=? AND year BETWEEN ? AND ?", args
    ).fetchone()[0]

    miles = [r[0] for r in con.execute(
        "SELECT miles FROM complaints WHERE make=? AND model=? AND year BETWEEN ? AND ? "
        "AND miles IS NOT NULL", args)]

    # Системы: доля жалоб и собственный профиль пробегов
    systems = []
    for sysname, cnt in con.execute(
        "SELECT system, COUNT(*) c FROM complaints WHERE make=? AND model=? AND year BETWEEN ? AND ? "
        "AND system IS NOT NULL GROUP BY system ORDER BY c DESC LIMIT 12", args
    ):
        smiles = sorted(r[0] for r in con.execute(
            "SELECT miles FROM complaints WHERE make=? AND model=? AND year BETWEEN ? AND ? "
            "AND system=? AND miles IS NOT NULL", (*args, sysname)))
        entry = {"system": sysname, "count": cnt, "share": round(cnt / total * 100, 1) if total else 0,
                 "with_miles": len(smiles)}
        if len(smiles) >= MIN_FOR_SYSTEM_STATS:
            entry |= {"median_miles": int(statistics.median(smiles)),
                      "p25_miles": _quantile(smiles, 0.25),
                      "p75_miles": _quantile(smiles, 0.75)}
        systems.append(entry)

    # По модельным годам — видно, какой год внутри поколения хуже
    by_year = [{"year": y, "complaints": c, "with_miles": wm,
                "median_miles": int(m) if m else None}
               for y, c, wm, m in con.execute(
        "SELECT year, COUNT(*), SUM(miles IS NOT NULL), "
        "  (SELECT AVG(miles) FROM complaints c2 WHERE c2.make=c.make AND c2.model=c.model "
        "   AND c2.year=c.year AND c2.miles IS NOT NULL) "
        "FROM complaints c WHERE make=? AND model=? AND year BETWEEN ? AND ? "
        "GROUP BY year ORDER BY year", args)]

    # Тяжесть
    sev = con.execute(
        "SELECT SUM(crash), SUM(fire), SUM(injured), SUM(deaths) FROM complaints "
        "WHERE make=? AND model=? AND year BETWEEN ? AND ?", args).fetchone()

    # Отзывы поколения
    recalls = [{"campaign": c, "year_min": y0, "year_max": y1, "component": comp,
                "report_date": rd, "defect": d, "remedy": rem,
                "do_not_drive": bool(dnd), "park_outside": bool(po)}
               for c, y0, y1, comp, rd, d, rem, dnd, po in con.execute(
        "SELECT campaign, MIN(year), MAX(year), component, MIN(report_date), "
        "  MIN(defect), MIN(remedy), MAX(do_not_drive), MAX(park_outside) "
        "FROM recalls WHERE make=? AND model=? AND year BETWEEN ? AND ? "
        "GROUP BY campaign ORDER BY MIN(report_date) DESC", args)]

    # Представительные цитаты: самые «плотные» жалобы из крупнейших систем
    quotes = [{"year": y, "system": s, "miles": m, "text": t}
              for y, s, m, t in con.execute(
        "SELECT year, system, miles, narrative FROM complaints "
        "WHERE make=? AND model=? AND year BETWEEN ? AND ? AND narrative IS NOT NULL "
        "AND miles IS NOT NULL AND LENGTH(narrative) > 200 "
        "ORDER BY LENGTH(narrative) DESC LIMIT 6", args)]

    return {
        "make": make.upper(), "model": model.upper(),
        "year_start": year_start, "year_end": year_end,
        "complaints_total": total,
        "complaints_with_miles": len(miles),
        "miles_coverage_pct": round(len(miles) / total * 100, 1) if total else 0,
        "histogram": _histogram(miles) if len(miles) >= MIN_FOR_HISTOGRAM else None,
        "shape": _shape(miles),
        "systems": systems,
        "by_year": by_year,
        "severity": {"crashes": sev[0] or 0, "fires": sev[1] or 0,
                     "injured": sev[2] or 0, "deaths": sev[3] or 0},
        "recalls": recalls,
        "recalls_count": len(recalls),
        "severe_advisories": sum(1 for r in recalls if r["do_not_drive"] or r["park_outside"]),
        "quotes": quotes,
    }


def _demo(make: str, model: str, y0: int, y1: int) -> None:
    con = sqlite3.connect(DB)
    s = generation_stats(con, make, model, y0, y1)
    print(f"\n=== {s['make']} {s['model']} {y0}–{y1} ===")
    print(f"жалоб: {s['complaints_total']:,} | с пробегом: {s['complaints_with_miles']:,} "
          f"({s['miles_coverage_pct']}%)")
    sh = s["shape"]
    print(f"\nФОРМА: {sh['kind'].upper()} — {sh['note']}")
    if sh.get("median"):
        print(f"  10%={sh['p10']:,}  25%={sh['p25']:,}  медиана={sh['median']:,}  "
              f"75%={sh['p75']:,}  90%={sh['p90']:,}")
    if s["histogram"]:
        print("\nГИСТОГРАММА")
        mx = max(b["count"] for b in s["histogram"]) or 1
        for b in s["histogram"]:
            bar = "█" * int(b["count"] / mx * 44)
            print(f"  {b['label']:>10} {b['count']:6,} {b['pct']:5.1f}% {bar}")
    print("\nСИСТЕМЫ (доля жалоб и типичный пробег отказа)")
    for x in s["systems"][:8]:
        med = f"{x['median_miles']:,}" if x.get("median_miles") else "—"
        print(f"  {x['system'][:38]:38} {x['count']:6,} {x['share']:5.1f}%  медиана {med:>9}")
    print(f"\nОТЗЫВОВ: {s['recalls_count']} (тяжёлых предупреждений: {s['severe_advisories']})")
    sv = s["severity"]
    print(f"ТЯЖЕСТЬ: аварий {sv['crashes']:,} | возгораний {sv['fires']:,} | "
          f"пострадавших {sv['injured']:,} | погибших {sv['deaths']:,}")
    con.close()


if __name__ == "__main__":
    if len(sys.argv) == 5:
        _demo(sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]))
    else:
        for a in [("FORD", "FUSION", 2010, 2012), ("TOYOTA", "PRIUS", 2010, 2015),
                  ("JEEP", "CHEROKEE", 2014, 2018)]:
            _demo(*a)
