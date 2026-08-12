"""
Нормализация карты поколений после разметки. Детерминированный Python — PLAYBOOK §5.

Чинит проблемы, найденные аудитом:
  1. дубликаты моделей;
  2. пересечения годов (реальные карряоверы, когда старое и новое поколение продавались одновременно);
  3. псевдо-поколения «нет модельного года» вместо явных пропусков;
  4. служебные записи, притворяющиеся дефектами (component = "n/a", "Data integrity" и т.п.);
  5. расплывчатые и слабо подтверждённые утверждения о дефектах — помечаются на ручную проверку.

Правило для спорного года: отдаём НОВОМУ поколению и ставим флаг mixed_year.
Обоснование: в смешанный год новое поколение почти всегда массовее, а исключение года
теряет сигнал. Флаг выносится на страницу — читатель должен знать.

Вход:  data/generations.json (сырая разметка)
Выход: data/generations.clean.json + reports/generation-cleanup.md

Запуск:  python pipeline/normalize_generations.py
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "generations.json"
OUT = ROOT / "data" / "generations.clean.json"
REPORT = ROOT / "reports" / "generation-cleanup.md"

# Компоненты, под которыми агенты сложили служебную информацию, а не дефекты.
META_COMPONENTS = {
    "n/a", "na", "none", "data integrity", "generation overlap", "note", "notes",
    "powertrain (mid-generation change)", "mid-generation change", "data note",
    "editorial", "routing", "coverage", "nameplate", "model identification",
    "generation note", "data", "scope",
}

# Признаки того, что запись не готова к публикации.
UNPUBLISHABLE_MARKERS = [
    "treat as reported", "before publishing", "confirm ", "unverified",
    "rather than fully established", "needs verification", "to be confirmed",
]

# Слишком коротко/расплывчато, чтобы быть утверждением о механизме отказа.
MIN_DESCRIPTION_CHARS = 60

VAGUE_PATTERNS = [
    r"^various\b", r"^multiple\b", r"^assorted\b", r"^general\b",
    r"electrical (faults|problems|issues)\.?$", r"warning[- ]light cascades?\.?$",
]

WEAK_SOURCE_HOSTS = ("forum", "reddit.com", "clublexus", "f150forum", "bimmerpost",
                     "tacomaworld", "cherokeeforum", "priuschat")


def is_meta(issue: dict) -> bool:
    return (issue.get("component") or "").strip().lower() in META_COMPONENTS


def is_unpublishable(issue: dict) -> bool:
    text = f"{issue.get('description','')} {issue.get('affected_years','')}".lower()
    return any(m in text for m in UNPUBLISHABLE_MARKERS)


def is_vague(issue: dict) -> bool:
    d = (issue.get("description") or "").strip()
    if len(d) < MIN_DESCRIPTION_CHARS:
        return True
    return any(re.search(p, d.lower()) for p in VAGUE_PATTERNS)


def main() -> int:
    # utf-8-sig: PowerShell пишет BOM, обычный utf-8 на нём падает
    models = json.loads(SRC.read_text(encoding="utf-8-sig"))
    log: list[str] = []
    add = log.append

    add("# Очистка карты поколений\n")
    add(f"> Вход: {len(models)} моделей, "
        f"{sum(len(m.get('generations') or []) for m in models)} поколений\n")

    # --- 1. Дубликаты моделей ---
    seen: dict[tuple, dict] = {}
    dupes = []
    for m in models:
        key = (m["make"].upper(), m["model"].upper())
        if key in seen:
            # оставляем ту запись, где больше поколений и больше описанных дефектов
            a, b = seen[key], m
            score = lambda x: (len(x.get("generations") or []),
                               sum(len(g.get("known_issues") or []) for g in (x.get("generations") or [])))
            if score(b) > score(a):
                seen[key] = b
            dupes.append(f"{key[0]} {key[1]}")
        else:
            seen[key] = m
    models = list(seen.values())
    add("## 1. Дубликаты\n")
    add(f"Удалено дубликатов: **{len(dupes)}** — {', '.join(dupes) or 'нет'}\n")

    # --- 2. Псевдо-поколения «нет модельного года» → явные пропуски ---
    gap_rows = 0
    for m in models:
        gens, gaps = [], []
        for g in m.get("generations") or []:
            label = (g.get("gen_label") or "").lower()
            if ("no us model year" in label or "not sold" in label or "gap" in label
                    or "hiatus" in label or "discontinued" in label):
                gaps.append({"year_start": g.get("year_start"), "year_end": g.get("year_end"),
                             "reason": g.get("gen_label")})
                gap_rows += 1
            else:
                gens.append(g)
        m["generations"] = gens
        if gaps:
            m["production_gaps"] = gaps
    add("## 2. Пропуски в производстве\n")
    add(f"Псевдо-поколений превращено в явные пропуски: **{gap_rows}**\n")

    # --- 3. Пересечения годов ---
    overlaps = []
    for m in models:
        gens = sorted([g for g in m["generations"]
                       if isinstance(g.get("year_start"), (int, float))
                       and isinstance(g.get("year_end"), (int, float))],
                      key=lambda g: (g["year_start"], g["year_end"]))
        for i in range(len(gens) - 1):
            cur, nxt = gens[i], gens[i + 1]
            if cur["year_end"] >= nxt["year_start"]:
                lo, hi = nxt["year_start"], min(cur["year_end"], nxt["year_end"])
                # спорные годы отдаём НОВОМУ поколению, старое подрезаем
                cur["year_end"] = nxt["year_start"] - 1
                nxt.setdefault("mixed_years", [])
                for y in range(int(lo), int(hi) + 1):
                    if y not in nxt["mixed_years"]:
                        nxt["mixed_years"].append(y)
                nxt["mixed_year_note"] = (
                    "В этот модельный год на рынке одновременно продавались обе версии; "
                    "жалобы NHTSA не разделены по кузову.")
                overlaps.append(f"{m['make']} {m['model']}: {int(lo)}"
                                + (f"–{int(hi)}" if hi > lo else "")
                                + f" → отдан «{nxt.get('gen_label','?')}»")
        m["generations"] = [g for g in gens if g["year_start"] <= g["year_end"]]

    add("## 3. Пересечения годов\n")
    add(f"Разрешено пересечений: **{len(overlaps)}**. Спорный год отдан новому поколению "
        "и помечен флагом `mixed_years` — он выносится на страницу.\n")
    for o in overlaps:
        add(f"- {o}")
    add("")

    # --- 4. Чистка known_issues ---
    stats = defaultdict(int)
    review: list[str] = []
    for m in models:
        for g in m["generations"]:
            keep = []
            for iss in g.get("known_issues") or []:
                if is_meta(iss):
                    stats["meta"] += 1
                    # служебное не выбрасываем — переносим в заметки поколения
                    g.setdefault("build_notes", []).append(
                        f"{iss.get('component')}: {iss.get('description')}")
                    continue
                if is_unpublishable(iss):
                    stats["unpublishable"] += 1
                    review.append(f"{m['make']} {m['model']} {g.get('gen_label')}: "
                                  f"[неготово] {iss.get('component')} — "
                                  f"{(iss.get('description') or '')[:110]}")
                    continue
                if is_vague(iss):
                    stats["vague"] += 1
                    review.append(f"{m['make']} {m['model']} {g.get('gen_label')}: "
                                  f"[расплывчато] {iss.get('component')} — "
                                  f"{(iss.get('description') or '')[:110]}")
                    continue
                srcs = g.get("sources") or []
                if srcs and all(any(h in s.lower() for h in WEAK_SOURCE_HOSTS) for s in srcs):
                    iss["source_strength"] = "weak"
                    stats["weak_source"] += 1
                keep.append(iss)
                stats["kept"] += 1
            g["known_issues"] = keep

    add("## 4. Чистка описаний дефектов\n")
    add("| Категория | Записей | Что сделано |")
    add("|---|---|---|")
    add(f"| Служебные (component = «n/a», «Data integrity»…) | {stats['meta']} | перенесены в `build_notes`, из дефектов убраны |")
    add(f"| Помечены самим агентом как неготовые к публикации | {stats['unpublishable']} | **убраны**, вынесены на ручную проверку |")
    add(f"| Расплывчатые (короче {MIN_DESCRIPTION_CHARS} симв. или без механизма) | {stats['vague']} | **убраны**, вынесены на ручную проверку |")
    add(f"| Опираются только на форумы | {stats['weak_source']} | оставлены с меткой `source_strength: weak` |")
    add(f"| **Оставлено к публикации** | **{stats['kept']}** | |")
    add("")

    # --- 5. Итоговая проверка ---
    problems = []
    for m in models:
        gens = sorted(m["generations"], key=lambda g: g["year_start"])
        for i in range(len(gens) - 1):
            if gens[i]["year_end"] >= gens[i + 1]["year_start"]:
                problems.append(f"ОСТАЛОСЬ ПЕРЕСЕЧЕНИЕ: {m['make']} {m['model']}")
        for g in gens:
            if g["year_end"] - g["year_start"] > 14:
                problems.append(f"длинное поколение (>14 лет): {m['make']} {m['model']} "
                                f"{g['year_start']}–{g['year_end']}")

    total_gens = sum(len(m["generations"]) for m in models)
    add("## 5. Итог\n")
    add(f"- моделей: **{len(models)}**")
    add(f"- поколений: **{total_gens}**")
    add(f"- дефектов к публикации: **{stats['kept']}**")
    add(f"- оставшихся структурных проблем: **{len([p for p in problems if 'ПЕРЕСЕЧЕНИЕ' in p])}**")
    add("")
    if problems:
        add("### Требует внимания\n")
        for p in problems[:30]:
            add(f"- {p}")
        add("")

    if review:
        add("## 6. На ручную проверку — убранные утверждения\n")
        add("Эти записи не публикуются. Сайт выходит под именем компании: "
            "недоказанные утверждения о дефектах автомобилей — юридический риск.\n")
        for r in review[:60]:
            add(f"- {r}")
        if len(review) > 60:
            add(f"\n…и ещё {len(review) - 60}.")
        add("")

    OUT.write_text(json.dumps(models, indent=1, ensure_ascii=False), encoding="utf-8")
    REPORT.parent.mkdir(exist_ok=True)
    REPORT.write_text("\n".join(log), encoding="utf-8")

    print(f"моделей: {len(models)} | поколений: {total_gens} | дефектов: {stats['kept']}")
    print(f"убрано: служебных {stats['meta']}, неготовых {stats['unpublishable']}, "
          f"расплывчатых {stats['vague']}")
    print(f"пересечений разрешено: {len(overlaps)}")
    print(f"→ {OUT}\n→ {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
