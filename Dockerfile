# 1. Temel imaj olarak resmi Python imajını kullan
FROM python:3.11-slim

# 2. Chrome ve ChromeDriver için gerekli bağımlılıkları kur
# Bu adımlar projenizin Selenium kullanması nedeniyle kritiktir.
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    gnupg \
    unzip \
    ca-certificates \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libx11-6 \
    libx11-xcb1 \
    libxcb1 \
    libxcomposite1 \
    libxcursor1 \
    libxdamage1 \
    libxi6 \
    libxrandr2 \
    libxrender1 \
    libxss1 \
    libxtst6 \
    --no-install-recommends && rm -rf /var/lib/apt/lists/*

# 3. Google Chrome'u kur
RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/google-linux-signing-keyring.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-linux-signing-keyring.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# 4. Chrome versiyonuna uygun ChromeDriver'ı kur
RUN set -eux; \
    CHROME_VERSION=$(google-chrome --version | grep -oE '[0-9.]+' | head -1); \
    CHROME_MAJOR=$(echo "$CHROME_VERSION" | cut -d. -f1); \
    DRIVER_VERSION=$(curl -sS https://chromedriver.storage.googleapis.com/LATEST_RELEASE); \
    wget -q https://chromedriver.storage.googleapis.com/${DRIVER_VERSION}/chromedriver_linux64.zip; \
    unzip -q chromedriver_linux64.zip -d /usr/local/bin/; \
    rm chromedriver_linux64.zip; \
    chmod +x /usr/local/bin/chromedriver

# 5. Ortam değişkenleri (Selenium için)
ENV CHROME_BINARY=/usr/bin/google-chrome \
    CHROMEDRIVER_PATH=/usr/local/bin/chromedriver \
    PIP_NO_CACHE_DIR=1 \
    PYTHONUNBUFFERED=1

# 6. Çalışma dizini oluştur ve ayarla
WORKDIR /app

# 7. Bağımlılıkları kopyala ve kur
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 8. Uygulama kodunun tamamını kopyala
COPY . .

# 9. Uygulamanın çalışacağı portu belirt
EXPOSE 8080

# 10. Python ile uygulamayı başlat (Gunicorn yerine doğrudan Python kullanımı)
CMD ["python", "simple_mcp_server.py"]


