# Use standard Python image
FROM python:3.11-slim

# Install the project into `/app`
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    ca-certificates \
    --no-install-recommends && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . /app

# Create necessary directories
RUN mkdir -p public/collaborator-sessions

# Set Python path
ENV PYTHONPATH="/app"

# Set transport mode to HTTP for container deployment
ENV TRANSPORT=http

# Expose port 8081 for Smithery
EXPOSE 8081

# Set default PORT for Smithery compatibility
ENV PORT=8081

# Reset the entrypoint, don't invoke `uv`
ENTRYPOINT []

# Add startup verification and run the simple MCP server
CMD ["sh", "-c", "echo '🚀 Container starting...' && python src/simple_server.py"]


