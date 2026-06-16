"""Yachay UNCP — backend principal (FastAPI).
- /derivar            : clasificador (prueba directa del ML)
- /chat               : probar el agente por consola/navegador (sin WhatsApp)
- /solicitudes        : lista para el dashboard
- /seguimiento/{cod}  : detalle + estado
- /notificar          : envía WhatsApp según el estado (formulario/derivada/admitido/rechazado)
- /convocatorias      : listar (GET) y crear/editar (POST) plazos
- /convocatoria-activa: la que el bot usa para validar el plazo
- /webhook/whatsapp   : entrada de Evolution API
"""
import asyncio
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json 
from .agent import yachay_agent
from .core import clasificador, config, db
 
# ── Semáforo: máximo N mensajes procesándose al mismo tiempo ──────────────────
# Con Groq free tier y 1 CPU, 3-5 es un buen límite.
# Sube a 8-10 si tienes Groq paid o usas Gemini con más cuota.
_SEM = asyncio.Semaphore(4)
 
# Cola FIFO simple en memoria (por número de teléfono)
# Evita que el mismo usuario mande 5 mensajes y los proceses out-of-order.
_cola_por_telefono: dict[str, asyncio.Queue] = {}
_worker_activo: dict[str, bool] = {}
 
 
@asynccontextmanager
async def lifespan(app: FastAPI):
    clasificador.init()
    yachay_agent.init()
    print(f"[yachay] listo. Agente en modo: {yachay_agent.modo()} | Turso: {db.usando_turso()}")
    yield
    # Limpieza al apagar
    _cola_por_telefono.clear()
    _worker_activo.clear()
 
 
app = FastAPI(title="Yachay UNCP", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)
 
 
# ---------- modelos ----------
class TextoIn(BaseModel):
    texto: str
 
class ChatIn(BaseModel):
    mensaje: str
    telefono: str = "51999000000"
 
class NotificarIn(BaseModel):
    telefono: str
    codigo: str
    tipo: str = "formulario"
    formulario_url: str = ""
 
class ConvocatoriaIn(BaseModel):
    periodo: str
    fecha_inicio: str
    fecha_cierre: str
    estado: str = "abierta"
 
 
# ---------- envío WhatsApp (siempre async) ------------------------------------
async def _enviar_whatsapp(numero: str, texto: str):
    if not config.EVOLUTION_URL:
        print(f"[wa-mock] a {numero}: {texto}")
        return
    try:
        async with httpx.AsyncClient(timeout=20) as cli:
            await cli.post(
                f"{config.EVOLUTION_URL}/message/sendText/{config.EVOLUTION_INSTANCE}",
                headers={"apikey": config.EVOLUTION_API_KEY},
                json={"number": numero, "text": texto},
            )
    except Exception as e:
        print(f"[wa] error enviando a {numero}: {e}")
 
 
# ---------- procesamiento con semáforo ----------------------------------------
async def _procesar_mensaje(telefono: str, texto: str):
    """Corre el agente en un thread pool (no bloquea el event loop)
    y limita la concurrencia con el semáforo global."""
    async with _SEM:
        loop = asyncio.get_event_loop()
        try:
            # run_in_executor: el LLM/clasificador corre en thread sin bloquear asyncio
            respuesta = await loop.run_in_executor(
                None,  # usa el ThreadPoolExecutor por defecto
                yachay_agent.responder,
                texto,
                telefono,
            )
        except Exception as e:
            print(f"[agente] error procesando {telefono}: {e}")
            respuesta = (
                "Hubo un problema al procesar tu mensaje. "
                "Por favor intenta en unos segundos. 🙏"
            )
        await _enviar_whatsapp(telefono.split("@")[0], respuesta)
 
 
# ---------- worker FIFO por teléfono ------------------------------------------
async def _worker_telefono(telefono: str):
    """Consume mensajes de un mismo número en orden, uno por uno.
    Esto evita respuestas desordenadas si el usuario escribe rápido."""
    cola = _cola_por_telefono[telefono]
    while True:
        try:
            texto = await asyncio.wait_for(cola.get(), timeout=60.0)
        except asyncio.TimeoutError:
            # Sin mensajes en 60s: terminamos el worker (se recreará al llegar uno nuevo)
            _worker_activo.pop(telefono, None)
            _cola_por_telefono.pop(telefono, None)
            break
        await _procesar_mensaje(telefono, texto)
        cola.task_done()
 
 
async def _encolar(telefono: str, texto: str):
    """Añade el mensaje a la cola del teléfono y arranca el worker si no existe."""
    if telefono not in _cola_por_telefono:
        _cola_por_telefono[telefono] = asyncio.Queue(maxsize=10)
 
    cola = _cola_por_telefono[telefono]
 
    # Cola llena (usuario spammeando): ignorar sin crashear
    if cola.full():
        print(f"[cola] {telefono} tiene la cola llena, mensaje descartado")
        return
 
    await cola.put(texto)
 
    if not _worker_activo.get(telefono):
        _worker_activo[telefono] = True
        asyncio.create_task(_worker_telefono(telefono))
 
 
# ---------- endpoints ----------------------------------------------------------
@app.get("/health")
def health():
    return {
        "ok": True,
        "agente": yachay_agent.modo(),
        "turso": db.usando_turso(),
        "colas_activas": len(_cola_por_telefono),
        "sem_disponible": _SEM._value,  # cuántos slots libres quedan
    }
 
 
