# YÖK Akademik MCP Server - Smithery Deployment
FROM python:3.10-slim-bullseye

# Install system dependencies including Chrome
RUN apt-get update && apt-get install -y \
    chromium \
    chromium-driver \
    wget \
    unzip \
    xvfb \
    xauth \
    && rm -rf /var/lib/apt/lists/*

# Create symlinks for Chrome compatibility
RUN ln -s /usr/bin/chromium /usr/bin/google-chrome \
    && ln -s /usr/bin/chromedriver /usr/local/bin/chromedriver

# Set Chrome environment variables
ENV CHROME_BIN=/usr/bin/chromium
ENV CHROME_DRIVER_PATH=/usr/bin/chromedriver
ENV CHROME_NO_SANDBOX=true
ENV CHROME_DISABLE_DEV_SHM=true

# Set working directory
WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p /app/public/collaborator-sessions \
    && mkdir -p /app/logs

# Set permissions
RUN chmod +x mcp_server_streaming_real.py

# Environment variables for production
ENV NODE_ENV=production
ENV PYTHON_ENV=production
ENV MCP_SERVER_PORT=5000
ENV MCP_SERVER_HOST=0.0.0.0
ENV HEADLESS_MODE=true

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import requests; requests.get('http://localhost:5000/ready')" || exit 1

# Expose port
EXPOSE 5000

# Start the MCP server
CMD ["python", "-u", "mcp_server_streaming_real.py"]