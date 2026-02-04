from fastapi import APIRouter, HTTPException, status
import structlog
from domain.model.payload import DirectPrintRequest, PrintResponse
from application.service.print_service import PrintService

router = APIRouter(tags=["Proxy Bridge"])
service = PrintService()
logger = structlog.get_logger()

@router.post("/direct-print", response_model=PrintResponse)
async def direct_print_endpoint(payload: DirectPrintRequest):
    # Log event spesifik (source dari payload)
    logger.info("proxy_request_received", source=payload.source, printer_id=payload.printer_id)
    
    result = await service.handle_direct_print(payload)
    
    if result.status == "ERROR":
        logger.error("proxy_print_failed", reason=result.message)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=result.message
        )
        
    return result