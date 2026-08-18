"""Глифы типов кузова — семейство «geometric-minimal», финальная редакция.

Одна грамматика на все восемь: viewBox 0 0 48 20, нос слева, линия земли
y=18 (центр колеса 15 + внешний радиус 3). Колёса идентичны во всех глифах:
кольца на (11,15) и (37,15), внешний r=3 по часовой (sweep=1), ступица r=1.2
против часовой (sweep=0) — при правиле nonzero перекрытие кузова и колеса
остаётся залитым, а ступица читается дырой. Кузов — один замкнутый
многоугольник M/L/Z; кривых в кузове нет, дуги только в колёсах.

Правки судей учтены: пикап — борт y=8 (нотка 6 юнитов); SUV — крыша до x=41,
тяжёлый скат к (45,6); фургон — плоский вертикальный нос x=2 (нарочно ломает
семейный скос бампера — это классовый признак); купе — фастбэк до (38,8.5),
палуба на полюнита ниже седана; хэтчбек — корма x=42 (2 юнита от колеса);
ступица 1.2 (кольцо 1.8 ≈ 1.1px при 30px). Выравнивание H1 — center, не
flex-end: проверено в Chrome на двухстрочном заголовке 360px, flex-end
отрывает глиф к строке годов.

Цвет НЕ задаётся здесь: fill="currentColor", а размещённые элементы получают
color:var(--bar) — тон гистограмм, ниже текста в иерархии; тёмная тема
приходит автоматически через токен. Размер тоже в CSS (width + aspect-ratio),
поэтому у <svg> нет атрибутов width/height.

Данные: data/body_styles.json — {"MAKE|MODEL": стиль} с ТОЧНЫМИ верхними
регистрами из generations.clean.json. Нет ключа или файла — глифа нет;
никогда не угадываем.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Оба колеса, одинаковые во всех восьми глифах. Внешний круг по часовой,
# ступица против — правило nonzero (по умолчанию) держит дыру только в ступице.
_WHEELS = ("M8 15a3 3 0 1 1 6 0a3 3 0 1 1-6 0Z"
           "m1.8 0a1.2 1.2 0 1 0 2.4 0a1.2 1.2 0 1 0-2.4 0Z"
           "M34 15a3 3 0 1 1 6 0a3 3 0 1 1-6 0Z"
           "m1.8 0a1.2 1.2 0 1 0 2.4 0a1.2 1.2 0 1 0-2.4 0Z")

_BODIES = {
    "sedan":     "M2 12.5L3 8L14 8L18 4L30 4L34 8L44 8L46 10.5L46 12.5Z",
    "coupe":     "M2 12.5L3 8L16 8L21 4L27 4L38 8.5L44 8.5L46 11L46 12.5Z",
    "wagon":     "M2 12.5L3 8L14 8L18 4L40 4L43 7L44 12.5Z",
    "hatchback": "M2 12.5L3 8L14 8L18 4L34 4L42 10.5L42 12.5Z",
    "suv":       "M2 12.5L3 6L13 6L17 2L41 2L45 6L45 12.5Z",
    "minivan":   "M2 12.5L3 8L7 8L15 2L43 2L45 4L45 12.5Z",
    "pickup":    "M2 12.5L3 6L13 6L17 2L26 2L26 8L45 8L45 12.5Z",
    "van":       "M2 12.5L2 6L5 6L9 1L45 1L45 12.5Z",
}

GLYPHS: dict[str, str] = {
    style: (f'<svg class="vglyph" viewBox="0 0 48 20" aria-hidden="true">'
            f'<path fill="currentColor" d="{d}{_WHEELS}"/></svg>')
    for style, d in _BODIES.items()
}


def _selfcheck() -> None:
    """Инварианты геометрии — пересчитываем утверждение, не глядя на картинку."""
    # земля: центр колеса + радиус == 18, из самой строки, не из комментария
    m = re.match(r"M\d+ (\d+)a(\d+) ", _WHEELS)
    cy, r = int(m.group(1)), int(m.group(2))
    assert cy + r == 18, "колесо не касается линии земли"
    pair = re.compile(r"[ML](-?[\d.]+) (-?[\d.]+)")
    for style, svg in GLYPHS.items():
        d = re.search(r' d="([^"]+)"', svg).group(1)
        assert len(d.encode("ascii")) <= 600, f"{style}: path > 600 байт"
        assert d.endswith(_WHEELS), f"{style}: колёса не канонические"
        for bad in ("evenodd", "stroke", "<text", "url("):
            assert bad not in svg, f"{style}: запрещённое '{bad}'"
        body = d[: -len(_WHEELS)]
        for xs, ys in pair.findall(body):
            x, y = float(xs), float(ys)
            assert 0 <= x <= 48 and 0 <= y <= 20, f"{style}: ({x},{y}) вне viewBox"


_selfcheck()

# Карта кузовов читается один раз при импорте. Нет файла — пустая карта:
# страницы рендерятся как сегодня, без глифов, сборка не падает.
try:
    _STYLES: dict[str, str] = json.loads(
        (ROOT / "data" / "body_styles.json").read_text(encoding="utf-8"))
except FileNotFoundError:
    _STYLES = {}


def body_style(make: str, model: str) -> str | None:
    """Стиль кузова для сырой пары MAKE|MODEL или None. Никогда не угадывает."""
    s = _STYLES.get(f"{make}|{model}")
    return s if s in GLYPHS else None


def glyph(make: str, model: str) -> str:
    """Готовый <svg> или пустая строка — вызывающий код ветвится по truthiness."""
    return GLYPHS.get(body_style(make, model) or "", "")
