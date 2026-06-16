# ============================================================
# evolution/Dockerfile
# Evolution API — WhatsApp gateway para Yachay UNCP
#
# Uso:
#   Local  → docker compose up (desde la raíz del repo)
#   Railway → detecta este Dockerfile con Root Directory = evolution
# ============================================================

FROM atendai/evolution-api:latest

# Crear directorios que serán montados como volumen
# Persiste la sesión de WhatsApp entre deploys y reinicios
RUN mkdir -p /evolution/instances /evolution/store

EXPOSE 8080

CMD ["node", "dist/main.js"]