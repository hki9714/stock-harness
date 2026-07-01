@echo off
cd /d "%~dp0"
set LOG=build_log.txt

echo Build started > %LOG%
echo Working dir: %CD% >> %LOG%
echo. >> %LOG%

echo [1/4] Activating venv...
echo [1/4] Activating venv >> %LOG%
if not exist "venv\Scripts\activate.bat" (
    echo [ERROR] venv not found >> %LOG%
    echo [ERROR] venv\Scripts\activate.bat not found
    cmd /k
)
call venv\Scripts\activate.bat
echo venv activated >> %LOG%

echo [2/4] Installing PyInstaller...
echo [2/4] Installing PyInstaller >> %LOG%
pip install pyinstaller --quiet >> %LOG% 2>&1
if errorlevel 1 (
    echo [ERROR] pip install failed >> %LOG%
    echo [ERROR] pip install failed
    cmd /k
)
echo PyInstaller ready >> %LOG%

echo [3/4] Cleaning previous build...
echo [3/4] Cleaning >> %LOG%
if exist "dist\StockHarness" rmdir /s /q "dist\StockHarness"
if exist "build" rmdir /s /q "build"

echo [4/4] Building exe (3-10 min)...
echo [4/4] Building >> %LOG%
pyinstaller stock_harness.spec --clean --noconfirm >> %LOG% 2>&1
if errorlevel 1 (
    echo [ERROR] Build failed - see build_log.txt >> %LOG%
    echo [ERROR] Build failed - see build_log.txt
    cmd /k
)

echo [DONE] Build complete >> %LOG%
echo.
echo [DONE] dist\StockHarness is ready.
echo Log: %CD%\build_log.txt
echo.
echo NOTE: Copy the guide file manually:
echo   source : %CD%\
echo   target : %CD%\dist\StockHarness\
echo.
if exist "dist\StockHarness" explorer "dist\StockHarness"
cmd /k
