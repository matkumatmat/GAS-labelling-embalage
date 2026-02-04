from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from collections import deque
from logging.handlers import TimedRotatingFileHandler
import logging
import sys
import structlog
import uuid
import time
import json
import os
import asyncio

# --- 0. GLOBAL VARS (Jembatan Sync ke Async) ---
# Kita butuh ini buat nampung log dari structlog (sync) sebelum dikirim ke websocket (async)
log_queue = None 

# --- 1. CONNECTION MANAGER (Buat Ngatur WebSocket) ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        # Kirim ke semua client yang connect
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except:
                pass # Kalo ada yang putus di tengah jalan, biarin

manager = ConnectionManager()

# --- 2. CUSTOM LOG HANDLER (Penculik Log) ---
class WebSocketLogHandler(logging.Handler):
    """
    Handler ini tugasnya 'nyulik' log yang udah di-format jadi JSON,
    terus dimasukin ke antrian (queue) biar bisa dikirim WebSocket.
    """
    def emit(self, record):
        try:
            # Format log jadi string (JSON karena formatter kita JSON)
            msg = self.format(record)
            
            # Masukin ke queue ASYNC (thread-safe)
            if log_queue is not None:
                loop = asyncio.get_running_loop()
                if loop.is_running():
                    loop.call_soon_threadsafe(log_queue.put_nowait, msg)
        except Exception:
            self.handleError(record)

