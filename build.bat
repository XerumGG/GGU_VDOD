@echo off
setlocal

echo ============================================
echo   GGU_VDOD - EXE Build Script
echo ============================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python was not found on your PATH.
    echo Install it from https://www.python.org/downloads/ and check
    echo "Add python.exe to PATH" during setup, then run this script again.
    pause
    exit /b 1
)

echo [1/4] Creating virtual environment...
python -m venv venv
call venv\Scripts\activate.bat

echo.
echo [2/4] Installing dependencies (yt-dlp, pyinstaller)...
python -m pip install --upgrade pip >nul
pip install -r requirements.txt
pip install pyinstaller

echo.
echo [3/4] Building GGU_VDOD.exe (this can take a minute)...
set "PYI_MODE=--onefile"
if /I "%GGU_BUILD_MODE%"=="onedir" set "PYI_MODE=--onedir"
pyinstaller %PYI_MODE% --noconsole --name GGU_VDOD app.py

if exist ffmpeg (
    echo Copying bundled ffmpeg folder into dist\ffmpeg...
    if not exist dist\ffmpeg mkdir dist\ffmpeg
    xcopy /E /I /Y ffmpeg dist\ffmpeg >nul
)

echo.
echo [4/4] Done!
echo.
echo Your app is here:  dist\GGU_VDOD.exe
echo You can copy that single file anywhere and run it directly.
echo.
echo TIP: to skip ffmpeg setup entirely, create a folder named "ffmpeg" next to
echo GGU_VDOD.exe and put ffmpeg.exe inside it (or in an "ffmpeg\bin" subfolder).
echo The app auto-detects it there. See README.md for details.
echo.
pause
