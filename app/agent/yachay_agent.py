"""Agente Yachay. Usa LangGraph con Groq (o Gemini) si están configurados.
Si no hay API key o falta langgraph, cae a un modo regla simple
para poder probar el resto del sistema sin LLM."""
import os

from ..core import config, db
from ..tools import yachay_tools as T

SYSTEM_PROMPT = """Eres Yachay, el asistente virtual de Proyección Social de la Universidad
Nacional del Centro del Perú (UNCP). Atiendes a representantes de comunidades campesinas,
urbanas y gobiernos locales de Huancayo.

TONO:
- Español simple, cálido y respetuoso. Frases cortas, sin tecnicismos ni burocracia.
- Recuerda que muchos usuarios tienen poca experiencia digital: sé claro y paciente.

ENFOQUE HUMANO:
- Atiende como una persona amable de mesa de ayuda, no como una oficina fría.
- Muchas personas pueden escribir con errores, frases incompletas o audios transcritos. Interpreta con paciencia.
- No corrijas la forma de escribir del usuario. Concéntrate en entender su necesidad.
- Usa palabras cercanas: "te ayudo", "no te preocupes", "vamos paso a paso", "gracias por contarme".
- No uses lenguaje burocrático como "proceda", "solicitud recepcionada", "derivación administrativa" o "según normativa", salvo que sea necesario.
- Si falta un dato, pídelo con calma y explica para qué sirve.
- Si el usuario parece confundido, resume lo entendido y pregunta solo lo siguiente.
- Si el usuario tiene una necesidad urgente o sensible, responde con empatía y registra la solicitud sin prometer una solución inmediata.
- Nunca hagas sentir al usuario culpable por no saber usar tecnología o por no tener toda la información.

TIENES HERRAMIENTAS Y DEBES USARLAS (no respondas de memoria ni describas lo que harías,
ejecútalas):
- orientar_servicios: cuando pregunten qué apoyo ofrece la UNCP.
- derivar: cuando el usuario describa una necesidad, para saber qué facultad corresponde.
- crear_solicitud: para registrar una solicitud (solo con datos reales y completos).
- consultar_estado: cuando den un código UNCP-2026-XXXXX.
- consultar_por_dni: cuando el usuario quiera ver TODAS sus solicitudes pendientes y dé su DNI.
- consultar_convocatoria: cuando pregunten por plazos, fechas, hasta cuándo pueden postular
  o cuándo abre la convocatoria. NUNCA inventes fechas ni enlaces; usa SIEMPRE esta herramienta.

CÓMO REGISTRAR UNA SOLICITUD (pide UN dato por mensaje, en este orden):
1. Nombre del solicitante.
2. Comunidad o entidad.
3. DNI del solicitante (OBLIGATORIO, 8 dígitos).
4. Descripción de la necesidad.
(El número de contacto NO lo pidas: ya tenemos su número de WhatsApp.)

Reglas del registro:
- NO registres sin DNI. Si no lo dan, vuelve a pedirlo explicando que es obligatorio para
  registrar y para que luego pueda consultar sus solicitudes.
- Cuando tengas nombre, comunidad, DNI y descripción, confirma una sola vez con un resumen:
  "¿Registro tu solicitud con estos datos? Nombre: X, Comunidad: Y, DNI: Z, Necesidad: W"
- Si confirma, LLAMA a crear_solicitud INMEDIATAMENTE. No repitas "¿quieres que la registre?".
- La herramienta detecta sola si hay convocatoria abierta o no. No lo preguntes ni lo asumas tú.
- Si MODALIDAD es "convocatoria": el registro es formal. Dile que fue aceptada en la convocatoria
  activa, dale el código y el link. Dile que lo avisarás cuando haya avances.
- Si MODALIDAD es "voluntariado": PRIMERO avísale con claridad que Proyección Social cerró el
  registro formal de solicitudes en este momento (no hay convocatoria activa). LUEGO dile que
  igual registramos su solicitud como postulación a voluntariado. Dale el código y el link.
  Nunca lo presentes como rechazo; es una vía alternativa válida. El dashboard interno lo marca
  como voluntariado para que la secretaría lo gestione diferenciado.

VALIDACIÓN (muy importante):
- NUNCA inventes datos ni uses placeholders como "tu nombre", "tu DNI", "Juan Pérez" por defecto.
  Usa SOLO lo que el usuario escribió de verdad.
- Si falta el nombre, la comunidad, el DNI o la descripción reales, PREGÚNTALOS. No registres a medias.
- Si crear_solicitud devuelve un error de datos faltantes, pídele al usuario lo que falta y reintenta.

CONSULTA DE ESTADO:
- Si dan un código (UNCP-2026-XXXXX), usa consultar_estado. NUNCA llames consultar_estado
  sin que el usuario haya dado el código explícitamente. Si no lo tienes, pídelo primero.
- Si quieren ver sus solicitudes pendientes pero no recuerdan el código, pídeles el DNI y usa
  consultar_por_dni.
- Si no se encuentra nada, dilo con claridad y ofrece registrar una nueva solicitud.
- Si la respuesta incluye un encargado asignado, menciónalo con nombre.

FORMATO PARA WHATSAPP (muy importante):
- Mensajes CORTOS: máximo 4-5 líneas por mensaje. Si hay más info, divide en partes naturales.
- Escribe la URL del link tal cual, SIN Markdown ni corchetes. Nunca uses [texto](url).
- Para negrita usa *un asterisco* a cada lado.
- Usa saltos de línea y, con moderación, emojis claros (✅ 📌 📍 🔎).
- Nunca respondas con párrafos largos. Prefiere frases sueltas con saltos de línea.
- Una idea por línea. Si vas a listar cosas, usa guion o número, no bloques de texto.

LÍMITES:
- Nunca repitas la misma pregunta dos veces; si el usuario ya dio un dato, avanza al siguiente.
- Nunca inventes servicios, oficinas ni plazos. Nunca pidas dinero ni claves. El servicio es gratuito.
- La facultad la SUGIERE el sistema; la decisión final es de la Unidad. No prometas facultad definitiva."""


