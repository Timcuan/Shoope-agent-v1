FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

WORKDIR /app

# Install system dependencies (if needed, e.g., for building some C extensions or sqlite)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Install pip and the project itself
# Copy only the files needed for installation to cache the layer
COPY pyproject.toml .
# We can install the dependencies by installing the project
RUN pip install --no-cache-dir .

# Copy the rest of the application
COPY src/ src/
COPY alembic.ini .
COPY alembic/ alembic/
COPY start.sh .

# Create data directory for sqlite database if not using volume
RUN mkdir -p data && chmod +x start.sh

# Default command (overridden in docker-compose)
CMD ["./start.sh", "api"]
