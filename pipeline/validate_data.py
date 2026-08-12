"""
Проверка пригодности данных NHTSA до того, как что-либо построено.

Отвечает на три вопроса, от которых зависит существование сайта:
  1. Какая доля жалоб несёт пробег до отказа (поле MILES)?
  2. Хватает ли объёма на «модель + год», чтобы гистограмма была осмысленной?
  3. Похоже ли распределение на что-то содержательное, или это шум?

Запуск:  python pipeline/validate_data.py
Вывод:   reports/data-validation.md  +  data/coverage.json
"""
from __future__ import annotations

import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "raw" / "cmpl" / "FLAT_CMPL.txt"
REPORTS = ROOT / "reports"
DATA = ROOT / "data"

# Поля (1-based) по документации NHTSA ODI
F_MFR, F_MAKE, F_MODEL, F_YEAR = 3, 4, 5, 6
F_COMPDESC, F_DATEA, F_MILES, F_CDESCR = 12, 16, 18, 20
F_PRODTYPE = 46

# Порог осмысленной гистограммы: ниже этого форма распределения — шум.
MIN_FOR_HISTOGRAM = 30
# Верхняя граница правдоподобия пробега (выше — опечатки и мусор).
MILES_SANE_MAX = 500_000


def parse_miles(raw: str) -> int | None:
    raw = raw.strip()
    if not raw:
        return None
    try:
        v = int(float(raw))
    except ValueError:
        return None
    if v <= 0 or v > MILES_SANE_MAX:
        return None
    return v


