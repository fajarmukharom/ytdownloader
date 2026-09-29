@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo.
echo ========================================
echo   YouTube Downloader - Installer
echo ========================================
echo.

REM [1/5] Python 3
echo [1/5] Mengecek Python 3...
where python >nul 2>nul
if errorlevel 1 (
    where winget >nul 2>nul
    if errorlevel 1 (
        echo [X] Python belum terinstall, dan winget tidak ditemukan untuk auto-install.
        echo     Download manual di https://www.python.org/downloads/
        echo     PENTING: centang "Add Python to PATH" saat install.
        pause
        exit /b 1
    )
    echo     Python belum ketemu, menginstall via winget, mohon tunggu...
    winget install --id Python.Python.3.12 -e --accept-source-agreements --accept-package-agreements
    if errorlevel 1 (
        echo [X] Gagal install Python via winget.
        echo     Install manual di https://www.python.org/downloads/
        echo     PENTING: centang "Add Python to PATH" saat install.
        pause
        exit /b 1
    )
    echo [OK] Python terinstall
    echo.
    echo     Tutup jendela ini, buka Command Prompt baru, lalu jalankan install.bat
    echo     lagi supaya PATH ter-refresh dan proses instalasi bisa dilanjutkan.
    pause
    exit /b 0
)
for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo [OK] Python %PYVER% ditemukan

REM [2/5] FFmpeg
echo [2/5] Mengecek / menginstall FFmpeg...
where ffmpeg >nul 2>nul
if errorlevel 1 (
    where winget >nul 2>nul
    if errorlevel 1 (
        echo [X] winget tidak ditemukan, tidak bisa auto-install FFmpeg.
        echo     Install manual: download dari https://www.gyan.dev/ffmpeg/builds/
        echo     lalu extract dan tambahkan folder bin-nya ke PATH.
        pause
        exit /b 1
    )
    echo     Menginstall FFmpeg via winget, mohon tunggu...
    winget install --id Gyan.FFmpeg -e --accept-source-agreements --accept-package-agreements
    if errorlevel 1 (
        echo [X] Gagal install FFmpeg via winget.
        echo     Install manual: download dari https://www.gyan.dev/ffmpeg/builds/
        echo     lalu extract dan tambahkan folder bin-nya ke PATH.
        pause
        exit /b 1
    )
    echo [OK] FFmpeg terinstall
    echo     Catatan: tutup dan buka ulang Command Prompt ini supaya PATH ter-refresh.
) else (
    echo [OK] FFmpeg sudah terinstall
)

REM [3/5] pytubefix
echo [3/5] Menginstall pytubefix...
python -m pip install -U "pytubefix>=11.1.0"
if errorlevel 1 (
    echo [X] Gagal install pytubefix. Coba manual: pip install -U pytubefix
    pause
    exit /b 1
)
echo [OK] pytubefix terinstall (versi terbaru)

REM [4/5] Flask
echo [4/5] Menginstall Flask...
python -c "import flask" >nul 2>nul
if errorlevel 1 (
    python -m pip install flask
    if errorlevel 1 (
        echo [X] Gagal install Flask. Coba manual: pip install flask
        pause
        exit /b 1
    )
    echo [OK] Flask terinstall
) else (
    echo [OK] Flask sudah terinstall
)

REM [5/5] downloads folder
echo [5/5] Menyiapkan folder downloads...
if not exist "%~dp0downloads" mkdir "%~dp0downloads"
echo [OK] Folder siap

echo.
echo ========================================
echo [OK] Instalasi selesai!
echo     Jalankan run.bat untuk mulai.
echo ========================================
echo.
pause