# --- 3. SETUP LOGGING (TERMINAL + FILE + WEBSOCKET) ---
def setup_logging():
    os.makedirs("logs", exist_ok=True)

    # Processor urutan log
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    # Config Structlog
    structlog.configure(
        processors=processors + [structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # -- Handler 1: Terminal (Warna-warni) --
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(structlog.stdlib.ProcessorFormatter(
        processor=structlog.dev.ConsoleRenderer(colors=True),
        foreign_pre_chain=processors,
    ))

    # -- Handler 2: File (JSON Lengkap) --
    file_handler = TimedRotatingFileHandler("logs/app.log", when="midnight", interval=1, backupCount=7, encoding="utf-8")
    file_handler.setFormatter(structlog.stdlib.ProcessorFormatter(
        processor=structlog.processors.JSONRenderer(),
        foreign_pre_chain=processors,
    ))

    # -- Handler 3: WebSocket (JSON Lengkap juga) --
    ws_handler = WebSocketLogHandler()
    ws_handler.setFormatter(structlog.stdlib.ProcessorFormatter(
        processor=structlog.processors.JSONRenderer(),
        foreign_pre_chain=processors,
    ))

    # Pasang ke Root Logger
    root_logger = logging.getLogger()
    root_logger.handlers = [console_handler, file_handler, ws_handler]
    root_logger.setLevel(logging.INFO)

    # Uvicorn biar ikut format kita
    logging.getLogger("uvicorn.access").handlers = root_logger.handlers
    logging.getLogger("uvicorn.error").handlers = root_logger.handlers
    logging.getLogger("uvicorn.access").propagate = False

# PANGGIL SETUP
setup_logging()
logger = structlog.get_logger()

# --- 4. APLIKASI UTAMA ---
from infrastructure.http.proxy_router import router as proxy_router

app = FastAPI(title="WMS Hybrid Host", version="3.0.0")

# Background Task buat Broadcast Log
async def log_broadcaster():
    """Worker yang mindahin log dari Queue -> WebSocket"""
    while True:
        # Tunggu log baru di queue
        log_msg = await log_queue.get()
        # Kirim ke semua browser
        await manager.broadcast(log_msg)

@app.on_event("startup")
async def startup_event():
    global log_queue
    # Init queue pas startup (karena butuh loop async)
    log_queue = asyncio.Queue()
    # Jalanin worker di background
    asyncio.create_task(log_broadcaster())
    
    logger.info("app_startup", status="ready", mode="websocket_enabled")

# Middleware Log Request
@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        request_id=request_id,
        path=request.url.path,
        method=request.method,
        client_ip=request.client.host
    )
    
    start_time = time.perf_counter()
    response = await call_next(request)
    process_time = time.perf_counter() - start_time
    
    # Filter log sampah (biar gak infinite loop log websocket)
    if request.url.path not in ["/", "/logs", "/favicon.ico"] and not request.url.path.startswith("/ws"):
        logger.info("http_request", status_code=response.status_code, time=f"{process_time:.4f}s")
        
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(proxy_router, prefix="/api/proxy")

@app.get("/")
def health_check():
    return {"status": "online"}

# --- 5. ENDPOINT WEBSOCKET ---
@app.websocket("/ws/logs")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Kita cuma push data ke client, gak perlu baca dari client
            # Tapi await receive biar koneksi tetep hold
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# --- 5. UI GLASSMORPHISM MODERN ---
@app.get("/logs", response_class=HTMLResponse)
async def view_logs(request: Request):
    # Setup Data Awal
    history_logs = []
    log_file = "logs/app.log"
    status_msg = "" # <--- INI FIX NYA! Variabel didefinisikan dulu.

    if os.path.exists(log_file):
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                lines = deque(f, maxlen=50)
                for line in lines:
                    if line.strip(): history_logs.append(line.strip())
        except Exception as e:
            status_msg = f'<div class="mb-4 p-4 bg-red-500/20 border border-red-500/50 rounded-lg text-red-200 text-sm">Error reading log file: {e}</div>'
    else:
        status_msg = '<div class="mb-4 p-4 bg-amber-500/20 border border-amber-500/50 rounded-lg text-amber-200 text-sm">Log file not found yet. Waiting for activity...</div>'
    
    initial_data = "[" + ",".join(history_logs) + "]"
    ws_scheme = "ws" if request.url.scheme == "http" else "wss"
    ws_url = f"{ws_scheme}://{request.url.netloc}/ws/logs"

    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>WMS Command Center</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600&family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">
        <script>
            tailwind.config = {{
                theme: {{
                    extend: {{
                        fontFamily: {{ sans: ['Inter', 'sans-serif'], mono: ['JetBrains Mono', 'monospace'] }},
                        colors: {{ dark: '#0f172a', card: '#1e293b' }}
                    }}
                }}
            }}
        </script>
        <style>
            body {{ background-color: #0f172a; color: #e2e8f0; }}
            .glass {{ background: rgba(30, 41, 59, 0.7); backdrop-filter: blur(10px); border: 1px solid rgba(255, 255, 255, 0.1); }}
            .log-row {{ transition: all 0.2s ease; border-left: 3px solid transparent; }}
            .log-row:hover {{ background: rgba(255,255,255,0.03); }}
            @keyframes slideIn {{ from {{ opacity: 0; transform: translateY(-10px); }} to {{ opacity: 1; transform: translateY(0); }} }}
            .new-log {{ animation: slideIn 0.3s ease-out forwards; }}
            .pulse {{ animation: pulse-green 2s infinite; }}
            @keyframes pulse-green {{
                0% {{ box-shadow: 0 0 0 0 rgba(52, 211, 153, 0.7); }}
                70% {{ box-shadow: 0 0 0 10px rgba(52, 211, 153, 0); }}
                100% {{ box-shadow: 0 0 0 0 rgba(52, 211, 153, 0); }}
            }}
        </style>
    </head>
    <body class="min-h-screen p-4 md:p-8 font-sans selection:bg-cyan-500/30">

        <header class="max-w-7xl mx-auto mb-6 flex justify-between items-center glass p-4 rounded-2xl sticky top-4 z-50 shadow-2xl">
            <div class="flex items-center gap-4">
                <div class="bg-indigo-500/20 p-2 rounded-xl border border-indigo-500/30">
                    <svg class="w-6 h-6 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"></path></svg>
                </div>
                <div>
                    <h1 class="text-xl font-bold text-white tracking-tight">WMS <span class="text-indigo-400">HOST</span></h1>
                    <div class="flex items-center gap-2 text-xs text-slate-400 font-mono">
                        <span class="text-emerald-400">● Live</span>
                        <span>{log_file}</span>
                    </div>
                </div>
            </div>
            <div class="flex items-center gap-3">
                <div class="flex items-center gap-2 px-3 py-1.5 rounded-full bg-slate-900/50 border border-slate-700">
                    <div id="status-dot" class="w-2 h-2 rounded-full bg-red-500"></div>
                    <span id="status-text" class="text-[10px] font-bold text-slate-400 uppercase tracking-widest">OFFLINE</span>
                </div>
                <button onclick="clearLogs()" class="p-2 hover:bg-slate-700/50 rounded-lg text-slate-400 hover:text-white transition">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path></svg>
                </button>
            </div>
        </header>

        {status_msg}

        <main class="max-w-7xl mx-auto glass rounded-2xl overflow-hidden shadow-2xl min-h-[600px]">
            <div class="overflow-x-auto">
                <table class="w-full text-left">
                    <thead>
                        <tr class="text-xs font-bold text-slate-400 uppercase bg-slate-900/50 border-b border-slate-700/50">
                            <th class="px-6 py-4 w-32">Time</th>
                            <th class="px-6 py-4 w-24">Level</th>
                            <th class="px-6 py-4 w-48">Event</th>
                            <th class="px-6 py-4">Payload</th>
                        </tr>
                    </thead>
                    <tbody id="log-table" class="font-mono text-sm divide-y divide-slate-800/50"></tbody>
                </table>
            </div>
            <div id="empty-state" class="hidden flex flex-col items-center justify-center py-20 text-slate-600">
                <p class="text-sm">Waiting for incoming logs...</p>
            </div>
        </main>

        <script>
            const initialLogs = {initial_data};
            const tableBody = document.getElementById('log-table');
            const statusDot = document.getElementById('status-dot');
            const statusText = document.getElementById('status-text');
            const emptyState = document.getElementById('empty-state');
            
            function addLog(log) {{
                emptyState.classList.add('hidden');
                const tr = document.createElement('tr');
                tr.className = "log-row new-log group";
                
                const ts = log.timestamp ? log.timestamp.split('T')[1].split('.')[0] : "-";
                let lvl = (log.level || "info").toUpperCase();
                const evt = log.event || "-";
                
                const details = {{...log}};
                delete details.timestamp; delete details.level; delete details.event; delete details.logger;
                let detailsStr = JSON.stringify(details).replace(/[\"{{}}]/g, "").replace(/,/g, ", ");

                // Badges
                let badgeClass = "bg-sky-500/10 text-sky-400 border-sky-500/20";
                let rowBorder = "transparent";
                if (lvl.includes("ERR") || lvl.includes("FAIL")) {{
                    badgeClass = "bg-rose-500/10 text-rose-400 border-rose-500/20";
                    rowBorder = "#f43f5e";
                }} else if (lvl.includes("WARN")) {{
                    badgeClass = "bg-amber-500/10 text-amber-400 border-amber-500/20";
                    rowBorder = "#f59e0b";
                }}
                tr.style.borderLeftColor = rowBorder;

                tr.innerHTML = `
                    <td class="px-6 py-3 text-slate-500 whitespace-nowrap">${{ts}}</td>
                    <td class="px-6 py-3"><span class="px-2 py-0.5 rounded text-[10px] font-bold border ${{badgeClass}}">${{lvl}}</span></td>
                    <td class="px-6 py-3 font-semibold text-slate-300">${{evt}}</td>
                    <td class="px-6 py-3 text-xs text-slate-500 group-hover:text-slate-400 transition-colors break-all">${{detailsStr}}</td>
                `;
                
                tableBody.insertBefore(tr, tableBody.firstChild);
                if (tableBody.children.length > 100) tableBody.removeChild(tableBody.lastChild);
            }}

            function clearLogs() {{ tableBody.innerHTML = ""; emptyState.classList.remove('hidden'); }}
            
            if (initialLogs.length > 0) initialLogs.forEach(log => addLog(log));
            else emptyState.classList.remove('hidden');

            function connect() {{
                const ws = new WebSocket("{ws_url}");
                ws.onopen = () => {{
                    statusText.innerText = "ONLINE"; statusText.className = "text-[10px] font-bold text-emerald-400 uppercase tracking-widest";
                    statusDot.className = "w-2 h-2 rounded-full bg-emerald-400 pulse shadow-[0_0_12px_#34d399]";
                }};
                ws.onmessage = (e) => {{ try {{ addLog(JSON.parse(e.data)); }} catch(err){{}} }};
                ws.onclose = () => {{
                    statusText.innerText = "RECONNECTING"; statusText.className = "text-[10px] font-bold text-amber-500 uppercase tracking-widest";
                    statusDot.className = "w-2 h-2 rounded-full bg-amber-500 animate-bounce";
                    setTimeout(connect, 3000);
                }};
            }}
            connect();
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)