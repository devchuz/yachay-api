"""Acceso a Turso (libSQL). Solicitudes, historial de estados y memoria de conversación.

Si no hay credenciales de Turso, usa un fallback en memoria para correr local sin cuenta.
"""

import json
import re
from datetime import date, datetime

from . import config

_client = None

_BASE_SEQ = 124

_mem = {
    "solicitudes": [],
    "historial": [],
    "conversaciones": [],
    "convocatorias": [],
    "seq": _BASE_SEQ,
}


def _get_client():
    global _client

    if _client is None and config.TURSO_DATABASE_URL and config.TURSO_AUTH_TOKEN:
        import libsql_client

        url = (
            config.TURSO_DATABASE_URL
            .replace("libsql://", "https://")
            .replace("wss://", "https://")
        )

        _client = libsql_client.create_client_sync(
            url=url,
            auth_token=config.TURSO_AUTH_TOKEN,
        )

    return _client


def usando_turso() -> bool:
    return _get_client() is not None


def _extraer_numero_codigo(codigo: str) -> int:
    """
    Extrae el número final de códigos tipo:
    UNCP-2026-00125
    """
    if not codigo:
        return _BASE_SEQ

    match = re.search(r"UNCP-2026-(\d+)$", str(codigo).strip().upper())
    if not match:
        return _BASE_SEQ

    return int(match.group(1))


def _nuevo_codigo() -> str:
    """
    Genera un código correlativo.

    Mejor que usar COUNT(*), porque si borras solicitudes,
    COUNT puede generar códigos repetidos.
    """
    c = _get_client()

    if c:
        rs = c.execute(
            """
            SELECT codigo
            FROM solicitudes
            WHERE codigo LIKE 'UNCP-2026-%'
            ORDER BY codigo DESC
            LIMIT 1
            """
        )

        if rs.rows:
            ultimo_codigo = rs.rows[0][0]
            n = _extraer_numero_codigo(ultimo_codigo) + 1
        else:
            n = _BASE_SEQ + 1

    else:
        _mem["seq"] += 1
        n = _mem["seq"]

    return f"UNCP-2026-{n:05d}"


def _normalizar_codigo(codigo: str) -> str:
    return str(codigo or "").strip().upper()


def _nombre_solicitante(datos: dict) -> str:
    return (
        datos.get("nombre")
        or datos.get("nombre_solicitante")
        or "solicitante"
    )


def _mensaje_confirmacion_solicitud(
    *,
    nombre: str,
    codigo: str,
    comunidad: str,
    tipo_proyecto: str,
    estado: str = "recibida",
) -> str:
    comunidad_txt = comunidad or "No especificada"
    tipo_txt = tipo_proyecto or "Solicitud de proyección social"
    base_url = config.SEGUIMIENTO_URL  # ej: https://tu-app.com
    link = f"{base_url}/seguimiento/{codigo}"

    return f"""✅ Solicitud registrada correctamente.

Hola {nombre}, tu solicitud fue recibida.

📌 Código de seguimiento: {codigo}
📍 Comunidad: {comunidad_txt}
📝 Tipo de solicitud: {tipo_txt}
📄 Estado actual: {estado}

👉 Sigue tu solicitud aquí:
{link}

Guarda este código o el enlace para ver el avance cuando quieras.""".strip()


