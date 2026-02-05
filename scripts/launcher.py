import subprocess
import re
import requests
import time
import sys
import os
import threading

# --- CONFIG (GANTI INI) ---
GAS_WEBAPP_URL = "https://script.google.com/macros/s/AKfycbyDTZAd1scdvbyiVGNVM6eokc1lhw8NfY6aEYASFC9lbEbtey9jKIBzRM5rrH4DzLWzBA/exec"
# --------------------------

def update_gas_config(tunnel_url):
    """Kirim URL Tunnel baru ke Google Sheet"""
    print(f"\n[SYSTEM] Tunnel URL Baru: {tunnel_url}")
    print("[SYSTEM] Sedang update Google Sheet...")
    try:
        resp = requests.post(
            GAS_WEBAPP_URL, 
            params={"action": "update_tunnel"},
            json={"url": tunnel_url},
            timeout=10
        )
        if resp.status_code == 200:
            print("[SYSTEM] SUKSES. Google Sheet berhasil diupdate.")
            print("[SYSTEM] SIAP PRINT. Jangan tutup window ini.\n")
        else:
            print(f"[SYSTEM] GAGAL Update Sheet: {resp.text}")
    except Exception as e:
        print(f"[SYSTEM] ERROR Koneksi GAS: {e}")

def start_backend():
    """Jalanin Server Python"""
    print("[SYSTEM] Menyalakan Backend Server...")
    # Pake sys.executable biar pasti pake python dari venv yang sama
    subprocess.run([sys.executable, "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"])

def start_tunnel():
    """Jalanin Cloudflare Tunnel"""
    print("[SYSTEM] Menyalakan Cloudflare Tunnel...")
    
    cmd = "cloudflared.exe" if os.path.exists("cloudflared.exe") else "cloudflared"
        
    process = subprocess.Popen(
        [cmd, "tunnel", "--url", "http://localhost:8080"],
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        universal_newlines=True
    )

    url_found = False
    
    for line in process.stderr:
        if "trycloudflare.com" in line:
            match = re.search(r'https://[a-zA-Z0-9-]+\.trycloudflare\.com', line)
            if match and not url_found:
                tunnel_url = match.group(0)
                threading.Thread(target=update_gas_config, args=(tunnel_url,)).start()
                url_found = True

if __name__ == "__main__":
    t = threading.Thread(target=start_tunnel)
    t.daemon = True
    t.start()
    
    time.sleep(3)
    
    try:
        start_backend()
    except KeyboardInterrupt:
        print("\n[SYSTEM] Shutting down...")