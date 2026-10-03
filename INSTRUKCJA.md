# INFOKASY – instrukcja strony

Jak zbudowana jest strona infokasy, co robi każda jej część i jak wykonywać typowe prace: zmiana cen, dodanie produktu, publikacja.

Stan na: 2026-10-03

---

## 1. W skrócie

- Strona to **jeden plik `index.html`**. Ma jedną podstronę: symulator kasy Datecs WP-25.
- Nie ma bazy danych ani panelu administracyjnego. Wszystko jest w plikach.
- **Produkty i ceny** są w plikach `data/products-*.json`, po jednym na producenta.
- **Formularze** wysyłają wiadomości e-mail przez usługę Formspree.
- Dwa narzędzia ułatwiają pracę:
  - `aktualizuj-ceny.bat` sprawdza ceny u producentów i aktualizuje katalog,
  - `synchronizuj-produkty.bat` przepisuje dane produktów do `index.html`.

---

## 2. Zawartość folderu

| Plik / folder | Do czego służy |
|---|---|
| `index.html` | Cała strona: treść, wygląd (CSS), skrypty, kopia danych produktów |
| `mpa0rk8f-datecs-wp25-v0.2.html` | Podstrona „Symulator kasy Datecs WP-25” |
| `data/products-datecs.json` | Produkty Datecs: kasy WP-25/50/500 Plus, POS HioPOS |
| `data/products-posnet.json` | Produkty Posnet: kasy i drukarki fiskalne |
| `data/products-novitus.json` | Produkty Novitus: kasy i drukarki POINT |
| `data/products-aclas.json` | Produkty Aclas: kasy Kos_OL, Kobra_ON, gastronomiczne |
| `data/products-satis.json` | Wagi SATIS: sklepowe i magazynowe |
| `data/*.xlsx` | Arkusze z cenami, z których powstały pliki JSON (archiwum, strona ich nie używa) |
| `data/kopie/` | Kopie zapasowe JSON tworzone automatycznie przed każdą zmianą cen |
| `pic/` | Zdjęcia strony: slajdy, logo, marki, DPD, mapa |
| `pic/modele/` | Zdjęcia produktów w katalogu (np. `wp-25-plus.webp`) |
| `aktualizuj-ceny.py` / `.bat` | Narzędzie do kontroli i aktualizacji cen (rozdział 7) |
| `sync-products.py` / `synchronizuj-produkty.bat` | Synchronizacja JSON → `index.html` (rozdział 8) |
| `raporty/` | Raporty z kontroli cen (pliki HTML) |
| `docs/DESIGN.md` | Zasady wyglądu: kolory, czcionki, odstępy |
| `test-strony-checklista.md` | Lista kontrolna do testowania linków i formularzy |

---

## 3. Jak otworzyć stronę na komputerze

**Sposób 1: dwuklik na `index.html`**
Strona otwiera się w przeglądarce i wszystko działa. Przeglądarka nie pozwala jednak wtedy czytać plików `data/*.json`. Katalog produktów korzysta więc z **kopii danych wbudowanej w `index.html`**. Po ręcznej edycji JSON trzeba zatem uruchomić `synchronizuj-produkty.bat`, inaczej zmian nie będzie widać.

**Sposób 2: lokalny serwer (tak samo jak na hostingu)**
W folderze strony uruchom:

```bash
py -m http.server 8000
```

Potem wejdź na `http://localhost:8000`. W tym trybie strona czyta pliki `data/*.json` bezpośrednio, więc zmiany widać po odświeżeniu.

---

## 4. Sekcje strony

Menu u góry prowadzi do sekcji przez kotwice, np. `#oferta`.

| Sekcja | Kotwica | Co zawiera |
|---|---|---|
| Nagłówek i menu | `#top` | Logo, menu; na telefonie menu rozwijane przyciskiem ☰ |
| Baner główny | `#hero` | Hasło, przyciski kontaktu, pokaz slajdów (zmiana co 3,5 s, kropki do przełączania) |
| Oferta | `#oferta` | 6 kafelków, opis poniżej |
| Marki | `#marki` | Logotypy producentów z linkami do ich stron (Posnet, Novitus, Datecs, Aclas, Satis, Axis…) |
| Dlaczego my | `#dlaczego` | Zalety firmy |
| Symulator | `#symulator` | Zapowiedź i link do podstrony z symulatorem kasy Datecs WP-25 |
| DPD Pickup | `#dpd` | Informacja o punkcie nadawania i odbioru paczek DPD |
| Kontakt | `#kontakt` | Adres (ul. Jana Pawła II 1, 19-300 Ełk), godziny (Pn–Pt 7:30–15:30), telefony, e-mail, mapa Google |
| Stopka | – | Dane firmy, rok uzupełniany automatycznie |

