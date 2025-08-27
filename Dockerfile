# Use standard Python image
FROM python:3.11-slim

# Install the project into `/app`
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    ca-certificates \
    --no-install-recommends && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies first (for better layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy only necessary project files
COPY src/ ./src/
COPY smithery.yaml .
COPY mcp_adapter.py .

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

# No custom entrypoint needed

# Run the simple MCP server directly
CMD ["python", "src/simple_server.py"]


