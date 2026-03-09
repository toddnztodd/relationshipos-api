FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create persistent data directory for SQLite
RUN mkdir -p /app/data

# Default environment variables (override at deploy time)
ENV DATABASE_URL=sqlite+aiosqlite:///./data/relationshipos.db
ENV JWT_SECRET_KEY=change-me-in-production
ENV CORS_ORIGINS=*
ENV APP_NAME=RelationshipOS
ENV APP_VERSION=1.0.0
ENV PORT=8000

# Expose port (Render/Railway/Fly read $PORT)
EXPOSE ${PORT}

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Start: seed database then run server
# The $PORT variable is respected by Render, Railway, and Fly.io
CMD python seed_data.py && uvicorn app.main:app --host 0.0.0.0 --port ${PORT}