### Kafelki w sekcji Oferta

| Kafelek | Co się dzieje po kliknięciu |
|---|---|
| **Kasy i drukarki fiskalne** | Otwiera katalog produktów ze wszystkimi modelami |
| **Systemy POS** | Otwiera katalog z filtrem „Systemy POS” |
| **Wagi** | Otwiera katalog z filtrem „Wagi” (sklepowe i magazynowe) |
| **Terminale płatnicze** | Otwiera formularz zapytania o terminal |
| **Serwis i instalacje** | Otwiera okno serwisu z formularzem zgłoszenia |
| **Punkt DPD Pickup** | Kafelek informacyjny |

---

## 5. Katalog produktów (okno z modelami)

### Co widzi klient
- **Filtry** u góry: „Wszystkie modele”, kategorie (Kasy fiskalne, Drukarki fiskalne, Systemy POS, Wagi…) i marki (Datecs, Posnet, Novitus, Aclas, SATIS). Strona tworzy filtry sama na podstawie danych. Nowa kategoria lub marka dodana w JSON pojawi się automatycznie.
- **Karta produktu** zawiera:
  - zdjęcie (gdy go brakuje, widać napis „Brak zdjęcia”),
  - markę i nazwę,
  - **cenę „od”**, czyli najniższą cenę spośród aktywnych wariantów, z dopiskiem netto albo brutto według pola `priceType`,
  - 3 pierwsze cechy z listy `features`.
- **„Zapytaj o ten model”** otwiera formularz z wpisanym już modelem, marką i kategorią.
- **„Zobacz szczegóły ↗”** otwiera stronę produktu u producenta (pole `sourceUrl`).

### Skąd strona bierze dane
1. Najpierw próbuje wczytać pliki `data/products-*.json`. Działa to na hostingu i na lokalnym serwerze.
2. Jeśli to się nie uda (np. przy otwarciu dwuklikiem), używa kopii wbudowanych w `index.html` w blokach `<script type="application/json" id="pd-…">`.

Listę plików z danymi ustawia `DATA_SOURCES` w skrypcie `index.html`. Nazwy kategorii i ich kolejność ustawiają `CATEGORY_LABELS` i `CATEGORY_ORDER`, a kolejność marek `BRAND_ORDER`.

---

## 6. Formularze

Strona ma 3 formularze. Wszystkie wysyłają dane do tego samego konta **Formspree** (`https://formspree.io/f/xqejjgok`), a zgłoszenia przychodzą e-mailem.

| Formularz | Gdzie | Temat e-maila | Pola wymagane |
|---|---|---|---|
| Zapytanie o produkt | Katalog → „Zapytaj o ten model” | Nowy lead produktowy - INFOKASY | Imię i nazwisko, telefon, zgoda |
| Terminal płatniczy | Kafelek „Terminale płatnicze” | Nowy lead - terminal płatniczy - INFOKASY | Imię i nazwisko, telefon, e-mail, branża, zgoda |
| Zgłoszenie serwisowe | Kafelek „Serwis i instalacje” | Nowe zgłoszenie serwisowe - INFOKASY | Imię i nazwisko, telefon, opis problemu |

- Po wysłaniu klient widzi komunikat o sukcesie. Przy błędzie pojawia się prośba o telefon (87 610 41 63 lub 600 994 205).
- **Darmowy plan Formspree to 50 zgłoszeń miesięcznie.** Testowe wysyłki też się liczą.
- Zmiana adresu, na który przychodzą zgłoszenia, odbywa się w panelu formspree.io, nie w kodzie strony.
- Procedura testowania formularzy: `test-strony-checklista.md`.

---

## 7. Aktualizacja cen u producentów (`aktualizuj-ceny.bat`)

### Co robi narzędzie
1. Wchodzi na strony producentów podane w danych produktów (`sourceUrl`) i odczytuje aktualne ceny:

   | Producent | Gdzie są ceny | Typ ceny |
   |---|---|---|
   | Datecs | tabela wariantów na stronie produktu | netto |
   | Posnet | listy kategorii (kasy, drukarki) | netto |
   | Novitus | listy kategorii (kasy, drukarki) | netto, cena sugerowana |
   | Aclas | lista kategorii i strony produktów | netto + 23% VAT |
   | SATIS | strona produktu | brutto |

