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

# Границы корзин гистограммы, мили. Шаг 10к до 150к, дальше крупнее — хвост длинный и разреженный.
BINS = [0, 5_000, 10_000, 20_000, 30_000, 40_000, 50_000, 60_000, 70_000, 80_000,
        90_000, 100_000, 120_000, 140_000, 160_000, 200_000, 500_000]

MIN_FOR_HISTOGRAM = 30
MIN_FOR_SYSTEM_STATS = 10


def _quantile(sorted_vals: list[int], q: float) -> int:
    if not sorted_vals:
        return 0
    idx = min(int(len(sorted_vals) * q), len(sorted_vals) - 1)
    return sorted_vals[idx]


def _histogram(vals: list[int]) -> list[dict]:
    counts = [0] * (len(BINS) - 1)
    for v in vals:
        for i in range(len(BINS) - 1):
            if BINS[i] <= v < BINS[i + 1]:
                counts[i] += 1
                break
    total = sum(counts) or 1
    out = []
    for i, c in enumerate(counts):
        lo, hi = BINS[i], BINS[i + 1]
        label = f"{lo // 1000}–{hi // 1000}k" if hi < 500_000 else f"{lo // 1000}k+"
        out.append({"lo": lo, "hi": hi, "label": label, "count": c, "pct": round(c / total * 100, 1)})
    return out


def _shape(vals: list[int]) -> dict:
    """Определяет форму распределения — это то, чего не публикует ни один конкурент."""
    if len(vals) < MIN_FOR_HISTOGRAM:
        return {"kind": "insufficient", "note": "мало данных для формы распределения"}
    vs = sorted(vals)
    med = statistics.median(vs)
    p10, p25, p75, p90 = (_quantile(vs, q) for q in (0.10, 0.25, 0.75, 0.90))

    early = sum(1 for v in vs if v <= 12_000) / len(vs)
    late = sum(1 for v in vs if v >= 100_000) / len(vs)

    # Двугорбость: заметная доля и совсем ранних, и совсем поздних отказов при
    # относительно пустой середине. Это подпись «заводской брак + износ» — случай Prius 2010.
    mid = sum(1 for v in vs if 20_000 <= v <= 80_000) / len(vs)
    if early >= 0.15 and late >= 0.15 and mid < 0.45:
        kind = "bimodal"
        note = (f"Два разных отказа: {early:.0%} машин ломается до 12 000 миль "
                f"(похоже на заводской дефект), ещё {late:.0%} — после 100 000 (износ).")
    elif early >= 0.30:
        kind = "early"
        note = f"Ранние отказы: {early:.0%} приходится на первые 12 000 миль."
    elif late >= 0.40:
        kind = "late"
        note = f"Поздние отказы: {late:.0%} — после 100 000 миль, картина износа."
    else:
        kind = "spread"
        note = f"Отказы распределены широко, половина между {p25:,} и {p75:,} миль."

    return {
        "kind": kind, "note": note,
        "p10": p10, "p25": p25, "median": int(med), "p75": p75, "p90": p90,
        "early_share": round(early, 3), "late_share": round(late, 3),
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
