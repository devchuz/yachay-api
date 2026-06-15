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
from contextlib import asynccontextmanager

import httpx
from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .agent import yachay_agent
from .core import clasificador, config, db


@asynccontextmanager
async def lifespan(app: FastAPI):
    clasificador.init()
    yachay_agent.init()
    print(f"[yachay] listo. Agente en modo: {yachay_agent.modo()} | Turso: {db.usando_turso()}")
    yield


app = FastAPI(title="Yachay UNCP", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)


# ---------- modelos ----------
class TextoIn(BaseModel):
    texto: str

class ChatIn(BaseModel):
    mensaje: str
    telefono: str = "51999000000"  # simula un remitente en pruebas

class NotificarIn(BaseModel):
    telefono: str
    codigo: str
    tipo: str = "formulario"
    formulario_url: str = ""   # ← el link que manda el dashboard

class ConvocatoriaIn(BaseModel):
    periodo: str
    fecha_inicio: str   # formato "2026-09-01"
    fecha_cierre: str
    estado: str = "abierta"


# ---------- ML directo ----------
@app.get("/health")
def health():
    return {"ok": True, "agente": yachay_agent.modo(), "turso": db.usando_turso()}

@app.post("/derivar")
def derivar(t: TextoIn):
    return clasificador.clasificar(t.texto)


# ---------- agente (prueba sin WhatsApp) ----------
@app.post("/chat")
def chat(c: ChatIn):
    return {"respuesta": yachay_agent.responder(c.mensaje, c.telefono)}


# ---------- REST para el dashboard ----------
@app.get("/solicitudes")
def listar(estado: str | None = None):
    # Lectura simple desde Turso (o memoria en fallback)
    c = db._get_client()
    if c:
        sql = "SELECT codigo, nombre_solicitante, comunidad, distrito, tipo_proyecto, descripcion, facultades_sugeridas, valencia, facultad_asignada, estado, creado_en FROM solicitudes"
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


# ---------- CONVOCATORIAS (plazos) ----------
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
    # upsert: crea o actualiza por periodo (PK)
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
    """La que el bot usa para validar el plazo de las solicitudes."""
    activa = db.convocatoria_activa()
    proxima = db.proxima_convocatoria() if not activa else None
    return {"activa": activa, "proxima": proxima}


# ---------- WEBHOOK WhatsApp (Evolution API) ----------
async def _enviar_whatsapp(numero: str, texto: str):
    if not config.EVOLUTION_URL:
        print(f"[wa-mock] a {numero}: {texto}")
        return
    async with httpx.AsyncClient(timeout=20) as cli:
        await cli.post(
            f"{config.EVOLUTION_URL}/message/sendText/{config.EVOLUTION_INSTANCE}",
            headers={"apikey": config.EVOLUTION_API_KEY},
            json={"number": numero, "text": texto},
        )


def _procesar_y_responder(telefono: str, texto: str):
    respuesta = yachay_agent.responder(texto, telefono)
    import asyncio
    asyncio.run(_enviar_whatsapp(telefono.split("@")[0], respuesta))


@app.post("/webhook/whatsapp")
async def webhook(req: Request, bg: BackgroundTasks):
    data = await req.json()
    # Evolution v2 manda event 'messages.upsert'
    if data.get("event") not in ("messages.upsert", "MESSAGES_UPSERT"):
        return {"ok": True}
    msg = data.get("data", {})
    key = msg.get("key", {})
    if key.get("fromMe"):
        return {"ok": True}  # evita responderse a sí mismo
    telefono = key.get("remoteJid", "")
    m = msg.get("message", {}) or {}
    texto = m.get("conversation") or m.get("extendedTextMessage", {}).get("text", "")
    if not texto:
        return {"ok": True}
    # Responder rápido el 200; procesar en background (evita timeout/reintentos)
    bg.add_task(_procesar_y_responder, telefono, texto)
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