def crear_solicitud(datos: dict, embedding: list | None = None) -> str:
    """
    Crea una solicitud y devuelve solo el código.

    datos:
    - nombre
    - dni
    - contacto
    - comunidad
    - tipo_proyecto
    - modalidad   (convocatoria | voluntariado)
    - descripcion
    - facultades_sugeridas
    - explicacion
    - telefono
    """

    codigo = _nuevo_codigo()
    c = _get_client()

    fac_json = json.dumps(
        datos.get("facultades_sugeridas", []),
        ensure_ascii=False,
    )

    exp_json = json.dumps(
        datos.get("explicacion", []),
        ensure_ascii=False,
    )

    embedding_json = json.dumps(embedding or [0.0] * 384)

    # El número de WhatsApp viene como "telefono@s.whatsapp.net": dejamos solo los dígitos
    telefono_limpio = str(datos.get("telefono", "")).split("@")[0]
    modalidad = datos.get("modalidad", "convocatoria")

    if c:
        c.execute(
            """
            INSERT INTO solicitudes
                (codigo, telefono, nombre_solicitante, dni, numero_contacto, comunidad,
                 tipo_proyecto, descripcion, facultades_sugeridas, modalidad, estado)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'recibida')
            """,
            [
                codigo,
                telefono_limpio,
                _nombre_solicitante(datos),
                datos.get("dni", ""),
                datos.get("contacto", ""),
                datos.get("comunidad", ""),
                datos.get("tipo_proyecto", ""),
                datos.get("descripcion", ""),
                fac_json,
                modalidad,
            ],
        )

        comentario_inicial = (
            "Registrada vía WhatsApp — modalidad voluntariado (fuera de convocatoria)"
            if modalidad == "voluntariado"
            else "Registrada vía WhatsApp — modalidad convocatoria"
        )
        c.execute(
            """
            INSERT INTO historial_estados
                (codigo, estado_nuevo, comentario)
            VALUES (?, ?, ?)
            """,
            [
                codigo,
                "recibida",
                comentario_inicial,
            ],
        )

    else:
        solicitud = {
            "codigo": codigo,
            "telefono": telefono_limpio,
            "nombre_solicitante": _nombre_solicitante(datos),
            "dni": datos.get("dni", ""),
            "numero_contacto": datos.get("contacto", ""),
            "comunidad": datos.get("comunidad", ""),
            "tipo_proyecto": datos.get("tipo_proyecto", ""),
            "modalidad": modalidad,
            "descripcion": datos.get("descripcion", ""),
            "facultades_sugeridas": datos.get("facultades_sugeridas", []),
            "explicacion": datos.get("explicacion", []),
            "estado": "recibida",
            "creado_en": datetime.now().isoformat(),
            "embedding": embedding or [0.0] * 384,
        }

        _mem["solicitudes"].append(solicitud)

        _mem["historial"].append(
            {
                "codigo": codigo,
                "estado_nuevo": "recibida",
                "comentario": "Registrada vía WhatsApp",
                "fecha": datetime.now().isoformat(),
            }
        )

    return codigo


def crear_solicitud_detalle(datos: dict, embedding: list | None = None) -> dict:
    """
    Crea una solicitud y devuelve un objeto completo para el agente o webhook.
    """

    codigo = crear_solicitud(datos, embedding)

    nombre = _nombre_solicitante(datos)
    comunidad = datos.get("comunidad", "")
    tipo_proyecto = datos.get("tipo_proyecto", "")
    estado = "recibida"

    mensaje = _mensaje_confirmacion_solicitud(
        nombre=nombre,
        codigo=codigo,
        comunidad=comunidad,
        tipo_proyecto=tipo_proyecto,
        estado=estado,
    )

    return {
        "ok": True,
        "codigo": codigo,
        "estado": estado,
        "nombre": nombre,
        "comunidad": comunidad,
        "tipo_proyecto": tipo_proyecto,
        "mensaje": "Solicitud registrada correctamente",
        "mensaje_usuario": mensaje,
    }


def crear_solicitud_y_mensaje(datos: dict, embedding: list | None = None) -> str:
    """
    Crea la solicitud y devuelve directamente el mensaje listo para WhatsApp.
    """
    resultado = crear_solicitud_detalle(datos, embedding)
    return resultado["mensaje_usuario"]


def consultar_estado(codigo: str) -> dict | None:
    codigo_normalizado = _normalizar_codigo(codigo)
    c = _get_client()

    if c:
        rs = c.execute(
            """
            SELECT
                codigo,
                comunidad,
                tipo_proyecto,
                estado,
                facultad_asignada,
                encargado
            FROM solicitudes
            WHERE codigo = ?
            """,
            [codigo_normalizado],
        )

        if not rs.rows:
            return None

        r = rs.rows[0]

        return {
            "codigo": r[0],
            "comunidad": r[1],
            "tipo_proyecto": r[2],
            "estado": r[3],
            "facultad_asignada": r[4],
            "encargado": r[5] or "",
        }

    for s in _mem["solicitudes"]:
        if _normalizar_codigo(s["codigo"]) == codigo_normalizado:
            return s

    return None


# Estados que cuentan como "cerrados" (no se muestran como pendientes)
_ESTADOS_CERRADOS = ("admitido", "rechazado")


