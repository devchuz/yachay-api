FROM python:3.11-slim

WORKDIR /app

# Dependencias del sistema (por si alguna lib las necesita)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Instalar dependencias de Python primero (mejor caché)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto del código
COPY . .

# HF Spaces espera el puerto 7860
EXPOSE 7860

# Arrancar uvicorn en el puerto 7860
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]