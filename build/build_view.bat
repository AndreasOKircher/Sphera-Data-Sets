@echo off
:: Build sphera-view.exe — terminal dataset viewer
:: Run from the project root:  build\build_view.bat

cd /d "%~dp0.."

echo Installing PyInstaller if needed...
pip install pyinstaller --quiet

echo.
echo Building sphera-view.exe ...
pyinstaller ^
  --onefile ^
  --name sphera-view ^
  --collect-all lxml ^
  view.py

echo.
if exist dist\sphera-view.exe (
    echo [OK] dist\sphera-view.exe built successfully.
    echo.
    echo Usage:
    echo   dist\sphera-view.exe                    -- list all datasets
    echo   dist\sphera-view.exe ^<uuid^>             -- inspect one dataset
    echo   dist\sphera-view.exe ^<uuid^> --full      -- show full text fields
    echo.
    echo NOTE: Place the .exe next to your dataset\ folder.
) else (
    echo [FAIL] Build failed. Check output above.
)
