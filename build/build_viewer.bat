@echo off
:: Build sphera-viewer.exe — Flask web viewer
:: Run from the project root:  build\build_viewer.bat

cd /d "%~dp0.."

echo Installing PyInstaller if needed...
pip install pyinstaller --quiet

echo.
echo Building sphera-viewer.exe ...
pyinstaller ^
  --onefile ^
  --noconsole ^
  --name sphera-viewer ^
  --collect-all lxml ^
  --collect-all flask ^
  --add-data "viewer\templates;templates" ^
  viewer\app.py

echo.
if exist dist\sphera-viewer.exe (
    echo [OK] dist\sphera-viewer.exe built successfully.
    echo.
    echo Usage:
    echo   dist\sphera-viewer.exe    -- starts web server on http://localhost:5000
    echo.
    echo NOTE: Place the .exe next to your dataset\ folder.
    echo       Open http://localhost:5000 in your browser.
) else (
    echo [FAIL] Build failed. Check output above.
)
