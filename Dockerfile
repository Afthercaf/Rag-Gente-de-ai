FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
ENV REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    ca-certificates \
    openssl \
    ffmpeg \
    && update-ca-certificates --fresh \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

RUN groupadd --system app \
    && useradd --system --gid app --home-dir /app --shell /usr/sbin/nologin app \
    && install -d -o app -g app /app/.cache

# Lista blanca: ningún .env, secreto, reporte, test o metadata Git entra a la imagen.
COPY --chown=app:app api2.py ./
COPY --chown=app:app config ./config
COPY --chown=app:app core ./core
COPY --chown=app:app documents ./documents
COPY --chown=app:app prompts ./prompts
COPY --chown=app:app providers ./providers
COPY --chown=app:app routers ./routers
COPY --chown=app:app schemas ./schemas
COPY --chown=app:app services ./services
COPY --chown=app:app src ./src
COPY --chown=app:app utils ./utils

USER app
EXPOSE 8000

CMD ["uvicorn", "api2:app", "--host", "0.0.0.0", "--port", "8000", "--no-server-header"]
