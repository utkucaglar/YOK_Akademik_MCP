# YÖK Akademik MCP Server - Smithery Deployment
FROM python:3.10-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Chromium and ChromeDriver (Debian packages - more reliable)
RUN apt-get update \
    && apt-get install -y \
        chromium \
        chromium-driver \
    && rm -rf /var/lib/apt/lists/*

# Create symlinks for compatibility
RUN ln -sf /usr/bin/chromium /usr/bin/google-chrome \
    && ln -sf /usr/bin/chromedriver /usr/local/bin/chromedriver

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV CHROME_BIN=/usr/bin/chromium
ENV CHROME_DRIVER_PATH=/usr/bin/chromedriver
ENV HEADLESS_MODE=true
ENV MCP_SERVER_HOST=0.0.0.0
ENV MCP_SERVER_PORT=5000
ENV NODE_ENV=production
ENV PYTHON_ENV=production
ENV CHROME_NO_SANDBOX=true
ENV CHROME_DISABLE_DEV_SHM=true

# Create app directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p public/collaborator-sessions && \
    mkdir -p logs && \
    chmod -R 755 public/ && \
    chmod -R 755 logs/

# Create non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser
RUN chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

# Start command
CMD ["python", "mcp_server_streaming_real.py"]
