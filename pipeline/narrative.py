"""
Содержательный разбор, выводимый ИЗ ДАННЫХ. Только стандартная библиотека — D-009.

Это не «наполнитель до нужного объёма». Каждое утверждение — факт о конкретной выборке:
доля системы, её пробег отказа относительно машины в целом, совпадение с отзывной кампанией,
разброс между модельными годами. На двух разных поколениях получается разный текст,
потому что разные числа, а не потому что переставлены слова.

Задача — довести страницу до 1500+ слов настоящего разбора без вызова модели.
Интерпретирующий слой поверх этого пишется отдельно и только для верхних страниц.
"""
from __future__ import annotations

import re
import statistics

import names

# Пороги, по которым система считается «ранней» или «поздней» относительно машины в целом
EARLY_RATIO = 0.65   # медиана системы заметно ниже медианы по машине
LATE_RATIO = 1.45

SYSTEM_PLAIN = {
    "POWER TRAIN": "the transmission and driveline",
    "ENGINE": "the engine",
    "ENGINE AND ENGINE COOLING": "the engine and its cooling system",
    "ELECTRICAL SYSTEM": "the electrical system",
    "SERVICE BRAKES": "the brakes",
    "SERVICE BRAKES, HYDRAULIC": "the hydraulic brake circuit",
    "SERVICE BRAKES, ELECTRIC": "the electronic brake control",
    "STEERING": "the steering",
    "SUSPENSION": "the suspension",
    "AIR BAGS": "the airbag system",
    "VEHICLE SPEED CONTROL": "throttle and speed control",
    "FUEL/PROPULSION SYSTEM": "the fuel and propulsion system",
    "FUEL SYSTEM, GASOLINE": "the fuel system",
    "EXTERIOR LIGHTING": "the exterior lighting",
    "STRUCTURE": "body structure",
    "SEAT BELTS": "the seat belts",
    "VISIBILITY": "visibility equipment",
    "WHEELS": "the wheels",
    "TIRES": "the tyres",
    "LATCHES/LOCKS/LINKAGES": "latches and locks",
    "EQUIPMENT": "equipment",
    "UNKNOWN OR OTHER": "problems owners could not categorise",
    "AIR BAGS:FRONTAL": "the frontal airbags",
    "TRACTION CONTROL SYSTEM": "traction control",
    "FORWARD COLLISION AVOIDANCE": "forward collision avoidance",
    "BACK OVER PREVENTION": "the reversing camera and sensors",
    "PARKING BRAKE": "the parking brake",
    "EXHAUST SYSTEM": "the exhaust system",
    "HYBRID PROPULSION SYSTEM": "the hybrid propulsion system",
}


def plain(system: str) -> str:
    s = (system or "").upper().strip()
    return SYSTEM_PLAIN.get(s, s.lower() or "an unspecified system")


def fmt(n) -> str:
    return f"{int(n):,}" if n is not None else "—"


def _p(text: str) -> str:
    return f"<p>{text}</p>"


# --------------------------------------------------------------- system-by-system
def systems_narrative(s: dict) -> str:
    """Разбор по системам: доля, свой пробег отказа, положение относительно машины."""
    overall = s["shape"].get("median")
    if not overall:
        return ""

    out: list[str] = []
    ranked = [x for x in s["systems"] if x.get("median_miles")][:6]
    if not ranked:
        return ""

    out.append(_p(
        f"Complaints about this generation are not spread evenly across the vehicle, and the "
        f"systems that generate the most of them do not all fail at the same point in a car's "
        f"life. The median failure across all systems here is {fmt(overall)} miles; the figures "
        f"below show which parts of the car run ahead of that and which run behind."))

    for i, x in enumerate(ranked):
        med = names.round_miles(x["median_miles"])
        ratio = med / overall if overall else 1
        name = plain(x["system"])
        share = x["share"]
        rng = (f"{fmt(names.round_miles(x['p25_miles']))} and "
               f"{fmt(names.round_miles(x['p75_miles']))} miles"
               if x.get("p25_miles") else None)

        # согласование числа: «the brakes account», но «the engine accounts»
        plural = name.rstrip().endswith("s") and not name.rstrip().endswith("ss")
        verb, pron = ("account", "they") if plural else ("accounts", "it")

        bits = [f"<strong>{name.capitalize()}</strong> {verb} for {share}% of complaints "
                f"({fmt(x['count'])} reports, {fmt(x['with_miles'])} of them with a mileage "
                f"figure), "]

        if ratio <= EARLY_RATIO:
            bits.append(f"and {pron} fail{'' if plural else 's'} early — a median of {fmt(med)} miles, well before the "
                        f"vehicle's overall median. Failures clustered this far below the rest of "
                        f"the car usually point to a design or manufacturing problem rather than "
                        f"wear, because wear does not selectively target one system on low-mileage "
                        f"examples")
        elif ratio >= LATE_RATIO:
            bits.append(f"and {pron} fail{'' if plural else 's'} late — a median of {fmt(med)} "
                        f"miles, considerably beyond the vehicle's overall median. That pattern is "
                        f"consistent with normal service life rather than a defect, though it "
                        f"matters for anyone buying an example already near that mileage")
        else:
            bits.append(f"with a median of {fmt(med)} miles, close to the vehicle's overall "
                        f"pattern")

        if rng:
            bits.append(f". The middle half of these reports falls between {rng}")

        out.append(_p("".join(bits) + "."))

        # На первой системе даём контекст, что означает доля
        if i == 0 and share >= 25:
            out.append(_p(
                f"A single system taking {share}% of all complaints is a concentration worth "
                f"noting. It means that for this generation, most of what owners reported came "
                f"back to one area of the car rather than being distributed across many small "
                f"faults."))

    return "".join(out)


