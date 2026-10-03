#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Kontrola i aktualizacja cen u producentów:  strony producentów  ->  data/products-*.json  ->  index.html

Co robi:
  1. Pobiera aktualne strony producentów (Datecs, Posnet, Novitus, Aclas, SATIS)
     wskazane w polach sourceUrl / sourceUrls w plikach data/products-*.json.
  2. Odczytuje z nich ceny i dopasowuje je do wariantów w katalogu.
  3. Jeśli cena się zmieniła - aktualizuje wariant, cenę "od" produktu i etykiety.
     Przed zapisem robi kopię zapasową pliku JSON w data/kopie/.
  4. Przepisuje dane do bloków inline w index.html (wywołuje sync-products.py).
  5. Zapisuje raport HTML w katalogu raporty/.

Użycie:
  python aktualizuj-ceny.py              # sprawdź i zaktualizuj
  python aktualizuj-ceny.py --sprawdz    # tylko sprawdź i zrób raport, nic nie zmieniaj
  python aktualizuj-ceny.py --akceptuj-duze   # zastosuj też zmiany większe niż PROG_DUZEJ_ZMIANY

Wymaga tylko standardowej biblioteki Pythona (3.8+).
"""

import argparse
import html
import importlib.util
import json
import re
import shutil
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
KOPIE = DATA / "kopie"
RAPORTY = ROOT / "raporty"

PLIKI = [
    "products-datecs.json",
    "products-posnet.json",
    "products-novitus.json",
    "products-aclas.json",
    "products-satis.json",
]

# Różnice do tej kwoty (zł) traktujemy jako zaokrąglenie przy imporcie - nie zmieniamy ceny.
TOLERANCJA_ZL = 1.5
# Zmiany większe niż ten procent nie są stosowane automatycznie (chyba że --akceptuj-duze).
PROG_DUZEJ_ZMIANY = 35.0

# Ręczne dopasowania, gdy nazwa w katalogu różni się od nazwy u producenta:
# id produktu -> nazwa produktu na stronie producenta
ALIASY = {
    "posnet-mobile2-online": "MOBILE2",
    "point-2": 'POINT - mechanizm drukujący 2"',
    "point-3": 'POINT - mechanizm drukujący 3"',
}

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"
)


# ───────────────────────── narzędzia ─────────────────────────

def norm(s):
    """Nazwa do porównań: bez encji/tagów, wielkie litery, pojedyncze spacje, ujednolicone cudzysłowy."""
    s = html.unescape(re.sub(r"<[^>]+>", " ", s or ""))
    s = s.replace(" ", " ").replace("”", '"').replace("“", '"').replace("″", '"')
    return re.sub(r"\s+", " ", s).strip().upper()


def bez_spacji(s):
    return re.sub(r"\s+", "", norm(s))


def parse_cena(tekst):
    """'1 349.00 pln', '3 090,00 zł', '1449 zł + 23% VAT', '584.25' -> float"""
    t = html.unescape(tekst).replace(" ", " ")
    m = re.search(r"(\d[\d ]*(?:[.,]\d{1,2})?)\s*(?:zł|pln)", t, re.I) or \
        re.search(r"(\d[\d ]*(?:[.,]\d{1,2})?)", t)
    if not m:
        return None
    liczba = m.group(1).replace(" ", "").replace(",", ".")
    try:
        return float(liczba)
    except ValueError:
        return None


def fmt_cena(v):
    """1349 -> '1 349', 584.25 -> '584,25'"""
    if abs(v - round(v)) < 0.005:
        return f"{int(round(v)):,}".replace(",", " ")
    calk, ulam = f"{v:.2f}".split(".")
    return f"{int(calk):,}".replace(",", " ") + "," + ulam


def jako_liczba(v):
    return int(round(v)) if abs(v - round(v)) < 0.005 else round(v, 2)


def pobierz(url, proby=3):
    ostatni = None
    for i in range(proby):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": USER_AGENT,
                "Accept-Language": "pl-PL,pl;q=0.9",
            })
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode("utf-8", errors="replace")
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            ostatni = e
            time.sleep(2 * (i + 1))
    raise RuntimeError(f"nie udało się pobrać ({ostatni})")


def tekst(fragment):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()


# ───────────────────────── parsery stron producentów ─────────────────────────
# Każdy parser zwraca listę pozycji: {"nazwa": str, "cena": float, "url": str|None}

def parser_datecs(src, url):
    poz = []
    # Tabela wariantów: <tr><td>WP-25 LAN</td><td><strong>1349,00 zł</strong></td></tr>
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", src, re.S | re.I):
        komorki = [tekst(td) for td in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S | re.I)]
        if len(komorki) == 2 and komorki[0] and re.search(r"\d.*(zł|pln)", komorki[1], re.I):
            c = parse_cena(komorki[1])
            if c:
                poz.append({"nazwa": komorki[0], "cena": c, "url": url})
    # Cena podstawowa: "Wersja podstawowa<meta itemprop="price" content="1490"/>"
    m = re.search(r'([^<>]{1,60})<meta itemprop="priceCurrency"[^>]*>\s*<meta itemprop="price" content="([\d.]+)"', src)
    if m:
        poz.append({"nazwa": m.group(1).strip(), "cena": float(m.group(2)), "url": url, "podstawowa": True})
    return poz


def parser_posnet(src, url):
    poz = []
    for blok in re.findall(r'<div class="product_cat_item">(.*?)<a class="compare', src, re.S):
        n = re.search(r'class="product_cat_title">(.*?)</div>', blok, re.S)
        c = re.search(r'class="product_cat_price">(.*?)</div>', blok, re.S)
        h = re.search(r'href="([^"]+)"', blok)
        if n and c and parse_cena(c.group(1)):
            poz.append({
                "nazwa": tekst(n.group(1)),
                "cena": parse_cena(c.group(1)),
                "url": "https://www.posnet.com.pl" + h.group(1) if h else url,
            })
    return poz


def parser_novitus(src, url):
    poz = []
    for blok in re.split(r'<div class="product">', src)[1:]:
        n = re.search(r'class="product__content-title">\s*<a href="([^"]+)">(.*?)</a>', blok, re.S)
        c = re.search(r'class="product__content-price">(.*?)</p>', blok, re.S)
        if n and c and parse_cena(c.group(1)):
            href = n.group(1)
            poz.append({
                "nazwa": tekst(n.group(2)),
                "cena": parse_cena(c.group(1)),
                "url": href if href.startswith("http") else "https://novitus.pl" + href,
            })
    return poz


def parser_aclas(src, url):
    poz = []
    for blok in re.findall(r'<a class="single-product-listing" href="([^"]+)"(.*?)</a>', src, re.S):
        href, wnetrze = blok
        n = re.search(r'class="spl-title">(.*?)</h3>', wnetrze, re.S)
        c = re.search(r'class="spl-price">(.*?)</aside>', wnetrze, re.S)
        if n and c and parse_cena(c.group(1)):
            poz.append({"nazwa": tekst(n.group(1)), "cena": parse_cena(c.group(1)), "url": href})
    # Strona pojedynczego produktu (gdy sourceUrl wskazuje na produkt)
    if not poz:
        m = re.search(r'class="base-price">(.*?)</span>', src, re.S) or \
            re.search(r"Cena sugerowana:?\s*(?:<[^>]+>\s*)*([\d\s.,]+\s*zł)", src)
        t = re.search(r"<h1[^>]*>(.*?)</h1>", src, re.S)
        if m and parse_cena(m.group(1)):
            poz.append({"nazwa": tekst(t.group(1)) if t else "", "cena": parse_cena(m.group(1)),
                        "url": url, "podstawowa": True})
    return poz


def parser_satis(src, url):
    # PrestaShop: cena brutto aktualnie wybranej kombinacji
    m = re.search(r'class="current-price-value"\s+content="([\d.]+)"', src) or \
        re.search(r'property="product:price:amount"\s+content="([\d.]+)"', src)
    if not m:
        return []
    t = re.search(r"<h1[^>]*>(.*?)</h1>", src, re.S)
    netto = re.search(r'sat-net-price">\s*([^<]+)', src)
    return [{
        "nazwa": tekst(t.group(1)) if t else "",
        "cena": float(m.group(1)),
        "url": url,
        "podstawowa": True,
        "netto": parse_cena(netto.group(1)) if netto else None,
    }]


def wybierz_parser(url):
    if "datecs-polska.pl" in url:
        return parser_datecs
    if "posnet.com.pl" in url:
        return parser_posnet
    if "novitus.pl" in url:
        return parser_novitus
    if "aclas-polska.pl" in url:
        return parser_aclas
    if "satispolska.pl" in url:
        return parser_satis
    return None


# ───────────────────────── model katalogu ─────────────────────────

def cena_wariantu(v):
    return v.get("price", v.get("priceNet"))


def ustaw_cene_wariantu(v, cena, typ, dzis):
    pole = "price" if "price" in v else "priceNet"
    v[pole] = jako_liczba(cena)
    etykieta = f"{fmt_cena(cena)} zł {typ}"
    if "priceLabel" in v:
        v["priceLabel"] = etykieta
    if "displayPrice" in v:
        v["displayPrice"] = etykieta
    if "dateScraped" in v:
        v["dateScraped"] = dzis


def przelicz_produkt(p, dzis):
    ceny = [cena_wariantu(v) for v in p.get("variants", [])
            if v.get("active") is not False and cena_wariantu(v)]
    if not ceny:
        return
    od = min(ceny)
    typ = p.get("priceType", "netto")
    pole = "priceFrom" if "priceFrom" in p else "priceFromNet"
    p[pole] = jako_liczba(od)
    etykieta = f"od {fmt_cena(od)} zł {typ}"
    if "priceLabel" in p:
        p["priceLabel"] = etykieta
    if "displayPrice" in p:
        p["displayPrice"] = etykieta
    for pole_daty in ("scrapedAt", "dateScraped"):
        if pole_daty in p:
            p[pole_daty] = dzis


def nazwa_wariantu(v):
    return v.get("version") or v.get("name") or ""


def dopasuj(p, v, pozycje, url_strony, ile_wariantow_na_stronie):
    """Zwraca (pozycja, sposób) albo (None, powód)."""
    if not pozycje:
        return None, "brak cen na stronie"
    model = p.get("model") or p.get("name") or ""
    wersja = nazwa_wariantu(v)
    jedyny = len(p.get("variants", [])) == 1

    def jeden(lista, sposob):
        unik = {(x["nazwa"], x["cena"], x["url"]): x for x in lista}
        if len(unik) == 1:
            return next(iter(unik.values())), sposob
        return None, None

    # 1. Wariant ma własny adres produktu, a strona listy zawiera link do niego
    vurl = (v.get("sourceUrl") or "").rstrip("/")
    if vurl and vurl != url_strony.rstrip("/"):
        x, s = jeden([x for x in pozycje if (x["url"] or "").rstrip("/") == vurl], "adres produktu")
        if x:
            return x, s
    # 2. Alias ręczny
    if p["id"] in ALIASY and jedyny:
        x, s = jeden([x for x in pozycje if norm(x["nazwa"]) == norm(ALIASY[p["id"]])], "alias")
        if x:
            return x, s
    # 3. Strona pojedynczego produktu - jedna cena na stronie
    if len(pozycje) == 1 and pozycje[0].get("podstawowa") and ile_wariantow_na_stronie == 1:
        return pozycje[0], "strona produktu"
    # 4. Dokładna nazwa wariantu / modelu
    for kandydat, sposob in ((wersja, "nazwa wariantu"), (model if jedyny else "", "nazwa modelu")):
        if not kandydat:
            continue
        x, s = jeden([x for x in pozycje if norm(x["nazwa"]) == norm(kandydat)], sposob)
        if x:
            return x, s
        x, s = jeden([x for x in pozycje if bez_spacji(x["nazwa"]) == bez_spacji(kandydat)], sposob)
        if x:
            return x, s
    # 5. Identyfikator produktu = końcówka adresu u producenta (np. aclas .../kasa-gastronomiczna-p9/)
    if jedyny:
        x, s = jeden([x for x in pozycje if (x["url"] or "").rstrip("/").rsplit("/", 1)[-1] == p["id"]],
                     "adres produktu")
        if x:
            return x, s
    # 6. Rodzina modelu + nazwa kończy się wersją (Aclas: "Kasa fiskalna ACLAS Kobra_ON LAN + WIFI")
    rodzina = norm(model).split()[-1] if model else ""
    if rodzina and wersja:
        x, s = jeden([x for x in pozycje
                      if rodzina in norm(x["nazwa"]) and norm(x["nazwa"]).endswith(" " + norm(wersja))],
                     "rodzina + wersja")
        if x:
            return x, s
    # 7. Jedyna cena podstawowa na stronie produktu
    podst = [x for x in pozycje if x.get("podstawowa")]
    if jedyny and len(podst) == 1 and norm(wersja) in ("WERSJA PODSTAWOWA", "STANDARD"):
        return podst[0], "cena podstawowa"
    return None, "nie znaleziono pozycji o tej nazwie"


# ───────────────────────── raport ─────────────────────────

def zapisz_raport(wyniki, czas, tryb):
    RAPORTY.mkdir(exist_ok=True)
    plik = RAPORTY / f"raport-cen_{czas:%Y-%m-%d_%H%M%S}.html"
    e = html.escape

    zmiany = [w for w in wyniki["warianty"] if w["status"] in ("zmieniono", "zmiana-niezastosowana")]
    bez_zmian = [w for w in wyniki["warianty"] if w["status"] == "bez-zmian"]
    zaokr = [w for w in wyniki["warianty"] if w["status"] == "zaokraglenie"]
    brak = [w for w in wyniki["warianty"] if w["status"] == "nie-znaleziono"]

    def wiersz_zmiany(w):
        roznica = w["nowa"] - w["stara"]
        proc = roznica / w["stara"] * 100 if w["stara"] else 0
        kl = "up" if roznica > 0 else "down"
        status = "zaktualizowano" if w["status"] == "zmieniono" else \
            ("do weryfikacji – nie zastosowano" if not wyniki["tylko_sprawdz"] else "wykryto")
        return (f"<tr><td>{e(w['producent'])}</td><td>{e(w['produkt'])}</td><td>{e(w['wariant'])}</td>"
                f"<td class=num>{fmt_cena(w['stara'])} zł</td><td class=num><b>{fmt_cena(w['nowa'])} zł</b></td>"
                f"<td class='num {kl}'>{'+' if roznica > 0 else ''}{fmt_cena(roznica) if roznica >= 0 else '-' + fmt_cena(-roznica)} zł"
                f" ({proc:+.1f}%)</td><td>{e(w['typ'])}</td><td>{e(status)}</td>"
                f"<td><a href='{e(w['url'])}' target=_blank>strona</a></td></tr>")

    def wiersz_prosty(w, uwaga=""):
        cena = f"{fmt_cena(w['stara'])} zł" if w.get("stara") is not None else ""
        nowa = f" → {fmt_cena(w['nowa'])} zł" if w.get("nowa") is not None and w["status"] == "zaokraglenie" else ""
        return (f"<tr><td>{e(w['producent'])}</td><td>{e(w['produkt'])}</td><td>{e(w['wariant'])}</td>"
                f"<td class=num>{cena}{nowa}</td><td>{e(uwaga or w.get('uwaga', ''))}</td>"
                f"<td><a href='{e(w['url'])}' target=_blank>strona</a></td></tr>")

    tab_zmiany = "".join(wiersz_zmiany(w) for w in zmiany) or \
        "<tr><td colspan=9 class=empty>Brak zmian cen u producentów.</td></tr>"
    tab_brak = "".join(wiersz_prosty(w) for w in brak)
    tab_zaokr = "".join(wiersz_prosty(w, "różnica w granicach tolerancji – nie zmieniono") for w in zaokr)
    tab_ok = "".join(wiersz_prosty(w, w.get("sposob", "")) for w in bez_zmian)
    tab_bledy = "".join(f"<tr><td>{e(u)}</td><td>{e(b)}</td></tr>" for u, b in wyniki["bledy"])
    tab_nowe = "".join(
        f"<tr><td>{e(x['producent'])}</td><td>{e(x['nazwa'])}</td><td class=num>{fmt_cena(x['cena'])} zł</td>"
        f"<td><a href='{e(x['url'] or '')}' target=_blank>strona</a></td></tr>" for x in wyniki["nowe"])

    def sekcja(tytul, naglowki, wiersze, otwarta=False):
        if not wiersze:
            return ""
        th = "".join(f"<th>{h}</th>" for h in naglowki)
        return (f"<details{' open' if otwarta else ''}><summary>{tytul}</summary>"
                f"<table><thead><tr>{th}</tr></thead><tbody>{wiersze}</tbody></table></details>")

    pliki = "".join(f"<li>{e(p)}</li>" for p in wyniki["zapisane"]) or "<li>żaden – brak zmian lub tryb sprawdzania</li>"

    doc = f"""<!doctype html>