PLANTILLA_BIENVENIDA = """¡Hola! 👋 Soy *Yachay*, el asistente de Proyección Social de la *UNCP*.

Te ayudo a pedir apoyo para tu comunidad sin que viajes a Huancayo. Puedo:
✅ Orientarte sobre el apoyo que ofrece la UNCP
✅ Registrar tu solicitud
✅ Darte el estado de una solicitud

Para registrar una solicitud necesito:
- Tu *nombre*
- Tu *comunidad*
- Tu *DNI* (8 dígitos)
- Qué *necesidad* tiene tu comunidad

Puedes escribirme con tus palabras. ¿Empezamos?"""


def _es_saludo(mensaje: str) -> bool:
    m = mensaje.lower().strip()
    return any(p in m for p in ["hola", "buenas", "buenos", "buen día", "buen dia"]) or len(m) < 6



def _build_llm():
    """Elige el proveedor de LLM disponible: Groq primero, luego Gemini."""
    if os.getenv("GROQ_API_KEY"):
        from langchain_groq import ChatGroq
        return ChatGroq(
            model="openai/gpt-oss-20b",
            api_key=os.getenv("GROQ_API_KEY"),
            temperature=0,
        )
    from langchain_google_genai import ChatGoogleGenerativeAI
    return ChatGoogleGenerativeAI(
        model=config.GEMINI_MODEL,
        google_api_key=config.GEMINI_API_KEY,
    )


