@echo off
title WMS PRINTER - RUNNING
color 0A

echo =================================================
echo        WMS LABEL SERVICE - AUTO RUNNER
echo =================================================
echo.

:: 1. Auto Update
echo [INFO] Cek update git...
git pull
echo.

:: 2. Cek Environment
if not exist ".venv" (
    echo [ERROR] Belum di-setup. Klik 'setup.bat' dulu.
    pause
    exit
)

:: 3. Cek Cloudflared
if not exist "cloudflared.exe" (
    echo [ERROR] Cloudflared hilang. Klik 'setup.bat' dulu.
    pause
    exit
)

:: 4. Jalankan Aplikasi
echo [INFO] Menyalakan Sistem...
call .venv\Scripts\activate

:: Pastikan launcher.py jalan pake python venv
python launcher.py

pause