2. Porównuje je z cenami każdego wariantu w katalogu.
3. Gdy cena się zmieniła, poprawia cenę wariantu, cenę „od”, napisy z ceną i daty. **Przed zapisem robi kopię pliku w `data/kopie/`.**
4. Aktualizuje kopię danych w `index.html`. Nie trzeba osobno uruchamiać synchronizacji.
5. Zapisuje raport w `raporty/raport-cen_DATA_GODZINA.html` i otwiera go w przeglądarce.

### Jak używać
- **Dwuklik `aktualizuj-ceny.bat`** sprawdza ceny i od razu je aktualizuje.
- Samo sprawdzenie, bez zmian w plikach:
  ```bash
  py aktualizuj-ceny.py --sprawdz
  ```
- Zastosowanie także bardzo dużych zmian (powyżej 35%):
  ```bash
  py aktualizuj-ceny.py --akceptuj-duze
  ```

Najbezpieczniej najpierw uruchomić `--sprawdz`, przejrzeć raport, a dopiero potem wprowadzić zmiany.

### Zabezpieczenia
- Zmiana **większa niż 35%** nie jest wprowadzana automatycznie, tylko oznaczana w raporcie jako „do weryfikacji”. Chroni to przed pomyłkami, np. gdy producent chwilowo wyświetli błędną cenę.
- Różnice **do 1,50 zł** są traktowane jako zaokrąglenia i pomijane.
- W plikach JSON zmieniają się tylko linie z cenami i datami.

### Co jest w raporcie
- liczby: ile wariantów sprawdzono, ile cen zmieniono, ilu nie znaleziono, ile było błędów,
- **tabela zmian**: produkt, wariant, cena przed zmianą i po zmianie, różnica w zł i %, link do źródła,
- **nie znaleziono u producenta**: produkt mógł zniknąć z oferty albo zmienić nazwę,
- **błędy pobierania**: strona producenta nie odpowiedziała albo zmieniła wygląd,
- **produkty u producenta, których nie ma w katalogu**: podpowiedź, co można dodać.

### Gdy produkt pojawia się jako „nie znaleziono”
Najczęściej producent zmienił nazwę. Wtedy:
1. Otwórz link z raportu i sprawdź, jak produkt nazywa się teraz u producenta.
2. W pliku `aktualizuj-ceny.py`, na początku, dopisz go do słownika `ALIASY`:
   ```python
   ALIASY = {
       "posnet-mobile2-online": "MOBILE2",
       "id-produktu-z-json": "Nazwa dokładnie jak u producenta",
   }
   ```
Jeśli produkt zniknął z oferty, ustaw w JSON `"active": false` (rozdział 9).

### Gdy wystąpi błąd „nie znaleziono na stronie cen”
Producent zmienił wygląd swojej strony i trzeba poprawić odczyt w `aktualizuj-ceny.py`. Każdy producent ma tam swoją funkcję, np. `parser_posnet`. Do tego czasu ceny tego producenta po prostu się nie zmieniają, bo narzędzie niczego nie psuje.

### Cofnięcie zmian
Skopiuj odpowiedni plik z `data/kopie/` z powrotem do `data/`, usuwając z nazwy datę, np. `products-posnet_2026-10-03_215131.json` → `products-posnet.json`. Potem uruchom `synchronizuj-produkty.bat`.

---

## 8. Synchronizacja danych (`synchronizuj-produkty.bat`)

Przepisuje zawartość `data/products-*.json` do kopii wbudowanych w `index.html`.

**Kiedy uruchamiać:** po każdej **ręcznej** edycji plików JSON. Bez tego strona otwierana dwuklikiem pokaże stare dane, a na hostingu stara kopia zostanie w `index.html`.
Po `aktualizuj-ceny.bat` nie trzeba, bo narzędzie robi to samo.

---

## 9. Dane produktów: jak edytować

Pliki JSON można edytować w Notatniku lub VS Code. **Zachowaj składnię**: cudzysłowy, przecinki między elementami, brak przecinka po ostatnim elemencie. Błąd składni wykryje `synchronizuj-produkty.bat`, który poda numer linii.

Pliki mają dwa układy. Posnet używa innych nazw pól, strona obsługuje oba:

