from pydantic import BaseModel, Field
from typing import Optional

# Schema buat Payload dari GAS (Proxy Mode)
class DirectPrintRequest(BaseModel):
    raw_zpl: str = Field(..., description="ZPL Code mentah yang sudah di-inject variable")
    source: str = Field("GAS", description="Identitas pengirim request")
    printer_id: Optional[str] = "DEFAULT"

# Schema Response
class PrintResponse(BaseModel):
    status: str
    message: str
    timestamp: str