"""
Сборка SQLite из плоских файлов NHTSA. Детерминированный Python, без LLM — PLAYBOOK §5.

Создаёт data/mileagecurve.db с таблицами complaints, recalls, investigations.
Поколения подключаются отдельно (build_generations.py) — эта часть от них не зависит.

Запуск:  python pipeline/build_db.py [--limit N]
"""
from __future__ import annotations

import argparse
import sqlite3
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
DB = ROOT / "data" / "mileagecurve.db"

MILES_SANE_MAX = 500_000
YEAR_MIN, YEAR_MAX = 1990, 2027
# Длина сохраняемого фрагмента жалобы: хватает на цитату, не раздувает базу до 1,5 ГБ.
NARRATIVE_CHARS = 400

SCHEMA = """
PRAGMA journal_mode = OFF;
PRAGMA synchronous = OFF;

DROP TABLE IF EXISTS complaints;
CREATE TABLE complaints (
    cmplid      INTEGER PRIMARY KEY,
    odino       INTEGER,
    make        TEXT NOT NULL,
    model       TEXT NOT NULL,
    year        INTEGER NOT NULL,
    component   TEXT,          -- полная строка COMPDESC
    system      TEXT,          -- верхний уровень: часть до первого ':'
    date_filed  TEXT,          -- YYYY-MM-DD
    date_failed TEXT,
    miles       INTEGER,       -- пробег до отказа; NULL если не указан или невалиден
    crash       INTEGER,
    fire        INTEGER,
    injured     INTEGER,
    deaths      INTEGER,
    narrative   TEXT
);

DROP TABLE IF EXISTS recalls;
CREATE TABLE recalls (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign    TEXT NOT NULL,
    make        TEXT NOT NULL,
    model       TEXT NOT NULL,
    year        INTEGER NOT NULL,
    component   TEXT,
    mfr         TEXT,
    report_date TEXT,
    potaff      INTEGER,       -- затронуто машин ПО ВСЕЙ КАМПАНИИ, не по году. См. D-007.
    defect      TEXT,
    consequence TEXT,
    remedy      TEXT,
    do_not_drive INTEGER,
    park_outside INTEGER
);

DROP TABLE IF EXISTS meta;
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
"""

INDEXES = """
CREATE INDEX idx_c_mmy     ON complaints(make, model, year);
CREATE INDEX idx_c_miles   ON complaints(make, model, year, miles);
CREATE INDEX idx_c_system  ON complaints(system);
CREATE INDEX idx_r_mmy     ON recalls(make, model, year);
CREATE INDEX idx_r_camp    ON recalls(campaign);
"""


def norm_date(s: str) -> str | None:
    s = s.strip()
    if len(s) == 8 and s.isdigit():
        y, m, d = s[:4], s[4:6], s[6:8]
        if "1900" < y < "2100" and "01" <= m <= "12" and "01" <= d <= "31":
            return f"{y}-{m}-{d}"
    return None


def to_int(s: str) -> int | None:
    s = s.strip()
    if not s:
        return None
    try:
        return int(float(s))
    except ValueError:
        return None


def yn(s: str) -> int:
    return 1 if s.strip().upper() == "Y" else 0


def load_complaints(con: sqlite3.Connection, limit: int | None) -> int:
    src = RAW / "cmpl" / "FLAT_CMPL.txt"
    if not src.exists():
        raise SystemExit(f"нет файла: {src}")

    rows, kept, t0 = 0, 0, time.time()
    buf: list[tuple] = []
    cur = con.cursor()

    with open(src, "r", encoding="latin-1", errors="replace") as f:
        for line in f:
            rows += 1
            if limit and rows > limit:
                break
            p = line.rstrip("\n").split("\t")
            if len(p) < 51 or p[45].strip().upper() != "V":
                continue

            make, model, yr = p[3].strip().upper(), p[4].strip().upper(), p[5].strip()
            if not (make and model and yr.isdigit()):
                continue
            year = int(yr)
            if not (YEAR_MIN <= year <= YEAR_MAX):
                continue

            miles = to_int(p[17])
            if miles is not None and not (0 < miles <= MILES_SANE_MAX):
                miles = None

            comp = p[11].strip()
            buf.append((
                to_int(p[0]), to_int(p[1]), make, model, year,
                comp or None, comp.split(":")[0] if comp else None,
                norm_date(p[15]), norm_date(p[7]), miles,
                yn(p[6]), yn(p[8]), to_int(p[9]) or 0, to_int(p[10]) or 0,
                p[19].strip()[:NARRATIVE_CHARS] or None,
            ))
            kept += 1

            if len(buf) >= 50_000:
                cur.executemany("INSERT OR REPLACE INTO complaints VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", buf)
                buf.clear()
                print(f"  жалобы: {kept:,} загружено ({time.time() - t0:.0f} с)", flush=True)

    if buf:
        cur.executemany("INSERT OR REPLACE INTO complaints VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", buf)
    con.commit()
    print(f"  жалобы: {kept:,} из {rows:,} строк за {time.time() - t0:.0f} с")
    return kept


