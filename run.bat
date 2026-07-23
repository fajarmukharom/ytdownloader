@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

set SCRIPT_DIR=%~dp0
set PORT=8421

REM [1] app.py exists
if not exist "%SCRIPT_DIR%app.py" (
    echo [X] File app.py nggak ketemu. Pastikan kamu di folder yang benar.
    pause
    exit /b 1
)

REM [2] python
where python >nul 2>nul
if errorlevel 1 (
    echo [X] Python nggak ketemu. Jalankan install.bat dulu.
    pause
    exit /b 1
)

REM [2] pytubefix
python -c "import pytubefix" >nul 2>nul
if errorlevel 1 (
    echo [X] Ada dependency yang belum terinstall (pytubefix^). Jalankan install.bat dulu.
    pause
    exit /b 1
)

REM [2] flask
python -c "import flask" >nul 2>nul
if errorlevel 1 (
    echo [X] Ada dependency yang belum terinstall (flask^). Jalankan install.bat dulu.
    pause
    exit /b 1
)

REM [2] ffmpeg
where ffmpeg >nul 2>nul
if errorlevel 1 (
    echo [X] Ada dependency yang belum terinstall (ffmpeg^). Jalankan install.bat dulu.
    pause
    exit /b 1
)

REM [3] downloads folder
if not exist "%SCRIPT_DIR%downloads" mkdir "%SCRIPT_DIR%downloads"

REM [4] Check port
netstat -ano | findstr /r /c:":%PORT% .*LISTENING" >nul 2>nul
if not errorlevel 1 (
    echo [X] Port %PORT% sudah dipakai. Tutup app lain di port itu dulu.
    pause
    exit /b 1
)

REM [5] Start app
cd /d "%SCRIPT_DIR%"

echo [OK] App running di http://localhost:%PORT%
echo     Tekan Ctrl+C untuk stop.
echo.

REM Buka browser setelah 2 detik, di proses terpisah, supaya app.py bisa langsung
REM jalan di foreground (Ctrl+C di window ini akan langsung menghentikannya).
start "" /min cmd /c "timeout /t 2 >nul && start "" http://localhost:%PORT%"

python app.py

echo.
echo App dihentikan.
pause
