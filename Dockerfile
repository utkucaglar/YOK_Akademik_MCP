FROM python:3.11-slim

# Sistem bağımlılıkları (chromium + driver + fontlar)
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    chromium-driver \
    fonts-dejavu \
    ca-certificates \
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
# Headless için tipik flag'ler
ENV CHROME_OPTIONS="--headless=new --no-sandbox --disable-dev-shm-usage"

ENV PYTHONUNBUFFERED=1 PYTHONPATH=.
EXPOSE 8000

CMD ["python", "-m", "server"]