| Znaczenie | Datecs, Novitus, Aclas, SATIS | Posnet |
|---|---|---|
| Cena „od” produktu | `priceFrom` | `priceFromNet` |
| Napis z ceną produktu | `priceLabel` | `displayPrice` |
| Cena wariantu | `price` | `priceNet` |
| Nazwa wariantu | `version` | `name` |
| Link do producenta | `sourceUrl` | `sourceUrls` (lista) |

### Przykład produktu

```json
{
  "id": "wp-25-plus",
  "category": "kasy-fiskalne",
  "brand": "Datecs",
  "model": "DATECS WP-25 PLUS",
  "name": "Datecs WP-25 Plus",
  "image": "pic/modele/wp-25-plus.webp",
  "priceFrom": 1349,
  "currency": "PLN",
  "priceType": "netto",
  "priceLabel": "od 1 349 zł netto",
  "features": ["Niewielkie rozmiary", "Kolorowy wyświetlacz", "Mobilna praca"],
  "sourceUrl": "https://www.datecs-polska.pl/...",
  "active": true,
  "variants": [
    { "version": "WP-25 LAN", "price": 1349, "currency": "PLN", "priceType": "netto",
      "priceLabel": "1 349 zł netto", "sourceUrl": "https://www.datecs-polska.pl/...", "active": true }
  ]
}
```

### Najważniejsze pola

| Pole | Opis |
|---|---|
| `id` | Unikalny identyfikator, małe litery i myślniki |
| `category` / `categories` | Kategoria, która decyduje o filtrze: `kasy-fiskalne`, `drukarki-fiskalne`, `systemy-pos`, `wagi-sklepowe`, `wagi-magazynowe`, `kasy-gastronomiczne` |
| `brand` | Marka, która tworzy filtr marki |
| `model` | Nazwa wyświetlana na karcie |
| `image` | Ścieżka do zdjęcia, np. `pic/modele/nazwa.webp` |
| `priceType` | `netto` albo `brutto`; wpływa na dopisek przy cenie |
| `features` | Cechy; na karcie widać 3 pierwsze |
| `sourceUrl` | Strona produktu u producenta: przycisk „Zobacz szczegóły” i źródło dla kontroli cen |
| `active` | `false` ukrywa wariant i pomija go przy cenie „od” i przy kontroli cen |
| `variants` | Wersje produktu z cenami. **Cena „od” na karcie to najniższa cena aktywnego wariantu** |

### Typowe zadania

**Zmiana ceny ręcznie**
Zmień `price` (u Posnetu `priceNet`) w wariancie. Popraw też napisy `priceLabel` / `displayPrice` dla porządku, bo karta i tak liczy cenę sama. Uruchom `synchronizuj-produkty.bat`.

**Dodanie produktu**
1. Skopiuj istniejący produkt tego samego producenta i wklej go jako nowy element listy `products`.
2. Zmień `id`, `model`, `name`, `image`, `features`, `sourceUrl` i warianty.
3. Wrzuć zdjęcie do `pic/modele/`: format `.webp`, najlepiej kwadratowe, ok. 600×600 px.
4. Uruchom `synchronizuj-produkty.bat`.
5. Uruchom `py aktualizuj-ceny.py --sprawdz` i sprawdź, czy nowy produkt został dopasowany. Jeśli nie, dodaj alias (rozdział 7).

**Ukrycie produktu, który zniknął z oferty**
Ustaw `"active": false` w jego wariantach i uruchom synchronizację.

**Dodanie nowego producenta**
1. Utwórz `data/products-nowy.json` w tym samym układzie co pozostałe pliki.
2. W `index.html` dopisz go do `DATA_SOURCES` i dodaj pusty blok `<script type="application/json" id="pd-nowy"></script>` obok innych bloków `pd-…`.
3. W `sync-products.py` dopisz go do `MAPPING`.
4. W `aktualizuj-ceny.py` dopisz plik do `PLIKI`. Kontrola cen nowego producenta wymaga dodatkowo nowej funkcji odczytu w `wybierz_parser`.

---

## 10. Symulator kasy Datecs WP-25

Plik `mpa0rk8f-datecs-wp25-v0.2.html` to osobna strona, na której klient może „poklikać” kasę przed zakupem. Link do niej jest w sekcji `#symulator`. Strona jest niezależna od katalogu i nie korzysta z plików JSON.

---

## 11. Publikacja na hostingu

Na serwer wgraj:
- `index.html`
- `mpa0rk8f-datecs-wp25-v0.2.html`
- folder `pic/`
- folder `data/`, ale wystarczą same pliki `products-*.json`

