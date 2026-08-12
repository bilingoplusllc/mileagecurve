# Очистка карты поколений

> Вход: 100 моделей, 396 поколений

## 1. Дубликаты

Удалено дубликатов: **1** — CHEVROLET EQUINOX

## 2. Пропуски в производстве

Псевдо-поколений превращено в явные пропуски: **12**

## 3. Пересечения годов

Разрешено пересечений: **8**. Спорный год отдан новому поколению и помечен флагом `mixed_years` — он выносится на страницу.

- NISSAN ROGUE: 2014–2015 → отдан «2nd generation (T32)»
- CHEVROLET TRAVERSE: 2024 → отдан «3rd generation»
- JEEP GRAND CHEROKEE: 2021–2022 → отдан «5th generation (WL)»
- CHEVROLET SILVERADO 1500: 2007 → отдан «2nd generation (GMT900)»
- VOLKSWAGEN JETTA: 1999 → отдан «Mk4 (A4)»
- VOLKSWAGEN JETTA: 2005 → отдан «Mk5 (A5)»
- JEEP WRANGLER: 2018 → отдан «JL (5th generation)»
- HYUNDAI SANTA FE: 2019 → отдан «4th generation (TM)»

## 4. Чистка описаний дефектов

| Категория | Записей | Что сделано |
|---|---|---|
| Служебные (component = «n/a», «Data integrity»…) | 25 | перенесены в `build_notes`, из дефектов убраны |
| Помечены самим агентом как неготовые к публикации | 2 | **убраны**, вынесены на ручную проверку |
| Расплывчатые (короче 60 симв. или без механизма) | 50 | **убраны**, вынесены на ручную проверку |
| Опираются только на форумы | 0 | оставлены с меткой `source_strength: weak` |
| **Оставлено к публикации** | **960** | |

## 5. Итог

- моделей: **99**
- поколений: **380**
- дефектов к публикации: **960**
- оставшихся структурных проблем: **0**

### Требует внимания

- длинное поколение (>14 лет): JEEP CHEROKEE 1984–2001
- длинное поколение (>14 лет): NISSAN FRONTIER 2005–2021

## 6. На ручную проверку — убранные утверждения

Эти записи не публикуются. Сайт выходит под именем компании: недоказанные утверждения о дефектах автомобилей — юридический риск.