# --------------------------------------------------------------- model years
def years_narrative(s: dict, gen: dict) -> str:
    rows = [y for y in s["by_year"] if y["complaints"] >= 20]
    if len(rows) < 3:
        return ""

    counts = [y["complaints"] for y in rows]
    worst = max(rows, key=lambda y: y["complaints"])
    best = min(rows, key=lambda y: y["complaints"])
    med = statistics.median(counts)

    out = [_p(
        f"Within this generation, complaint volume is not constant across model years. "
        f"The {worst['year']} model year drew the most — {fmt(worst['complaints'])} complaints — "
        f"while {best['year']} drew the fewest at {fmt(best['complaints'])}. The median year "
        f"sits at {fmt(med)}.")]

    if worst["complaints"] > med * 2 and med > 0:
        factor = worst["complaints"] / med
        out.append(_p(
            f"That makes {worst['year']} an outlier: roughly {factor:.1f} times the median year "
            f"of this generation. A single year standing that far apart usually reflects either a "
            f"first-year issue that was later corrected, or a component change introduced for "
            f"that year. Anyone shopping this generation has a straightforward reason to prefer a "
            f"different year, all else being equal."))
    elif rows[0]["complaints"] > med * 1.6:
        out.append(_p(
            f"The first year of the generation, {rows[0]['year']}, sits above the median. "
            f"That is a common pattern — early production of a redesigned vehicle tends to "
            f"surface problems that later years do not repeat — and it is worth weighing when "
            f"choosing between years."))

    if gen.get("mixed_years"):
        yrs = ", ".join(str(y) for y in gen["mixed_years"])
        out.append(_p(
            f"One caveat on the year figures: in {yrs}, the manufacturer sold both this "
            f"generation and the previous one at the same time, and NHTSA records do not "
            f"distinguish between them. Complaints filed under that year may describe either "
            f"vehicle."))

    return "".join(out)


# --------------------------------------------------------------- recalls
def recalls_narrative(s: dict) -> str:
    n = s["recalls_count"]
    if not n:
        return _p(
            "No recall campaigns covering this generation appear in NHTSA's post-2010 recall "
            "file. That is not the same as an absence of problems — recalls address safety "
            "defects specifically, and many of the complaints above concern faults that are "
            "expensive or annoying without meeting that threshold.")

    out = [_p(
        f"NHTSA records {n} recall campaign{'s' if n != 1 else ''} covering vehicles in this "
        f"generation. A recall means the manufacturer or the regulator concluded there was a "
        f"safety defect or a standard was not met, and that a free remedy is owed to owners — "
        f"including second and later owners.")]

    if s["severe_advisories"]:
        out.append(_p(
            f"<strong>{s['severe_advisories']} of these carry a severe advisory</strong> — "
            f"NHTSA's <em>do not drive</em> or <em>park outside</em> warnings, which the agency "
            f"applies only when it considers the risk immediate. If you own one of these "
            f"vehicles, that is the first thing to check by VIN."))

    comps = {}
    for r in s["recalls"]:
        key = (r["component"] or "").split(":")[0].strip().upper()
        if key:
            comps[key] = comps.get(key, 0) + 1
    top = sorted(comps.items(), key=lambda kv: -kv[1])[:3]
    if top and top[0][1] > 1:
        campaign_areas = ", ".join(f"{plain(k)} ({v})" for k, v in top)
        out.append(_p(
            f"The campaigns cluster around {campaign_areas}. Repeated recalls against the same area of "
            f"the car generally mean the first remedy did not fully resolve the underlying "
            f"problem."))

    out.append(_p(
        "Recall status is specific to the individual vehicle, not the model. Checking a VIN "
        'against <a href="https://www.nhtsa.gov/recalls">NHTSA\'s lookup</a> is free and takes '
        "under a minute, and it is the only way to know whether a particular car has had the "
        "work done."))
    return "".join(out)


