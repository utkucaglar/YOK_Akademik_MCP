FROM python:3.11-slim

# Sistem bağımlılıkları (chromium + driver + fontlar)
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    chromium-driver \
    fonts-dejavu \
    ca-certificates \
    curl \
 && rm -rf /var/lib/apt/lists/*

# Python bağımlılıkları
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

# Uygulama kodu
COPY . /app

# Selenium için Chromium binary yolu
ENV CHROME_BIN=/usr/bin/chromium
ENV CHROME_OPTIONS="--headless=new --no-sandbox --disable-dev-shm-usage"

# Server konfigürasyonu
ENV PYTHONUNBUFFERED=1 
ENV PYTHONPATH=.
ENV MCP_SERVER_HOST=0.0.0.0
ENV MCP_SERVER_PORT=8000
ENV HEADLESS_MODE=true
ENV NODE_ENV=production

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD curl -f http://localhost:8000/ready || exit 1

EXPOSE 8000

# Graceful shutdown için
STOPSIGNAL SIGTERM

CMD ["python", "-m", "server"]