- CHEVROLET MALIBU 5th generation (nameplate revival): [расплывчато] Engine — 2.4L LD9 head gasket failure and elevated oil consumption.
- HONDA ODYSSEY 2nd generation (RL1): [расплывчато] Body — Power sliding door motor, cable and roller failures.
- SUBARU OUTBACK 3rd generation (BP): [расплывчато] Suspension — Wheel bearing and front control arm bushing wear.
- SUBARU OUTBACK 4th generation (BR): [расплывчато] Engine — EJ253 external head gasket seepage on the carryover engine.
- SUBARU OUTBACK 5th generation (BS): [расплывчато] Engine — FB25 oil consumption on early builds of this generation.
- CHEVROLET TRAVERSE 2nd generation: [расплывчато] Electrical — Infotainment and rear camera module faults on early builds.
- HONDA CR-V 2nd generation: [расплывчато] Airbags — Takata inflator recalls cover this generation.
- HONDA CR-V 3rd generation: [расплывчато] Airbags — Takata front inflator recalls cover the full generation.
- HONDA CR-V 4th generation: [расплывчато] Airbags — Takata inflator recalls cover the earlier model years.
- FORD EDGE 1st generation: [расплывчато] Infotainment — MyFord Touch freezing, reboots and unresponsive screen.
- TOYOTA COROLLA 9th generation (North American E130 body): [расплывчато] Airbags — Takata front airbag inflator recalls cover this generation.
- TOYOTA COROLLA 10th generation: [расплывчато] Airbags — Takata inflator recalls cover this generation.
- TOYOTA COROLLA 11th generation: [расплывчато] Airbags — Takata inflator recalls cover the early model years.
- HYUNDAI ELANTRA 3rd generation: [расплывчато] Engine — Interference-design timing belt; failure destroys valves.
- HYUNDAI ELANTRA 4th generation: [расплывчато] Body — Door lock actuator and window regulator failures.
- GMC ACADIA 1st generation: [расплывчато] Airbags — Takata inflator recall exposure across the generation.
- JEEP GRAND CHEROKEE 3rd generation (WK): [расплывчато] Electrical — Widespread window regulator, door module and instrument-cluster complaints; intermittent no-start and warning-
- NISSAN ALTIMA 1st generation (U13): [расплывчато] Body — Strut tower and rear subframe corrosion in salt-belt cars.
- TOYOTA RAV4 1st generation (XA10): [расплывчато] Body — Rear subframe and rocker corrosion in salt-belt cars.
- NISSAN SENTRA 4th generation (B14): [расплывчато] Body — Strut tower and rear rail corrosion in salt-belt use.
- DODGE RAM 1500 2nd generation (BR/BE): [расплывчато] HVAC — Heater core failures requiring full dash removal.
- HYUNDAI TUCSON 4th generation (NX4): [неготово] Brakes / ABS (HECU) — The ABS module electrical-short fire risk that drove the 2019-2021 park-outside recalls continues to be a live
- HYUNDAI SONATA 4th generation (EF): [расплывчато] Transmission — F4A4x 4-speed automatic solenoid and clutch pack failures.
- HYUNDAI SONATA 6th generation (YF): [расплывчато] Glazing — Panoramic sunroof glass spontaneously shattering.
- DODGE DURANGO 1st generation (DN): [расплывчато] Body structure — Rear frame rail and liftgate corrosion in salt-belt states.
- DODGE GRAND CARAVAN 3rd generation (NS): [расплывчато] Brakes — Bendix ABS system faults with extended pedal travel.
- DODGE GRAND CARAVAN 4th generation (RS): [расплывчато] Suspension — Lower ball joint and tie rod end wear.
- DODGE GRAND CARAVAN 4th generation (RS): [расплывчато] Engine — 3.3L/3.8L oil sludging and head gasket leaks.
- DODGE GRAND CARAVAN 5th generation (RT): [расплывчато] Transmission — 62TE torque converter shudder and solenoid faults.
- CHEVROLET EQUINOX 1st generation: [расплывчато] Steering — Power steering assist loss.
- CHEVROLET EQUINOX 2nd generation: [расплывчато] Engine — 3.6L LFX timing chain wear.
- CHEVROLET EQUINOX 3rd generation: [расплывчато] Fuel system — Low-pressure fuel pump failures causing stalling.
- KIA SORENTO 1st generation (BL): [расплывчато] Body structure — Liftgate and rear frame corrosion in road-salt states.
- TOYOTA HIGHLANDER 1st generation (XU20): [расплывчато] Emissions — ECM and oxygen sensor faults triggering emissions failures.
- TOYOTA HIGHLANDER 2nd generation (XU40): [расплывчато] Engine — 2.7L 1AR-FE four-cylinder oil consumption.
- TOYOTA HIGHLANDER 2nd generation (XU40): [расплывчато] Airbags — Takata inflator recalls apply across these model years.
- KIA SOUL 2nd generation (PS): [расплывчато] Transmission — 7-speed dual-clutch shudder and hesitation on turbo models.
- KIA SOUL 2nd generation (PS): [расплывчато] Anti-theft — Non-immobilizer trims remain highly theft-prone.
- VOLKSWAGEN JETTA Mk3 (A3): [расплывчато] Transmission — 01M 4-speed automatic failures.
- VOLKSWAGEN JETTA Mk4 (A4): [расплывчато] Body / windows — Window regulator failures, carried over and still endemic.
- VOLKSWAGEN JETTA Mk4 (A4): [расплывчато] Transmission — 01M 4-speed automatic failures.
- VOLKSWAGEN JETTA Mk4 (A4): [расплывчато] Engine — PD TDI camshaft and cam follower wear on the BEW engine.
- BMW 3 SERIES E36 (3rd generation): [расплывчато] Body / windows — Window regulator failures.
- BMW 3 SERIES E90/E91/E92/E93 (5th generation): [расплывчато] Engine — S65 V8 connecting rod bearing wear (M3 only).
- BMW 3 SERIES F30/F31/F34 (6th generation): [расплывчато] Cooling system — Electric water pump failure.
- HONDA PILOT 2nd generation: [расплывчато] Airbags — Takata inflator recalls covering this generation.
- MERCEDES-BENZ C-CLASS 3rd generation (W204): [расплывчато] Body — Panoramic sunroof leaks and shade mechanism failures.
- AUDI A4 2nd generation (B6, Typ 8E): [расплывчато] Ignition — coil packs — Continued 1.8T coil pack failures causing misfires.
- PONTIAC GRAND AM 5th generation: [расплывчато] Body - windows — Front power window regulator cable failure.
- OLDSMOBILE ALERO Only generation: [расплывчато] Engine - cylinder head — 2.4L LD9 head gasket failure and coolant consumption.
- OLDSMOBILE ALERO Only generation: [расплывчато] Body - windows — Power window regulator cable breakage.
- KIA SPORTAGE 4th generation (QL): [неготово] Brakes - electrical — Hydraulic Electronic Control Unit (ABS module) brake fluid leak causing an electrical short and engine-compart
