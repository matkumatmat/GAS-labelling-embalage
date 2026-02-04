from application.utils.client import PrinterClient
from domain.model.payload import DirectPrintRequest, PrintResponse
from datetime import datetime
import os
import structlog

# Load Config
PRINTER_IP = os.getenv("PRINTER_IP", "192.168.19.5")
logger = structlog.get_logger()

class PrintService:
    def __init__(self):
        self.client = PrinterClient(ip=PRINTER_IP)

    async def handle_direct_print(self, payload: DirectPrintRequest) -> PrintResponse:
        """
        Terima Request -> SIMPAN DEBUG FILE -> Print -> Lapor
        """

        # # --- [START] FITUR DEBUGGING ---
        # try:
        #     # 1. Bikin folder 'debug_zpl' kalo belum ada
        #     debug_folder = "debug_zpl"
        #     os.makedirs(debug_folder, exist_ok=True)

        #     # 2. Bikin nama file unik pake Timestamp
        #     timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        #     filename = f"zpl_received_{timestamp}.txt"
        #     file_path = os.path.join(debug_folder, filename)

        #     # 3. Tulis isi raw_zpl ke file
        #     with open(file_path, "w", encoding="utf-8") as f:
        #         f.write(payload.raw_zpl)
            
        #     # Log kalo file berhasil disimpan
        #     logger.info("debug_file_saved", filename=filename, content_length=len(payload.raw_zpl))
            
        # except Exception as e:
        #     # Kalo gagal simpan file, jangan sampe bikin print gagal. Cukup log error aja.
        #     logger.error("debug_file_error", error=str(e))
        # # --- [END] FITUR DEBUGGING ---

        
        # --- LOGIC UTAMA (Kirim ke Printer) ---
        # Kalau mau test DEBUG DOANG (tanpa nge-print beneran), 
        # baris di bawah ini bisa dikomen dulu (#)
        success, msg = self.client.send_zpl(payload.raw_zpl)
        
        status_code = "SUCCESS" if success else "ERROR"
        
        return PrintResponse(
            status=status_code,
            message=msg,
            timestamp=datetime.now().isoformat()
        )