# --------------------------------------------------------------- severity
def severity_narrative(s: dict) -> str:
    """Ряд из четырёх ячеек ОДНИМ кеглем — и никогда график. Флаги пересекаются
    (одна жалоба несёт несколько), разброс 100×+: линейная длина прячет смерти,
    логарифм у нас запрещён, стек двойным счётом лжёт о частях целого,
    пиктограммы выдумывают единицу. Позиция и одинаковый кегль — единственные
    каналы, в которых нечего завысить."""
    sev = s["severity"]
    total = s["complaints_total"]
    if not total or not any(sev.values()):
        return ""
    pct = (sev["crashes"] or 0) / total * 100
    cells = [("Crashes", f'{fmt(sev["crashes"])} ({pct:.1f}%)'),
             ("Fires", fmt(sev["fires"])),
             ("Injury reports", fmt(sev["injured"])),
             ("Fatality reports", fmt(sev["deaths"]))]
    row = "".join(f'<div><dt>{k}</dt><dd>{v}</dd></div>' for k, v in cells)
    out = [_p(f"What owners reported alongside the failure itself, out of {fmt(total)} "
              f"complaints against this generation:"),
           f'<dl class="pct">{row}</dl>',
           _p("These flags are self-reported by complainants and unverified by NHTSA; one "
              "report can carry several flags, so the counts overlap and do not sum to a "
              "total. They are not adjusted for how many of these vehicles are on the road. "
              "No chart is drawn here on purpose: overlapping counts spanning very "
              "different magnitudes cannot be honestly encoded as lengths.")]
    return "".join(out)


# --------------------------------------------------------------- buying guidance
def guidance_narrative(s: dict) -> str:
    sh = s["shape"]
    if not sh.get("median"):
        return ""
    kind = sh["kind"]
    out = []

    if kind == "bimodal":
        out.append(_p(
            f"For a buyer, the two-peak pattern is the useful part. The early cluster — "
            f"{sh['early_pct']}% of failures below 12,000 miles — will already have "
            f"happened on any example you are looking at today, and either been repaired under "
            f"warranty or not. Ask what was done. The late cluster, "
            f"{sh['late_pct']}% above 100,000 miles, is the one still ahead of you if "
            f"the car has lower mileage than that."))
    elif kind == "early":
        out.append(_p(
            f"For a buyer, an early-failure pattern is comparatively good news on a used example: "
            f"{sh['early_pct']}% of the reported failures occur in the first 12,000 "
            f"miles, which on a car of this age means they have already happened or they were "
            f"never going to. Service history matters more than mileage here."))
    elif kind == "late":
        out.append(_p(
            f"For a buyer, a late-failure pattern shifts the question from <em>whether</em> to "
            f"<em>when</em>. {sh['late_pct']}% of reported failures occur beyond "
            f"100,000 miles, so an example approaching that figure is approaching the range where "
            f"other owners started reporting problems. The middle half of all failures falls "
            f"between {fmt(names.round_miles(sh['p25']))} and "
            f"{fmt(names.round_miles(sh['p75']))} miles."))
    else:
        out.append(_p(
            f"For a buyer, failures on this generation are spread rather than concentrated: the "
            f"middle half falls between {fmt(names.round_miles(sh['p25']))} and "
            f"{fmt(names.round_miles(sh['p75']))} miles, with a "
            f"median of {fmt(names.round_miles(sh['median']))}. There is no single mileage "
            f"threshold to watch, which "
            f"means condition and maintenance records are more informative than the odometer."))

    top = [x for x in s["systems"] if x.get("median_miles")][:2]
    if top:
        top_systems = " and ".join(plain(x["system"]) for x in top)
        earliest = min(top, key=lambda x: x["median_miles"])
        out.append(_p(
            f"On inspection, {top_systems} are where this generation's reports concentrate, so those "
            f"are the areas worth a specific look. {plain(earliest['system']).capitalize()} in "
            f"particular shows a median failure mileage of "
            f"{fmt(names.round_miles(earliest['median_miles']))}, which "
            f"gives a concrete number to compare against the odometer of any car you are "
            f"considering."))

    out.append(_p(
        "None of this is a substitute for a pre-purchase inspection on the individual car. "
        "Aggregate patterns describe a population; the example in front of you has its own "
        "history."))
    return "".join(out)


