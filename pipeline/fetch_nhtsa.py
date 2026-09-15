"""
Скачивание открытых данных NHTSA. Детерминированный Python, без LLM — правило PLAYBOOK §5.

Источники (все — общественное достояние правительства США, коммерческое использование разрешено):
  FLAT_CMPL.zip  — жалобы владельцев (ODI Complaints). Поле MILES = пробег до отказа. Ядро сайта.
  FLAT_TSBS.zip  — сервисные бюллетени производителей.
  FLAT_RCL.zip   — отзывные кампании.
  FLAT_INV.zip   — расследования ODI.

Запуск:  python pipeline/fetch_nhtsa.py [--only cmpl]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

BASE = "https://static.nhtsa.gov/odi/ffdd"
DATA = Path(__file__).resolve().parent.parent / "data"

SOURCES = {
    # Жалобы владельцев. Поле 18 MILES = пробег до отказа. Ядро сайта.
    "cmpl": f"{BASE}/cmpl/FLAT_CMPL.zip",
    # Отзывные кампании с 2010 г. Одна строка на (кампания, марка, модель, год).
    # Поле POTAFF = число потенциально затронутых машин — кандидат в знаменатель.
    "rcl": f"{BASE}/rcl/FLAT_RCL_POST_2010.zip",
    # Расследования ODI.
    "inv": f"{BASE}/inv/FLAT_INV.zip",
}

UA = {"User-Agent": "Mozilla/5.0 (compatible; BiLingoPlus-research/1.0)"}


def human(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def download(key: str, url: str, dest_dir: Path) -> dict | None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{key}.zip"
    print(f"[{key}] {url}")

    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=120) as resp:
            total = resp.headers.get("Content-Length")
            total = int(total) if total else None
            h = hashlib.sha256()
            got = 0
            t0 = time.time()
            last = 0.0
            with open(dest, "wb") as f:
                while True:
                    chunk = resp.read(1 << 20)
                    if not chunk:
                        break
                    f.write(chunk)
                    h.update(chunk)
                    got += len(chunk)
                    now = time.time()
                    if now - last > 3:
                        last = now
                        pct = f" {got / total * 100:5.1f}%" if total else ""
                        print(f"[{key}]{pct} {human(got)} за {now - t0:.0f} с", flush=True)
    except Exception as e:  # noqa: BLE001 — источник внешний, падать нельзя
        print(f"[{key}] ОШИБКА: {type(e).__name__}: {e}", file=sys.stderr)
        return None

    print(f"[{key}] готово: {human(got)} за {time.time() - t0:.0f} с")

    # Распаковка
    members = []
    try:
        with zipfile.ZipFile(dest) as z:
            for info in z.infolist():
                members.append({"name": info.filename, "size": info.file_size})
            z.extractall(dest_dir)
    except zipfile.BadZipFile:
        print(f"[{key}] ОШИБКА: битый архив", file=sys.stderr)
        return None

    for m in members:
        print(f"[{key}]   -> {m['name']}  {human(m['size'])}")

    return {
        "key": key,
        "url": url,
        "bytes": got,
        "sha256": h.hexdigest(),
        "fetched_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "members": members,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", choices=list(SOURCES), help="скачать только указанные наборы")
    args = ap.parse_args()

    keys = args.only or list(SOURCES)
    raw = DATA / "raw"
    manifest_path = DATA / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    prev_manifest = dict(manifest)   # нужен, чтобы не закрепить усохший объём как норму

    ok = 0
    shrink = []            # наборы, чей объём рухнул относительно прошлого снимка
    for k in keys:
        info = download(k, SOURCES[k], raw / k)
        if info:
            # Сравнение с прошлым снимком — правило PLAYBOOK §6:
            # отклонение объёма >±8% означает «остановиться и разобраться», а не публиковать.
            prev = manifest.get(k)
            if prev and prev.get("bytes"):
                delta = (info["bytes"] - prev["bytes"]) / prev["bytes"]
                flag = "  ⚠️ ОТКЛОНЕНИЕ >8%" if abs(delta) > 0.08 else ""
                print(f"[{k}] изменение объёма к прошлому снимку: {delta:+.1%}{flag}")
                info["delta_vs_prev"] = round(delta, 4)
                # Правило выше было написано, но не исполнялось: код печатал флаг и шёл дальше.
                # 2026-09-12 NHTSA отдал FLAT_CMPL.zip, усохший на 99.1% (1.5 ГБ -> 15.5 МБ).
                # Загрузка «удалась», база собралась почти пустой (пробег остался у ОДНОЙ жалобы
                # из 42 529), и сборку остановил только гейт «мало страниц» в самом конце — с
                # сообщением про страницы, а не про данные. Усыхание источника недвусмысленно:
                # такие корпуса не теряют пятую часть объёма законно. Рост не трогаем — новый
                # месяц данных законно прибавляет объём.
                if delta < -0.20:
                    shrink.append((k, prev["bytes"], info["bytes"], delta))
            manifest[k] = info
            ok += 1

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    print(f"\nМанифест: {manifest_path}")
    print(f"Успешно: {ok}/{len(keys)}")

    # Останавливаемся ЗДЕСЬ, а не через три шага на счётчике страниц: сообщение должно
    # называть настоящую причину. Усохший объём в манифест НЕ записываем — иначе следующий
    # запуск сравнит новый файл с усохшим снимком, увидит «рост» и промолчит.
    if shrink:
        for k, was, now, delta in shrink:
            # Три отдельных print вместо одной строки с \n: при записи этого файла escape
            # трижды превращался в настоящий перевод строки и рвал f-строку. Проще не рисковать.
            print("", file=sys.stderr)
            print(f"[{k}] ИСТОЧНИК УСОХ: было {human(was)}, стало {human(now)} ({delta:+.1%}).", file=sys.stderr)
            print("      Данные на стороне NHTSA неполные — публиковать нечего, сборка остановлена.", file=sys.stderr)
            print("      Это не наша поломка: перезапустить, когда файл на их стороне восстановят.", file=sys.stderr)
            if prev_manifest.get(k):
                manifest[k] = prev_manifest[k]
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
        return 2

    return 0 if ok == len(keys) else 1


if __name__ == "__main__":
    raise SystemExit(main())