**Nie trzeba wgrywać:** `data/kopie/`, `data/*.xlsx`, `raporty/`, plików `.py`, `.bat`, `.md`, `docs/`.

Po publikacji:
- sprawdź na żywej stronie katalog produktów i wyślij jeden testowy formularz,
- po każdej aktualizacji cen wgraj ponownie zmienione `data/products-*.json` i `index.html`.

---

## 12. Rozwiązywanie problemów

| Problem | Przyczyna i rozwiązanie |
|---|---|
| Po edycji JSON strona pokazuje stare ceny | Przy otwarciu dwuklikiem strona używa kopii w `index.html`. Uruchom `synchronizuj-produkty.bat`. Na hostingu wyczyść pamięć przeglądarki (Ctrl+F5) |
| „Nie udało się załadować produktów” | Błąd składni w pliku JSON. Uruchom `synchronizuj-produkty.bat`, który wskaże linię |
| Karta pokazuje „Brak zdjęcia” | Ścieżka w `image` nie zgadza się z plikiem w `pic/modele/`. Wielkość liter ma znaczenie na hostingu |
| Produkt nie pojawia się pod filtrem | Sprawdź `category` / `categories` i `brand` |
| Formularz pokazuje błąd wysyłania | Brak internetu, wyczerpany limit Formspree (50/mies.) albo niepotwierdzony formularz w panelu Formspree |
| `aktualizuj-ceny.bat`: „nie znaleziono Python” | Zainstaluj Python ze strony python.org i zaznacz „Add to PATH”. Narzędzie korzysta z polecenia `py` |
| Raport: „nie znaleziono u producenta” | Rozdział 7: alias albo `active: false` |

---


## 13. SEO – widoczność w Google

Co jest na stronie:

| Element | Gdzie | Do czego służy |
|---|---|---|
| Tytuł i opis | `<title>` i `<meta name="description">` w `index.html` | Tekst wyświetlany w wynikach Google; zawierają miejscowość „Ełk” |
| Link kanoniczny | `<link rel="canonical">` | Wskazuje Google główny adres strony |
| Open Graph i karta X | `og:*`, `twitter:*` | Podgląd linku na Facebooku, Messengerze, WhatsAppie, LinkedIn i X |
| Grafika do udostępnień | `pic/og-image.jpg` (1200×630) | Obrazek pokazywany przy udostępnieniu linku |
| Dane strukturalne | `<script type="application/ld+json">` w `index.html` | Dane firmy dla Google: adres, telefony, godziny, mapa |
| Mapa witryny | `sitemap.xml` | Lista podstron do zgłoszenia w Google Search Console |
| Zasady dla robotów | `robots.txt` | Pozwala indeksować stronę i wskazuje mapę witryny |
| Wymiary obrazów | atrybuty `width`/`height` w `<img>` | Strona nie „skacze” podczas ładowania zdjęć |

**Zmiana danych firmy** (telefon, godziny, adres): popraw je w treści strony **i** w bloku `application/ld+json` w `<head>`.

**Przejście na własną domenę** (np. `infokasy.pl`): zamień adres `https://kkrysztofik.github.io/infokasy/` na nowy we wszystkich miejscach:
- `index.html`: `canonical`, `og:url`, `og:image`, `twitter:image` i adresy w bloku `application/ld+json`,
- `mpa0rk8f-datecs-wp25-v0.2.html`: `canonical`,
- `sitemap.xml` i `robots.txt`.

Najprościej wyszukać w tych plikach `kkrysztofik.github.io/infokasy` i zamienić wszystkie wystąpienia.

**Po publikacji:**
- zgłoś stronę i `sitemap.xml` w [Google Search Console](https://search.google.com/search-console),
- sprawdź dane strukturalne w [teście wyników z elementami rozszerzonymi](https://search.google.com/test/rich-results),
- sprawdź podgląd linku w [Facebook Sharing Debugger](https://developers.facebook.com/tools/debug/).

**Ograniczenia GitHub Pages:**
- `robots.txt` działa tylko w katalogu głównym domeny. Pod adresem `kkrysztofik.github.io/infokasy/` Google go nie czyta, więc mapę witryny trzeba zgłosić ręcznie w Search Console. Zacznie działać po przejściu na własną domenę.
- Nagłówków bezpieczeństwa (np. HSTS) nie da się ustawić na GitHub Pages. Strona i tak działa wyłącznie po HTTPS.
