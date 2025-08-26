# 1. Temel imaj olarak resmi Python imajını kullan
FROM python:3.11-slim

# 2. Gerekli sistem bağımlılıkları (sadece HTTP server için)
RUN apt-get update && apt-get install -y \
    curl \
    ca-certificates \
    --no-install-recommends && rm -rf /var/lib/apt/lists/*

# 3. Ortam değişkenleri
ENV PIP_NO_CACHE_DIR=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# 4. Çalışma dizini oluştur ve ayarla
WORKDIR /app

# 5. Bağımlılıkları kopyala ve kur
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 6. Uygulama kodunun tamamını kopyala
COPY . .

# 7. Gerekli dizinleri oluştur
RUN mkdir -p public/collaborator-sessions

# 8. Uygulamanın çalışacağı portu belirt
EXPOSE 8080

# 9. Python ile uygulamayı başlat
CMD ["python", "mcp_server_streaming_real.py"]