def _build_langgraph_agent():
    from langchain_core.tools import tool
    from langgraph.checkpoint.memory import MemorySaver
    from langgraph.prebuilt import create_react_agent

    @tool
    def orientar_servicios() -> str:
        """Lista los tipos de apoyo que ofrece la UNCP."""
        return T.orientar_servicios()

    @tool
    def derivar(descripcion: str) -> str:
        """Sugiere la facultad responsable de una necesidad y por qué."""
        r = T.derivar(descripcion)
        return f"Sugerencia: {r['facultad_top']} (confianza {r['score']}). " \
               f"Términos clave: {', '.join(t['termino'] for t in r['explicacion'])}"

    @tool
    def crear_solicitud(nombre: str, comunidad: str, descripcion: str,
                        dni: str = "", contacto: str = "", tipo_proyecto: str = "otro") -> str:
        """Registra una solicitud de proyección social. Úsala solo con datos REALES del usuario,
        nunca con placeholders ni datos inventados. La herramienta detecta automáticamente si
        hay convocatoria activa o no, y registra según corresponda."""
        r = T.crear_solicitud(_ctx.get("telefono", ""), nombre, comunidad,
                              descripcion, dni, contacto, tipo_proyecto)
        if r.get("error"):
            return r["error"] + " Pídele al usuario los datos que faltan."

        modalidad = r.get("modalidad", "convocatoria")
        nota = r.get("nota_plazo", "")
        codigo = r["codigo"]
        link = r["link"]
        periodo = r.get("periodo_conv", "")

        if modalidad == "convocatoria":
            # Registro formal dentro de convocatoria
            return (
                f"MODALIDAD:convocatoria PERIODO:{periodo} "
                f"CODIGO:{codigo} LINK:{link} "
                f"NOTA:{nota} "
                f"INSTRUCCION: Dile al usuario que su solicitud fue registrada formalmente "
                f"dentro de la convocatoria {periodo}. Entrégale el código {codigo} y el link "
                f"{link}. Dile que será evaluada por Proyección Social y que lo avisarás por este chat."
            )
        else:
            # Registro como voluntariado (fuera de convocatoria)
            return (
                f"MODALIDAD:voluntariado "
                f"CODIGO:{codigo} LINK:{link} "
                f"NOTA:{nota} "
                f"INSTRUCCION: Primero explícale con amabilidad que en este momento Proyección "
                f"Social cerró el registro formal. Luego dile que SÍ se registró su solicitud "
                f"como postulación a voluntariado con código {codigo}. Entrégale también el link "
                f"{link}. No lo presentes como rechazo, es una vía alternativa válida."
            )

    @tool
    def consultar_estado(codigo: str) -> str:
        """Consulta el estado de una solicitud por su código (formato UNCP-2026-XXXXX)."""
        r = T.consultar_estado(codigo)
        if not r:
            return "No encontré esa solicitud. Revisa el código."
        return f"Solicitud {r['codigo']} ({r.get('comunidad', '')}): estado {r['estado']}."

    @tool
    def consultar_por_dni(dni: str) -> str:
        """Lista las solicitudes abiertas (no cerradas) de un usuario por su DNI.
        Úsala cuando el usuario quiera ver sus solicitudes pendientes y dé su DNI."""
        solicitudes = T.consultar_por_dni(dni)
        if not solicitudes:
            return f"No encontré solicitudes abiertas con el DNI {dni}."
        lineas = [
            f"- {s['codigo']} ({s['tipo_proyecto'] or 'solicitud'}): estado {s['estado']}"
            for s in solicitudes
        ]
        return (f"Solicitudes abiertas del DNI {dni}:\n" + "\n".join(lineas) +
                "\nEntrega esta lista al usuario de forma clara.")

    @tool
    def consultar_convocatoria() -> str:
        """Consulta las fechas de la convocatoria de proyección social: si está abierta hoy
        y hasta cuándo, o cuándo abre la próxima. Úsala SIEMPRE que el usuario pregunte por
        plazos, fechas, cuándo puede postular o hasta cuándo hay tiempo."""
        activa = db.convocatoria_activa()
        if activa:
            return (f"Hay una convocatoria ABIERTA: periodo {activa['periodo']}, "
                    f"desde {activa['inicio']} hasta {activa['cierre']}. "
                    f"El usuario puede registrar su solicitud dentro de este plazo.")
        prox = db.proxima_convocatoria()
        if prox:
            return (f"No hay convocatoria abierta ahora mismo. La próxima ({prox['periodo']}) "
                    f"abre el {prox['inicio']}. Mientras tanto, las solicitudes se registran "
                    f"como postulación a voluntariado.")
        return ("No hay convocatorias programadas por el momento. Las solicitudes que lleguen "
                "se registran como voluntariado.")

    llm = _build_llm()
    return create_react_agent(
        llm,
        [orientar_servicios, derivar, crear_solicitud, consultar_estado, consultar_por_dni, consultar_convocatoria],
        checkpointer=MemorySaver(),
        prompt=SYSTEM_PROMPT,
    )



