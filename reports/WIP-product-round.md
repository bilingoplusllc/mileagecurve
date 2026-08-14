# WIP: продуктовый раунд — контрольная точка 2026-08-13

**Статус: работа ПРИОСТАНОВЛЕНА на середине, локальные правки НЕ закоммичены и НЕ выложены.**
Живой сайт в порядке (последний деплой полный). CI собирает только по пушу — пуша не было.
Следующий cron-запуск сборки только 2026-09-12, так что незакоммиченное состояние безопасно.

## Что сделано в этом раунде

1. **Продуктовый план готов** — `reports/` не содержит, полный текст в
   `C:\Users\Lenovo\AppData\Local\Temp\claude\D--BiLingoPlus\abb63f21-8b69-4942-be0b-5836d7c7b89c\tasks\wgskzbrhh.output`
   (скопировать в `reports/product-roadmap-2026-08.md` при возобновлении!).
   Итог: 4 видения → 3 судьи → план. Формула продукта: «единственный сайт, который по
   конкретному поколению и конкретному пробегу говорит, какие поломки обычно уже позади,
   а какие впереди — система за системой, с бесплатным лечением по каждому отзыву».

2. **analyze.py — СДЕЛАНО**: в запрос отзывов добавлено поле `consequence`
   («что может случиться») — заполнено на всех 217 256 строках, но раньше вообще
   не выбиралось. Ключ `"consequence"` теперь в словаре recalls.

3. **narrative.py — СДЕЛАНО**: добавлен `checklist_items(s, gen)` (чек-лист «перед
   покупкой»: VIN-проверка + тревожный пункт при do_not_drive, ранние системы
   (медиана ≤12k, count ≥50, топ-2), курируемые known_issues (топ-3), нейтральный
   указатель на разброс по годам (только если max ≥ 3×min; БЕЗ «years to avoid»),
   закрывающий пункт про осмотр). Раздел «What this means if you are buying one»
   УБРАН из full_analysis — его заменяет чек-лист. ВНИМАНИЕ: render.py ещё НЕ
   рендерит чек-лист, поэтому пересборка прямо сейчас потеряла бы покупательский
   раздел. Не собирать до завершения шага 4.

## Что осталось (план «на этой неделе» из роадмапа)

4. **render.py — раздел «Before you buy» (id="buy")**: после Figure 1 + карточки-вывода
   + note. H2: «Before you buy a 2010–2015 Prius: the 3-minute check». Подзаголовок:
   «Generated from N mileage-tagged complaints, N recall campaigns and N documented
   problem areas. Print this page — the checklist survives print.» Нумерованный список
   в .card из checklist_items(); тревожные пункты — с .alert. После списка — прозу
   guidance_narrative(s) (она осталась в narrative.py, вызывать напрямую).

5. **render.py — answer box (п.1.1 роадмапа)**: под dateline, in-flow копия .snap
   (класс .snap-top): Reports with mileage / **Median of reported failures** (ярлык
   обязателен именно такой — не «Median at failure») / Most-reported system (share%) /
   Recalls. Ниже две кнопки-ссылки: «Before-you-buy checklist ↓» (#buy) и «Check this
   VIN — NHTSA ↗». На 57 страницах с severe_advisories>0 — .alert-полоса НАД боксом:
   «A DO NOT DRIVE recall covers part of this generation — check the VIN before driving
   it home.» CSS: .snap-top скрывается ≥1180px (там рельс с тем же .snap).

6. **render.py — отзывы как <details> (п.1.2)**: вместо таблицы — список <details>
   (класс .rcl): summary = год(ы) · узел · первая фраза consequence (через
   names.sentence_case + truncate_words ~90); do_not_drive → атрибут open + .alert-бейдж.
   Тело: **The defect** / **What can happen** / **The free fix** (defect/consequence/
   remedy через sentence_case, это КАПС) + meta «NHTSA campaign X, reported Y. Text is
   NHTSA's own wording.» Лимит 25 остаётся. PII-проверка официального текста СДЕЛАНА:
   чисто (телефоны там — горячие линии производителей, их не отбрасывать).
   В рельс — карточка «Recall check: N campaigns... Enter your VIN at NHTSA ↗».

7. **Главная (вердикт роадмапа, шаг «эта неделя»)**: вынести .stats из .hero-say в
   отдельный элемент .hero (третьим ребёнком), чтобы на мобильном порядок стал
   H1 → поиск → цифры (сейчас поиск после цифр). Wide-сетка: .hero-say col1,
   .hero-find col2 row1/span2, .stats col1. Плейсхолдер поиска → «e.g. 2013 Escape».

8. **CSS** для всего выше: .snap-top, .btn-row (кнопки), ol.check (чек-лист),
   details.rcl (+summary маркер, .rcl-body), .rail-vin. Правила дома: без
   position:absolute, 360px без гориз. прокрутки, шрифты ≥12px.

9. **Пересборка + шлюзы + деплой + скриншоты** (Chrome connected: real Chrome
   вкладка tabId 1716060414). Проверить: чек-лист печатается (print CSS уже
   прячет nav/ads), answer box на 360px, details раскрываются, DND-страница
   (например ford-escape-2013-* или bmw m5/m6 2013) показывает тревогу.

10. **После деплоя**: обновить MEMORY.md проекта + REGISTRY.md ветки (продуктовый
    раунд), скопировать роадмап в reports/, обновить память
    (`web-properties-program.md`? нет — продуктовые уроки в MEMORY.md проекта).

## На месяц (НЕ начато, по роадмапу)

- 2.1 «Where your car sits» — секция пробега с 3 статическими якорями (60/90/120k)
  + JS-ввод одометра + маркер на Figure 2 (line.you через lx()).
- 2.2 /compare/ — ~120 страниц, data/rivalries.json (~30 пар), compare.py,
  system_strips_pair(). Слаги канонические по алфавиту; правило стабильности слагов.
- 2.3 «Cross-shopping this class?» — модуль соперников на страницах поколений
  (после 2.2). Заголовок НЕ «Shoppers also checked» (фальшивое соц. доказательство).
- Главная после 2.2: qpop «Most reported» → «Popular comparisons» (6 пар).

## Отвергнуто судьями (НЕ делать)

Сегмент-хабы /class/ (замаскированный рейтинг); системные страницы ×745;
таблица симптомов по подстрокам (misfire/backfire ловятся как fire — фабрикация);
550 сравнений; таблицы годов бок-о-бок на сравнениях; «prefer 2012+, 6x» и любые
«years to avoid»; сравнение долей crash/fire между машинами; «Shoppers also checked»;
/embed/-страницы; видимая дельта свежести.
