# Use a Python image with uv pre-installed
FROM ghcr.io/astral-sh/uv:python3.12-alpine

# Install the project into `/app`
WORKDIR /app

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1

# Copy from the cache instead of linking since it's a mounted volume
ENV UV_LINK_MODE=copy

# Copy project configuration
COPY pyproject.toml .

# Install dependencies using the lockfile if available
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev || uv sync --no-dev

# Copy project files
COPY . /app

# Create necessary directories
RUN mkdir -p public/collaborator-sessions

# Place executables in the environment at the front of the path
ENV PATH="/app/.venv/bin:$PATH"

# Set transport mode to HTTP for container deployment
ENV TRANSPORT=http

# Expose port 8081 for Smithery
EXPOSE 8081

# Set default PORT for Smithery compatibility
ENV PORT=8081

# Reset the entrypoint, don't invoke `uv`
ENTRYPOINT []

# Run the MCP server in HTTP mode
CMD ["python", "src/main.py"]