def load_recalls(con: sqlite3.Connection) -> int:
    src = RAW / "rcl" / "FLAT_RCL_POST_2010.txt"
    if not src.exists():
        print(f"  пропуск отзывов: нет {src}")
        return 0

    kept, t0 = 0, time.time()
    buf: list[tuple] = []
    cur = con.cursor()

    with open(src, "r", encoding="latin-1", errors="replace") as f:
        for line in f:
            p = line.rstrip("\n").split("\t")
            if len(p) < 29 or p[10].strip().upper() != "V":
                continue
            make, model, yr = p[2].strip().upper(), p[3].strip().upper(), p[4].strip()
            if not (make and model and yr.isdigit()):
                continue
            year = int(yr)
            if not (YEAR_MIN <= year <= YEAR_MAX):
                continue

            buf.append((
                p[1].strip(), make, model, year, p[6].strip() or None, p[14].strip() or None,
                norm_date(p[12]), to_int(p[11]),
                p[19].strip()[:600] or None, p[20].strip()[:600] or None, p[21].strip()[:600] or None,
                yn(p[27]), yn(p[28]),
            ))
            kept += 1
            if len(buf) >= 50_000:
                cur.executemany(
                    "INSERT INTO recalls (campaign,make,model,year,component,mfr,report_date,potaff,"
                    "defect,consequence,remedy,do_not_drive,park_outside) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", buf)
                buf.clear()

    if buf:
        cur.executemany(
            "INSERT INTO recalls (campaign,make,model,year,component,mfr,report_date,potaff,"
            "defect,consequence,remedy,do_not_drive,park_outside) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", buf)
    con.commit()
    print(f"  отзывы: {kept:,} строк за {time.time() - t0:.0f} с")
    return kept


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, help="ограничить число строк жалоб (для отладки)")
    args = ap.parse_args()

    DB.parent.mkdir(parents=True, exist_ok=True)
    if DB.exists():
        DB.unlink()

    con = sqlite3.connect(DB)
    con.executescript(SCHEMA)

    print("Загрузка...")
    n_c = load_complaints(con, args.limit)
    n_r = load_recalls(con)

    print("Индексы...")
    t0 = time.time()
    con.executescript(INDEXES)
    con.commit()
    print(f"  готово за {time.time() - t0:.0f} с")

    con.executemany("INSERT OR REPLACE INTO meta VALUES (?,?)", [
        ("built_utc", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())),
        ("complaints", str(n_c)),
        ("recalls", str(n_r)),
        ("source", "NHTSA ODI flat files, public domain"),
    ])
    con.commit()

    size = DB.stat().st_size / 1048576
    print(f"\nБаза: {DB}  ({size:.0f} МБ)")
    for q, label in [
        ("SELECT COUNT(*) FROM complaints", "жалоб"),
        ("SELECT COUNT(*) FROM complaints WHERE miles IS NOT NULL", "  из них с пробегом"),
        ("SELECT COUNT(*) FROM recalls", "отзывов"),
        ("SELECT COUNT(DISTINCT make || '|' || model) FROM complaints", "уникальных моделей"),
    ]:
        print(f"{label}: {con.execute(q).fetchone()[0]:,}")
    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
