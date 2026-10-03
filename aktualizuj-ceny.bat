@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Kontrola cen u producentow i aktualizacja katalogu...
echo (aby tylko sprawdzic bez zmian, uruchom: aktualizuj-ceny.bat --sprawdz)
echo.
py aktualizuj-ceny.py %*
if errorlevel 9009 python aktualizuj-ceny.py %*
echo.
for /f "delims=" %%f in ('dir /b /o-d raporty\raport-cen_*.html 2^>nul') do (
  start "" "raporty\%%f"
  goto :koniec
)
:koniec
pause
