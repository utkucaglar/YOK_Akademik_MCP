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

# 9. Comprehensive test ve minimal server'ı başlat
RUN python -c "print('✅ Python test successful'); import http.server; print('✅ HTTP server import successful'); import json; print('✅ JSON import successful'); import socket; print('✅ Socket import successful'); print('🎉 All imports successful')"

# 10. Test ultra-simple server functionality
RUN python -c "import ultra_simple; print('✅ Ultra-simple server imported successfully')"

# 11. Ultra-simple server - single file, no complexity
CMD ["python", "-u", "ultra_simple.py"]


