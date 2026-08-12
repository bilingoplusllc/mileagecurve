"""
Проверка гипотезы Q-3: годится ли поле POTAFF из отзывных кампаний как оценка тиража модели.

Логика: отзывная кампания, покрывающая весь модельный год, имеет POTAFF ≈ выпуску.
Значит максимум POTAFF по всем кампаниям для (марка, модель, год) — оценка снизу.

Риск, который и проверяем: кампании часто охватывают несколько модельных лет, а POTAFF
относится ко всей кампании. Тогда максимум завышает тираж одного года кратно числу лет.

Проверка — сверка с известными объёмами продаж в США.
Запуск:  python pipeline/test_denominator.py
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RCL = ROOT / "data" / "raw" / "rcl" / "FLAT_RCL_POST_2010.txt"

F_MAKE, F_MODEL, F_YEAR, F_TYPE, F_POTAFF, F_CAMP = 3, 4, 5, 11, 12, 2

# Известные объёмы продаж в США (открытые отраслевые данные) — эталон для сверки.
KNOWN_US_SALES = {
    ("FORD", "FUSION", 2010): 219_219,
    ("FORD", "FUSION", 2013): 295_280,
    ("FORD", "F-150", 2013): 763_402,   # весь F-Series
    ("TOYOTA", "CAMRY", 2007): 473_108,
    ("TOYOTA", "PRIUS", 2010): 140_928,
    ("HONDA", "CIVIC", 2012): 317_909,
    ("HYUNDAI", "SONATA", 2011): 225_961,
    ("CHEVROLET", "CRUZE", 2012): 237_758,
    ("JEEP", "GRAND CHEROKEE", 2014): 174_275,
    ("NISSAN", "ALTIMA", 2013): 320_723,
}


def main() -> int:
    if not RCL.exists():
        print(f"нет файла: {RCL}")
        return 1

    max_potaff: dict[tuple, int] = {}
    campaigns: defaultdict[tuple, set] = defaultdict(set)
    # сколько модельных лет охватывает каждая кампания — ключ к оценке завышения
    camp_years: defaultdict[str, set] = defaultdict(set)
    camp_potaff: dict[str, int] = {}

    rows = 0
    with open(RCL, "r", encoding="latin-1", errors="replace") as f:
        for line in f:
            p = line.rstrip("\n").split("\t")
            if len(p) < 29:
                continue
            if p[F_TYPE - 1].strip().upper() != "V":
                continue
            rows += 1
            make = p[F_MAKE - 1].strip().upper()
            model = p[F_MODEL - 1].strip().upper()
            yr = p[F_YEAR - 1].strip()
            camp = p[F_CAMP - 1].strip()
            try:
                potaff = int(p[F_POTAFF - 1].strip() or 0)
            except ValueError:
                continue
            if not (make and model and yr.isdigit() and potaff > 0):
                continue
            year = int(yr)
            key = (make, model, year)
            max_potaff[key] = max(max_potaff.get(key, 0), potaff)
            campaigns[key].add(camp)
            camp_years[camp].add(year)
            camp_potaff[camp] = potaff

    print(f"строк ТС в файле отзывов: {rows:,}")
    print(f"уникальных марка+модель+год: {len(max_potaff):,}\n")

    # --- Сверка с известными продажами ---
    print("СВЕРКА max(POTAFF) С ФАКТИЧЕСКИМИ ПРОДАЖАМИ В США")
    print(f"{'модель':38} {'max POTAFF':>12} {'продажи США':>12} {'отношение':>10} {'кампаний':>9}")
    print("-" * 86)
    ratios = []
    for key, sales in KNOWN_US_SALES.items():
        mp = max_potaff.get(key)
        label = f"{key[0]} {key[1]} {key[2]}"
        if not mp:
            print(f"{label:38} {'нет данных':>12} {sales:>12,}")
            continue
        r = mp / sales
        ratios.append(r)
        print(f"{label:38} {mp:>12,} {sales:>12,} {r:>10.2f}x {len(campaigns[key]):>9}")

    if ratios:
        ratios.sort()
        med = ratios[len(ratios) // 2]
        print(f"\nмедианное отношение: {med:.2f}x   разброс: {min(ratios):.2f}x — {max(ratios):.2f}x")

    # --- Насколько кампании «размазаны» по годам ---
    spread = defaultdict(int)
    for c, yrs in camp_years.items():
        spread[len(yrs)] += 1
    print("\nСКОЛЬКО МОДЕЛЬНЫХ ЛЕТ ОХВАТЫВАЕТ ОДНА КАМПАНИЯ")
    tot = sum(spread.values())
    for n in sorted(spread)[:10]:
        print(f"  {n:2d} лет: {spread[n]:6,} кампаний ({spread[n] / tot * 100:4.1f}%)")
    multi = sum(v for k, v in spread.items() if k > 1)
    print(f"  охватывают >1 года: {multi:,} из {tot:,} ({multi / tot * 100:.1f}%)")

    print("\nВЫВОД:")
    if ratios:
        if 0.7 <= med <= 1.6 and max(ratios) < 3:
            print("  POTAFF годится как оценка тиража — отношение близко к 1.")
        elif med > 1.6:
            print("  POTAFF систематически ЗАВЫШАЕТ тираж: кампании охватывают несколько лет,")
            print("  а число затронутых машин указано на всю кампанию. Как знаменатель не годится.")
        else:
            print("  POTAFF систематически ЗАНИЖАЕТ тираж: не каждый год попадает под широкий отзыв.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