@app.post("/derivar")
def derivar(t: TextoIn):
    return clasificador.clasificar(t.texto)
 
 
@app.post("/chat")
def chat(c: ChatIn):
    return {"respuesta": yachay_agent.responder(c.mensaje, c.telefono)}
 
 
@app.get("/solicitudes")
def listar(estado: str | None = None):
    c = db._get_client()
    if c:
        sql = ("SELECT codigo, nombre_solicitante, comunidad, distrito, tipo_proyecto, "
               "descripcion, facultades_sugeridas, valencia, facultad_asignada, estado, creado_en "
               "FROM solicitudes")
        args = []
        if estado:
            sql += " WHERE estado = ?"; args = [estado]
        sql += " ORDER BY creado_en DESC"
        rs = c.execute(sql, args)
        cols = ["codigo","nombre_solicitante","comunidad","distrito","tipo_proyecto",
                "descripcion","facultades_sugeridas","valencia","facultad_asignada","estado","creado_en"]
        sols = [dict(zip(cols, r)) for r in rs.rows]
        return {"solicitudes": sols, "total": len(sols)}
    return {"solicitudes": db._mem["solicitudes"], "total": len(db._mem["solicitudes"])}
 
 
@app.get("/seguimiento/{codigo}")
def seguimiento(codigo: str):
    r = db.consultar_estado(codigo)
    if not r:
        return {"error": "Solicitud no encontrada"}
    return r
 
 
@app.get("/convocatorias")
def listar_convocatorias():
    c = db._get_client()
    if c:
        rs = c.execute("SELECT periodo, fecha_inicio, fecha_cierre, estado FROM convocatorias ORDER BY fecha_inicio DESC")
        cols = ["periodo", "fecha_inicio", "fecha_cierre", "estado"]
        return {"convocatorias": [dict(zip(cols, r)) for r in rs.rows]}
    return {"convocatorias": []}
 
 
@app.post("/convocatorias")
def guardar_convocatoria(conv: ConvocatoriaIn):
    c = db._get_client()
    if not c:
        return {"error": "Sin conexión a base de datos"}
    c.execute(
        """INSERT INTO convocatorias (periodo, fecha_inicio, fecha_cierre, estado)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(periodo) DO UPDATE SET
             fecha_inicio = excluded.fecha_inicio,
             fecha_cierre = excluded.fecha_cierre,
             estado = excluded.estado""",
        [conv.periodo, conv.fecha_inicio, conv.fecha_cierre, conv.estado],
    )
    return {"ok": True, "periodo": conv.periodo}
 
 
@app.get("/convocatoria-activa")
def get_convocatoria_activa():
    activa = db.convocatoria_activa()
    proxima = db.proxima_convocatoria() if not activa else None
    return {"activa": activa, "proxima": proxima}
 
 
@app.post("/webhook/whatsapp")
async def webhook(req: Request):
    # Guard contra body vacío (health checks de HF Spaces y proxies)
    body = await req.body()
    if not body:
        return {"ok": True}
    
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return {"ok": True}

    if data.get("event") not in ("messages.upsert", "MESSAGES_UPSERT"):
        return {"ok": True}
    msg = data.get("data", {})
    key = msg.get("key", {})
    if key.get("fromMe"):
        return {"ok": True}
    telefono = key.get("remoteJid", "")
    m = msg.get("message", {}) or {}
    texto = m.get("conversation") or m.get("extendedTextMessage", {}).get("text", "")
    if not texto:
        return {"ok": True}

    await _encolar(telefono, texto)
    return {"ok": True}
 
@app.post("/notificar")
async def notificar(n: NotificarIn):
    link_seguimiento = f"{config.SEGUIMIENTO_URL}/seguimiento/{n.codigo}"
 
    if n.tipo == "formulario":
        link_form = n.formulario_url or config.FORMULARIO_URL
        texto = (f"📋 Hola, tu solicitud *{n.codigo}* necesita información adicional.\n\n"
                 f"Por favor completa este formulario para continuar:\n{link_form}\n\n"
                 f"📍 También puedes ver el estado de tu solicitud aquí:\n{link_seguimiento}\n\n"
                 f"Una vez completado, seguiremos con tu trámite. ¡Gracias!")
    elif n.tipo == "derivada":
        texto = (f"✅ ¡Buenas noticias! Tu solicitud *{n.codigo}* fue derivada a una facultad "
                 f"y está en el último tramo de evaluación.\n\n"
                 f"📍 Sigue su avance aquí:\n{link_seguimiento}")
    elif n.tipo == "admitido":
        texto = (f"🎉 ¡Felicitaciones! Tu solicitud *{n.codigo}* fue *ADMITIDA*.\n\n"
                 f"La UNCP se pondrá en contacto contigo para coordinar las actividades de proyección social.\n\n"
                 f"📍 Detalle:\n{link_seguimiento}")
    elif n.tipo == "rechazado":
        texto = (f"Tu solicitud *{n.codigo}* no pudo ser admitida en esta convocatoria.\n\n"
                 f"Te animamos a volver a postular en la próxima. ¡Gracias por tu interés!\n\n"
                 f"📍 Detalle:\n{link_seguimiento}")
    else:
        texto = f"Tu solicitud *{n.codigo}* tuvo una actualización.\n\n📍 {link_seguimiento}"
 
    await _enviar_whatsapp(n.telefono, texto)
    return {"ok": True}