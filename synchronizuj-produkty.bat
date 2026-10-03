@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Synchronizuje dane produktow (data\products-*.json -^> index.html)...
echo.
python sync-products.py
if errorlevel 1 (
  py sync-products.py
)
echo.
pause