<html lang="pl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Raport cen {czas:%Y-%m-%d %H:%M}</title>
<style>
:root{{--bg:#f6f7f9;--card:#fff;--fg:#1d2330;--muted:#667085;--line:#e4e7ec;--up:#b42318;--down:#067647;--accent:#1d4ed8}}
@media (prefers-color-scheme:dark){{:root{{--bg:#11141a;--card:#1a1f27;--fg:#e6e9ef;--muted:#98a2b3;--line:#2b323d;--up:#f97066;--down:#47cd89;--accent:#7aa2ff}}}}
body{{margin:0;background:var(--bg);color:var(--fg);font:14px/1.5 system-ui,Segoe UI,sans-serif}}
main{{max-width:1200px;margin:0 auto;padding:24px 16px}}
h1{{font-size:22px;margin:0 0 4px}} .muted{{color:var(--muted)}}
.stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:20px 0}}
.stat{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 14px}}
.stat b{{display:block;font-size:24px}}
h2{{font-size:17px;margin:28px 0 8px}}
.wrap{{overflow-x:auto;background:var(--card);border:1px solid var(--line);border-radius:10px}}
table{{width:100%;border-collapse:collapse}} th,td{{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);vertical-align:top}}
th{{font-size:12px;text-transform:uppercase;letter-spacing:.03em;color:var(--muted)}}
.num{{text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}}
.up{{color:var(--up)}} .down{{color:var(--down)}} .empty{{text-align:center;color:var(--muted);padding:20px}}
details{{background:var(--card);border:1px solid var(--line);border-radius:10px;margin:12px 0;overflow-x:auto}}
summary{{cursor:pointer;padding:10px 14px;font-weight:600}}
a{{color:var(--accent)}}
</style></head><body><main>
<h1>Raport kontroli cen u producentów</h1>
<div class="muted">{czas:%d.%m.%Y, godz. %H:%M} · tryb: {e(tryb)}</div>
<div class="stats">
  <div class="stat"><b>{wyniki['sprawdzone']}</b>sprawdzonych wariantów</div>
  <div class="stat"><b>{len([w for w in zmiany if w['status'] == 'zmieniono'])}</b>zaktualizowanych cen</div>
  <div class="stat"><b>{len([w for w in zmiany if w['status'] != 'zmieniono'])}</b>zmian niezastosowanych</div>
  <div class="stat"><b>{len(bez_zmian) + len(zaokr)}</b>bez zmian</div>
  <div class="stat"><b>{len(brak)}</b>nie znaleziono</div>
  <div class="stat"><b>{len(wyniki['bledy'])}</b>błędów pobierania</div>
</div>
<h2>Zmiany cen</h2>
<div class="wrap"><table><thead><tr><th>Producent</th><th>Produkt</th><th>Wariant</th><th class=num>Było</th>
<th class=num>Jest</th><th class=num>Różnica</th><th>Typ</th><th>Status</th><th>Źródło</th></tr></thead>
<tbody>{tab_zmiany}</tbody></table></div>
<h2>Zapisane pliki</h2><ul>{pliki}</ul>
{sekcja("Błędy pobierania stron", ["Adres", "Błąd"], tab_bledy, True)}
{sekcja(f"Nie znaleziono u producenta ({len(brak)}) – sprawdź ręcznie, produkt mógł zniknąć lub zmienić nazwę",
        ["Producent", "Produkt", "Wariant", "Cena w katalogu", "Powód", "Źródło"], tab_brak, True)}
{sekcja(f"Różnice w granicach tolerancji ±{fmt_cena(TOLERANCJA_ZL)} zł ({len(zaokr)})",
        ["Producent", "Produkt", "Wariant", "Cena", "Uwaga", "Źródło"], tab_zaokr)}
{sekcja(f"Ceny bez zmian ({len(bez_zmian)})", ["Producent", "Produkt", "Wariant", "Cena", "Dopasowanie", "Źródło"], tab_ok)}
{sekcja(f"Produkty u producenta, których nie ma w katalogu ({len(wyniki['nowe'])})",
        ["Producent", "Nazwa u producenta", "Cena", "Źródło"], tab_nowe)}
</main></body></html>"""
    plik.write_text(doc, encoding="utf-8")
    return plik


# ───────────────────────── główna logika ─────────────────────────

def uruchom_sync():
    skrypt = ROOT / "sync-products.py"
    if not skrypt.exists():
        print("  UWAGA: brak sync-products.py – index.html nie został zaktualizowany")
        return
    spec = importlib.util.spec_from_file_location("sync_products", skrypt)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.main()


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    ap = argparse.ArgumentParser(description="Kontrola i aktualizacja cen u producentów")
    ap.add_argument("--sprawdz", action="store_true", help="tylko sprawdź i zrób raport, bez zmian w plikach")
    ap.add_argument("--akceptuj-duze", action="store_true",
                    help=f"stosuj też zmiany większe niż {PROG_DUZEJ_ZMIANY:.0f}%%")
    args = ap.parse_args()

    czas = datetime.now()
    dzis = czas.strftime("%Y-%m-%d")
    tryb = "tylko sprawdzanie" if args.sprawdz else "sprawdzanie i aktualizacja"
    print(f"Kontrola cen u producentów – {czas:%Y-%m-%d %H:%M} ({tryb})\n")

    wyniki = {"warianty": [], "bledy": [], "nowe": [], "zapisane": [], "sprawdzone": 0,
              "tylko_sprawdz": args.sprawdz}
    cache = {}          # url -> lista pozycji lub None
    uzyte = set()       # (url strony, nazwa) dopasowanych pozycji
    uzyte_url = set()   # adresy produktów już sprawdzonych

    def strona(url):
        if url not in cache:
            parser = wybierz_parser(url)
            if not parser:
                wyniki["bledy"].append((url, "nieznany producent – brak parsera"))
                cache[url] = None
            else:
                try:
                    print(f"  pobieram {url}")
                    cache[url] = parser(pobierz(url), url)
                    if not cache[url]:
                        wyniki["bledy"].append((url, "strona pobrana, ale nie znaleziono na niej cen "
                                                     "(zmienił się wygląd strony?)"))
                except Exception as ex:
                    wyniki["bledy"].append((url, str(ex)))
                    cache[url] = None
                time.sleep(0.5)
        return cache[url]

    for nazwa_pliku in PLIKI:
        sciezka = DATA / nazwa_pliku
        if not sciezka.exists():
            continue
        surowy = sciezka.read_bytes().decode("utf-8")
        dane = json.loads(surowy)
        zmieniony = False

        # ile wariantów korzysta z danego adresu (do rozpoznania stron pojedynczych produktów)
        licznik_url = {}
        for p in dane.get("products", []):
            for v in p.get("variants", []):
                u = v.get("sourceUrl") or p.get("sourceUrl")
                licznik_url[u] = licznik_url.get(u, 0) + 1

        for p in dane.get("products", []):
            zmiana_produktu = False
            producent = p.get("brand", "")
            for v in p.get("variants", []):
                if v.get("active") is False:
                    continue
                url = v.get("sourceUrl") or p.get("sourceUrl") or (p.get("sourceUrls") or [None])[0]
                stara = cena_wariantu(v)
                typ = v.get("priceType") or p.get("priceType", "netto")
                rekord = {"producent": producent, "produkt": p.get("name") or p.get("model", ""),
                          "wariant": nazwa_wariantu(v), "stara": stara, "typ": typ, "url": url or ""}
                wyniki["sprawdzone"] += 1
                if not url:
                    rekord.update(status="nie-znaleziono", uwaga="brak adresu źródłowego")
                    wyniki["warianty"].append(rekord)
                    continue
                pozycje = strona(url)
                if pozycje is None:
                    rekord.update(status="nie-znaleziono", uwaga="błąd pobierania strony")
                    wyniki["warianty"].append(rekord)
                    continue

                poz, sposob = dopasuj(p, v, pozycje, url, licznik_url.get(url, 0))
                if not poz:
                    rekord.update(status="nie-znaleziono", uwaga=sposob)
                    wyniki["warianty"].append(rekord)
                    continue

                uzyte.add((url, poz["nazwa"]))
                uzyte_url.update(u.rstrip("/") for u in (url, poz.get("url")) if u)
                nowa = poz["cena"]
                rekord.update(nowa=nowa, sposob=sposob)
                if poz.get("url") and poz["url"] != url:
                    rekord["url"] = poz["url"]
                roznica = abs(nowa - stara) if stara else nowa
                if roznica < 0.005:
                    rekord["status"] = "bez-zmian"
                elif roznica <= TOLERANCJA_ZL:
                    rekord["status"] = "zaokraglenie"
                else:
                    proc = abs(nowa - stara) / stara * 100 if stara else 100
                    if args.sprawdz or (proc > PROG_DUZEJ_ZMIANY and not args.akceptuj_duze):
                        rekord["status"] = "zmiana-niezastosowana"
                    else:
                        ustaw_cene_wariantu(v, nowa, typ, dzis)
                        rekord["status"] = "zmieniono"
                        zmiana_produktu = True
                    znak = "↑" if nowa > stara else "↓"
                    print(f"    {znak} {rekord['produkt']} / {rekord['wariant']}: "
                          f"{fmt_cena(stara)} → {fmt_cena(nowa)} zł"
                          + ("" if rekord["status"] == "zmieniono" else "  (nie zastosowano)"))
                wyniki["warianty"].append(rekord)

            if zmiana_produktu:
                przelicz_produkt(p, dzis)
                zmieniony = True

        if zmieniony:
            meta = dane.get("meta") or dane.get("metadata")
            if isinstance(meta, dict):
                for pole in ("generatedAt", "updatedAt"):
                    if pole in meta:
                        meta[pole] = dzis
            KOPIE.mkdir(exist_ok=True)
            kopia = KOPIE / f"{sciezka.stem}_{czas:%Y-%m-%d_%H%M%S}.json"
            shutil.copy2(sciezka, kopia)
            # zachowaj końce linii i (brak) końcowego znaku nowej linii z oryginału
            nowy = json.dumps(dane, ensure_ascii=False, indent=2)
            if surowy.endswith("\n"):
                nowy += "\n"
            if "\r\n" in surowy:
                nowy = nowy.replace("\n", "\r\n")
            sciezka.write_bytes(nowy.encode("utf-8"))
            wyniki["zapisane"].append(f"data/{nazwa_pliku}  (kopia: data/kopie/{kopia.name})")

    # Pozycje z list producentów, których nie ma w katalogu
    for url, pozycje in cache.items():
        if not pozycje or len(pozycje) < 2:
            continue
        for x in pozycje:
            if x.get("podstawowa") or (url, x["nazwa"]) in uzyte or (x["url"] or "").rstrip("/") in uzyte_url:
                continue
            producent = next((b for k, b in (("datecs", "Datecs"), ("posnet", "Posnet"), ("novitus", "Novitus"),
                                             ("aclas", "Aclas"), ("satis", "SATIS")) if k in url), "")
            wyniki["nowe"].append({**x, "producent": producent})
    # bez duplikatów (ten sam produkt bywa na kilku listach)
    wyniki["nowe"] = list({(x["producent"], norm(x["nazwa"])): x for x in wyniki["nowe"]}.values())

    if wyniki["zapisane"]:
        print("\nAktualizuję kopie inline w index.html:")
        uruchom_sync()
        wyniki["zapisane"].append("index.html  (bloki inline zsynchronizowane)")

    raport = zapisz_raport(wyniki, czas, tryb)
    zm = sum(1 for w in wyniki["warianty"] if w["status"] == "zmieniono")
    nz = sum(1 for w in wyniki["warianty"] if w["status"] == "zmiana-niezastosowana")
    bz = sum(1 for w in wyniki["warianty"] if w["status"] == "nie-znaleziono")
    print(f"\nSprawdzono {wyniki['sprawdzone']} wariantów: zaktualizowano {zm}, "
          f"wykryte niezastosowane {nz}, nie znaleziono {bz}, błędy pobierania {len(wyniki['bledy'])}.")
    print(f"Raport: {raport}")


if __name__ == "__main__":
    main()
