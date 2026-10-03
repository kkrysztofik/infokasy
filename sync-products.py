#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Synchronizacja danych produktów: data/products-*.json  ->  bloki inline w index.html

Po co to:
  Strona zawsze najpierw próbuje wczytać pliki data/products-*.json przez fetch
  (działa na hostingu / serwerze HTTP). Gdy index.html otwierasz dwuklikiem
  z dysku (file://), przeglądarka blokuje fetch i strona używa KOPII INLINE
  wbudowanych w index.html.

  Ten skrypt przepisuje aktualną zawartość plików JSON do tych kopii inline,
  żeby tryb file:// też pokazywał najnowsze ceny i kategorie.

Kiedy uruchamiać:
  Po każdej edycji plików data/products-*.json — JEŚLI otwierasz stronę lokalnie
  (file://). Przy publikacji na hostingu (HTTP) nie jest wymagane.

Użycie:
  python sync-products.py
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
INDEX = ROOT / "index.html"

# id bloku inline w index.html  ->  plik z danymi
MAPPING = {
    "pd-datecs":  "data/products-datecs.json",
    "pd-posnet":  "data/products-posnet.json",
    "pd-novitus": "data/products-novitus.json",
    "pd-aclas":   "data/products-aclas.json",
    "pd-satis":   "data/products-satis.json",
}


def main():
    if not INDEX.exists():
        print(f"BŁĄD: nie znaleziono {INDEX}")
        sys.exit(1)

    html = INDEX.read_text(encoding="utf-8")
    changed = 0

    for block_id, rel_path in MAPPING.items():
        json_path = ROOT / rel_path
        if not json_path.exists():
            print(f"  pomijam {block_id}: brak pliku {rel_path}")
            continue

        # Walidacja + ładne formatowanie JSON
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            print(f"  BŁĄD JSON w {rel_path}: {e}")
            sys.exit(1)

        pretty = json.dumps(data, ensure_ascii=False, indent=2)

        # Podmień zawartość konkretnego bloku <script ... id="pd-...">...</script>
        pattern = re.compile(
            r'(<script type="application/json" id="'
            + re.escape(block_id)
            + r'">)(.*?)(</script>)',
            re.DOTALL,
        )

        if not pattern.search(html):
            print(f"  UWAGA: nie znaleziono bloku inline id=\"{block_id}\" w index.html")
            continue

        html = pattern.sub(
            lambda m: m.group(1) + "\n" + pretty + "\n  " + m.group(3),
            html,
            count=1,
        )
        changed += 1
        print(f"  zaktualizowano {block_id}  <-  {rel_path}")

    if changed:
        INDEX.write_text(html, encoding="utf-8")
        print(f"\nGotowe. Zaktualizowano {changed} blok(ów) w index.html.")
    else:
        print("\nNic nie zmieniono.")


if __name__ == "__main__":
    main()
