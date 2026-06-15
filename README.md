# yachay-app 🧠

> Backend principal del sistema Yachay UNCP.
> Agente conversacional por WhatsApp para Proyección Social de la Universidad Nacional del Centro del Perú.
> **Hackatón Transformagob 2026**

**Desarrollado por [devchuz](https://github.com/devchuz) · jhonrinconroman@gmail.com**

---

## ¿Qué hace este repo?

Es el cerebro del sistema. Recibe mensajes de WhatsApp vía Evolution API, los procesa con un agente LangGraph + LLM, clasifica la necesidad del comunero con embeddings (`multilingual-e5-small`) y guarda todo en Turso (libSQL). También expone los endpoints REST que consumen el dashboard y la página de seguimiento.

---

## Estructura

```
yachay-app/
├── app/
│   ├── main.py               ← FastAPI + sistema de colas asyncio
│   ├── agent/
│   │   └── yachay_agent.py   ← LangGraph ReAct + 6 tools + SYSTEM_PROMPT
│   ├── core/
│   │   ├── clasificador.py   ← e5-small + coseno similarity
│   │   ├── db.py             ← cliente Turso + fallback memoria
│   │   └── config.py         ← variables de entorno
│   └── tools/
│       └── yachay_tools.py   ← lógica de negocio (orientar, derivar, crear, consultar)
└── seeds/
    ├── facultades.json           ← catálogo de las 38 carreras UNCP con keywords y ejemplos
    ├── facultades_embeddings.npy ← embeddings precalculados (384 dim)
    └── facultades_index.json     ← índice para búsqueda por similitud
```

---

## Stack

| | |
|---|---|
| Lenguaje | Python 3.12 |
| Framework | FastAPI |
| Agente | LangGraph `create_react_agent` |
| LLM primario | Groq `openai/gpt-oss-20b` |
| LLM respaldo | Gemini 2.0 Flash |
| Embeddings | `intfloat/multilingual-e5-small` (384 dim) |
| Base de datos | Turso (libSQL) |
| WhatsApp gateway | Evolution API |
| Colas | `asyncio.Queue` + `asyncio.Semaphore` |

---

## Flujo del webhook

```
WhatsApp
    │
    ▼
Evolution API → POST /webhook/whatsapp
    │
    ▼ (200 OK inmediato)
asyncio.Queue por teléfono  (FIFO, max 10 mensajes por usuario)
    │
    ▼
asyncio.Semaphore(4)        (max 4 LLM calls simultáneas)
    │
    ▼
run_in_executor → yachay_agent.responder()
    │
    ├── Primer contacto + saludo → Plantilla bienvenida
    │
    └── LangGraph ReAct loop
          ├── orientar_servicios()
          ├── derivar(descripcion) → clasificador e5-small
          ├── crear_solicitud(...)
          │     ├── ¿convocatoria activa? → modalidad = "convocatoria"
          │     └── ¿sin convocatoria?   → modalidad = "voluntariado"
          ├── consultar_estado(codigo)
          ├── consultar_por_dni(dni)
          └── consultar_convocatoria()
    │
    ▼
Evolution API → WhatsApp del comunero
```

### Sistema de colas

El webhook responde `200 OK` inmediatamente (Evolution no reintenta). El procesamiento ocurre en background:

- **Cola FIFO por teléfono**: mensajes del mismo usuario procesados en orden, uno por uno. Evita respuestas desordenadas si el usuario escribe rápido.
- **Semáforo global `(4)`**: máximo 4 conversaciones procesando LLM al mismo tiempo. Ajustar según cuota de Groq.
- **Worker que se auto-destruye**: si un usuario no escribe en 60 segundos, la coroutine termina sola. Sin memory leak.
- **Cola con `maxsize=10`**: si alguien spamea, los mensajes extras se descartan silenciosamente.

Para monitorear en vivo: `GET /health` devuelve `colas_activas` y `sem_disponible`.

---

## Lógica de convocatoria vs voluntariado

Cada vez que se llama `crear_solicitud`, el sistema consulta la tabla `convocatorias` en Turso:

```
¿Hay convocatoria con estado='abierta' y fecha_inicio <= hoy <= fecha_cierre?
    │
    ├── SÍ → modalidad = "convocatoria"
    │         Registro formal. Mensaje al usuario: "Registrada en convocatoria 2026-I"
    │
    └── NO → modalidad = "voluntariado"
              Mensaje al usuario: "Proyección Social cerró el registro formal.
              La próxima convocatoria abre el [fecha]. Igual te registramos
              como postulación a voluntariado."
```

El dashboard muestra la `modalidad` de cada solicitud para que la secretaría las gestione diferenciado.

---

## Endpoints

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/health` | Estado del sistema, colas activas, slots disponibles |
| `POST` | `/webhook/whatsapp` | Entrada de Evolution API |
| `POST` | `/chat` | Prueba del agente sin WhatsApp |
| `POST` | `/derivar` | Prueba directa del clasificador |
| `GET` | `/solicitudes` | Lista de solicitudes (para el dashboard) |
| `GET` | `/seguimiento/{codigo}` | Detalle de una solicitud por código |
| `GET` | `/convocatorias` | Lista de convocatorias |
| `POST` | `/convocatorias` | Crear o editar una convocatoria (upsert por periodo) |
| `GET` | `/convocatoria-activa` | La que el bot usa para validar el plazo |
| `POST` | `/notificar` | Envía WhatsApp según estado (dashboard → comunero) |

---

## Variables de entorno

Crear `.env` en la raíz de `yachay-app/`:

```env
# Turso
TURSO_DATABASE_URL=libsql://yachay-uncp-<usuario>.aws-us-east-1.turso.io
TURSO_AUTH_TOKEN=<token>

# LLM
GROQ_API_KEY=<key>
GEMINI_API_KEY=<key>
GEMINI_MODEL=gemini-2.0-flash

# Evolution API (WhatsApp)
EVOLUTION_URL=https://evolution-api-production-xxxx.up.railway.app
EVOLUTION_API_KEY=<key>
EVOLUTION_INSTANCE=1111

# URLs públicas
SEGUIMIENTO_URL=https://yachay-seguimiento.vercel.app
FORMULARIO_URL=https://forms.gle/<id>

# Clasificador
UMBRAL_FACULTAD=0.84
```

> `.env` está en `.gitignore`. Nunca subir el token de Turso al repo.

---

## Correr en local

```bash
# 1. Crear entorno virtual
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/Mac

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Arrancar
uvicorn app.main:app --reload --port 8000
```

Al arrancar debe aparecer:
```
[clasificador] embeddings cargados desde .../seeds/facultades_embeddings.npy
[agente] LangGraph activo con Groq.
[yachay] listo. Agente en modo: langgraph | Turso: True
```

Luego exponer con ngrok para el webhook de Evolution:
```bash
ngrok http 8000
# Copiar https://XXXX.ngrok-free.app
# En Evolution → Webhook: https://XXXX.ngrok-free.app/webhook/whatsapp
# Evento: solo MESSAGES_UPSERT
```

> ngrok free cambia la URL al reiniciar. Actualizar el webhook en Evolution cada vez.

---

## Despliegue

El repo incluye `Dockerfile`. Opción recomendada: **Hugging Face Spaces** (tier gratis, Docker, CPU suficiente para e5-small).

```
# En HF Spaces:
# 1. Crear Space tipo "Docker"
# 2. Subir el repo (o conectar GitHub)
# 3. Configurar variables de entorno en Settings
# 4. URL pública fija → apuntar webhook de Evolution aquí
```

Alternativa: GCP Cloud Run (scale-to-zero, recomendado para producción real post-hackathon).

---

## Base de datos

Las tablas las gestiona este repo pero son compartidas con los otros dos repos vía Turso:

```sql
solicitudes       -- registro principal
historial_estados -- auditoría de cambios de estado
conversaciones    -- memoria del agente por teléfono
convocatorias     -- periodos y fechas de apertura/cierre
```

Si migraste desde una versión anterior sin la columna `encargado`:
```sql
ALTER TABLE solicitudes ADD COLUMN encargado TEXT DEFAULT '';
```

---

## Repos relacionados

| Repo | Descripción |
|---|---|
| [`yachay-dashboard`](https://github.com/devchuz/yachay-dashboard) | Panel interno para la secretaría (Remix + Clerk) |
| [`yachay-seguimiento`](https://github.com/devchuz/yachay-seguimiento) | Página pública de seguimiento para el comunero (Remix) |

Los 3 repos comparten la misma base Turso (`TURSO_DATABASE_URL`).