def checklist_items(s: dict, gen: dict) -> list[tuple[str, str, bool]]:
    """Проверка перед покупкой: (жирный зачин, продолжение, тревожный?).

    Каждый пункт — действие, а не факт: персона стоит на площадке с телефоном
    и у неё три минуты. Всё генерируется из данных; ручной работы на страницу
    нет. ЗАПРЕЩЕНО: «years to avoid» и любые множители по годам — счёт жалоб
    по годам смешивает объём продаж и срок на дороге (D-007).
    """
    items: list[tuple[str, str, bool]] = []

    dnd = any(r["do_not_drive"] for r in s["recalls"])
    if dnd:
        items.append((
            "A DO NOT DRIVE recall covers part of this generation.",
            "Run the VIN before you drive it home — the fix is free at any dealer.",
            True))
    if s["recalls_count"]:
        items.append((
            'Run the VIN at <a href="https://www.nhtsa.gov/recalls">nhtsa.gov/recalls</a>.',
            f'{s["recalls_count"]} campaign{"s" if s["recalls_count"] != 1 else ""} cover this '
            f'generation; an open recall is a free repair you can make the seller\'s problem.',
            False))

    # Системы с ранним отказом: на машине этого возраста дефект либо уже
    # случился, либо уже не случится — вопрос в том, чинили ли по гарантии.
    early = [x for x in s["systems"]
             if x.get("median_miles") and x["median_miles"] <= 12_000
             and x.get("count", 0) >= 50][:2]
    for x in early:
        nm = plain(x["system"])
        items.append((
            f"Ask for {re.sub(r'^the ', '', nm)} repair records.",
            f"This area fails at a median of {fmt(names.round_miles(x['median_miles']))} miles — "
            f"on any car this age it already happened or never will; the question is whether "
            f"it was fixed under warranty.",
            False))

    # Курируемые документированные проблемы — с годами, которых они касаются.
    for it in (gen.get("known_issues") or [])[:3]:
        comp = names.display(it.get("component", "")) or "the documented problem area"
        yrs = it.get("affected_years", "")
        yrs_bit = f" on {yrs.replace('-', '–')} cars" if yrs else ""
        # Опускаем регистр, но возвращаем аббревиатуры: «Check EGR system»,
        # а не «Check egr system».
        comp_low = names._restore(comp.lower()) if not comp.isupper() else comp
        items.append((
            f"Check {comp_low}{yrs_bit}.",
            names.truncate_words(it.get("description") or "", 220), False))

    # Нейтральный указатель на разброс по годам — без «избегайте» и множителей.
    by = s.get("by_year") or []
    if len(by) > 2:
        counts = [y["complaints"] for y in by if y.get("complaints")]
        if counts and max(counts) >= 3 * max(1, min(counts)):
            items.append((
                "Complaint reports are not spread evenly across model years here",
                "— see the by-model-year table below before you settle on a year.", False))

    items.append((
        "End with a pre-purchase inspection of this car.",
        "Aggregate data describes the population; the example in front of you has its own history.",
        False))
    return items


def full_analysis(s: dict, gen: dict) -> list[tuple[str, str]]:
    """Возвращает список (заголовок, html) — разделы разбора.

    «What this means if you are buying one» отсюда убран: его содержимое
    влито в раздел «Before you buy» (чек-лист), чтобы две покупательские
    секции не соревновались на одной странице.
    """
    sections = [
        ("Which systems, and when", systems_narrative(s)),
        ("Differences between model years", years_narrative(s, gen)),
        ("Recalls and what they cover", recalls_narrative(s)),
        ("Reported severity", severity_narrative(s)),
    ]
    return [(t, b) for t, b in sections if b]
