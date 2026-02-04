import socket
import structlog
from typing import Tuple

# Init logger (automatis dapet context dari middleware)
logger = structlog.get_logger()

class PrinterClient:
    def __init__(self, ip: str, port: int = 9100, timeout: int = 5):
        self.ip = ip
        self.port = port
        self.timeout = timeout

    def send_zpl(self, zpl_code: str) -> Tuple[bool, str]:
        if not zpl_code:
            logger.warning("zpl_empty_payload", ip=self.ip)
            return False, "ZPL Code kosong"

        try:
            logger.info("printer_connecting", ip=self.ip, port=self.port)
            
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(self.timeout)
                s.connect((self.ip, self.port))
                s.sendall(zpl_code.encode('utf-8'))
            
            logger.info("printer_success", ip=self.ip)
            return True, "Sukses dikirim ke antrian printer"
            
        except Exception as e:
            # logger.exception otomatis nambahin stack trace lengkap di JSON
            logger.exception("printer_connection_failed", ip=self.ip, error=str(e))
            return False, f"Gagal koneksi printer: {str(e)}"