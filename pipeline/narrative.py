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

import statistics

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
        med = x["median_miles"]
        ratio = med / overall if overall else 1
        name = plain(x["system"])
        share = x["share"]
        rng = (f"{fmt(x['p25_miles'])} and {fmt(x['p75_miles'])} miles"
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
        names = ", ".join(f"{plain(k)} ({v})" for k, v in top)
        out.append(_p(
            f"The campaigns cluster around {names}. Repeated recalls against the same area of "
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
    sev = s["severity"]
    total = s["complaints_total"]
    if not total:
        return ""
    parts = []
    if sev["crashes"]:
        parts.append(f"{fmt(sev['crashes'])} reported a crash")
    if sev["fires"]:
        parts.append(f"{fmt(sev['fires'])} reported a fire")
    if sev["injured"]:
        parts.append(f"{fmt(sev['injured'])} reported an injury")
    if sev["deaths"]:
        parts.append(f"{fmt(sev['deaths'])} reported a fatality")
    if not parts:
        return ""

    pct = (sev["crashes"] or 0) / total * 100
    out = [_p(
        f"Of the {fmt(total)} complaints filed against this generation, " + "; ".join(parts) +
        f". Crash-involved reports represent {pct:.1f}% of the total.")]
    out.append(_p(
        "These are owner-reported outcomes, not verified investigations, and they are not "
        "adjusted for how many of these vehicles are on the road. They are included because the "
        "distinction between a fault that strands a car and a fault that causes a collision is "
        "the one that matters most, and it is not visible in a complaint count alone."))
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
            f"{sh['early_share'] * 100:.0f}% of failures below 12,000 miles — will already have "
            f"happened on any example you are looking at today, and either been repaired under "
            f"warranty or not. Ask what was done. The late cluster, "
            f"{sh['late_share'] * 100:.0f}% above 100,000 miles, is the one still ahead of you if "
            f"the car has lower mileage than that."))
    elif kind == "early":
        out.append(_p(
            f"For a buyer, an early-failure pattern is comparatively good news on a used example: "
            f"{sh['early_share'] * 100:.0f}% of the reported failures occur in the first 12,000 "
            f"miles, which on a car of this age means they have already happened or they were "
            f"never going to. Service history matters more than mileage here."))
    elif kind == "late":
        out.append(_p(
            f"For a buyer, a late-failure pattern shifts the question from <em>whether</em> to "
            f"<em>when</em>. {sh['late_share'] * 100:.0f}% of reported failures occur beyond "
            f"100,000 miles, so an example approaching that figure is approaching the range where "
            f"other owners started reporting problems. The middle half of all failures falls "
            f"between {fmt(sh['p25'])} and {fmt(sh['p75'])} miles."))
    else:
        out.append(_p(
            f"For a buyer, failures on this generation are spread rather than concentrated: the "
            f"middle half falls between {fmt(sh['p25'])} and {fmt(sh['p75'])} miles, with a "
            f"median of {fmt(sh['median'])}. There is no single mileage threshold to watch, which "
            f"means condition and maintenance records are more informative than the odometer."))

    top = [x for x in s["systems"] if x.get("median_miles")][:2]
    if top:
        names = " and ".join(plain(x["system"]) for x in top)
        earliest = min(top, key=lambda x: x["median_miles"])
        out.append(_p(
            f"On inspection, {names} are where this generation's reports concentrate, so those "
            f"are the areas worth a specific look. {plain(earliest['system']).capitalize()} in "
            f"particular shows a median failure mileage of {fmt(earliest['median_miles'])}, which "
            f"gives a concrete number to compare against the odometer of any car you are "
            f"considering."))

    out.append(_p(
        "None of this is a substitute for a pre-purchase inspection on the individual car. "
        "Aggregate patterns describe a population; the example in front of you has its own "
        "history."))
    return "".join(out)


def full_analysis(s: dict, gen: dict) -> list[tuple[str, str]]:
    """Возвращает список (заголовок, html) — разделы разбора."""
    sections = [
        ("Which systems, and when", systems_narrative(s)),
        ("Differences between model years", years_narrative(s, gen)),
        ("Recalls and what they cover", recalls_narrative(s)),
        ("Reported severity", severity_narrative(s)),
        ("What this means if you are buying one", guidance_narrative(s)),
    ]
    return [(t, b) for t, b in sections if b]
