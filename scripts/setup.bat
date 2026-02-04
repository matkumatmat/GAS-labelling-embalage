@echo off
title WMS SETUP
color 0B

echo =================================================
echo           WMS PRINTER - INSTALLER
echo =================================================
echo.

:: 1. Cek Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python belum terinstall. Install dulu.
    pause
    exit
)

:: 2. Download Cloudflared
if not exist "cloudflared.exe" (
    echo [INFO] Sedang mendownload Cloudflared...
    powershell -Command "Invoke-WebRequest -Uri 'https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe' -OutFile 'cloudflared.exe'"
    echo [OK] Cloudflared berhasil didownload.
) else (
    echo [INFO] Cloudflared sudah ada.
)

:: 3. Setup Virtual Environment & Poetry
if not exist ".venv" (
    echo [INFO] Membuat Virtual Environment...
    python -m venv .venv
)

echo [INFO] Mengaktifkan venv...
call .venv\Scripts\activate

echo [INFO] Menginstall Poetry...
pip install poetry

echo [INFO] Konfigurasi Poetry...
:: Biar poetry install library-nya ke dalam .venv yang lagi aktif ini
poetry config virtualenvs.create false --local

echo [INFO] Menginstall dependencies via Poetry...
:: Pastikan pyproject.toml dan poetry.lock ada di folder ini
poetry install

echo.
echo =================================================
echo      SETUP SELESAI. LANJUT KLIK start.bat
echo =================================================
pause