"""
Отбор моделей, из которых строится корпус сайта.

Критерий: топ-N по числу жалоб + наличие модельных лет с достаточной статистикой пробегов.
Результат — data/top_models.json, вход для разметки поколений.

Запуск:  python pipeline/top_models.py [--top 100]
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "raw" / "cmpl" / "FLAT_CMPL.txt"
OUT = ROOT / "data" / "top_models.json"

F_MAKE, F_MODEL, F_YEAR, F_MILES, F_PRODTYPE, F_COMPDESC = 4, 5, 6, 18, 46, 12
MIN_MILES_PER_YEAR = 30
YEAR_MIN, YEAR_MAX = 1996, 2025
MILES_SANE_MAX = 500_000


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=100)
    args = ap.parse_args()

    if not SRC.exists():
        print(f"нет файла: {SRC}")
        return 1

    model_total: Counter[tuple] = Counter()
    year_total: defaultdict[tuple, Counter] = defaultdict(Counter)
    year_miles: defaultdict[tuple, int] = defaultdict(int)
    model_comp: defaultdict[tuple, Counter] = defaultdict(Counter)

    with open(SRC, "r", encoding="latin-1", errors="replace") as f:
        for line in f:
            p = line.rstrip("\n").split("\t")
            if len(p) < 51 or p[F_PRODTYPE - 1].strip().upper() != "V":
                continue
            mk = p[F_MAKE - 1].strip().upper()
            md = p[F_MODEL - 1].strip().upper()
            yr = p[F_YEAR - 1].strip()
            if not (mk and md and yr.isdigit()):
                continue
            y = int(yr)
            if not (YEAR_MIN <= y <= YEAR_MAX):
                continue

            key = (mk, md)
            model_total[key] += 1
            year_total[key][y] += 1

            cd = p[F_COMPDESC - 1].strip()
            if cd:
                model_comp[key][cd.split(":")[0]] += 1

            ms = p[F_MILES - 1].strip()
            if ms:
                try:
                    v = int(float(ms))
                    if 0 < v <= MILES_SANE_MAX:
                        year_miles[(mk, md, y)] += 1
                except ValueError:
                    pass

    out = []
    for (mk, md), total in model_total.most_common(args.top):
        years = sorted(year_total[(mk, md)])
        good = [y for y in years if year_miles.get((mk, md, y), 0) >= MIN_MILES_PER_YEAR]
        out.append({
            "make": mk,
            "model": md,
            "complaints": total,
            "year_min": years[0],
            "year_max": years[-1],
            "years_with_data": good,
            "top_systems": [c for c, _ in model_comp[(mk, md)].most_common(5)],
        })

    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"отобрано моделей: {len(out)}")
    print(f"суммарно жалоб: {sum(m['complaints'] for m in out):,}")
    print(f"модель-лет с данными: {sum(len(m['years_with_data']) for m in out):,}")
    print(f"файл: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