_ctx = {}
_agent = None
_modo = "fallback"


def init():
    global _agent, _modo
    if os.getenv("GROQ_API_KEY") or config.GEMINI_API_KEY:
        try:
            _agent = _build_langgraph_agent()
            _modo = "langgraph"
            proveedor = "Groq" if os.getenv("GROQ_API_KEY") else "Gemini"
            print(f"[agente] LangGraph activo con {proveedor}.")
        except Exception as e:  # noqa
            print(f"[agente] LangGraph no disponible ({e}); usando fallback.")
            _modo = "fallback"
    else:
        print("[agente] Sin API key de LLM; usando fallback de reglas.")


def modo() -> str:
    return _modo



def responder(mensaje: str, telefono: str) -> str:
    """Punto de entrada único. Devuelve la respuesta de texto para el usuario."""
    # ¿Primer contacto? (sin historial previo) → plantilla de bienvenida
    historial_previo = db.historial_conversacion(telefono, limite=1)
    es_primer_contacto = len(historial_previo) == 0

    db.guardar_mensaje(telefono, "user", mensaje)

    if es_primer_contacto and _es_saludo(mensaje):
        respuesta = PLANTILLA_BIENVENIDA
        db.guardar_mensaje(telefono, "assistant", respuesta)
        return respuesta

    if _modo == "langgraph" and _agent is not None:
        _ctx["telefono"] = telefono
        try:
            out = _agent.invoke(
                {"messages": [{"role": "user", "content": mensaje}]},
                config={"configurable": {"thread_id": telefono}},
            )
            respuesta = out["messages"][-1].content
        except Exception as e:  # noqa
            print(f"[agente] error en invoke ({e}); usando fallback.")
            respuesta = _fallback(mensaje, telefono)
    else:
        respuesta = _fallback(mensaje, telefono)

    respuesta = _recortar_para_whatsapp(respuesta)
    db.guardar_mensaje(telefono, "assistant", respuesta)
    return respuesta


def _recortar_para_whatsapp(texto: str, max_chars: int = 1000) -> str:
    """Asegura que el mensaje no sea demasiado largo para WhatsApp.
    Si supera max_chars, corta en el último salto de línea completo.
    """
    if len(texto) <= max_chars:
        return texto
    # Buscar el último salto de línea antes del límite
    corte = texto.rfind("\n", 0, max_chars)
    if corte == -1:
        corte = max_chars
    return texto[:corte] + "\n\n_(Escríbeme si quieres más detalles.)_"


def _fallback(mensaje: str, telefono: str) -> str:
    """Modo sin LLM: reglas mínimas para demostrar el flujo y el clasificador."""
    m = mensaje.lower().strip()
    if any(p in m for p in ["hola", "buenas", "buenos"]):
        return ("¡Hola! Soy Yachay, asistente de Proyección Social de la UNCP. "
                "Puedo orientarte sobre el apoyo disponible, registrar tu solicitud "
                "o darte el estado de una solicitud. ¿Qué necesitas?")
    if "uncp-2026" in m:
        cod = next((w.upper() for w in mensaje.split() if "UNCP-2026" in w.upper()), "")
        r = T.consultar_estado(cod)
        if r:
            return f"Tu solicitud {r['codigo']} está en estado: {r['estado']}."
        return "No encontré esa solicitud. Revisa el código (formato UNCP-2026-00000)."
    if len(m.split()) <= 6 and any(p in m for p in ["qué apoyo", "que apoyo", "qué puedo", "que puedo", "qué servicios", "que servicios", "qué ofrecen", "que ofrecen"]):
        return T.orientar_servicios() + "\n\nSi quieres registrar una solicitud, cuéntame tu necesidad."
    r = T.derivar(mensaje)
    terms = ", ".join(t["termino"] for t in r["explicacion"][:3])
    return (f"Entiendo tu necesidad. Esto correspondería a *{r['facultad_top']}* "
            f"(por: {terms}). Para registrarla dime tu nombre y tu comunidad.")