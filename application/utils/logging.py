import logging
import sys
import structlog
from typing import Any, Dict

def configure_logging(log_level: str = "INFO"):
    """
    Konfigurasi structlog agar output berupa JSON dan menangkap 
    log dari standard library (Uvicorn, FastAPI, dll).
    """
    
    # Processor yang dipakai bersama (structlog & stdlib)
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info, # Print tracebacks
        structlog.processors.UnicodeDecoder(),
    ]

    # Konfigurasi khusus structlog
    structlog.configure(
        processors=shared_processors + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Formatter untuk Standard Library (biar Uvicorn juga JSON)
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.processors.JSONRenderer(), # <--- INI KUNCINYA (Output JSON)
        ],
    )

    # Handler ke Stdout
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    # Setup Root Logger
    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(log_level.upper())

    # Heningkan logger yang terlalu berisik (Opsional)
    logging.getLogger("uvicorn.error").handlers = [handler]
    logging.getLogger("uvicorn.access").handlers = [handler]
    
    # Pastikan uvicorn access log tidak double print
    logging.getLogger("uvicorn.access").propagate = False