def consultar_por_dni(dni: str) -> list[dict]:
    """Devuelve las solicitudes NO cerradas (ni admitidas ni rechazadas) de un DNI."""
    dni = str(dni or "").strip()
    c = _get_client()

    if c:
        rs = c.execute(
            """
            SELECT codigo, comunidad, tipo_proyecto, estado
            FROM solicitudes
            WHERE dni = ? AND estado NOT IN ('admitido', 'rechazado')
            ORDER BY creado_en DESC
            """,
            [dni],
        )
        return [
            {"codigo": r[0], "comunidad": r[1], "tipo_proyecto": r[2], "estado": r[3]}
            for r in rs.rows
        ]

    return [
        {"codigo": s["codigo"], "comunidad": s.get("comunidad", ""),
         "tipo_proyecto": s.get("tipo_proyecto", ""), "estado": s.get("estado", "")}
        for s in _mem["solicitudes"]
        if s.get("dni") == dni and s.get("estado") not in _ESTADOS_CERRADOS
    ]


# ---------- CONVOCATORIAS (plazos) ----------
def convocatoria_activa() -> dict | None:
    """Convocatoria abierta cuyo rango de fechas incluye hoy."""
    hoy = date.today().isoformat()
    c = _get_client()
    if c:
        rs = c.execute(
            """
            SELECT periodo, fecha_inicio, fecha_cierre
            FROM convocatorias
            WHERE estado = 'abierta' AND fecha_inicio <= ? AND fecha_cierre >= ?
            LIMIT 1
            """,
            [hoy, hoy],
        )
        if rs.rows:
            r = rs.rows[0]
            return {"periodo": r[0], "inicio": r[1], "cierre": r[2]}
        return None

    # fallback memoria
    for conv in _mem["convocatorias"]:
        if conv.get("estado") == "abierta" and conv["fecha_inicio"] <= hoy <= conv["fecha_cierre"]:
            return {"periodo": conv["periodo"], "inicio": conv["fecha_inicio"], "cierre": conv["fecha_cierre"]}
    return None


def proxima_convocatoria() -> dict | None:
    """La próxima convocatoria que abrirá (para avisar al usuario)."""
    hoy = date.today().isoformat()
    c = _get_client()
    if c:
        rs = c.execute(
            "SELECT periodo, fecha_inicio FROM convocatorias WHERE fecha_inicio > ? ORDER BY fecha_inicio ASC LIMIT 1",
            [hoy],
        )
        if rs.rows:
            return {"periodo": rs.rows[0][0], "inicio": rs.rows[0][1]}
        return None

    futuras = sorted(
        [cv for cv in _mem["convocatorias"] if cv["fecha_inicio"] > hoy],
        key=lambda x: x["fecha_inicio"],
    )
    if futuras:
        return {"periodo": futuras[0]["periodo"], "inicio": futuras[0]["fecha_inicio"]}
    return None


def guardar_mensaje(telefono: str, rol: str, contenido: str):
    c = _get_client()

    if c:
        c.execute(
            """
            INSERT INTO conversaciones
                (
                    telefono,
                    rol,
                    contenido
                )
            VALUES
                (
                    ?,
                    ?,
                    ?
                )
            """,
            [
                telefono,
                rol,
                contenido,
            ],
        )

    else:
        _mem["conversaciones"].append(
            {
                "telefono": telefono,
                "rol": rol,
                "contenido": contenido,
                "creado_en": datetime.now().isoformat(),
            }
        )


def historial_conversacion(telefono: str, limite: int = 12) -> list[dict]:
    c = _get_client()
 
    if c:
        rs = c.execute(
            """
            SELECT rol, contenido
            FROM (
                SELECT *
                FROM conversaciones
                WHERE telefono = ?
                ORDER BY id DESC
                LIMIT ?
            )
            ORDER BY id ASC
            """,
            [
                telefono,
                limite,
            ],
        )

        return [
            {
                "rol": r[0],
                "contenido": r[1],
            }
            for r in rs.rows
        ]

    mensajes = [
        {
            "rol": m["rol"],
            "contenido": m["contenido"],
        }
        for m in _mem["conversaciones"]
        if m["telefono"] == telefono
    ]

    return mensajes[-limite:]