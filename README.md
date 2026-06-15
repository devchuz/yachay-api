# Yachay App — Backend (agente + clasificador)

FastAPI con el clasificador de derivación, el agente Yachay y el webhook de WhatsApp.

## Correr local (Windows / Mac / Linux)

```bash
python -m venv .venv
# Windows:  .venv\Scripts\activate
# Mac/Linux: source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env       # edita .env con tus credenciales (Windows: copy)
uvicorn app.main:app --reload --port 8000
```

La PRIMERA vez descarga el modelo e5-small (~120MB) — normal, solo una vez.
Cuando veas "Application startup complete", abre http://localhost:8000/docs

## Niveles (cada uno funciona solo)

1. **Solo clasificador** (sin nada más): POST /derivar con {"texto":"..."}
   → ML real funcionando. Corre las evals: `python ../evals/run_evals.py`
2. **Agente por chat** (sin WhatsApp): POST /chat con {"mensaje":"...","telefono":"519..."}
   - Sin GEMINI_API_KEY → modo fallback de reglas (igual demuestra el flujo + clasificador)
   - Con GEMINI_API_KEY → agente LangGraph completo con memoria
3. **WhatsApp real**: llenar EVOLUTION_* en .env y apuntar el webhook de Evolution a
   POST /webhook/whatsapp (necesita URL pública: ngrok en dev).

## Endpoints
- GET  /health               estado del sistema
- POST /derivar               clasificador (ML directo)
- POST /chat                  probar el agente
- GET  /solicitudes           lista para el dashboard
- GET  /seguimiento/{codigo}  estado de una solicitud
- POST /webhook/whatsapp      entrada de Evolution API
