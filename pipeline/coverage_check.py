"""
Сводка покрытия: сколько страниц реально получится и что они охватывают.

Это интеграционная проверка — соединяет карту поколений с базой жалоб и отвечает
на главный планировочный вопрос: сколько страниц уровня «годна к публикации».

Запуск:  python pipeline/coverage_check.py
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "mileagecurve.db"
GENS = ROOT / "data" / "generations.clean.json"
REPORT = ROOT / "reports" / "coverage.md"

# Пороги качества страницы
TIER_A = 300   # полноценная страница: гистограмма надёжна, разбивка по системам осмысленна
TIER_B = 100   # страница есть, но с оговоркой об объёме
TIER_C = 30    # минимум для гистограммы


def main() -> int:
    models = json.loads(GENS.read_text(encoding="utf-8"))
    con = sqlite3.connect(DB)

    rows = []
    for m in models:
        for g in m["generations"]:
            y0, y1 = int(g["year_start"]), int(g["year_end"])
            total, with_miles = con.execute(
                "SELECT COUNT(*), SUM(miles IS NOT NULL) FROM complaints "
                "WHERE make=? AND model=? AND year BETWEEN ? AND ?",
                (m["make"], m["model"], y0, y1)).fetchone()
            rows.append({
                "make": m["make"], "model": m["model"],
                "gen": g.get("gen_label", "?"), "y0": y0, "y1": y1,
                "complaints": total or 0, "with_miles": with_miles or 0,
                "issues": len(g.get("known_issues") or []),
                "platform": g.get("platform_code"),
                "mixed": bool(g.get("mixed_years")),
            })

    rows.sort(key=lambda r: r["with_miles"], reverse=True)
    a = [r for r in rows if r["with_miles"] >= TIER_A]
    b = [r for r in rows if TIER_B <= r["with_miles"] < TIER_A]
    c = [r for r in rows if TIER_C <= r["with_miles"] < TIER_B]
    thin = [r for r in rows if r["with_miles"] < TIER_C]

    total_complaints = con.execute("SELECT COUNT(*) FROM complaints").fetchone()[0]
    covered = sum(r["complaints"] for r in rows)

    L = []
    add = L.append
    add("# Покрытие: сколько страниц получится\n")
    add("| Уровень | Порог (жалоб с пробегом) | Страниц | Что это значит |")
    add("|---|---|---|---|")
    add(f"| **A** | ≥{TIER_A} | **{len(a)}** | полноценная страница: гистограмма надёжна, разбивка по системам осмысленна |")
    add(f"| **B** | {TIER_B}–{TIER_A - 1} | **{len(b)}** | страница публикуется с оговоркой об объёме выборки |")
    add(f"| **C** | {TIER_C}–{TIER_B - 1} | {len(c)} | гистограмма на грани; публиковать выборочно |")
    add(f"| тонкие | <{TIER_C} | {len(thin)} | **не публиковать** отдельной страницей, сворачивать в модель |")
    add("")
    add(f"**Страниц к публикации (A+B): {len(a) + len(b)}.** С уровнем C — {len(a) + len(b) + len(c)}.\n")
    add(f"Охвачено жалоб: {covered:,} из {total_complaints:,} в базе "
        f"({covered / total_complaints * 100:.1f}%).\n")
    add(f"Поколений с флагом «смешанный год»: {sum(1 for r in rows if r['mixed'])}\n")

    add("## Топ-30 страниц по объёму данных\n")
    add("| Марка | Модель | Поколение | Годы | Жалоб | С пробегом | Дефектов |")
    add("|---|---|---|---|---|---|---|")
    for r in rows[:30]:
        add(f"| {r['make']} | {r['model']} | {r['gen']} | {r['y0']}–{r['y1']} | "
            f"{r['complaints']:,} | {r['with_miles']:,} | {r['issues']} |")
    add("")

    add("## Тонкие поколения — свернуть, а не публиковать\n")
    add(f"Всего {len(thin)}. Первые 20:\n")
    add("| Марка | Модель | Поколение | Годы | С пробегом |")
    add("|---|---|---|---|---|")
    for r in sorted(thin, key=lambda r: r["with_miles"])[:20]:
        add(f"| {r['make']} | {r['model']} | {r['gen']} | {r['y0']}–{r['y1']} | {r['with_miles']} |")
    add("")

    REPORT.write_text("\n".join(L), encoding="utf-8")

    print(f"A (≥{TIER_A}): {len(a)}   B ({TIER_B}+): {len(b)}   C ({TIER_C}+): {len(c)}   тонкие: {len(thin)}")
    print(f"К публикации (A+B): {len(a) + len(b)} страниц")
    print(f"Охват жалоб: {covered:,} / {total_complaints:,} ({covered / total_complaints * 100:.1f}%)")
    print(f"→ {REPORT}")
    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
