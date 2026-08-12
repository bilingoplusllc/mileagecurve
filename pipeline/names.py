"""
Отображаемые названия. Только стандартная библиотека — D-009.

Причина существования: Python .title() превращает BMW в «Bmw», GMC в «Gmc»,
RAV4 в «Rav4», CR-V в «Cr-V». Это видно в заголовке вкладки, в <h1> и в описании
для поисковой выдачи — то есть покупатель видит это ДО клика, на 318 страницах.
"""
from __future__ import annotations

import re

# Аббревиатуры и обозначения, которые остаются как есть
KEEP_UPPER = {
    "BMW", "GMC", "RAM", "MINI", "MDX", "RDX", "TSX", "TLX", "ILX", "HHR", "XC90",
    "XC60", "XC70", "RX", "GX", "LX", "ES", "IS", "LS", "NX", "UX", "GS", "SUV",
    "EV", "SE", "XLE", "LE", "TRD", "SRT", "GT", "SS", "LT", "LTZ", "XL", "XLT",
    "ODI", "NHTSA", "VIN", "TSB", "ABS", "AWD", "4WD", "FWD", "RWD", "CVT", "DCT",
}

# Точные написания моделей, где обычные правила не срабатывают
EXACT = {
    "RAV4": "RAV4", "CR-V": "CR-V", "HR-V": "HR-V", "CX-5": "CX-5", "CX-9": "CX-9",
    "CX-30": "CX-30", "MAZDA3": "Mazda3", "MAZDA6": "Mazda6", "F-150": "F-150",
    "F-250": "F-250", "F-350": "F-350", "CR-Z": "CR-Z", "C-CLASS": "C-Class",
    "E-CLASS": "E-Class", "S-CLASS": "S-Class", "3 SERIES": "3 Series",
    "5 SERIES": "5 Series", "X3": "X3", "X5": "X5", "A4": "A4", "A6": "A6",
    "Q5": "Q5", "Q7": "Q7", "G35": "G35", "G37": "G37", "TT": "TT",
    "SILVERADO 1500": "Silverado 1500", "SIERRA 1500": "Sierra 1500",
    "RAM 1500": "Ram 1500", "4RUNNER": "4Runner", "GRAND CHEROKEE": "Grand Cherokee",
    "TOWN AND COUNTRY": "Town and Country", "GRAND CARAVAN": "Grand Caravan",
    "GRAND MARQUIS": "Grand Marquis", "GRAND AM": "Grand Am",
    "UNKNOWN OR OTHER": "Other or unspecified",
}

# Служебные слова, которые внутри названия пишутся строчными
LOWER_WORDS = {"and", "or", "of", "the", "for", "in", "on", "with", "by"}

# Марки — восстанавливаются в цитатах владельцев после снятия КАПСА
MAKES = ("Toyota", "Honda", "Ford", "Chevrolet", "Nissan", "Hyundai", "Kia", "Jeep",
         "Dodge", "Chrysler", "Subaru", "Mazda", "Volkswagen", "Audi", "Volvo",
         "Lexus", "Acura", "Infiniti", "Buick", "Cadillac", "Lincoln", "Mercury",
         "Pontiac", "Saturn", "Oldsmobile", "Mitsubishi", "Mercedes-Benz", "Tesla")


def display(raw: str) -> str:
    """Название марки, модели или узла в человеческом виде."""
    if not raw:
        return ""
    s = raw.strip()
    up = s.upper()
    if up in EXACT:
        return EXACT[up]
    if up in KEEP_UPPER:
        return up

    words = re.split(r"(\s+|-|/)", s)
    out = []
    first = True
    for w in words:
        if not w.strip() or w in ("-", "/"):
            out.append(w)
            continue
        wu = w.upper()
        if wu in KEEP_UPPER:
            out.append(wu)
        elif not first and w.lower() in LOWER_WORDS:
            out.append(w.lower())
        # модели вида «G35», «A4», «CX9» — цифра внутри, значит это обозначение
        elif re.fullmatch(r"[A-Za-z]{1,3}\d{1,3}", w):
            out.append(wu)
        else:
            out.append(w.capitalize())
        first = False
    return "".join(out)


def round_miles(n) -> int | None:
    """Единое округление пробега: до 500 ниже 10 тысяч, до 1000 выше.

    Иначе в одной колонке соседствуют «87,000» и «58,847», и вторая цифра
    создаёт ложное впечатление точности, которой в данных нет.
    """
    if n is None:
        return None
    n = int(n)
    if n < 1_000:
        return n                       # мелкий пробег значим сам по себе, не округляем
    if n < 10_000:
        return int(round(n / 500.0)) * 500
    return int(round(n / 1000.0)) * 1000


def sentence_case(text: str, extra: tuple = ()) -> str:
    """Жалобы NHTSA приходят КАПСОМ. Приводим к нормальному виду, не ломая аббревиатуры."""
    if not text:
        return ""
    letters = [c for c in text if c.isalpha()]
    shouty = bool(letters) and sum(c.isupper() for c in letters) / len(letters) >= 0.7
    if not shouty:
        return _restore(text, extra)   # регистр нормальный, но обозначения всё равно чиним
    out, cap = [], True
    for ch in text.lower():
        if cap and ch.isalpha():
            out.append(ch.upper())
            cap = False
        else:
            out.append(ch)
        if ch in ".!?":
            cap = True
    return _restore("".join(out), extra)


def _restore(s: str, extra: tuple = ()) -> str:
    """Вернуть аббревиатуры и обозначения моделей.

    Без этого «GMC» в жалобе владельца становится «Gmc», а «RAV4» — «Rav4»,
    прямо в цитате на странице.
    """
    for ab in ("nhtsa", "abs", "suv", "vin", "tsb", "usa", "us dot", "epa", "dot",
               "led", "ecu", "pcm", "tpms", "awd", "4wd", "fwd", "rwd", "cvt",
               "mph", "rpm", "psi", "vsc"):
        s = re.sub(rf"\b{ab}\b", ab.upper(), s)
    # Только однозначные обозначения. Короткие вроде IS, ES, LS, SE, GT сталкиваются
    # с обычными словами: без этого фильтра глагол «is» превращался в модель Lexus IS.
    safe = {t for t in (KEEP_UPPER | set(EXACT))
            if len(t) >= 3 and t not in {"SUV", "AWD", "FWD", "RWD", "XLT", "XLE", "TRD"}}
    for token in sorted(safe, key=len, reverse=True):
        s = re.sub(rf"\b{re.escape(token.lower())}\b", EXACT.get(token, token), s,
                   flags=re.IGNORECASE)
    for mk in MAKES:
        s = re.sub(rf"\b{mk.lower()}\b", mk, s, flags=re.IGNORECASE)
    # Название модели самой страницы: владелец пишет «my acadia», нужно «my Acadia».
    # Общего списка моделей не держим — их сотни, а нужна ровно текущая.
    for token in extra:
        if token and len(token) >= 3:
            s = re.sub(rf"\b{re.escape(str(token).lower())}\b", str(token), s,
                       flags=re.IGNORECASE)
    return s


def truncate_words(text: str, limit: int) -> str:
    """Обрезка по границе слова — «...mid-wor» в цитате выглядит как брак."""
    if not text or len(text) <= limit:
        return text or ""
    cut = text[:limit].rsplit(" ", 1)[0].rstrip(" ,;:—-")
    return cut + "…"