def main() -> int:
    if not SRC.exists():
        print(f"нет файла: {SRC}\nсначала: python pipeline/fetch_nhtsa.py --only cmpl")
        return 1

    total = 0
    vehicles = 0
    with_miles = 0
    bad_miles = 0

    by_decade: Counter[str] = Counter()
    by_decade_miles: Counter[str] = Counter()
    # ключ: (make, model, year) -> список пробегов
    mmy_miles: defaultdict[tuple, list[int]] = defaultdict(list)
    mmy_count: Counter[tuple] = Counter()
    make_count: Counter[str] = Counter()
    comp_count: Counter[str] = Counter()

    with open(SRC, "r", encoding="latin-1", errors="replace") as f:
        for line in f:
            total += 1
            p = line.rstrip("\n").split("\t")
            if len(p) < 51:
                continue

            # только легковые/грузовые ТС (V), не шины/детские кресла/оборудование
            if p[F_PRODTYPE - 1].strip().upper() != "V":
                continue
            vehicles += 1

            make = p[F_MAKE - 1].strip().upper()
            model = p[F_MODEL - 1].strip().upper()
            year_raw = p[F_YEAR - 1].strip()
            datea = p[F_DATEA - 1].strip()
            miles_raw = p[F_MILES - 1].strip()

            decade = f"{datea[:3]}0s" if len(datea) >= 4 and datea[:4].isdigit() else "?"
            by_decade[decade] += 1

            miles = parse_miles(miles_raw)
            if miles_raw and miles is None:
                bad_miles += 1
            if miles is not None:
                with_miles += 1
                by_decade_miles[decade] += 1

            if not (make and model and year_raw.isdigit()):
                continue
            year = int(year_raw)
            if not (1990 <= year <= 2027):
                continue

            key = (make, model, year)
            mmy_count[key] += 1
            make_count[make] += 1
            if miles is not None:
                mmy_miles[key].append(miles)
            cd = p[F_COMPDESC - 1].strip()
            if cd:
                comp_count[cd.split(":")[0]] += 1

            if total % 500_000 == 0:
                print(f"  ...{total:,} строк", flush=True)

    # --- сводка ---
    hist_ready = {k: v for k, v in mmy_miles.items() if len(v) >= MIN_FOR_HISTOGRAM}
    mmy_with_any = len(mmy_count)

    def pct(a: int, b: int) -> str:
        return f"{a / b * 100:.1f}%" if b else "—"

    lines: list[str] = []
    add = lines.append
    add("# Проверка данных NHTSA — пригодность для MileageCurve\n")
    add(f"> Источник: `FLAT_CMPL.txt`, {SRC.stat().st_size / 1_073_741_824:.2f} ГБ\n")

    add("## 1. Объём и покрытие поля «пробег»\n")
    add("| Метрика | Значение |")
    add("|---|---|")
    add(f"| Всего записей | {total:,} |")
    add(f"| Из них транспортные средства (не шины/кресла) | {vehicles:,} |")
    add(f"| **С пробегом до отказа** | **{with_miles:,} ({pct(with_miles, vehicles)})** |")
    add(f"| Пробег указан, но невалиден | {bad_miles:,} |")
    add("")

    add("### Покрытие по десятилетиям подачи жалобы\n")
    add("| Десятилетие | Жалоб | С пробегом | Покрытие |")
    add("|---|---|---|---|")
    for d in sorted(by_decade):
        add(f"| {d} | {by_decade[d]:,} | {by_decade_miles[d]:,} | {pct(by_decade_miles[d], by_decade[d])} |")
    add("")

    add("## 2. Хватает ли объёма на страницу\n")
    add("| Метрика | Значение |")
    add("|---|---|")
    add(f"| Уникальных «марка+модель+год» (1990–2027) | {mmy_with_any:,} |")
    add(f"| Из них с ≥1 пробегом | {len(mmy_miles):,} |")
    add(f"| **С ≥{MIN_FOR_HISTOGRAM} пробегами — годны для гистограммы** | **{len(hist_ready):,}** |")
    add("")
    add(f"Порог {MIN_FOR_HISTOGRAM} выбран как минимум, ниже которого форма распределения — шум, а не сигнал.")
    add("Страницы строятся **по поколениям**, то есть объём нескольких модель-годов складывается —")
    add("реальное число пригодных страниц будет выше этой оценки.\n")

    add("### Топ-25 «модель+год» по числу пробегов\n")
    add("| Марка | Модель | Год | Жалоб | С пробегом | Медиана | 10-й проц. | 90-й проц. |")
    add("|---|---|---|---|---|---|---|---|")
    top = sorted(mmy_miles.items(), key=lambda kv: len(kv[1]), reverse=True)[:25]
    for (mk, md, yr), vals in top:
        vs = sorted(vals)
        p10 = vs[int(len(vs) * 0.10)]
        p90 = vs[int(len(vs) * 0.90)]
        add(f"| {mk} | {md} | {yr} | {mmy_count[(mk, md, yr)]:,} | {len(vs):,} | "
            f"{int(statistics.median(vs)):,} | {p10:,} | {p90:,} |")
    add("")

    add("### Топ-15 марок по объёму жалоб\n")
    add("| Марка | Жалоб |")
    add("|---|---|")
    for mk, c in make_count.most_common(15):
        add(f"| {mk} | {c:,} |")
    add("")

    add("### Топ-15 систем по числу жалоб\n")
    add("| Система | Жалоб |")
    add("|---|---|")
    for cd, c in comp_count.most_common(15):
        add(f"| {cd} | {c:,} |")
    add("")

    add("## 3. Форма распределения — проверка на осмысленность\n")
    add("Если гистограмма несёт сигнал, у разных дефектов пик придётся на разный пробег:")
    add("производственный брак — ранний, износ — поздний.\n")
    add("| Марка | Модель | Год | N | 10% | 25% | Медиана | 75% | 90% |")
    add("|---|---|---|---|---|---|---|---|---|")
    for (mk, md, yr), vals in top[:12]:
        vs = sorted(vals)

        def q(x: float) -> int:
            return vs[min(int(len(vs) * x), len(vs) - 1)]

        add(f"| {mk} | {md} | {yr} | {len(vs):,} | {q(.10):,} | {q(.25):,} | "
            f"{int(statistics.median(vs)):,} | {q(.75):,} | {q(.90):,} |")
    add("")

    REPORTS.mkdir(exist_ok=True)
    (REPORTS / "data-validation.md").write_text("\n".join(lines), encoding="utf-8")

    (DATA / "coverage.json").write_text(json.dumps({
        "total_rows": total,
        "vehicle_rows": vehicles,
        "rows_with_miles": with_miles,
        "miles_coverage_pct": round(with_miles / vehicles * 100, 2) if vehicles else 0,
        "unique_mmy": mmy_with_any,
        "mmy_with_miles": len(mmy_miles),
        "mmy_histogram_ready": len(hist_ready),
        "min_for_histogram": MIN_FOR_HISTOGRAM,
    }, indent=2), encoding="utf-8")

    print(f"\nВсего: {total:,} | ТС: {vehicles:,} | с пробегом: {with_miles:,} ({pct(with_miles, vehicles)})")
    print(f"Модель-годов с >={MIN_FOR_HISTOGRAM} пробегами: {len(hist_ready):,}")
    print(f"Отчёт: {REPORTS / 'data-validation.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
