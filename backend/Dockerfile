# Stage 1: Builder - instala dependencias
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# libxmlsec1-dev + pkg-config: python3-saml (SAML SSO) compila xmlsec
# cuando no hay wheel prebuilt para la plataforma.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       build-essential libpq-dev libxmlsec1-dev pkg-config \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/
RUN pip install --upgrade pip && pip install -r requirements.txt

# Stage 2: Runtime - imagen final ligera
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=config.settings

WORKDIR /app

# Runtime: libpq + libxmlsec1 (firma/validación SAML), sin toolchain
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 libxmlsec1 curl \
    && rm -rf /var/lib/apt/lists/*

# Copiar paquetes instalados del builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copiar código
COPY . /app/

# Crear usuario no-root
RUN useradd -m -u 1000 django && chown -R django:django /app
USER django

EXPOSE 8000

# Healthcheck (endpoint público; /api/auth/me/ exige auth y siempre da 401)
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/api/health/ || exit 1

# Daphne (ASGI): sirve HTTP y WebSockets (Channels). WSGI no soportaría WS.
CMD ["daphne", "--bind", "0.0.0.0", "--port", "8000", "config.asgi:application"]
