"""Configuración central. Lee de variables de entorno."""
import os
from dotenv import load_dotenv

load_dotenv()

# LLM
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")

# Turso
TURSO_DATABASE_URL = os.getenv("TURSO_DATABASE_URL", "")
TURSO_AUTH_TOKEN = os.getenv("TURSO_AUTH_TOKEN", "")

# Evolution API (WhatsApp)
EVOLUTION_URL = os.getenv("EVOLUTION_URL", "").rstrip("/")
EVOLUTION_API_KEY = os.getenv("EVOLUTION_API_KEY", "")

EVOLUTION_INSTANCE = os.getenv("EVOLUTION_INSTANCE", "yachay")

# Langfuse (opcional)
LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY", "")
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY", "")
LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")

# Modelo de embeddings
EMBED_MODEL = "intfloat/multilingual-e5-small"

# Umbral para sugerir que una facultad es relevante (clasificador)
UMBRAL_FACULTAD = float(os.getenv("UMBRAL_FACULTAD", "0.84"))

# Link de seguimiento
SEGUIMIENTO_URL = os.getenv("SEGUIMIENTO_URL", "http://localhost:5173")

FORMULARIO_URL = os.getenv("FORMULARIO_URL", "https://forms.gle/tu-formulario")